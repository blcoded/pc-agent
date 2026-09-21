"""Standalone PyInstaller build pipeline for PC Voice Agent (TASK-8.3).

Automates building the desktop application into a standalone Windows executable.
Handles environment verification, directory cleanup, spec validation,
and PyInstaller invocation with informative diagnostic reporting.
"""

from __future__ import annotations

import argparse
import compileall
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys


def get_repo_root() -> Path:
    """Return the absolute path to the repository root directory."""
    return Path(__file__).resolve().parent.parent


def clean_artifacts(repo_root: Path) -> None:
    """Remove previous build and dist output directories."""
    for folder_name in ("build", "dist"):
        folder = repo_root / folder_name
        if folder.exists() and folder.is_dir():
            print(f"[Build] Cleaning previous output directory: {folder}")
            try:
                shutil.rmtree(folder)
            except Exception as e:
                print(f"[Build] Warning: Could not remove {folder}: {e}")


def validate_sources(repo_root: Path) -> bool:
    """Ensure all Python source files compile cleanly without syntax errors."""
    print("[Build] Compiling and validating Python source files...")
    src_dir = repo_root / "voice_agent"
    if not src_dir.exists():
        print(f"[Build] Error: Source directory '{src_dir}' does not exist.")
        return False

    success = compileall.compile_dir(str(src_dir), quiet=1, force=True)
    if not success:
        print("[Build] Error: Syntax or compilation errors detected in source files.")
        return False

    entry_point = repo_root / "voice_agent" / "app" / "main.py"
    if not entry_point.exists():
        print(f"[Build] Error: Main entry point '{entry_point}' not found.")
        return False

    print("[Build] Source validation successful.")
    return True


def validate_spec_file(spec_path: Path) -> bool:
    """Validate that the PyInstaller spec file exists and contains expected configurations."""
    print(f"[Build] Validating PyInstaller spec file: {spec_path}")
    if not spec_path.exists():
        print(f"[Build] Error: Spec file '{spec_path}' does not exist.")
        return False

    with open(spec_path, "r", encoding="utf-8") as f:
        content = f.read()

    required_tokens = [
        "ENTRY_POINT",
        "Analysis",
        "PYZ",
        "EXE",
        "console=False",
        "PCVoiceAgent",
    ]

    for token in required_tokens:
        if token not in content:
            print(f"[Build] Error: Spec file is missing required configuration token: '{token}'")
            return False

    print("[Build] Spec file validation passed.")
    return True


def run_build(
    clean: bool = True,
    dry_run: bool = False,
    spec_file: str | None = None,
) -> int:
    """Execute the PyInstaller build pipeline.

    Args:
        clean: Clean previous build and dist directories before starting.
        dry_run: Run validation only without invoking PyInstaller.
        spec_file: Path to custom spec file. Defaults to packaging/voice_agent.spec.

    Returns:
        Exit code: 0 on success, non-zero on failure.
    """
    repo_root = get_repo_root()
    spec_path = Path(spec_file) if spec_file else repo_root / "packaging" / "voice_agent.spec"

    print("==================================================")
    print("      PC Voice Agent - Executable Build Pipeline  ")
    print("==================================================")
    print(f"Repository Root: {repo_root}")
    print(f"Spec Path:       {spec_path}")
    print(f"Python Exec:     {sys.executable}")
    print(f"Dry Run Mode:    {dry_run}")
    print("==================================================")

    # 1. Validate source code integrity
    if not validate_sources(repo_root):
        return 1

    # 2. Validate spec file
    if not validate_spec_file(spec_path):
        return 1

    # 3. Clean previous build artifacts
    if clean:
        clean_artifacts(repo_root)

    # 4. Dry run check
    if dry_run:
        print("[Build] Pre-flight checks passed successfully. (Dry run completed)")
        return 0

    # 5. Check PyInstaller availability
    has_pyinstaller = importlib.util.find_spec("PyInstaller") is not None
    if not has_pyinstaller:
        print("\n[Build] Notice: PyInstaller is not installed in the current environment.")
        print("[Build] To build the standalone binary, run:")
        print("    pip install pyinstaller")
        print(f"    pyinstaller --noconfirm \"{spec_path}\"")
        print("[Build] Pre-flight validation and spec configuration are complete and ready.")
        return 0

    # 6. Invoke PyInstaller
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        str(spec_path),
    ]

    print(f"[Build] Executing command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(repo_root))
    if result.returncode != 0:
        print(f"[Build] Error: PyInstaller exited with error code {result.returncode}")
        return result.returncode

    output_exe = repo_root / "dist" / "PCVoiceAgent" / "PCVoiceAgent.exe"
    print("\n==================================================")
    print(f"[Build] Build successful! Standalone executable output:")
    print(f"        {output_exe}")
    print("==================================================")
    return 0


def main() -> None:
    """CLI entry point for scripts/build.py."""
    parser = argparse.ArgumentParser(description="PC Voice Agent Executable Builder")
    parser.add_argument("--no-clean", action="store_true", help="Do not delete existing build/ and dist/ folders")
    parser.add_argument("--dry-run", action="store_true", help="Validate spec and files without building")
    parser.add_argument("--spec", type=str, default=None, help="Custom path to .spec file")

    args = parser.parse_args()
    code = run_build(
        clean=not args.no_clean,
        dry_run=args.dry_run,
        spec_file=args.spec,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
