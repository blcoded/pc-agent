"""Dictation pipeline coordinator and state machine."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import threading
import time
from typing import Any, Callable

import numpy as np

from voice_agent.app.lifecycle import ApplicationLifecycle, DictationState
from voice_agent.app.logging import get_logger
from voice_agent.audio.recorder import AudioRecorder
from voice_agent.dictation.formatter import DictationFormatter
from voice_agent.dictation.inserter import InsertionResult, InsertionStatus, TextInserter
from voice_agent.dictation.normalizer import TextNormalizer
from voice_agent.storage.database import DatabaseManager
from voice_agent.storage.models import HistoryEntry
from voice_agent.stt.engine import SpeechToTextEngine

logger = get_logger("dictation.processor")


class DictationProcessor:
    """Coordinates audio capture, Whisper STT, normalization, formatting, and insertion."""

    def __init__(
        self,
        recorder: AudioRecorder,
        stt_engine: SpeechToTextEngine,
        db: DatabaseManager,
        normalizer: TextNormalizer | None = None,
        formatter: DictationFormatter | None = None,
        inserter: TextInserter | None = None,
        lifecycle: ApplicationLifecycle | None = None,
        language: str = "en",
        format_commands: bool = True,
        feedback_pause: float = 0.5,
        on_state_change: Callable[[DictationState], None] | None = None,
        on_transcription: Callable[[str, str], None] | None = None,
        on_no_target: Callable[[str, str], None] | None = None,
    ) -> None:
        self.recorder = recorder
        self.stt_engine = stt_engine
        self.db = db
        self.normalizer = normalizer or TextNormalizer()
        self.formatter = formatter or DictationFormatter(enabled=format_commands)
        self.inserter = inserter or TextInserter(on_no_target=on_no_target)
        self.lifecycle = lifecycle

        self.language = language
        self.format_commands = format_commands
        self.feedback_pause = feedback_pause
        self.on_state_change = on_state_change
        self.on_transcription = on_transcription
        self.on_no_target = on_no_target

        self._state = DictationState.READY
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="dictation_worker")

    @property
    def state(self) -> DictationState:
        """Current state of the dictation state machine."""
        with self._lock:
            return self._state

    def _set_state(self, new_state: DictationState) -> None:
        with self._lock:
            if self._state != new_state:
                self._state = new_state
                logger.debug("DictationProcessor state -> %s", new_state.value)
                if self.lifecycle:
                    self.lifecycle.set_dictation_state(new_state)
                if self.on_state_change:
                    try:
                        self.on_state_change(new_state)
                    except Exception as e:
                        logger.error("Error in on_state_change callback: %s", e)

    def start_listening(self, device_id: int | None = None) -> None:
        """Begin audio capture on hotkey trigger."""
        with self._lock:
            if self._state == DictationState.LISTENING:
                logger.debug("start_listening called while already listening.")
                return

            self._set_state(DictationState.LISTENING)
            try:
                self.recorder.start_recording(device_id=device_id)
            except Exception as e:
                logger.error("Failed to start audio recording: %s", e)
                self._set_state(DictationState.ERROR)
                self._set_state(DictationState.READY)

    def stop_listening(self) -> None:
        """Stop audio capture and submit audio for STT and insertion processing."""
        with self._lock:
            if self._state != DictationState.LISTENING:
                return

            self._set_state(DictationState.PROCESSING)

            try:
                audio = self.recorder.stop_recording()
            except Exception as e:
                logger.error("Error stopping audio recording: %s", e)
                self._set_state(DictationState.ERROR)
                self._set_state(DictationState.READY)
                return

            if len(audio) == 0:
                logger.debug("Empty audio buffer (click/too short); returning to READY.")
                self._set_state(DictationState.READY)
                return

            # Submit processing asynchronously to avoid blocking UI
            if self.lifecycle:
                self.lifecycle.run_async(self._process_audio, audio)
            else:
                self._executor.submit(self._process_audio, audio)

    def _process_audio(self, audio: np.ndarray) -> None:
        """Execute full pipeline: STT -> Format -> Normalize -> Insert -> History."""
        duration_sec = len(audio) / 16000.0
        try:
            # 1. Speech-to-Text
            raw_text = self.stt_engine.transcribe(audio, language=self.language).strip()
            if not raw_text:
                logger.debug("No speech recognized in audio buffer.")
                self._set_state(DictationState.READY)
                return

            # 2. Spoken Formatting Commands
            if self.format_commands:
                formatted_text = self.formatter.format(raw_text)
            else:
                formatted_text = raw_text

            # 3. Linguistic Text Normalization
            processed_text = self.normalizer.normalize(formatted_text)

            if self.on_transcription:
                try:
                    self.on_transcription(raw_text, processed_text)
                except Exception as e:
                    logger.error("Error in on_transcription callback: %s", e)

            # 4. Text Insertion
            self._set_state(DictationState.TYPING)
            result = self.inserter.insert(processed_text)

            # 5. History Record Storage
            entry = HistoryEntry(
                mode="dictation",
                raw_text=raw_text,
                processed_text=processed_text,
                status=result.status.value,
                details={
                    "duration_sec": round(duration_sec, 2),
                    "target_title": result.target_title,
                    "target_hwnd": result.target_hwnd,
                    "status_message": result.message,
                },
            )
            try:
                self.db.insert_history(entry)
            except Exception as e:
                logger.error("Failed to record dictation history: %s", e)

            # 6. Final State Transition
            if result.status == InsertionStatus.NO_TARGET:
                self._set_state(DictationState.NO_TARGET)
                if self.feedback_pause > 0:
                    time.sleep(self.feedback_pause)

            self._set_state(DictationState.READY)

        except Exception as e:
            logger.critical("Unhandled error during dictation processing: %s", e, exc_info=True)
            self._set_state(DictationState.ERROR)
            try:
                self.db.insert_history(
                    HistoryEntry(
                        mode="dictation",
                        raw_text="",
                        processed_text="",
                        status="error",
                        details={"error": str(e), "duration_sec": round(duration_sec, 2)},
                    )
                )
            except Exception:
                pass
            if self.feedback_pause > 0:
                time.sleep(self.feedback_pause)
            self._set_state(DictationState.READY)

    def shutdown(self) -> None:
        """Clean up threads and active recorder."""
        with self._lock:
            self.recorder.reset()
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._set_state(DictationState.READY)
