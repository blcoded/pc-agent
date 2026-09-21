"""Structured Action Request and Result Models for PC Voice Agent Control Core.

This module defines the enums, data models, and serialization methods for
all control operations performed by the voice agent.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class ActionType(str, enum.Enum):
    """Enumeration of all supported action types in the control subsystem."""

    # Application control
    OPEN_APP = "open_app"
    CLOSE_APP = "close_app"
    SWITCH_WINDOW = "switch_window"

    # Keyboard & typing
    TYPE_TEXT = "type_text"
    PRESS_KEY = "press_key"
    HOTKEY = "hotkey"

    # Mouse control
    MOVE_MOUSE = "move_mouse"
    CLICK = "click"

    # Web & search
    OPEN_URL = "open_url"
    SEARCH_WEB = "search_web"

    # Clipboard
    READ_CLIPBOARD = "read_clipboard"
    COPY = "copy"
    PASTE = "paste"

    # File & filesystem operations
    OPEN_FILE = "open_file"
    RENAME_FILE = "rename_file"
    MOVE_FILE = "move_file"
    DELETE_FILE = "delete_file"
    OPEN_FOLDER = "open_folder"

    def __str__(self) -> str:
        return self.value


class RiskLevel(str, enum.Enum):
    """Classification of risk for actions to determine confirmation requirements."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    def __str__(self) -> str:
        return self.value


class ActionError(Exception):
    """Base exception for action-related errors."""


class ActionValidationError(ActionError):
    """Raised when an action's parameters fail validation."""


class ActionExecutionError(ActionError):
    """Raised when an action fails during execution."""


@dataclass
class ActionRequest:
    """Represents a structured request to execute a PC control action."""

    action_type: ActionType
    params: dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.LOW
    raw_command: str = ""
    confirmed: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert ActionRequest to a serializable dictionary."""
        return {
            "action_type": self.action_type.value,
            "params": dict(self.params),
            "risk_level": self.risk_level.value,
            "raw_command": self.raw_command,
            "confirmed": self.confirmed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionRequest:
        """Construct an ActionRequest from a dictionary."""
        action_type_raw = data.get("action_type")
        if isinstance(action_type_raw, ActionType):
            action_type = action_type_raw
        elif isinstance(action_type_raw, str):
            try:
                action_type = ActionType(action_type_raw.lower())
            except ValueError:
                try:
                    action_type = ActionType[action_type_raw.upper()]
                except KeyError:
                    raise ActionValidationError(f"Invalid or unsupported action_type: {action_type_raw}")
        else:
            raise ActionValidationError(f"Invalid or missing action_type: {action_type_raw}")

        risk_level_raw = data.get("risk_level", RiskLevel.LOW)
        if isinstance(risk_level_raw, RiskLevel):
            risk_level = risk_level_raw
        elif isinstance(risk_level_raw, str):
            try:
                risk_level = RiskLevel(risk_level_raw.lower())
            except ValueError:
                risk_level = RiskLevel.LOW
        else:
            risk_level = RiskLevel.LOW

        return cls(
            action_type=action_type,
            params=dict(data.get("params") or {}),
            risk_level=risk_level,
            raw_command=str(data.get("raw_command", "")),
            confirmed=bool(data.get("confirmed", False)),
        )


@dataclass
class ActionResult:
    """Represents the outcome of an executed action."""

    success: bool
    output: Any = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert ActionResult to a serializable dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionResult:
        """Construct an ActionResult from a dictionary."""
        return cls(
            success=bool(data.get("success", False)),
            output=data.get("output"),
            error_message=data.get("error_message"),
        )
