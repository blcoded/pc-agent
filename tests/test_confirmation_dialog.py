import os
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
try:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
except ImportError:
    app = None

from voice_agent.control.models import ActionRequest, ActionType, RiskLevel
from voice_agent.ui.confirmation import RiskConfirmationDialog, request_user_confirmation



class TestRiskConfirmationDialog(unittest.TestCase):
    """Test suite for RiskConfirmationDialog interaction, styles, and timeout."""

    def setUp(self) -> None:
        self.del_action = ActionRequest(
            action_type=ActionType.DELETE_FILE,
            params={"path": "C:\\temp\\report.docx"},
            risk_level=RiskLevel.HIGH,
            raw_command="delete file report.docx",
        )
        self.close_action = ActionRequest(
            action_type=ActionType.CLOSE_APP,
            params={"target": "Notepad"},
            risk_level=RiskLevel.MEDIUM,
            raw_command="close notepad",
        )

    def test_high_risk_styling_and_properties(self) -> None:
        """Verify high-risk styling and labels."""
        dialog = RiskConfirmationDialog(
            action=self.del_action,
            prompt="Delete 'report.docx'?",
            timeout_seconds=20,
        )
        self.assertEqual(dialog.risk_level, RiskLevel.HIGH)
        self.assertIn("HIGH RISK", dialog.header_title)
        self.assertEqual(dialog.primary_color, "#D32F2F")
        self.assertEqual(dialog.prompt, "Delete 'report.docx'?")
        self.assertEqual(dialog.remaining_seconds, 20)
        self.assertFalse(dialog.is_confirmed)

    def test_medium_risk_styling(self) -> None:
        """Verify medium-risk styling."""
        dialog = RiskConfirmationDialog(
            action=self.close_action,
            prompt="Close application 'Notepad'?",
        )
        self.assertEqual(dialog.risk_level, RiskLevel.MEDIUM)
        self.assertIn("MEDIUM RISK", dialog.header_title)
        self.assertEqual(dialog.primary_color, "#F57C00")

    def test_user_confirmation_flow(self) -> None:
        """Verify user clicking confirm accepts dialog and marks action confirmed."""
        dialog = RiskConfirmationDialog(action=self.del_action)
        self.assertFalse(self.del_action.confirmed)
        self.assertFalse(dialog.is_confirmed)

        dialog.on_confirm()
        self.assertTrue(dialog.is_confirmed)
        self.assertTrue(self.del_action.confirmed)
        self.assertEqual(dialog.result(), dialog.Accepted)

    def test_user_cancellation_flow(self) -> None:
        """Verify user clicking cancel rejects dialog."""
        dialog = RiskConfirmationDialog(action=self.del_action)
        dialog.on_cancel()
        self.assertFalse(dialog.is_confirmed)
        self.assertFalse(self.del_action.confirmed)
        self.assertEqual(dialog.result(), dialog.Rejected)

    def test_timeout_countdown_and_cancellation(self) -> None:
        """Verify unattended timer tick countdown and automatic cancellation."""
        dialog = RiskConfirmationDialog(action=self.del_action, timeout_seconds=3)
        self.assertEqual(dialog.remaining_seconds, 3)

        # Tick 1
        dialog._on_timer_tick()
        self.assertEqual(dialog.remaining_seconds, 2)
        self.assertFalse(dialog.is_confirmed)

        # Tick 2
        dialog._on_timer_tick()
        self.assertEqual(dialog.remaining_seconds, 1)

        # Tick 3: reaches 0 -> auto timeout
        dialog._on_timer_tick()
        self.assertEqual(dialog.remaining_seconds, 0)
        self.assertFalse(dialog.is_confirmed)
        self.assertFalse(self.del_action.confirmed)
        self.assertEqual(dialog.result(), dialog.Rejected)

    def test_request_user_confirmation_helper(self) -> None:
        """Verify the request_user_confirmation convenience helper."""
        action = ActionRequest(
            action_type=ActionType.DELETE_FILE,
            params={"path": "file.txt"},
            risk_level=RiskLevel.HIGH,
        )

        with patch.object(RiskConfirmationDialog, "exec") as mock_exec:
            # Simulate rejection
            mock_exec.return_value = 0
            res = request_user_confirmation(action)
            self.assertFalse(res)

            # Simulate acceptance
            def mock_accept(self_dialog: RiskConfirmationDialog) -> int:
                self_dialog._confirmed = True
                return self_dialog.Accepted

            mock_exec.side_effect = lambda: 1
            with patch.object(RiskConfirmationDialog, "is_confirmed", True):
                res2 = request_user_confirmation(action)
                self.assertTrue(res2)


if __name__ == "__main__":
    unittest.main()
