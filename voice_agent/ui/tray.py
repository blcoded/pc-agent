"""Windows system tray icon, context menu, and balloon notification manager."""

from __future__ import annotations

import logging
from typing import Any, Callable

from voice_agent.app.config import AppConfig, load_config
from voice_agent.app.lifecycle import ApplicationLifecycle
from voice_agent.app.logging import get_logger

logger = get_logger("ui.tray")

try:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
    from PySide6.QtWidgets import QMenu, QSystemTrayIcon
    HAS_PYSIDE = True
except ImportError:
    HAS_PYSIDE = False


if HAS_PYSIDE:
    _BaseTray = QSystemTrayIcon
else:
    class _BaseTray:  # type: ignore[no-redef]
        def __init__(self, icon: Any = None, parent: Any = None) -> None:
            self._tooltip = ""
            self._visible = False
            self._menu: Any = None

        def setIcon(self, icon: Any) -> None:
            pass

        def setToolTip(self, tip: str) -> None:
            self._tooltip = tip

        def toolTip(self) -> str:
            return self._tooltip

        def setContextMenu(self, menu: Any) -> None:
            self._menu = menu

        def contextMenu(self) -> Any:
            return self._menu

        def show(self) -> None:
            self._visible = True

        def hide(self) -> None:
            self._visible = False

        def isVisible(self) -> bool:
            return self._visible

        def showMessage(self, title: str, msg: str, icon: Any = None, msecs: int = 10000) -> None:
            pass


def create_default_tray_icon() -> Any:
    """Generate a clean programmatic 32x32 tray icon."""
    if not HAS_PYSIDE:
        return None

    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Blue-accent circle
    painter.setBrush(QColor(33, 150, 243))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, 28, 28)

    # White microphone symbol in center
    painter.setBrush(QColor(255, 255, 255))
    painter.drawRoundedRect(12, 7, 8, 12, 4, 4)

    painter.setPen(QColor(255, 255, 255))
    painter.drawArc(8, 12, 16, 10, 0, -180 * 16)
    painter.drawLine(16, 22, 16, 26)
    painter.drawLine(12, 26, 20, 26)
    painter.end()

    return QIcon(pixmap)


class SystemTrayManager(_BaseTray):
    """Manages system tray integration, context menus, and notification popups."""

    def __init__(
        self,
        lifecycle: ApplicationLifecycle | None = None,
        config: AppConfig | None = None,
        on_toggle_overlay: Callable[[], None] | None = None,
        on_open_history: Callable[[], None] | None = None,
        on_open_settings: Callable[[], None] | None = None,
        on_about: Callable[[], None] | None = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self.lifecycle = lifecycle
        self.config = config or load_config()

        self.on_toggle_overlay = on_toggle_overlay
        self.on_open_history = on_open_history
        self.on_open_settings = on_open_settings
        self.on_about = on_about

        self.is_paused: bool = False
        self.last_notification: tuple[str, str] | None = None

        self._menu_actions: dict[str, Any] = {}
        self._init_tray()

    def _init_tray(self) -> None:
        self.setIcon(create_default_tray_icon())
        self.setToolTip("PC Voice Agent - Ready")
        self._build_context_menu()

        if HAS_PYSIDE:
            self.activated.connect(self._on_activated)

    def _build_context_menu(self) -> None:
        """Construct the tray right-click context menu."""
        if not HAS_PYSIDE:
            # Provide mock dictionary representation for test inspection
            self._menu_actions = {
                "status": "Status: Ready (Dictation)",
                "pause": False,
                "overlay": True,
                "history": self.on_open_history,
                "settings": self.on_open_settings,
                "about": self.on_about,
                "exit": self._handle_exit,
            }
            return

        menu = QMenu()

        # 1. Status Indicator (non-clickable header)
        status_action = menu.addAction("Status: Ready (Dictation)")
        status_action.setEnabled(False)
        self._menu_actions["status"] = status_action

        menu.addSeparator()

        # 2. Pause Toggle
        pause_action = menu.addAction("Pause Voice Agent")
        pause_action.setCheckable(True)
        pause_action.setChecked(self.is_paused)
        pause_action.triggered.connect(self._handle_pause_toggle)
        self._menu_actions["pause"] = pause_action

        # 3. Toggle Overlay Visibility
        overlay_action = menu.addAction("Show/Hide Overlay")
        if self.on_toggle_overlay:
            overlay_action.triggered.connect(self.on_toggle_overlay)
        self._menu_actions["overlay"] = overlay_action

        menu.addSeparator()

        # 4. History Window
        history_action = menu.addAction("History...")
        if self.on_open_history:
            history_action.triggered.connect(self.on_open_history)
        self._menu_actions["history"] = history_action

        # 5. Settings Dialog
        settings_action = menu.addAction("Settings...")
        if self.on_open_settings:
            settings_action.triggered.connect(self.on_open_settings)
        self._menu_actions["settings"] = settings_action

        # 6. About Dialog
        about_action = menu.addAction("About PC Voice Agent")
        if self.on_about:
            about_action.triggered.connect(self.on_about)
        self._menu_actions["about"] = about_action

        menu.addSeparator()

        # 7. Exit Application
        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(self._handle_exit)
        self._menu_actions["exit"] = exit_action

        self.setContextMenu(menu)

    def _on_activated(self, reason: Any) -> None:
        """Handle left-click or double-click on system tray icon."""
        if not HAS_PYSIDE:
            return

        # Trigger = Left click, DoubleClick = Double click
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            if self.on_toggle_overlay:
                self.on_toggle_overlay()

    def update_status(self, mode: str, state_name: str) -> None:
        """Update status menu item and tray tooltip."""
        status_text = f"Status: {state_name.capitalize()} ({mode.capitalize()})"
        tooltip = f"PC Voice Agent - {state_name.capitalize()} ({mode.capitalize()})"
        self.setToolTip(tooltip)

        if HAS_PYSIDE:
            action = self._menu_actions.get("status")
            if action and hasattr(action, "setText"):
                action.setText(status_text)
        else:
            self._menu_actions["status"] = status_text

    def _handle_pause_toggle(self, checked: bool) -> None:
        """Pause or unpause agent operation."""
        self.is_paused = checked
        if self.is_paused:
            self.setToolTip("PC Voice Agent - Paused")
            self.show_notification("PC Voice Agent", "Voice Agent is now paused.")
        else:
            self.setToolTip("PC Voice Agent - Ready")

    def _handle_exit(self) -> None:
        """Trigger graceful shutdown and exit."""
        logger.info("Exit selected from system tray context menu.")
        if self.lifecycle:
            self.lifecycle.shutdown()
        if HAS_PYSIDE:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.quit()

    def show_notification(self, title: str, message: str, icon_type: str = "info") -> None:
        """Display an OS balloon/toast notification."""
        self.last_notification = (title, message)
        logger.info("System Tray Notification: [%s] %s", title, message)

        if HAS_PYSIDE:
            icon = QSystemTrayIcon.MessageIcon.Information
            if icon_type == "warning":
                icon = QSystemTrayIcon.MessageIcon.Warning
            elif icon_type == "error":
                icon = QSystemTrayIcon.MessageIcon.Critical

            self.showMessage(title, message, icon, 5000)
