"""File and Folder System Actions for PC Voice Agent.

Provides safe file/folder opening, renaming, moving, and deletion using
pathlib, shutil, os.startfile, and strict path validation boundaries.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any, Callable

from voice_agent.control.actions.base import (
    Action,
    ActionResult,
    ActionType,
    ActionValidationError,
)
from voice_agent.control.action_validator import ActionValidator

logger = logging.getLogger(__name__)

# Default file opening function (os.startfile on Windows)
_default_file_opener: Callable[[str], None] | None = getattr(os, "startfile", None)


class OpenFileAction(Action):
    """Action that opens a file using the default associated application."""

    def __init__(
        self,
        validator: ActionValidator | None = None,
        opener: Callable[[str], None] | None = None,
    ) -> None:
        self.validator = validator or ActionValidator()
        self.opener = opener or _default_file_opener

    @property
    def action_type(self) -> ActionType:
        return ActionType.OPEN_FILE

    def validate(self, params: dict[str, Any]) -> bool:
        if "path" not in params:
            raise ActionValidationError("Missing 'path' parameter for OPEN_FILE.")
        self.validator.validate_path(params["path"], must_exist=True)
        return True

    def execute(self, params: dict[str, Any]) -> ActionResult:
        raw_path = params["path"]
        resolved_path = self.validator.validate_path(raw_path, must_exist=True)

        if resolved_path.is_dir():
            return ActionResult(
                success=False,
                error_message=f"Path '{resolved_path}' is a directory, not a file. Use OPEN_FOLDER instead.",
            )

        try:
            if self.opener:
                self.opener(str(resolved_path))
            logger.info("Opened file '%s'", resolved_path)
            return ActionResult(
                success=True,
                output={"path": str(resolved_path), "name": resolved_path.name},
            )
        except Exception as exc:
            logger.error("Failed to open file '%s': %s", resolved_path, exc)
            return ActionResult(success=False, output=None, error_message=str(exc))


class OpenFolderAction(Action):
    """Action that opens a folder or directory in File Explorer."""

    def __init__(
        self,
        validator: ActionValidator | None = None,
        opener: Callable[[str], None] | None = None,
    ) -> None:
        self.validator = validator or ActionValidator()
        self.opener = opener or _default_file_opener

    @property
    def action_type(self) -> ActionType:
        return ActionType.OPEN_FOLDER

    def validate(self, params: dict[str, Any]) -> bool:
        if "path" not in params:
            raise ActionValidationError("Missing 'path' parameter for OPEN_FOLDER.")
        self.validator.validate_path(params["path"], must_exist=True)
        return True

    def execute(self, params: dict[str, Any]) -> ActionResult:
        raw_path = params["path"]
        resolved_path = self.validator.validate_path(raw_path, must_exist=True)

        if not resolved_path.is_dir():
            # If it's a file, open its parent folder
            resolved_path = resolved_path.parent

        try:
            if self.opener:
                self.opener(str(resolved_path))
            logger.info("Opened folder '%s'", resolved_path)
            return ActionResult(
                success=True,
                output={"path": str(resolved_path), "name": resolved_path.name},
            )
        except Exception as exc:
            logger.error("Failed to open folder '%s': %s", resolved_path, exc)
            return ActionResult(success=False, output=None, error_message=str(exc))


class RenameFileAction(Action):
    """Action that renames a file or directory."""

    def __init__(self, validator: ActionValidator | None = None) -> None:
        self.validator = validator or ActionValidator()

    @property
    def action_type(self) -> ActionType:
        return ActionType.RENAME_FILE

    def validate(self, params: dict[str, Any]) -> bool:
        if "source" not in params:
            raise ActionValidationError("Missing 'source' parameter for RENAME_FILE.")
        if "destination" not in params:
            raise ActionValidationError("Missing 'destination' parameter for RENAME_FILE.")
        self.validator.validate_path(params["source"], must_exist=True)
        self.validator.validate_path(params["destination"])
        return True

    def execute(self, params: dict[str, Any]) -> ActionResult:
        src = self.validator.validate_path(params["source"], must_exist=True)
        dst = self.validator.validate_path(params["destination"])

        try:
            # If destination is just a new filename, keep in same parent
            if len(Path(params["destination"]).parts) == 1:
                dst = src.parent / params["destination"].strip()

            src.rename(dst)
            logger.info("Renamed '%s' to '%s'", src, dst)
            return ActionResult(
                success=True,
                output={"source": str(src), "destination": str(dst)},
            )
        except Exception as exc:
            logger.error("Failed to rename '%s' to '%s': %s", src, dst, exc)
            return ActionResult(success=False, output=None, error_message=str(exc))


class MoveFileAction(Action):
    """Action that moves a file or directory to a target directory or path."""

    def __init__(self, validator: ActionValidator | None = None) -> None:
        self.validator = validator or ActionValidator()

    @property
    def action_type(self) -> ActionType:
        return ActionType.MOVE_FILE

    def validate(self, params: dict[str, Any]) -> bool:
        if "source" not in params or "destination" not in params:
            raise ActionValidationError("MOVE_FILE requires 'source' and 'destination' parameters.")
        self.validator.validate_path(params["source"], must_exist=True)
        self.validator.validate_path(params["destination"])
        return True

    def execute(self, params: dict[str, Any]) -> ActionResult:
        src = self.validator.validate_path(params["source"], must_exist=True)
        dst = self.validator.validate_path(params["destination"])

        try:
            moved_path = shutil.move(str(src), str(dst))
            logger.info("Moved '%s' to '%s'", src, moved_path)
            return ActionResult(
                success=True,
                output={"source": str(src), "destination": moved_path},
            )
        except Exception as exc:
            logger.error("Failed to move '%s' to '%s': %s", src, dst, exc)
            return ActionResult(success=False, output=None, error_message=str(exc))


class DeleteFileAction(Action):
    """Action that deletes a file, enforcing protected directory safety."""

    def __init__(
        self,
        validator: ActionValidator | None = None,
        use_trash: bool = True,
    ) -> None:
        self.validator = validator or ActionValidator()
        self.use_trash = use_trash

    @property
    def action_type(self) -> ActionType:
        return ActionType.DELETE_FILE

    def validate(self, params: dict[str, Any]) -> bool:
        if "path" not in params:
            raise ActionValidationError("Missing 'path' parameter for DELETE_FILE.")
        self.validator.validate_path(params["path"], must_exist=True, for_deletion=True)
        return True

    def execute(self, params: dict[str, Any]) -> ActionResult:
        target_path = self.validator.validate_path(
            params["path"],
            must_exist=True,
            for_deletion=True,
        )

        try:
            if self.use_trash:
                try:
                    import send2trash
                    send2trash.send2trash(str(target_path))
                    logger.info("Moved file to Recycle Bin: '%s'", target_path)
                    return ActionResult(
                        success=True,
                        output={"path": str(target_path), "recycle_bin": True},
                    )
                except ImportError:
                    pass

            if target_path.is_dir():
                shutil.rmtree(str(target_path))
            else:
                target_path.unlink()

            logger.info("Deleted file '%s'", target_path)
            return ActionResult(
                success=True,
                output={"path": str(target_path), "recycle_bin": False},
            )
        except Exception as exc:
            logger.error("Failed to delete '%s': %s", target_path, exc)
            return ActionResult(success=False, output=None, error_message=str(exc))


__all__ = [
    "DeleteFileAction",
    "MoveFileAction",
    "OpenFileAction",
    "OpenFolderAction",
    "RenameFileAction",
]
