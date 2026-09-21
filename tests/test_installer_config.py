"""Unit tests for Inno Setup Windows installer configuration (TASK-8.4)."""

from __future__ import annotations

import os
from pathlib import Path
import unittest


class TestInstallerConfiguration(unittest.TestCase):
    """Test suite for packaging/installer.iss and scripts/build_installer.ps1."""

    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parent.parent
        self.iss_path = self.repo_root / "packaging" / "installer.iss"
        self.ps1_path = self.repo_root / "scripts" / "build_installer.ps1"

    def test_iss_file_exists(self) -> None:
        """Verify installer.iss exists and is non-empty."""
        self.assertTrue(self.iss_path.exists(), f"installer.iss not found at {self.iss_path}")
        self.assertGreater(self.iss_path.stat().st_size, 0)

    def test_required_inno_setup_sections_present(self) -> None:
        """Verify all mandatory Inno Setup sections exist."""
        with open(self.iss_path, "r", encoding="utf-8") as f:
            content = f.read()

        sections = [
            "[Setup]",
            "[Languages]",
            "[Tasks]",
            "[Files]",
            "[Icons]",
            "[Registry]",
            "[Run]",
            "[UninstallDelete]",
        ]

        for sec in sections:
            self.assertIn(sec, content, f"Missing required section '{sec}' in installer.iss")

    def test_setup_configuration_directives(self) -> None:
        """Verify application metadata, directory paths, and upgrade flags."""
        with open(self.iss_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("AppName={#MyAppName}", content)
        self.assertIn("AppVersion={#MyAppVersion}", content)
        self.assertIn("DefaultDirName={autopf}\\{#MyAppName}", content)
        self.assertIn("OutputBaseFilename=PCVoiceAgent_Setup_1.0.0", content)
        self.assertIn("CloseApplications=yes", content)
        self.assertIn("ArchitecturesInstallIn64BitMode=x64compatible", content)

    def test_registry_startup_configuration(self) -> None:
        """Verify Windows Run at Startup registry entry and parameters."""
        with open(self.iss_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn(r"Software\Microsoft\Windows\CurrentVersion\Run", content)
        self.assertIn("ValueName: \"PCVoiceAgent\"", content)
        self.assertIn("--tray", content)
        self.assertIn("Tasks: startup", content)
        self.assertIn("Flags: uninsdeletevalue", content)

    def test_shortcuts_and_tasks(self) -> None:
        """Verify desktop and Start Menu shortcuts."""
        with open(self.iss_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Name: \"desktopicon\"", content)
        self.assertIn("Name: \"startup\"", content)
        self.assertIn("{group}\\{#MyAppName}", content)
        self.assertIn("{autodesktop}\\{#MyAppName}", content)

    def test_build_installer_script_exists(self) -> None:
        """Verify build_installer.ps1 exists and contains validation logic."""
        self.assertTrue(self.ps1_path.exists(), f"Script not found at {self.ps1_path}")
        with open(self.ps1_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("ISCC", content)
        self.assertIn("installer.iss", content)
        self.assertIn("DryRun", content)


if __name__ == "__main__":
    unittest.main()
