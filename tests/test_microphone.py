"""Unit tests for microphone enumeration and fallback management."""

from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from voice_agent.audio.microphone import AudioDeviceInfo, MicrophoneManager


class MockSoundDevice:
    """Mock sounddevice module for deterministic unit testing."""

    def __init__(self, devices: list[dict] | None = None, default_device: tuple[int, int] = (1, 0)) -> None:
        self._devices = devices if devices is not None else [
            {
                "name": "Speakers (Realtek Audio)",
                "hostapi": 0,
                "max_input_channels": 0,
                "max_output_channels": 2,
                "default_samplerate": 48000.0,
            },
            {
                "name": "Microphone (Realtek Audio)",
                "hostapi": 0,
                "max_input_channels": 2,
                "max_output_channels": 0,
                "default_samplerate": 48000.0,
            },
            {
                "name": "Headset Mic (HyperX Cloud)",
                "hostapi": 1,
                "max_input_channels": 1,
                "max_output_channels": 0,
                "default_samplerate": 44100.0,
            },
            {
                "name": "Headset Earphone (HyperX Cloud)",
                "hostapi": 1,
                "max_input_channels": 0,
                "max_output_channels": 2,
                "default_samplerate": 44100.0,
            },
        ]
        self._hostapis = [
            {"name": "MME", "devices": [0, 1]},
            {"name": "Windows WASAPI", "devices": [2, 3]},
        ]
        self.default = SimpleNamespace(device=default_device)

    def query_devices(self) -> list[dict]:
        return list(self._devices)

    def query_hostapis(self) -> list[dict]:
        return list(self._hostapis)

    def set_devices(self, devices: list[dict]) -> None:
        self._devices = devices


class TestMicrophoneManager(unittest.TestCase):
    """Test suite for MicrophoneManager device resolution, enumeration, and fallback."""

    def setUp(self) -> None:
        self.mock_sd = MockSoundDevice()

    def test_enumeration_filters_input_devices_and_marks_default(self) -> None:
        """Verify only devices with max_input_channels > 0 are enumerated."""
        manager = MicrophoneManager(sd_module=self.mock_sd)
        devices = manager.get_input_devices()

        self.assertEqual(len(devices), 2)
        # Device 1: Microphone (Realtek Audio)
        self.assertEqual(devices[0].id, 1)
        self.assertEqual(devices[0].name, "Microphone (Realtek Audio)")
        self.assertEqual(devices[0].hostapi_name, "MME")
        self.assertTrue(devices[0].is_default)

        # Device 2: Headset Mic (HyperX Cloud)
        self.assertEqual(devices[1].id, 2)
        self.assertEqual(devices[1].name, "Headset Mic (HyperX Cloud)")
        self.assertEqual(devices[1].hostapi_name, "Windows WASAPI")
        self.assertFalse(devices[1].is_default)

    def test_resolve_default_device(self) -> None:
        """Verify resolving None or empty returns default without fallback flag."""
        manager = MicrophoneManager(sd_module=self.mock_sd)
        dev, was_fallback = manager.resolve_device(None)

        self.assertIsNotNone(dev)
        assert dev is not None
        self.assertEqual(dev.id, 1)
        self.assertFalse(was_fallback)

    def test_resolve_device_by_id(self) -> None:
        """Verify resolving device by integer and numeric string ID."""
        manager = MicrophoneManager(sd_module=self.mock_sd)

        dev_int, was_fallback_int = manager.resolve_device(2)
        self.assertIsNotNone(dev_int)
        assert dev_int is not None
        self.assertEqual(dev_int.id, 2)
        self.assertFalse(was_fallback_int)

        dev_str, was_fallback_str = manager.resolve_device("2")
        self.assertIsNotNone(dev_str)
        assert dev_str is not None
        self.assertEqual(dev_str.id, 2)
        self.assertFalse(was_fallback_str)

    def test_resolve_device_by_name(self) -> None:
        """Verify resolving device by exact name and case-insensitive substring."""
        manager = MicrophoneManager(sd_module=self.mock_sd)

        # Substring match
        dev, was_fallback = manager.resolve_device("hyperx")
        self.assertIsNotNone(dev)
        assert dev is not None
        self.assertEqual(dev.id, 2)
        self.assertFalse(was_fallback)

        # Exact match
        dev_exact, was_fallback_exact = manager.resolve_device("Microphone (Realtek Audio)")
        self.assertIsNotNone(dev_exact)
        assert dev_exact is not None
        self.assertEqual(dev_exact.id, 1)
        self.assertFalse(was_fallback_exact)

    def test_fallback_when_device_not_found(self) -> None:
        """Verify missing device falls back to system default and triggers callback."""
        fallback_calls: list[tuple[str | int, AudioDeviceInfo | None]] = []

        def on_fallback(target: str | int, fb_dev: AudioDeviceInfo | None) -> None:
            fallback_calls.append((target, fb_dev))

        manager = MicrophoneManager(
            configured_device="NonExistentMicrophone",
            on_fallback=on_fallback,
            sd_module=self.mock_sd,
        )

        active = manager.active_device
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active.id, 1)  # Default mic
        self.assertEqual(len(fallback_calls), 1)
        self.assertEqual(fallback_calls[0][0], "NonExistentMicrophone")
        self.assertEqual(fallback_calls[0][1].id, 1)

    def test_device_change_notification(self) -> None:
        """Verify on_device_changed callback is called when switching microphones."""
        changed_devices: list[AudioDeviceInfo | None] = []

        manager = MicrophoneManager(sd_module=self.mock_sd)
        manager.on_device_changed = changed_devices.append

        manager.set_device(2)
        self.assertEqual(len(changed_devices), 1)
        assert changed_devices[0] is not None
        self.assertEqual(changed_devices[0].id, 2)

    def test_monitoring_start_and_stop(self) -> None:
        """Verify monitoring thread lifecycle."""
        manager = MicrophoneManager(sd_module=self.mock_sd)
        manager.start_monitoring(interval_seconds=0.05)
        self.assertIsNotNone(manager._monitor_thread)
        self.assertTrue(manager._monitor_thread.is_alive())

        manager.stop_monitoring()
        self.assertIsNone(manager._monitor_thread)

    def test_empty_devices_handled_gracefully(self) -> None:
        """Verify no crashes when sounddevice returns no input devices."""
        empty_sd = MockSoundDevice(devices=[])
        manager = MicrophoneManager(sd_module=empty_sd)

        devices = manager.get_input_devices()
        self.assertEqual(devices, [])

        dev, was_fallback = manager.resolve_device("some_mic")
        self.assertIsNone(dev)
        self.assertFalse(was_fallback)


if __name__ == "__main__":
    unittest.main()
