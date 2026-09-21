"""History Repository for PC Voice Agent.

Provides repository pattern abstractions for recording, querying, filtering,
cleaning up, and exporting interaction records across Dictation and Control modes.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from voice_agent.storage.database import DatabaseManager
from voice_agent.storage.models import HistoryEntry

logger = logging.getLogger(__name__)


class HistoryRepository:
    """Repository managing user interaction history records."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        """Initialize repository.

        Args:
            db: DatabaseManager instance. If omitted, uses default database.
        """
        self.db = db or DatabaseManager()

    def add_entry(self, entry: HistoryEntry) -> int:
        """Add a new history entry record.

        Args:
            entry: HistoryEntry to persist.

        Returns:
            int: The generated database record ID.
        """
        return self.db.insert_history(entry)

    def record(
        self,
        mode: str,
        raw_text: str,
        processed_text: str,
        status: str = "success",
        details: dict[str, Any] | None = None,
    ) -> int:
        """Convenience method to construct and record an interaction entry.

        Args:
            mode: Operational mode ('dictation' or 'control').
            raw_text: Spoken audio transcript or command.
            processed_text: Inserted text or action result summary.
            status: 'success', 'failed', or 'cancelled'.
            details: Optional metadata or action execution reports.

        Returns:
            int: Inserted entry ID.
        """
        entry = HistoryEntry(
            mode=mode,
            raw_text=raw_text,
            processed_text=processed_text,
            status=status,
            details=details or {},
        )
        return self.add_entry(entry)

    def get_entries(
        self,
        limit: int = 50,
        offset: int = 0,
        query: str | None = None,
        mode: str | None = None,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
    ) -> list[HistoryEntry]:
        """Query history entries with flexible multi-criteria filtering and pagination.

        Args:
            limit: Maximum records to return.
            offset: Record offset for pagination.
            query: Substring search filter against raw_text and processed_text.
            mode: Mode filter ('dictation' or 'control').
            start_date: Earliest ISO timestamp or datetime.
            end_date: Latest ISO timestamp or datetime.

        Returns:
            List of HistoryEntry objects ordered by newest first.
        """
        sql = "SELECT * FROM history WHERE 1=1"
        params: list[Any] = []

        if mode and mode.lower() != "all":
            sql += " AND mode = ?"
            params.append(mode.lower().strip())

        if query and query.strip():
            clean_q = f"%{query.strip()}%"
            sql += " AND (raw_text LIKE ? OR processed_text LIKE ?)"
            params.extend([clean_q, clean_q])

        if start_date:
            iso_start = start_date.isoformat() if isinstance(start_date, datetime) else str(start_date)
            sql += " AND timestamp >= ?"
            params.append(iso_start)

        if end_date:
            iso_end = end_date.isoformat() if isinstance(end_date, datetime) else str(end_date)
            sql += " AND timestamp <= ?"
            params.append(iso_end)

        sql += " ORDER BY timestamp DESC, id DESC LIMIT ? OFFSET ?;"
        params.extend([limit, offset])

        with self.db.connection() as conn:
            cur = conn.execute(sql, params)
            rows = cur.fetchall()
            return [HistoryEntry.from_row(dict(r)) for r in rows]

    def count_entries(
        self,
        query: str | None = None,
        mode: str | None = None,
    ) -> int:
        """Count total entries matching the given criteria.

        Args:
            query: Search text filter.
            mode: Operational mode filter.

        Returns:
            int: Number of matching rows.
        """
        sql = "SELECT COUNT(*) as count FROM history WHERE 1=1"
        params: list[Any] = []

        if mode and mode.lower() != "all":
            sql += " AND mode = ?"
            params.append(mode.lower().strip())

        if query and query.strip():
            clean_q = f"%{query.strip()}%"
            sql += " AND (raw_text LIKE ? OR processed_text LIKE ?)"
            params.extend([clean_q, clean_q])

        with self.db.connection() as conn:
            cur = conn.execute(sql, params)
            row = cur.fetchone()
            return int(row["count"]) if row else 0

    def get_entry_by_id(self, entry_id: int) -> HistoryEntry | None:
        """Retrieve a specific history entry by its primary key ID.

        Args:
            entry_id: Entry ID.

        Returns:
            HistoryEntry or None if not found.
        """
        with self.db.connection() as conn:
            cur = conn.execute("SELECT * FROM history WHERE id = ?;", (entry_id,))
            row = cur.fetchone()
            return HistoryEntry.from_row(dict(row)) if row else None

    def delete_entry(self, entry_id: int) -> bool:
        """Delete an individual history record by ID.

        Args:
            entry_id: Record primary key ID.

        Returns:
            bool: True if deleted.
        """
        return self.db.delete_history_entry(entry_id)

    def clear_history(self) -> int:
        """Clear all history entries.

        Returns:
            int: Number of cleared rows.
        """
        return self.db.clear_history()

    def auto_cleanup(self, retention_days: int = 30) -> int:
        """Purge entries older than the specified retention window.

        Args:
            retention_days: Max age of entries to preserve.

        Returns:
            int: Number of deleted entries.
        """
        return self.db.purge_old_history(retention_days)

    def export_to_json(self, output_path: Path | str, mode: str | None = None) -> int:
        """Export history entries to a JSON file.

        Args:
            output_path: File destination.
            mode: Optional mode filter.

        Returns:
            int: Number of exported records.
        """
        entries = self.get_entries(limit=100000, offset=0, mode=mode)
        records = [
            {
                "id": e.id,
                "timestamp": e.timestamp,
                "mode": e.mode,
                "raw_text": e.raw_text,
                "processed_text": e.processed_text,
                "status": e.status,
                "details": e.details,
            }
            for e in entries
        ]

        target_path = Path(output_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

        logger.info("Exported %d history records to JSON: %s", len(records), target_path)
        return len(records)

    def export_to_csv(self, output_path: Path | str, mode: str | None = None) -> int:
        """Export history entries to a CSV spreadsheet.

        Args:
            output_path: File destination.
            mode: Optional mode filter.

        Returns:
            int: Number of exported records.
        """
        entries = self.get_entries(limit=100000, offset=0, mode=mode)

        target_path = Path(output_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Timestamp", "Mode", "Raw Text", "Processed Text", "Status", "Details"])
            for e in entries:
                writer.writerow([
                    e.id,
                    e.timestamp,
                    e.mode,
                    e.raw_text,
                    e.processed_text,
                    e.status,
                    e.details_json,
                ])

        logger.info("Exported %d history records to CSV: %s", len(entries), target_path)
        return len(entries)


__all__ = ["HistoryRepository"]
