"""Unit tests for File & Folder System Actions (TASK-6.5)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from voice_agent.control.actions.files import (
    DeleteFileAction,
    MoveFileAction,
    OpenFileAction,
    OpenFolderAction,
    RenameFileAction,
)
from voice_agent.control.action_validator import ActionValidator
from voice_agent.control.models import ActionType


class TestActionFiles(unittest.TestCase):
    """Test suite for file and folder filesystem operations."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.validator = ActionValidator(base_directory=self.base_dir)

        # Create a sample file
        self.sample_file = self.base_dir / "sample.txt"
        self.sample_file.write_text("Hello World", encoding="utf-8")

        # Create a sample subfolder
        self.sample_folder = self.base_dir / "subfolder"
        self.sample_folder.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_open_file_success(self) -> None:
        """Test opening an existing file with mock opener."""
        mock_opener = MagicMock()
        action = OpenFileAction(validator=self.validator, opener=mock_opener)
        self.assertEqual(action.action_type, ActionType.OPEN_FILE)

        result = action.run({"path": "sample.txt"})
        self.assertTrue(result.success)
        mock_opener.assert_called_once_with(str(self.sample_file.resolve()))

    def test_open_file_errors(self) -> None:
        """Test open file with non-existent file or directory target."""
        mock_opener = MagicMock()
        action = OpenFileAction(validator=self.validator, opener=mock_opener)

        # Non-existent
        res_nonexist = action.run({"path": "does_not_exist.txt"})
        self.assertFalse(res_nonexist.success)
        self.assertIn("does not exist", res_nonexist.error_message or "")

        # Directory target
        res_dir = action.run({"path": "subfolder"})
        self.assertFalse(res_dir.success)
        self.assertIn("is a directory", res_dir.error_message or "")

    def test_open_folder_success(self) -> None:
        """Test opening an existing folder."""
        mock_opener = MagicMock()
        action = OpenFolderAction(validator=self.validator, opener=mock_opener)
        self.assertEqual(action.action_type, ActionType.OPEN_FOLDER)

        result = action.run({"path": "subfolder"})
        self.assertTrue(result.success)
        mock_opener.assert_called_once_with(str(self.sample_folder.resolve()))

    def test_rename_file_success(self) -> None:
        """Test renaming a file within the same directory."""
        action = RenameFileAction(validator=self.validator)
        self.assertEqual(action.action_type, ActionType.RENAME_FILE)

        result = action.run({"source": "sample.txt", "destination": "renamed.txt"})
        self.assertTrue(result.success)

        self.assertFalse(self.sample_file.exists())
        renamed_path = self.base_dir / "renamed.txt"
        self.assertTrue(renamed_path.exists())
        self.assertEqual(renamed_path.read_text(encoding="utf-8"), "Hello World")

    def test_move_file_success(self) -> None:
        """Test moving a file into a subfolder."""
        action = MoveFileAction(validator=self.validator)
        self.assertEqual(action.action_type, ActionType.MOVE_FILE)

        dst = self.sample_folder / "moved_sample.txt"
        result = action.run({"source": "sample.txt", "destination": str(dst)})
        self.assertTrue(result.success)

        self.assertFalse(self.sample_file.exists())
        self.assertTrue(dst.exists())
        self.assertEqual(dst.read_text(encoding="utf-8"), "Hello World")

    def test_delete_file_success(self) -> None:
        """Test deleting a file without recycling."""
        action = DeleteFileAction(validator=self.validator, use_trash=False)
        self.assertEqual(action.action_type, ActionType.DELETE_FILE)

        result = action.run({"path": "sample.txt"})
        self.assertTrue(result.success)
        self.assertFalse(self.sample_file.exists())

    def test_delete_file_protected_path_rejection(self) -> None:
        """Verify strict sandboxing prevents deleting system paths."""
        action = DeleteFileAction(validator=self.validator, use_trash=False)

        res_sys = action.run({"path": "C:\\Windows"})
        self.assertFalse(res_sys.success)
        self.assertIn("Validation failed", res_sys.error_message or "")


if __name__ == "__main__":
    unittest.main()
