"""Pytest fixtures and configuration for PC Voice Agent test suite.

Provides shared mocks for audio hardware, clipboard, STT engine,
temporary databases, and isolated configurations.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Any, Generator
from unittest.mock import MagicMock

import numpy as np

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

from voice_agent.app.config import AppConfig, save_config
from voice_agent.clipboard.manager import ClipboardManager
from voice_agent.dictation.inserter import TextInserter
from voice_agent.dictation.normalizer import TextNormalizer
from voice_agent.storage.database import DatabaseManager
from voice_agent.storage.history import HistoryRepository
from voice_agent.stt.engine import SpeechToTextEngine


class SyntheticSTTEngine(SpeechToTextEngine):
    """Deterministic in-memory STT engine for integration testing."""

    def __init__(self, transcript: str = "hello world") -> None:
        self.transcript = transcript
        self.call_count = 0

    def transcribe(self, audio: np.ndarray, language: str | None = None) -> str:
        self.call_count += 1
        return self.transcript

    def is_model_loaded(self) -> bool:
        return True

    def unload_model(self) -> None:
        pass


if HAS_PYTEST:

    @pytest.fixture
    def temp_dir() -> Generator[Path, None, None]:
        """Provide an isolated temporary directory."""
        with tempfile.TemporaryDirectory() as td:
            yield Path(td)

    @pytest.fixture
    def test_config(temp_dir: Path) -> AppConfig:
        """Provide a test AppConfig saved in a temporary path."""
        cfg = AppConfig()
        cfg_path = temp_dir / "config.toml"
        save_config(cfg, cfg_path)
        return cfg

    @pytest.fixture
    def test_db(temp_dir: Path) -> Generator[DatabaseManager, None, None]:
        """Provide an isolated SQLite DatabaseManager."""
        db_path = temp_dir / "test_agent.db"
        db = DatabaseManager(db_path)
        yield db
        db.close()

    @pytest.fixture
    def history_repo(test_db: DatabaseManager) -> HistoryRepository:
        """Provide an isolated HistoryRepository."""
        return HistoryRepository(db_manager=test_db)

    @pytest.fixture
    def mock_clipboard() -> MagicMock:
        """Provide a mocked Win32 ClipboardManager."""
        mock = MagicMock(spec=ClipboardManager)
        mock._clipboard_content = ""

        def get_text():
            return mock._clipboard_content

        def set_text(text):
            mock._clipboard_content = text
            return True

        mock.get_text.side_effect = get_text
        mock.set_text.side_effect = set_text
        mock.backup_clipboard.return_value = "original text"
        mock.restore_clipboard.return_value = True
        return mock

    @pytest.fixture
    def synthetic_audio() -> np.ndarray:
        """Provide 1 second of 16kHz mono audio zeros."""
        return np.zeros(16000, dtype=np.float32)
