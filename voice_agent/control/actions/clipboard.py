"""Clipboard Control Actions for PC Voice Agent.

Provides Copy, Paste, and Read Clipboard actions in control mode using
system keyboard shortcut dispatch and the Win32 Clipboard Manager.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from voice_agent.clipboard.manager import ClipboardManager
from voice_agent.control.actions.base import (
    Action,
    ActionResult,
    ActionType,
)
from voice_agent.control.actions.keyboard import (
    IKeyboardBackend,
    _default_keyboard_backend,
)

logger = logging.getLogger(__name__)


class CopyAction(Action):
    """Action that triggers standard Ctrl+C to copy selected content to the clipboard."""

    def __init__(self, keyboard_backend: IKeyboardBackend | None = None) -> None:
        self.keyboard = keyboard_backend or _default_keyboard_backend

    @property
    def action_type(self) -> ActionType:
        return ActionType.COPY

    def validate(self, params: dict[str, Any]) -> bool:
        return True

    def execute(self, params: dict[str, Any]) -> ActionResult:
        try:
            self.keyboard.hotkey(["ctrl", "c"])
            time.sleep(0.05)  # Allow clipboard buffer to settle
            logger.info("Dispatched Copy (Ctrl+C) command")
            return ActionResult(success=True, output="Selection copied to clipboard")
        except Exception as exc:
            logger.error("Failed to execute Copy action: %s", exc)
            return ActionResult(success=False, output=None, error_message=str(exc))


class PasteAction(Action):
    """Action that triggers standard Ctrl+V to paste clipboard content."""

    def __init__(self, keyboard_backend: IKeyboardBackend | None = None) -> None:
        self.keyboard = keyboard_backend or _default_keyboard_backend

    @property
    def action_type(self) -> ActionType:
        return ActionType.PASTE

    def validate(self, params: dict[str, Any]) -> bool:
        return True

    def execute(self, params: dict[str, Any]) -> ActionResult:
        try:
            self.keyboard.hotkey(["ctrl", "v"])
            time.sleep(0.05)
            logger.info("Dispatched Paste (Ctrl+V) command")
            return ActionResult(success=True, output="Pasted clipboard content")
        except Exception as exc:
            logger.error("Failed to execute Paste action: %s", exc)
            return ActionResult(success=False, output=None, error_message=str(exc))


class ReadClipboardAction(Action):
    """Action that retrieves current text content from the clipboard."""

    def __init__(self, clipboard_manager: ClipboardManager | None = None) -> None:
        self.clipboard = clipboard_manager or ClipboardManager()

    @property
    def action_type(self) -> ActionType:
        return ActionType.READ_CLIPBOARD

    def validate(self, params: dict[str, Any]) -> bool:
        return True

    def execute(self, params: dict[str, Any]) -> ActionResult:
        try:
            content = self.clipboard.get_text()
            logger.info("Retrieved %d characters from clipboard", len(content))
            return ActionResult(
                success=True,
                output={"text": content, "character_count": len(content)},
            )
        except Exception as exc:
            logger.error("Failed to read clipboard content: %s", exc)
            return ActionResult(success=False, output=None, error_message=str(exc))


__all__ = ["CopyAction", "PasteAction", "ReadClipboardAction"]
