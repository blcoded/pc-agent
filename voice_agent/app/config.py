"""Configuration management for PC Voice Agent.

Handles strongly-typed configuration loading, validation, saving, and defaults
using TOML and atomic writes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import os
from pathlib import Path
import tempfile
import tomllib
from typing import Any


@dataclass
class DictationConfig:
    """Settings for Dictation Mode."""

    hotkey: str = "ctrl_r"
    mode: str = "both"  # "push_to_talk", "toggle", or "both"
    model: str = "base"  # "tiny", "base", "small", "medium"
    language: str = "en"
    format_commands: bool = True
    restore_clipboard: bool = True
    keep_in_clipboard: bool = False


@dataclass
class ControlConfig:
    """Settings for Control Mode."""

    hotkey: str = "alt_r"
    mode: str = "both"  # "push_to_talk", "toggle", or "both"
    confirm_medium: bool = False
    confirm_high: bool = True


@dataclass
class AudioConfig:
    """Settings for Audio capture."""

    microphone: str | None = None  # None indicates system default microphone
    sample_rate: int = 16000
    channels: int = 1
    max_duration: int = 60  # seconds, clamped between 10 and 150

    def __post_init__(self) -> None:
        try:
            self.max_duration = max(10, min(150, int(self.max_duration)))
        except (ValueError, TypeError):
            self.max_duration = 60



@dataclass
class UIConfig:
    """Settings for Floating Overlay and UI appearance."""

    overlay_enabled: bool = True
    overlay_x: int = -1  # -1 denotes default automatic placement
    overlay_y: int = -1
    opacity: float = 0.95


@dataclass
class StorageConfig:
    """Settings for SQLite persistence and retention."""

    history_retention_days: int = 30
    max_history_entries: int = 5000


@dataclass
class GeneralConfig:
    """Application-wide general preferences."""

    run_at_startup: bool = False
    minimize_to_tray: bool = True


@dataclass
class AppConfig:
    """Root configuration holding all sub-configurations."""

    dictation: DictationConfig = field(default_factory=DictationConfig)
    control: ControlConfig = field(default_factory=ControlConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    general: GeneralConfig = field(default_factory=GeneralConfig)


def get_default_config_dir() -> Path:
    """Return the default configuration directory in APPDATA or home."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        base = Path(appdata)
    else:
        base = Path.home() / ".config"
    config_dir = base / "PCVoiceAgent"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_default_config_path() -> Path:
    """Return the default configuration file path."""
    return get_default_config_dir() / "config.toml"


def _format_toml_value(value: Any) -> str:
    """Format Python values into valid TOML values."""
    if isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    elif value is None:
        return '""'
    elif isinstance(value, list):
        items = ", ".join(_format_toml_value(v) for v in value)
        return f"[{items}]"
    else:
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'


def serialize_to_toml(config: AppConfig) -> str:
    """Serialize AppConfig instance into a TOML-formatted string."""
    lines: list[str] = [
        "# PC Voice Agent Configuration",
        "# Automatically generated and validated",
        "",
    ]

    data = asdict(config)
    for section_name, section_dict in data.items():
        lines.append(f"[{section_name}]")
        for key, val in section_dict.items():
            lines.append(f"{key} = {_format_toml_value(val)}")
        lines.append("")

    return "\n".join(lines)


def load_config(path: Path | None = None) -> AppConfig:
    """Load configuration from the specified TOML path or return defaults."""
    target_path = path or get_default_config_path()

    if not target_path.exists():
        cfg = AppConfig()
        save_config(cfg, target_path)
        return cfg

    try:
        with open(target_path, "rb") as f:
            data = tomllib.load(f)

        def _get_section(cls: type, section_key: str) -> Any:
            section_data = data.get(section_key, {})
            # Filter out unknown keys to prevent crashes on schema changes
            valid_keys = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
            filtered = {k: v for k, v in section_data.items() if k in valid_keys}
            # Special case for empty string in microphone representing None
            if section_key == "audio" and filtered.get("microphone") == "":
                filtered["microphone"] = None
            return cls(**filtered)

        return AppConfig(
            dictation=_get_section(DictationConfig, "dictation"),
            control=_get_section(ControlConfig, "control"),
            audio=_get_section(AudioConfig, "audio"),
            ui=_get_section(UIConfig, "ui"),
            storage=_get_section(StorageConfig, "storage"),
            general=_get_section(GeneralConfig, "general"),
        )
    except Exception as e:
        # If config is corrupted, fall back safely to defaults
        return AppConfig()


def save_config(config: AppConfig, path: Path | None = None) -> None:
    """Save configuration to the specified path atomically."""
    target_path = path or get_default_config_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    toml_content = serialize_to_toml(config)

    # Atomic write via temporary file
    temp_dir = target_path.parent
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=temp_dir, delete=False) as tf:
        tf.write(toml_content)
        temp_file_name = tf.name

    # Replace target file atomically
    os.replace(temp_file_name, target_path)
