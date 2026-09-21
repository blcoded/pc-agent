"""Unit tests for Application Control Actions (TASK-6.1)."""

import unittest
from unittest.mock import MagicMock

from voice_agent.control.actions.applications import (
    CloseAppAction,
    NativeWin32WindowBackend,
    OpenAppAction,
    SimulatedWindowBackend,
    SwitchWindowAction,
    WindowInfo,
)
from voice_agent.control.models import ActionType, ActionValidationError


class TestActionApplications(unittest.TestCase):
    """Test suite for OpenAppAction, CloseAppAction, and SwitchWindowAction."""

    def setUp(self) -> None:
        self.windows = [
            WindowInfo(hwnd=1001, title="Untitled - Notepad", visible=True),
            WindowInfo(hwnd=1002, title="Google Chrome - Work", visible=True),
            WindowInfo(hwnd=1003, title="Slack - Workspace", visible=True),
        ]
        self.backend = SimulatedWindowBackend(self.windows)

    def test_open_app_success(self) -> None:
        """Test launching an application via mocked launcher."""
        mock_launcher = MagicMock()
        mock_proc = MagicMock()
        mock_proc.pid = 9876
        mock_launcher.return_value = mock_proc

        action = OpenAppAction(launcher=mock_launcher)
        self.assertEqual(action.action_type, ActionType.OPEN_APP)

        result = action.run({"app_name": "notepad"})
        self.assertTrue(result.success)
        self.assertEqual(result.output["pid"], 9876)
        self.assertEqual(result.output["app_name"], "notepad")
        mock_launcher.assert_called_once()
        # Verify notepad was resolved to notepad.exe
        called_args = mock_launcher.call_args[0][0]
        self.assertTrue(any("notepad" in arg.lower() for arg in called_args))

    def test_open_app_validation_failure(self) -> None:
        """Test that invalid app names fail validation."""
        action = OpenAppAction()

        # Disallowed binary
        res_cmd = action.run({"app_name": "cmd.exe"})
        self.assertFalse(res_cmd.success)
        self.assertIn("Validation failed", res_cmd.error_message or "")

        # Injection chars
        res_inj = action.run({"app_name": "notepad & calc"})
        self.assertFalse(res_inj.success)
        self.assertIn("Validation failed", res_inj.error_message or "")

        # Missing app_name
        res_missing = action.run({})
        self.assertFalse(res_missing.success)

    def test_open_app_execution_error(self) -> None:
        """Test graceful failure when launcher raises an exception."""
        def bad_launcher(args: list[str]) -> None:
            raise FileNotFoundError("Executable not found on system")

        action = OpenAppAction(launcher=bad_launcher)
        result = action.run({"app_name": "unknown_app_12345"})
        self.assertFalse(result.success)
        self.assertIn("Could not launch application", result.error_message or "")

    def test_close_app_current_window(self) -> None:
        """Test closing current active window."""
        action = CloseAppAction(backend=self.backend)
        self.backend.foreground_hwnd = 1002  # Chrome

        result = action.run({"target": "current_window"})
        self.assertTrue(result.success)
        self.assertEqual(result.output["hwnd"], 1002)
        self.assertIn(1002, self.backend.closed_hwnds)

    def test_close_app_by_name(self) -> None:
        """Test closing a window by matching name/title."""
        action = CloseAppAction(backend=self.backend)

        result = action.run({"target": "notepad"})
        self.assertTrue(result.success)
        self.assertEqual(result.output["hwnd"], 1001)
        self.assertIn(1001, self.backend.closed_hwnds)

    def test_close_app_not_found(self) -> None:
        """Test closing when target window does not exist."""
        action = CloseAppAction(backend=self.backend)
        result = action.run({"target": "NonExistentApp"})
        self.assertFalse(result.success)
        self.assertIn("No matching open window found", result.error_message or "")

    def test_switch_window_success(self) -> None:
        """Test switching focus to an open window by title."""
        action = SwitchWindowAction(backend=self.backend)
        self.assertEqual(action.action_type, ActionType.SWITCH_WINDOW)

        result = action.run({"window_name": "slack"})
        self.assertTrue(result.success)
        self.assertEqual(result.output["hwnd"], 1003)
        self.assertEqual(self.backend.foreground_hwnd, 1003)
        self.assertIn(1003, self.backend.focused_hwnds)

    def test_switch_window_not_found(self) -> None:
        """Test switching when window is not found."""
        action = SwitchWindowAction(backend=self.backend)
        result = action.run({"window_name": "Photoshop"})
        self.assertFalse(result.success)
        self.assertIn("No matching window found", result.error_message or "")

    def test_native_backend_instantiation(self) -> None:
        """Test NativeWin32WindowBackend initialization without crashing."""
        native = NativeWin32WindowBackend()
        # Should return int without exception
        fg = native.get_foreground_window()
        self.assertIsInstance(fg, int)


if __name__ == "__main__":
    unittest.main()
