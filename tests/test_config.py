"""Unit tests for configuration manager."""

import os
from pathlib import Path
import tempfile
import unittest

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
    serialize_to_toml,
)


class TestConfig(unittest.TestCase):
    """Test suite for AppConfig and TOML serialization/deserialization."""

    def setUp(self) -> None:
        self.test_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.test_dir.name) / "config.toml"

    def tearDown(self) -> None:
        self.test_dir.cleanup()

    def test_default_config_values(self) -> None:
        """Verify default config values match project specifications."""
        cfg = AppConfig()
        self.assertEqual(cfg.dictation.hotkey, "ctrl_r")
        self.assertEqual(cfg.dictation.mode, "both")
        self.assertEqual(cfg.dictation.model, "base")
        self.assertEqual(cfg.dictation.language, "en")
        self.assertTrue(cfg.dictation.format_commands)
        self.assertTrue(cfg.dictation.restore_clipboard)
        self.assertFalse(cfg.dictation.keep_in_clipboard)

        self.assertEqual(cfg.control.hotkey, "alt_r")
        self.assertEqual(cfg.control.mode, "both")
        self.assertFalse(cfg.control.confirm_medium)
        self.assertTrue(cfg.control.confirm_high)

        self.assertIsNone(cfg.audio.microphone)
        self.assertEqual(cfg.audio.sample_rate, 16000)

        self.assertTrue(cfg.ui.overlay_enabled)
        self.assertEqual(cfg.ui.overlay_x, -1)
        self.assertEqual(cfg.ui.overlay_y, -1)

        self.assertEqual(cfg.storage.history_retention_days, 30)
        self.assertFalse(cfg.general.run_at_startup)

    def test_save_and_load_roundtrip(self) -> None:
        """Verify saving and re-loading preserves customized configurations."""
        cfg = AppConfig()
        cfg.dictation.hotkey = "f8"
        cfg.dictation.model = "small"
        cfg.control.confirm_medium = True
        cfg.ui.overlay_x = 500
        cfg.ui.overlay_y = 600
        cfg.general.run_at_startup = True

        save_config(cfg, self.config_path)
        self.assertTrue(self.config_path.exists())

        loaded = load_config(self.config_path)
        self.assertEqual(loaded.dictation.hotkey, "f8")
        self.assertEqual(loaded.dictation.model, "small")
        self.assertTrue(loaded.control.confirm_medium)
        self.assertEqual(loaded.ui.overlay_x, 500)
        self.assertEqual(loaded.ui.overlay_y, 600)
        self.assertTrue(loaded.general.run_at_startup)

    def test_load_non_existent_creates_default(self) -> None:
        """Verify loading from non-existent path creates and saves defaults."""
        self.assertFalse(self.config_path.exists())
        cfg = load_config(self.config_path)
        self.assertTrue(self.config_path.exists())
        self.assertEqual(cfg.dictation.hotkey, "ctrl_r")

    def test_corrupted_config_falls_back_to_defaults(self) -> None:
        """Verify that corrupted TOML files fall back gracefully to default values."""
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("invalid [[[ toml syntax :::")

        cfg = load_config(self.config_path)
        self.assertEqual(cfg.dictation.hotkey, "ctrl_r")
        self.assertEqual(cfg.control.hotkey, "alt_r")

    def test_partial_config_preserves_defaults(self) -> None:
        """Verify that missing keys in TOML retain their default values."""
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write('[dictation]\nhotkey = "space"\n')

        cfg = load_config(self.config_path)
        self.assertEqual(cfg.dictation.hotkey, "space")
        # Unspecified fields retain defaults
        self.assertEqual(cfg.dictation.model, "base")
        self.assertEqual(cfg.control.hotkey, "alt_r")


if __name__ == "__main__":
    unittest.main()
