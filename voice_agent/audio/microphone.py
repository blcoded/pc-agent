"""Microphone enumeration, selection, fallback handling, and hotplug monitoring."""

from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any, Callable

from voice_agent.app.logging import get_logger

logger = get_logger("audio.microphone")

try:
    import sounddevice as sd  # type: ignore[import-untyped]
except ImportError:
    sd = None


@dataclass
class AudioDeviceInfo:
    """Information describing an audio input device."""

    id: int
    name: str
    hostapi: int
    hostapi_name: str
    max_input_channels: int
    default_sample_rate: float
    is_default: bool = False

    def __str__(self) -> str:
        default_str = " (Default)" if self.is_default else ""
        return f"[{self.id}] {self.name} ({self.hostapi_name}){default_str}"


class MicrophoneManager:
    """Manages microphone enumeration, validation, fallback, and status monitoring."""

    def __init__(
        self,
        configured_device: str | int | None = None,
        on_device_changed: Callable[[AudioDeviceInfo | None], None] | None = None,
        on_fallback: Callable[[str | int, AudioDeviceInfo | None], None] | None = None,
        sd_module: Any = None,
    ) -> None:
        self._sd = sd_module or sd
        self.configured_device: str | int | None = configured_device
        self.on_device_changed = on_device_changed
        self.on_fallback = on_fallback

        self._active_device: AudioDeviceInfo | None = None
        self._monitor_thread: threading.Thread | None = None
        self._monitor_stop_event = threading.Event()
        self._lock = threading.RLock()

        # Initial resolution
        self.refresh()

    @property
    def active_device(self) -> AudioDeviceInfo | None:
        """Return the current active input device."""
        with self._lock:
            return self._active_device

    def get_input_devices(self) -> list[AudioDeviceInfo]:
        """Query and return all available audio input devices."""
        if self._sd is None:
            logger.warning("sounddevice module is not available.")
            return []

        try:
            raw_devices = self._sd.query_devices()
            host_apis = self._sd.query_hostapis()
        except Exception as e:
            logger.error("Failed to query sound devices: %s", e)
            return []

        default_input_idx: int = -1
        try:
            default_device = self._sd.default.device
            if isinstance(default_device, (list, tuple)) and len(default_device) > 0:
                default_input_idx = int(default_device[0])
            elif isinstance(default_device, int):
                default_input_idx = default_device
        except Exception:
            default_input_idx = -1

        devices: list[AudioDeviceInfo] = []

        if isinstance(raw_devices, dict):
            raw_devices = [raw_devices]

        for idx, dev in enumerate(raw_devices):
            input_channels = int(dev.get("max_input_channels", 0))
            if input_channels <= 0:
                continue

            hostapi_idx = int(dev.get("hostapi", 0))
            hostapi_name = "Unknown"
            if 0 <= hostapi_idx < len(host_apis):
                hostapi_name = host_apis[hostapi_idx].get("name", "Unknown")

            is_default = (idx == default_input_idx)
            devices.append(
                AudioDeviceInfo(
                    id=idx,
                    name=str(dev.get("name", f"Microphone {idx}")),
                    hostapi=hostapi_idx,
                    hostapi_name=hostapi_name,
                    max_input_channels=input_channels,
                    default_sample_rate=float(dev.get("default_samplerate", 16000.0)),
                    is_default=is_default,
                )
            )

        return devices

    def get_default_input_device(self) -> AudioDeviceInfo | None:
        """Find and return system default input device."""
        devices = self.get_input_devices()
        for dev in devices:
            if dev.is_default:
                return dev
        return devices[0] if devices else None

    def resolve_device(
        self, target: str | int | None = None
    ) -> tuple[AudioDeviceInfo | None, bool]:
        """Resolve a device by ID or name with automatic fallback to system default.

        Returns:
            Tuple of (resolved_device, was_fallback: bool)
        """
        devices = self.get_input_devices()
        if not devices:
            logger.warning("No audio input devices found on system.")
            return None, False

        # If no target specified, use system default
        if target is None or target == "" or target == "default":
            default_dev = self.get_default_input_device()
            return default_dev, False

        # Match by integer ID
        if isinstance(target, int):
            for dev in devices:
                if dev.id == target:
                    return dev, False

        # Match by integer ID represented as string
        if isinstance(target, str) and target.isdigit():
            target_int = int(target)
            for dev in devices:
                if dev.id == target_int:
                    return dev, False

        # Match by name (exact or case-insensitive substring)
        if isinstance(target, str):
            target_lower = target.lower()
            # Exact match first
            for dev in devices:
                if dev.name.lower() == target_lower:
                    return dev, False
            # Substring match
            for dev in devices:
                if target_lower in dev.name.lower():
                    return dev, False

        # Fallback to default
        fallback_dev = self.get_default_input_device()
        logger.warning(
            "Configured microphone '%s' not found. Falling back to default: %s",
            target,
            fallback_dev,
        )
        return fallback_dev, True

    def set_device(self, device: str | int | None) -> AudioDeviceInfo | None:
        """Update configured microphone and resolve active device."""
        with self._lock:
            self.configured_device = device
            return self.refresh()

    def refresh(self) -> AudioDeviceInfo | None:
        """Re-scan devices and update active microphone."""
        with self._lock:
            old_device = self._active_device
            resolved, was_fallback = self.resolve_device(self.configured_device)

            if was_fallback and self.configured_device is not None:
                if self.on_fallback:
                    try:
                        self.on_fallback(self.configured_device, resolved)
                    except Exception as e:
                        logger.error("Error in on_fallback callback: %s", e)

            device_changed = (
                (old_device is None and resolved is not None)
                or (old_device is not None and resolved is None)
                or (old_device is not None and resolved is not None and old_device.id != resolved.id)
            )

            self._active_device = resolved

            if device_changed and self.on_device_changed:
                try:
                    self.on_device_changed(resolved)
                except Exception as e:
                    logger.error("Error in on_device_changed callback: %s", e)

            return resolved

    def start_monitoring(self, interval_seconds: float = 2.0) -> None:
        """Start background polling thread to detect device connection changes."""
        with self._lock:
            if self._monitor_thread and self._monitor_thread.is_alive():
                return

            self._monitor_stop_event.clear()

            def _monitor_loop() -> None:
                last_device_ids = {d.id for d in self.get_input_devices()}
                while not self._monitor_stop_event.wait(interval_seconds):
                    current_devices = self.get_input_devices()
                    current_ids = {d.id for d in current_devices}
                    if current_ids != last_device_ids:
                        logger.info("Audio input device configuration changed. Refreshing...")
                        last_device_ids = current_ids
                        self.refresh()

            self._monitor_thread = threading.Thread(
                target=_monitor_loop,
                name="audio_hotplug_monitor",
                daemon=True,
            )
            self._monitor_thread.start()
            logger.debug("Microphone hot-plug monitor started.")

    def stop_monitoring(self) -> None:
        """Stop background device monitoring."""
        with self._lock:
            if self._monitor_thread:
                self._monitor_stop_event.set()
                self._monitor_thread.join(timeout=2.0)
                self._monitor_thread = None
                logger.debug("Microphone hot-plug monitor stopped.")
