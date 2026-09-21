"""Data models for persistence and database storage."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any


@dataclass
class HistoryEntry:
    """Represents an interaction record in the history database."""

    id: int | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    mode: str = "dictation"  # "dictation" or "control"
    raw_text: str = ""
    processed_text: str = ""
    status: str = "success"  # "success", "failed", "cancelled"
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def details_json(self) -> str:
        """Serialize details dictionary to JSON string."""
        return json.dumps(self.details)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> HistoryEntry:
        """Instantiate HistoryEntry from a database row dictionary."""
        details_val = row.get("details", "{}")
        if isinstance(details_val, str):
            try:
                details_dict = json.loads(details_val)
            except Exception:
                details_dict = {}
        elif isinstance(details_val, dict):
            details_dict = details_val
        else:
            details_dict = {}

        return cls(
            id=row.get("id"),
            timestamp=row.get("timestamp", ""),
            mode=row.get("mode", "dictation"),
            raw_text=row.get("raw_text", ""),
            processed_text=row.get("processed_text", ""),
            status=row.get("status", "success"),
            details=details_dict,
        )
