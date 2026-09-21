"""Unit tests for HotkeyManager and GestureDetector (tap vs hold)."""

from types import SimpleNamespace
from typing import Any
import unittest
from unittest.mock import MagicMock

from voice_agent.input.gesture import GestureDetector, GestureMode
from voice_agent.input.hotkeys import (
    HotkeyManager,
    canonicalize_key,
    normalize_key_name,
)


class MockPynputListener:
    """Mock keyboard listener simulating pynput background listener."""

    def __init__(self, on_press: Any, on_release: Any) -> None:
        self.on_press = on_press
        self.on_release = on_release
        self.daemon = True
        self.is_running = False

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False


class TestHotkeyNormalization(unittest.TestCase):
    """Test suite for hotkey string normalization and canonicalization."""

    def test_normalize_key_name(self) -> None:
        """Verify various user aliases normalize to canonical form."""
        self.assertEqual(normalize_key_name("Right Ctrl"), "ctrl_r")
        self.assertEqual(normalize_key_name("r_ctrl"), "ctrl_r")
        self.assertEqual(normalize_key_name("rctrl"), "ctrl_r")
        self.assertEqual(normalize_key_name("Right Alt"), "alt_r")
        self.assertEqual(normalize_key_name("alt_gr"), "alt_r")
        self.assertEqual(normalize_key_name("capslock"), "caps_lock")
        self.assertEqual(normalize_key_name("F9"), "f9")

    def test_canonicalize_key_objects(self) -> None:
        """Verify pynput-style Key objects and Windows VK codes canonicalize properly."""
        # Key with name attribute
        key_rctrl = SimpleNamespace(name="ctrl_r")
        self.assertEqual(canonicalize_key(key_rctrl), "ctrl_r")

        # Windows Virtual Key Code 163 (VK_RCONTROL)
        key_vk_rctrl = SimpleNamespace(vk=163)
        self.assertEqual(canonicalize_key(key_vk_rctrl), "ctrl_r")

        # Windows Virtual Key Code 165 (VK_RMENU / Right Alt)
        key_vk_ralt = SimpleNamespace(vk=165)
        self.assertEqual(canonicalize_key(key_vk_ralt), "alt_r")

        # Char key
        key_char = SimpleNamespace(char="K")
        self.assertEqual(canonicalize_key(key_char), "k")


class TestGestureDetector(unittest.TestCase):
    """Test suite for tap vs. hold detection logic across operational modes."""

    def test_push_to_talk_mode(self) -> None:
        """Verify push-to-talk starts on down and stops immediately on up."""
        starts = []
        stops = []
        detector = GestureDetector(
            mode=GestureMode.PUSH_TO_TALK,
            on_start=lambda: starts.append(True),
            on_stop=lambda: stops.append(True),
        )

        detector.handle_key_down(timestamp=10.0)
        self.assertTrue(detector.is_active)
        self.assertEqual(len(starts), 1)
        self.assertEqual(len(stops), 0)

        detector.handle_key_up(timestamp=10.5)
        self.assertFalse(detector.is_active)
        self.assertEqual(len(starts), 1)
        self.assertEqual(len(stops), 1)

    def test_toggle_mode(self) -> None:
        """Verify toggle mode alternates start and stop on key release."""
        starts = []
        stops = []
        detector = GestureDetector(
            mode=GestureMode.TOGGLE,
            on_start=lambda: starts.append(True),
            on_stop=lambda: stops.append(True),
        )

        # First tap (down + up) -> start
        detector.handle_key_down(timestamp=10.0)
        detector.handle_key_up(timestamp=10.1)
        self.assertTrue(detector.is_active)
        self.assertEqual(len(starts), 1)
        self.assertEqual(len(stops), 0)

        # Second tap (down + up) -> stop
        detector.handle_key_down(timestamp=11.0)
        detector.handle_key_up(timestamp=11.1)
        self.assertFalse(detector.is_active)
        self.assertEqual(len(starts), 1)
        self.assertEqual(len(stops), 1)

    def test_both_mode_tap_locks_on_and_second_tap_stops(self) -> None:
        """In 'both' mode, quick tap (<300ms) while idle toggles ON; subsequent tap toggles OFF."""
        starts = []
        stops = []
        detector = GestureDetector(
            mode=GestureMode.BOTH,
            tap_threshold=0.3,
            on_start=lambda: starts.append(True),
            on_stop=lambda: stops.append(True),
        )

        # Tap 1: duration 0.1s (< 0.3s threshold)
        detector.handle_key_down(timestamp=1.0)
        detector.handle_key_up(timestamp=1.1)
        self.assertTrue(detector.is_active)
        self.assertEqual(len(starts), 1)
        self.assertEqual(len(stops), 0)

        # Tap 2: duration 0.1s while active -> should turn OFF
        detector.handle_key_down(timestamp=2.0)
        detector.handle_key_up(timestamp=2.1)
        self.assertFalse(detector.is_active)
        self.assertEqual(len(starts), 1)
        self.assertEqual(len(stops), 1)

    def test_both_mode_hold_acts_as_push_to_talk(self) -> None:
        """In 'both' mode, holding key past threshold (0.5s >= 0.3s) releases on key up."""
        starts = []
        stops = []
        detector = GestureDetector(
            mode=GestureMode.BOTH,
            tap_threshold=0.3,
            on_start=lambda: starts.append(True),
            on_stop=lambda: stops.append(True),
        )

        # Hold for 0.5s
        detector.handle_key_down(timestamp=1.0)
        self.assertTrue(detector.is_active)
        self.assertEqual(len(starts), 1)

        detector.handle_key_up(timestamp=1.5)
        self.assertFalse(detector.is_active)
        self.assertEqual(len(stops), 1)


class TestHotkeyManager(unittest.TestCase):
    """Test suite for HotkeyManager routing, mutual exclusion, and reconfiguration."""

    def test_mutual_exclusion_between_modes(self) -> None:
        """Triggering Control while Dictation is active must reset Dictation."""
        dictation_events = []
        control_events = []

        manager = HotkeyManager(
            dictation_hotkey="ctrl_r",
            control_hotkey="alt_r",
            on_dictation_start=lambda: dictation_events.append("start"),
            on_dictation_stop=lambda: dictation_events.append("stop"),
            on_control_start=lambda: control_events.append("start"),
            on_control_stop=lambda: control_events.append("stop"),
        )

        # Tap Dictation hotkey -> Dictation active
        manager.simulate_press("ctrl_r", timestamp=1.0)
        manager.simulate_release("ctrl_r", timestamp=1.1)
        self.assertTrue(manager.dictation_detector.is_active)
        self.assertFalse(manager.control_detector.is_active)
        self.assertEqual(dictation_events, ["start"])

        # Tap Control hotkey -> Dictation must be reset, Control must start
        manager.simulate_press("alt_r", timestamp=2.0)
        self.assertFalse(manager.dictation_detector.is_active)
        self.assertTrue(manager.control_detector.is_active)
        self.assertIn("stop", dictation_events)
        self.assertEqual(control_events, ["start"])

    def test_runtime_reconfiguration(self) -> None:
        """Verify updating hotkeys switches which keys trigger gestures."""
        starts = []
        manager = HotkeyManager(
            dictation_hotkey="ctrl_r",
            on_dictation_start=lambda: starts.append(True),
        )

        # Press old hotkey
        manager.simulate_press("ctrl_r", timestamp=1.0)
        self.assertEqual(len(starts), 1)
        manager.simulate_release("ctrl_r", timestamp=1.5)

        # Reconfigure to F8
        manager.reconfigure(dictation_hotkey="f8")

        # Press old hotkey -> should do nothing
        manager.simulate_press("ctrl_r", timestamp=2.0)
        self.assertEqual(len(starts), 1)

        # Press new hotkey F8 -> triggers start
        manager.simulate_press("f8", timestamp=3.0)
        self.assertEqual(len(starts), 2)

    def test_listener_lifecycle(self) -> None:
        """Verify listener start and stop."""
        manager = HotkeyManager(listener_factory=MockPynputListener)
        manager.start()
        self.assertTrue(manager.is_running)

        manager.stop()
        self.assertFalse(manager.is_running)


if __name__ == "__main__":
    unittest.main()
