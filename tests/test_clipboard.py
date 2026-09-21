"""Unit tests for Windows clipboard manager, format preservation, and restoration."""

import unittest

from voice_agent.clipboard.manager import (
    CF_DIB,
    CF_TEXT,
    CF_UNICODETEXT,
    ClipboardManager,
    ClipboardSnapshot,
    SimulatedClipboardBackend,
)


class TestClipboardManager(unittest.TestCase):
    """Test suite for ClipboardManager operations and format preservation."""

    def setUp(self) -> None:
        self.backend = SimulatedClipboardBackend()
        self.manager = ClipboardManager(clipboard_module=self.backend)

    def test_set_and_get_text(self) -> None:
        """Verify setting and reading unicode text."""
        success = self.manager.set_text("Hello from Voice Agent!")
        self.assertTrue(success)
        self.assertEqual(self.manager.get_text(), "Hello from Voice Agent!")

    def test_format_preservation_and_restoration(self) -> None:
        """Verify multi-format snapshot captures and completely restores original formats."""
        # 1. Populate clipboard with multiple distinct formats (e.g. text + image/DIB + rich text)
        self.backend.SetClipboardData(CF_UNICODETEXT, "Original text snippet")
        self.backend.SetClipboardData(CF_TEXT, b"Original ASCII")
        self.backend.SetClipboardData(CF_DIB, b"fake_raw_dib_bitmap_bytes_12345")

        # 2. Capture snapshot
        snapshot = self.manager.create_snapshot()
        self.assertFalse(snapshot.is_empty())
        self.assertEqual(len(snapshot.formats), 3)
        self.assertIn(CF_UNICODETEXT, snapshot.formats)
        self.assertIn(CF_DIB, snapshot.formats)

        # 3. Inject new dictated text into clipboard
        injected = self.manager.set_text("Transcribed spoken dictation.")
        self.assertTrue(injected)
        self.assertEqual(self.manager.get_text(), "Transcribed spoken dictation.")
        # Only CF_UNICODETEXT is present now
        self.assertFalse(self.backend.IsClipboardFormatAvailable(CF_DIB))

        # 4. Restore original snapshot
        restored = self.manager.restore_snapshot(snapshot)
        self.assertTrue(restored)

        # 5. Assert all original formats and content restored
        self.assertEqual(self.manager.get_text(), "Original text snippet")
        self.assertTrue(self.backend.IsClipboardFormatAvailable(CF_DIB))
        self.assertEqual(self.backend.GetClipboardData(CF_DIB), b"fake_raw_dib_bitmap_bytes_12345")

    def test_keep_in_clipboard_bypasses_restoration(self) -> None:
        """Verify keep_in_clipboard=True leaves dictated text on the clipboard."""
        manager_keep = ClipboardManager(keep_in_clipboard=True, clipboard_module=self.backend)

        self.backend.SetClipboardData(CF_UNICODETEXT, "Prior contents")
        snapshot = manager_keep.create_snapshot()

        manager_keep.set_text("Preserved dictation text")

        # Restore called, but should bypass
        manager_keep.restore_snapshot(snapshot)

        self.assertEqual(manager_keep.get_text(), "Preserved dictation text")

    def test_retry_on_clipboard_lock(self) -> None:
        """Verify retry mechanism recovers from temporary clipboard contention."""
        self.backend.should_simulate_lock = True
        self.backend.lock_attempts = 0

        # Should retry twice, then succeed on 3rd attempt
        success = self.manager.set_text("Retry succeeded!")
        self.assertTrue(success)
        self.assertEqual(self.manager.get_text(), "Retry succeeded!")
        self.assertEqual(self.backend.lock_attempts, 2)

    def test_clear_and_empty_snapshot(self) -> None:
        """Verify clear() removes all clipboard formats."""
        self.manager.set_text("To be cleared")
        self.assertEqual(self.manager.get_text(), "To be cleared")

        cleared = self.manager.clear()
        self.assertTrue(cleared)
        self.assertEqual(self.manager.get_text(), "")

        # Restoring empty snapshot clears clipboard
        self.manager.set_text("Some text")
        empty_snapshot = ClipboardSnapshot()
        self.manager.restore_snapshot(empty_snapshot)
        self.assertEqual(self.manager.get_text(), "")


if __name__ == "__main__":
    unittest.main()
