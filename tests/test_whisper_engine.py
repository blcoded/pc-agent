"""Unit tests for faster-whisper local STT engine and CUDA/CPU fallback."""

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

import numpy as np

from voice_agent.stt.whisper_engine import (
    FasterWhisperEngine,
    detect_optimal_device,
)


class MockSegment:
    """Mock segment object returned by faster-whisper."""

    def __init__(self, text: str, start: float = 0.0, end: float = 1.0) -> None:
        self.text = text
        self.start = start
        self.end = end
        self.avg_logprob = -0.2
        self.no_speech_prob = 0.01


class MockWhisperModel:
    """Mock WhisperModel simulating faster-whisper inference."""

    def __init__(
        self,
        model_source: str,
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: int = 4,
        num_workers: int = 1,
        download_root: str | None = None,
    ) -> None:
        self.model_source = model_source
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self.num_workers = num_workers
        self.download_root = download_root
        self.transcribe_calls = 0
        self.should_raise_cuda_oom = False

    def transcribe(
        self,
        audio: np.ndarray,
        language: str | None = "en",
        beam_size: int = 1,
        temperature: float = 0.0,
        vad_filter: bool = True,
    ) -> tuple[list[MockSegment], SimpleNamespace]:
        self.transcribe_calls += 1
        if self.should_raise_cuda_oom and self.device == "cuda":
            raise RuntimeError("CUDA out of memory. Tried to allocate 512 MiB")

        info = SimpleNamespace(language=language or "en")
        segments = [
            MockSegment("Open file explorer", 0.0, 1.2),
            MockSegment("and create new folder.", 1.2, 2.5),
        ]
        return segments, info


class TestFasterWhisperEngine(unittest.TestCase):
    """Test suite for FasterWhisperEngine inference, model lifecycle, and fallback."""

    def setUp(self) -> None:
        self.test_dir = tempfile.TemporaryDirectory()
        self.models_dir = Path(self.test_dir.name)
        self.mock_model_instances: list[MockWhisperModel] = []

    def tearDown(self) -> None:
        self.test_dir.cleanup()

    def _factory(self, *args, **kwargs) -> MockWhisperModel:
        instance = MockWhisperModel(*args, **kwargs)
        self.mock_model_instances.append(instance)
        return instance

    def test_optimal_device_detection(self) -> None:
        """Verify device detection produces valid device and compute type."""
        device, compute = detect_optimal_device()
        self.assertIn(device, ("cuda", "cpu"))
        self.assertIn(compute, ("float16", "int8"))

    def test_load_and_unload_lifecycle(self) -> None:
        """Verify load_model and unload_model update is_loaded state."""
        engine = FasterWhisperEngine(
            model_size="base",
            models_dir=self.models_dir,
            device="cpu",
            compute_type="int8",
            model_factory=self._factory,
        )

        self.assertFalse(engine.is_loaded())
        engine.load_model()
        self.assertTrue(engine.is_loaded())
        self.assertEqual(len(self.mock_model_instances), 1)

        engine.unload_model()
        self.assertFalse(engine.is_loaded())

    def test_transcription_and_detailed_results(self) -> None:
        """Verify successful transcription execution and result packaging."""
        engine = FasterWhisperEngine(
            model_size="base",
            models_dir=self.models_dir,
            device="cpu",
            compute_type="int8",
            model_factory=self._factory,
        )

        audio = np.zeros(32000, dtype=np.float32)  # 2 seconds
        text = engine.transcribe(audio, language="en")
        self.assertEqual(text, "Open file explorer and create new folder.")

        result = engine.transcribe_detailed(audio, language="en")
        self.assertEqual(result.text, "Open file explorer and create new folder.")
        self.assertEqual(result.language, "en")
        self.assertEqual(result.duration, 2.0)
        self.assertEqual(len(result.segments), 2)
        self.assertEqual(result.segments[0]["text"], "Open file explorer")

    def test_empty_audio_returns_empty_string(self) -> None:
        """Verify empty audio does not trigger transcription."""
        engine = FasterWhisperEngine(
            model_size="base",
            models_dir=self.models_dir,
            device="cpu",
            compute_type="int8",
            model_factory=self._factory,
        )

        empty_audio = np.zeros(0, dtype=np.float32)
        text = engine.transcribe(empty_audio)
        self.assertEqual(text, "")
        self.assertEqual(len(self.mock_model_instances), 0)

    def test_cuda_oom_automatic_fallback_to_cpu(self) -> None:
        """Verify CUDA OOM during transcription automatically falls back to CPU/int8."""
        first_call = True

        def failing_cuda_factory(*args, **kwargs) -> MockWhisperModel:
            nonlocal first_call
            inst = MockWhisperModel(*args, **kwargs)
            if inst.device == "cuda" and first_call:
                inst.should_raise_cuda_oom = True
                first_call = False
            self.mock_model_instances.append(inst)
            return inst

        engine = FasterWhisperEngine(
            model_size="base",
            models_dir=self.models_dir,
            device="cuda",
            compute_type="float16",
            model_factory=failing_cuda_factory,
        )

        audio = np.zeros(16000, dtype=np.float32)
        text = engine.transcribe(audio)

        self.assertEqual(text, "Open file explorer and create new folder.")
        self.assertEqual(engine.device, "cpu")
        self.assertEqual(engine.compute_type, "int8")

    def test_multi_channel_and_type_casting(self) -> None:
        """Verify 2D and non-float32 arrays are normalized before inference."""
        engine = FasterWhisperEngine(
            model_size="base",
            models_dir=self.models_dir,
            device="cpu",
            compute_type="int8",
            model_factory=self._factory,
        )

        # 2D stereo array
        stereo_audio = np.ones((16000, 2), dtype=np.float64)
        text = engine.transcribe(stereo_audio)
        self.assertEqual(text, "Open file explorer and create new folder.")


if __name__ == "__main__":
    unittest.main()
