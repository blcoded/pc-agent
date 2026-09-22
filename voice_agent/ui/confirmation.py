"""Risk Confirmation Modal Dialog for PC Voice Agent.

Displays an accessible, explicit modal dialog for Medium and High risk voice actions:
- Clear visual severity indicators (Yellow/Amber for Medium, Red for High).
- Exact action description and target details.
- Default focus on Confirm (Enter) and Cancel (Esc).
- Automatic timeout countdown with auto-cancellation if unattended.
- Graceful headless fallback for testing and non-GUI environments.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from voice_agent.control.models import ActionRequest, RiskLevel

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtGui import QColor, QFont, QKeyEvent
    from PySide6.QtWidgets import (
        QApplication,
        QDialog,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
    HAS_PYSIDE = True
except ImportError:
    HAS_PYSIDE = False


if HAS_PYSIDE:
    _BaseDialog = QDialog
else:
    class _BaseDialog:  # type: ignore[no-redef]
        """Headless simulation base dialog when PySide6 is unavailable."""

        Accepted = 1
        Rejected = 0

        def __init__(self, parent: Any = None) -> None:
            self.parent = parent
            self._result = 0

        def setWindowTitle(self, title: str) -> None:
            pass

        def setWindowFlags(self, flags: Any) -> None:
            pass

        def setAttribute(self, attr: Any, on: bool = True) -> None:
            pass

        def setModal(self, modal: bool) -> None:
            pass

        def accept(self) -> None:
            self._result = self.Accepted

        def reject(self) -> None:
            self._result = self.Rejected

        def exec(self) -> int:
            return self._result

        def result(self) -> int:
            return self._result


class RiskConfirmationDialog(_BaseDialog):
    """Modal confirmation dialog for medium and high-risk control actions."""

    Accepted = 1
    Rejected = 0


    def __init__(
        self,
        action: ActionRequest,
        prompt: str | None = None,
        timeout_seconds: int = 15,
        parent: Any = None,
    ) -> None:
        """Initialize the confirmation dialog.

        Args:
            action: The ActionRequest requiring confirmation.
            prompt: User-facing question (e.g. "Delete 'report.docx'?")
            timeout_seconds: Seconds before unattended dialog cancels automatically.
            parent: Optional parent QWidget.
        """
        super().__init__(parent)
        self.action = action
        self.risk_level = action.risk_level
        self.prompt = prompt or f"Confirm executing '{action.action_type.value}'?"
        self.timeout_seconds = max(1, timeout_seconds)
        self.remaining_seconds = self.timeout_seconds
        self._confirmed: bool = False

        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize widget layout, styles, and countdown timer."""
        self.setWindowTitle("Voice Agent - Action Confirmation")

        # Visual styling based on risk level
        if self.risk_level == RiskLevel.HIGH:
            self.header_title = "⚠️ HIGH RISK OPERATION"
            self.primary_color = "#D32F2F"  # Red
            self.bg_color = "#FFEBEE"
        else:
            self.header_title = "⚠️ MEDIUM RISK ACTION"
            self.primary_color = "#F57C00"  # Orange/Amber
            self.bg_color = "#FFF8E1"

        if HAS_PYSIDE:
            self.setModal(True)
            self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
            self.setMinimumWidth(420)

            main_layout = QVBoxLayout(self)
            main_layout.setSpacing(14)
            main_layout.setContentsMargins(20, 20, 20, 20)

            # 1. Header Banner
            self.header_label = QLabel(self.header_title, self)
            self.header_label.setStyleSheet(
                f"font-weight: bold; font-size: 14px; color: {self.primary_color};"
            )
            main_layout.addWidget(self.header_label)

            # 2. Main Prompt
            self.prompt_label = QLabel(self.prompt, self)
            self.prompt_label.setWordWrap(True)
            self.prompt_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #212121;")
            main_layout.addWidget(self.prompt_label)

            # 3. Action Command Detail
            detail_text = f"Spoken Command: \"{self.action.raw_command}\"\nAction: {self.action.action_type.value}"
            self.detail_label = QLabel(detail_text, self)
            self.detail_label.setStyleSheet(
                "font-size: 12px; color: #616161; background: #F5F5F5; padding: 8px; border-radius: 4px;"
            )
            main_layout.addWidget(self.detail_label)

            # 4. Timeout Countdown Label
            self.countdown_label = QLabel(f"Auto-cancelling in {self.remaining_seconds}s...", self)
            self.countdown_label.setStyleSheet("font-size: 11px; color: #757575; font-style: italic;")
            main_layout.addWidget(self.countdown_label)

            # 5. Buttons
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()

            self.cancel_button = QPushButton("Cancel (Esc)", self)
            self.cancel_button.setStyleSheet(
                "padding: 8px 16px; font-size: 13px; border: 1px solid #BDBDBD; border-radius: 4px; background: white;"
            )
            self.cancel_button.clicked.connect(self.on_cancel)
            btn_layout.addWidget(self.cancel_button)

            self.confirm_button = QPushButton("Confirm (Enter)", self)
            self.confirm_button.setStyleSheet(
                f"padding: 8px 18px; font-size: 13px; font-weight: bold; color: white; "
                f"background: {self.primary_color}; border: none; border-radius: 4px;"
            )
            self.confirm_button.setDefault(True)
            self.confirm_button.setFocus()
            self.confirm_button.clicked.connect(self.on_confirm)
            btn_layout.addWidget(self.confirm_button)

            main_layout.addLayout(btn_layout)

            # Setup QTimer for countdown
            self.timer = QTimer(self)
            self.timer.setInterval(1000)
            self.timer.timeout.connect(self._on_timer_tick)
            self.timer.start()

    def _on_timer_tick(self) -> None:
        """Handle 1-second countdown tick."""
        self.remaining_seconds -= 1
        if HAS_PYSIDE and hasattr(self, "countdown_label"):
            self.countdown_label.setText(f"Auto-cancelling in {self.remaining_seconds}s...")

        if self.remaining_seconds <= 0:
            logger.info("Confirmation dialog timed out unattended. Auto-cancelling.")
            self.on_timeout()

    def on_confirm(self) -> None:
        """Handle explicit user confirmation."""
        logger.info("User confirmed action '%s'", self.action.action_type.value)
        self._confirmed = True
        self.action.confirmed = True
        if HAS_PYSIDE and hasattr(self, "timer") and self.timer.isActive():
            self.timer.stop()
        self.accept()

    def on_cancel(self) -> None:
        """Handle user cancellation."""
        logger.info("User cancelled action '%s'", self.action.action_type.value)
        self._confirmed = False
        self.action.confirmed = False
        if HAS_PYSIDE and hasattr(self, "timer") and self.timer.isActive():
            self.timer.stop()
        self.reject()

    def on_timeout(self) -> None:
        """Handle timeout expiration (treated as cancellation)."""
        self._confirmed = False
        self.action.confirmed = False
        if HAS_PYSIDE and hasattr(self, "timer") and self.timer.isActive():
            self.timer.stop()
        self.reject()

    def keyPressEvent(self, event: Any) -> None:
        """Handle keyboard shortcuts (Enter to confirm, Esc to cancel)."""
        if HAS_PYSIDE and isinstance(event, QKeyEvent):
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.on_confirm()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Escape:
                self.on_cancel()
                event.accept()
                return
        super().keyPressEvent(event)

    @property
    def is_confirmed(self) -> bool:
        """Whether the user approved the action."""
        return self._confirmed


def request_user_confirmation(
    action: ActionRequest,
    prompt: str | None = None,
    timeout_seconds: int = 15,
) -> bool:
    """Helper function to present the modal dialog and return approval bool.

    Args:
        action: The ActionRequest.
        prompt: Optional custom prompt.
        timeout_seconds: Seconds until timeout.

    Returns:
        bool: True if confirmed, False if cancelled or timed out.
    """
    dialog = RiskConfirmationDialog(
        action=action,
        prompt=prompt,
        timeout_seconds=timeout_seconds,
    )
    result = dialog.exec()
    return result == _BaseDialog.Accepted and dialog.is_confirmed


__all__ = ["RiskConfirmationDialog", "request_user_confirmation"]
