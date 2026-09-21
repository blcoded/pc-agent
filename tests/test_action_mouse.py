"""Unit tests for Mouse Movement and Click Actions (TASK-6.3)."""

import unittest

from voice_agent.control.actions.mouse import (
    ClickAction,
    MoveMouseAction,
    NativeWin32MouseBackend,
    SimulatedMouseBackend,
)
from voice_agent.control.models import ActionType


class TestActionMouse(unittest.TestCase):
    """Test suite for ClickAction and MoveMouseAction."""

    def setUp(self) -> None:
        self.backend = SimulatedMouseBackend(screen_bounds=(1920, 1080))
        # Initial position is (960, 540)
        self.assertEqual(self.backend.get_position(), (960, 540))

    def test_click_action_success(self) -> None:
        """Test left, right, middle, and double clicks."""
        action = ClickAction(backend=self.backend)
        self.assertEqual(action.action_type, ActionType.CLICK)

        # Single left click (default)
        res_left = action.run({})
        self.assertTrue(res_left.success)
        self.assertEqual(res_left.output["button"], "left")
        self.assertEqual(res_left.output["click_count"], 1)

        # Double click
        res_double = action.run({"button": "left", "click_count": 2})
        self.assertTrue(res_double.success)
        self.assertEqual(res_double.output["click_count"], 2)

        # Right click
        res_right = action.run({"button": "right"})
        self.assertTrue(res_right.success)
        self.assertEqual(res_right.output["button"], "right")

        # Middle click
        res_mid = action.run({"button": "middle"})
        self.assertTrue(res_mid.success)
        self.assertEqual(res_mid.output["button"], "middle")

        self.assertEqual(len(self.backend.click_history), 4)

    def test_click_action_validation_failure(self) -> None:
        """Test validation failure for invalid button or click count."""
        action = ClickAction(backend=self.backend)

        # Invalid button
        res_bad_btn = action.run({"button": "extra_button"})
        self.assertFalse(res_bad_btn.success)
        self.assertIn("Validation failed", res_bad_btn.error_message or "")

        # Invalid count
        res_bad_count = action.run({"click_count": 0})
        self.assertFalse(res_bad_count.success)

        res_bad_count_max = action.run({"click_count": 999})
        self.assertFalse(res_bad_count_max.success)

    def test_move_mouse_absolute(self) -> None:
        """Test absolute mouse movement."""
        action = MoveMouseAction(backend=self.backend)
        self.assertEqual(action.action_type, ActionType.MOVE_MOUSE)

        result = action.run({"mode": "absolute", "x": 400, "y": 300})
        self.assertTrue(result.success)
        self.assertEqual(result.output["final_position"], (400, 300))
        self.assertEqual(self.backend.get_position(), (400, 300))

    def test_move_mouse_relative(self) -> None:
        """Test relative cursor movement."""
        action = MoveMouseAction(backend=self.backend)
        self.backend.set_position(500, 500)

        # Move right by 100
        res_right = action.run({"mode": "relative", "direction": "right", "distance": 100})
        self.assertTrue(res_right.success)
        self.assertEqual(self.backend.get_position(), (600, 500))

        # Move up by 50
        res_up = action.run({"mode": "relative", "direction": "up", "distance": 50})
        self.assertTrue(res_up.success)
        self.assertEqual(self.backend.get_position(), (600, 450))

        # Move down by 20
        res_down = action.run({"mode": "relative", "direction": "down", "distance": 20})
        self.assertTrue(res_down.success)
        self.assertEqual(self.backend.get_position(), (600, 470))

        # Move left by 80
        res_left = action.run({"mode": "relative", "direction": "left", "distance": 80})
        self.assertTrue(res_left.success)
        self.assertEqual(self.backend.get_position(), (520, 470))

    def test_move_mouse_boundary_clamping(self) -> None:
        """Verify cursor coordinates are clamped to stay within desktop boundaries."""
        action = MoveMouseAction(backend=self.backend)

        # Move beyond right and bottom screen bounds (1920 x 1080)
        res_oob = action.run({"mode": "absolute", "x": 3000, "y": 2500})
        self.assertTrue(res_oob.success)
        # Should be clamped to (1919, 1079)
        self.assertEqual(self.backend.get_position(), (1919, 1079))

        # Move beyond top/left bounds
        res_neg = action.run({"mode": "relative", "direction": "up", "distance": 5000})
        self.assertTrue(res_neg.success)
        self.assertEqual(self.backend.get_position(), (1919, 0))

    def test_move_mouse_validation_failure(self) -> None:
        """Test move mouse validation failures."""
        action = MoveMouseAction(backend=self.backend)

        # Absolute without x or y
        res_abs_no_y = action.run({"mode": "absolute", "x": 100})
        self.assertFalse(res_abs_no_y.success)

        # Invalid mode
        res_bad_mode = action.run({"mode": "diagonal"})
        self.assertFalse(res_bad_mode.success)

        # Invalid direction
        res_bad_dir = action.run({"mode": "relative", "direction": "forward"})
        self.assertFalse(res_bad_dir.success)

    def test_native_backend_instantiation(self) -> None:
        """Test NativeWin32MouseBackend initialization on Windows."""
        native = NativeWin32MouseBackend()
        bounds = native.get_screen_bounds()
        self.assertEqual(len(bounds), 2)
        self.assertGreater(bounds[0], 0)
        self.assertGreater(bounds[1], 0)


if __name__ == "__main__":
    unittest.main()
