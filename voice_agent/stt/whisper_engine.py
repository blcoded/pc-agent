"""Local Speech-to-Text inference engine utilizing faster-whisper (CTranslate2)."""

from __future__ import annotations

import gc
from pathlib import Path
import threading
from typing import Any

import numpy as np

from voice_agent.app.logging import get_logger
from voice_agent.stt.engine import SpeechToTextEngine, TranscriptionResult
from voice_agent.stt.models import ModelManager, get_default_models_dir

logger = get_logger("stt.whisper")

try:
    from faster_whisper import WhisperModel  # type: ignore[import-untyped]
except ImportError:
    WhisperModel = None

try:
    import ctranslate2  # type: ignore[import-untyped]
except ImportError:
    ctranslate2 = None


def detect_optimal_device() -> tuple[str, str]:
    """Detect whether CUDA is available and select optimal device and compute type.

    Returns:
        Tuple of (device: 'cuda' | 'cpu', compute_type: 'float16' | 'int8')
    """
    if ctranslate2 is not None:
        try:
            if ctranslate2.get_cuda_device_count() > 0:
                # CUDA GPU available: use CUDA with float16 for maximum throughput
                logger.info("CUDA device detected. Using GPU with float16 compute type.")
                return "cuda", "float16"
        except Exception as e:
            logger.debug("Failed to query CUDA devices: %s", e)

    # CPU fallback: use 8-bit quantization for optimal CPU speed and low RAM footprint
    logger.info("Using CPU with int8 quantization compute type.")
    return "cpu", "int8"


class FasterWhisperEngine(SpeechToTextEngine):
    """Local offline STT engine using faster-whisper CTranslate2 backend."""

    def __init__(
        self,
        model_size: str = "base",
        models_dir: Path | None = None,
        device: str = "auto",
        compute_type: str = "auto",
        beam_size: int = 1,
        temperature: float = 0.0,
        cpu_threads: int = 4,
        num_workers: int = 1,
        model_factory: Any = None,
    ) -> None:
        self.model_size = model_size.lower().strip()
        self.models_dir = models_dir or get_default_models_dir()
        self.model_manager = ModelManager(self.models_dir)

        # Device and compute resolution
        if device == "auto" or compute_type == "auto":
            opt_device, opt_compute = detect_optimal_device()
            self.device = opt_device if device == "auto" else device
            self.compute_type = opt_compute if compute_type == "auto" else compute_type
        else:
            self.device = device
            self.compute_type = compute_type

        self.beam_size = beam_size
        self.temperature = temperature
        self.cpu_threads = cpu_threads
        self.num_workers = num_workers

        self._model_factory = model_factory or WhisperModel
        self._model: Any = None
        self._lock = threading.RLock()

    @property
    def is_loaded_property(self) -> bool:
        """Property indicating if the model is currently in memory."""
        with self._lock:
            return self._model is not None

    def is_loaded(self) -> bool:
        """Return True if model is initialized and ready for inference."""
        with self._lock:
            return self._model is not None

    def load_model(self) -> None:
        """Load or warm up the Whisper model weights into memory."""
        with self._lock:
            if self._model is not None:
                return

            if self._model_factory is None:
                raise RuntimeError(
                    "faster-whisper is not installed. Please install 'faster-whisper' package."
                )

            model_dir = self.model_manager.get_model_path(self.model_size)
            model_source = str(model_dir) if self.model_manager.is_model_available(self.model_size) else self.model_size

            logger.info(
                "Loading Whisper model '%s' (device=%s, compute_type=%s, threads=%d)...",
                self.model_size,
                self.device,
                self.compute_type,
                self.cpu_threads,
            )

            try:
                self._model = self._model_factory(
                    model_source,
                    device=self.device,
                    compute_type=self.compute_type,
                    cpu_threads=self.cpu_threads,
                    num_workers=self.num_workers,
                    download_root=str(self.models_dir),
                )
                logger.info("Whisper model '%s' loaded successfully.", self.model_size)
            except Exception as e:
                # If CUDA failed (e.g. OOM or driver issue), automatically fall back to CPU
                if self.device == "cuda":
                    logger.warning(
                        "Failed to load model on CUDA (%s). Falling back to CPU with int8...",
                        e,
                    )
                    self.device = "cpu"
                    self.compute_type = "int8"
                    self._model = self._model_factory(
                        model_source,
                        device="cpu",
                        compute_type="int8",
                        cpu_threads=self.cpu_threads,
                        num_workers=self.num_workers,
                        download_root=str(self.models_dir),
                    )
                    logger.info("Model loaded successfully on CPU fallback.")
                else:
                    logger.error("Failed to load Whisper model: %s", e)
                    raise

    def unload_model(self) -> None:
        """Release Whisper model from memory and trigger garbage collection."""
        with self._lock:
            if self._model is not None:
                logger.info("Unloading Whisper model '%s' from memory...", self.model_size)
                del self._model
                self._model = None
                gc.collect()

    def transcribe(self, audio: np.ndarray, language: str | None = "en") -> str:
        """Transcribe audio into normalized text.

        Args:
            audio: 1D numpy array of 16kHz mono float32 audio.
            language: Target ISO language code (default 'en').

        Returns:
            The transcribed text string.
        """
        result = self.transcribe_detailed(audio, language=language)
        return result.text

    def transcribe_detailed(
        self, audio: np.ndarray, language: str | None = "en"
    ) -> TranscriptionResult:
        """Perform inference and return detailed transcript metadata.

        Args:
            audio: 1D numpy array of 16kHz mono float32 audio.
            language: Target ISO language code.

        Returns:
            TranscriptionResult object with segments and duration.
        """
        with self._lock:
            # 1. Validate audio input
            if audio is None or len(audio) == 0:
                logger.debug("Received empty audio array for transcription.")
                return TranscriptionResult(text="", language=language or "en", duration=0.0)

            # Ensure 1D float32 array
            if not isinstance(audio, np.ndarray):
                audio = np.asarray(audio, dtype=np.float32)

            if audio.ndim > 1:
                audio = audio[:, 0]

            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            duration = len(audio) / 16000.0

            # 2. Ensure model is loaded
            if self._model is None:
                self.load_model()

            # 3. Perform inference with error recovery
            try:
                return self._run_inference(audio, language, duration)
            except RuntimeError as e:
                # Check for CUDA OOM during inference
                err_msg = str(e).lower()
                if "out of memory" in err_msg or "cuda" in err_msg:
                    logger.warning("CUDA error during transcription (%s). Recovering on CPU...", e)
                    self.device = "cpu"
                    self.compute_type = "int8"
                    self.unload_model()
                    self.load_model()
                    return self._run_inference(audio, language, duration)
                raise

    def _run_inference(
        self, audio: np.ndarray, language: str | None, duration: float
    ) -> TranscriptionResult:
        """Execute faster-whisper transcribe call."""
        segments_raw, info = self._model.transcribe(
            audio,
            language=language,
            beam_size=self.beam_size,
            temperature=self.temperature,
            vad_filter=True,
        )

        segment_list: list[dict[str, Any]] = []
        collected_text: list[str] = []

        for seg in segments_raw:
            text = seg.text.strip()
            if text:
                collected_text.append(text)
                segment_list.append(
                    {
                        "start": getattr(seg, "start", 0.0),
                        "end": getattr(seg, "end", 0.0),
                        "text": text,
                        "avg_logprob": getattr(seg, "avg_logprob", 0.0),
                        "no_speech_prob": getattr(seg, "no_speech_prob", 0.0),
                    }
                )

        full_text = " ".join(collected_text).strip()
        detected_language = getattr(info, "language", language or "en")

        return TranscriptionResult(
            text=full_text,
            language=detected_language,
            duration=duration,
            segments=segment_list,
        )
