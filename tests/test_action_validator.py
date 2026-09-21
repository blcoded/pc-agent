"""Unit tests for Action Parameter & Path Validator (TASK-5.3)."""

import tempfile
import unittest
from pathlib import Path

from voice_agent.control.action_validator import ActionValidator
from voice_agent.control.models import (
    ActionRequest,
    ActionType,
    ActionValidationError,
    RiskLevel,
)


class TestActionValidator(unittest.TestCase):
    """Test suite for ActionValidator parameter constraints and security boundaries."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.validator = ActionValidator(base_directory=self.base_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_validate_app_name_valid(self) -> None:
        """Test valid application names."""
        self.assertEqual(self.validator.validate_app_name("notepad"), "notepad")
        self.assertEqual(self.validator.validate_app_name("chrome"), "chrome")
        self.assertEqual(self.validator.validate_app_name("C:\\Tools\\App.exe"), "C:\\Tools\\App.exe")

    def test_validate_app_name_injection_and_disallowed(self) -> None:
        """Test rejection of shell injection and administrative binaries."""
        # Empty
        with self.assertRaises(ActionValidationError):
            self.validator.validate_app_name("")
        with self.assertRaises(ActionValidationError):
            self.validator.validate_app_name("   ")

        # Shell injection characters
        injections = [
            "notepad & calc",
            "calc | dir",
            "foo; rm -rf",
            "test > output.txt",
            "app < input",
            "run`whoami`",
            "app$VAR",
            "app\nmalicious",
            "app\0null",
        ]
        for bad in injections:
            with self.assertRaises(ActionValidationError, msg=f"Should reject: {bad}"):
                self.validator.validate_app_name(bad)

        # Disallowed binaries
        disallowed = ["cmd", "cmd.exe", "powershell", "powershell.exe", "format", "vssadmin.exe", "reg.exe"]
        for bad_bin in disallowed:
            with self.assertRaises(ActionValidationError, msg=f"Should reject binary: {bad_bin}"):
                self.validator.validate_app_name(bad_bin)

    def test_validate_path_security(self) -> None:
        """Test path traversal, normalization, and protected folder restrictions."""
        # Null bytes
        with self.assertRaises(ActionValidationError):
            self.validator.validate_path("file\0.txt")

        # Empty
        with self.assertRaises(ActionValidationError):
            self.validator.validate_path("")

        # Relative path resolution inside base_directory
        resolved = self.validator.validate_path("notes.txt")
        self.assertEqual(resolved, (self.base_dir / "notes.txt").resolve())

        # Protected system directories
        with self.assertRaises(ActionValidationError):
            self.validator.validate_path("C:\\Windows")

        with self.assertRaises(ActionValidationError):
            self.validator.validate_path("C:\\Windows\\System32")

        # Protected path deletion
        with self.assertRaises(ActionValidationError):
            self.validator.validate_path("C:\\", for_deletion=True)

        # Existing check
        with self.assertRaises(ActionValidationError):
            self.validator.validate_path("non_existent_file.txt", must_exist=True)

        existing_file = self.base_dir / "exists.txt"
        existing_file.write_text("hello", encoding="utf-8")
        self.assertEqual(self.validator.validate_path("exists.txt", must_exist=True), existing_file.resolve())

    def test_validate_url(self) -> None:
        """Test URL validation and disallowed protocol filtering."""
        # Valid URLs
        self.assertEqual(self.validator.validate_url("https://github.com"), "https://github.com")
        self.assertEqual(self.validator.validate_url("http://localhost:8080"), "http://localhost:8080")
        self.assertEqual(self.validator.validate_url("docs.python.org"), "https://docs.python.org")

        # Disallowed schemes
        bad_urls = [
            "javascript:alert(1)",
            "file:///C:/Windows/System32",
            "ftp://files.example.com",
            "data:text/html,<html>",
        ]
        for bad in bad_urls:
            with self.assertRaises(ActionValidationError, msg=f"Should reject URL: {bad}"):
                self.validator.validate_url(bad)

        # Malformed or control chars
        with self.assertRaises(ActionValidationError):
            self.validator.validate_url("https://example.com\nmalicious")

    def test_validate_mouse_and_keyboard(self) -> None:
        """Test mouse coordinates, buttons, and keys."""
        # Coordinates
        self.assertEqual(self.validator.validate_mouse_coords(100, 200), (100, 200))
        with self.assertRaises(ActionValidationError):
            self.validator.validate_mouse_coords(-5, 100)
        with self.assertRaises(ActionValidationError):
            self.validator.validate_mouse_coords(20000, 100)

        # Buttons
        self.assertEqual(self.validator.validate_mouse_button("LEFT"), "left")
        self.assertEqual(self.validator.validate_mouse_button("right"), "right")
        with self.assertRaises(ActionValidationError):
            self.validator.validate_mouse_button("invalid_btn")

        # Text
        self.assertEqual(self.validator.validate_text("Hello World"), "Hello World")
        with self.assertRaises(ActionValidationError):
            self.validator.validate_text("Bad\0Text")
        with self.assertRaises(ActionValidationError):
            self.validator.validate_text(12345)  # Not a string

    def test_validate_action_requests(self) -> None:
        """Test full ActionRequest parameter validation across different ActionTypes."""
        # Valid OPEN_APP
        req = ActionRequest(action_type=ActionType.OPEN_APP, params={"app_name": "notepad"})
        self.assertTrue(self.validator.validate_action(req))
        self.assertTrue(self.validator.is_valid(req))

        # Invalid OPEN_APP (cmd.exe)
        bad_app_req = ActionRequest(action_type=ActionType.OPEN_APP, params={"app_name": "cmd.exe"})
        self.assertFalse(self.validator.is_valid(bad_app_req))
        with self.assertRaises(ActionValidationError):
            self.validator.validate_action(bad_app_req)

        # Valid OPEN_URL
        req_url = ActionRequest(action_type=ActionType.OPEN_URL, params={"url": "https://google.com"})
        self.assertTrue(self.validator.validate_action(req_url))

        # Invalid OPEN_URL (file://)
        bad_url_req = ActionRequest(action_type=ActionType.OPEN_URL, params={"url": "file:///C:/secret"})
        self.assertFalse(self.validator.is_valid(bad_url_req))

        # Valid CLICK
        req_click = ActionRequest(action_type=ActionType.CLICK, params={"button": "right", "click_count": 1})
        self.assertTrue(self.validator.validate_action(req_click))

        # Invalid CLICK count
        bad_click_req = ActionRequest(action_type=ActionType.CLICK, params={"click_count": 99})
        self.assertFalse(self.validator.is_valid(bad_click_req))

        # Valid MOVE_MOUSE
        req_move = ActionRequest(
            action_type=ActionType.MOVE_MOUSE,
            params={"mode": "absolute", "x": 500, "y": 400},
        )
        self.assertTrue(self.validator.validate_action(req_move))

        # Valid SEARCH_WEB
        req_search = ActionRequest(action_type=ActionType.SEARCH_WEB, params={"query": "python"})
        self.assertTrue(self.validator.validate_action(req_search))

        # Invalid SEARCH_WEB (empty query)
        bad_search = ActionRequest(action_type=ActionType.SEARCH_WEB, params={"query": "   "})
        self.assertFalse(self.validator.is_valid(bad_search))

        # Valid DELETE_FILE
        del_req = ActionRequest(action_type=ActionType.DELETE_FILE, params={"path": "safe_file.txt"}, risk_level=RiskLevel.HIGH)
        self.assertTrue(self.validator.validate_action(del_req))

        # Invalid DELETE_FILE (system root)
        bad_del_req = ActionRequest(action_type=ActionType.DELETE_FILE, params={"path": "C:\\"}, risk_level=RiskLevel.HIGH)
        self.assertFalse(self.validator.is_valid(bad_del_req))


if __name__ == "__main__":
    unittest.main()
