"""Multi-Step Command Router and Control Mode Pipeline Coordinator.

Orchestrates full control mode execution:
State Machine: READY -> LISTENING -> PROCESSING -> VALIDATING -> CONFIRMING -> EXECUTING -> RESULT -> READY
Sequential multi-step chaining with immediate abort on error or confirmation rejection.
History recording in SQLite database.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from voice_agent.app.lifecycle import ControlState
from voice_agent.control.actions.applications import (
    CloseAppAction,
    OpenAppAction,
    SwitchWindowAction,
)
from voice_agent.control.actions.base import (
    Action,
    ActionResult,
    ActionType,
    ActionValidationError,
    RiskLevel,
)
from voice_agent.control.actions.browser import (
    OpenUrlAction,
    SearchWebAction,
)
from voice_agent.control.actions.clipboard import (
    CopyAction,
    PasteAction,
    ReadClipboardAction,
)
from voice_agent.control.actions.files import (
    DeleteFileAction,
    MoveFileAction,
    OpenFileAction,
    OpenFolderAction,
    RenameFileAction,
)
from voice_agent.control.actions.keyboard import (
    HotkeyAction,
    PressKeyAction,
    TypeTextAction,
)
from voice_agent.control.actions.mouse import (
    ClickAction,
    MoveMouseAction,
)
from voice_agent.control.action_validator import ActionValidator
from voice_agent.control.models import ActionRequest
from voice_agent.control.parser import CommandParser, UnsupportedCommandResult
from voice_agent.control.risk import RiskClassifier
from voice_agent.storage.database import DatabaseManager
from voice_agent.storage.models import HistoryEntry

logger = logging.getLogger(__name__)


@dataclass
class ActionStepReport:
    """Report detailing the execution outcome of an individual action in a chain."""

    action_type: ActionType
    params: dict[str, Any]
    risk_level: RiskLevel
    success: bool
    output: Any = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "params": dict(self.params),
            "risk_level": self.risk_level.value,
            "success": self.success,
            "output": self.output,
            "error_message": self.error_message,
        }


@dataclass
class CommandExecutionReport:
    """Consolidated report for a complete voice control interaction."""

    raw_command: str
    status: str  # "success", "failed", "cancelled"
    steps: list[ActionStepReport] = field(default_factory=list)
    error_message: str | None = None
    execution_time_ms: float = 0.0

    @property
    def is_success(self) -> bool:
        return self.status == "success"

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_command": self.raw_command,
            "status": self.status,
            "steps": [s.to_dict() for s in self.steps],
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
        }


class CommandRouter:
    """Coordinates parsing, validation, confirmation, and sequential action dispatch."""

    def __init__(
        self,
        parser: CommandParser | None = None,
        validator: ActionValidator | None = None,
        risk_classifier: RiskClassifier | None = None,
        action_registry: dict[ActionType, Action] | None = None,
        database: DatabaseManager | None = None,
        confirm_handler: Callable[[ActionRequest], bool] | None = None,
        state_callback: Callable[[ControlState, str | None], None] | None = None,
        confirm_medium: bool = False,
        confirm_high: bool = True,
        step_pause_seconds: float = 0.05,
    ) -> None:
        """Initialize CommandRouter.

        Args:
            parser: CommandParser instance.
            validator: ActionValidator instance.
            risk_classifier: RiskClassifier instance.
            action_registry: Optional custom action implementations dictionary.
            database: Optional DatabaseManager for interaction logging.
            confirm_handler: Callable displaying confirmation dialog to user.
            state_callback: Callback receiving (ControlState, optional_message).
            confirm_medium: Require confirmation for medium-risk actions.
            confirm_high: Require confirmation for high-risk actions.
            step_pause_seconds: Delay pause between multi-step action executions.
        """
        self.parser = parser or CommandParser()
        self.validator = validator or ActionValidator()
        self.risk_classifier = risk_classifier or RiskClassifier()
        self.database = database
        self.confirm_handler = confirm_handler
        self.state_callback = state_callback
        self.confirm_medium = confirm_medium
        self.confirm_high = confirm_high
        self.step_pause_seconds = step_pause_seconds

        self.current_state = ControlState.READY

        # Register default actions if not provided
        self.registry: dict[ActionType, Action] = dict(action_registry or self._build_default_registry())

    def _build_default_registry(self) -> dict[ActionType, Action]:
        """Construct the default mapping from ActionType to concrete Action handlers."""
        return {
            ActionType.OPEN_APP: OpenAppAction(validator=self.validator),
            ActionType.CLOSE_APP: CloseAppAction(validator=self.validator),
            ActionType.SWITCH_WINDOW: SwitchWindowAction(validator=self.validator),
            ActionType.TYPE_TEXT: TypeTextAction(validator=self.validator),
            ActionType.PRESS_KEY: PressKeyAction(validator=self.validator),
            ActionType.HOTKEY: HotkeyAction(validator=self.validator),
            ActionType.CLICK: ClickAction(validator=self.validator),
            ActionType.MOVE_MOUSE: MoveMouseAction(validator=self.validator),
            ActionType.OPEN_URL: OpenUrlAction(validator=self.validator),
            ActionType.SEARCH_WEB: SearchWebAction(validator=self.validator),
            ActionType.OPEN_FILE: OpenFileAction(validator=self.validator),
            ActionType.OPEN_FOLDER: OpenFolderAction(validator=self.validator),
            ActionType.RENAME_FILE: RenameFileAction(validator=self.validator),
            ActionType.MOVE_FILE: MoveFileAction(validator=self.validator),
            ActionType.DELETE_FILE: DeleteFileAction(validator=self.validator),
            ActionType.COPY: CopyAction(),
            ActionType.PASTE: PasteAction(),
            ActionType.READ_CLIPBOARD: ReadClipboardAction(),
        }

    def _set_state(self, state: ControlState, message: str | None = None) -> None:
        """Update current control state and invoke state_callback."""
        self.current_state = state
        logger.debug("Control state -> %s (%s)", state.value, message)
        if self.state_callback:
            try:
                self.state_callback(state, message)
            except Exception as exc:
                logger.warning("Error in state callback: %s", exc)

    def execute(self, raw_command: str) -> CommandExecutionReport:
        """Execute a natural language voice command through the full control pipeline.

        Args:
            raw_command: Voice speech transcript or typed command string.

        Returns:
            CommandExecutionReport summarizing outcome of all steps.
        """
        start_time = time.perf_counter()
        clean_text = raw_command.strip()
        if not clean_text:
            return CommandExecutionReport(
                raw_command=raw_command,
                status="failed",
                error_message="Empty command received.",
                execution_time_ms=0.0,
            )

        # 1. State: PROCESSING (Local rule-based parsing)
        self._set_state(ControlState.PROCESSING, "Parsing command...")
        parsed_items = self.parser.parse(clean_text)

        if not parsed_items:
            err_msg = f"Could not parse any actionable commands from '{clean_text}'."
            self._set_state(ControlState.ERROR, err_msg)
            self._set_state(ControlState.READY)
            return self._record_and_return(
                CommandExecutionReport(
                    raw_command=clean_text,
                    status="failed",
                    error_message=err_msg,
                    execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
                )
            )

        # Check for any unsupported clauses
        actions: list[ActionRequest] = []
        for item in parsed_items:
            if isinstance(item, UnsupportedCommandResult):
                err_msg = f"Unsupported command clause: '{item.raw_command}' ({item.reason})"
                logger.warning(err_msg)
                self._set_state(ControlState.ERROR, err_msg)
                self._set_state(ControlState.READY)
                return self._record_and_return(
                    CommandExecutionReport(
                        raw_command=clean_text,
                        status="failed",
                        error_message=err_msg,
                        execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
                    )
                )
            actions.append(item)

        # 2. State: VALIDATING (Security and parameter constraints)
        self._set_state(ControlState.VALIDATING, "Validating action parameters...")
        for act in actions:
            try:
                self.validator.validate_action(act)
            except ActionValidationError as exc:
                err_msg = f"Validation failed for {act.action_type.value}: {exc}"
                logger.error(err_msg)
                self._set_state(ControlState.ERROR, err_msg)
                self._set_state(ControlState.READY)
                return self._record_and_return(
                    CommandExecutionReport(
                        raw_command=clean_text,
                        status="failed",
                        error_message=err_msg,
                        execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
                    )
                )

        # 3. Execution Loop with Confirmation
        step_reports: list[ActionStepReport] = []

        for i, act in enumerate(actions):
            # Check risk and confirmation requirement
            risk = self.risk_classifier.classify(act)
            needs_confirm = self.risk_classifier.requires_confirmation(
                act,
                confirm_medium=self.confirm_medium,
                confirm_high=self.confirm_high,
            )

            if needs_confirm:
                self._set_state(ControlState.CONFIRMING, f"Confirming {act.action_type.value}...")
                confirmed = False
                if self.confirm_handler:
                    try:
                        confirmed = self.confirm_handler(act)
                    except Exception as exc:
                        logger.error("Error during confirmation handler: %s", exc)
                        confirmed = False
                else:
                    logger.warning("Action '%s' requires confirmation but no confirm_handler registered.", act.action_type)
                    confirmed = False

                if not confirmed:
                    err_msg = f"Action '{act.action_type.value}' was rejected or cancelled by user."
                    logger.info(err_msg)
                    step_reports.append(
                        ActionStepReport(
                            action_type=act.action_type,
                            params=act.params,
                            risk_level=risk,
                            success=False,
                            error_message="User cancelled confirmation",
                        )
                    )
                    self._set_state(ControlState.READY)
                    return self._record_and_return(
                        CommandExecutionReport(
                            raw_command=clean_text,
                            status="cancelled",
                            steps=step_reports,
                            error_message=err_msg,
                            execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
                        )
                    )

                act.confirmed = True

            # 4. State: EXECUTING
            self._set_state(ControlState.EXECUTING, f"Executing {act.action_type.value}...")
            handler = self.registry.get(act.action_type)
            if not handler:
                err_msg = f"No handler registered for action type '{act.action_type.value}'"
                logger.error(err_msg)
                step_reports.append(
                    ActionStepReport(
                        action_type=act.action_type,
                        params=act.params,
                        risk_level=risk,
                        success=False,
                        error_message=err_msg,
                    )
                )
                self._set_state(ControlState.ERROR, err_msg)
                self._set_state(ControlState.READY)
                return self._record_and_return(
                    CommandExecutionReport(
                        raw_command=clean_text,
                        status="failed",
                        steps=step_reports,
                        error_message=err_msg,
                        execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
                    )
                )

            # Run action
            result: ActionResult = handler.run(act.params)
            step_reports.append(
                ActionStepReport(
                    action_type=act.action_type,
                    params=act.params,
                    risk_level=risk,
                    success=result.success,
                    output=result.output,
                    error_message=result.error_message,
                )
            )

            # Abort execution chain immediately on failure
            if not result.success:
                err_msg = f"Step {i + 1} ({act.action_type.value}) failed: {result.error_message}"
                logger.warning(err_msg)
                self._set_state(ControlState.ERROR, err_msg)
                self._set_state(ControlState.READY)
                return self._record_and_return(
                    CommandExecutionReport(
                        raw_command=clean_text,
                        status="failed",
                        steps=step_reports,
                        error_message=err_msg,
                        execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
                    )
                )

            # Pause briefly between chained commands
            if i < len(actions) - 1 and self.step_pause_seconds > 0:
                time.sleep(self.step_pause_seconds)

        # 5. State: RESULT
        self._set_state(ControlState.RESULT, "Command executed successfully")
        self._set_state(ControlState.READY)

        report = CommandExecutionReport(
            raw_command=clean_text,
            status="success",
            steps=step_reports,
            error_message=None,
            execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
        )
        return self._record_and_return(report)

    def _record_and_return(self, report: CommandExecutionReport) -> CommandExecutionReport:
        """Persist command report to history database if available and return report."""
        if self.database:
            try:
                processed_summary = "; ".join(
                    f"{s.action_type.value}({s.output or s.error_message or ''})"
                    for s in report.steps
                )
                entry = HistoryEntry(
                    mode="control",
                    raw_text=report.raw_command,
                    processed_text=processed_summary,
                    status=report.status,
                    details=report.to_dict(),
                )
                self.database.insert_history(entry)
            except Exception as exc:
                logger.error("Failed to record command report in database: %s", exc)

        return report


__all__ = [
    "ActionStepReport",
    "CommandExecutionReport",
    "CommandRouter",
]
