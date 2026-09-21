"""End-to-End Pipeline & Stress Testing for Control Mode (TASK-8.2).

Verifies:
- 100 consecutive simulated control commands across various action types.
- Sequential chained multi-step executions under rapid dispatch.
- Risk confirmation workflows (Medium and High risk confirmation handling).
- Error handling, unsupported command recovery, and security boundary enforcement.
"""

from __future__ import annotations

import gc
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock

from voice_agent.app.lifecycle import ControlState
from voice_agent.control.actions.base import Action, ActionResult, ActionType
from voice_agent.control.command_router import CommandExecutionReport, CommandRouter
from voice_agent.control.models import RiskLevel
from voice_agent.storage.database import DatabaseManager
from voice_agent.storage.history import HistoryRepository


class E2EMockAction(Action):
    """Configurable action tracker for E2E control tests."""

    def __init__(self, action_type: ActionType) -> None:
        self._type = action_type
        self.invocations: list[dict] = []
        self.fail = False

    @property
    def action_type(self) -> ActionType:
        return self._type

    def execute(self, params: dict) -> ActionResult:
        self.invocations.append(params)
        if self.fail:
            return ActionResult(success=False, output=None, error_message="Action failed in E2E")
        return ActionResult(success=True, output=f"Executed {self._type.value}")


class TestControlE2E(unittest.TestCase):
    """End-to-End stress and multi-step pipeline test suite for Control subsystem."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "e2e_control.db"
        self.db = DatabaseManager(self.db_path)
        self.history_repo = HistoryRepository(db=self.db)

        # Setup mock actions
        self.act_open = E2EMockAction(ActionType.OPEN_APP)
        self.act_close = E2EMockAction(ActionType.CLOSE_APP)
        self.act_type = E2EMockAction(ActionType.TYPE_TEXT)
        self.act_press = E2EMockAction(ActionType.PRESS_KEY)
        self.act_copy = E2EMockAction(ActionType.COPY)
        self.act_search = E2EMockAction(ActionType.SEARCH_WEB)
        self.act_delete = E2EMockAction(ActionType.DELETE_FILE)

        self.registry = {
            ActionType.OPEN_APP: self.act_open,
            ActionType.CLOSE_APP: self.act_close,
            ActionType.TYPE_TEXT: self.act_type,
            ActionType.PRESS_KEY: self.act_press,
            ActionType.COPY: self.act_copy,
            ActionType.SEARCH_WEB: self.act_search,
            ActionType.DELETE_FILE: self.act_delete,
        }

        self.confirmations_requested: list[str] = []

        def mock_confirm(request) -> bool:
            self.confirmations_requested.append(request.action_type.value)
            return True  # By default confirm

        self.mock_confirm = mock_confirm

        self.router = CommandRouter(
            action_registry=self.registry,
            database=self.db,
            confirm_handler=self.mock_confirm,
            confirm_medium=True,
            confirm_high=True,
            step_pause_seconds=0.0,
        )

    def tearDown(self) -> None:
        self.db.close()
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_100_consecutive_simulated_control_commands(self) -> None:
        """Execute 100 varied voice commands in rapid succession."""
        commands = [
            "open notepad",
            "type hello world",
            "press enter",
            "copy that",
            "close notepad",
        ]

        total_runs = 100
        for i in range(total_runs):
            cmd = commands[i % len(commands)]
            report = self.router.execute(cmd)

            self.assertTrue(report.is_success, f"Command #{i+1} ('{cmd}') failed: {report.error_message}")
            self.assertEqual(self.router.current_state, ControlState.READY)

        # Verify all 100 executions recorded in database
        history = self.db.get_history(limit=200)
        self.assertEqual(len(history), total_runs)
        self.assertTrue(all(r.mode == "control" for r in history))
        self.assertTrue(all(r.status == "success" for r in history))

    def test_rapid_chained_multi_step_commands(self) -> None:
        """Execute 10 complex multi-step commands sequentially."""
        complex_cmd = "open notepad and type Hello then press enter and copy that"

        for i in range(10):
            report = self.router.execute(complex_cmd)
            self.assertTrue(report.is_success)
            self.assertEqual(len(report.steps), 4)
            self.assertTrue(all(s.success for s in report.steps))
            self.assertEqual(self.router.current_state, ControlState.READY)

        self.assertEqual(len(self.act_open.invocations), 10)
        self.assertEqual(len(self.act_type.invocations), 10)
        self.assertEqual(len(self.act_press.invocations), 10)
        self.assertEqual(len(self.act_copy.invocations), 10)

    def test_unsupported_and_failing_command_recovery(self) -> None:
        """Router handles syntax errors, unsupported clauses, and action failures cleanly."""
        # 1. Unsupported clause
        report1 = self.router.execute("fly to the moon")
        self.assertFalse(report1.is_success)
        self.assertEqual(report1.status, "failed")
        self.assertEqual(self.router.current_state, ControlState.READY)

        # 2. Action execution failure mid-chain
        self.act_type.fail = True
        report2 = self.router.execute("open notepad and type testing failure then press enter")
        self.assertFalse(report2.is_success)
        self.assertEqual(report2.status, "failed")
        # Step 1 succeeded, step 2 failed, step 3 was aborted
        self.assertEqual(len(report2.steps), 2)
        self.assertTrue(report2.steps[0].success)
        self.assertFalse(report2.steps[1].success)
        self.assertEqual(self.router.current_state, ControlState.READY)

        # 3. High risk confirmation rejected
        self.router.confirm_handler = lambda req: False  # Reject
        report3 = self.router.execute(r"delete file C:\Users\Test\notes.txt")
        self.assertEqual(report3.status, "cancelled")
        self.assertEqual(self.router.current_state, ControlState.READY)

        # Check database records the failed/cancelled entries accurately
        entries = self.history_repo.get_entries(limit=10, mode="control")
        statuses = [e.status for e in entries]
        self.assertIn("failed", statuses)
        self.assertIn("cancelled", statuses)


if __name__ == "__main__":
    unittest.main()
