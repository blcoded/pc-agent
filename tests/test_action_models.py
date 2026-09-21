"""Unit tests for Action models, enums, and base Action class (TASK-5.1)."""

import unittest
from typing import Any

from voice_agent.control.actions.base import (
    Action,
    ActionError,
    ActionExecutionError,
    ActionRequest,
    ActionResult,
    ActionType,
    ActionValidationError,
    RiskLevel,
)


class DummyValidAction(Action):
    """Test concrete implementation of Action."""

    @property
    def action_type(self) -> ActionType:
        return ActionType.OPEN_APP

    def validate(self, params: dict[str, Any]) -> bool:
        if "app_name" not in params:
            raise ActionValidationError("Missing 'app_name' parameter")
        return True

    def execute(self, params: dict[str, Any]) -> ActionResult:
        return ActionResult(success=True, output=f"Launched {params['app_name']}")


class DummyFailingAction(Action):
    """Test concrete implementation that raises ActionExecutionError."""

    @property
    def action_type(self) -> ActionType:
        return ActionType.CLOSE_APP

    def execute(self, params: dict[str, Any]) -> ActionResult:
        raise ActionExecutionError("Process terminated unexpectedly")


class DummyCrashingAction(Action):
    """Test concrete implementation that raises unexpected exception."""

    @property
    def action_type(self) -> ActionType:
        return ActionType.DELETE_FILE

    def execute(self, params: dict[str, Any]) -> ActionResult:
        raise ZeroDivisionError("Math error in action")


class TestActionModels(unittest.TestCase):
    """Test suite for Action enums and dataclass models."""

    def test_action_type_enum_completeness(self) -> None:
        """Verify all required action types exist with expected string values."""
        expected_types = {
            "OPEN_APP": "open_app",
            "CLOSE_APP": "close_app",
            "SWITCH_WINDOW": "switch_window",
            "TYPE_TEXT": "type_text",
            "PRESS_KEY": "press_key",
            "HOTKEY": "hotkey",
            "MOVE_MOUSE": "move_mouse",
            "CLICK": "click",
            "OPEN_URL": "open_url",
            "SEARCH_WEB": "search_web",
            "READ_CLIPBOARD": "read_clipboard",
            "COPY": "copy",
            "PASTE": "paste",
            "OPEN_FILE": "open_file",
            "RENAME_FILE": "rename_file",
            "MOVE_FILE": "move_file",
            "DELETE_FILE": "delete_file",
            "OPEN_FOLDER": "open_folder",
        }
        for name, val in expected_types.items():
            self.assertTrue(hasattr(ActionType, name), f"Missing ActionType.{name}")
            self.assertEqual(getattr(ActionType, name).value, val)
            self.assertEqual(str(getattr(ActionType, name)), val)

    def test_risk_level_enum(self) -> None:
        """Verify RiskLevel contains LOW, MEDIUM, HIGH."""
        self.assertEqual(RiskLevel.LOW.value, "low")
        self.assertEqual(RiskLevel.MEDIUM.value, "medium")
        self.assertEqual(RiskLevel.HIGH.value, "high")
        self.assertEqual(str(RiskLevel.LOW), "low")

    def test_action_request_defaults_and_custom(self) -> None:
        """Test ActionRequest instantiation and default values."""
        req_default = ActionRequest(action_type=ActionType.CLICK)
        self.assertEqual(req_default.action_type, ActionType.CLICK)
        self.assertEqual(req_default.params, {})
        self.assertEqual(req_default.risk_level, RiskLevel.LOW)
        self.assertEqual(req_default.raw_command, "")
        self.assertFalse(req_default.confirmed)

        req_custom = ActionRequest(
            action_type=ActionType.DELETE_FILE,
            params={"path": "C:\\temp\\file.txt"},
            risk_level=RiskLevel.HIGH,
            raw_command="delete file file.txt",
            confirmed=True,
        )
        self.assertEqual(req_custom.action_type, ActionType.DELETE_FILE)
        self.assertEqual(req_custom.params["path"], "C:\\temp\\file.txt")
        self.assertEqual(req_custom.risk_level, RiskLevel.HIGH)
        self.assertEqual(req_custom.raw_command, "delete file file.txt")
        self.assertTrue(req_custom.confirmed)

    def test_action_request_dict_roundtrip(self) -> None:
        """Test ActionRequest to_dict and from_dict serialization."""
        req = ActionRequest(
            action_type=ActionType.OPEN_URL,
            params={"url": "https://google.com"},
            risk_level=RiskLevel.LOW,
            raw_command="open google.com",
            confirmed=True,
        )
        d = req.to_dict()
        self.assertEqual(
            d,
            {
                "action_type": "open_url",
                "params": {"url": "https://google.com"},
                "risk_level": "low",
                "raw_command": "open google.com",
                "confirmed": True,
            },
        )

        restored = ActionRequest.from_dict(d)
        self.assertEqual(restored.action_type, ActionType.OPEN_URL)
        self.assertEqual(restored.params, {"url": "https://google.com"})
        self.assertEqual(restored.risk_level, RiskLevel.LOW)
        self.assertEqual(restored.raw_command, "open google.com")
        self.assertTrue(restored.confirmed)

    def test_action_request_from_dict_variations(self) -> None:
        """Test from_dict with uppercase enum strings and fallback risk levels."""
        d = {
            "action_type": "TYPE_TEXT",
            "params": {"text": "hello"},
            "risk_level": "MEDIUM",
        }
        req = ActionRequest.from_dict(d)
        self.assertEqual(req.action_type, ActionType.TYPE_TEXT)
        self.assertEqual(req.risk_level, RiskLevel.MEDIUM)
        self.assertEqual(req.params, {"text": "hello"})

        # Invalid action_type raises ActionValidationError
        with self.assertRaises(ActionValidationError):
            ActionRequest.from_dict({"action_type": "non_existent_type"})

    def test_action_result_roundtrip(self) -> None:
        """Test ActionResult serialization and reconstruction."""
        res_ok = ActionResult(success=True, output={"status": "ok"})
        d_ok = res_ok.to_dict()
        self.assertEqual(d_ok, {"success": True, "output": {"status": "ok"}, "error_message": None})
        restored_ok = ActionResult.from_dict(d_ok)
        self.assertTrue(restored_ok.success)
        self.assertEqual(restored_ok.output, {"status": "ok"})
        self.assertIsNone(restored_ok.error_message)

        res_err = ActionResult(success=False, output=None, error_message="File not found")
        d_err = res_err.to_dict()
        restored_err = ActionResult.from_dict(d_err)
        self.assertFalse(restored_err.success)
        self.assertEqual(restored_err.error_message, "File not found")


class TestBaseAction(unittest.TestCase):
    """Test suite for the Action base interface."""

    def test_successful_action_run(self) -> None:
        """Test standard validation and execution flow."""
        action = DummyValidAction()
        self.assertEqual(action.action_type, ActionType.OPEN_APP)

        result = action.run({"app_name": "notepad"})
        self.assertTrue(result.success)
        self.assertEqual(result.output, "Launched notepad")
        self.assertIsNone(result.error_message)

    def test_validation_failure(self) -> None:
        """Test that missing required parameters returns a failed ActionResult."""
        action = DummyValidAction()
        result = action.run({})
        self.assertFalse(result.success)
        self.assertIn("Validation failed", result.error_message or "")
        self.assertIn("Missing 'app_name'", result.error_message or "")

    def test_execution_failure(self) -> None:
        """Test that ActionExecutionError is caught and returned cleanly."""
        action = DummyFailingAction()
        result = action.run({"pid": 1234})
        self.assertFalse(result.success)
        self.assertIn("Execution error", result.error_message or "")
        self.assertIn("Process terminated unexpectedly", result.error_message or "")

    def test_unexpected_exception_handling(self) -> None:
        """Test that unhandled exceptions during execution are caught."""
        action = DummyCrashingAction()
        result = action.run({"path": "file.txt"})
        self.assertFalse(result.success)
        self.assertIn("Unexpected error", result.error_message or "")
        self.assertIn("ZeroDivisionError", result.error_message or "")


if __name__ == "__main__":
    unittest.main()
