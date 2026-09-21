"""Abstract Speech-to-Text (STT) engine interface and data models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class TranscriptionResult:
    """Detailed result produced by an STT engine."""

    text: str
    language: str = "en"
    duration: float = 0.0
    segments: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0


class SpeechToTextEngine(ABC):
    """Abstract interface defining the contract for local speech-to-text inference engines."""

    @abstractmethod
    def transcribe(self, audio: np.ndarray, language: str | None = None) -> str:
        """Transcribe a 16kHz mono float32 audio array into text.

        Args:
            audio: 1D numpy array containing 16kHz mono float32 samples in [-1.0, 1.0].
            language: ISO language code (e.g. 'en') or None for default/auto.

        Returns:
            The transcribed text as a string.
        """
        raise NotImplementedError

    @abstractmethod
    def is_loaded(self) -> bool:
        """Return True if the underlying model is loaded in memory and ready for inference."""
        raise NotImplementedError

    def load_model(self) -> None:
        """Explicitly load or warm-up the STT model."""
        pass

    def unload_model(self) -> None:
        """Release model weights and clear GPU/CPU memory."""
        pass
