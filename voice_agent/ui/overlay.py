"""Floating status overlay widget for visual state and audio level feedback."""

from __future__ import annotations

from dataclasses import dataclass
import sys
import time
from typing import Any, Callable

from voice_agent.app.config import AppConfig, load_config, save_config
from voice_agent.app.lifecycle import ControlState, DictationState
from voice_agent.app.logging import get_logger

logger = get_logger("ui.overlay")

OVERLAY_WIDTH = 220
OVERLAY_HEIGHT = 48

try:
    from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
    from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent
    from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QVBoxLayout, QWidget
    HAS_PYSIDE = True
except ImportError:
    HAS_PYSIDE = False


@dataclass
class VisualStateStyle:
    """Style configuration for an overlay operational state."""

    label: str
    primary_color: str  # Hex color code
    mode: str           # "dictation" or "control"


STATE_STYLES: dict[str, VisualStateStyle] = {
    # Dictation States
    "dictation_ready": VisualStateStyle(label="Ready", primary_color="#9E9E9E", mode="dictation"),
    "dictation_listening": VisualStateStyle(label="Listening...", primary_color="#F44336", mode="dictation"),
    "dictation_processing": VisualStateStyle(label="Processing...", primary_color="#2196F3", mode="dictation"),
    "dictation_typing": VisualStateStyle(label="Typing...", primary_color="#4CAF50", mode="dictation"),
    "dictation_no_target": VisualStateStyle(label="No Text Target", primary_color="#FF9800", mode="dictation"),
    "dictation_error": VisualStateStyle(label="Error", primary_color="#E91E63", mode="dictation"),
    # Control States
    "control_ready": VisualStateStyle(label="Control Ready", primary_color="#9E9E9E", mode="control"),
    "control_listening": VisualStateStyle(label="Listening (Control)...", primary_color="#9C27B0", mode="control"),
    "control_processing": VisualStateStyle(label="Parsing Command...", primary_color="#3F51B5", mode="control"),
    "control_validating": VisualStateStyle(label="Validating...", primary_color="#FF9800", mode="control"),
    "control_confirming": VisualStateStyle(label="Confirm Action?", primary_color="#FF5722", mode="control"),
    "control_executing": VisualStateStyle(label="Executing...", primary_color="#00BCD4", mode="control"),
    "control_result": VisualStateStyle(label="Action Completed", primary_color="#4CAF50", mode="control"),
    "control_error": VisualStateStyle(label="Action Failed", primary_color="#F44336", mode="control"),
}


if HAS_PYSIDE:
    _BaseWidget = QWidget
else:
    class _BaseWidget:  # type: ignore[no-redef]
        def __init__(self, parent: Any = None) -> None:
            self._geometry = (100, 100, OVERLAY_WIDTH, OVERLAY_HEIGHT)
            self._visible = False

        def setWindowFlags(self, flags: Any) -> None:
            pass

        def setAttribute(self, attr: Any, on: bool = True) -> None:
            pass

        def setFixedSize(self, w: int, h: int) -> None:
            self._geometry = (self._geometry[0], self._geometry[1], w, h)

        def move(self, x: int, y: int) -> None:
            self._geometry = (x, y, self._geometry[2], self._geometry[3])

        def x(self) -> int:
            return self._geometry[0]

        def y(self) -> int:
            return self._geometry[1]

        def width(self) -> int:
            return self._geometry[2]

        def height(self) -> int:
            return self._geometry[3]

        def show(self) -> None:
            self._visible = True

        def hide(self) -> None:
            self._visible = False

        def isVisible(self) -> bool:
            return self._visible

        def update(self) -> None:
            pass


class FloatingStatusOverlay(_BaseWidget):
    """Floating transparent pill widget displaying mode, state, and audio activity."""

    if HAS_PYSIDE:
        sig_set_dictation_state = Signal(object)
        sig_set_control_state = Signal(object)
        sig_set_audio_level = Signal(float)
        sig_reset = Signal()

    def __init__(
        self,
        config: AppConfig | None = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self.config: AppConfig = config or load_config()

        self.current_mode: str = "dictation"
        self.current_state_key: str = "dictation_ready"
        self.status_text: str = "Ready"
        self.audio_level: float = 0.0
        self._last_level_time: float = 0.0

        self._drag_pos: Any = None
        self._is_dragging: bool = False

        self._init_ui()
        self._restore_position()

        if HAS_PYSIDE:
            self.sig_set_dictation_state.connect(self._on_dictation_state)
            self.sig_set_control_state.connect(self._on_control_state)
            self.sig_set_audio_level.connect(self._on_audio_level)
            self.sig_reset.connect(self._on_reset)

            # Auto-reset timer to revert to "Ready" after transient results/errors
            if QApplication.instance():
                self._auto_reset_timer = QTimer(self)
                self._auto_reset_timer.setSingleShot(True)
                self._auto_reset_timer.timeout.connect(self._on_reset)
            else:
                self._auto_reset_timer = None

    def _init_ui(self) -> None:
        self.setFixedSize(OVERLAY_WIDTH, OVERLAY_HEIGHT)

        if HAS_PYSIDE:
            # Set window flags: stays on top, frameless, doesn't steal focus
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

    def _restore_position(self) -> None:
        """Position the overlay from saved configuration or default bottom-right."""
        saved_x = self.config.ui.overlay_x
        saved_y = self.config.ui.overlay_y

        if saved_x >= 0 and saved_y >= 0:
            self.move(saved_x, saved_y)
        else:
            # Default placement: Bottom right with 24px margins
            if HAS_PYSIDE and QApplication.primaryScreen():
                screen_geom = QApplication.primaryScreen().geometry()
                default_x = screen_geom.width() - OVERLAY_WIDTH - 30
                default_y = screen_geom.height() - OVERLAY_HEIGHT - 60
            else:
                default_x = 1000
                default_y = 700
            self.move(default_x, default_y)

    def set_dictation_state(self, state: DictationState | str) -> None:
        """Update overlay visual state for Dictation mode (thread-safe)."""
        if HAS_PYSIDE:
            self.sig_set_dictation_state.emit(state)
        else:
            self._on_dictation_state(state)

    def set_control_state(self, state: ControlState | str) -> None:
        """Update overlay visual state for Control mode (thread-safe)."""
        if HAS_PYSIDE:
            self.sig_set_control_state.emit(state)
        else:
            self._on_control_state(state)

    def set_audio_level(self, level: float) -> None:
        """Update volume meter level between 0.0 and 1.0 (thread-safe, throttled)."""
        clamped = max(0.0, min(1.0, level))
        self.audio_level = clamped

        now = time.perf_counter()
        if now - self._last_level_time < 0.033:  # Max 30 FPS repaint
            return
        self._last_level_time = now

        if HAS_PYSIDE:
            self.sig_set_audio_level.emit(clamped)
        else:
            self.update()

    def _on_dictation_state(self, state: DictationState | str) -> None:
        timer = getattr(self, "_auto_reset_timer", None)
        if timer and timer.isActive():
            timer.stop()
        self.current_mode = "dictation"
        state_val = state.value if isinstance(state, DictationState) else str(state).lower()
        key = f"dictation_{state_val}"
        self._apply_state(key)

        if state_val in ("typing", "no_target", "error") and timer:
            timer.start(2000)

    def _on_control_state(self, state: ControlState | str) -> None:
        timer = getattr(self, "_auto_reset_timer", None)
        if timer and timer.isActive():
            timer.stop()
        self.current_mode = "control"
        state_val = state.value if isinstance(state, ControlState) else str(state).lower()
        key = f"control_{state_val}"
        self._apply_state(key)

        if state_val in ("result", "error", "ready") and timer:
            timer.start(2000)

    def _on_audio_level(self, level: float) -> None:
        self.audio_level = level
        self.update()

    def _on_reset(self) -> None:
        self.current_mode = "dictation"
        self._apply_state("dictation_ready")

    def _apply_state(self, state_key: str) -> None:
        style = STATE_STYLES.get(state_key, STATE_STYLES["dictation_ready"])
        self.current_state_key = state_key
        self.status_text = style.label
        if "listening" not in state_key:
            self.audio_level = 0.0
        self.update()

    def mousePressEvent(self, event: Any) -> None:
        """Record drag anchor when user clicks on overlay."""
        if HAS_PYSIDE and isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            self._is_dragging = True
            event.accept()

    def mouseMoveEvent(self, event: Any) -> None:
        """Move widget according to cursor drag."""
        if HAS_PYSIDE and self._is_dragging and self._drag_pos is not None:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event: Any) -> None:
        """Save new position to persistent configuration when drag completes."""
        if HAS_PYSIDE and self._is_dragging:
            self._is_dragging = False
            self.save_current_position()
            event.accept()

    def save_current_position(self) -> None:
        """Save current screen coordinates to configuration file."""
        self.config.ui.overlay_x = self.x()
        self.config.ui.overlay_y = self.y()
        try:
            save_config(self.config)
            logger.debug("Overlay position saved: (%d, %d)", self.x(), self.y())
        except Exception as e:
            logger.error("Failed to save overlay position: %s", e)

    def paintEvent(self, event: Any) -> None:
        """Render the pill-shaped background, indicator dot, text, and VU meter."""
        if not HAS_PYSIDE:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        style = STATE_STYLES.get(self.current_state_key, STATE_STYLES["dictation_ready"])

        # 1. Background Pill: Dark frosted glass effect
        pill_rect = QRect(0, 0, OVERLAY_WIDTH, OVERLAY_HEIGHT)
        bg_color = QColor(25, 25, 30, 220)
        painter.setBrush(bg_color)
        border_color = QColor(style.primary_color)
        border_color.setAlpha(120)
        painter.setPen(border_color)
        painter.drawRoundedRect(pill_rect, 24, 24)

        # 2. State Indicator Dot
        dot_color = QColor(style.primary_color)
        painter.setBrush(dot_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(18, 18, 12, 12)

        # 3. Audio Activity Level Ring (when listening)
        if "listening" in self.current_state_key and self.audio_level > 0.05:
            pulse_radius = 6 + int(self.audio_level * 10)
            pulse_color = QColor(style.primary_color)
            pulse_color.setAlpha(int(100 * self.audio_level))
            painter.setBrush(pulse_color)
            painter.drawEllipse(24 - pulse_radius, 24 - pulse_radius, pulse_radius * 2, pulse_radius * 2)

        # 4. Status Text Label
        painter.setPen(QColor(240, 240, 245))
        font = QFont("Segoe UI", 10, QFont.Weight.Medium)
        painter.setFont(font)
        text_rect = QRect(40, 0, OVERLAY_WIDTH - 50, OVERLAY_HEIGHT)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.status_text)
