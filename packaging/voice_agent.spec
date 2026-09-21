# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build specification for PC Voice Agent.

Produces a standalone, windowless Windows executable with system tray support,
dynamic library dependencies (PySide6, CTranslate2), and external Whisper
model management.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

# PyInstaller execution context
block_cipher = None

# Root directory of the repository
BASE_DIR = Path(SPECPATH).resolve().parent
ENTRY_POINT = str(BASE_DIR / "voice_agent" / "app" / "main.py")

# Application resource files (icons, defaults, templates)
datas = [
    (str(BASE_DIR / "voice_agent" / "resources"), "voice_agent/resources"),
]

# Binaries and C-extension dynamic libraries
binaries = []

# Dynamic imports and submodules needed by voice_agent and external packages
hiddenimports = [
    # GUI and Qt Core
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    # Audio capture & processing
    "sounddevice",
    "numpy",
    # Speech-to-Text inference
    "faster_whisper",
    "ctranslate2",
    # Global input hooks & Windows APIs
    "pynput",
    "pynput.keyboard",
    "pynput.keyboard._win32",
    "pynput.mouse",
    "pynput.mouse._win32",
    "win32gui",
    "win32process",
    "win32clipboard",
    "win32con",
    "win32api",
    # Standard library backends
    "tomllib",
    "sqlite3",
    "ctypes",
    "ctypes.wintypes",
    "winreg",
]

# Excluded packages to keep binary footprint minimal
excludes = [
    "tests",
    "pytest",
    "unittest",
    "tkinter",
    "matplotlib",
    "IPython",
    "jupyter",
    "scipy",
    "pandas",
    "pip",
    "setuptools",
]

a = Analysis(
    [ENTRY_POINT],
    pathex=[str(BASE_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PCVoiceAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowless background execution with system tray
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Optional custom icon (.ico)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PCVoiceAgent",
)
