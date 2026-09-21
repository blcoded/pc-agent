"""Unit tests for PyInstaller build specification and pipeline (TASK-8.3)."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from scripts.build import (
    clean_artifacts,
    get_repo_root,
    run_build,
    validate_sources,
    validate_spec_file,
)


class TestPyInstallerBuildConfig(unittest.TestCase):
    """Test suite for packaging/voice_agent.spec and scripts/build.py."""

    def setUp(self) -> None:
        self.repo_root = get_repo_root()
        self.spec_path = self.repo_root / "packaging" / "voice_agent.spec"

    def test_spec_file_exists(self) -> None:
        """Verify voice_agent.spec file exists at packaging/."""
        self.assertTrue(self.spec_path.exists(), f"Spec file missing at {self.spec_path}")

    def test_spec_file_contains_required_components(self) -> None:
        """Verify spec file defines entry point, hidden imports, and windowless config."""
        with open(self.spec_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check entry point
        self.assertIn("voice_agent", content)
        self.assertIn("main.py", content)

        # Check required hidden imports
        expected_imports = [
            "PySide6",
            "faster_whisper",
            "ctranslate2",
            "sounddevice",
            "pynput",
            "win32gui",
            "win32clipboard",
            "tomllib",
            "sqlite3",
        ]
        for imp in expected_imports:
            self.assertIn(imp, content, f"Expected hidden import '{imp}' in spec file")

        # Check windowless execution
        self.assertIn("console=False", content)
        self.assertIn("PCVoiceAgent", content)

    def test_validate_sources_passes(self) -> None:
        """Source validator confirms voice_agent compilation and main entry point."""
        self.assertTrue(validate_sources(self.repo_root))

    def test_validate_spec_file_passes(self) -> None:
        """Spec validator validates packaging/voice_agent.spec."""
        self.assertTrue(validate_spec_file(self.spec_path))

    def test_run_build_dry_run(self) -> None:
        """Dry-run build executes pre-flight checks and exits with 0."""
        exit_code = run_build(clean=False, dry_run=True, spec_file=str(self.spec_path))
        self.assertEqual(exit_code, 0)

    def test_clean_artifacts(self) -> None:
        """clean_artifacts removes mock build and dist directories."""
        with tempfile.TemporaryDirectory() as td:
            mock_root = Path(td)
            mock_build = mock_root / "build"
            mock_dist = mock_root / "dist"
            mock_build.mkdir()
            mock_dist.mkdir()
            (mock_build / "temp.txt").write_text("temp", encoding="utf-8")
            (mock_dist / "output.txt").write_text("out", encoding="utf-8")

            self.assertTrue(mock_build.exists())
            self.assertTrue(mock_dist.exists())

            clean_artifacts(mock_root)

            self.assertFalse(mock_build.exists())
            self.assertFalse(mock_dist.exists())


if __name__ == "__main__":
    unittest.main()
