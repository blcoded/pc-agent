"""Risk Classification Engine for PC Voice Agent Control Core.

Classifies every ActionRequest into Low, Medium, or High risk based on its
potential real-world impact, data irreversibility, and dynamic parameter context.
Provides confirmation necessity checks and user-facing prompt formatting.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from voice_agent.control.models import (
    ActionRequest,
    ActionType,
    RiskLevel,
)

logger = logging.getLogger(__name__)

# Relative ordering for comparing risk severity
_RISK_SEVERITY: dict[RiskLevel, int] = {
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
}

# Hotkeys considered potentially disruptive or closing active work
_MEDIUM_RISK_HOTKEYS = {
    ("alt", "f4"),
    ("ctrl", "w"),
    ("ctrl", "shift", "w"),
    ("ctrl", "q"),
    ("win", "l"),
}


class RiskClassifier:
    """Classifies ActionRequests into risk levels and checks confirmation rules."""

    def __init__(self) -> None:
        """Initialize RiskClassifier."""

    def classify(self, action: ActionRequest) -> RiskLevel:
        """Evaluate the risk level of an ActionRequest based on type and parameters.

        Args:
            action: The ActionRequest to evaluate.

        Returns:
            RiskLevel enum (LOW, MEDIUM, or HIGH).
        """
        calculated_level = self._evaluate_action_risk(action)

        # Do not downgrade if action was already marked with higher risk
        if _RISK_SEVERITY.get(action.risk_level, 1) > _RISK_SEVERITY.get(calculated_level, 1):
            calculated_level = action.risk_level

        action.risk_level = calculated_level
        return calculated_level

    def _evaluate_action_risk(self, action: ActionRequest) -> RiskLevel:
        """Internal risk evaluation rules."""
        t = action.action_type
        p = action.params

        # 1. High Risk Operations (Irreversible data loss / critical OS state)
        if t == ActionType.DELETE_FILE:
            return RiskLevel.HIGH

        # 2. Medium Risk Operations (Potential loss of unsaved state, moving/renaming)
        if t in (ActionType.CLOSE_APP, ActionType.MOVE_FILE, ActionType.RENAME_FILE):
            return RiskLevel.MEDIUM

        # 3. Check Hotkeys for disruptive shortcuts
        if t == ActionType.HOTKEY:
            keys = p.get("keys")
            if keys and isinstance(keys, list):
                keys_tuple = tuple(k.lower().strip() for k in keys)
                for disruptive in _MEDIUM_RISK_HOTKEYS:
                    if set(disruptive).issubset(set(keys_tuple)):
                        return RiskLevel.MEDIUM

            hotkey_str = str(p.get("hotkey", "")).lower()
            if any(term in hotkey_str for term in ("alt+f4", "alt f4", "ctrl+w", "ctrl w", "win+l", "win l")):
                return RiskLevel.MEDIUM

        # 4. Low Risk Operations (Navigation, typing, inspection, clicks)
        return RiskLevel.LOW

    def requires_confirmation(
        self,
        action: ActionRequest,
        confirm_medium: bool = False,
        confirm_high: bool = True,
    ) -> bool:
        """Check whether the given action requires user confirmation before execution.

        Args:
            action: The ActionRequest to check.
            confirm_medium: Whether medium risk actions require confirmation (from config).
            confirm_high: Whether high risk actions require confirmation (from config).

        Returns:
            bool: True if confirmation must be obtained from user, False if immediate execution.
        """
        if action.confirmed:
            return False

        # Ensure risk level is up to date
        risk = self.classify(action)

        if risk == RiskLevel.HIGH:
            return confirm_high
        elif risk == RiskLevel.MEDIUM:
            return confirm_medium
        else:
            return False

    def get_confirmation_prompt(self, action: ActionRequest) -> str:
        """Generate a concise, human-readable confirmation prompt for modal display.

        Args:
            action: The ActionRequest requiring confirmation.

        Returns:
            String prompt describing the exact operation.
        """
        t = action.action_type
        p = action.params

        if t == ActionType.DELETE_FILE:
            raw_path = p.get("path", "")
            filename = Path(raw_path).name if raw_path else "file"
            return f"Delete '{filename}'?"

        if t == ActionType.CLOSE_APP:
            target = p.get("target", "current window")
            return f"Close application '{target}'?"

        if t == ActionType.RENAME_FILE:
            src = Path(p.get("source", "")).name
            dst = Path(p.get("destination", "")).name
            return f"Rename '{src}' to '{dst}'?"

        if t == ActionType.MOVE_FILE:
            src = Path(p.get("source", "")).name
            dst = Path(p.get("destination", "")).name
            return f"Move '{src}' to '{dst}'?"

        if t == ActionType.HOTKEY:
            hotkey = p.get("hotkey", "") or " ".join(p.get("keys", []))
            return f"Execute hotkey shortcut '{hotkey}'?"

        return f"Confirm executing '{t.value}'?"


# Convenience singleton
risk_classifier = RiskClassifier()

__all__ = ["RiskClassifier", "risk_classifier"]
