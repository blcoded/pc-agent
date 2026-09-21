"""Mouse Movement and Click Actions for PC Voice Agent.

Provides cursor positioning, boundary checking against desktop geometry,
and simulated mouse clicks (left, right, middle, double-click) using
Win32 SendInput / mouse_event with simulated test fallback.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from voice_agent.control.actions.base import (
    Action,
    ActionResult,
    ActionType,
    ActionValidationError,
)
from voice_agent.control.action_validator import ActionValidator

logger = logging.getLogger(__name__)

# Win32 Mouse Event Flags
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

# System Metrics
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
SM_CXSCREEN = 0
SM_CYSCREEN = 1


@dataclass
class MouseClickEvent:
    """Recorded mouse click event for diagnostics and testing."""

    button: str
    count: int
    x: int
    y: int


class IMouseBackend:
    """Interface for mouse positioning and click simulation."""

    def get_position(self) -> tuple[int, int]:
        raise NotImplementedError

    def set_position(self, x: int, y: int) -> None:
        raise NotImplementedError

    def click(self, button: str = "left", count: int = 1) -> None:
        raise NotImplementedError

    def get_screen_bounds(self) -> tuple[int, int]:
        raise NotImplementedError


class NativeWin32MouseBackend(IMouseBackend):
    """Native Windows implementation using ctypes.windll.user32."""

    def __init__(self) -> None:
        if os.name == "nt" and hasattr(ctypes, "windll"):
            self._user32 = ctypes.windll.user32
        else:
            self._user32 = None

    def get_screen_bounds(self) -> tuple[int, int]:
        if not self._user32:
            return 1920, 1080
        w = self._user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        h = self._user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        if w <= 0 or h <= 0:
            w = self._user32.GetSystemMetrics(SM_CXSCREEN)
            h = self._user32.GetSystemMetrics(SM_CYSCREEN)
        return (w if w > 0 else 1920, h if h > 0 else 1080)

    def get_position(self) -> tuple[int, int]:
        if not self._user32:
            return 0, 0
        pt = wintypes.POINT()
        self._user32.GetCursorPos(ctypes.byref(pt))
        return int(pt.x), int(pt.y)

    def set_position(self, x: int, y: int) -> None:
        if not self._user32:
            return
        self._user32.SetCursorPos(x, y)

    def click(self, button: str = "left", count: int = 1) -> None:
        if not self._user32:
            return

        btn = button.lower().strip()
        if btn == "left":
            down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP
        elif btn == "right":
            down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
        elif btn == "middle":
            down_flag, up_flag = MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP
        else:
            raise ValueError(f"Invalid mouse button: {button}")

        for i in range(count):
            self._user32.mouse_event(down_flag, 0, 0, 0, 0)
            time.sleep(0.01)
            self._user32.mouse_event(up_flag, 0, 0, 0, 0)
            if i < count - 1:
                time.sleep(0.05)


class SimulatedMouseBackend(IMouseBackend):
    """In-memory mock mouse backend for deterministic unit tests."""

    def __init__(self, screen_bounds: tuple[int, int] = (1920, 1080)) -> None:
        self.bounds = screen_bounds
        self.x: int = screen_bounds[0] // 2
        self.y: int = screen_bounds[1] // 2
        self.click_history: list[MouseClickEvent] = []
        self.move_history: list[tuple[int, int]] = []

    def get_screen_bounds(self) -> tuple[int, int]:
        return self.bounds

    def get_position(self) -> tuple[int, int]:
        return self.x, self.y

    def set_position(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        self.move_history.append((x, y))

    def click(self, button: str = "left", count: int = 1) -> None:
        self.click_history.append(
            MouseClickEvent(button=button.lower(), count=count, x=self.x, y=self.y)
        )


# Default backend instance
_default_mouse_backend: IMouseBackend = (
    NativeWin32MouseBackend() if os.name == "nt" and hasattr(ctypes, "windll") else SimulatedMouseBackend()
)


class ClickAction(Action):
    """Action that performs mouse clicks at the current cursor position."""

    def __init__(
        self,
        backend: IMouseBackend | None = None,
        validator: ActionValidator | None = None,
    ) -> None:
        self.backend = backend or _default_mouse_backend
        self.validator = validator or ActionValidator()

    @property
    def action_type(self) -> ActionType:
        return ActionType.CLICK

    def validate(self, params: dict[str, Any]) -> bool:
        button = params.get("button", "left")
        self.validator.validate_mouse_button(button)
        click_count = params.get("click_count", 1)
        if not isinstance(click_count, int) or click_count < 1 or click_count > 10:
            raise ActionValidationError(f"Invalid click_count: {click_count}")
        return True

    def execute(self, params: dict[str, Any]) -> ActionResult:
        button = str(params.get("button", "left")).lower()
        click_count = int(params.get("click_count", 1))

        try:
            self.backend.click(button=button, count=click_count)
            x, y = self.backend.get_position()
            logger.info("Executed %s-click (count=%d) at (%d, %d)", button, click_count, x, y)
            return ActionResult(
                success=True,
                output={"button": button, "click_count": click_count, "position": (x, y)},
            )
        except Exception as exc:
            logger.error("Failed to execute mouse click: %s", exc)
            return ActionResult(success=False, output=None, error_message=str(exc))


class MoveMouseAction(Action):
    """Action that moves the mouse cursor to absolute or relative coordinates."""

    def __init__(
        self,
        backend: IMouseBackend | None = None,
        validator: ActionValidator | None = None,
    ) -> None:
        self.backend = backend or _default_mouse_backend
        self.validator = validator or ActionValidator()

    @property
    def action_type(self) -> ActionType:
        return ActionType.MOVE_MOUSE

    def validate(self, params: dict[str, Any]) -> bool:
        mode = params.get("mode", "relative")
        if mode == "absolute":
            if "x" not in params or "y" not in params:
                raise ActionValidationError("Absolute MOVE_MOUSE requires 'x' and 'y' coordinates.")
            self.validator.validate_mouse_coords(params["x"], params["y"])
        elif mode == "relative":
            direction = str(params.get("direction", "up")).lower()
            if direction not in self.validator.ALLOWED_MOUSE_DIRECTIONS:
                raise ActionValidationError(f"Invalid mouse move direction: {direction}")
        else:
            raise ActionValidationError(f"Invalid mouse move mode: {mode}")
        return True

    def execute(self, params: dict[str, Any]) -> ActionResult:
        mode = params.get("mode", "relative")
        max_w, max_h = self.backend.get_screen_bounds()
        curr_x, curr_y = self.backend.get_position()

        if mode == "absolute":
            target_x = int(params["x"])
            target_y = int(params["y"])
        else:
            # Relative mode
            direction = str(params.get("direction", "up")).lower()
            dist = int(params.get("distance", 50))
            if direction == "up":
                target_x, target_y = curr_x, curr_y - dist
            elif direction == "down":
                target_x, target_y = curr_x, curr_y + dist
            elif direction == "left":
                target_x, target_y = curr_x - dist, curr_y
            elif direction == "right":
                target_x, target_y = curr_x + dist, curr_y
            else:
                return ActionResult(success=False, error_message=f"Unknown direction '{direction}'")

        # Clamp within desktop geometry bounds
        clamped_x = max(0, min(target_x, max_w - 1))
        clamped_y = max(0, min(target_y, max_h - 1))

        try:
            self.backend.set_position(clamped_x, clamped_y)
            logger.info("Moved mouse to (%d, %d)", clamped_x, clamped_y)
            return ActionResult(
                success=True,
                output={
                    "mode": mode,
                    "target": (target_x, target_y),
                    "final_position": (clamped_x, clamped_y),
                },
            )
        except Exception as exc:
            logger.error("Failed to move mouse: %s", exc)
            return ActionResult(success=False, output=None, error_message=str(exc))


__all__ = [
    "ClickAction",
    "IMouseBackend",
    "MouseClickEvent",
    "MoveMouseAction",
    "NativeWin32MouseBackend",
    "SimulatedMouseBackend",
]
