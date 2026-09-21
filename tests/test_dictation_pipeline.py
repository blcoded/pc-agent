"""Unit tests for DictationProcessor pipeline coordinator and state machine."""

from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock

import numpy as np

from voice_agent.app.lifecycle import DictationState
from voice_agent.audio.recorder import AudioRecorder
from voice_agent.clipboard.manager import ClipboardManager, SimulatedClipboardBackend
from voice_agent.dictation.formatter import DictationFormatter
from voice_agent.dictation.inserter import InsertionResult, InsertionStatus, TextInserter
from voice_agent.dictation.normalizer import TextNormalizer
from voice_agent.dictation.processor import DictationProcessor
from voice_agent.storage.database import DatabaseManager
from voice_agent.stt.engine import SpeechToTextEngine


class MockRecorder(AudioRecorder):
    """Mock AudioRecorder returning predictable audio buffers."""

    def __init__(self, audio_to_return: np.ndarray) -> None:
        self.audio_to_return = audio_to_return
        self._is_rec = False

    @property
    def is_recording(self) -> bool:
        return self._is_rec

    def start_recording(self, device_id: int | None = None) -> None:
        self._is_rec = True

    def stop_recording(self) -> np.ndarray:
        self._is_rec = False
        return self.audio_to_return

    def reset(self) -> None:
        self._is_rec = False


class MockSTTEngine(SpeechToTextEngine):
    """Mock STT engine for pipeline testing."""

    def __init__(self, transcript_to_return: str = "hello comma how are you question mark") -> None:
        self.transcript_to_return = transcript_to_return
        self.transcribe_called = 0

    def transcribe(self, audio: np.ndarray, language: str | None = None) -> str:
        self.transcribe_called += 1
        return self.transcript_to_return

    def is_loaded(self) -> bool:
        return True


class TestDictationPipeline(unittest.TestCase):
    """Test suite for end-to-end dictation pipeline and SQLite history recording."""

    def setUp(self) -> None:
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.test_dir.name) / "test_dictation.db"
        self.db = DatabaseManager(self.db_path)
        self.clip_backend = SimulatedClipboardBackend()
        self.clipboard = ClipboardManager(clipboard_module=self.clip_backend)

    def tearDown(self) -> None:
        self.db.close()
        self.test_dir.cleanup()

    def test_full_dictation_success_flow(self) -> None:
        """Verify complete pipeline: hotkey -> audio -> STT -> format -> normalize -> insert -> history."""
        # 16,000 samples = 1.0s audio
        synthetic_audio = np.ones(16000, dtype=np.float32) * 0.1
        recorder = MockRecorder(synthetic_audio)
        stt = MockSTTEngine("hello comma world period i'm dictating period")

        state_history: list[DictationState] = []
        inserted_texts: list[str] = []

        def mock_paste() -> bool:
            return True

        inserter = TextInserter(
            clipboard_manager=self.clipboard,
            get_window_func=lambda: (101, "Notepad", "Edit"),
            paste_func=mock_paste,
        )

        processor = DictationProcessor(
            recorder=recorder,
            stt_engine=stt,
            db=self.db,
            inserter=inserter,
            feedback_pause=0.01,
            on_state_change=state_history.append,
        )

        self.assertEqual(processor.state, DictationState.READY)

        # 1. Start listening
        processor.start_listening()
        self.assertEqual(processor.state, DictationState.LISTENING)
        self.assertTrue(recorder.is_recording)

        # 2. Stop listening -> processing begins
        processor.stop_listening()

        # Allow worker thread execution
        for _ in range(30):
            if processor.state == DictationState.READY:
                break
            time.sleep(0.05)

        # Verify state returned to READY
        self.assertEqual(processor.state, DictationState.READY)
        self.assertIn(DictationState.LISTENING, state_history)
        self.assertIn(DictationState.PROCESSING, state_history)
        self.assertIn(DictationState.TYPING, state_history)

        # Verify history written to database
        history = self.db.get_history()
        self.assertEqual(len(history), 1)
        record = history[0]

        self.assertEqual(record.mode, "dictation")
        self.assertEqual(record.raw_text, "hello comma world period i'm dictating period")
        self.assertEqual(record.processed_text, "Hello, world. I'm dictating.")
        self.assertEqual(record.status, "success")
        self.assertEqual(record.details.get("target_title"), "Notepad")
        self.assertAlmostEqual(record.details.get("duration_sec"), 1.0, places=1)

        processor.shutdown()

    def test_empty_audio_click_ignored(self) -> None:
        """Verify short/empty audio resets immediately to READY without STT."""
        empty_audio = np.zeros(0, dtype=np.float32)
        recorder = MockRecorder(empty_audio)
        stt = MockSTTEngine()

        processor = DictationProcessor(
            recorder=recorder,
            stt_engine=stt,
            db=self.db,
        )

        processor.start_listening()
        processor.stop_listening()

        time.sleep(0.05)

        self.assertEqual(processor.state, DictationState.READY)
        self.assertEqual(stt.transcribe_called, 0)
        self.assertEqual(len(self.db.get_history()), 0)

        processor.shutdown()

    def test_no_target_fallback_records_history(self) -> None:
        """Verify when target is invalid (e.g. desktop), fallback is recorded in history."""
        synthetic_audio = np.ones(16000, dtype=np.float32)
        recorder = MockRecorder(synthetic_audio)
        stt = MockSTTEngine("note on desktop")

        notifications: list[str] = []
        inserter = TextInserter(
            clipboard_manager=self.clipboard,
            get_window_func=lambda: (50, "Desktop", "Progman"),
            on_no_target=lambda txt, msg: notifications.append(txt),
        )

        processor = DictationProcessor(
            recorder=recorder,
            stt_engine=stt,
            db=self.db,
            inserter=inserter,
            feedback_pause=0.01,
        )

        processor.start_listening()
        processor.stop_listening()

        # Wait for processing and no-target pause
        for _ in range(30):
            if processor.state == DictationState.READY:
                break
            time.sleep(0.02)

        self.assertEqual(processor.state, DictationState.READY)
        self.assertEqual(len(notifications), 1)

        history = self.db.get_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].status, "no_target")
        self.assertEqual(history[0].processed_text, "Note on desktop")

        processor.shutdown()

    def test_error_handling_in_pipeline(self) -> None:
        """Verify pipeline recovers cleanly from unexpected transcription exception."""
        class FailingSTTEngine(SpeechToTextEngine):
            def transcribe(self, audio: np.ndarray, language: str | None = None) -> str:
                raise RuntimeError("STT Model Out of Memory")

            def is_loaded(self) -> bool:
                return True

        recorder = MockRecorder(np.ones(16000, dtype=np.float32))
        processor = DictationProcessor(
            recorder=recorder,
            stt_engine=FailingSTTEngine(),
            db=self.db,
            feedback_pause=0.01,
        )

        processor.start_listening()
        processor.stop_listening()

        for _ in range(30):
            if processor.state == DictationState.READY:
                break
            time.sleep(0.02)

        self.assertEqual(processor.state, DictationState.READY)
        history = self.db.get_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].status, "error")

        processor.shutdown()


if __name__ == "__main__":
    unittest.main()
