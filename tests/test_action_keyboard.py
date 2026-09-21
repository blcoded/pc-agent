"""Unit tests for Keyboard & Typing Actions (TASK-6.2)."""

import unittest
from unittest.mock import MagicMock

from voice_agent.control.actions.keyboard import (
    HotkeyAction,
    NativeWin32KeyboardBackend,
    PressKeyAction,
    SimulatedKeyboardBackend,
    TypeTextAction,
    VK_MAP,
)
from voice_agent.control.models import ActionType


class TestActionKeyboard(unittest.TestCase):
    """Test suite for TypeTextAction, PressKeyAction, and HotkeyAction."""

    def setUp(self) -> None:
        self.backend = SimulatedKeyboardBackend()

    def test_type_text_success(self) -> None:
        """Test typing text string into active window."""
        action = TypeTextAction(backend=self.backend)
        self.assertEqual(action.action_type, ActionType.TYPE_TEXT)

        result = action.run({"text": "Hello World!"})
        self.assertTrue(result.success)
        self.assertEqual(result.output["character_count"], 12)
        self.assertEqual(self.backend.typed_history, ["Hello World!"])

    def test_type_text_validation_failure(self) -> None:
        """Test type text parameter validation."""
        action = TypeTextAction(backend=self.backend)

        # Missing text
        res_missing = action.run({})
        self.assertFalse(res_missing.success)
        self.assertIn("Validation failed", res_missing.error_message or "")

        # Text with null byte
        res_null = action.run({"text": "Bad\0Text"})
        self.assertFalse(res_null.success)

    def test_press_key_success(self) -> None:
        """Test pressing standard and special keys."""
        action = PressKeyAction(backend=self.backend)
        self.assertEqual(action.action_type, ActionType.PRESS_KEY)

        keys_to_test = ["enter", "backspace", "tab", "escape", "space", "up", "down", "left", "right"]
        for k in keys_to_test:
            result = action.run({"key": k})
            self.assertTrue(result.success, f"Failed on key {k}")
            self.assertEqual(result.output["key"], k)

        self.assertEqual(self.backend.pressed_keys_history, keys_to_test)

    def test_press_key_validation_and_error(self) -> None:
        """Test press key validation and unknown key errors."""
        action = PressKeyAction(backend=self.backend)

        # Missing key
        res_missing = action.run({})
        self.assertFalse(res_missing.success)

        # Empty key
        res_empty = action.run({"key": "   "})
        self.assertFalse(res_empty.success)

        # Unknown key
        res_unknown = action.run({"key": "NonExistentKey123"})
        self.assertFalse(res_unknown.success)
        self.assertIn("Unknown key", res_unknown.error_message or "")

    def test_hotkey_action_success(self) -> None:
        """Test executing hotkeys via list and string formats."""
        action = HotkeyAction(backend=self.backend)
        self.assertEqual(action.action_type, ActionType.HOTKEY)

        # List format
        res_list = action.run({"keys": ["ctrl", "c"]})
        self.assertTrue(res_list.success)
        self.assertEqual(res_list.output["chord"], "ctrl+c")

        # String format with +
        res_str_plus = action.run({"hotkey": "ctrl+v"})
        self.assertTrue(res_str_plus.success)
        self.assertEqual(res_str_plus.output["chord"], "ctrl+v")

        # String format with space
        res_str_space = action.run({"hotkey": "alt tab"})
        self.assertTrue(res_str_space.success)
        self.assertEqual(res_str_space.output["chord"], "alt+tab")

        self.assertEqual(
            self.backend.hotkeys_history,
            [["ctrl", "c"], ["ctrl", "v"], ["alt", "tab"]],
        )

    def test_hotkey_validation_and_unknown_keys(self) -> None:
        """Test hotkey validation and invalid chords."""
        action = HotkeyAction(backend=self.backend)

        # Missing both keys and hotkey
        res_missing = action.run({})
        self.assertFalse(res_missing.success)

        # Invalid key inside chord
        res_invalid = action.run({"keys": ["ctrl", "InvalidKey99"]})
        self.assertFalse(res_invalid.success)
        self.assertIn("Unknown key in chord", res_invalid.error_message or "")

    def test_vk_map_completeness(self) -> None:
        """Verify common virtual key code mappings."""
        self.assertIn("enter", VK_MAP)
        self.assertIn("backspace", VK_MAP)
        self.assertIn("tab", VK_MAP)
        self.assertIn("ctrl", VK_MAP)
        self.assertIn("alt", VK_MAP)
        self.assertIn("shift", VK_MAP)
        self.assertIn("win", VK_MAP)
        self.assertIn("f1", VK_MAP)
        self.assertIn("f12", VK_MAP)
        self.assertIn("a", VK_MAP)
        self.assertIn("z", VK_MAP)
        self.assertIn("0", VK_MAP)
        self.assertIn("9", VK_MAP)

    def test_native_backend_instantiation(self) -> None:
        """Test NativeWin32KeyboardBackend instantiation on Windows."""
        native = NativeWin32KeyboardBackend()
        self.assertIsNotNone(native)


if __name__ == "__main__":
    unittest.main()
