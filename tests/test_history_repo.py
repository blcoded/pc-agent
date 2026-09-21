"""Unit tests for History Repository and SQLite persistence (TASK-7.1)."""

import csv
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from voice_agent.storage.database import DatabaseManager
from voice_agent.storage.history import HistoryRepository
from voice_agent.storage.models import HistoryEntry


class TestHistoryRepository(unittest.TestCase):
    """Test suite for HistoryRepository operations, queries, exports, and auto-cleanup."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "history_test.db"
        self.db = DatabaseManager(db_path=self.db_path)
        self.repo = HistoryRepository(db=self.db)

    def tearDown(self) -> None:
        self.db.close()
        self.temp_dir.cleanup()

    def test_add_and_get_entry(self) -> None:
        """Test adding a single entry and retrieving it by ID."""
        entry_id = self.repo.record(
            mode="dictation",
            raw_text="hello world",
            processed_text="Hello world.",
            status="success",
            details={"char_count": 12},
        )
        self.assertGreater(entry_id, 0)

        entry = self.repo.get_entry_by_id(entry_id)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.mode, "dictation")
        self.assertEqual(entry.raw_text, "hello world")
        self.assertEqual(entry.processed_text, "Hello world.")
        self.assertEqual(entry.status, "success")
        self.assertEqual(entry.details.get("char_count"), 12)

    def test_filtering_and_pagination(self) -> None:
        """Test multi-criteria filtering by mode, query, and pagination."""
        # Insert test records
        self.repo.record(mode="dictation", raw_text="apples and oranges", processed_text="Apples and oranges.")
        self.repo.record(mode="dictation", raw_text="bananas are yellow", processed_text="Bananas are yellow.")
        self.repo.record(mode="control", raw_text="open notepad", processed_text="open_app(notepad)")
        self.repo.record(mode="control", raw_text="open chrome", processed_text="open_app(chrome)")

        # Total count
        self.assertEqual(self.repo.count_entries(), 4)

        # Mode filter
        dictation_entries = self.repo.get_entries(mode="dictation")
        self.assertEqual(len(dictation_entries), 2)
        control_entries = self.repo.get_entries(mode="control")
        self.assertEqual(len(control_entries), 2)

        # Query filter
        search_res = self.repo.get_entries(query="notepad")
        self.assertEqual(len(search_res), 1)
        self.assertEqual(search_res[0].raw_text, "open notepad")

        # Pagination
        page1 = self.repo.get_entries(limit=2, offset=0)
        page2 = self.repo.get_entries(limit=2, offset=2)
        self.assertEqual(len(page1), 2)
        self.assertEqual(len(page2), 2)
        self.assertNotEqual(page1[0].id, page2[0].id)

    def test_delete_and_clear(self) -> None:
        """Test single record deletion and clearing all history."""
        id1 = self.repo.record(mode="dictation", raw_text="test 1", processed_text="test 1")
        id2 = self.repo.record(mode="dictation", raw_text="test 2", processed_text="test 2")
        self.assertEqual(self.repo.count_entries(), 2)

        # Delete one
        deleted = self.repo.delete_entry(id1)
        self.assertTrue(deleted)
        self.assertEqual(self.repo.count_entries(), 1)
        self.assertIsNone(self.repo.get_entry_by_id(id1))

        # Clear all
        cleared = self.repo.clear_history()
        self.assertEqual(cleared, 1)
        self.assertEqual(self.repo.count_entries(), 0)

    def test_auto_cleanup_retention(self) -> None:
        """Test purging history records older than retention limit."""
        now = datetime.now(timezone.utc)
        old_time = (now - timedelta(days=45)).isoformat()
        recent_time = (now - timedelta(days=5)).isoformat()

        # Insert manually with specific timestamps
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO history (timestamp, mode, raw_text, processed_text, status, details)
                VALUES (?, 'dictation', 'old entry', 'old', 'success', '{}'),
                       (?, 'dictation', 'recent entry', 'recent', 'success', '{}');
                """,
                (old_time, recent_time),
            )
            conn.commit()

        self.assertEqual(self.repo.count_entries(), 2)

        # Auto cleanup with 30 days retention
        purged = self.repo.auto_cleanup(retention_days=30)
        self.assertEqual(purged, 1)
        self.assertEqual(self.repo.count_entries(), 1)
        entries = self.repo.get_entries()
        self.assertEqual(entries[0].raw_text, "recent entry")

    def test_export_to_json_and_csv(self) -> None:
        """Test exporting interaction history to JSON and CSV formats."""
        self.repo.record(mode="dictation", raw_text="speech test", processed_text="Speech test.")
        self.repo.record(mode="control", raw_text="click button", processed_text="click(left)")

        # Export JSON
        json_path = Path(self.temp_dir.name) / "exports" / "history.json"
        exported_count = self.repo.export_to_json(json_path)
        self.assertEqual(exported_count, 2)
        self.assertTrue(json_path.exists())

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["mode"], "control")

        # Export CSV
        csv_path = Path(self.temp_dir.name) / "exports" / "history.csv"
        csv_count = self.repo.export_to_csv(csv_path)
        self.assertEqual(csv_count, 2)
        self.assertTrue(csv_path.exists())

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = list(csv.reader(f))
            # 1 header row + 2 data rows
            self.assertEqual(len(reader), 3)
            self.assertEqual(reader[0], ["ID", "Timestamp", "Mode", "Raw Text", "Processed Text", "Status", "Details"])


if __name__ == "__main__":
    unittest.main()
