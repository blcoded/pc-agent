"""Unit tests for Windows Startup Registry helper."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

from voice_agent.app.startup import (
    MemoryRegistryBackend,
    RUN_REG_KEY,
    WinregBackend,
    build_startup_command,
    get_startup_command,
    is_startup_enabled,
    set_startup_enabled,
)


class TestStartupRegistryHelper(unittest.TestCase):
    """Test suite for Windows Startup registry management."""

    def setUp(self) -> None:
        self.backend = MemoryRegistryBackend()

    def test_build_startup_command_custom_exe(self) -> None:
        """Custom executable path is resolved and quoted."""
        cmd = build_startup_command(exe_path=r"C:\Program Files\App\agent.exe", args="--tray")
        self.assertTrue(cmd.startswith('"C:\\Program Files\\App\\agent.exe"'))
        self.assertTrue(cmd.endswith("--tray"))

    def test_build_startup_command_frozen(self) -> None:
        """Frozen executable appends arguments directly to executable path."""
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", r"C:\VoiceAgent\VoiceAgent.exe"):
            cmd = build_startup_command(args="--minimized")
            self.assertEqual(cmd, '"C:\\VoiceAgent\\VoiceAgent.exe" --minimized')

    def test_build_startup_command_script(self) -> None:
        """Script mode includes python executable and script path."""
        with patch.object(sys, "frozen", False, create=True), \
             patch.object(sys, "executable", r"C:\Python311\python.exe"), \
             patch.object(sys, "argv", [r"C:\VoiceAgent\run.py"]):
            cmd = build_startup_command(args="--tray")
            self.assertEqual(cmd, '"C:\\Python311\\python.exe" "C:\\VoiceAgent\\run.py" --tray')

    def test_startup_initial_state(self) -> None:
        """Newly initialized backend has startup disabled."""
        self.assertFalse(is_startup_enabled(backend=self.backend))
        self.assertIsNone(get_startup_command(backend=self.backend))

    def test_set_startup_enabled_true(self) -> None:
        """Enabling startup sets registry key and command."""
        success = set_startup_enabled(
            enabled=True,
            app_name="PCVoiceAgentTest",
            exe_path=r"C:\TestApp\app.exe",
            args="--tray",
            backend=self.backend,
        )
        self.assertTrue(success)
        self.assertTrue(is_startup_enabled(app_name="PCVoiceAgentTest", backend=self.backend))
        self.assertEqual(
            get_startup_command(app_name="PCVoiceAgentTest", backend=self.backend),
            '"C:\\TestApp\\app.exe" --tray',
        )

    def test_set_startup_enabled_false(self) -> None:
        """Disabling startup removes entry cleanly."""
        set_startup_enabled(
            enabled=True,
            app_name="PCVoiceAgentTest",
            exe_path=r"C:\TestApp\app.exe",
            backend=self.backend,
        )
        self.assertTrue(is_startup_enabled(app_name="PCVoiceAgentTest", backend=self.backend))

        # Disable
        success = set_startup_enabled(
            enabled=False,
            app_name="PCVoiceAgentTest",
            backend=self.backend,
        )
        self.assertTrue(success)
        self.assertFalse(is_startup_enabled(app_name="PCVoiceAgentTest", backend=self.backend))
        self.assertIsNone(get_startup_command(app_name="PCVoiceAgentTest", backend=self.backend))

    def test_set_startup_disabled_when_already_missing(self) -> None:
        """Disabling non-existent startup entry does not error."""
        success = set_startup_enabled(
            enabled=False,
            app_name="NonExistentApp",
            backend=self.backend,
        )
        self.assertTrue(success)
        self.assertFalse(is_startup_enabled(app_name="NonExistentApp", backend=self.backend))

    def test_winreg_backend_get_value(self) -> None:
        """WinregBackend correctly delegates to winreg functions."""
        mock_winreg = MagicMock()
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
        mock_winreg.QueryValueEx.return_value = (r'"C:\App\agent.exe" --tray', 1)

        with patch("voice_agent.app.startup.HAS_WINREG", True), \
             patch("voice_agent.app.startup.winreg", mock_winreg):
            backend = WinregBackend()
            val = backend.get_value(RUN_REG_KEY, "TestApp")
            self.assertEqual(val, r'"C:\App\agent.exe" --tray')

    def test_winreg_backend_get_value_not_found(self) -> None:
        """WinregBackend returns None when FileNotFoundError is raised."""
        mock_winreg = MagicMock()
        mock_winreg.OpenKey.side_effect = FileNotFoundError("Not found")

        with patch("voice_agent.app.startup.HAS_WINREG", True), \
             patch("voice_agent.app.startup.winreg", mock_winreg):
            backend = WinregBackend()
            val = backend.get_value(RUN_REG_KEY, "MissingApp")
            self.assertIsNone(val)

    def test_winreg_backend_set_value(self) -> None:
        """WinregBackend correctly sets value via winreg."""
        mock_winreg = MagicMock()
        mock_key = MagicMock()
        mock_winreg.CreateKeyEx.return_value.__enter__.return_value = mock_key

        with patch("voice_agent.app.startup.HAS_WINREG", True), \
             patch("voice_agent.app.startup.winreg", mock_winreg):
            backend = WinregBackend()
            backend.set_value(RUN_REG_KEY, "TestApp", r'"C:\App\agent.exe"')
            mock_winreg.SetValueEx.assert_called_once_with(
                mock_key, "TestApp", 0, mock_winreg.REG_SZ, r'"C:\App\agent.exe"'
            )

    def test_winreg_backend_delete_value(self) -> None:
        """WinregBackend deletes value and returns True."""
        mock_winreg = MagicMock()
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key

        with patch("voice_agent.app.startup.HAS_WINREG", True), \
             patch("voice_agent.app.startup.winreg", mock_winreg):
            backend = WinregBackend()
            deleted = backend.delete_value(RUN_REG_KEY, "TestApp")
            self.assertTrue(deleted)
            mock_winreg.DeleteValue.assert_called_once_with(mock_key, "TestApp")


if __name__ == "__main__":
    unittest.main()
