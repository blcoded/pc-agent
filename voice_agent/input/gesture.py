"""Gesture detection engine for discriminating tap (toggle) vs hold (push-to-talk)."""

from __future__ import annotations

from enum import Enum
import threading
import time
from typing import Callable

from voice_agent.app.logging import get_logger

logger = get_logger("input.gesture")


class GestureMode(str, Enum):
    """Operational mode for hotkey interaction."""

    PUSH_TO_TALK = "push_to_talk"
    TOGGLE = "toggle"
    BOTH = "both"


class GestureDetector:
    """Discriminates between quick key taps (toggle) and sustained holds (push-to-talk)."""

    def __init__(
        self,
        mode: str | GestureMode = GestureMode.BOTH,
        tap_threshold: float = 0.3,  # 300 ms threshold
        on_start: Callable[[], None] | None = None,
        on_stop: Callable[[], None] | None = None,
    ) -> None:
        self.mode = GestureMode(mode)
        self.tap_threshold = tap_threshold
        self.on_start = on_start
        self.on_stop = on_stop

        self._lock = threading.RLock()
        self._is_pressed: bool = False
        self._press_start_time: float = 0.0
        self._is_active: bool = False
        self._is_toggle_active: bool = False
        self._was_already_active_on_press: bool = False

    @property
    def is_active(self) -> bool:
        """Return True if the gesture is currently in an active listening state."""
        with self._lock:
            return self._is_active

    @property
    def is_pressed(self) -> bool:
        """Return True if the hotkey is physically pressed down."""
        with self._lock:
            return self._is_pressed

    def handle_key_down(self, timestamp: float | None = None) -> None:
        """Process a key down event."""
        with self._lock:
            if self._is_pressed:
                # Key repeat event from OS: ignore
                return

            now = timestamp if timestamp is not None else time.perf_counter()
            self._is_pressed = True
            self._press_start_time = now
            self._was_already_active_on_press = self._is_active

            logger.debug(
                "Gesture key down (mode=%s, currently_active=%s)",
                self.mode.value,
                self._is_active,
            )

            if self.mode == GestureMode.PUSH_TO_TALK:
                self._trigger_start()
            elif self.mode == GestureMode.BOTH:
                # In 'both' mode, start immediately for instant responsiveness
                if not self._is_active:
                    self._trigger_start()

    def handle_key_up(self, timestamp: float | None = None) -> None:
        """Process a key up event."""
        with self._lock:
            if not self._is_pressed:
                return

            now = timestamp if timestamp is not None else time.perf_counter()
            duration = now - self._press_start_time
            self._is_pressed = False

            logger.debug("Gesture key up: held for %.3fs (mode=%s)", duration, self.mode.value)

            if self.mode == GestureMode.PUSH_TO_TALK:
                self._trigger_stop()

            elif self.mode == GestureMode.TOGGLE:
                # Toggle on release
                if self._is_active:
                    self._trigger_stop()
                else:
                    self._trigger_start()

            elif self.mode == GestureMode.BOTH:
                if duration < self.tap_threshold:
                    # Key was tapped (< threshold)
                    if self._was_already_active_on_press:
                        # Tapped while active: turn OFF
                        logger.debug("Tap gesture detected while active -> stopping.")
                        self._trigger_stop()
                        self._is_toggle_active = False
                    else:
                        # Tapped while idle: turn ON and stay active
                        logger.debug("Tap gesture detected while idle -> locking toggle ON.")
                        self._is_toggle_active = True
                        if not self._is_active:
                            self._trigger_start()
                else:
                    # Key was held (>= threshold): Push-to-talk release
                    logger.debug("Hold gesture release detected -> stopping.")
                    self._trigger_stop()
                    self._is_toggle_active = False

    def reset(self) -> None:
        """Reset state and stop listening if active."""
        with self._lock:
            self._is_pressed = False
            self._is_toggle_active = False
            self._was_already_active_on_press = False
            if self._is_active:
                self._trigger_stop()

    def _trigger_start(self) -> None:
        if not self._is_active:
            self._is_active = True
            if self.on_start:
                try:
                    self.on_start()
                except Exception as e:
                    logger.error("Error in on_start callback: %s", e)

    def _trigger_stop(self) -> None:
        if self._is_active:
            self._is_active = False
            if self.on_stop:
                try:
                    self.on_stop()
                except Exception as e:
                    logger.error("Error in on_stop callback: %s", e)
