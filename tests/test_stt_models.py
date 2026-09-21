"""Unit tests for STT engine interface and model management."""

import hashlib
from pathlib import Path
import tempfile
import unittest

import numpy as np

from voice_agent.stt.engine import SpeechToTextEngine, TranscriptionResult
from voice_agent.stt.models import (
    DEFAULT_MODEL_NAME,
    SUPPORTED_MODELS,
    ModelInfo,
    ModelManager,
)


class DummyEngine(SpeechToTextEngine):
    """Concrete test implementation of SpeechToTextEngine."""

    def __init__(self) -> None:
        self._loaded = True

    def transcribe(self, audio: np.ndarray, language: str | None = None) -> str:
        return f"transcribed {len(audio)} samples in {language or 'auto'}"

    def is_loaded(self) -> bool:
        return self._loaded


class TestSTTEngineInterface(unittest.TestCase):
    """Test suite for SpeechToTextEngine ABC."""

    def test_abstract_class_cannot_be_instantiated(self) -> None:
        """Verify ABC cannot be directly instantiated."""
        with self.assertRaises(TypeError):
            SpeechToTextEngine()  # type: ignore[abstract]

    def test_concrete_engine_implementation(self) -> None:
        """Verify concrete engine contract fulfillment."""
        engine = DummyEngine()
        self.assertTrue(engine.is_loaded())
        audio = np.zeros(16000, dtype=np.float32)
        res = engine.transcribe(audio, "en")
        self.assertEqual(res, "transcribed 16000 samples in en")

    def test_transcription_result_dataclass(self) -> None:
        """Verify TranscriptionResult properties."""
        result = TranscriptionResult(text="Hello world", language="en", duration=1.5)
        self.assertEqual(result.text, "Hello world")
        self.assertEqual(result.language, "en")
        self.assertEqual(result.duration, 1.5)


class TestModelManager(unittest.TestCase):
    """Test suite for Whisper ModelManager metadata and cache verification."""

    def setUp(self) -> None:
        self.test_dir = tempfile.TemporaryDirectory()
        self.models_dir = Path(self.test_dir.name)
        self.manager = ModelManager(models_dir=self.models_dir)

    def tearDown(self) -> None:
        self.test_dir.cleanup()

    def test_supported_models_list(self) -> None:
        """Verify all expected Whisper model tiers are defined."""
        models = self.manager.list_supported_models()
        model_names = {m.name for m in models}
        self.assertIn("tiny", model_names)
        self.assertIn("base", model_names)
        self.assertIn("small", model_names)
        self.assertIn("medium", model_names)
        self.assertEqual(DEFAULT_MODEL_NAME, "base")

    def test_get_model_info(self) -> None:
        """Verify model lookup with case insensitivity and whitespace stripping."""
        base_info = self.manager.get_model_info("base")
        self.assertEqual(base_info.name, "base")
        self.assertTrue(base_info.is_default)
        self.assertEqual(base_info.size_mb, 145)
        self.assertEqual(base_info.estimated_ram_mb, 600)

        # Case-insensitive
        upper_info = self.manager.get_model_info("  BASE  ")
        self.assertEqual(upper_info.name, "base")

        with self.assertRaises(ValueError):
            self.manager.get_model_info("huge-nonexistent-model")

    def test_model_availability_checks(self) -> None:
        """Verify checking local cache presence."""
        self.assertFalse(self.manager.is_model_available("base"))

        # Create dummy model folder with model.bin
        base_dir = self.manager.get_model_path("base")
        base_dir.mkdir(parents=True, exist_ok=True)
        (base_dir / "model.bin").write_bytes(b"dummy_model_binary")

        self.assertTrue(self.manager.is_model_available("base"))

    def test_compute_file_checksum(self) -> None:
        """Verify SHA-256 hash calculation."""
        test_file = self.models_dir / "test_file.txt"
        test_data = b"Speech to text voice agent test file."
        test_file.write_bytes(test_data)

        expected_hash = hashlib.sha256(test_data).hexdigest()
        actual_hash = self.manager.compute_file_checksum(test_file)
        self.assertEqual(actual_hash, expected_hash)

        # Missing file
        with self.assertRaises(FileNotFoundError):
            self.manager.compute_file_checksum(self.models_dir / "does_not_exist.bin")

    def test_get_model_status(self) -> None:
        """Verify get_model_status returns complete information."""
        base_dir = self.manager.get_model_path("base")
        base_dir.mkdir(parents=True, exist_ok=True)
        (base_dir / "model.bin").write_bytes(b"1234567890")

        status = self.manager.get_model_status("base")
        self.assertEqual(status["name"], "base")
        self.assertTrue(status["is_available"])
        self.assertEqual(status["cached_files"], 1)
        self.assertEqual(status["cached_bytes"], 10)


if __name__ == "__main__":
    unittest.main()
