"""Unit tests for ring-buffered AudioRecorder."""

from types import SimpleNamespace
from typing import Any
import unittest
from unittest.mock import MagicMock

import numpy as np

from voice_agent.audio.recorder import (
    DEFAULT_SAMPLE_RATE,
    AudioRecorder,
)


class MockInputStream:
    """Mock sounddevice.InputStream for simulating audio streams."""

    def __init__(
        self,
        samplerate: int,
        channels: int,
        dtype: str,
        device: int | None,
        callback: Any,
    ) -> None:
        self.samplerate = samplerate
        self.channels = channels
        self.dtype = dtype
        self.device = device
        self.callback = callback
        self.is_active = False
        self.closed = False

    def start(self) -> None:
        self.is_active = True

    def stop(self) -> None:
        self.is_active = False

    def close(self) -> None:
        self.closed = True

    def push_data(self, data: np.ndarray) -> None:
        """Helper to simulate sounddevice delivering audio data."""
        if self.is_active and self.callback:
            self.callback(data, len(data), None, None)


class MockSoundDeviceWithStream:
    """Mock sounddevice module with InputStream factory."""

    def __init__(self) -> None:
        self.last_stream: MockInputStream | None = None

    def InputStream(
        self,
        samplerate: int,
        channels: int,
        dtype: str,
        device: int | None,
        callback: Any,
    ) -> MockInputStream:
        stream = MockInputStream(samplerate, channels, dtype, device, callback)
        self.last_stream = stream
        return stream


class TestAudioRecorder(unittest.TestCase):
    """Test suite for AudioRecorder recording lifecycle and buffer safety."""

    def setUp(self) -> None:
        self.mock_sd = MockSoundDeviceWithStream()
        self.recorder = AudioRecorder(
            sample_rate=16000,
            channels=1,
            min_duration=0.1,
            max_duration=5.0,
            sd_module=self.mock_sd,
        )

    def test_initial_state(self) -> None:
        """Verify recorder is idle upon creation."""
        self.assertFalse(self.recorder.is_recording)
        self.assertEqual(len(self.recorder.stop_recording()), 0)

    def test_normal_recording_lifecycle(self) -> None:
        """Verify starting, capturing chunks, and stopping returns proper numpy array."""
        self.recorder.start_recording(device_id=1)
        self.assertTrue(self.recorder.is_recording)
        self.assertIsNotNone(self.mock_sd.last_stream)
        stream = self.mock_sd.last_stream
        assert stream is not None

        # Simulate 0.5s of audio (8,000 samples) in two chunks
        chunk1 = np.ones((4000, 1), dtype=np.float32) * 0.25
        chunk2 = np.ones((4000, 1), dtype=np.float32) * 0.5

        stream.push_data(chunk1)
        stream.push_data(chunk2)

        audio = self.recorder.stop_recording()

        self.assertFalse(self.recorder.is_recording)
        self.assertTrue(stream.closed)
        self.assertEqual(len(audio), 8000)
        self.assertEqual(audio.dtype, np.float32)
        self.assertAlmostEqual(float(audio[0]), 0.25, places=5)
        self.assertAlmostEqual(float(audio[4000]), 0.5, places=5)

    def test_click_protection_discards_short_audio(self) -> None:
        """Verify audio shorter than min_duration (0.1s = 1600 samples) returns empty array."""
        self.recorder.start_recording()
        stream = self.mock_sd.last_stream
        assert stream is not None

        # Simulate 0.05s of audio (800 samples)
        short_chunk = np.ones((800, 1), dtype=np.float32) * 0.1
        stream.push_data(short_chunk)

        audio = self.recorder.stop_recording()
        self.assertEqual(len(audio), 0)

    def test_max_duration_cutoff_and_callback(self) -> None:
        """Verify recording clamps and auto-stops when exceeding max_duration."""
        cutoff_called = []
        recorder = AudioRecorder(
            sample_rate=16000,
            channels=1,
            min_duration=0.1,
            max_duration=0.5,  # Max 0.5s = 8000 samples
            sd_module=self.mock_sd,
            on_max_duration=lambda: cutoff_called.append(True),
        )

        recorder.start_recording()
        stream = self.mock_sd.last_stream
        assert stream is not None

        # Push 1.0s of data (16,000 samples)
        big_chunk = np.ones((16000, 1), dtype=np.float32) * 0.2
        stream.push_data(big_chunk)

        self.assertEqual(cutoff_called, [True])
        self.assertFalse(recorder.is_recording)

        audio = recorder.stop_recording()
        self.assertEqual(len(audio), 8000)  # Clamped to exactly 0.5s

    def test_audio_level_callback(self) -> None:
        """Verify on_level callback receives RMS volume levels."""
        levels: list[float] = []
        self.recorder.on_level = levels.append

        self.recorder.start_recording()
        stream = self.mock_sd.last_stream
        assert stream is not None

        # Amplitude 0.5 constant chunk has RMS = 0.5
        chunk = np.ones((1600, 1), dtype=np.float32) * 0.5
        stream.push_data(chunk)

        self.recorder.stop_recording()
        self.assertEqual(len(levels), 1)
        self.assertAlmostEqual(levels[0], 0.5, places=4)

    def test_multi_channel_flattened_to_mono(self) -> None:
        """Verify stereo input is converted to 1D mono."""
        self.recorder.start_recording()
        stream = self.mock_sd.last_stream
        assert stream is not None

        # Stereo chunk (2000 frames, 2 channels)
        stereo_chunk = np.ones((2000, 2), dtype=np.float32)
        stereo_chunk[:, 0] = 0.3
        stereo_chunk[:, 1] = 0.7

        stream.push_data(stereo_chunk)
        audio = self.recorder.stop_recording()

        self.assertEqual(audio.ndim, 1)
        self.assertEqual(len(audio), 2000)
        self.assertAlmostEqual(float(audio[0]), 0.3, places=5)

    def test_reset_aborts_recording(self) -> None:
        """Verify reset clears buffer and closes stream."""
        self.recorder.start_recording()
        stream = self.mock_sd.last_stream
        assert stream is not None

        chunk = np.ones((2000, 1), dtype=np.float32)
        stream.push_data(chunk)

        self.recorder.reset()
        self.assertFalse(self.recorder.is_recording)
        self.assertEqual(len(self.recorder.stop_recording()), 0)

    def test_set_max_duration(self) -> None:
        """Verify dynamic updating of max_duration and clamping."""
        self.recorder.set_max_duration(90.0)
        self.assertEqual(self.recorder.max_duration, 90.0)
        self.assertEqual(self.recorder._max_samples, int(90.0 * 16000))

        # Test upper cap at 150.0
        self.recorder.set_max_duration(300.0)
        self.assertEqual(self.recorder.max_duration, 150.0)
        self.assertEqual(self.recorder._max_samples, int(150.0 * 16000))

        # Test lower bound clamping to min_duration
        self.recorder.set_max_duration(0.01)
        self.assertEqual(self.recorder.max_duration, self.recorder.min_duration)


if __name__ == "__main__":
    unittest.main()

