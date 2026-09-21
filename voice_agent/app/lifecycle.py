"""Application lifecycle, single-instance management, and service coordination."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import ctypes
from enum import Enum
import logging
import os
from pathlib import Path
import signal
import sys
from typing import Any, Callable

from voice_agent.app.config import AppConfig, load_config
from voice_agent.app.logging import get_logger, setup_logging
from voice_agent.storage.database import DatabaseManager

logger = get_logger("lifecycle")

# Windows API error code for already existing named object
ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Local\\PCVoiceAgent_SingleInstance_Mutex"


class SingleInstanceLock:
    """Windows-native mutex to enforce a single running application instance."""

    def __init__(self, mutex_name: str = MUTEX_NAME) -> None:
        self.mutex_name = mutex_name
        self.mutex_handle: int | None = None
        self.is_already_running: bool = False

    def acquire(self) -> bool:
        """Attempt to acquire the named Windows mutex.

        Returns:
            True if this instance successfully acquired the lock; False if another instance exists.
        """
        if sys.platform != "win32":
            # For non-Windows environments (e.g. CI testing), bypass named mutex
            return True

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.CreateMutexW(None, False, self.mutex_name)
        last_error = kernel32.GetLastError()

        if last_error == ERROR_ALREADY_EXISTS:
            self.is_already_running = True
            logger.warning("Another instance of PC Voice Agent is already running.")
            if handle:
                kernel32.CloseHandle(handle)
            self.mutex_handle = None
            return False

        self.mutex_handle = handle
        self.is_already_running = False
        return True

    def release(self) -> None:
        """Release and close the named mutex handle."""
        if self.mutex_handle and sys.platform == "win32":
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.CloseHandle(self.mutex_handle)
            self.mutex_handle = None


class DictationState(Enum):
    """Lifecycle states for Dictation Mode."""

    READY = "ready"
    LISTENING = "listening"
    PROCESSING = "processing"
    TYPING = "typing"
    NO_TARGET = "no_target"
    ERROR = "error"


class ControlState(Enum):
    """Lifecycle states for Control Mode."""

    READY = "ready"
    LISTENING = "listening"
    PROCESSING = "processing"
    VALIDATING = "validating"
    CONFIRMING = "confirming"
    EXECUTING = "executing"
    RESULT = "result"
    ERROR = "error"


class ApplicationLifecycle:
    """Coordinates central state, services, thread pool, and graceful shutdown."""

    def __init__(
        self,
        config: AppConfig | None = None,
        db: DatabaseManager | None = None,
        enable_logging: bool = True,
    ) -> None:
        self.instance_lock = SingleInstanceLock()
        self.config: AppConfig = config or load_config()
        if enable_logging:
            setup_logging()

        self.db: DatabaseManager = db or DatabaseManager()
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="voice_agent_worker")
        self.is_shutting_down: bool = False

        # State tracking
        self.dictation_state = DictationState.READY
        self.control_state = ControlState.READY

        # Subscribers for state change events
        self._dictation_subscribers: list[Callable[[DictationState], None]] = []
        self._control_subscribers: list[Callable[[ControlState], None]] = []
        self._shutdown_hooks: list[Callable[[], None]] = []

        self._setup_signals()

    def _setup_signals(self) -> None:
        """Register OS signal handlers for graceful termination."""
        try:
            signal.signal(signal.SIGINT, lambda sig, frame: self.shutdown())
            signal.signal(signal.SIGTERM, lambda sig, frame: self.shutdown())
        except (ValueError, AttributeError):
            # Not in main thread or platform unsupported
            pass

    def add_shutdown_hook(self, hook: Callable[[], None]) -> None:
        """Register a callback to be invoked upon application shutdown."""
        self._shutdown_hooks.append(hook)

    def subscribe_dictation_state(self, callback: Callable[[DictationState], None]) -> None:
        """Subscribe to Dictation state transitions."""
        self._dictation_subscribers.append(callback)

    def subscribe_control_state(self, callback: Callable[[ControlState], None]) -> None:
        """Subscribe to Control state transitions."""
        self._control_subscribers.append(callback)

    def set_dictation_state(self, new_state: DictationState) -> None:
        """Transition Dictation state and notify observers."""
        if self.dictation_state != new_state:
            self.dictation_state = new_state
            logger.debug("DictationState transition -> %s", new_state.value)
            for subscriber in self._dictation_subscribers:
                try:
                    subscriber(new_state)
                except Exception as e:
                    logger.error("Error notifying dictation subscriber: %s", e)

    def set_control_state(self, new_state: ControlState) -> None:
        """Transition Control state and notify observers."""
        if self.control_state != new_state:
            self.control_state = new_state
            logger.debug("ControlState transition -> %s", new_state.value)
            for subscriber in self._control_subscribers:
                try:
                    subscriber(new_state)
                except Exception as e:
                    logger.error("Error notifying control subscriber: %s", e)

    def run_async(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Submit a task to the background worker thread pool."""
        if not self.is_shutting_down:
            self.executor.submit(fn, *args, **kwargs)

    def shutdown(self) -> None:
        """Perform orderly, graceful shutdown of all active services."""
        if self.is_shutting_down:
            return

        self.is_shutting_down = True
        logger.info("Initiating graceful application shutdown...")

        # 1. Execute registered shutdown hooks (e.g. stop hotkey listeners, stop recorders)
        for hook in reversed(self._shutdown_hooks):
            try:
                hook()
            except Exception as e:
                logger.error("Error executing shutdown hook: %s", e)

        # 2. Terminate background worker threads
        self.executor.shutdown(wait=True, cancel_futures=True)

        # 3. Close database connection
        self.db.close()

        # 4. Release single-instance mutex
        self.instance_lock.release()

        logger.info("Application shutdown complete.")
