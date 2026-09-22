"""Action Parameter and Path Validator for PC Voice Agent Control Core.

Enforces strict security boundaries before action execution:
- Path traversal protection and normalization.
- Protection against arbitrary shell command injection.
- Blacklisting of dangerous administrative binaries.
- URL protocol and hostname validation.
- Safe keyboard, mouse, and text parameter validation.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from voice_agent.control.models import (
    ActionRequest,
    ActionType,
    ActionValidationError,
)

logger = logging.getLogger(__name__)


class ActionValidator:
    """Validator enforcing security constraints on ActionRequest parameters."""

    # Disallowed executable binaries (to prevent arbitrary shell/admin execution)
    DISALLOWED_BINARIES = {
        "cmd",
        "cmd.exe",
        "powershell",
        "powershell.exe",
        "pwsh",
        "pwsh.exe",
        "bash",
        "bash.exe",
        "wscript",
        "wscript.exe",
        "cscript",
        "cscript.exe",
        "reg",
        "reg.exe",
        "format",
        "format.com",
        "vssadmin",
        "vssadmin.exe",
        "diskpart",
        "diskpart.exe",
        "bcdedit",
        "bcdedit.exe",
        "attrib",
        "attrib.exe",
        "schtasks",
        "schtasks.exe",
    }

    # Shell injection and control characters
    SHELL_INJECTION_CHARS = set("&|;><`$\r\n\0")

    # Allowed URL protocols
    ALLOWED_URL_SCHEMES = {"http", "https"}

    # Allowed mouse buttons
    ALLOWED_MOUSE_BUTTONS = {"left", "right", "middle"}

    # Allowed mouse directions
    ALLOWED_MOUSE_DIRECTIONS = {"up", "down", "left", "right"}

    # Windows protected root system directories (cannot be deleted or overwritten)
    PROTECTED_SYSTEM_PATHS = {
        "c:\\",
        "c:\\windows",
        "c:\\windows\\system32",
        "c:\\program files",
        "c:\\program files (x86)",
        "c:\\users",
    }

    def __init__(self, base_directory: Path | str | None = None) -> None:
        """Initialize ActionValidator.

        Args:
            base_directory: Optional base working directory for relative paths.
        """
        self.base_directory = Path(base_directory).resolve() if base_directory else Path.cwd().resolve()

    def validate_app_name(self, app_name: str) -> str:
        """Validate an application name for launch.

        Args:
            app_name: The application name or binary requested.

        Returns:
            Cleaned app name string.

        Raises:
            ActionValidationError: If name contains injection chars or is blacklisted.
        """
        if not app_name or not isinstance(app_name, str):
            raise ActionValidationError("Application name must be a non-empty string.")

        clean_name = app_name.strip().rstrip(".!?,;:\"'")
        if not clean_name:
            raise ActionValidationError("Application name cannot be blank.")

        # Check shell injection characters
        for char in clean_name:
            if char in self.SHELL_INJECTION_CHARS:
                raise ActionValidationError(
                    f"Shell injection character '{char}' detected in application name: {clean_name}"
                )

        # Check against disallowed binaries
        base_binary = os.path.basename(clean_name).lower()
        if base_binary in self.DISALLOWED_BINARIES or base_binary.removesuffix(".exe") in self.DISALLOWED_BINARIES:
            raise ActionValidationError(
                f"Execution of administrative or shell binary '{clean_name}' is prohibited."
            )

        return clean_name

    def validate_path(
        self,
        path_str: str,
        must_exist: bool = False,
        for_deletion: bool = False,
    ) -> Path:
        """Validate, normalize, and verify safety of a filesystem path.

        Args:
            path_str: File or directory path string.
            must_exist: Whether the path must already exist on disk.
            for_deletion: Whether the path is targeted for deletion.

        Returns:
            Resolved Path object.

        Raises:
            ActionValidationError: If path contains null bytes, invalid traversal,
                                  is a protected system path, or does not exist.
        """
        if not path_str or not isinstance(path_str, str):
            raise ActionValidationError("Path parameter must be a non-empty string.")

        if "\0" in path_str:
            raise ActionValidationError("Null byte detected in path.")

        clean_path_str = path_str.strip().strip('"\'')
        if not clean_path_str:
            raise ActionValidationError("Path parameter cannot be blank.")

        # Resolve path
        candidate_path = Path(clean_path_str)
        if not candidate_path.is_absolute():
            resolved = (self.base_directory / candidate_path).resolve()
        else:
            resolved = candidate_path.resolve()

        resolved_lower = str(resolved).lower().rstrip("\\/")

        # Protect Windows core system folders
        for protected in self.PROTECTED_SYSTEM_PATHS:
            if resolved_lower == protected.rstrip("\\/"):
                raise ActionValidationError(
                    f"Access to protected system directory '{resolved}' is restricted."
                )

        if for_deletion:
            # Prevent deleting entire drives or root folders
            if len(resolved.parts) <= 1 or resolved_lower in self.PROTECTED_SYSTEM_PATHS:
                raise ActionValidationError(
                    f"Deletion of root or protected directory '{resolved}' is strictly prohibited."
                )

        if must_exist and not resolved.exists():
            raise ActionValidationError(f"File or directory does not exist: {resolved}")

        return resolved

    def validate_url(self, url_str: str) -> str:
        """Validate a web URL for protocol and hostname.

        Args:
            url_str: Web URL to validate.

        Returns:
            Validated URL string.

        Raises:
            ActionValidationError: If URL is malformed or uses disallowed schemes.
        """
        if not url_str or not isinstance(url_str, str):
            raise ActionValidationError("URL must be a non-empty string.")

        clean_url = url_str.strip()
        parsed = urlparse(clean_url)

        if not parsed.scheme:
            # If scheme missing, prepend https:// and re-parse
            clean_url = f"https://{clean_url}"
            parsed = urlparse(clean_url)

        if parsed.scheme.lower() not in self.ALLOWED_URL_SCHEMES:
            raise ActionValidationError(
                f"Disallowed URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."
            )

        if not parsed.netloc:
            raise ActionValidationError(f"Invalid URL host in '{url_str}'.")

        # Check for control or injection characters
        for char in clean_url:
            if char in ("\r", "\n", "\0", "`"):
                raise ActionValidationError("Invalid control characters in URL.")

        return clean_url

    def validate_mouse_coords(self, x: Any, y: Any) -> tuple[int, int]:
        """Validate mouse absolute coordinates.

        Args:
            x: X-coordinate integer.
            y: Y-coordinate integer.

        Returns:
            Tuple of validated (x, y) integers.

        Raises:
            ActionValidationError: If coordinates are non-integer or out of bounds.
        """
        try:
            x_int = int(x)
            y_int = int(y)
        except (ValueError, TypeError) as exc:
            raise ActionValidationError(f"Mouse coordinates must be integers: x={x}, y={y}") from exc

        if x_int < 0 or x_int > 16384 or y_int < 0 or y_int > 16384:
            raise ActionValidationError(f"Mouse coordinates out of desktop range: ({x_int}, {y_int})")

        return x_int, y_int

    def validate_mouse_button(self, button: str) -> str:
        """Validate mouse button name.

        Args:
            button: Button name string ('left', 'right', 'middle').

        Returns:
            Cleaned button name.

        Raises:
            ActionValidationError: If button is invalid.
        """
        btn = str(button).lower().strip()
        if btn not in self.ALLOWED_MOUSE_BUTTONS:
            raise ActionValidationError(f"Invalid mouse button '{button}'. Must be one of {self.ALLOWED_MOUSE_BUTTONS}")
        return btn

    def validate_text(self, text: Any) -> str:
        """Validate text to be typed or processed.

        Args:
            text: Text string.

        Returns:
            Validated text string.

        Raises:
            ActionValidationError: If text contains null bytes or is invalid type.
        """
        if not isinstance(text, str):
            raise ActionValidationError("Text parameter must be a string.")
        if "\0" in text:
            raise ActionValidationError("Null bytes not permitted in typed text.")
        return text

    def validate_action(self, action: ActionRequest) -> bool:
        """Validate all parameters of an ActionRequest according to its ActionType.

        Args:
            action: The ActionRequest to validate.

        Returns:
            bool: True if all parameters pass validation.

        Raises:
            ActionValidationError: If any parameter is missing or violates security constraints.
        """
        if not isinstance(action, ActionRequest):
            raise ActionValidationError(f"Expected ActionRequest instance, got {type(action).__name__}")

        t = action.action_type
        p = action.params

        if t == ActionType.OPEN_APP:
            if "app_name" not in p:
                raise ActionValidationError("Action OPEN_APP requires 'app_name' parameter.")
            self.validate_app_name(p["app_name"])

        elif t == ActionType.CLOSE_APP:
            if "target" not in p:
                raise ActionValidationError("Action CLOSE_APP requires 'target' parameter.")
            target = str(p["target"]).strip()
            if not target:
                raise ActionValidationError("CLOSE_APP 'target' cannot be empty.")
            for char in target:
                if char in self.SHELL_INJECTION_CHARS:
                    raise ActionValidationError(f"Shell injection character in CLOSE_APP target: {target}")

        elif t == ActionType.SWITCH_WINDOW:
            if "window_name" not in p or not str(p["window_name"]).strip():
                raise ActionValidationError("Action SWITCH_WINDOW requires non-empty 'window_name'.")

        elif t == ActionType.TYPE_TEXT:
            if "text" not in p:
                raise ActionValidationError("Action TYPE_TEXT requires 'text' parameter.")
            self.validate_text(p["text"])

        elif t == ActionType.PRESS_KEY:
            if "key" not in p or not str(p["key"]).strip():
                raise ActionValidationError("Action PRESS_KEY requires non-empty 'key' parameter.")

        elif t == ActionType.HOTKEY:
            if "keys" not in p and "hotkey" not in p:
                raise ActionValidationError("Action HOTKEY requires 'keys' list or 'hotkey' string.")

        elif t == ActionType.CLICK:
            button = p.get("button", "left")
            self.validate_mouse_button(button)
            click_count = p.get("click_count", 1)
            try:
                if int(click_count) < 1 or int(click_count) > 10:
                    raise ActionValidationError(f"Invalid click_count: {click_count}")
            except (ValueError, TypeError) as exc:
                raise ActionValidationError(f"click_count must be an integer: {click_count}") from exc

        elif t == ActionType.MOVE_MOUSE:
            mode = p.get("mode", "relative")
            if mode == "absolute":
                if "x" not in p or "y" not in p:
                    raise ActionValidationError("Absolute MOVE_MOUSE requires 'x' and 'y' parameters.")
                self.validate_mouse_coords(p["x"], p["y"])
            elif mode == "relative":
                direction = p.get("direction", "up")
                if direction not in self.ALLOWED_MOUSE_DIRECTIONS:
                    raise ActionValidationError(f"Invalid mouse move direction: {direction}")
            else:
                raise ActionValidationError(f"Invalid mouse move mode: {mode}")

        elif t == ActionType.OPEN_URL:
            if "url" not in p:
                raise ActionValidationError("Action OPEN_URL requires 'url' parameter.")
            self.validate_url(p["url"])

        elif t == ActionType.SEARCH_WEB:
            if "query" not in p or not str(p["query"]).strip():
                raise ActionValidationError("Action SEARCH_WEB requires non-empty 'query'.")

        elif t in (ActionType.READ_CLIPBOARD, ActionType.COPY, ActionType.PASTE):
            # No specific mandatory parameters needed
            pass

        elif t == ActionType.OPEN_FILE:
            if "path" not in p:
                raise ActionValidationError("Action OPEN_FILE requires 'path' parameter.")
            self.validate_path(p["path"])

        elif t == ActionType.OPEN_FOLDER:
            if "path" not in p:
                raise ActionValidationError("Action OPEN_FOLDER requires 'path' parameter.")
            self.validate_path(p["path"])

        elif t == ActionType.DELETE_FILE:
            if "path" not in p:
                raise ActionValidationError("Action DELETE_FILE requires 'path' parameter.")
            self.validate_path(p["path"], for_deletion=True)

        elif t in (ActionType.RENAME_FILE, ActionType.MOVE_FILE):
            if "source" not in p or "destination" not in p:
                raise ActionValidationError(f"Action {t.value} requires 'source' and 'destination' parameters.")
            self.validate_path(p["source"])
            self.validate_path(p["destination"])

        return True

    def is_valid(self, action: ActionRequest) -> bool:
        """Check if an ActionRequest passes validation without raising an exception.

        Args:
            action: The ActionRequest to check.

        Returns:
            bool: True if valid, False otherwise.
        """
        try:
            return self.validate_action(action)
        except ActionValidationError:
            return False


__all__ = ["ActionValidator"]
