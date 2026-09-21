"""Unit tests for FloatingStatusOverlay widget and visual state representation."""

import unittest

from voice_agent.app.config import AppConfig
from voice_agent.app.lifecycle import ControlState, DictationState
from voice_agent.ui.overlay import (
    OVERLAY_HEIGHT,
    OVERLAY_WIDTH,
    STATE_STYLES,
    FloatingStatusOverlay,
)


class TestFloatingStatusOverlay(unittest.TestCase):
    """Test suite for overlay state transitions, audio levels, and position persistence."""

    def setUp(self) -> None:
        self.config = AppConfig()

    def test_dimensions_and_initial_state(self) -> None:
        """Verify default pill size and ready state."""
        overlay = FloatingStatusOverlay(config=self.config)
        self.assertEqual(overlay.width(), OVERLAY_WIDTH)
        self.assertEqual(overlay.height(), OVERLAY_HEIGHT)
        self.assertEqual(overlay.status_text, "Ready")
        self.assertEqual(overlay.current_mode, "dictation")

    def test_dictation_state_transitions(self) -> None:
        """Verify all DictationState enum transitions update status label."""
        overlay = FloatingStatusOverlay(config=self.config)

        overlay.set_dictation_state(DictationState.LISTENING)
        self.assertEqual(overlay.status_text, "Listening...")
        self.assertEqual(overlay.current_mode, "dictation")

        overlay.set_dictation_state(DictationState.PROCESSING)
        self.assertEqual(overlay.status_text, "Processing...")

        overlay.set_dictation_state(DictationState.TYPING)
        self.assertEqual(overlay.status_text, "Typing...")

        overlay.set_dictation_state(DictationState.NO_TARGET)
        self.assertEqual(overlay.status_text, "No Text Target")

        overlay.set_dictation_state(DictationState.ERROR)
        self.assertEqual(overlay.status_text, "Error")

        overlay.set_dictation_state(DictationState.READY)
        self.assertEqual(overlay.status_text, "Ready")

    def test_control_state_transitions(self) -> None:
        """Verify all ControlState enum transitions update status label."""
        overlay = FloatingStatusOverlay(config=self.config)

        overlay.set_control_state(ControlState.LISTENING)
        self.assertEqual(overlay.status_text, "Listening (Control)...")
        self.assertEqual(overlay.current_mode, "control")

        overlay.set_control_state(ControlState.CONFIRMING)
        self.assertEqual(overlay.status_text, "Confirm Action?")

        overlay.set_control_state(ControlState.EXECUTING)
        self.assertEqual(overlay.status_text, "Executing...")

        overlay.set_control_state(ControlState.RESULT)
        self.assertEqual(overlay.status_text, "Action Completed")

        overlay.set_control_state(ControlState.ERROR)
        self.assertEqual(overlay.status_text, "Action Failed")

    def test_audio_level_clamping(self) -> None:
        """Verify audio meter levels are clamped to [0.0, 1.0]."""
        overlay = FloatingStatusOverlay(config=self.config)

        overlay.set_audio_level(0.65)
        self.assertAlmostEqual(overlay.audio_level, 0.65, places=3)

        overlay.set_audio_level(1.5)
        self.assertEqual(overlay.audio_level, 1.0)

        overlay.set_audio_level(-0.25)
        self.assertEqual(overlay.audio_level, 0.0)

    def test_position_restoration_and_saving(self) -> None:
        """Verify overlay restores coordinates from config and saves new positions."""
        self.config.ui.overlay_x = 450
        self.config.ui.overlay_y = 300

        overlay = FloatingStatusOverlay(config=self.config)
        self.assertEqual(overlay.x(), 450)
        self.assertEqual(overlay.y(), 300)

        # Move to new position
        overlay.move(600, 400)
        self.assertEqual(overlay.x(), 600)
        self.assertEqual(overlay.y(), 400)

        overlay.save_current_position()
        self.assertEqual(self.config.ui.overlay_x, 600)
        self.assertEqual(self.config.ui.overlay_y, 400)


if __name__ == "__main__":
    unittest.main()
