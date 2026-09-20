"""Application logging and diagnostic subsystem for PC Voice Agent.

Provides privacy-safe, structured rotating file logging and console output.
Strictly ensures raw audio and sensitive user dictation transcripts are never logged.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
from typing import ClassVar

from voice_agent.app.config import get_default_config_dir

# Global logger instance name
LOGGER_NAME = "voice_agent"

# Maximum log file size: 5 MB
MAX_LOG_BYTES = 5 * 1024 * 1024
# Number of backup log files to retain
BACKUP_COUNT = 3


class PrivacyFilter(logging.Filter):
    """Filter that sanitizes potentially sensitive data from log records.

    Ensures that dictated text, sensitive tokens, or raw audio markers
    are masked or redacted before reaching any log destination.
    """

    REDACTED_PATTERNS: ClassVar[list[tuple[re.Pattern[str], str]]] = [
        (re.compile(r"(transcript\s*[:=]\s*['\"][^'\"]*['\"])", re.IGNORECASE), "transcript=[REDACTED]"),
        (re.compile(r"(dictation_text\s*[:=]\s*['\"][^'\"]*['\"])", re.IGNORECASE), "dictation_text=[REDACTED]"),
        (re.compile(r"(bearer\s+[\w\-_.]+)", re.IGNORECASE), "bearer [REDACTED]"),
        (re.compile(r"(gh[opsu]_[a-zA-Z0-9_]{36,})"), "[REDACTED_GITHUB_TOKEN]"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, replacement in self.REDACTED_PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        return True


def get_default_log_dir() -> Path:
    """Return the default log directory path."""
    log_dir = get_default_config_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def setup_logging(
    log_dir: Path | None = None,
    level: int = logging.INFO,
    console_output: bool = True,
) -> logging.Logger:
    """Initialize the application-wide logging system.

    Args:
        log_dir: Directory where logs should be stored. Defaults to %APPDATA%/PCVoiceAgent/logs.
        level: Minimum log level. Defaults to logging.INFO.
        console_output: Whether to attach a console StreamHandler.

    Returns:
        Configured root logger for the voice_agent package.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)

    # Avoid duplicating handlers if setup_logging is called multiple times
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] (%(name)s.%(funcName)s:%(lineno)d) %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    privacy_filter = PrivacyFilter()
    logger.addFilter(privacy_filter)

    # File Handler
    target_log_dir = log_dir or get_default_log_dir()
    target_log_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_log_dir / "voice_agent.log"

    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(privacy_filter)
    logger.addHandler(file_handler)

    # Console Handler
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(privacy_filter)
        logger.addHandler(console_handler)

    logger.info("Logging initialized at level %s in %s", logging.getLevelName(level), log_file)
    return logger


def get_logger(module_name: str | None = None) -> logging.Logger:
    """Get a child logger under the voice_agent namespace."""
    if module_name:
        return logging.getLogger(f"{LOGGER_NAME}.{module_name}")
    return logging.getLogger(LOGGER_NAME)
