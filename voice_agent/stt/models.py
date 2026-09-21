"""Whisper model specifications, local cache management, and tradeoff metrics."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import Any

from voice_agent.app.config import get_default_config_dir
from voice_agent.app.logging import get_logger

logger = get_logger("stt.models")


@dataclass(frozen=True)
class ModelInfo:
    """Metadata describing a Whisper model profile and hardware tradeoffs."""

    name: str
    display_name: str
    size_mb: int
    estimated_ram_mb: int
    speed_rating: str
    accuracy_rating: str
    description: str
    is_default: bool = False


# Supported local Whisper models
SUPPORTED_MODELS: dict[str, ModelInfo] = {
    "tiny": ModelInfo(
        name="tiny",
        display_name="Tiny (Fastest / Lowest RAM)",
        size_mb=75,
        estimated_ram_mb=400,
        speed_rating="Very Fast",
        accuracy_rating="Fair",
        description="Fastest execution and minimal memory usage. Recommended for low-spec PCs.",
    ),
    "base": ModelInfo(
        name="base",
        display_name="Base (Balanced - Recommended)",
        size_mb=145,
        estimated_ram_mb=600,
        speed_rating="Fast",
        accuracy_rating="Good",
        description="Default balanced model offering quick response times and good accuracy.",
        is_default=True,
    ),
    "small": ModelInfo(
        name="small",
        display_name="Small (Higher Accuracy)",
        size_mb=480,
        estimated_ram_mb=1500,
        speed_rating="Moderate",
        accuracy_rating="High",
        description="Significantly improved vocabulary and accent accuracy with moderate resource requirements.",
    ),
    "medium": ModelInfo(
        name="medium",
        display_name="Medium (Maximum Accuracy)",
        size_mb=1500,
        estimated_ram_mb=3500,
        speed_rating="Slow",
        accuracy_rating="Very High",
        description="Maximum transcription precision. Requires powerful CPU or dedicated GPU.",
    ),
}

DEFAULT_MODEL_NAME = "base"


def get_default_models_dir() -> Path:
    """Return default directory where Whisper models are cached."""
    return get_default_config_dir() / "models"


class ModelManager:
    """Manages Whisper model directory storage, presence verification, and metadata queries."""

    def __init__(self, models_dir: Path | None = None) -> None:
        self.models_dir = models_dir or get_default_models_dir()
        self.models_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def list_supported_models() -> list[ModelInfo]:
        """Return list of all supported model specifications."""
        return list(SUPPORTED_MODELS.values())

    @staticmethod
    def get_model_info(model_name: str) -> ModelInfo:
        """Get specifications for a named model or raise ValueError if unsupported."""
        clean_name = model_name.lower().strip()
        if clean_name not in SUPPORTED_MODELS:
            raise ValueError(
                f"Unsupported model '{model_name}'. Supported models: {list(SUPPORTED_MODELS.keys())}"
            )
        return SUPPORTED_MODELS[clean_name]

    def get_model_path(self, model_name: str) -> Path:
        """Return the target directory path for a model."""
        clean_name = model_name.lower().strip()
        return self.models_dir / clean_name

    def is_model_available(self, model_name: str) -> bool:
        """Check if model files are cached locally."""
        model_dir = self.get_model_path(model_name)
        if not model_dir.is_dir():
            return False

        # Verify essential model files exist and are non-empty
        # faster-whisper CTranslate2 model files typically include model.bin and config.json
        expected_files = ["model.bin", "config.json"]
        found = 0
        for f in expected_files:
            file_path = model_dir / f
            if file_path.is_file() and file_path.stat().st_size > 0:
                found += 1

        # Consider available if at least model.bin or custom weights exist
        return found > 0 or any(model_dir.glob("*.bin"))

    def compute_file_checksum(self, file_path: Path) -> str:
        """Compute SHA-256 checksum of a file."""
        if not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                sha256.update(chunk)
        return sha256.hexdigest()

    def get_model_status(self, model_name: str) -> dict[str, Any]:
        """Return comprehensive status information for a model."""
        info = self.get_model_info(model_name)
        model_dir = self.get_model_path(model_name)
        is_cached = self.is_model_available(model_name)

        total_bytes = 0
        file_count = 0
        if model_dir.is_dir():
            for root, _, files in os.walk(model_dir):
                for file in files:
                    fp = Path(root) / file
                    try:
                        total_bytes += fp.stat().st_size
                        file_count += 1
                    except OSError:
                        pass

        return {
            "name": info.name,
            "display_name": info.display_name,
            "size_mb": info.size_mb,
            "estimated_ram_mb": info.estimated_ram_mb,
            "speed_rating": info.speed_rating,
            "accuracy_rating": info.accuracy_rating,
            "is_default": info.is_default,
            "is_available": is_cached,
            "path": str(model_dir),
            "cached_bytes": total_bytes,
            "cached_files": file_count,
        }
