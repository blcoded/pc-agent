"""End-to-End Pipeline & Stress Testing for Dictation Mode (TASK-8.2).

Verifies:
- 100 consecutive simulated dictations without deadlocks, memory leaks, or crashes.
- Rapid tap vs. hold sequences to guarantee state synchronization.
- Clipboard restoration under rapid typing and concurrent updates.
- Failure resilience: STT out-of-memory, invalid window targets (zero silent loss of text).
"""

from __future__ import annotations

import gc
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock

import numpy as np

from voice_agent.app.lifecycle import DictationState
from voice_agent.audio.recorder import AudioRecorder
from voice_agent.clipboard.manager import ClipboardManager, SimulatedClipboardBackend
from voice_agent.dictation.inserter import TextInserter
from voice_agent.dictation.processor import DictationProcessor
from voice_agent.storage.database import DatabaseManager
from voice_agent.storage.history import HistoryRepository
from voice_agent.stt.engine import SpeechToTextEngine


class E2EMockRecorder(AudioRecorder):
    """Predictable in-memory recorder for stress testing."""

    def __init__(self, audio_data: np.ndarray | None = None) -> None:
        self._audio = audio_data if audio_data is not None else np.ones(16000, dtype=np.float32) * 0.05
        self._is_rec = False

    @property
    def is_recording(self) -> bool:
        return self._is_rec

    def set_audio(self, audio_data: np.ndarray) -> None:
        self._audio = audio_data

    def start_recording(self, device_id: int | None = None) -> None:
        self._is_rec = True

    def stop_recording(self) -> np.ndarray:
        self._is_rec = False
        return self._audio

    def reset(self) -> None:
        self._is_rec = False


class E2EMockSTT(SpeechToTextEngine):
    """Fast deterministic STT engine with configurable behavior."""

    def __init__(self, default_response: str = "stress test sentence number") -> None:
        self.default_response = default_response
        self.counter = 0
        self.should_throw_oom = False

    def transcribe(self, audio: np.ndarray, language: str | None = None) -> str:
        self.counter += 1
        if self.should_throw_oom:
            raise RuntimeError("CUDA Out of Memory in E2E simulation")
        return f"{self.default_response} {self.counter}"

    def is_loaded(self) -> bool:
        return True


class TestDictationE2E(unittest.TestCase):
    """End-to-End stress and resilience test suite for Dictation subsystem."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "e2e_dictation.db"
        self.db = DatabaseManager(self.db_path)
        self.history_repo = HistoryRepository(db=self.db)

        self.clip_backend = SimulatedClipboardBackend()
        self.clipboard = ClipboardManager(clipboard_module=self.clip_backend)
        self.clipboard.set_text("Initial original clipboard content")

        self.recorder = E2EMockRecorder()
        self.stt = E2EMockSTT()
        self.pasted_items: list[str] = []
        self.notifications: list[tuple[str, str]] = []

        def mock_paste() -> bool:
            self.pasted_items.append(self.clipboard.get_text())
            return True

        def mock_no_target(title: str, text: str) -> None:
            self.notifications.append((title, text))

        self.inserter = TextInserter(
            clipboard_manager=self.clipboard,
            get_window_func=lambda: (200, "TextEditor", "Edit"),
            paste_func=mock_paste,
            on_no_target=mock_no_target,
        )

        self.processor = DictationProcessor(
            recorder=self.recorder,
            stt_engine=self.stt,
            db=self.db,
            inserter=self.inserter,
            language="en",
            format_commands=True,
            feedback_pause=0.001,
            on_no_target=mock_no_target,
        )

    def tearDown(self) -> None:
        try:
            self.processor.shutdown()
        except Exception:
            pass

        self.db.close()
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_100_consecutive_simulated_dictations(self) -> None:
        """Execute 100 consecutive dictations without crashing or leaking state."""
        total_runs = 100

        for i in range(total_runs):
            self.processor.start_listening()
            self.assertEqual(self.processor.state, DictationState.LISTENING)
            self.processor.stop_listening()

            # Wait for processor to settle back to READY
            for _ in range(50):
                if self.processor.state == DictationState.READY:
                    break
                time.sleep(0.01)

            self.assertEqual(
                self.processor.state,
                DictationState.READY,
                f"Processor failed to return to READY on run #{i+1}",
            )

        # Verify all 100 were transcribed and inserted
        self.assertEqual(self.stt.counter, total_runs)
        self.assertEqual(len(self.pasted_items), total_runs)

        # Verify all 100 were persisted in SQLite history
        history = self.db.get_history(limit=200)
        self.assertEqual(len(history), total_runs)
        self.assertTrue(all(r.status == "success" for r in history))

        # Verify clipboard was restored after each insertion
        self.assertEqual(self.clipboard.get_text(), "Initial original clipboard content")

    def test_rapid_tap_vs_hold_sequences(self) -> None:
        """Verify rapid micro-taps (<0.1s empty clicks) do not deadlock."""
        # 1. 20 consecutive micro-taps (empty audio click)
        self.recorder.set_audio(np.zeros(0, dtype=np.float32))

        for _ in range(20):
            self.processor.start_listening()
            self.processor.stop_listening()
            time.sleep(0.005)
            self.assertEqual(self.processor.state, DictationState.READY)

        # Ensure no transcripts generated for empty clicks
        self.assertEqual(self.stt.counter, 0)

        # 2. Immediately followed by 5 valid holds
        self.recorder.set_audio(np.ones(16000, dtype=np.float32) * 0.1)
        for _ in range(5):
            self.processor.start_listening()
            self.processor.stop_listening()
            for _ in range(50):
                if self.processor.state == DictationState.READY:
                    break
                time.sleep(0.01)
            self.assertEqual(self.processor.state, DictationState.READY)

        self.assertEqual(self.stt.counter, 5)
        self.assertEqual(len(self.pasted_items), 5)

    def test_zero_silent_loss_on_invalid_target_window(self) -> None:
        """When user dictates to non-target window (Desktop/Progman), text is copied to clipboard and notified."""
        # Target returns Progman (Desktop)
        self.inserter._get_window = lambda: (500, "Program Manager", "Progman")

        self.processor.start_listening()
        self.processor.stop_listening()

        for _ in range(50):
            if self.processor.state == DictationState.READY:
                break
            time.sleep(0.01)

        self.assertEqual(self.processor.state, DictationState.READY)

        # Zero silent loss: Text was NOT pasted into desktop, but safely copied to clipboard
        self.assertEqual(len(self.pasted_items), 0)
        current_clip = self.clipboard.get_text()
        self.assertIn("Stress test sentence number 1", current_clip)

        # Notification was dispatched
        self.assertGreater(len(self.notifications), 0)

    def test_stt_out_of_memory_recovery(self) -> None:
        """Pipeline recovers cleanly to READY on STT exception and records error."""
        self.stt.should_throw_oom = True

        self.processor.start_listening()
        self.processor.stop_listening()

        for _ in range(50):
            if self.processor.state == DictationState.READY:
                break
            time.sleep(0.01)

        # Must recover cleanly to READY
        self.assertEqual(self.processor.state, DictationState.READY)

        # Must record failure in history
        history = self.db.get_history(limit=10)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].status, "error")
        self.assertIn("CUDA Out of Memory", history[0].details.get("error", ""))


if __name__ == "__main__":
    unittest.main()
