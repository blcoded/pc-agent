"""Unit tests for Multi-Step Command Router and Control Pipeline (TASK-6.7)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from voice_agent.app.lifecycle import ControlState
from voice_agent.control.actions.base import Action, ActionResult, ActionType
from voice_agent.control.command_router import CommandRouter
from voice_agent.control.models import ActionRequest, RiskLevel
from voice_agent.storage.database import DatabaseManager


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


class TestCommandRouter(unittest.TestCase):
    """Test suite for CommandRouter coordination and multi-step pipeline."""

    def setUp(self) -> None:
        self.state_history: list[tuple[ControlState, str | None]] = []

        def state_recorder(state: ControlState, msg: str | None) -> None:
            self.state_history.append((state, msg))

        self.state_callback = state_recorder

        # Set up custom mock actions
        self.mock_open = MockCustomAction(ActionType.OPEN_APP)
        self.mock_type = MockCustomAction(ActionType.TYPE_TEXT)
        self.mock_press = MockCustomAction(ActionType.PRESS_KEY)
        self.mock_del = MockCustomAction(ActionType.DELETE_FILE)

        self.registry = {
            ActionType.OPEN_APP: self.mock_open,
            ActionType.TYPE_TEXT: self.mock_type,
            ActionType.PRESS_KEY: self.mock_press,
            ActionType.DELETE_FILE: self.mock_del,
        }

        self.router = CommandRouter(
            action_registry=self.registry,
            state_callback=self.state_callback,
            step_pause_seconds=0.0,
        )

    def test_single_command_execution(self) -> None:
        """Test executing a single recognized command."""
        report = self.router.execute("open notepad")
        self.assertTrue(report.is_success)
        self.assertEqual(len(report.steps), 1)
        self.assertEqual(report.steps[0].action_type, ActionType.OPEN_APP)
        self.assertEqual(self.mock_open.call_history, [{"app_name": "notepad"}])

        # Verify state machine lifecycle
        states = [s[0] for s in self.state_history]
        self.assertIn(ControlState.PROCESSING, states)
        self.assertIn(ControlState.VALIDATING, states)
        self.assertIn(ControlState.EXECUTING, states)
        self.assertIn(ControlState.RESULT, states)
        self.assertEqual(self.router.current_state, ControlState.READY)

    def test_multi_step_chained_execution(self) -> None:
        """Test sequential execution of chained multi-step commands."""
        report = self.router.execute("open notepad and type Hello then press enter")
        self.assertTrue(report.is_success)
        self.assertEqual(len(report.steps), 3)

        self.assertEqual(report.steps[0].action_type, ActionType.OPEN_APP)
        self.assertEqual(report.steps[1].action_type, ActionType.TYPE_TEXT)
        self.assertEqual(report.steps[2].action_type, ActionType.PRESS_KEY)

        self.assertEqual(self.mock_open.call_history, [{"app_name": "notepad"}])
        self.assertEqual(self.mock_type.call_history, [{"text": "Hello"}])
        self.assertEqual(self.mock_press.call_history, [{"key": "enter"}])

    def test_abort_on_step_failure(self) -> None:
        """Test that execution halts immediately if an intermediate step fails."""
        # Make type action fail
        self.mock_type.return_success = False

        report = self.router.execute("open notepad and type Hello then press enter")
        self.assertFalse(report.is_success)
        self.assertEqual(report.status, "failed")
        self.assertIn("failed", report.error_message or "")

        # Open succeeded, type failed, press was never called
        self.assertEqual(len(report.steps), 2)
        self.assertTrue(report.steps[0].success)
        self.assertFalse(report.steps[1].success)
        self.assertEqual(len(self.mock_press.call_history), 0)

    def test_confirmation_approval_flow(self) -> None:
        """Test high-risk action with approved confirmation."""
        confirm_mock = MagicMock(return_value=True)
        router = CommandRouter(
            action_registry=self.registry,
            confirm_handler=confirm_mock,
            state_callback=self.state_callback,
            step_pause_seconds=0.0,
        )

        report = router.execute("delete file test.txt")
        self.assertTrue(report.is_success)
        confirm_mock.assert_called_once()
        self.assertEqual(len(self.mock_del.call_history), 1)

    def test_confirmation_rejection_flow(self) -> None:
        """Test high-risk action with user cancellation."""
        confirm_mock = MagicMock(return_value=False)
        router = CommandRouter(
            action_registry=self.registry,
            confirm_handler=confirm_mock,
            state_callback=self.state_callback,
            step_pause_seconds=0.0,
        )

        report = router.execute("delete file test.txt")
        self.assertEqual(report.status, "cancelled")
        self.assertFalse(report.is_success)
        confirm_mock.assert_called_once()
        # Ensure delete action was NOT executed
        self.assertEqual(len(self.mock_del.call_history), 0)

    def test_unsupported_command_handling(self) -> None:
        """Test rejection of unsupported command."""
        report = self.router.execute("fly me to the moon")
        self.assertFalse(report.is_success)
        self.assertEqual(report.status, "failed")
        self.assertIn("Unsupported command", report.error_message or "")

    def test_history_database_recording(self) -> None:
        """Test that execution reports are recorded to the SQLite database."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            db = DatabaseManager(db_path=db_path)
            db.initialize()

            router = CommandRouter(
                action_registry=self.registry,
                database=db,
                step_pause_seconds=0.0,
            )

            report = router.execute("open notepad and type Welcome")
            self.assertTrue(report.is_success)

            # Query database
            entries = db.get_history(mode="control")
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].mode, "control")
            self.assertEqual(entries[0].status, "success")
            self.assertEqual(entries[0].raw_text, "open notepad and type Welcome")

            db.close()


if __name__ == "__main__":
    unittest.main()
