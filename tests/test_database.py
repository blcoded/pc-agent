"""Unit tests for SQLite database and migration engine."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import threading
import unittest

from voice_agent.storage.database import DatabaseManager
from voice_agent.storage.models import HistoryEntry


class TestDatabaseManager(unittest.TestCase):
    """Test suite for SQLite DatabaseManager operations."""

    def setUp(self) -> None:
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.test_dir.name) / "test.db"
        self.db = DatabaseManager(self.db_path)

    def tearDown(self) -> None:
        self.db.close()
        self.test_dir.cleanup()

    def test_database_initialization_and_schema(self) -> None:
        """Verify initialization runs migrations and creates expected tables."""
        with self.db.connection() as conn:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
            )
            tables = [row["name"] for row in cur.fetchall()]

        self.assertIn("history", tables)
        self.assertIn("app_metadata", tables)
        self.assertIn("schema_migrations", tables)

    def test_insert_and_get_history(self) -> None:
        """Verify inserting and querying history records."""
        entry = HistoryEntry(
            mode="dictation",
            raw_text="hello world",
            processed_text="Hello world.",
            status="success",
            details={"engine": "whisper-base"},
        )
        entry_id = self.db.insert_history(entry)
        self.assertGreater(entry_id, 0)

        history = self.db.get_history()
        self.assertEqual(len(history), 1)
        record = history[0]
        self.assertEqual(record.id, entry_id)
        self.assertEqual(record.processed_text, "Hello world.")
        self.assertEqual(record.details.get("engine"), "whisper-base")

    def test_history_filtering_and_search(self) -> None:
        """Verify mode filtering and text query search."""
        self.db.insert_history(HistoryEntry(mode="dictation", raw_text="report", processed_text="Report"))
        self.db.insert_history(HistoryEntry(mode="control", raw_text="open notepad", processed_text="open_application(notepad)"))
        self.db.insert_history(HistoryEntry(mode="dictation", raw_text="invoice", processed_text="Invoice"))

        dictation_only = self.db.get_history(mode="dictation")
        self.assertEqual(len(dictation_only), 2)

        control_only = self.db.get_history(mode="control")
        self.assertEqual(len(control_only), 1)

        search_result = self.db.get_history(query="notepad")
        self.assertEqual(len(search_result), 1)
        self.assertEqual(search_result[0].mode, "control")

    def test_delete_and_clear_history(self) -> None:
        """Verify individual deletion and clearing all history."""
        id1 = self.db.insert_history(HistoryEntry(mode="dictation", raw_text="one", processed_text="One"))
        id2 = self.db.insert_history(HistoryEntry(mode="dictation", raw_text="two", processed_text="Two"))

        deleted = self.db.delete_history_entry(id1)
        self.assertTrue(deleted)
        self.assertEqual(len(self.db.get_history()), 1)

        cleared_count = self.db.clear_history()
        self.assertEqual(cleared_count, 1)
        self.assertEqual(len(self.db.get_history()), 0)

    def test_retention_purge(self) -> None:
        """Verify purging records older than retention threshold."""
        old_time = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()
        recent_time = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()

        old_entry = HistoryEntry(timestamp=old_time, raw_text="old", processed_text="Old")
        recent_entry = HistoryEntry(timestamp=recent_time, raw_text="recent", processed_text="Recent")

        self.db.insert_history(old_entry)
        self.db.insert_history(recent_entry)

        self.assertEqual(len(self.db.get_history()), 2)
        purged = self.db.purge_old_history(retention_days=30)
        self.assertEqual(purged, 1)

        remaining = self.db.get_history()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].processed_text, "Recent")

    def test_metadata_operations(self) -> None:
        """Verify key-value metadata get and set."""
        self.assertIsNone(self.db.get_metadata("test_key"))
        self.db.set_metadata("test_key", "test_value")
        self.assertEqual(self.db.get_metadata("test_key"), "test_value")

        # Update key
        self.db.set_metadata("test_key", "updated_value")
        self.assertEqual(self.db.get_metadata("test_key"), "updated_value")

    def test_concurrent_writes(self) -> None:
        """Verify thread-safe concurrent insertions."""
        errors: list[Exception] = []

        def worker(num: int) -> None:
            try:
                for i in range(10):
                    self.db.insert_history(
                        HistoryEntry(raw_text=f"thread_{num}_{i}", processed_text=f"Thread {num} {i}")
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(self.db.get_history(limit=100)), 50)


if __name__ == "__main__":
    unittest.main()
