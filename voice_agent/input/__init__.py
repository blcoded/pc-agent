"""Keyboard hotkey capture and gesture detection package."""

from voice_agent.input.gesture import GestureDetector, GestureMode
from voice_agent.input.hotkeys import (
    HotkeyManager,
    canonicalize_key,
    normalize_key_name,
)

__all__ = [
    "GestureDetector",
    "GestureMode",
    "HotkeyManager",
    "normalize_key_name",
    "canonicalize_key",
]
