"""Unit tests for SettingsDialog preferences configuration UI."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
try:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
except ImportError:
    app = None

from voice_agent.app.config import (
    AppConfig,
    AudioConfig,
    ControlConfig,
    DictationConfig,
    GeneralConfig,
    StorageConfig,
    UIConfig,
    load_config,
    save_config,
)
from voice_agent.audio.microphone import AudioDeviceInfo
from voice_agent.ui.settings import SettingsDialog


class TestSettingsDialog(unittest.TestCase):
    """Test suite for SettingsDialog UI and configuration synchronization."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.toml"

        self.initial_config = AppConfig(
            dictation=DictationConfig(
                hotkey="ctrl_r",
                mode="both",
                model="base",
                language="en",
                format_commands=True,
                restore_clipboard=True,
            ),
            control=ControlConfig(
                hotkey="alt_r",
                mode="both",
                confirm_medium=False,
                confirm_high=True,
            ),
            audio=AudioConfig(
                microphone=None,
                sample_rate=16000,
                channels=1,
            ),
            ui=UIConfig(
                overlay_enabled=True,
                overlay_x=100,
                overlay_y=200,
                opacity=0.95,
            ),
            storage=StorageConfig(
                history_retention_days=30,
                max_history_entries=5000,
            ),
            general=GeneralConfig(
                run_at_startup=False,
                minimize_to_tray=True,
            ),
        )
        save_config(self.initial_config, self.config_path)

        # Mock mic manager
        self.mock_mic_manager = MagicMock()
        self.mock_mic_manager.get_input_devices.return_value = [
            AudioDeviceInfo(
                id=1,
                name="Headset Mic",
                hostapi=0,
                hostapi_name="MME",
                max_input_channels=1,
                default_sample_rate=16000.0,
                is_default=True,
            ),
            AudioDeviceInfo(
                id=2,
                name="USB Array Mic",
                hostapi=0,
                hostapi_name="MME",
                max_input_channels=2,
                default_sample_rate=48000.0,
                is_default=False,
            ),
        ]

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_initialization_loads_config(self) -> None:
        """Dialog loads initial values correctly."""
        dialog = SettingsDialog(
            config_path=self.config_path,
            mic_manager=self.mock_mic_manager,
        )

        self.assertEqual(dialog.dictation_hotkey, "ctrl_r")
        self.assertEqual(dialog.dictation_mode, "both")
        self.assertEqual(dialog.stt_model, "base")
        self.assertEqual(dialog.language, "en")
        self.assertTrue(dialog.format_commands)
        self.assertTrue(dialog.restore_clipboard)

        self.assertEqual(dialog.control_hotkey, "alt_r")
        self.assertEqual(dialog.control_mode, "both")
        self.assertFalse(dialog.confirm_medium)
        self.assertTrue(dialog.confirm_high)

        self.assertIsNone(dialog.microphone)
        self.assertEqual(dialog.max_duration, 60)
        self.assertEqual(len(dialog.available_microphones), 2)


        self.assertFalse(dialog.run_at_startup)
        self.assertTrue(dialog.minimize_to_tray)
        self.assertEqual(dialog.history_retention_days, 30)
        self.assertTrue(dialog.overlay_enabled)
        self.assertEqual(dialog.overlay_x, 100)
        self.assertEqual(dialog.overlay_y, 200)

    def test_modify_and_apply_saves_toml(self) -> None:
        """Modifying dialog fields and calling apply updates config.toml."""
        applied_events: list[AppConfig] = []

        def on_applied(cfg: AppConfig) -> None:
            applied_events.append(cfg)

        dialog = SettingsDialog(
            config_path=self.config_path,
            on_applied=on_applied,
            mic_manager=self.mock_mic_manager,
        )

        # Modify values
        dialog.dictation_hotkey = "f10"
        dialog.dictation_mode = "push_to_talk"
        dialog.stt_model = "small"
        dialog.language = "es"
        dialog.format_commands = False
        dialog.restore_clipboard = False

        dialog.control_hotkey = "f11"
        dialog.control_mode = "toggle"
        dialog.confirm_medium = True

        dialog.microphone = "USB Array Mic"
        dialog.max_duration = 120

        dialog.run_at_startup = True
        dialog.minimize_to_tray = False
        dialog.history_retention_days = 60
        dialog.overlay_enabled = False

        # Apply changes
        updated_cfg = dialog.apply()

        self.assertEqual(len(applied_events), 1)
        self.assertEqual(applied_events[0], updated_cfg)

        # Verify disk serialization
        disk_cfg = load_config(self.config_path)
        self.assertEqual(disk_cfg.dictation.hotkey, "f10")
        self.assertEqual(disk_cfg.dictation.mode, "push_to_talk")
        self.assertEqual(disk_cfg.dictation.model, "small")
        self.assertEqual(disk_cfg.dictation.language, "es")
        self.assertFalse(disk_cfg.dictation.format_commands)
        self.assertFalse(disk_cfg.dictation.restore_clipboard)

        self.assertEqual(disk_cfg.control.hotkey, "f11")
        self.assertEqual(disk_cfg.control.mode, "toggle")
        self.assertTrue(disk_cfg.control.confirm_medium)

        self.assertEqual(disk_cfg.audio.microphone, "USB Array Mic")
        self.assertEqual(disk_cfg.audio.max_duration, 120)

        self.assertTrue(disk_cfg.general.run_at_startup)
        self.assertFalse(disk_cfg.general.minimize_to_tray)
        self.assertEqual(disk_cfg.storage.history_retention_days, 60)
        self.assertFalse(disk_cfg.ui.overlay_enabled)


    def test_save_applies_and_accepts(self) -> None:
        """Save action commits changes and accepts dialog."""
        dialog = SettingsDialog(
            config_path=self.config_path,
            mic_manager=self.mock_mic_manager,
        )

        dialog.dictation_hotkey = "f12"
        saved_cfg = dialog.save()

        self.assertEqual(saved_cfg.dictation.hotkey, "f12")
        self.assertEqual(dialog.result(), dialog.Accepted)

        reloaded = load_config(self.config_path)
        self.assertEqual(reloaded.dictation.hotkey, "f12")

    def test_cancel_reverts_modifications(self) -> None:
        """Cancel reverts unsaved changes to baseline and rejects dialog."""
        dialog = SettingsDialog(
            config_path=self.config_path,
            mic_manager=self.mock_mic_manager,
        )

        # Alter values
        dialog.dictation_hotkey = "f9"
        dialog.history_retention_days = 90

        # Cancel
        dialog.cancel()

        self.assertEqual(dialog.result(), dialog.Rejected)
        self.assertEqual(dialog.dictation_hotkey, "ctrl_r")
        self.assertEqual(dialog.history_retention_days, 30)

        # Ensure config file was not overwritten
        disk_cfg = load_config(self.config_path)
        self.assertEqual(disk_cfg.dictation.hotkey, "ctrl_r")
        self.assertEqual(disk_cfg.storage.history_retention_days, 30)

    def test_reset_overlay_position(self) -> None:
        """Resetting overlay sets coordinates back to (-1, -1)."""
        dialog = SettingsDialog(
            config_path=self.config_path,
            mic_manager=self.mock_mic_manager,
        )
        self.assertEqual(dialog.overlay_x, 100)
        self.assertEqual(dialog.overlay_y, 200)

        dialog.reset_overlay_position()
        self.assertEqual(dialog.overlay_x, -1)
        self.assertEqual(dialog.overlay_y, -1)

        cfg = dialog.apply()
        self.assertEqual(cfg.ui.overlay_x, -1)
        self.assertEqual(cfg.ui.overlay_y, -1)

        disk_cfg = load_config(self.config_path)
        self.assertEqual(disk_cfg.ui.overlay_x, -1)
        self.assertEqual(disk_cfg.ui.overlay_y, -1)

    def test_max_duration_setting_cap(self) -> None:
        """Verify max duration setting is capped at 150 seconds."""
        dialog = SettingsDialog(
            config_path=self.config_path,
            mic_manager=self.mock_mic_manager,
        )
        self.assertEqual(dialog.max_duration, 60)

        # Attempt to set to 250s -> should be clamped to 150s
        dialog.max_duration = 250
        self.assertEqual(dialog.max_duration, 150)

        cfg = dialog.apply()
        self.assertEqual(cfg.audio.max_duration, 150)
        disk_cfg = load_config(self.config_path)
        self.assertEqual(disk_cfg.audio.max_duration, 150)

        # Attempt to set below 10s -> clamped to 10s
        dialog.max_duration = 5
        self.assertEqual(dialog.max_duration, 10)
        cfg2 = dialog.apply()
        self.assertEqual(cfg2.audio.max_duration, 10)


if __name__ == "__main__":
    unittest.main()

