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
from voice_agent.ui.tray import (
    SystemTrayManager,
    create_default_tray_icon,
)

__all__ = [
    "FloatingStatusOverlay",
    "VisualStateStyle",
    "OVERLAY_WIDTH",
    "OVERLAY_HEIGHT",
    "STATE_STYLES",
    "SystemTrayManager",
    "create_default_tray_icon",
    "RiskConfirmationDialog",
    "request_user_confirmation",
]
