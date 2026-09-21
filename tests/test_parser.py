"""Unit tests for local rule-based command parser (TASK-5.2)."""

import unittest

from voice_agent.control.models import ActionType, RiskLevel
from voice_agent.control.parser import CommandParser, UnsupportedCommandResult


class TestCommandParser(unittest.TestCase):
    """Comprehensive unit test suite for CommandParser."""

    def setUp(self) -> None:
        self.parser = CommandParser()

    def test_application_commands(self) -> None:
        """Test open, launch, close, and switch window commands."""
        # Open app
        req = self.parser.parse_single_command("open notepad")
        self.assertEqual(req.action_type, ActionType.OPEN_APP)
        self.assertEqual(req.params["app_name"], "notepad")

        req = self.parser.parse_single_command("launch chrome")
        self.assertEqual(req.action_type, ActionType.OPEN_APP)
        self.assertEqual(req.params["app_name"], "chrome")

        req = self.parser.parse_single_command("start spotify")
        self.assertEqual(req.action_type, ActionType.OPEN_APP)
        self.assertEqual(req.params["app_name"], "spotify")

        # Close window / app
        req = self.parser.parse_single_command("close window")
        self.assertEqual(req.action_type, ActionType.CLOSE_APP)
        self.assertEqual(req.params["target"], "current_window")
        self.assertEqual(req.risk_level, RiskLevel.MEDIUM)

        req = self.parser.parse_single_command("quit notepad")
        self.assertEqual(req.action_type, ActionType.CLOSE_APP)
        self.assertEqual(req.params["target"], "notepad")

        # Switch / focus window
        req = self.parser.parse_single_command("switch to slack")
        self.assertEqual(req.action_type, ActionType.SWITCH_WINDOW)
        self.assertEqual(req.params["window_name"], "slack")

        req = self.parser.parse_single_command("focus discord")
        self.assertEqual(req.action_type, ActionType.SWITCH_WINDOW)
        self.assertEqual(req.params["window_name"], "discord")

    def test_keyboard_and_typing_commands(self) -> None:
        """Test press key, typing text, and shortcuts."""
        # Press key
        req = self.parser.parse_single_command("press enter")
        self.assertEqual(req.action_type, ActionType.PRESS_KEY)
        self.assertEqual(req.params["key"], "enter")

        req = self.parser.parse_single_command("press backspace")
        self.assertEqual(req.action_type, ActionType.PRESS_KEY)
        self.assertEqual(req.params["key"], "backspace")

        req = self.parser.parse_single_command("hit escape")
        self.assertEqual(req.action_type, ActionType.PRESS_KEY)
        self.assertEqual(req.params["key"], "escape")

        # Type text
        req = self.parser.parse_single_command("type Hello world")
        self.assertEqual(req.action_type, ActionType.TYPE_TEXT)
        self.assertEqual(req.params["text"], "Hello world")

        req = self.parser.parse_single_command('write "sample quotation"')
        self.assertEqual(req.action_type, ActionType.TYPE_TEXT)
        self.assertEqual(req.params["text"], "sample quotation")

        # Shortcuts
        req = self.parser.parse_single_command("shortcut ctrl c")
        self.assertEqual(req.action_type, ActionType.HOTKEY)
        self.assertEqual(req.params["keys"], ["ctrl", "c"])

        req = self.parser.parse_single_command("hotkey alt+f4")
        self.assertEqual(req.action_type, ActionType.HOTKEY)
        self.assertEqual(req.params["keys"], ["alt", "f4"])

    def test_mouse_commands(self) -> None:
        """Test click, double click, right click, and mouse moves."""
        req = self.parser.parse_single_command("click")
        self.assertEqual(req.action_type, ActionType.CLICK)
        self.assertEqual(req.params["button"], "left")
        self.assertEqual(req.params["click_count"], 1)

        req = self.parser.parse_single_command("double click")
        self.assertEqual(req.action_type, ActionType.CLICK)
        self.assertEqual(req.params["click_count"], 2)

        req = self.parser.parse_single_command("right click")
        self.assertEqual(req.action_type, ActionType.CLICK)
        self.assertEqual(req.params["button"], "right")

        # Move mouse absolute
        req = self.parser.parse_single_command("move mouse to 300 450")
        self.assertEqual(req.action_type, ActionType.MOVE_MOUSE)
        self.assertEqual(req.params["x"], 300)
        self.assertEqual(req.params["y"], 450)
        self.assertEqual(req.params["mode"], "absolute")

        # Move mouse relative
        req = self.parser.parse_single_command("move mouse right 100 pixels")
        self.assertEqual(req.action_type, ActionType.MOVE_MOUSE)
        self.assertEqual(req.params["direction"], "right")
        self.assertEqual(req.params["distance"], 100)
        self.assertEqual(req.params["mode"], "relative")

    def test_web_and_search_commands(self) -> None:
        """Test URL opening and search queries."""
        req = self.parser.parse_single_command("open github.com")
        self.assertEqual(req.action_type, ActionType.OPEN_URL)
        self.assertEqual(req.params["url"], "https://github.com")

        req = self.parser.parse_single_command("browse to https://docs.python.org")
        self.assertEqual(req.action_type, ActionType.OPEN_URL)
        self.assertEqual(req.params["url"], "https://docs.python.org")

        req = self.parser.parse_single_command("search for python documentation")
        self.assertEqual(req.action_type, ActionType.SEARCH_WEB)
        self.assertEqual(req.params["query"], "python documentation")

        req = self.parser.parse_single_command("google artificial intelligence")
        self.assertEqual(req.action_type, ActionType.SEARCH_WEB)
        self.assertEqual(req.params["query"], "artificial intelligence")

    def test_clipboard_commands(self) -> None:
        """Test copy, paste, and read clipboard."""
        req = self.parser.parse_single_command("copy")
        self.assertEqual(req.action_type, ActionType.COPY)

        req = self.parser.parse_single_command("paste")
        self.assertEqual(req.action_type, ActionType.PASTE)

        req = self.parser.parse_single_command("read clipboard")
        self.assertEqual(req.action_type, ActionType.READ_CLIPBOARD)

    def test_filesystem_commands(self) -> None:
        """Test file opening, moving, renaming, and deletion."""
        # Open file
        req = self.parser.parse_single_command("open file report.txt")
        self.assertEqual(req.action_type, ActionType.OPEN_FILE)
        self.assertEqual(req.params["path"], "report.txt")

        # Open folder
        req = self.parser.parse_single_command("open folder C:\\Users\\Public")
        self.assertEqual(req.action_type, ActionType.OPEN_FOLDER)
        self.assertEqual(req.params["path"], "C:\\Users\\Public")

        # Delete file (High Risk)
        req = self.parser.parse_single_command("delete file draft.doc")
        self.assertEqual(req.action_type, ActionType.DELETE_FILE)
        self.assertEqual(req.params["path"], "draft.doc")
        self.assertEqual(req.risk_level, RiskLevel.HIGH)

        # Rename file
        req = self.parser.parse_single_command("rename file a.txt to b.txt")
        self.assertEqual(req.action_type, ActionType.RENAME_FILE)
        self.assertEqual(req.params["source"], "a.txt")
        self.assertEqual(req.params["destination"], "b.txt")
        self.assertEqual(req.risk_level, RiskLevel.MEDIUM)

        # Move file
        req = self.parser.parse_single_command("move file document.pdf to archive")
        self.assertEqual(req.action_type, ActionType.MOVE_FILE)
        self.assertEqual(req.params["source"], "document.pdf")
        self.assertEqual(req.params["destination"], "archive")
        self.assertEqual(req.risk_level, RiskLevel.MEDIUM)

    def test_multi_command_chaining(self) -> None:
        """Test chaining multiple actions with 'and' or 'then'."""
        actions = self.parser.parse("open notepad and type Hello")
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0].action_type, ActionType.OPEN_APP)
        self.assertEqual(actions[0].params["app_name"], "notepad")
        self.assertEqual(actions[1].action_type, ActionType.TYPE_TEXT)
        self.assertEqual(actions[1].params["text"], "Hello")

        # Three-step chain
        chain = self.parser.parse("open github.com then press enter and then click")
        self.assertEqual(len(chain), 3)
        self.assertEqual(chain[0].action_type, ActionType.OPEN_URL)
        self.assertEqual(chain[1].action_type, ActionType.PRESS_KEY)
        self.assertEqual(chain[2].action_type, ActionType.CLICK)

        # 'and' inside search query should not be split
        search_actions = self.parser.parse("search for fish and chips")
        self.assertEqual(len(search_actions), 1)
        self.assertEqual(search_actions[0].action_type, ActionType.SEARCH_WEB)
        self.assertEqual(search_actions[0].params["query"], "fish and chips")

    def test_unsupported_and_ambiguous_commands(self) -> None:
        """Test that invalid/unsupported commands return UnsupportedCommandResult without guessing."""
        result = self.parser.parse_single_command("play me some jazz music")
        self.assertIsInstance(result, UnsupportedCommandResult)
        self.assertEqual(result.raw_command, "play me some jazz music")
        self.assertTrue(result.to_dict()["unsupported"])

        result2 = self.parser.parse_single_command("fly me to the moon")
        self.assertIsInstance(result2, UnsupportedCommandResult)

        self.assertFalse(self.parser.is_supported("cook a dinner"))
        self.assertTrue(self.parser.is_supported("open notepad"))

        # parse_actions returns empty list if any clause is unsupported
        self.assertEqual(self.parser.parse_actions("open notepad and bake a cake"), [])

    def test_empty_and_whitespace_input(self) -> None:
        """Test empty and whitespace-only command parsing."""
        self.assertEqual(self.parser.parse(""), [])
        self.assertEqual(self.parser.parse("   "), [])
        self.assertFalse(self.parser.is_supported(""))

    def test_copy_and_paste_chain(self) -> None:
        """Test chaining copy and paste."""
        actions = self.parser.parse("copy and paste")
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0].action_type, ActionType.COPY)
        self.assertEqual(actions[1].action_type, ActionType.PASTE)

    def test_type_then_press_enter(self) -> None:
        """Test typing followed by pressing enter."""
        actions = self.parser.parse("type Welcome to PC Voice Agent then press enter")
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0].action_type, ActionType.TYPE_TEXT)
        self.assertEqual(actions[0].params["text"], "Welcome to PC Voice Agent")
        self.assertEqual(actions[1].action_type, ActionType.PRESS_KEY)
        self.assertEqual(actions[1].params["key"], "enter")


if __name__ == "__main__":
    unittest.main()
