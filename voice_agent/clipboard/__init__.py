"""Windows clipboard preservation, restoration, and management package."""

from voice_agent.clipboard.manager import (
    CF_BITMAP,
    CF_DIB,
    CF_TEXT,
    CF_UNICODETEXT,
    ClipboardManager,
    ClipboardSnapshot,
    SimulatedClipboardBackend,
)

__all__ = [
    "ClipboardManager",
    "ClipboardSnapshot",
    "SimulatedClipboardBackend",
    "CF_UNICODETEXT",
    "CF_TEXT",
    "CF_BITMAP",
    "CF_DIB",
]
