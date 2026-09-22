"""Application entry point for PC Voice Agent."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from typing import Any

from voice_agent.app.config import AppConfig, load_config
from voice_agent.app.lifecycle import (
    ApplicationLifecycle,
    ControlState,
    DictationState,
    SingleInstanceLock,
)
from voice_agent.app.logging import get_logger, setup_logging
from voice_agent.audio.microphone import MicrophoneManager
from voice_agent.audio.recorder import AudioRecorder
from voice_agent.clipboard.manager import ClipboardManager
from voice_agent.control.command_router import CommandRouter
from voice_agent.dictation.inserter import TextInserter
from voice_agent.dictation.processor import DictationProcessor
from voice_agent.input.hotkeys import HotkeyManager
from voice_agent.storage.database import DatabaseManager
from voice_agent.storage.history import HistoryRepository
from voice_agent.stt.whisper_engine import FasterWhisperEngine
from voice_agent.ui.history import HistoryViewerWindow
from voice_agent.ui.overlay import FloatingStatusOverlay
from voice_agent.ui.settings import SettingsDialog
from voice_agent.ui.tray import SystemTrayManager

logger = get_logger("main")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Windows Local Voice Agent")
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="Start minimized directly to the system tray without showing overlay",
    )
    parser.add_argument(
        "--offscreen",
        action="store_true",
        help="Run Qt application in offscreen headless mode (for testing)",
    )
    return parser.parse_args()


def main() -> int:
    """Main application execution sequence."""
    args = parse_args()

    # Configure offscreen Qt platform if requested (useful for headless/CI runs)
    if args.offscreen or os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    # 1. Single Instance Check
    lock = SingleInstanceLock()
    if not lock.acquire():
        print(
            "PC Voice Agent is already running! Check your system tray (notification area near the clock).",
            file=sys.stderr,
        )
        return 1

    # 2. Setup Logging and Configuration
    setup_logging()
    config = load_config()
    logger.info("Starting PC Voice Agent v0.1.0...")

    # 3. Core Storage & Lifecycle
    db = DatabaseManager()
    history_repo = HistoryRepository(db=db)
    lifecycle = ApplicationLifecycle(config=config, db=db, enable_logging=False)

    # 4. Clipboard and Text Inserter
    clipboard = ClipboardManager()

    # 5. Microphone Resolution
    mic_manager = MicrophoneManager(configured_device=config.audio.microphone)
    active_mic = mic_manager.active_device
    active_device_id: int | None = active_mic.id if active_mic else None
    logger.info("Active input microphone: %s (id=%s)", active_mic, active_device_id)

    # 6. Speech-to-Text Engine
    stt_engine = FasterWhisperEngine(model_size=config.dictation.model)

    # Pre-warm Whisper model asynchronously on startup so first speech inference is instant
    if not args.offscreen:
        lifecycle.run_async(stt_engine.load_model)

    # 7. Initialize PySide6 Application & UI
    try:
        from PySide6.QtCore import QCoreApplication, QObject, Qt, Signal
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        app.setApplicationName("PC Voice Agent")
        app.setOrganizationName("PCVoiceAgent")
        app.setQuitOnLastWindowClosed(False)  # Keep running in system tray

        # Register cleanup on Qt application aboutToQuit
        app.aboutToQuit.connect(lifecycle.shutdown)

        # Thread-safe Confirmation Dialog Bridge for background control worker
        class ConfirmationBridge(QObject):
            request_confirm = Signal(object, object, object)

            def __init__(self) -> None:
                super().__init__()
                self.request_confirm.connect(self._on_confirm)

            def _on_confirm(self, action: Any, event: Any, res_dict: dict[str, Any]) -> None:
                try:
                    from voice_agent.ui.confirmation import request_user_confirmation

                    res_dict["confirmed"] = request_user_confirmation(action)
                except Exception as err:
                    logger.error("Error displaying confirmation dialog: %s", err)
                    res_dict["confirmed"] = False
                finally:
                    event.set()

            def ask(self, action: Any) -> bool:
                if args.offscreen:
                    return True
                evt = threading.Event()
                res: dict[str, Any] = {"confirmed": False}
                self.request_confirm.emit(action, evt, res)
                evt.wait()
                return bool(res.get("confirmed", False))

        bridge = ConfirmationBridge()
        confirm_handler = bridge.ask

        # 8. Floating Status Overlay Widget
        overlay = FloatingStatusOverlay(config=config)
        lifecycle.subscribe_dictation_state(overlay.set_dictation_state)
        lifecycle.subscribe_control_state(overlay.set_control_state)

        # 9. Audio Recorder (connected to overlay audio level meter)
        recorder = AudioRecorder(
            sample_rate=config.audio.sample_rate,
            channels=config.audio.channels,
            on_level=overlay.set_audio_level,
        )

        # 10. Inserter with Fallback Notification
        inserter = TextInserter(
            clipboard_manager=clipboard,
            on_no_target=lambda title, msg: tray.show_notification(
                title, msg, icon_type="warning"
            )
            if tray
            else None,
        )

        # 11. Dictation Processor Coordinator
        dictation_processor = DictationProcessor(
            recorder=recorder,
            stt_engine=stt_engine,
            db=db,
            inserter=inserter,
            lifecycle=lifecycle,
            language=config.dictation.language,
            format_commands=config.dictation.format_commands,
        )

        # 12. Command Router for Control Mode
        command_router = CommandRouter(
            database=db,
            confirm_handler=confirm_handler,
            confirm_medium=config.control.confirm_medium,
            confirm_high=config.control.confirm_high,
        )

        # 13. History Window & Settings Dialog
        history_window = HistoryViewerWindow(repository=history_repo, clipboard=clipboard)

        def on_settings_applied(new_config: AppConfig) -> None:
            nonlocal config, active_device_id
            config = new_config
            mic_manager.set_device(new_config.audio.microphone)
            new_active_mic = mic_manager.active_device
            active_device_id = new_active_mic.id if new_active_mic else None
            logger.info("Microphone updated via settings: %s (id=%s)", new_active_mic, active_device_id)

            hotkey_manager.reconfigure(
                dictation_hotkey=new_config.dictation.hotkey,
                control_hotkey=new_config.control.hotkey,
                dictation_mode=new_config.dictation.mode,
                control_mode=new_config.control.mode,
            )
            dictation_processor.language = new_config.dictation.language
            dictation_processor.format_commands = new_config.dictation.format_commands
            command_router.confirm_medium = new_config.control.confirm_medium
            command_router.confirm_high = new_config.control.confirm_high
            if new_config.ui.overlay_enabled and not args.minimized:
                overlay.show()
            elif not new_config.ui.overlay_enabled:
                overlay.hide()

        settings_dialog = SettingsDialog(
            config=config,
            mic_manager=mic_manager,
            on_applied=on_settings_applied,
        )

        # 14. System Tray Manager
        def toggle_overlay() -> None:
            if overlay.isVisible():
                overlay.hide()
            else:
                overlay.show()

        def open_history() -> None:
            history_window.refresh_data()
            history_window.show()
            history_window.raise_()
            history_window.activateWindow()

        def open_settings() -> None:
            settings_dialog.show()
            settings_dialog.raise_()
            settings_dialog.activateWindow()

        def show_about() -> None:
            QMessageBox.information(
                None,
                "About PC Voice Agent",
                "PC Voice Agent v0.1.0\n\n"
                "A lightweight, fully local voice dictation and PC control agent for Windows 10/11.\n\n"
                "• Right Ctrl: Dictate text\n"
                "• Right Alt: Control PC with voice commands\n"
                "• 100% offline and private.",
            )

        tray = SystemTrayManager(
            lifecycle=lifecycle,
            config=config,
            on_toggle_overlay=toggle_overlay,
            on_open_history=open_history,
            on_open_settings=open_settings,
            on_about=show_about,
        )
        tray.show()
        lifecycle.subscribe_dictation_state(lambda s: tray.update_status("dictation", s.value))
        lifecycle.subscribe_control_state(lambda s: tray.update_status("control", s.value))

        # Show initial balloon toast pointing to system tray
        tray.show_notification(
            "PC Voice Agent",
            f"Voice Agent is running! Using mic: {active_mic.name if active_mic else 'Default'}.\nPress Right Ctrl to dictate or Right Alt for control.",
        )

        # 15. Control Mode Audio Capture Handlers
        def handle_control_start() -> None:
            if tray.is_paused:
                return
            logger.info("Control hotkey triggered: starting audio capture (device_id=%s)...", active_device_id)
            lifecycle.set_control_state(ControlState.LISTENING)
            try:
                recorder.start_recording(device_id=active_device_id)
            except Exception as exc:
                logger.error("Failed to start recording for control: %s", exc)
                lifecycle.set_control_state(ControlState.ERROR)
                lifecycle.set_control_state(ControlState.READY)

        def handle_control_stop() -> None:
            if tray.is_paused:
                return
            logger.info("Control hotkey released: processing audio...")
            lifecycle.set_control_state(ControlState.PROCESSING)
            try:
                audio = recorder.stop_recording()
            except Exception as exc:
                logger.error("Failed to stop recording for control: %s", exc)
                lifecycle.set_control_state(ControlState.ERROR)
                lifecycle.set_control_state(ControlState.READY)
                return

            if len(audio) == 0:
                logger.debug("Control audio capture was empty; returning to READY.")
                lifecycle.set_control_state(ControlState.READY)
                return

            def _process_control_audio(audio_data: Any) -> None:
                try:
                    duration_sec = len(audio_data) / 16000.0
                    import numpy as np
                    max_amp = float(np.max(np.abs(audio_data))) if len(audio_data) > 0 else 0.0
                    logger.info(
                        "Control audio captured: %.2f sec (%d samples), peak amplitude: %.4f",
                        duration_sec,
                        len(audio_data),
                        max_amp,
                    )
                    if max_amp < 0.0005:
                        logger.warning("Control audio was nearly silent (peak=%.5f). Check microphone.", max_amp)
                        tray.show_notification(
                            "Microphone Warning",
                            "Microphone captured silence. Check your microphone device in Settings.",
                            icon_type="warning",
                        )
                        lifecycle.set_control_state(ControlState.READY)
                        return

                    raw_text = stt_engine.transcribe(audio_data, language="en")
                    clean_text = raw_text.strip()
                    if not clean_text:
                        logger.info("No speech recognized for control command.")
                        lifecycle.set_control_state(ControlState.READY)
                        return

                    logger.info("Voice command recognized: %r", clean_text)
                    report = command_router.execute(clean_text)
                    if report.is_success:
                        lifecycle.set_control_state(ControlState.RESULT)
                    else:
                        lifecycle.set_control_state(ControlState.ERROR)
                        tray.show_notification(
                            "Control Command Unrecognized",
                            f"'{clean_text}' is not a recognized PC command.\nTip: Press Right Ctrl to dictate text.",
                            icon_type="warning",
                        )
                except Exception as exc:
                    logger.error("Error executing voice command: %s", exc, exc_info=True)
                    lifecycle.set_control_state(ControlState.ERROR)
                finally:
                    time.sleep(0.6)
                    lifecycle.set_control_state(ControlState.READY)

            lifecycle.run_async(_process_control_audio, audio)

        def handle_dictation_start() -> None:
            if tray.is_paused:
                return
            logger.info("Dictation hotkey triggered: starting audio capture (device_id=%s)...", active_device_id)
            dictation_processor.start_listening(device_id=active_device_id)

        def handle_dictation_stop() -> None:
            if tray.is_paused:
                return
            logger.info("Dictation hotkey released: processing audio...")
            dictation_processor.stop_listening()

        # 16. Global Hotkey Manager
        hotkey_manager = HotkeyManager(
            dictation_hotkey=config.dictation.hotkey,
            control_hotkey=config.control.hotkey,
            dictation_mode=config.dictation.mode,
            control_mode=config.control.mode,
            on_dictation_start=handle_dictation_start,
            on_dictation_stop=handle_dictation_stop,
            on_control_start=handle_control_start,
            on_control_stop=handle_control_stop,
        )
        hotkey_manager.start()

        # Register clean shutdown hooks
        lifecycle.add_shutdown_hook(hotkey_manager.stop)
        lifecycle.add_shutdown_hook(dictation_processor.shutdown)
        lifecycle.add_shutdown_hook(lambda: recorder.reset() if recorder.is_recording else None)

        # 17. Show Floating Overlay if enabled
        if config.ui.overlay_enabled and not args.minimized and not args.offscreen:
            overlay.show()

        # Print friendly guidance in terminal
        mic_name = active_mic.name if active_mic else "Default"
        print("=" * 65)
        print("[*] PC Voice Agent is running!")
        print("=" * 65)
        print(" * Dictation Mode:  Press Right Ctrl (Tap to toggle or hold to talk)")
        print("   -> Tip: If your keyboard lacks Right Ctrl, open Settings to use Left Ctrl or F8")
        print(" * PC Control Mode: Press Right Alt (Tap or hold to speak command)")
        print(f" * Active Mic:      {mic_name}")
        print(" * Status Overlay:  Floating pill shown on your screen")
        print(" * System Tray:     Microphone icon in bottom-right Windows taskbar")
        print("                    (Click '^' upward chevron if icons are hidden)")
        print(" * Right-click tray icon for: Settings, History, or Exit")
        print(" * Press Ctrl+C in this terminal window to stop.")
        print("=" * 65)

        logger.info("Application initialized. Entering Qt main event loop...")
        if not args.offscreen:
            exit_code = app.exec()
        else:
            exit_code = 0
    except ImportError:
        logger.warning("PySide6 not found. Running in headless core mode.")
        exit_code = 0
    except Exception as e:
        logger.critical("Unhandled exception in main event loop: %s", e, exc_info=True)
        exit_code = 1
    finally:
        lifecycle.shutdown()
        lock.release()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
