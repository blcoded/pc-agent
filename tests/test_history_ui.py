"""Unit tests for History Viewer Window (TASK-7.2)."""

import tempfile
import unittest
from pathlib import Path

from voice_agent.clipboard.manager import ClipboardManager, SimulatedClipboardBackend
from voice_agent.storage.database import DatabaseManager
from voice_agent.storage.history import HistoryRepository
from voice_agent.ui.history import HistoryViewerWindow


class TestHistoryViewerUI(unittest.TestCase):
    """Test suite for HistoryViewerWindow filtering, searching, selection, and operations."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "ui_history_test.db"
        self.db = DatabaseManager(db_path=self.db_path)
        self.repo = HistoryRepository(db=self.db)
        self.clip_backend = SimulatedClipboardBackend()
        self.clipboard = ClipboardManager(clipboard_module=self.clip_backend)

        # Seed sample data
        self.id_d1 = self.repo.record(mode="dictation", raw_text="Hello world", processed_text="Hello world.")
        self.id_d2 = self.repo.record(mode="dictation", raw_text="Another dictation note", processed_text="Another note.")
        self.id_c1 = self.repo.record(mode="control", raw_text="open notepad", processed_text="open_app(notepad)")
        self.id_c2 = self.repo.record(mode="control", raw_text="click button", processed_text="click(left)")

        self.window = HistoryViewerWindow(
            repository=self.repo,
            clipboard=self.clipboard,
            page_size=2,  # Small page size to test pagination
        )

    def tearDown(self) -> None:
        self.db.close()
        self.temp_dir.cleanup()

    def test_initial_load(self) -> None:
        """Verify initial data population with pagination."""
        self.assertEqual(self.window.total_count, 4)
        self.assertEqual(len(self.window.entries), 2)  # page_size=2
        self.assertEqual(self.window.current_page, 0)

    def test_mode_filtering(self) -> None:
        """Test filtering by dictation vs control mode."""
        # Dictation filter
        self.window.on_mode_changed("Dictation")
        self.assertEqual(self.window.total_count, 2)
        for e in self.window.entries:
            self.assertEqual(e.mode, "dictation")

        # Control filter
        self.window.on_mode_changed("Control")
        self.assertEqual(self.window.total_count, 2)
        for e in self.window.entries:
            self.assertEqual(e.mode, "control")

        # Reset to All
        self.window.on_mode_changed("All")
        self.assertEqual(self.window.total_count, 4)

    def test_search_filtering(self) -> None:
        """Test search query filtering."""
        self.window.on_search_changed("notepad")
        self.assertEqual(self.window.total_count, 1)
        self.assertEqual(self.window.entries[0].raw_text, "open notepad")

        # Reset search
        self.window.on_search_changed("")
        self.assertEqual(self.window.total_count, 4)

    def test_pagination(self) -> None:
        """Test navigating across pages."""
        self.assertEqual(self.window.current_page, 0)
        page0_ids = [e.id for e in self.window.entries]

        # Next page
        self.window.on_next_page()
        self.assertEqual(self.window.current_page, 1)
        page1_ids = [e.id for e in self.window.entries]
        self.assertNotEqual(page0_ids, page1_ids)

        # Prev page
        self.window.on_prev_page()
        self.assertEqual(self.window.current_page, 0)
        self.assertEqual([e.id for e in self.window.entries], page0_ids)

    def test_copy_selected(self) -> None:
        """Test copying selected row text to clipboard."""
        self.window.selected_entry_id = self.id_d1
        copied = self.window.on_copy_selected()
        self.assertTrue(copied)
        self.assertEqual(self.clipboard.get_text(), "Hello world")

    def test_delete_selected(self) -> None:
        """Test deleting selected history entry."""
        self.window.selected_entry_id = self.id_d1
        deleted = self.window.on_delete_selected()
        self.assertTrue(deleted)
        self.assertEqual(self.window.total_count, 3)
        self.assertIsNone(self.repo.get_entry_by_id(self.id_d1))

    def test_clear_all(self) -> None:
        """Test clearing all interaction history."""
        cleared = self.window.on_clear_all()
        self.assertEqual(cleared, 4)
        self.assertEqual(self.window.total_count, 0)
        self.assertEqual(len(self.window.entries), 0)


if __name__ == "__main__":
    unittest.main()
