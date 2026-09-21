"""Unit tests for Risk Classification Engine (TASK-5.4)."""

import unittest

from voice_agent.control.models import (
    ActionRequest,
    ActionType,
    RiskLevel,
)
from voice_agent.control.risk import RiskClassifier


class TestRiskClassifier(unittest.TestCase):
    """Test suite for action risk classification and confirmation rules."""

    def setUp(self) -> None:
        self.classifier = RiskClassifier()

    def test_low_risk_classification(self) -> None:
        """Test actions that must be classified as Low risk."""
        low_actions = [
            ActionRequest(action_type=ActionType.OPEN_APP, params={"app_name": "notepad"}),
            ActionRequest(action_type=ActionType.OPEN_URL, params={"url": "https://google.com"}),
            ActionRequest(action_type=ActionType.SWITCH_WINDOW, params={"window_name": "chrome"}),
            ActionRequest(action_type=ActionType.TYPE_TEXT, params={"text": "Hello"}),
            ActionRequest(action_type=ActionType.PRESS_KEY, params={"key": "enter"}),
            ActionRequest(action_type=ActionType.MOVE_MOUSE, params={"x": 100, "y": 100}),
            ActionRequest(action_type=ActionType.CLICK, params={"button": "left"}),
            ActionRequest(action_type=ActionType.SEARCH_WEB, params={"query": "python"}),
            ActionRequest(action_type=ActionType.COPY, params={}),
            ActionRequest(action_type=ActionType.PASTE, params={}),
            ActionRequest(action_type=ActionType.READ_CLIPBOARD, params={}),
            ActionRequest(action_type=ActionType.OPEN_FILE, params={"path": "doc.txt"}),
            ActionRequest(action_type=ActionType.OPEN_FOLDER, params={"path": "C:\\"}),
            ActionRequest(action_type=ActionType.HOTKEY, params={"keys": ["ctrl", "c"]}),
            ActionRequest(action_type=ActionType.HOTKEY, params={"hotkey": "alt tab"}),
        ]

        for act in low_actions:
            self.assertEqual(
                self.classifier.classify(act),
                RiskLevel.LOW,
                f"Action {act.action_type} should be classified as LOW risk",
            )
            self.assertFalse(self.classifier.requires_confirmation(act))

    def test_medium_risk_classification(self) -> None:
        """Test actions that must be classified as Medium risk."""
        med_actions = [
            ActionRequest(action_type=ActionType.CLOSE_APP, params={"target": "notepad"}),
            ActionRequest(action_type=ActionType.MOVE_FILE, params={"source": "a.txt", "destination": "b.txt"}),
            ActionRequest(action_type=ActionType.RENAME_FILE, params={"source": "old.txt", "destination": "new.txt"}),
            ActionRequest(action_type=ActionType.HOTKEY, params={"keys": ["alt", "f4"]}),
            ActionRequest(action_type=ActionType.HOTKEY, params={"hotkey": "ctrl+w"}),
        ]

        for act in med_actions:
            self.assertEqual(
                self.classifier.classify(act),
                RiskLevel.MEDIUM,
                f"Action {act.action_type} should be classified as MEDIUM risk",
            )
            # Default: confirm_medium is False
            self.assertFalse(self.classifier.requires_confirmation(act, confirm_medium=False))
            # If confirm_medium is True
            self.assertTrue(self.classifier.requires_confirmation(act, confirm_medium=True))

    def test_high_risk_classification(self) -> None:
        """Test actions that must be classified as High risk."""
        del_act = ActionRequest(
            action_type=ActionType.DELETE_FILE,
            params={"path": "C:\\Users\\User\\Documents\\report.docx"},
        )
        self.assertEqual(self.classifier.classify(del_act), RiskLevel.HIGH)

        # High risk requires confirmation by default
        self.assertTrue(self.classifier.requires_confirmation(del_act, confirm_high=True))

        # If already confirmed
        del_act.confirmed = True
        self.assertFalse(self.classifier.requires_confirmation(del_act, confirm_high=True))

    def test_existing_high_risk_preservation(self) -> None:
        """Ensure an action already flagged as HIGH risk is never downgraded."""
        act = ActionRequest(
            action_type=ActionType.OPEN_APP,
            params={"app_name": "danger.exe"},
            risk_level=RiskLevel.HIGH,
        )
        self.assertEqual(self.classifier.classify(act), RiskLevel.HIGH)

    def test_confirmation_prompts(self) -> None:
        """Test human-readable confirmation message formatting."""
        del_act = ActionRequest(
            action_type=ActionType.DELETE_FILE,
            params={"path": "C:\\Users\\User\\Documents\\report.docx"},
        )
        self.assertEqual(self.classifier.get_confirmation_prompt(del_act), "Delete 'report.docx'?")

        close_act = ActionRequest(action_type=ActionType.CLOSE_APP, params={"target": "Notepad"})
        self.assertEqual(self.classifier.get_confirmation_prompt(close_act), "Close application 'Notepad'?")

        ren_act = ActionRequest(
            action_type=ActionType.RENAME_FILE,
            params={"source": "C:\\temp\\old.txt", "destination": "C:\\temp\\new.txt"},
        )
        self.assertEqual(self.classifier.get_confirmation_prompt(ren_act), "Rename 'old.txt' to 'new.txt'?")

        move_act = ActionRequest(
            action_type=ActionType.MOVE_FILE,
            params={"source": "C:\\temp\\file.txt", "destination": "C:\\archive\\file.txt"},
        )
        self.assertEqual(self.classifier.get_confirmation_prompt(move_act), "Move 'file.txt' to 'file.txt'?")


if __name__ == "__main__":
    unittest.main()
