"""Keyboard and Typing Actions for PC Voice Agent.

Provides key press, shortcut chord, and text typing simulation using
Win32 SendInput / pynput with fallback to a simulated test backend.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import os
import time
from typing import Any, Sequence

from voice_agent.control.actions.base import (
    Action,
    ActionResult,
    ActionType,
    ActionValidationError,
)
from voice_agent.control.action_validator import ActionValidator

logger = logging.getLogger(__name__)

# Win32 Virtual Key mappings
VK_MAP: dict[str, int] = {
    "backspace": 0x08,
    "back": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "pause": 0x13,
    "capslock": 0x14,
    "caps_lock": 0x14,
    "escape": 0x1B,
    "esc": 0x1B,
    "space": 0x20,
    "spacebar": 0x20,
    "pageup": 0x21,
    "page_up": 0x21,
    "pagedown": 0x22,
    "page_down": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "printscreen": 0x2C,
    "insert": 0x2D,
    "delete": 0x2E,
    "del": 0x2E,
    "win": 0x5B,
    "windows": 0x5B,
    "cmd": 0x5B,
    "super": 0x5B,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
}

# Populate alphanumeric keys (0-9, a-z)
for c in range(ord("0"), ord("9") + 1):
    VK_MAP[chr(c)] = c
for c in range(ord("a"), ord("z") + 1):
    VK_MAP[chr(c)] = ord(chr(c).upper())


class IKeyboardBackend:
    """Interface for keyboard typing and key events."""

    def type_text(self, text: str) -> None:
        raise NotImplementedError

    def press_key(self, key_name: str) -> None:
        raise NotImplementedError

    def hotkey(self, keys: Sequence[str]) -> None:
        raise NotImplementedError


# Win32 SendInput Structures
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUT_UNION),
    ]


class NativeWin32KeyboardBackend(IKeyboardBackend):
    """Native Windows implementation using SendInput API."""

    def __init__(self) -> None:
        if os.name == "nt" and hasattr(ctypes, "windll"):
            self._user32 = ctypes.windll.user32
        else:
            self._user32 = None

    def _send_vk(self, vk: int, keyup: bool = False) -> None:
        if not self._user32:
            return
        flags = KEYEVENTF_KEYUP if keyup else 0
        try:
            self._user32.keybd_event(vk, 0, flags, 0)
            return
        except Exception:
            pass

        inp = INPUT(
            type=INPUT_KEYBOARD,
            ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0),
        )
        self._user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def _send_unicode_char(self, char: str) -> None:
        if not self._user32:
            return
        code = ord(char)
        # Key down
        inp_down = INPUT(
            type=INPUT_KEYBOARD,
            ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=0),
        )
        # Key up
        inp_up = INPUT(
            type=INPUT_KEYBOARD,
            ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=0),
        )
        inputs = (INPUT * 2)(inp_down, inp_up)
        self._user32.SendInput(2, inputs, ctypes.sizeof(INPUT))

    def type_text(self, text: str) -> None:
        for char in text:
            self._send_unicode_char(char)
            time.sleep(0.005)

    def press_key(self, key_name: str) -> None:
        vk = VK_MAP.get(key_name.lower())
        if vk is None:
            if len(key_name) == 1:
                self._send_unicode_char(key_name)
                return
            raise ValueError(f"Unknown virtual key '{key_name}'")
        self._send_vk(vk, keyup=False)
        time.sleep(0.01)
        self._send_vk(vk, keyup=True)

    def hotkey(self, keys: Sequence[str]) -> None:
        vks: list[int] = []
        for k in keys:
            vk = VK_MAP.get(k.lower())
            if vk is None:
                raise ValueError(f"Unknown key in hotkey chord: '{k}'")
            vks.append(vk)

        # Press down in order
        for vk in vks:
            self._send_vk(vk, keyup=False)
            time.sleep(0.005)

        time.sleep(0.02)

        # Release in reverse order
        for vk in reversed(vks):
            self._send_vk(vk, keyup=True)
            time.sleep(0.005)


class SimulatedKeyboardBackend(IKeyboardBackend):
    """In-memory simulated keyboard for deterministic unit tests."""

    def __init__(self) -> None:
        self.typed_history: list[str] = []
        self.pressed_keys_history: list[str] = []
        self.hotkeys_history: list[list[str]] = []

    def type_text(self, text: str) -> None:
        self.typed_history.append(text)

    def press_key(self, key_name: str) -> None:
        clean_key = key_name.lower().strip()
        if clean_key not in VK_MAP and len(clean_key) > 1:
            raise ValueError(f"Unknown key '{key_name}'")
        self.pressed_keys_history.append(clean_key)

    def hotkey(self, keys: Sequence[str]) -> None:
        chord: list[str] = []
        for k in keys:
            clean_k = k.lower().strip()
            if clean_k not in VK_MAP and len(clean_k) > 1:
                raise ValueError(f"Unknown key in chord: '{k}'")
            chord.append(clean_k)
        self.hotkeys_history.append(chord)


# Default keyboard backend
_default_keyboard_backend: IKeyboardBackend = (
    NativeWin32KeyboardBackend() if os.name == "nt" and hasattr(ctypes, "windll") else SimulatedKeyboardBackend()
)


class TypeTextAction(Action):
    """Action that types explicit text strings into the active application."""

    def __init__(
        self,
        backend: IKeyboardBackend | None = None,
        validator: ActionValidator | None = None,
    ) -> None:
        self.backend = backend or _default_keyboard_backend
        self.validator = validator or ActionValidator()

    @property
    def action_type(self) -> ActionType:
        return ActionType.TYPE_TEXT

    def validate(self, params: dict[str, Any]) -> bool:
        if "text" not in params:
            raise ActionValidationError("Missing 'text' parameter for TYPE_TEXT.")
        self.validator.validate_text(params["text"])
        return True

    def execute(self, params: dict[str, Any]) -> ActionResult:
        text = str(params["text"])
        try:
            self.backend.type_text(text)
            logger.info("Typed %d characters of text", len(text))
            return ActionResult(success=True, output={"character_count": len(text)})
        except Exception as exc:
            logger.error("Failed to type text: %s", exc)
            return ActionResult(success=False, output=None, error_message=str(exc))


class PressKeyAction(Action):
    """Action that presses and releases a single special or alphanumeric key."""

    def __init__(
        self,
        backend: IKeyboardBackend | None = None,
        validator: ActionValidator | None = None,
    ) -> None:
        self.backend = backend or _default_keyboard_backend
        self.validator = validator or ActionValidator()

    @property
    def action_type(self) -> ActionType:
        return ActionType.PRESS_KEY

    def validate(self, params: dict[str, Any]) -> bool:
        if "key" not in params:
            raise ActionValidationError("Missing 'key' parameter for PRESS_KEY.")
        key_str = str(params["key"]).strip()
        if not key_str:
            raise ActionValidationError("'key' cannot be empty.")
        return True

    def execute(self, params: dict[str, Any]) -> ActionResult:
        key_name = str(params["key"]).strip()
        try:
            self.backend.press_key(key_name)
            logger.info("Pressed key '%s'", key_name)
            return ActionResult(success=True, output={"key": key_name})
        except Exception as exc:
            logger.error("Failed to press key '%s': %s", key_name, exc)
            return ActionResult(success=False, output=None, error_message=str(exc))


class HotkeyAction(Action):
    """Action that executes composite keyboard shortcuts (e.g. Ctrl+C, Alt+Tab)."""

    def __init__(
        self,
        backend: IKeyboardBackend | None = None,
        validator: ActionValidator | None = None,
    ) -> None:
        self.backend = backend or _default_keyboard_backend
        self.validator = validator or ActionValidator()

    @property
    def action_type(self) -> ActionType:
        return ActionType.HOTKEY

    def validate(self, params: dict[str, Any]) -> bool:
        keys = params.get("keys")
        hotkey_str = params.get("hotkey")
        if not keys and not hotkey_str:
            raise ActionValidationError("HOTKEY requires 'keys' list or 'hotkey' string.")
        return True

    def execute(self, params: dict[str, Any]) -> ActionResult:
        keys: list[str]
        if "keys" in params and isinstance(params["keys"], list):
            keys = [str(k).strip() for k in params["keys"] if str(k).strip()]
        elif "hotkey" in params and isinstance(params["hotkey"], str):
            import re
            keys = [k.strip() for k in re.split(r"[\s\+]+", params["hotkey"]) if k.strip()]
        else:
            return ActionResult(success=False, error_message="No valid keys provided for hotkey.")

        if not keys:
            return ActionResult(success=False, error_message="Empty key chord.")

        try:
            self.backend.hotkey(keys)
            chord_repr = "+".join(keys)
            logger.info("Executed hotkey chord '%s'", chord_repr)
            return ActionResult(success=True, output={"chord": chord_repr, "keys": keys})
        except Exception as exc:
            logger.error("Failed to execute hotkey %s: %s", keys, exc)
            return ActionResult(success=False, output=None, error_message=str(exc))


__all__ = [
    "HotkeyAction",
    "IKeyboardBackend",
    "NativeWin32KeyboardBackend",
    "PressKeyAction",
    "SimulatedKeyboardBackend",
    "TypeTextAction",
    "VK_MAP",
]
