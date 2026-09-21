"""History Viewer Window for PC Voice Agent.

Displays desktop interface for browsing, filtering, searching, copying,
and deleting past dictation and control interaction records.
Includes headless simulation fallback for testing environments.
"""

from __future__ import annotations

import logging
from typing import Any

from voice_agent.clipboard.manager import ClipboardManager
from voice_agent.storage.history import HistoryRepository
from voice_agent.storage.models import HistoryEntry

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
    HAS_PYSIDE = True
except ImportError:
    HAS_PYSIDE = False


if HAS_PYSIDE:
    _BaseWidget = QWidget
else:
    class _BaseWidget:  # type: ignore[no-redef]
        """Headless base widget when PySide6 is unavailable."""

        def __init__(self, parent: Any = None) -> None:
            self.parent = parent

        def setWindowTitle(self, title: str) -> None:
            pass

        def resize(self, w: int, h: int) -> None:
            pass

        def show(self) -> None:
            pass

        def close(self) -> None:
            pass


class HistoryViewerWindow(_BaseWidget):
    """Desktop window for viewing and managing interaction history."""

    def __init__(
        self,
        repository: HistoryRepository | None = None,
        clipboard: ClipboardManager | None = None,
        parent: Any = None,
        page_size: int = 50,
    ) -> None:
        """Initialize the History Viewer window.

        Args:
            repository: HistoryRepository instance.
            clipboard: ClipboardManager instance.
            parent: Optional parent QWidget.
            page_size: Number of entries per page.
        """
        super().__init__(parent)
        self.repo = repository or HistoryRepository()
        self.clipboard = clipboard or ClipboardManager()
        self.page_size = max(1, page_size)

        self.current_page: int = 0
        self.mode_filter: str = "All"
        self.search_query: str = ""
        self.selected_entry_id: int | None = None
        self.entries: list[HistoryEntry] = []
        self.total_count: int = 0

        self._init_ui()
        self.load_data()

    def _init_ui(self) -> None:
        """Construct widget controls and layout."""
        self.setWindowTitle("Voice Agent - Interaction History")

        if HAS_PYSIDE:
            self.resize(800, 520)
            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(16, 16, 16, 16)
            main_layout.setSpacing(12)

            # 1. Filter and Search Bar Row
            filter_layout = QHBoxLayout()

            self.search_box = QLineEdit(self)
            self.search_box.setPlaceholderText("Search spoken text or results...")
            self.search_box.textChanged.connect(self.on_search_changed)
            filter_layout.addWidget(self.search_box, stretch=3)

            mode_label = QLabel("Mode:", self)
            filter_layout.addWidget(mode_label)

            self.mode_combo = QComboBox(self)
            self.mode_combo.addItems(["All", "Dictation", "Control"])
            self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
            filter_layout.addWidget(self.mode_combo, stretch=1)

            main_layout.addLayout(filter_layout)

            # 2. History Table
            self.table = QTableWidget(self)
            self.table.setColumnCount(4)
            self.table.setHorizontalHeaderLabels(["Timestamp", "Mode", "Spoken Text", "Result / Status"])
            self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
            self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
            self.table.itemSelectionChanged.connect(self._on_selection_changed)
            main_layout.addWidget(self.table)

            # 3. Pagination Controls Row
            page_layout = QHBoxLayout()
            self.prev_btn = QPushButton("◀ Previous", self)
            self.prev_btn.clicked.connect(self.on_prev_page)
            page_layout.addWidget(self.prev_btn)

            self.page_label = QLabel("Page 1 of 1", self)
            self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            page_layout.addWidget(self.page_label, stretch=1)

            self.next_btn = QPushButton("Next ▶", self)
            self.next_btn.clicked.connect(self.on_next_page)
            page_layout.addWidget(self.next_btn)

            main_layout.addLayout(page_layout)

            # 4. Action Buttons Row
            btn_layout = QHBoxLayout()

            self.copy_btn = QPushButton("Copy Spoken Text", self)
            self.copy_btn.clicked.connect(self.on_copy_selected)
            btn_layout.addWidget(self.copy_btn)

            self.delete_btn = QPushButton("Delete Entry", self)
            self.delete_btn.clicked.connect(self.on_delete_selected)
            btn_layout.addWidget(self.delete_btn)

            btn_layout.addStretch()

            self.clear_btn = QPushButton("Clear All History", self)
            self.clear_btn.setStyleSheet("color: #D32F2F;")
            self.clear_btn.clicked.connect(self.on_clear_all)
            btn_layout.addWidget(self.clear_btn)

            main_layout.addLayout(btn_layout)

    def load_data(self) -> None:
        """Fetch filtered records from the repository and populate table."""
        mode_param = None if self.mode_filter.lower() == "all" else self.mode_filter.lower()
        query_param = self.search_query.strip() if self.search_query.strip() else None

        self.total_count = self.repo.count_entries(query=query_param, mode=mode_param)
        offset = self.current_page * self.page_size
        self.entries = self.repo.get_entries(
            limit=self.page_size,
            offset=offset,
            query=query_param,
            mode=mode_param,
        )

        total_pages = max(1, (self.total_count + self.page_size - 1) // self.page_size)

        if HAS_PYSIDE and hasattr(self, "table"):
            self.table.setRowCount(len(self.entries))
            for row_idx, entry in enumerate(self.entries):
                # Clean timestamp formatting
                time_str = entry.timestamp.split("T")[0] if "T" in entry.timestamp else entry.timestamp
                self.table.setItem(row_idx, 0, QTableWidgetItem(time_str))
                self.table.setItem(row_idx, 1, QTableWidgetItem(entry.mode.capitalize()))
                self.table.setItem(row_idx, 2, QTableWidgetItem(entry.raw_text))
                result_repr = f"[{entry.status}] {entry.processed_text}"
                self.table.setItem(row_idx, 3, QTableWidgetItem(result_repr))

            self.page_label.setText(f"Page {self.current_page + 1} of {total_pages} ({self.total_count} entries)")
            self.prev_btn.setEnabled(self.current_page > 0)
            self.next_btn.setEnabled((self.current_page + 1) < total_pages)

    def _on_selection_changed(self) -> None:
        """Handle table row selection change."""
        if HAS_PYSIDE and hasattr(self, "table"):
            selected = self.table.selectedItems()
            if selected:
                row = selected[0].row()
                if 0 <= row < len(self.entries):
                    self.selected_entry_id = self.entries[row].id
                    return
        self.selected_entry_id = None

    def on_search_changed(self, text: str) -> None:
        """Handle search bar input changes."""
        self.search_query = text
        self.current_page = 0
        self.load_data()

    def on_mode_changed(self, mode: str) -> None:
        """Handle mode dropdown selection changes."""
        self.mode_filter = mode
        self.current_page = 0
        self.load_data()

    def on_prev_page(self) -> None:
        """Navigate to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.load_data()

    def on_next_page(self) -> None:
        """Navigate to next page."""
        total_pages = (self.total_count + self.page_size - 1) // self.page_size
        if (self.current_page + 1) < total_pages:
            self.current_page += 1
            self.load_data()

    def on_copy_selected(self) -> bool:
        """Copy the selected entry's spoken text to the clipboard."""
        target_entry = self._get_selected_entry()
        if not target_entry:
            logger.warning("No entry selected to copy.")
            return False

        copied = self.clipboard.set_text(target_entry.raw_text)
        logger.info("Copied entry #%s text to clipboard (success=%s)", target_entry.id, copied)
        return copied

    def on_delete_selected(self) -> bool:
        """Delete the currently selected history entry."""
        target_entry = self._get_selected_entry()
        if not target_entry or target_entry.id is None:
            logger.warning("No entry selected to delete.")
            return False

        deleted = self.repo.delete_entry(target_entry.id)
        if deleted:
            logger.info("Deleted history entry #%s", target_entry.id)
            self.selected_entry_id = None
            self.load_data()
        return deleted

    def on_clear_all(self) -> int:
        """Clear all entries from history."""
        cleared_count = self.repo.clear_history()
        logger.info("Cleared all history (%d entries removed)", cleared_count)
        self.current_page = 0
        self.selected_entry_id = None
        self.load_data()
        return cleared_count

    def _get_selected_entry(self) -> HistoryEntry | None:
        """Helper to find the currently selected HistoryEntry."""
        if self.selected_entry_id is None:
            return None
        for entry in self.entries:
            if entry.id == self.selected_entry_id:
                return entry
        return self.repo.get_entry_by_id(self.selected_entry_id)


__all__ = ["HistoryViewerWindow"]
