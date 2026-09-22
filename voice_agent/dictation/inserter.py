"""Hybrid text inserter and fallback notifier for Dictation Mode."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from enum import Enum
import sys
import time
from typing import Any, Callable

from voice_agent.app.logging import get_logger
from voice_agent.clipboard.manager import ClipboardManager

logger = get_logger("dictation.inserter")

# Windows Virtual Key Codes
VK_CONTROL = 0x11
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1

# Window class names that cannot receive user text input
NON_INPUT_CLASS_NAMES = {
    "progman",
    "workerw",
    "shell_traywnd",
    "shell_secondarytraywnd",
    "lockscreenwindow",
}


class InsertionStatus(str, Enum):
    """Result status of an insertion attempt."""

    SUCCESS = "success"
    NO_TARGET = "no_target"
    FALLBACK_COPIED = "fallback_copied"
    ERROR = "error"


@dataclass
class InsertionResult:
    """Outcome and diagnostics of a text insertion operation."""

    success: bool
    status: InsertionStatus
    message: str = ""
    target_hwnd: int = 0
    target_title: str = ""


# CTypes structures for SendInput (correct 40-byte layout on 64-bit Windows)
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("u", INPUT_UNION),
    ]


def default_get_foreground_window() -> tuple[int, str, str]:
    """Query current foreground window handle, title, and class name on Windows."""
    if sys.platform != "win32":
        return 1, "Simulated Window", "Edit"

    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return 0, "", ""

        title_buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title_buf, 512)
        title = title_buf.value

        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 256)
        class_name = class_buf.value

        return hwnd, title, class_name
    except Exception as e:
        logger.debug("Failed to query foreground window: %s", e)
        return 0, "", ""


def default_send_paste() -> bool:
    """Synthesize Ctrl+V using native Windows keybd_event, SendInput, or pynput."""
    if sys.platform != "win32":
        return True

    # Primary method: Windows keybd_event (direct, reliable across all Windows architectures)
    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_V, 0, 0, 0)
        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        return True
    except Exception as e:
        logger.debug("keybd_event Ctrl+V failed (%s), trying SendInput...", e)

    # Secondary method: SendInput with 40-byte aligned struct
    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        inputs = (INPUT * 4)()
        for i in range(4):
            inputs[i].type = INPUT_KEYBOARD

        inputs[0].u.ki.wVk = VK_CONTROL
        inputs[0].u.ki.dwFlags = 0
        inputs[1].u.ki.wVk = VK_V
        inputs[1].u.ki.dwFlags = 0
        inputs[2].u.ki.wVk = VK_V
        inputs[2].u.ki.dwFlags = KEYEVENTF_KEYUP
        inputs[3].u.ki.wVk = VK_CONTROL
        inputs[3].u.ki.dwFlags = KEYEVENTF_KEYUP

        sent = user32.SendInput(4, ctypes.byref(inputs), ctypes.sizeof(INPUT))
        if sent == 4:
            return True
    except Exception as e:
        logger.debug("SendInput Ctrl+V failed (%s), trying pynput...", e)

    # Tertiary method: pynput keyboard controller
    try:
        from pynput.keyboard import Controller, Key

        kb = Controller()
        with kb.pressed(Key.ctrl):
            kb.tap("v")
        return True
    except Exception as e:
        logger.error("All paste synthesis methods failed: %s", e)
        return False


class TextInserter:
    """Coordinates hybrid clipboard paste, target validation, and fallback notification."""

    def __init__(
        self,
        clipboard_manager: ClipboardManager | None = None,
        get_window_func: Callable[[], tuple[int, str, str]] | None = None,
        paste_func: Callable[[], bool] | None = None,
        on_no_target: Callable[[str, str], None] | None = None,
    ) -> None:
        self.clipboard = clipboard_manager or ClipboardManager()
        self._get_window = get_window_func or default_get_foreground_window
        self._send_paste = paste_func or default_send_paste
        self.on_no_target = on_no_target

    def is_valid_target(self, hwnd: int, title: str, class_name: str) -> bool:
        """Evaluate whether a window is capable of receiving text input."""
        if hwnd == 0:
            return False

        lower_class = class_name.lower().strip()
        if lower_class in NON_INPUT_CLASS_NAMES:
            return False

        # Lock screen or desktop
        if "lockapp" in lower_class or "shell_tray" in lower_class:
            return False

        return True

    def insert(self, text: str) -> InsertionResult:
        """Inject text into active application via clipboard paste or fallback."""
        if not text:
            return InsertionResult(
                success=True,
                status=InsertionStatus.SUCCESS,
                message="Empty text; nothing to insert.",
            )

        hwnd, title, class_name = self._get_window()

        # 1. Target Validation
        if not self.is_valid_target(hwnd, title, class_name):
            logger.warning(
                "No valid input target window detected (hwnd=%d, title='%s', class='%s').",
                hwnd,
                title,
                class_name,
            )
            # Copy to clipboard as safe fallback so user doesn't lose dictation
            self.clipboard.set_text(text)
            msg = "No text field detected — copied to clipboard."
            if self.on_no_target:
                try:
                    self.on_no_target(text, msg)
                except Exception as e:
                    logger.error("Error in on_no_target callback: %s", e)

            return InsertionResult(
                success=False,
                status=InsertionStatus.NO_TARGET,
                message=msg,
                target_hwnd=hwnd,
                target_title=title,
            )

        # 2. Preferred Clipboard Paste Sequence
        logger.debug("Beginning clipboard paste into '%s' (hwnd=%d)...", title, hwnd)

        # Snapshot current clipboard
        snapshot = self.clipboard.create_snapshot()

        # Put dictated text on clipboard
        if not self.clipboard.set_text(text):
            logger.error("Failed to set clipboard for paste.")
            msg = "Failed to copy dictated text to clipboard."
            return InsertionResult(
                success=False,
                status=InsertionStatus.ERROR,
                message=msg,
                target_hwnd=hwnd,
                target_title=title,
            )

        # Short pause to ensure clipboard update is registered by Windows
        time.sleep(0.025)

        # Synthesize Ctrl+V paste
        pasted = self._send_paste()

        # Wait for target app to consume clipboard contents before restoring
        time.sleep(0.080)

        # Restore previous clipboard
        self.clipboard.restore_snapshot(snapshot)

        if pasted:
            logger.info("Dictated text successfully injected into '%s'.", title)
            return InsertionResult(
                success=True,
                status=InsertionStatus.SUCCESS,
                message="Text inserted successfully.",
                target_hwnd=hwnd,
                target_title=title,
            )

        # 3. Paste failed: Fallback to safety copy
        logger.warning("SendInput paste failed; copying text to clipboard.")
        self.clipboard.set_text(text)
        msg = "Paste command failed — copied to clipboard."
        if self.on_no_target:
            try:
                self.on_no_target(text, msg)
            except Exception as e:
                logger.error("Error in on_no_target callback: %s", e)

        return InsertionResult(
            success=False,
            status=InsertionStatus.FALLBACK_COPIED,
            message=msg,
            target_hwnd=hwnd,
            target_title=title,
        )
