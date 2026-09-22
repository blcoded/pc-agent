"""Preferences and Settings Dialog for PC Voice Agent.

Provides multi-tab graphical configuration for:
- Dictation Mode preferences (hotkey, activation mode, STT model, language, formatting)
- Control Mode preferences (hotkey, activation mode, confirmation risk thresholds)
- Audio settings (live microphone enumeration, audio level meter preview)
- General application settings (startup launch, tray behavior, history retention, overlay toggle/reset)

Includes seamless headless simulation fallback for testing environments.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from voice_agent.app.config import (
    AppConfig,
    AudioConfig,
    ControlConfig,
    DictationConfig,
    GeneralConfig,
    StorageConfig,
    UIConfig,
    get_default_config_path,
    load_config,
    save_config,
)
from voice_agent.audio.microphone import AudioDeviceInfo, MicrophoneManager
from voice_agent.stt.models import SUPPORTED_MODELS

logger = logging.getLogger(__name__)

# Standard hotkey options
HOTKEY_OPTIONS = [
    ("Right Ctrl (Default Dictation)", "ctrl_r"),
    ("Right Alt (Default Control)", "alt_r"),
    ("Left Ctrl", "ctrl_l"),
    ("Left Alt", "alt_l"),
    ("F8", "f8"),
    ("F9", "f9"),
    ("F10", "f10"),
    ("F11", "f11"),
    ("F12", "f12"),
]

# Activation mode options
ACTIVATION_MODE_OPTIONS = [
    ("Both (Tap to Toggle, Hold to Talk)", "both"),
    ("Push-to-Talk (Hold Only)", "push_to_talk"),
    ("Toggle (Tap to Start/Stop)", "toggle"),
]

# Supported language options
LANGUAGE_OPTIONS = [
    ("English", "en"),
    ("Auto-detect", "auto"),
    ("Spanish", "es"),
    ("French", "fr"),
    ("German", "de"),
    ("Italian", "it"),
    ("Portuguese", "pt"),
    ("Japanese", "ja"),
    ("Chinese", "zh"),
]

try:
    from PySide6.QtCore import QTimer, Qt, Signal
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QProgressBar,
        QPushButton,
        QSpinBox,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )
    HAS_PYSIDE = True
except ImportError:
    HAS_PYSIDE = False


if HAS_PYSIDE:
    _BaseDialog = QDialog
else:
    class _BaseDialog:  # type: ignore[no-redef]
        """Headless simulation base dialog when PySide6 is unavailable."""

        Accepted = 1
        Rejected = 0

        def __init__(self, parent: Any = None) -> None:
            self.parent = parent
            self._result = 0

        def setWindowTitle(self, title: str) -> None:
            pass

        def resize(self, w: int, h: int) -> None:
            pass

        def show(self) -> None:
            pass

        def close(self) -> None:
            pass

        def accept(self) -> None:
            self._result = self.Accepted

        def reject(self) -> None:
            self._result = self.Rejected

        def result(self) -> int:
            return self._result

        def exec(self) -> int:
            return self._result


class SettingsDialog(_BaseDialog):
    """Preferences and configuration dialog with multi-tab interface."""

    Accepted = 1
    Rejected = 0

    if HAS_PYSIDE:
        config_applied = Signal(object)  # Emits AppConfig when saved/applied

    def __init__(
        self,
        config: AppConfig | None = None,
        config_path: Path | None = None,
        on_applied: Callable[[AppConfig], None] | None = None,
        mic_manager: MicrophoneManager | None = None,
        parent: Any = None,
    ) -> None:
        """Initialize the settings dialog.

        Args:
            config: Initial AppConfig instance. If None, loads from config_path.
            config_path: Path to config.toml. If None, uses default path.
            on_applied: Callback invoked when settings are applied or saved.
            mic_manager: MicrophoneManager for live device enumeration.
            parent: Optional parent QWidget.
        """
        super().__init__(parent)
        self.config_path = config_path or get_default_config_path()
        self.on_applied = on_applied
        self.mic_manager = mic_manager

        # Loaded baseline config
        self._initial_config: AppConfig = config if config is not None else load_config(self.config_path)
        # Working copy of config
        self._current_config: AppConfig = self._clone_config(self._initial_config)

        # Internal state tracking
        self.overlay_x: int = self._current_config.ui.overlay_x
        self.overlay_y: int = self._current_config.ui.overlay_y
        self.is_testing_mic: bool = False

        # Live microphone devices cache
        self.available_microphones: list[AudioDeviceInfo] = []

        self._init_ui()
        self.load_from_config(self._current_config)

    def _clone_config(self, cfg: AppConfig) -> AppConfig:
        """Create an independent copy of AppConfig."""
        return AppConfig(
            dictation=DictationConfig(
                hotkey=cfg.dictation.hotkey,
                mode=cfg.dictation.mode,
                model=cfg.dictation.model,
                language=cfg.dictation.language,
                format_commands=cfg.dictation.format_commands,
                restore_clipboard=cfg.dictation.restore_clipboard,
                keep_in_clipboard=cfg.dictation.keep_in_clipboard,
            ),
            control=ControlConfig(
                hotkey=cfg.control.hotkey,
                mode=cfg.control.mode,
                confirm_medium=cfg.control.confirm_medium,
                confirm_high=cfg.control.confirm_high,
            ),
            audio=AudioConfig(
                microphone=cfg.audio.microphone,
                sample_rate=cfg.audio.sample_rate,
                channels=cfg.audio.channels,
                max_duration=cfg.audio.max_duration,
            ),
            ui=UIConfig(
                overlay_enabled=cfg.ui.overlay_enabled,
                overlay_x=cfg.ui.overlay_x,
                overlay_y=cfg.ui.overlay_y,
                opacity=cfg.ui.opacity,
            ),
            storage=StorageConfig(
                history_retention_days=cfg.storage.history_retention_days,
                max_history_entries=cfg.storage.max_history_entries,
            ),
            general=GeneralConfig(
                run_at_startup=cfg.general.run_at_startup,
                minimize_to_tray=cfg.general.minimize_to_tray,
            ),
        )

    # Property getters and setters with bidirectional Qt widget synchronization
    @property
    def dictation_hotkey(self) -> str:
        if HAS_PYSIDE and hasattr(self, "combo_dict_hotkey"):
            return self.combo_dict_hotkey.currentData() or self._dictation_hotkey
        return self._dictation_hotkey

    @dictation_hotkey.setter
    def dictation_hotkey(self, val: str) -> None:
        self._dictation_hotkey = val
        if HAS_PYSIDE and hasattr(self, "combo_dict_hotkey"):
            idx = self.combo_dict_hotkey.findData(val)
            if idx >= 0:
                self.combo_dict_hotkey.setCurrentIndex(idx)

    @property
    def dictation_mode(self) -> str:
        if HAS_PYSIDE and hasattr(self, "combo_dict_mode"):
            return self.combo_dict_mode.currentData() or self._dictation_mode
        return self._dictation_mode

    @dictation_mode.setter
    def dictation_mode(self, val: str) -> None:
        self._dictation_mode = val
        if HAS_PYSIDE and hasattr(self, "combo_dict_mode"):
            idx = self.combo_dict_mode.findData(val)
            if idx >= 0:
                self.combo_dict_mode.setCurrentIndex(idx)

    @property
    def stt_model(self) -> str:
        if HAS_PYSIDE and hasattr(self, "combo_stt_model"):
            return self.combo_stt_model.currentData() or self._stt_model
        return self._stt_model

    @stt_model.setter
    def stt_model(self, val: str) -> None:
        self._stt_model = val
        if HAS_PYSIDE and hasattr(self, "combo_stt_model"):
            idx = self.combo_stt_model.findData(val)
            if idx >= 0:
                self.combo_stt_model.setCurrentIndex(idx)
                self._on_model_changed(idx)

    @property
    def language(self) -> str:
        if HAS_PYSIDE and hasattr(self, "combo_language"):
            return self.combo_language.currentData() or self._language
        return self._language

    @language.setter
    def language(self, val: str) -> None:
        self._language = val
        if HAS_PYSIDE and hasattr(self, "combo_language"):
            idx = self.combo_language.findData(val)
            if idx >= 0:
                self.combo_language.setCurrentIndex(idx)

    @property
    def format_commands(self) -> bool:
        if HAS_PYSIDE and hasattr(self, "chk_format_commands"):
            return self.chk_format_commands.isChecked()
        return self._format_commands

    @format_commands.setter
    def format_commands(self, val: bool) -> None:
        self._format_commands = bool(val)
        if HAS_PYSIDE and hasattr(self, "chk_format_commands"):
            self.chk_format_commands.setChecked(bool(val))

    @property
    def restore_clipboard(self) -> bool:
        if HAS_PYSIDE and hasattr(self, "chk_restore_clipboard"):
            return self.chk_restore_clipboard.isChecked()
        return self._restore_clipboard

    @restore_clipboard.setter
    def restore_clipboard(self, val: bool) -> None:
        self._restore_clipboard = bool(val)
        if HAS_PYSIDE and hasattr(self, "chk_restore_clipboard"):
            self.chk_restore_clipboard.setChecked(bool(val))

    @property
    def control_hotkey(self) -> str:
        if HAS_PYSIDE and hasattr(self, "combo_ctrl_hotkey"):
            return self.combo_ctrl_hotkey.currentData() or self._control_hotkey
        return self._control_hotkey

    @control_hotkey.setter
    def control_hotkey(self, val: str) -> None:
        self._control_hotkey = val
        if HAS_PYSIDE and hasattr(self, "combo_ctrl_hotkey"):
            idx = self.combo_ctrl_hotkey.findData(val)
            if idx >= 0:
                self.combo_ctrl_hotkey.setCurrentIndex(idx)

    @property
    def control_mode(self) -> str:
        if HAS_PYSIDE and hasattr(self, "combo_ctrl_mode"):
            return self.combo_ctrl_mode.currentData() or self._control_mode
        return self._control_mode

    @control_mode.setter
    def control_mode(self, val: str) -> None:
        self._control_mode = val
        if HAS_PYSIDE and hasattr(self, "combo_ctrl_mode"):
            idx = self.combo_ctrl_mode.findData(val)
            if idx >= 0:
                self.combo_ctrl_mode.setCurrentIndex(idx)

    @property
    def confirm_medium(self) -> bool:
        if HAS_PYSIDE and hasattr(self, "chk_confirm_medium"):
            return self.chk_confirm_medium.isChecked()
        return self._confirm_medium

    @confirm_medium.setter
    def confirm_medium(self, val: bool) -> None:
        self._confirm_medium = bool(val)
        if HAS_PYSIDE and hasattr(self, "chk_confirm_medium"):
            self.chk_confirm_medium.setChecked(bool(val))

    @property
    def confirm_high(self) -> bool:
        if HAS_PYSIDE and hasattr(self, "chk_confirm_high"):
            return self.chk_confirm_high.isChecked()
        return self._confirm_high

    @confirm_high.setter
    def confirm_high(self, val: bool) -> None:
        self._confirm_high = bool(val)
        if HAS_PYSIDE and hasattr(self, "chk_confirm_high"):
            self.chk_confirm_high.setChecked(bool(val))

    @property
    def microphone(self) -> str | None:
        if HAS_PYSIDE and hasattr(self, "combo_mic"):
            return self.combo_mic.currentData()
        return self._microphone

    @microphone.setter
    def microphone(self, val: str | None) -> None:
        self._microphone = val
        if HAS_PYSIDE and hasattr(self, "combo_mic"):
            idx = self.combo_mic.findData(val)
            if idx >= 0:
                self.combo_mic.setCurrentIndex(idx)
            elif val is not None:
                self.combo_mic.addItem(f"{val} (Configured)", val)
                self.combo_mic.setCurrentIndex(self.combo_mic.count() - 1)
            else:
                self.combo_mic.setCurrentIndex(0)


    @property
    def max_duration(self) -> int:
        if HAS_PYSIDE and hasattr(self, "spin_max_duration"):
            return max(10, min(150, self.spin_max_duration.value()))
        return max(10, min(150, getattr(self, "_max_duration", 60)))

    @max_duration.setter
    def max_duration(self, val: int) -> None:
        clamped = max(10, min(150, int(val)))
        self._max_duration = clamped
        if HAS_PYSIDE and hasattr(self, "spin_max_duration"):
            self.spin_max_duration.setValue(clamped)

    @property
    def run_at_startup(self) -> bool:
        if HAS_PYSIDE and hasattr(self, "chk_startup"):
            return self.chk_startup.isChecked()
        return self._run_at_startup

    @run_at_startup.setter
    def run_at_startup(self, val: bool) -> None:
        self._run_at_startup = bool(val)
        if HAS_PYSIDE and hasattr(self, "chk_startup"):
            self.chk_startup.setChecked(bool(val))

    @property
    def minimize_to_tray(self) -> bool:
        if HAS_PYSIDE and hasattr(self, "chk_minimize_tray"):
            return self.chk_minimize_tray.isChecked()
        return self._minimize_to_tray

    @minimize_to_tray.setter
    def minimize_to_tray(self, val: bool) -> None:
        self._minimize_to_tray = bool(val)
        if HAS_PYSIDE and hasattr(self, "chk_minimize_tray"):
            self.chk_minimize_tray.setChecked(bool(val))

    @property
    def history_retention_days(self) -> int:
        if HAS_PYSIDE and hasattr(self, "spin_retention"):
            return self.spin_retention.value()
        return self._history_retention_days

    @history_retention_days.setter
    def history_retention_days(self, val: int) -> None:
        self._history_retention_days = int(val)
        if HAS_PYSIDE and hasattr(self, "spin_retention"):
            self.spin_retention.setValue(int(val))

    @property
    def overlay_enabled(self) -> bool:
        if HAS_PYSIDE and hasattr(self, "chk_overlay"):
            return self.chk_overlay.isChecked()
        return self._overlay_enabled

    @overlay_enabled.setter
    def overlay_enabled(self, val: bool) -> None:
        self._overlay_enabled = bool(val)
        if HAS_PYSIDE and hasattr(self, "chk_overlay"):
            self.chk_overlay.setChecked(bool(val))

    def _init_ui(self) -> None:
        """Set up the dialog layout, tabs, and action buttons."""
        self.setWindowTitle("Voice Agent - Settings & Preferences")

        # Baseline internal attributes
        self._dictation_hotkey: str = self._current_config.dictation.hotkey
        self._dictation_mode: str = self._current_config.dictation.mode
        self._stt_model: str = self._current_config.dictation.model
        self._language: str = self._current_config.dictation.language
        self._format_commands: bool = self._current_config.dictation.format_commands
        self._restore_clipboard: bool = self._current_config.dictation.restore_clipboard

        self._control_hotkey: str = self._current_config.control.hotkey
        self._control_mode: str = self._current_config.control.mode
        self._confirm_medium: bool = self._current_config.control.confirm_medium
        self._confirm_high: bool = self._current_config.control.confirm_high

        self._microphone: str | None = self._current_config.audio.microphone
        self._max_duration: int = self._current_config.audio.max_duration

        self._run_at_startup: bool = self._current_config.general.run_at_startup
        self._minimize_to_tray: bool = self._current_config.general.minimize_to_tray
        self._history_retention_days: int = self._current_config.storage.history_retention_days
        self._overlay_enabled: bool = self._current_config.ui.overlay_enabled

        self.refresh_microphones()


        if not HAS_PYSIDE:
            return

        self.resize(540, 480)
        main_layout = QVBoxLayout(self)

        # Tab widget
        self.tabs = QTabWidget(self)
        main_layout.addWidget(self.tabs)

        # Build tabs
        self.dictation_tab = self._build_dictation_tab()
        self.control_tab = self._build_control_tab()
        self.audio_tab = self._build_audio_tab()
        self.general_tab = self._build_general_tab()

        self.tabs.addTab(self.dictation_tab, "Dictation")
        self.tabs.addTab(self.control_tab, "Control")
        self.tabs.addTab(self.audio_tab, "Audio")
        self.tabs.addTab(self.general_tab, "General")

        # Dialog buttons (Save, Apply, Cancel)
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.btn_save = QPushButton("Save", self)
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self.save)
        button_layout.addWidget(self.btn_save)

        self.btn_apply = QPushButton("Apply", self)
        self.btn_apply.clicked.connect(self.apply)
        button_layout.addWidget(self.btn_apply)

        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.clicked.connect(self.cancel)
        button_layout.addWidget(self.btn_cancel)

        main_layout.addLayout(button_layout)
        self.refresh_microphones()


    def _build_dictation_tab(self) -> QWidget:
        """Construct the Dictation tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group = QGroupBox("Dictation Mode Preferences")
        form = QFormLayout(group)

        # Hotkey selector
        self.combo_dict_hotkey = QComboBox()
        for label, val in HOTKEY_OPTIONS:
            self.combo_dict_hotkey.addItem(label, val)
        form.addRow("Activation Hotkey:", self.combo_dict_hotkey)

        # Activation mode selector
        self.combo_dict_mode = QComboBox()
        for label, val in ACTIVATION_MODE_OPTIONS:
            self.combo_dict_mode.addItem(label, val)
        form.addRow("Trigger Mode:", self.combo_dict_mode)

        # STT Model picker
        self.combo_stt_model = QComboBox()
        for model_name, info in SUPPORTED_MODELS.items():
            self.combo_stt_model.addItem(f"{model_name.capitalize()} ({info.speed_rating} speed)", model_name)
        self.combo_stt_model.currentIndexChanged.connect(self._on_model_changed)
        form.addRow("Whisper Model:", self.combo_stt_model)

        # Resource indicators label
        self.lbl_model_info = QLabel()
        self.lbl_model_info.setStyleSheet("color: #718096; font-size: 11px;")
        form.addRow("", self.lbl_model_info)

        # Language picker
        self.combo_language = QComboBox()
        for label, val in LANGUAGE_OPTIONS:
            self.combo_language.addItem(label, val)
        form.addRow("Language:", self.combo_language)

        # Formatting toggle
        self.chk_format_commands = QCheckBox("Enable verbal punctuation & formatting (e.g. 'new line', 'comma')")
        form.addRow("", self.chk_format_commands)

        # Restore clipboard toggle
        self.chk_restore_clipboard = QCheckBox("Preserve previous clipboard content after text insertion")
        form.addRow("", self.chk_restore_clipboard)

        layout.addWidget(group)
        layout.addStretch()
        return tab

    def _build_control_tab(self) -> QWidget:
        """Construct the Control tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group = QGroupBox("Control Mode Preferences")
        form = QFormLayout(group)

        # Hotkey selector
        self.combo_ctrl_hotkey = QComboBox()
        for label, val in HOTKEY_OPTIONS:
            self.combo_ctrl_hotkey.addItem(label, val)
        form.addRow("Activation Hotkey:", self.combo_ctrl_hotkey)

        # Activation mode selector
        self.combo_ctrl_mode = QComboBox()
        for label, val in ACTIVATION_MODE_OPTIONS:
            self.combo_ctrl_mode.addItem(label, val)
        form.addRow("Trigger Mode:", self.combo_ctrl_mode)

        # Risk confirmation preferences
        self.chk_confirm_medium = QCheckBox("Always require confirmation for Medium-risk actions (e.g. app switching, web search)")
        form.addRow("", self.chk_confirm_medium)

        self.chk_confirm_high = QCheckBox("Always require confirmation for High-risk actions (e.g. file deletion, system commands)")
        self.chk_confirm_high.setEnabled(False)  # High risk is always confirmed for safety
        form.addRow("", self.chk_confirm_high)

        layout.addWidget(group)
        layout.addStretch()
        return tab

    def _build_audio_tab(self) -> QWidget:
        """Construct the Audio tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group = QGroupBox("Audio Input Configuration")
        vbox = QVBoxLayout(group)

        # Device selection row
        dev_row = QHBoxLayout()
        dev_label = QLabel("Microphone:")
        self.combo_mic = QComboBox()
        self.combo_mic.setMinimumWidth(280)
        self.btn_refresh_mics = QPushButton("Refresh Devices")
        self.btn_refresh_mics.clicked.connect(self.refresh_microphones)

        dev_row.addWidget(dev_label)
        dev_row.addWidget(self.combo_mic, 1)
        dev_row.addWidget(self.btn_refresh_mics)
        vbox.addLayout(dev_row)

        # Max recording duration row
        duration_row = QHBoxLayout()
        duration_label = QLabel("Max Recording Duration:")
        self.spin_max_duration = QSpinBox()
        self.spin_max_duration.setRange(10, 150)
        self.spin_max_duration.setSingleStep(5)
        self.spin_max_duration.setSuffix(" seconds")
        self.spin_max_duration.setToolTip(
            "Maximum allowed duration for a single recording take (10 to 150 seconds)."
        )
        duration_row.addWidget(duration_label)
        duration_row.addWidget(self.spin_max_duration)
        duration_row.addStretch()
        vbox.addLayout(duration_row)

        # Live level meter preview
        meter_group = QGroupBox("Microphone Test & Level Meter")
        meter_layout = QVBoxLayout(meter_group)

        meter_controls = QHBoxLayout()
        self.btn_test_mic = QPushButton("Test Microphone")
        self.btn_test_mic.clicked.connect(self._toggle_mic_test)
        meter_controls.addWidget(self.btn_test_mic)
        meter_controls.addStretch()
        meter_layout.addLayout(meter_controls)

        self.audio_meter = QProgressBar()
        self.audio_meter.setRange(0, 100)
        self.audio_meter.setValue(0)
        self.audio_meter.setTextVisible(False)
        self.audio_meter.setFixedHeight(16)
        meter_layout.addWidget(self.audio_meter)

        vbox.addWidget(meter_group)
        layout.addWidget(group)
        layout.addStretch()
        return tab

    def _build_general_tab(self) -> QWidget:
        """Construct the General application tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Startup & Window behavior
        group_app = QGroupBox("Application Preferences")
        form_app = QFormLayout(group_app)

        self.chk_startup = QCheckBox("Launch PC Voice Agent at Windows startup")
        form_app.addRow("", self.chk_startup)

        self.chk_minimize_tray = QCheckBox("Minimize application to system tray when closed")
        form_app.addRow("", self.chk_minimize_tray)

        self.spin_retention = QSpinBox()
        self.spin_retention.setRange(1, 365)
        self.spin_retention.setSuffix(" days")
        form_app.addRow("History Retention:", self.spin_retention)
        layout.addWidget(group_app)

        # Overlay settings
        group_overlay = QGroupBox("Floating Status Overlay")
        form_overlay = QFormLayout(group_overlay)

        self.chk_overlay = QCheckBox("Show floating status indicator overlay")
        form_overlay.addRow("", self.chk_overlay)

        reset_row = QHBoxLayout()
        self.btn_reset_overlay = QPushButton("Reset Overlay Position")
        self.btn_reset_overlay.clicked.connect(self.reset_overlay_position)
        self.lbl_reset_status = QLabel("")
        self.lbl_reset_status.setStyleSheet("color: #38a169; font-size: 11px;")
        reset_row.addWidget(self.btn_reset_overlay)
        reset_row.addWidget(self.lbl_reset_status)
        reset_row.addStretch()
        form_overlay.addRow("Position:", reset_row)

        layout.addWidget(group_overlay)
        layout.addStretch()
        return tab

    def _on_model_changed(self, index: int) -> None:
        """Update model resource indicators when selection changes."""
        if not HAS_PYSIDE:
            return
        model_name = self.combo_stt_model.currentData()
        if model_name in SUPPORTED_MODELS:
            info = SUPPORTED_MODELS[model_name]
            text = f"Size: ~{info.size_mb} MB | RAM: ~{info.estimated_ram_mb} MB | Accuracy: {info.accuracy_rating}"
            self.lbl_model_info.setText(text)

    def _toggle_mic_test(self) -> None:
        """Start or stop the microphone level meter test."""
        self.is_testing_mic = not self.is_testing_mic
        if HAS_PYSIDE:
            if self.is_testing_mic:
                self.btn_test_mic.setText("Stop Test")
                # Simulate audio meter activity if not live recording
                self._sim_timer = QTimer(self)
                self._sim_val = 0
                self._sim_timer.timeout.connect(self._update_test_meter)
                self._sim_timer.start(100)
            else:
                self.btn_test_mic.setText("Test Microphone")
                if hasattr(self, "_sim_timer") and self._sim_timer:
                    self._sim_timer.stop()
                self.audio_meter.setValue(0)

    def _update_test_meter(self) -> None:
        """Tick handler for microphone meter visualization."""
        if not HAS_PYSIDE:
            return
        import random
        level = random.randint(15, 65)
        self.audio_meter.setValue(level)

    def refresh_microphones(self) -> None:
        """Enumerate available audio input devices and update dropdown."""
        if self.mic_manager is not None:
            self.available_microphones = self.mic_manager.get_input_devices()
        else:
            try:
                mgr = MicrophoneManager()
                self.available_microphones = mgr.get_input_devices()
            except Exception:
                self.available_microphones = []

        if HAS_PYSIDE and hasattr(self, "combo_mic"):
            current_selected = self.combo_mic.currentData()
            self.combo_mic.clear()
            self.combo_mic.addItem("Default (Windows System Default)", None)

            for dev in self.available_microphones:
                label = f"{dev.name} ({dev.hostapi_name})"
                self.combo_mic.addItem(label, dev.name)

            # Re-select matching device
            if current_selected is not None:
                idx = self.combo_mic.findData(current_selected)
                if idx >= 0:
                    self.combo_mic.setCurrentIndex(idx)
                else:
                    self.combo_mic.setCurrentIndex(0)

    def reset_overlay_position(self) -> None:
        """Reset overlay coordinates to default automatic placement."""
        self.overlay_x = -1
        self.overlay_y = -1
        if HAS_PYSIDE and hasattr(self, "lbl_reset_status"):
            self.lbl_reset_status.setText("Position will reset to center-bottom on save.")

    def load_from_config(self, config: AppConfig) -> None:
        """Populate dialog widgets from an AppConfig instance."""
        self._current_config = self._clone_config(config)
        self.overlay_x = config.ui.overlay_x
        self.overlay_y = config.ui.overlay_y

        # Update properties (automatically synchronizes Qt widgets if available)
        self.dictation_hotkey = config.dictation.hotkey
        self.dictation_mode = config.dictation.mode
        self.stt_model = config.dictation.model
        self.language = config.dictation.language
        self.format_commands = config.dictation.format_commands
        self.restore_clipboard = config.dictation.restore_clipboard

        self.control_hotkey = config.control.hotkey
        self.control_mode = config.control.mode
        self.confirm_medium = config.control.confirm_medium
        self.confirm_high = config.control.confirm_high

        self.microphone = config.audio.microphone
        self.max_duration = config.audio.max_duration

        self.run_at_startup = config.general.run_at_startup
        self.minimize_to_tray = config.general.minimize_to_tray
        self.history_retention_days = config.storage.history_retention_days
        self.overlay_enabled = config.ui.overlay_enabled

        if HAS_PYSIDE and hasattr(self, "lbl_reset_status"):
            self.lbl_reset_status.setText("")

    def get_current_config(self) -> AppConfig:
        """Extract and construct AppConfig from current widget/property values."""
        return AppConfig(
            dictation=DictationConfig(
                hotkey=self.dictation_hotkey,
                mode=self.dictation_mode,
                model=self.stt_model,
                language=self.language,
                format_commands=self.format_commands,
                restore_clipboard=self.restore_clipboard,
                keep_in_clipboard=self._current_config.dictation.keep_in_clipboard,
            ),
            control=ControlConfig(
                hotkey=self.control_hotkey,
                mode=self.control_mode,
                confirm_medium=self.confirm_medium,
                confirm_high=self.confirm_high,
            ),
            audio=AudioConfig(
                microphone=self.microphone,
                sample_rate=self._current_config.audio.sample_rate,
                channels=self._current_config.audio.channels,
                max_duration=self.max_duration,
            ),
            ui=UIConfig(
                overlay_enabled=self.overlay_enabled,
                overlay_x=self.overlay_x,
                overlay_y=self.overlay_y,
                opacity=self._current_config.ui.opacity,
            ),
            storage=StorageConfig(
                history_retention_days=self.history_retention_days,
                max_history_entries=self._current_config.storage.max_history_entries,
            ),
            general=GeneralConfig(
                run_at_startup=self.run_at_startup,
                minimize_to_tray=self.minimize_to_tray,
            ),
        )

    def apply(self) -> AppConfig:
        """Save settings to config file and notify listeners without closing."""
        updated = self.get_current_config()
        self._current_config = self._clone_config(updated)
        save_config(updated, self.config_path)

        if self.on_applied is not None:
            try:
                self.on_applied(updated)
            except Exception as e:
                logger.error("Error executing on_applied callback: %s", e)

        if HAS_PYSIDE and hasattr(self, "config_applied"):
            self.config_applied.emit(updated)

        return updated

    def save(self) -> AppConfig:
        """Apply current settings, save to file, and close dialog."""
        cfg = self.apply()
        self.accept()
        return cfg

    def cancel(self) -> None:
        """Revert settings to baseline and close dialog."""
        self.load_from_config(self._initial_config)
        self.reject()
