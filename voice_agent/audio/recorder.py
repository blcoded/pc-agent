"""In-memory ring-buffered audio recorder for speech capture and STT processing."""

from __future__ import annotations

import logging
import math
import threading
from typing import Any, Callable

import numpy as np

from voice_agent.app.logging import get_logger

logger = get_logger("audio.recorder")

try:
    import sounddevice as sd  # type: ignore[import-untyped]
except ImportError:
    sd = None

DEFAULT_SAMPLE_RATE: int = 16000
DEFAULT_CHANNELS: int = 1
MIN_DURATION_SECONDS: float = 0.1
MAX_DURATION_SECONDS: float = 60.0


class AudioRecorder:
    """Non-blocking, ring-buffered audio capture into memory for Whisper STT.

    Audio format: 16kHz mono 32-bit float array normalized to [-1.0, 1.0].
    Zero persistent disk writes by default.
    """

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        min_duration: float = MIN_DURATION_SECONDS,
        max_duration: float = MAX_DURATION_SECONDS,
        sd_module: Any = None,
        on_level: Callable[[float], None] | None = None,
        on_max_duration: Callable[[], None] | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.min_duration = min_duration
        self.max_duration = max_duration
        self._sd = sd_module or sd

        self.on_level = on_level
        self.on_max_duration = on_max_duration

        self._lock = threading.RLock()
        self._is_recording: bool = False
        self._stream: Any = None
        self._chunks: list[np.ndarray] = []
        self._total_samples: int = 0
        self._max_samples: int = int(self.max_duration * self.sample_rate)
        self._min_samples: int = int(self.min_duration * self.sample_rate)

    @property
    def is_recording(self) -> bool:
        """Return True if currently capturing audio."""
        with self._lock:
            return self._is_recording

    def start_recording(self, device_id: int | None = None) -> None:
        """Begin non-blocking audio capture from the specified or default input device."""
        with self._lock:
            if self._is_recording:
                logger.warning("start_recording called while already recording.")
                return

            if self._sd is None:
                raise RuntimeError("sounddevice is not available.")

            self._chunks.clear()
            self._total_samples = 0
            self._is_recording = True

            try:
                self._stream = self._sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype="float32",
                    device=device_id,
                    callback=self._audio_callback,
                )
                self._stream.start()
                logger.debug(
                    "Audio recording started on device %s (sample_rate=%d, channels=%d)",
                    device_id,
                    self.sample_rate,
                    self.channels,
                )
            except Exception as e:
                self._is_recording = False
                logger.error("Failed to start audio stream: %s", e)
                raise

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        """Internal callback invoked by sounddevice for each captured buffer chunk."""
        if status:
            logger.warning("sounddevice stream status: %s", status)

        with self._lock:
            if not self._is_recording:
                return

            # Flatten to 1D mono float32 array
            if indata.ndim > 1:
                chunk = indata[:, 0].astype(np.float32)
            else:
                chunk = indata.astype(np.float32)

            chunk_len = len(chunk)

            # Safety check: enforce max duration limit
            if self._total_samples + chunk_len > self._max_samples:
                allowed = max(0, self._max_samples - self._total_samples)
                if allowed > 0:
                    self._chunks.append(chunk[:allowed])
                    self._total_samples += allowed
                logger.warning(
                    "Audio recording reached max duration limit (%.1fs). Auto-stopping.",
                    self.max_duration,
                )
                self._is_recording = False
                if self.on_max_duration:
                    try:
                        self.on_max_duration()
                    except Exception as e:
                        logger.error("Error in on_max_duration callback: %s", e)
                return

            self._chunks.append(chunk.copy())
            self._total_samples += chunk_len

            # Calculate audio RMS level for VU meter / audio activity indicator
            if self.on_level and chunk_len > 0:
                try:
                    rms = float(np.sqrt(np.mean(chunk**2)))
                    self.on_level(rms)
                except Exception as e:
                    logger.debug("Error computing RMS level: %s", e)

    def stop_recording(self) -> np.ndarray:
        """Stop capturing audio and return the captured audio as a 1D float32 numpy array.

        Returns:
            np.ndarray: Audio data. Empty array if duration is less than min_duration (click protection).
        """
        with self._lock:
            if not self._is_recording and self._stream is None and not self._chunks:
                logger.debug("stop_recording called with no active recording.")
                return np.zeros(0, dtype=np.float32)

            self._is_recording = False

            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as e:
                    logger.error("Error closing audio stream: %s", e)
                finally:
                    self._stream = None

            if not self._chunks:
                logger.debug("No audio chunks captured.")
                return np.zeros(0, dtype=np.float32)

            audio = np.concatenate(self._chunks, axis=0)
            self._chunks.clear()

            duration = len(audio) / self.sample_rate
            logger.debug("Audio recording stopped. Duration: %.3fs (%d samples)", duration, len(audio))

            # Minimum audio length protection (ignore clicks / accidental taps)
            if len(audio) < self._min_samples:
                logger.debug(
                    "Audio duration %.3fs is below minimum threshold %.3fs (discarded as click/noise).",
                    duration,
                    self.min_duration,
                )
                return np.zeros(0, dtype=np.float32)

            # Maximum duration clamp
            if len(audio) > self._max_samples:
                audio = audio[: self._max_samples]

            return audio

    def reset(self) -> None:
        """Stop recording and clear all internal buffers."""
        with self._lock:
            self._is_recording = False
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            self._chunks.clear()
            self._total_samples = 0
