"""Windows Run at Startup registry helper for PC Voice Agent.

Manages automatic application launch on Windows user login by interacting
safely with HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run.
Supports testable registry backends and isolated execution.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
from typing import Any, Protocol

logger = logging.getLogger(__name__)

RUN_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
DEFAULT_APP_NAME = "PCVoiceAgent"
DEFAULT_ARGS = "--tray"

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    winreg = None  # type: ignore[assignment]
    HAS_WINREG = False


class RegistryBackend(Protocol):
    """Protocol defining registry read/write operations for startup management."""

    def get_value(self, subkey: str, name: str) -> str | None:
        """Read a string value from HKCU\\subkey. Return None if not found."""
        ...

    def set_value(self, subkey: str, name: str, value: str) -> None:
        """Set a string value in HKCU\\subkey."""
        ...

    def delete_value(self, subkey: str, name: str) -> bool:
        """Delete a named value from HKCU\\subkey. Return True if deleted, False if not found."""
        ...


class WinregBackend:
    """Real Windows Registry backend interacting with winreg."""

    def get_value(self, subkey: str, name: str) -> str | None:
        if not HAS_WINREG:
            return None
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_READ) as key:
                val, val_type = winreg.QueryValueEx(key, name)
                return str(val) if val is not None else None
        except FileNotFoundError:
            return None
        except OSError as e:
            logger.warning("Error reading registry key %s\\%s: %s", subkey, name, e)
            return None

    def set_value(self, subkey: str, name: str, value: str) -> None:
        if not HAS_WINREG:
            raise RuntimeError("winreg module not available on this platform")
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)

    def delete_value(self, subkey: str, name: str) -> bool:
        if not HAS_WINREG:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)
                return True
        except FileNotFoundError:
            return False
        except OSError as e:
            logger.warning("Error deleting registry value %s\\%s: %s", subkey, name, e)
            return False


class MemoryRegistryBackend:
    """In-memory simulated registry backend for testing and cross-platform execution."""

    def __init__(self, initial_values: dict[str, dict[str, str]] | None = None) -> None:
        self._store: dict[str, dict[str, str]] = initial_values or {}

    def get_value(self, subkey: str, name: str) -> str | None:
        return self._store.get(subkey, {}).get(name)

    def set_value(self, subkey: str, name: str, value: str) -> None:
        if subkey not in self._store:
            self._store[subkey] = {}
        self._store[subkey][name] = str(value)

    def delete_value(self, subkey: str, name: str) -> bool:
        if subkey in self._store and name in self._store[subkey]:
            del self._store[subkey][name]
            return True
        return False


def get_default_backend() -> RegistryBackend:
    """Return WinregBackend if supported, otherwise MemoryRegistryBackend."""
    if HAS_WINREG and sys.platform == "win32":
        return WinregBackend()
    return MemoryRegistryBackend()


def build_startup_command(
    exe_path: str | Path | None = None,
    args: str = DEFAULT_ARGS,
) -> str:
    """Construct the command line string to launch the application.

    Args:
        exe_path: Custom executable path. If None, resolves from current python process.
        args: Arguments to append (e.g. '--tray' or '--minimized').

    Returns:
        Properly quoted startup command string.
    """
    clean_args = args.strip()

    if exe_path is not None:
        target = Path(exe_path).resolve()
        if clean_args:
            return f'"{target}" {clean_args}'
        return f'"{target}"'

    # Check if running as a frozen PyInstaller bundle
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        if clean_args:
            return f'"{exe}" {clean_args}'
        return f'"{exe}"'

    # Running from Python source
    python_exe = Path(sys.executable).resolve()
    script_path = Path(sys.argv[0]).resolve()
    if clean_args:
        return f'"{python_exe}" "{script_path}" {clean_args}'
    return f'"{python_exe}" "{script_path}"'


def is_startup_enabled(
    app_name: str = DEFAULT_APP_NAME,
    backend: RegistryBackend | None = None,
) -> bool:
    """Check whether the application is registered to run at Windows user login.

    Args:
        app_name: Name of the registry value in HKCU Run key.
        backend: Optional RegistryBackend. Defaults to system backend.

    Returns:
        True if the value is registered and non-empty, False otherwise.
    """
    reg = backend or get_default_backend()
    val = reg.get_value(RUN_REG_KEY, app_name)
    return bool(val and val.strip())


def get_startup_command(
    app_name: str = DEFAULT_APP_NAME,
    backend: RegistryBackend | None = None,
) -> str | None:
    """Retrieve the registered startup command line string.

    Args:
        app_name: Name of the registry value in HKCU Run key.
        backend: Optional RegistryBackend. Defaults to system backend.

    Returns:
        The command string if registered, or None.
    """
    reg = backend or get_default_backend()
    return reg.get_value(RUN_REG_KEY, app_name)


def set_startup_enabled(
    enabled: bool,
    app_name: str = DEFAULT_APP_NAME,
    exe_path: str | Path | None = None,
    args: str = DEFAULT_ARGS,
    backend: RegistryBackend | None = None,
) -> bool:
    """Enable or disable application launch at Windows user login.

    Args:
        enabled: True to register in Run key, False to unregister.
        app_name: Registry value name.
        exe_path: Custom executable path. If None, auto-detected.
        args: Command-line arguments to append.
        backend: Optional RegistryBackend for testing or custom persistence.

    Returns:
        True if the operation succeeded, False on failure.
    """
    reg = backend or get_default_backend()

    try:
        if enabled:
            cmd = build_startup_command(exe_path=exe_path, args=args)
            reg.set_value(RUN_REG_KEY, app_name, cmd)
            logger.info("Enabled Windows startup for '%s': %s", app_name, cmd)
            return True
        else:
            reg.delete_value(RUN_REG_KEY, app_name)
            logger.info("Disabled Windows startup for '%s'", app_name)
            return True
    except Exception as e:
        logger.error("Failed to set startup enabled=%s for '%s': %s", enabled, app_name, e)
        return False
