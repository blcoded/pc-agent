"""Comprehensive integration tests verifying cross-subsystem execution.

Tests interaction between:
- Dictation processor, STT engine, formatting, text inserter, and SQLite history
- Control command router, parser, validator, risk classifier, execution, and SQLite history
- Settings configuration propagation to pipelines
- State transitions and floating overlay events
"""

from __future__ import annotations

import gc
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock

import numpy as np

from voice_agent.app.config import AppConfig, ControlConfig, DictationConfig
from voice_agent.app.lifecycle import ControlState, DictationState
from voice_agent.audio.recorder import AudioRecorder
from voice_agent.clipboard.manager import ClipboardManager, SimulatedClipboardBackend
from voice_agent.control.actions.base import Action, ActionResult
from voice_agent.control.command_router import CommandExecutionReport, CommandRouter
from voice_agent.control.models import ActionType, RiskLevel
from voice_agent.dictation.inserter import TextInserter
from voice_agent.dictation.processor import DictationProcessor
from voice_agent.storage.database import DatabaseManager
from voice_agent.storage.history import HistoryRepository
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
    """Deterministic STT engine returning preconfigured responses."""

    def __init__(self, response: str = "hello comma world period") -> None:
        self.response = response
        self.call_count = 0

    def transcribe(self, audio: np.ndarray, language: str | None = None) -> str:
        self.call_count += 1
        return self.response

    def is_loaded(self) -> bool:
        return True


class MockCustomAction(Action):
    """Configurable mock action for router testing."""

    def __init__(self, action_type: ActionType, return_success: bool = True) -> None:
        self._type = action_type
        self.return_success = return_success
        self.call_history: list[dict] = []

    @property
    def action_type(self) -> ActionType:
        return self._type

    def execute(self, params: dict) -> ActionResult:
        self.call_history.append(params)
        if self.return_success:
            return ActionResult(success=True, output=f"Executed {self._type.value}")
        return ActionResult(success=False, output=None, error_message=f"Failed {self._type.value}")


class TestFullSystemIntegration(unittest.TestCase):
    """End-to-end integration test suite across all subsystems."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_integration.db"
        self.db = DatabaseManager(self.db_path)
        self.history_repo = HistoryRepository(db=self.db)

        # Mock clipboard manager
        self.clip_backend = SimulatedClipboardBackend()
        self.clipboard = ClipboardManager(clipboard_module=self.clip_backend)
        self._active_processors: list[DictationProcessor] = []

    def tearDown(self) -> None:
        for p in self._active_processors:
            try:
                p.shutdown()
            except Exception:
                pass
        self._active_processors.clear()

        self.db.close()
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_dictation_end_to_end_flow(self) -> None:
        """Audio -> STT -> Format -> Insert -> History DB flow."""
        audio_data = np.ones(16000, dtype=np.float32) * 0.1
        recorder = MockRecorder(audio_data)
        stt = MockSTTEngine(response="hello comma how are you question mark")

        state_history: list[DictationState] = []
        pasted_texts: list[str] = []

        def mock_paste() -> bool:
            pasted_texts.append(self.clipboard.get_text())
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
            language="en",
            format_commands=True,
            feedback_pause=0.01,
            on_state_change=state_history.append,
        )
        self._active_processors.append(processor)

        self.assertEqual(processor.state, DictationState.READY)

        # Start and stop recording
        processor.start_listening()
        self.assertEqual(processor.state, DictationState.LISTENING)
        processor.stop_listening()

        # Wait for processing
        for _ in range(50):
            if processor.state == DictationState.READY:
                break
            time.sleep(0.05)

        self.assertEqual(processor.state, DictationState.READY)
        self.assertIn(DictationState.LISTENING, state_history)
        self.assertIn(DictationState.PROCESSING, state_history)
        self.assertIn(DictationState.TYPING, state_history)

        # 1. Verify STT was invoked
        self.assertEqual(stt.call_count, 1)

        # 2. Verify text was inserted with formatting
        self.assertEqual(len(pasted_texts), 1)
        self.assertEqual(pasted_texts[0], "Hello, how are you?")

        # 3. Verify history recorded in database
        history = self.db.get_history()
        self.assertEqual(len(history), 1)
        record = history[0]
        self.assertEqual(record.mode, "dictation")
        self.assertEqual(record.raw_text, "hello comma how are you question mark")
        self.assertEqual(record.processed_text, "Hello, how are you?")
        self.assertEqual(record.status, "success")
        self.assertEqual(record.details.get("target_title"), "Notepad")

    def test_control_mode_low_risk_end_to_end_flow(self) -> None:
        """Low risk voice command -> Parse -> Validate -> Execute -> History flow."""
        mock_open = MockCustomAction(ActionType.OPEN_APP)
        router = CommandRouter(
            action_registry={ActionType.OPEN_APP: mock_open},
            database=self.db,
            confirm_medium=False,
            confirm_high=True,
            step_pause_seconds=0.0,
        )

        report = router.execute("open notepad")

        self.assertIsInstance(report, CommandExecutionReport)
        self.assertTrue(report.is_success)
        self.assertEqual(len(mock_open.call_history), 1)

        # Verify history database record via HistoryRepository
        entries = self.history_repo.get_entries(limit=10, mode="control")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].mode, "control")
        self.assertEqual(entries[0].raw_text, "open notepad")
        self.assertEqual(entries[0].status, "success")

    def test_control_mode_high_risk_confirmation_rejected(self) -> None:
        """High risk action cancelled by user should abort execution."""
        mock_confirm_handler = MagicMock(return_value=False)
        mock_delete = MockCustomAction(ActionType.DELETE_FILE)

        router = CommandRouter(
            action_registry={ActionType.DELETE_FILE: mock_delete},
            database=self.db,
            confirm_handler=mock_confirm_handler,
            confirm_medium=False,
            confirm_high=True,
            step_pause_seconds=0.0,
        )

        report = router.execute(r"delete file C:\Users\Test\doc.txt")

        self.assertEqual(report.status, "cancelled")
        # Action execute must NOT be called when cancelled
        self.assertEqual(len(mock_delete.call_history), 0)

        # History should record cancellation
        entries = self.history_repo.get_entries(limit=10, mode="control")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].status, "cancelled")

    def test_control_mode_multi_step_chain_flow(self) -> None:
        """Multi-step chained command execution ('open notepad and type Hello')."""
        mock_open = MockCustomAction(ActionType.OPEN_APP)
        mock_type = MockCustomAction(ActionType.TYPE_TEXT)

        router = CommandRouter(
            action_registry={
                ActionType.OPEN_APP: mock_open,
                ActionType.TYPE_TEXT: mock_type,
            },
            database=self.db,
            step_pause_seconds=0.0,
        )

        report = router.execute("open notepad and type Hello")

        self.assertTrue(report.is_success)
        self.assertEqual(len(report.steps), 2)
        self.assertTrue(report.steps[0].success)
        self.assertTrue(report.steps[1].success)

        # Verify history reflects actions in details
        entries = self.history_repo.get_entries(limit=10, mode="control")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].status, "success")

    def test_settings_reconfiguration_affects_pipeline(self) -> None:
        """Pipeline behavior reflects config changes dynamically."""
        cfg = AppConfig(
            dictation=DictationConfig(
                format_commands=False,  # Raw dictation without punctuation replacement
            ),
            control=ControlConfig(
                confirm_medium=True,   # Require confirmation for medium risk
            ),
        )

        audio_data = np.ones(16000, dtype=np.float32) * 0.1
        recorder = MockRecorder(audio_data)
        stt = MockSTTEngine(response="hello comma world")

        pasted: list[str] = []
        inserter = TextInserter(
            clipboard_manager=self.clipboard,
            get_window_func=lambda: (101, "Notepad", "Edit"),
            paste_func=lambda: (pasted.append(self.clipboard.get_text()), True)[1],
        )

        processor = DictationProcessor(
            recorder=recorder,
            stt_engine=stt,
            db=self.db,
            inserter=inserter,
            format_commands=cfg.dictation.format_commands,
            feedback_pause=0.01,
        )
        self._active_processors.append(processor)

        processor.start_listening()
        processor.stop_listening()

        for _ in range(50):
            if processor.state == DictationState.READY:
                break
            time.sleep(0.05)

        # With format_commands=False, "comma" is preserved
        self.assertEqual(len(pasted), 1)
        self.assertEqual(pasted[0], "Hello comma world")

        # Now test control router with confirm_medium=True on a medium-risk action (CLOSE_APP)
        mock_confirm_handler = MagicMock(return_value=True)
        mock_close = MockCustomAction(ActionType.CLOSE_APP)

        router = CommandRouter(
            action_registry={ActionType.CLOSE_APP: mock_close},
            database=self.db,
            confirm_handler=mock_confirm_handler,
            confirm_medium=cfg.control.confirm_medium,
            step_pause_seconds=0.0,
        )

        router.execute("close notepad")

        # Verify confirmation was requested because close_app is medium risk and confirm_medium=True
        self.assertTrue(mock_confirm_handler.called)


if __name__ == "__main__":
    unittest.main()
