"""Windows clipboard format preservation, snapshot restoration, and injection."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import time
from typing import Any, Generator

from voice_agent.app.logging import get_logger

logger = get_logger("clipboard.manager")

# Standard Windows Clipboard Formats
CF_TEXT = 1
CF_BITMAP = 2
CF_DIB = 8
CF_UNICODETEXT = 13
CF_HDROP = 15
CF_DIBV5 = 17

try:
    import win32clipboard as wclip  # type: ignore[import-untyped]
    import win32con  # type: ignore[import-untyped]
except ImportError:
    wclip = None
    win32con = None


@dataclass
class ClipboardSnapshot:
    """Snapshot preserving existing clipboard formats and contents."""

    formats: dict[int, Any] = field(default_factory=dict)
    has_data: bool = False

    def is_empty(self) -> bool:
        """Return True if the snapshot contains no captured formats."""
        return not self.formats or not self.has_data


class SimulatedClipboardBackend:
    """In-memory simulated clipboard backend for non-Windows platforms or test suites."""

    def __init__(self) -> None:
        self._data: dict[int, Any] = {}
        self._is_open = False
        self.lock_attempts = 0
        self.should_simulate_lock = False

    def OpenClipboard(self) -> None:
        if self.should_simulate_lock and self.lock_attempts < 2:
            self.lock_attempts += 1
            raise RuntimeError("Clipboard locked by another process")
        self._is_open = True

    def CloseClipboard(self) -> None:
        self._is_open = False

    def EmptyClipboard(self) -> None:
        self._data.clear()

    def EnumClipboardFormats(self, current_format: int) -> int:
        formats = sorted(self._data.keys())
        if current_format == 0:
            return formats[0] if formats else 0
        try:
            idx = formats.index(current_format)
            if idx + 1 < len(formats):
                return formats[idx + 1]
        except ValueError:
            pass
        return 0

    def GetClipboardData(self, fmt: int) -> Any:
        return self._data.get(fmt)

    def SetClipboardData(self, fmt: int, data: Any) -> None:
        self._data[fmt] = data

    def IsClipboardFormatAvailable(self, fmt: int) -> bool:
        return fmt in self._data


class ClipboardManager:
    """Manages Windows clipboard preservation, restoration, and retry-based access."""

    def __init__(
        self,
        keep_in_clipboard: bool = False,
        retry_count: int = 5,
        retry_delay: float = 0.05,
        clipboard_module: Any = None,
    ) -> None:
        self.keep_in_clipboard = keep_in_clipboard
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self._clip = clipboard_module or wclip or SimulatedClipboardBackend()

    @contextmanager
    def session(self) -> Generator[Any, None, None]:
        """Context manager to safely open and close the clipboard with retries."""
        opened = False
        last_err: Exception | None = None

        for attempt in range(self.retry_count):
            try:
                self._clip.OpenClipboard()
                opened = True
                break
            except Exception as e:
                last_err = e
                time.sleep(self.retry_delay * (1.5**attempt))

        if not opened:
            logger.error("Failed to open clipboard after %d attempts: %s", self.retry_count, last_err)
            raise RuntimeError(f"Could not open Windows clipboard: {last_err}")

        try:
            yield self._clip
        finally:
            try:
                self._clip.CloseClipboard()
            except Exception as e:
                logger.debug("Error closing clipboard: %s", e)

    def create_snapshot(self) -> ClipboardSnapshot:
        """Capture and preserve all current formats on the clipboard."""
        snapshot = ClipboardSnapshot()
        try:
            with self.session() as clip:
                current_fmt = 0
                while True:
                    next_fmt = clip.EnumClipboardFormats(current_fmt)
                    if next_fmt == 0:
                        break

                    try:
                        data = clip.GetClipboardData(next_fmt)
                        if data is not None:
                            snapshot.formats[next_fmt] = data
                            snapshot.has_data = True
                    except Exception as e:
                        # Some exotic formats cannot be retrieved directly; ignore gracefully
                        logger.debug("Could not copy clipboard format %d: %s", next_fmt, e)

                    current_fmt = next_fmt
        except Exception as e:
            logger.warning("Error creating clipboard snapshot: %s", e)

        logger.debug("Clipboard snapshot created with %d formats.", len(snapshot.formats))
        return snapshot

    def restore_snapshot(self, snapshot: ClipboardSnapshot) -> bool:
        """Restore the clipboard snapshot, unless keep_in_clipboard is configured."""
        if self.keep_in_clipboard:
            logger.debug("keep_in_clipboard is True; skipping clipboard restoration.")
            return True

        if snapshot.is_empty():
            logger.debug("Snapshot is empty; clearing clipboard.")
            return self.clear()

        try:
            with self.session() as clip:
                clip.EmptyClipboard()
                for fmt, data in snapshot.formats.items():
                    try:
                        clip.SetClipboardData(fmt, data)
                    except Exception as e:
                        logger.debug("Failed restoring clipboard format %d: %s", fmt, e)
            logger.debug("Clipboard restored with %d formats.", len(snapshot.formats))
            return True
        except Exception as e:
            logger.error("Failed to restore clipboard snapshot: %s", e)
            return False

    def set_text(self, text: str) -> bool:
        """Inject text into CF_UNICODETEXT."""
        try:
            with self.session() as clip:
                clip.EmptyClipboard()
                clip.SetClipboardData(CF_UNICODETEXT, text)
            return True
        except Exception as e:
            logger.error("Failed to set clipboard text: %s", e)
            return False

    def get_text(self) -> str:
        """Retrieve text from CF_UNICODETEXT or CF_TEXT."""
        try:
            with self.session() as clip:
                if clip.IsClipboardFormatAvailable(CF_UNICODETEXT):
                    data = clip.GetClipboardData(CF_UNICODETEXT)
                    return str(data) if data is not None else ""
                if clip.IsClipboardFormatAvailable(CF_TEXT):
                    data = clip.GetClipboardData(CF_TEXT)
                    if isinstance(data, bytes):
                        return data.decode("utf-8", errors="replace")
                    return str(data) if data is not None else ""
                return ""
        except Exception as e:
            logger.error("Failed to get clipboard text: %s", e)
            return ""

    def clear(self) -> bool:
        """Clear all formats from the clipboard."""
        try:
            with self.session() as clip:
                clip.EmptyClipboard()
            return True
        except Exception as e:
            logger.error("Failed to clear clipboard: %s", e)
            return False
