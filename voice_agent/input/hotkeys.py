"""Global keyboard hook manager and hotkey event router."""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Callable

from voice_agent.app.logging import get_logger
from voice_agent.input.gesture import GestureDetector, GestureMode

logger = get_logger("input.hotkeys")

try:
    from pynput import keyboard as pynput_keyboard  # type: ignore[import-untyped]
except ImportError:
    pynput_keyboard = None

# Windows Virtual Key Codes for modifiers
VK_LCONTROL = 0xA2  # 162
VK_RCONTROL = 0xA3  # 163
VK_LMENU = 0xA4     # 164 (Left Alt)
VK_RMENU = 0xA5     # 165 (Right Alt)


def normalize_key_name(key_name: str) -> str:
    """Normalize a user-configured hotkey string to its canonical identifier."""
    cleaned = key_name.lower().strip()
    cleaned = re.sub(r"[\s\-_]+", "_", cleaned)

    alias_map = {
        "right_ctrl": "ctrl_r",
        "r_ctrl": "ctrl_r",
        "rctrl": "ctrl_r",
        "ctrl_right": "ctrl_r",
        "control_r": "ctrl_r",
        "right_control": "ctrl_r",
        "left_ctrl": "ctrl_l",
        "l_ctrl": "ctrl_l",
        "lctrl": "ctrl_l",
        "ctrl_left": "ctrl_l",
        "control_l": "ctrl_l",
        "left_control": "ctrl_l",
        "right_alt": "alt_r",
        "r_alt": "alt_r",
        "ralt": "alt_r",
        "alt_right": "alt_r",
        "alt_gr": "alt_r",
        "altgr": "alt_r",
        "left_alt": "alt_l",
        "l_alt": "alt_l",
        "lalt": "alt_l",
        "alt_left": "alt_l",
        "caps": "caps_lock",
        "capslock": "caps_lock",
    }

    return alias_map.get(cleaned, cleaned)


def canonicalize_key(key: Any) -> str | None:
    """Extract canonical string name from a pynput key or virtual key code."""
    if key is None:
        return None

    # 1. pynput Key enum
    name = getattr(key, "name", None)
    if name:
        return normalize_key_name(name)

    # 2. Check virtual key code on Windows
    vk = getattr(key, "vk", None)
    if vk is not None:
        if vk == VK_RCONTROL:
            return "ctrl_r"
        if vk == VK_LCONTROL:
            return "ctrl_l"
        if vk == VK_RMENU:
            return "alt_r"
        if vk == VK_LMENU:
            return "alt_l"

    # 3. Char attribute
    char = getattr(key, "char", None)
    if char:
        return char.lower()

    # 4. Fallback string representation
    key_str = str(key).replace("Key.", "").lower()
    return normalize_key_name(key_str)


class HotkeyManager:
    """Manages global keyboard hooks, key-to-gesture routing, and runtime reconfiguration."""

    def __init__(
        self,
        dictation_hotkey: str = "ctrl_r",
        control_hotkey: str = "alt_r",
        dictation_mode: str = "both",
        control_mode: str = "both",
        tap_threshold: float = 0.3,
        on_dictation_start: Callable[[], None] | None = None,
        on_dictation_stop: Callable[[], None] | None = None,
        on_control_start: Callable[[], None] | None = None,
        on_control_stop: Callable[[], None] | None = None,
        listener_factory: Any = None,
    ) -> None:
        self.dictation_hotkey = normalize_key_name(dictation_hotkey)
        self.control_hotkey = normalize_key_name(control_hotkey)
        self.tap_threshold = tap_threshold

        self._user_on_dictation_start = on_dictation_start
        self._user_on_dictation_stop = on_dictation_stop
        self._user_on_control_start = on_control_start
        self._user_on_control_stop = on_control_stop

        self._lock = threading.RLock()
        self._is_running: bool = False
        self._listener: Any = None
        self._listener_factory = listener_factory

        # Initialize gesture detectors with mutual exclusion
        self.dictation_detector = GestureDetector(
            mode=dictation_mode,
            tap_threshold=tap_threshold,
            on_start=self._handle_dictation_start,
            on_stop=self._handle_dictation_stop,
        )

        self.control_detector = GestureDetector(
            mode=control_mode,
            tap_threshold=tap_threshold,
            on_start=self._handle_control_start,
            on_stop=self._handle_control_stop,
        )

    @property
    def is_running(self) -> bool:
        """Return True if hotkey hooks are currently monitoring events."""
        with self._lock:
            return self._is_running

    def _handle_dictation_start(self) -> None:
        # Enforce mode exclusivity: stop Control mode if running
        if self.control_detector.is_active:
            logger.debug("Control mode active when Dictation triggered; resetting Control.")
            self.control_detector.reset()
        if self._user_on_dictation_start:
            self._user_on_dictation_start()

    def _handle_dictation_stop(self) -> None:
        if self._user_on_dictation_stop:
            self._user_on_dictation_stop()

    def _handle_control_start(self) -> None:
        # Enforce mode exclusivity: stop Dictation mode if running
        if self.dictation_detector.is_active:
            logger.debug("Dictation mode active when Control triggered; resetting Dictation.")
            self.dictation_detector.reset()
        if self._user_on_control_start:
            self._user_on_control_start()

    def _handle_control_stop(self) -> None:
        if self._user_on_control_stop:
            self._user_on_control_stop()

    def reconfigure(
        self,
        dictation_hotkey: str | None = None,
        control_hotkey: str | None = None,
        dictation_mode: str | None = None,
        control_mode: str | None = None,
        tap_threshold: float | None = None,
    ) -> None:
        """Update hotkey bindings or modes at runtime without restarting."""
        with self._lock:
            if dictation_hotkey:
                self.dictation_hotkey = normalize_key_name(dictation_hotkey)
            if control_hotkey:
                self.control_hotkey = normalize_key_name(control_hotkey)
            if tap_threshold is not None:
                self.tap_threshold = tap_threshold
                self.dictation_detector.tap_threshold = tap_threshold
                self.control_detector.tap_threshold = tap_threshold
            if dictation_mode:
                self.dictation_detector.mode = GestureMode(dictation_mode)
            if control_mode:
                self.control_detector.mode = GestureMode(control_mode)

            logger.info(
                "HotkeyManager reconfigured: Dictation=(key=%s, mode=%s), Control=(key=%s, mode=%s)",
                self.dictation_hotkey,
                self.dictation_detector.mode.value,
                self.control_hotkey,
                self.control_detector.mode.value,
            )

    def start(self) -> None:
        """Start global keyboard listener."""
        with self._lock:
            if self._is_running:
                return

            factory = self._listener_factory or (
                pynput_keyboard.Listener if pynput_keyboard is not None else None
            )

            if factory is None:
                logger.warning(
                    "pynput is not installed and no listener factory provided. Simulated hotkeys only."
                )
                self._is_running = True
                return

            try:
                self._listener = factory(
                    on_press=self._on_press,
                    on_release=self._on_release,
                )
                self._listener.daemon = True
                self._listener.start()
                self._is_running = True
                logger.info(
                    "Global hotkey hooks active: Dictation=%s, Control=%s",
                    self.dictation_hotkey,
                    self.control_hotkey,
                )
            except Exception as e:
                logger.error("Failed to start global keyboard hook listener: %s", e)
                raise

    def stop(self) -> None:
        """Stop global keyboard listener and reset all detectors."""
        with self._lock:
            if not self._is_running:
                return

            self._is_running = False
            if self._listener is not None:
                try:
                    self._listener.stop()
                except Exception as e:
                    logger.debug("Error stopping listener: %s", e)
                self._listener = None

            self.dictation_detector.reset()
            self.control_detector.reset()
            logger.info("Global hotkey hooks stopped.")

    def _on_press(self, key: Any) -> None:
        """Internal callback for key press events."""
        canonical = canonicalize_key(key)
        if canonical is None:
            return

        self.simulate_press(canonical)

    def _on_release(self, key: Any) -> None:
        """Internal callback for key release events."""
        canonical = canonicalize_key(key)
        if canonical is None:
            return

        self.simulate_release(canonical)

    def simulate_press(self, key_str: str, timestamp: float | None = None) -> None:
        """Simulate a key press event (used directly in tests and event dispatching)."""
        normalized = normalize_key_name(key_str)
        if normalized == self.dictation_hotkey:
            self.dictation_detector.handle_key_down(timestamp)
        elif normalized == self.control_hotkey:
            self.control_detector.handle_key_down(timestamp)

    def simulate_release(self, key_str: str, timestamp: float | None = None) -> None:
        """Simulate a key release event (used directly in tests and event dispatching)."""
        normalized = normalize_key_name(key_str)
        if normalized == self.dictation_hotkey:
            self.dictation_detector.handle_key_up(timestamp)
        elif normalized == self.control_hotkey:
            self.control_detector.handle_key_up(timestamp)
