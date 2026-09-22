"""Application Control Actions (Launch, Close, Switch) for PC Voice Agent.

Provides Windows application management using Win32 API window enumeration,
message posting (WM_CLOSE), window focusing (SetForegroundWindow), and subprocess
process launching.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Callable

from voice_agent.control.actions.base import (
    Action,
    ActionResult,
    ActionType,
    ActionValidationError,
)
from voice_agent.control.action_validator import ActionValidator

logger = logging.getLogger(__name__)

try:
    import winreg
except ImportError:
    winreg = None  # type: ignore[assignment]

# Constants
WM_CLOSE = 0x0010
SW_RESTORE = 9

# Common Windows application aliases mapped to binary names or protocols
DEFAULT_APP_ALIASES: dict[str, str] = {
    "notepad": "notepad.exe",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "firefox": "firefox.exe",
    "brave": "brave.exe",
    "brave browser": "brave.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "paint": "mspaint.exe",
    "wordpad": "wordpad.exe",
    "taskmgr": "taskmgr.exe",
    "task manager": "taskmgr.exe",
    "code": "code.cmd",
    "vs code": "code.cmd",
    "vscode": "code.cmd",
    "visual studio code": "code.cmd",
    "spotify": "spotify.exe",
    "discord": "discord.exe",
    "slack": "slack.exe",
    "word": "winword.exe",
    "microsoft word": "winword.exe",
    "excel": "excel.exe",
    "microsoft excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "microsoft powerpoint": "powerpnt.exe",
    "vlc": "vlc.exe",
    "vlc media player": "vlc.exe",
    "settings": "ms-settings:",
    "windows settings": "ms-settings:",
}


@dataclass
class WindowInfo:
    """Information regarding a top-level OS window."""

    hwnd: int
    title: str
    visible: bool = True


class IWindowBackend:
    """Interface for window enumeration and manipulation."""

    def get_foreground_window(self) -> int:
        raise NotImplementedError

    def get_window_title(self, hwnd: int) -> str:
        raise NotImplementedError

    def find_windows(self) -> list[WindowInfo]:
        raise NotImplementedError

    def close_window(self, hwnd: int) -> bool:
        raise NotImplementedError

    def focus_window(self, hwnd: int) -> bool:
        raise NotImplementedError


class NativeWin32WindowBackend(IWindowBackend):
    """Native Windows implementation using ctypes.windll.user32."""

    def __init__(self) -> None:
        if os.name == "nt" and hasattr(ctypes, "windll"):
            self._user32 = ctypes.windll.user32
        else:
            self._user32 = None

    def get_foreground_window(self) -> int:
        if not self._user32:
            return 0
        return int(self._user32.GetForegroundWindow())

    def get_window_title(self, hwnd: int) -> str:
        if not self._user32 or not hwnd:
            return ""
        length = self._user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        self._user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value

    def find_windows(self) -> list[WindowInfo]:
        if not self._user32:
            return []

        windows: list[WindowInfo] = []
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd: int, lparam: int) -> bool:
            if self._user32.IsWindowVisible(hwnd):
                title = self.get_window_title(hwnd)
                if title.strip():
                    windows.append(WindowInfo(hwnd=hwnd, title=title.strip(), visible=True))
            return True

        self._user32.EnumWindows(EnumWindowsProc(callback), 0)
        return windows

    def close_window(self, hwnd: int) -> bool:
        if not self._user32 or not hwnd:
            return False
        res = self._user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        return bool(res)

    def focus_window(self, hwnd: int) -> bool:
        if not self._user32 or not hwnd:
            return False
        # Restore if minimized
        self._user32.ShowWindow(hwnd, SW_RESTORE)
        res = self._user32.SetForegroundWindow(hwnd)
        return bool(res)


class SimulatedWindowBackend(IWindowBackend):
    """In-memory mock window backend for unit tests."""

    def __init__(self, initial_windows: list[WindowInfo] | None = None) -> None:
        self.windows: list[WindowInfo] = list(initial_windows or [])
        self.foreground_hwnd: int = self.windows[0].hwnd if self.windows else 0
        self.closed_hwnds: list[int] = []
        self.focused_hwnds: list[int] = []

    def get_foreground_window(self) -> int:
        return self.foreground_hwnd

    def get_window_title(self, hwnd: int) -> str:
        for w in self.windows:
            if w.hwnd == hwnd:
                return w.title
        return ""

    def find_windows(self) -> list[WindowInfo]:
        return [w for w in self.windows if w.hwnd not in self.closed_hwnds and w.visible]

    def close_window(self, hwnd: int) -> bool:
        self.closed_hwnds.append(hwnd)
        return True

    def focus_window(self, hwnd: int) -> bool:
        self.focused_hwnds.append(hwnd)
        self.foreground_hwnd = hwnd
        return True


# Default backend instance
_default_window_backend: IWindowBackend = (
    NativeWin32WindowBackend() if os.name == "nt" and hasattr(ctypes, "windll") else SimulatedWindowBackend()
)


class OpenAppAction(Action):
    """Action that launches an application executable safely via subprocess."""

    def __init__(
        self,
        validator: ActionValidator | None = None,
        launcher: Callable[..., Any] | None = None,
        aliases: dict[str, str] | None = None,
    ) -> None:
        self.validator = validator or ActionValidator()
        self.launcher = launcher or subprocess.Popen
        self.aliases = dict(aliases or DEFAULT_APP_ALIASES)

    @property
    def action_type(self) -> ActionType:
        return ActionType.OPEN_APP

    def validate(self, params: dict[str, Any]) -> bool:
        if "app_name" not in params:
            raise ActionValidationError("Missing 'app_name' parameter for OPEN_APP.")
        self.validator.validate_app_name(params["app_name"])
        return True

    def _resolve_application(self, target_binary: str, app_lower: str) -> str | None:
        """Resolve target application to an executable or shortcut path on the system."""
        # 1. Absolute path check
        if os.path.isabs(target_binary) and os.path.exists(target_binary):
            return target_binary

        # 2. PATH resolution via shutil.which
        for cand in (target_binary, f"{target_binary}.exe", f"{app_lower}.exe"):
            found = shutil.which(cand)
            if found:
                return found

        # 3. Windows Store Apps (App Execution Aliases in %LOCALAPPDATA%\Microsoft\WindowsApps)
        winapps_dir = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps")
        if os.path.isdir(winapps_dir):
            for cand in (target_binary, f"{target_binary}.exe", f"{app_lower}.exe"):
                full_path = os.path.join(winapps_dir, cand)
                if os.path.exists(full_path):
                    return full_path
            # Case-insensitive directory scan
            target_low = target_binary.lower()
            try:
                for entry in os.listdir(winapps_dir):
                    entry_low = entry.lower()
                    if entry_low in (target_low, f"{target_low}.exe", f"{app_lower}.exe"):
                        return os.path.join(winapps_dir, entry)
            except OSError:
                pass

        # 4. Windows Registry App Paths (HKLM and HKCU)
        if winreg and os.name == "nt":
            for root_hkey in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                for key_name in (target_binary, f"{target_binary}.exe", f"{app_lower}.exe"):
                    try:
                        key_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{key_name}"
                        with winreg.OpenKey(root_hkey, key_path) as k:
                            raw_val, _ = winreg.QueryValueEx(k, "")
                            if raw_val:
                                expanded = os.path.expandvars(raw_val.strip().strip('"'))
                                if os.path.exists(expanded):
                                    return expanded
                    except Exception:
                        pass

        # 5. Start Menu Shortcuts (.lnk files)
        for start_dir in (
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
        ):
            if os.path.isdir(start_dir):
                try:
                    for root_dir, _, files in os.walk(start_dir):
                        for f in files:
                            if f.lower().endswith(".lnk"):
                                stem = f[:-4].lower()
                                if stem in (app_lower, target_binary.lower().removesuffix(".exe")):
                                    return os.path.join(root_dir, f)
                except Exception:
                    pass

        return None

    def execute(self, params: dict[str, Any]) -> ActionResult:
        app_name = params["app_name"].strip()
        app_lower = app_name.lower()

        # Resolve alias if present
        target_binary = self.aliases.get(app_lower, app_name)

        # Protocol URI handling (e.g. "ms-settings:")
        if target_binary.endswith(":") or "://" in target_binary:
            try:
                if self.launcher is subprocess.Popen:
                    if os.name == "nt" and hasattr(os, "startfile"):
                        os.startfile(target_binary)
                    else:
                        subprocess.Popen(["xdg-open", target_binary])
                else:
                    self.launcher([target_binary])
                logger.info("Launched protocol target '%s' for '%s'", target_binary, app_name)
                return ActionResult(
                    success=True,
                    output={"app_name": app_name, "target": target_binary, "pid": None},
                )
            except Exception as exc:
                logger.error("Failed to launch protocol '%s': %s", target_binary, exc)
                return ActionResult(
                    success=False,
                    output=None,
                    error_message=f"Could not launch application '{app_name}': {exc}",
                )

        # Resolve executable path on system
        resolved_bin = self._resolve_application(target_binary, app_lower)

        # If not resolved to a file on disk:
        if not resolved_bin:
            # If custom launcher was supplied (e.g. in unit tests), use target_binary with it
            if self.launcher is not subprocess.Popen:
                resolved_bin = target_binary
            else:
                # Try os.startfile as a fallback before failing
                try:
                    if os.name == "nt" and hasattr(os, "startfile"):
                        os.startfile(target_binary)
                        logger.info("Launched via os.startfile: '%s'", target_binary)
                        return ActionResult(
                            success=True,
                            output={"app_name": app_name, "binary": target_binary, "pid": None},
                        )
                except Exception:
                    pass
                return ActionResult(
                    success=False,
                    output=None,
                    error_message=f"Could not launch application '{app_name}': Executable not found on system",
                )

        try:
            if resolved_bin.lower().endswith(".lnk") and self.launcher is subprocess.Popen:
                os.startfile(resolved_bin)
                pid = None
            else:
                proc = self.launcher([resolved_bin])
                pid = getattr(proc, "pid", None)

            logger.info("Launched application '%s' (binary='%s', pid=%s)", app_name, resolved_bin, pid)
            return ActionResult(
                success=True,
                output={"app_name": app_name, "binary": resolved_bin, "pid": pid},
            )
        except Exception as exc:
            logger.error("Failed to launch application '%s': %s", app_name, exc)
            return ActionResult(
                success=False,
                output=None,
                error_message=f"Could not launch application '{app_name}': {exc}",
            )


class CloseAppAction(Action):
    """Action that gracefully closes a target window or application using WM_CLOSE."""

    def __init__(
        self,
        backend: IWindowBackend | None = None,
        validator: ActionValidator | None = None,
    ) -> None:
        self.backend = backend or _default_window_backend
        self.validator = validator or ActionValidator()

    @property
    def action_type(self) -> ActionType:
        return ActionType.CLOSE_APP

    def validate(self, params: dict[str, Any]) -> bool:
        if "target" not in params:
            raise ActionValidationError("Missing 'target' parameter for CLOSE_APP.")
        target = str(params["target"]).strip()
        if not target:
            raise ActionValidationError("'target' cannot be empty for CLOSE_APP.")
        return True

    def execute(self, params: dict[str, Any]) -> ActionResult:
        target = str(params["target"]).strip()
        target_lower = target.lower()

        # 1. Target is current active window
        if target_lower in ("current_window", "window", "active_window", "this"):
            hwnd = self.backend.get_foreground_window()
            if not hwnd:
                return ActionResult(success=False, error_message="No active foreground window found.")
            title = self.backend.get_window_title(hwnd)
            success = self.backend.close_window(hwnd)
            if success:
                logger.info("Closed current active window '%s' (hwnd=%d)", title, hwnd)
                return ActionResult(success=True, output={"hwnd": hwnd, "title": title})
            return ActionResult(success=False, error_message=f"Failed to post close message to window (hwnd={hwnd})")

        # 2. Search for matching top-level window by title or name
        windows = self.backend.find_windows()
        matching_window: WindowInfo | None = None

        for win in windows:
            if target_lower in win.title.lower():
                matching_window = win
                break

        if not matching_window:
            return ActionResult(
                success=False,
                error_message=f"No matching open window found for '{target}'",
            )

        success = self.backend.close_window(matching_window.hwnd)
        if success:
            logger.info("Closed window '%s' (hwnd=%d)", matching_window.title, matching_window.hwnd)
            return ActionResult(
                success=True,
                output={"hwnd": matching_window.hwnd, "title": matching_window.title},
            )

        return ActionResult(
            success=False,
            error_message=f"Failed to close window '{matching_window.title}'",
        )


class SwitchWindowAction(Action):
    """Action that brings an application or window to the foreground."""

    def __init__(
        self,
        backend: IWindowBackend | None = None,
        validator: ActionValidator | None = None,
    ) -> None:
        self.backend = backend or _default_window_backend
        self.validator = validator or ActionValidator()

    @property
    def action_type(self) -> ActionType:
        return ActionType.SWITCH_WINDOW

    def validate(self, params: dict[str, Any]) -> bool:
        if "window_name" not in params:
            raise ActionValidationError("Missing 'window_name' parameter for SWITCH_WINDOW.")
        name = str(params["window_name"]).strip()
        if not name:
            raise ActionValidationError("'window_name' cannot be empty.")
        return True

    def execute(self, params: dict[str, Any]) -> ActionResult:
        window_name = str(params["window_name"]).strip()
        name_lower = window_name.lower()

        windows = self.backend.find_windows()
        matching_window: WindowInfo | None = None

        for win in windows:
            if name_lower in win.title.lower():
                matching_window = win
                break

        if not matching_window:
            return ActionResult(
                success=False,
                error_message=f"No matching window found for '{window_name}'",
            )

        success = self.backend.focus_window(matching_window.hwnd)
        if success:
            logger.info("Switched foreground to window '%s' (hwnd=%d)", matching_window.title, matching_window.hwnd)
            return ActionResult(
                success=True,
                output={"hwnd": matching_window.hwnd, "title": matching_window.title},
            )

        return ActionResult(
            success=False,
            error_message=f"Failed to focus window '{matching_window.title}'",
        )


__all__ = [
    "CloseAppAction",
    "DEFAULT_APP_ALIASES",
    "IWindowBackend",
    "NativeWin32WindowBackend",
    "OpenAppAction",
    "SimulatedWindowBackend",
    "SwitchWindowAction",
    "WindowInfo",
]
