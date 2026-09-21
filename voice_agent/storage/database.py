"""SQLite database management and schema migration engine for PC Voice Agent.

Provides thread-safe connection pooling, WAL mode optimization,
automatic migrations, and history storage operations.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Generator

from voice_agent.app.config import get_default_config_dir
from voice_agent.storage.models import HistoryEntry


def get_default_db_path() -> Path:
    """Return default database file location in APPDATA."""
    return get_default_config_dir() / "data.db"


class DatabaseManager:
    """Manages SQLite connection lifecycle, schema migrations, and queries."""

    # Current schema version
    CURRENT_VERSION = 1

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_default_db_path()
        self._local = threading.local()
        self._lock = threading.Lock()
        self.initialize()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a thread-local SQLite connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            # Enable WAL mode and foreign keys for high-performance concurrency
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            self._local.conn = conn
        return self._local.conn

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager yielding thread-safe database connection."""
        conn = self._get_connection()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise

    def initialize(self) -> None:
        """Initialize tables and run all pending migrations."""
        with self._lock:
            with self.connection() as conn:
                # Create migrations table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version INTEGER PRIMARY KEY,
                        applied_at TEXT NOT NULL
                    );
                    """
                )
                conn.commit()

                # Get currently applied version
                cur = conn.execute("SELECT MAX(version) FROM schema_migrations;")
                row = cur.fetchone()
                current_ver = row[0] if row and row[0] is not None else 0

                if current_ver < 1:
                    self._apply_migration_v1(conn)
                    conn.execute(
                        "INSERT INTO schema_migrations (version, applied_at) VALUES (1, ?);",
                        (datetime.now(timezone.utc).isoformat(),),
                    )
                    conn.commit()

    def _apply_migration_v1(self, conn: sqlite3.Connection) -> None:
        """Apply Version 1 Migration: History and App Metadata tables."""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                mode TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                processed_text TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT DEFAULT '{}'
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history (timestamp);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_mode ON history (mode);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_status ON history (status);")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

    # -------------------------------------------------------------------------
    # History Operations
    # -------------------------------------------------------------------------

    def insert_history(self, entry: HistoryEntry) -> int:
        """Insert a history entry and return the newly generated ID."""
        with self.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO history (timestamp, mode, raw_text, processed_text, status, details)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    entry.timestamp,
                    entry.mode,
                    entry.raw_text,
                    entry.processed_text,
                    entry.status,
                    entry.details_json,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
        mode: str | None = None,
        query: str | None = None,
    ) -> list[HistoryEntry]:
        """Fetch filtered and paginated history records ordered newest first."""
        sql = "SELECT * FROM history WHERE 1=1"
        params: list[Any] = []

        if mode:
            sql += " AND mode = ?"
            params.append(mode)

        if query:
            sql += " AND (processed_text LIKE ? OR raw_text LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])

        sql += " ORDER BY timestamp DESC, id DESC LIMIT ? OFFSET ?;"
        params.extend([limit, offset])

        with self.connection() as conn:
            cur = conn.execute(sql, params)
            rows = cur.fetchall()
            return [HistoryEntry.from_row(dict(r)) for r in rows]

    def delete_history_entry(self, entry_id: int) -> bool:
        """Delete a single history entry by ID."""
        with self.connection() as conn:
            cur = conn.execute("DELETE FROM history WHERE id = ?;", (entry_id,))
            conn.commit()
            return cur.rowcount > 0

    def clear_history(self) -> int:
        """Delete all history entries."""
        with self.connection() as conn:
            cur = conn.execute("DELETE FROM history;")
            conn.commit()
            return cur.rowcount

    def purge_old_history(self, retention_days: int) -> int:
        """Purge history records older than retention_days.

        Returns:
            Count of deleted records.
        """
        if retention_days <= 0:
            return 0
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        with self.connection() as conn:
            cur = conn.execute("DELETE FROM history WHERE timestamp < ?;", (cutoff,))
            conn.commit()
            return cur.rowcount

    # -------------------------------------------------------------------------
    # Metadata Operations
    # -------------------------------------------------------------------------

    def set_metadata(self, key: str, value: str) -> None:
        """Set or update a persistent metadata key-value pair."""
        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO app_metadata (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at;
                """,
                (key, value, now),
            )
            conn.commit()

    def get_metadata(self, key: str, default: str | None = None) -> str | None:
        """Retrieve a persistent metadata value by key."""
        with self.connection() as conn:
            cur = conn.execute("SELECT value FROM app_metadata WHERE key = ?;", (key,))
            row = cur.fetchone()
            if row:
                return str(row["value"])
            return default

    def close(self) -> None:
        """Close thread-local database connection if active."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None
