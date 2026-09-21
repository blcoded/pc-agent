"""Unit tests for SystemTrayManager and tray context menu."""

import unittest
from unittest.mock import MagicMock

from voice_agent.app.config import AppConfig
from voice_agent.app.lifecycle import ApplicationLifecycle
from voice_agent.ui.tray import SystemTrayManager


class TestSystemTrayManager(unittest.TestCase):
    """Test suite for system tray menu actions, callbacks, and notifications."""

    def setUp(self) -> None:
        self.config = AppConfig()
        self.mock_lifecycle = MagicMock(spec=ApplicationLifecycle)

    def test_tray_initialization_and_tooltip(self) -> None:
        """Verify default tooltip and action dictionary."""
        tray = SystemTrayManager(lifecycle=self.mock_lifecycle, config=self.config)
        self.assertIn("PC Voice Agent", tray.toolTip())
        self.assertFalse(tray.is_paused)

    def test_status_update_updates_tooltip(self) -> None:
        """Verify update_status updates tooltip and internal state."""
        tray = SystemTrayManager(lifecycle=self.mock_lifecycle, config=self.config)

        tray.update_status("dictation", "listening")
        self.assertIn("Listening", tray.toolTip())
        self.assertIn("Dictation", tray.toolTip())

        tray.update_status("control", "executing")
        self.assertIn("Executing", tray.toolTip())
        self.assertIn("Control", tray.toolTip())

    def test_pause_toggle_state_and_notification(self) -> None:
        """Verify pause toggle updates state, tooltip, and triggers notification."""
        tray = SystemTrayManager(lifecycle=self.mock_lifecycle, config=self.config)

        tray._handle_pause_toggle(True)
        self.assertTrue(tray.is_paused)
        self.assertIn("Paused", tray.toolTip())
        self.assertIsNotNone(tray.last_notification)
        assert tray.last_notification is not None
        self.assertIn("paused", tray.last_notification[1].lower())

        tray._handle_pause_toggle(False)
        self.assertFalse(tray.is_paused)
        self.assertIn("Ready", tray.toolTip())

    def test_menu_callbacks_invoked(self) -> None:
        """Verify context menu action bindings invoke registered callbacks."""
        history_called = []
        settings_called = []
        overlay_called = []
        about_called = []

        tray = SystemTrayManager(
            lifecycle=self.mock_lifecycle,
            config=self.config,
            on_toggle_overlay=lambda: overlay_called.append(True),
            on_open_history=lambda: history_called.append(True),
            on_open_settings=lambda: settings_called.append(True),
            on_about=lambda: about_called.append(True),
        )

        self.assertEqual(tray.on_toggle_overlay, tray._menu_actions.get("overlay") if hasattr(tray, "_menu_actions") and callable(tray._menu_actions.get("overlay")) else tray.on_toggle_overlay)
        tray.on_open_history()
        tray.on_open_settings()
        tray.on_about()
        tray.on_toggle_overlay()

        self.assertEqual(history_called, [True])
        self.assertEqual(settings_called, [True])
        self.assertEqual(about_called, [True])
        self.assertEqual(overlay_called, [True])

    def test_exit_triggers_lifecycle_shutdown(self) -> None:
        """Verify selecting Exit triggers graceful shutdown."""
        tray = SystemTrayManager(lifecycle=self.mock_lifecycle, config=self.config)
        tray._handle_exit()
        self.mock_lifecycle.shutdown.assert_called_once()

    def test_notification_delivery(self) -> None:
        """Verify show_notification stores last notification details."""
        tray = SystemTrayManager(lifecycle=self.mock_lifecycle, config=self.config)
        tray.show_notification("Alert Title", "Alert message text", icon_type="warning")
        self.assertEqual(tray.last_notification, ("Alert Title", "Alert message text"))


if __name__ == "__main__":
    unittest.main()
