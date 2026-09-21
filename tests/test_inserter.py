"""Unit tests for TextInserter hybrid clipboard paste and fallback notification."""

import unittest

from voice_agent.clipboard.manager import ClipboardManager, SimulatedClipboardBackend
from voice_agent.dictation.inserter import (
    InsertionResult,
    InsertionStatus,
    TextInserter,
)


class TestTextInserter(unittest.TestCase):
    """Test suite for TextInserter injection lifecycle and no-target safety handling."""

    def setUp(self) -> None:
        self.clip_backend = SimulatedClipboardBackend()
        self.clipboard = ClipboardManager(clipboard_module=self.clip_backend)
        self.paste_calls = 0

    def _mock_paste_success(self) -> bool:
        self.paste_calls += 1
        return True

    def _mock_paste_fail(self) -> bool:
        self.paste_calls += 1
        return False

    def test_insert_into_valid_target(self) -> None:
        """Verify normal insertion into valid target window."""
        self.clip_backend.SetClipboardData(13, "Existing prior clipboard text")

        inserter = TextInserter(
            clipboard_manager=self.clipboard,
            get_window_func=lambda: (1001, "Document - Notepad", "Edit"),
            paste_func=self._mock_paste_success,
        )

        result = inserter.insert("Hello world from voice dictation!")

        self.assertTrue(result.success)
        self.assertEqual(result.status, InsertionStatus.SUCCESS)
        self.assertEqual(self.paste_calls, 1)

        # Prior clipboard content must have been restored
        self.assertEqual(self.clipboard.get_text(), "Existing prior clipboard text")

    def test_insert_no_target_fallback_notification(self) -> None:
        """Verify non-target window (Desktop/Taskbar) copies text and triggers notification."""
        notifications: list[tuple[str, str]] = []

        def on_no_target(txt: str, msg: str) -> None:
            notifications.append((txt, msg))

        # Desktop window (Progman)
        inserter = TextInserter(
            clipboard_manager=self.clipboard,
            get_window_func=lambda: (500, "Program Manager", "Progman"),
            paste_func=self._mock_paste_success,
            on_no_target=on_no_target,
        )

        dictated_text = "Important note to preserve"
        result = inserter.insert(dictated_text)

        self.assertFalse(result.success)
        self.assertEqual(result.status, InsertionStatus.NO_TARGET)
        self.assertIn("No text field detected", result.message)

        # Ensure no paste synthesized
        self.assertEqual(self.paste_calls, 0)

        # Text safely copied to clipboard
        self.assertEqual(self.clipboard.get_text(), dictated_text)

        # Notification dispatched
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0][0], dictated_text)
        self.assertIn("copied to clipboard", notifications[0][1])

    def test_insert_paste_failure_fallback(self) -> None:
        """Verify when key synthesis fails, text is safely preserved in clipboard."""
        notifications: list[tuple[str, str]] = []

        inserter = TextInserter(
            clipboard_manager=self.clipboard,
            get_window_func=lambda: (2002, "Editor", "RichEdit20W"),
            paste_func=self._mock_paste_fail,
            on_no_target=lambda t, m: notifications.append((t, m)),
        )

        result = inserter.insert("Text that failed paste")
        self.assertFalse(result.success)
        self.assertEqual(result.status, InsertionStatus.FALLBACK_COPIED)
        self.assertEqual(self.clipboard.get_text(), "Text that failed paste")
        self.assertEqual(len(notifications), 1)

    def test_empty_text_returns_success_immediately(self) -> None:
        """Verify empty string does not perform any clipboard operations."""
        inserter = TextInserter(
            clipboard_manager=self.clipboard,
            get_window_func=lambda: (1001, "Notepad", "Edit"),
            paste_func=self._mock_paste_success,
        )

        result = inserter.insert("")
        self.assertTrue(result.success)
        self.assertEqual(self.paste_calls, 0)

    def test_target_validation_rules(self) -> None:
        """Verify invalid window classes are rejected and standard apps accepted."""
        inserter = TextInserter()

        self.assertFalse(inserter.is_valid_target(0, "", ""))
        self.assertFalse(inserter.is_valid_target(1, "Desktop", "Progman"))
        self.assertFalse(inserter.is_valid_target(2, "Worker", "WorkerW"))
        self.assertFalse(inserter.is_valid_target(3, "Taskbar", "Shell_TrayWnd"))
        self.assertFalse(inserter.is_valid_target(4, "Windows Lock", "LockScreenWindow"))

        # Valid windows
        self.assertTrue(inserter.is_valid_target(10, "Notepad", "Notepad"))
        self.assertTrue(inserter.is_valid_target(11, "Chrome", "Chrome_WidgetWin_1"))
        self.assertTrue(inserter.is_valid_target(12, "Word", "OpusApp"))


if __name__ == "__main__":
    unittest.main()
