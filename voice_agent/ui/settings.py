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

    def _init_ui(self) -> None:
        """Set up the dialog layout, tabs, and action buttons."""
        self.setWindowTitle("Voice Agent - Settings & Preferences")

        # Headless attributes
        self.dictation_hotkey: str = self._current_config.dictation.hotkey
        self.dictation_mode: str = self._current_config.dictation.mode
        self.stt_model: str = self._current_config.dictation.model
        self.language: str = self._current_config.dictation.language
        self.format_commands: bool = self._current_config.dictation.format_commands
        self.restore_clipboard: bool = self._current_config.dictation.restore_clipboard

        self.control_hotkey: str = self._current_config.control.hotkey
        self.control_mode: str = self._current_config.control.mode
        self.confirm_medium: bool = self._current_config.control.confirm_medium
        self.confirm_high: bool = self._current_config.control.confirm_high

        self.microphone: str | None = self._current_config.audio.microphone

        self.run_at_startup: bool = self._current_config.general.run_at_startup
        self.minimize_to_tray: bool = self._current_config.general.minimize_to_tray
        self.history_retention_days: int = self._current_config.storage.history_retention_days
        self.overlay_enabled: bool = self._current_config.ui.overlay_enabled

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

        # Update headless properties
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

        self.run_at_startup = config.general.run_at_startup
        self.minimize_to_tray = config.general.minimize_to_tray
        self.history_retention_days = config.storage.history_retention_days
        self.overlay_enabled = config.ui.overlay_enabled

        if not HAS_PYSIDE or not hasattr(self, "tabs"):
            return

        # Dictation Tab
        idx_dict_hotkey = self.combo_dict_hotkey.findData(config.dictation.hotkey)
        if idx_dict_hotkey >= 0:
            self.combo_dict_hotkey.setCurrentIndex(idx_dict_hotkey)

        idx_dict_mode = self.combo_dict_mode.findData(config.dictation.mode)
        if idx_dict_mode >= 0:
            self.combo_dict_mode.setCurrentIndex(idx_dict_mode)

        idx_model = self.combo_stt_model.findData(config.dictation.model)
        if idx_model >= 0:
            self.combo_stt_model.setCurrentIndex(idx_model)
        self._on_model_changed(self.combo_stt_model.currentIndex())

        idx_lang = self.combo_language.findData(config.dictation.language)
        if idx_lang >= 0:
            self.combo_language.setCurrentIndex(idx_lang)

        self.chk_format_commands.setChecked(config.dictation.format_commands)
        self.chk_restore_clipboard.setChecked(config.dictation.restore_clipboard)

        # Control Tab
        idx_ctrl_hotkey = self.combo_ctrl_hotkey.findData(config.control.hotkey)
        if idx_ctrl_hotkey >= 0:
            self.combo_ctrl_hotkey.setCurrentIndex(idx_ctrl_hotkey)

        idx_ctrl_mode = self.combo_ctrl_mode.findData(config.control.mode)
        if idx_ctrl_mode >= 0:
            self.combo_ctrl_mode.setCurrentIndex(idx_ctrl_mode)

        self.chk_confirm_medium.setChecked(config.control.confirm_medium)
        self.chk_confirm_high.setChecked(config.control.confirm_high)

        # Audio Tab
        idx_mic = self.combo_mic.findData(config.audio.microphone)
        if idx_mic >= 0:
            self.combo_mic.setCurrentIndex(idx_mic)
        else:
            self.combo_mic.setCurrentIndex(0)

        # General Tab
        self.chk_startup.setChecked(config.general.run_at_startup)
        self.chk_minimize_tray.setChecked(config.general.minimize_to_tray)
        self.spin_retention.setValue(config.storage.history_retention_days)
        self.chk_overlay.setChecked(config.ui.overlay_enabled)
        if hasattr(self, "lbl_reset_status"):
            self.lbl_reset_status.setText("")

    def get_current_config(self) -> AppConfig:
        """Extract and construct AppConfig from current widget values."""
        if HAS_PYSIDE and hasattr(self, "tabs"):
            dict_hotkey = self.combo_dict_hotkey.currentData() or "ctrl_r"
            dict_mode = self.combo_dict_mode.currentData() or "both"
            stt_model = self.combo_stt_model.currentData() or "base"
            lang = self.combo_language.currentData() or "en"
            format_cmds = self.chk_format_commands.isChecked()
            restore_clip = self.chk_restore_clipboard.isChecked()

            ctrl_hotkey = self.combo_ctrl_hotkey.currentData() or "alt_r"
            ctrl_mode = self.combo_ctrl_mode.currentData() or "both"
            confirm_med = self.chk_confirm_medium.isChecked()
            confirm_hi = self.chk_confirm_high.isChecked()

            mic = self.combo_mic.currentData()

            startup = self.chk_startup.isChecked()
            min_tray = self.chk_minimize_tray.isChecked()
            retention = self.spin_retention.value()
            overlay_en = self.chk_overlay.isChecked()
        else:
            dict_hotkey = self.dictation_hotkey
            dict_mode = self.dictation_mode
            stt_model = self.stt_model
            lang = self.language
            format_cmds = self.format_commands
            restore_clip = self.restore_clipboard

            ctrl_hotkey = self.control_hotkey
            ctrl_mode = self.control_mode
            confirm_med = self.confirm_medium
            confirm_hi = self.confirm_high

            mic = self.microphone

            startup = self.run_at_startup
            min_tray = self.minimize_to_tray
            retention = self.history_retention_days
            overlay_en = self.overlay_enabled

        return AppConfig(
            dictation=DictationConfig(
                hotkey=dict_hotkey,
                mode=dict_mode,
                model=stt_model,
                language=lang,
                format_commands=format_cmds,
                restore_clipboard=restore_clip,
                keep_in_clipboard=self._current_config.dictation.keep_in_clipboard,
            ),
            control=ControlConfig(
                hotkey=ctrl_hotkey,
                mode=ctrl_mode,
                confirm_medium=confirm_med,
                confirm_high=confirm_hi,
            ),
            audio=AudioConfig(
                microphone=mic,
                sample_rate=self._current_config.audio.sample_rate,
                channels=self._current_config.audio.channels,
            ),
            ui=UIConfig(
                overlay_enabled=overlay_en,
                overlay_x=self.overlay_x,
                overlay_y=self.overlay_y,
                opacity=self._current_config.ui.opacity,
            ),
            storage=StorageConfig(
                history_retention_days=retention,
                max_history_entries=self._current_config.storage.max_history_entries,
            ),
            general=GeneralConfig(
                run_at_startup=startup,
                minimize_to_tray=min_tray,
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
