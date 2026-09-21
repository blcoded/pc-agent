"""Audio recording, input device management, and buffer capture package."""

from voice_agent.audio.microphone import AudioDeviceInfo, MicrophoneManager
from voice_agent.audio.recorder import (
    DEFAULT_CHANNELS,
    DEFAULT_SAMPLE_RATE,
    MAX_DURATION_SECONDS,
    MIN_DURATION_SECONDS,
    AudioRecorder,
)

__all__ = [
    "AudioDeviceInfo",
    "MicrophoneManager",
    "AudioRecorder",
    "DEFAULT_SAMPLE_RATE",
    "DEFAULT_CHANNELS",
    "MIN_DURATION_SECONDS",
    "MAX_DURATION_SECONDS",
]
