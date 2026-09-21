"""Base Action Interface and Core Models for PC Voice Agent.

This module defines the abstract `Action` base class that all concrete control
actions (application, mouse, keyboard, web, filesystem, etc.) implement.
"""

from __future__ import annotations

import abc
import logging
from typing import Any

from voice_agent.control.models import (
    ActionError,
    ActionExecutionError,
    ActionRequest,
    ActionResult,
    ActionType,
    ActionValidationError,
    RiskLevel,
)

logger = logging.getLogger(__name__)


class Action(abc.ABC):
    """Abstract base class for all executable control actions."""

    @property
    @abc.abstractmethod
    def action_type(self) -> ActionType:
        """The ActionType enum value corresponding to this action."""
        raise NotImplementedError

    def validate(self, params: dict[str, Any]) -> bool:
        """Validate the incoming action parameters.

        Subclasses should override this method to perform parameter presence,
        type, and security checks.

        Args:
            params: Dictionary of parameters for the action.

        Returns:
            bool: True if parameters are valid.

        Raises:
            ActionValidationError: If parameters are invalid or missing.
        """
        return True

    @abc.abstractmethod
    def execute(self, params: dict[str, Any]) -> ActionResult:
        """Execute the action with the given parameters.

        Args:
            params: Dictionary of validated parameters.

        Returns:
            ActionResult containing success status, output, and error message.

        Raises:
            ActionExecutionError: If action execution fails fundamentally.
        """
        raise NotImplementedError

    def run(self, params: dict[str, Any]) -> ActionResult:
        """Safely validate and execute the action, catching errors.

        Args:
            params: Dictionary of parameters.

        Returns:
            ActionResult: Result of the action execution.
        """
        try:
            self.validate(params)
            return self.execute(params)
        except ActionValidationError as exc:
            logger.warning("Action validation failed for %s: %s", self.action_type.value, exc)
            return ActionResult(success=False, output=None, error_message=f"Validation failed: {exc}")
        except ActionExecutionError as exc:
            logger.error("Action execution error for %s: %s", self.action_type.value, exc)
            return ActionResult(success=False, output=None, error_message=f"Execution error: {exc}")
        except Exception as exc:
            logger.exception("Unexpected exception executing %s: %s", self.action_type.value, exc)
            return ActionResult(success=False, output=None, error_message=f"Unexpected error ({type(exc).__name__}): {exc}")


__all__ = [
    "Action",
    "ActionError",
    "ActionExecutionError",
    "ActionRequest",
    "ActionResult",
    "ActionType",
    "ActionValidationError",
    "RiskLevel",
]
