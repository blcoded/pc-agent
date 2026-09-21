"""User interface widgets, overlay, tray, and dialogs package."""

from voice_agent.ui.overlay import (
    OVERLAY_HEIGHT,
    OVERLAY_WIDTH,
    STATE_STYLES,
    FloatingStatusOverlay,
    VisualStateStyle,
)
from voice_agent.ui.confirmation import (
    RiskConfirmationDialog,
    request_user_confirmation,
)
from voice_agent.ui.history import HistoryViewerWindow
from voice_agent.ui.settings import SettingsDialog
from voice_agent.ui.tray import (
    SystemTrayManager,
    create_default_tray_icon,
)

__all__ = [
    "FloatingStatusOverlay",
    "HistoryViewerWindow",
    "OVERLAY_HEIGHT",
    "OVERLAY_WIDTH",
    "RiskConfirmationDialog",
    "STATE_STYLES",
    "SettingsDialog",
    "SystemTrayManager",
    "VisualStateStyle",
    "create_default_tray_icon",
    "request_user_confirmation",
]
