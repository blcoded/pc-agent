"""Speech-to-Text abstraction, model management, and Whisper inference."""

from voice_agent.stt.engine import SpeechToTextEngine, TranscriptionResult
from voice_agent.stt.models import (
    DEFAULT_MODEL_NAME,
    SUPPORTED_MODELS,
    ModelInfo,
    ModelManager,
    get_default_models_dir,
)
from voice_agent.stt.whisper_engine import (
    FasterWhisperEngine,
    detect_optimal_device,
)

__all__ = [
    "SpeechToTextEngine",
    "TranscriptionResult",
    "ModelInfo",
    "ModelManager",
    "SUPPORTED_MODELS",
    "DEFAULT_MODEL_NAME",
    "get_default_models_dir",
    "FasterWhisperEngine",
    "detect_optimal_device",
]
