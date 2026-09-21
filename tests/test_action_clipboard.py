"""Unit tests for Clipboard Control Actions (TASK-6.6)."""

import unittest
from unittest.mock import MagicMock

from voice_agent.clipboard.manager import ClipboardManager, SimulatedClipboardBackend
from voice_agent.control.actions.clipboard import (
    CopyAction,
    PasteAction,
    ReadClipboardAction,
)
from voice_agent.control.actions.keyboard import SimulatedKeyboardBackend as SimKeyboard
from voice_agent.control.models import ActionType


class TestActionClipboard(unittest.TestCase):
    """Test suite for CopyAction, PasteAction, and ReadClipboardAction."""

    def setUp(self) -> None:
        self.keyboard = SimKeyboard()
        self.clip_backend = SimulatedClipboardBackend()
        self.clipboard_mgr = ClipboardManager(clipboard_module=self.clip_backend)

    def test_copy_action_success(self) -> None:
        """Test triggering Copy (Ctrl+C)."""
        action = CopyAction(keyboard_backend=self.keyboard)
        self.assertEqual(action.action_type, ActionType.COPY)

        result = action.run({})
        self.assertTrue(result.success)
        self.assertIn(["ctrl", "c"], self.keyboard.hotkeys_history)

    def test_paste_action_success(self) -> None:
        """Test triggering Paste (Ctrl+V)."""
        action = PasteAction(keyboard_backend=self.keyboard)
        self.assertEqual(action.action_type, ActionType.PASTE)

        result = action.run({})
        self.assertTrue(result.success)
        self.assertIn(["ctrl", "v"], self.keyboard.hotkeys_history)

    def test_read_clipboard_success(self) -> None:
        """Test reading text from clipboard."""
        self.clipboard_mgr.set_text("Sample Clipboard Text")
        action = ReadClipboardAction(clipboard_manager=self.clipboard_mgr)
        self.assertEqual(action.action_type, ActionType.READ_CLIPBOARD)

        result = action.run({})
        self.assertTrue(result.success)
        self.assertEqual(result.output["text"], "Sample Clipboard Text")
        self.assertEqual(result.output["character_count"], 21)

    def test_read_clipboard_empty(self) -> None:
        """Test reading from empty clipboard."""
        action = ReadClipboardAction(clipboard_manager=self.clipboard_mgr)
        result = action.run({})
        self.assertTrue(result.success)
        self.assertEqual(result.output["text"], "")
        self.assertEqual(result.output["character_count"], 0)

    def test_copy_action_error_handling(self) -> None:
        """Test handling failure in keyboard backend during copy."""
        mock_kb = MagicMock()
        mock_kb.hotkey.side_effect = RuntimeError("Keyboard device error")

        action = CopyAction(keyboard_backend=mock_kb)
        result = action.run({})
        self.assertFalse(result.success)
        self.assertIn("Keyboard device error", result.error_message or "")


if __name__ == "__main__":
    unittest.main()
