# Windows Local Voice Agent — Project Tasks & Implementation Roadmap

Based on the official specification in [`docs/spec.md`](file:///C:/Users/Free%20user/Documents/AI%20Dev%20tools/pc-voice-agent/docs/spec.md).

---

## 1. Project Overview & Architectural Blueprint

The **Windows Local Voice Agent** is an offline-capable, privacy-respecting Windows desktop application with two strictly separated operational modes:
1. **Dictation Mode**: Speech → lightly normalized text → direct insertion into the active application (No LLM, no command execution).
2. **Control Mode**: Speech → local rule parser → structured Action API → risk evaluation & confirmation → validated OS execution.

### Target Architecture

```text
voice_agent/
├── app/
│   ├── main.py              # Application entrypoint & dependency injection
│   ├── lifecycle.py         # PySide6 application lifecycle & event loop
│   └── config.py            # TOML configuration loader, schema & watcher
├── audio/
│   ├── microphone.py        # Sounddevice microphone enumerator & fallback
│   └── recorder.py          # Ring-buffered 16kHz mono audio recorder
├── stt/
│   ├── engine.py            # Abstract SpeechToTextEngine interface
│   ├── whisper_engine.py    # faster-whisper CTranslate2 implementation
│   └── models.py            # Whisper model manager (download, cache, switch)
├── dictation/
│   ├── processor.py         # Dictation state machine & coordination
│   ├── normalizer.py        # Text capitalization, punctuation & glitch cleanup
│   ├── formatter.py         # Spoken formatting commands ("new line", etc.)
│   └── inserter.py          # Hybrid clipboard/SendInput text injector
├── control/
│   ├── parser.py            # Regex/rule-based command interpreter
│   ├── command_router.py    # Multi-step command dispatcher
│   ├── action_validator.py  # Path, boundary & parameter validator
│   ├── risk.py              # Low/Medium/High risk classification engine
│   └── actions/
│       ├── base.py          # Base Action class & execution context
│       ├── applications.py  # Launch, switch, close Windows applications
│       ├── keyboard.py      # Individual keys, shortcuts & hotkey chords
│       ├── mouse.py         # Mouse movement & click simulation
│       ├── browser.py       # Open URLs & web search via default browser
│       ├── clipboard.py     # Read, copy & paste clipboard operations
│       └── files.py         # Open, rename, move, delete files/folders
├── input/
│   ├── hotkeys.py           # Global keyboard hooks (Right Ctrl, Right Alt)
│   └── gesture.py           # Tap vs. hold detection logic
├── clipboard/
│   └── manager.py           # Win32 clipboard format preservation & restoration
├── ui/
│   ├── overlay.py           # Frameless floating status overlay widget
│   ├── tray.py              # System tray icon & context menu
│   ├── settings.py          # Multi-tab settings configuration dialog
│   ├── history.py           # Searchable history viewer & entry manager
│   └── confirmation.py      # Risk confirmation modal dialog
├── storage/
│   ├── database.py          # SQLite connection manager & schema migrations
│   ├── history.py           # History repository (transcripts & commands)
│   └── settings.py          # Persistent application state repository
└── tests/                   # Comprehensive pytest test suite
```

---

## 2. Master Task Progress Tracker

| Task ID | Phase | Component | Title | Status |
|---|---|---|---|---|
| **TASK-1.1** | Phase 1 | Foundation | Project Environment & Dependency Setup | `[x]` |
| **TASK-1.2** | Phase 1 | Foundation | Configuration System (TOML & Models) | `[x]` |
| **TASK-1.3** | Phase 1 | Foundation | Application Logging & Diagnostic Subsystem | `[x]` |
| **TASK-1.4** | Phase 1 | Foundation | SQLite Database & Schema Migration Engine | `[x]` |
| **TASK-1.5** | Phase 1 | Foundation | PySide6 Application Skeleton & Lifecycle | `[x]` |
| **TASK-2.1** | Phase 2 | Audio / STT | Microphone Enumerator & Fallback Handler | `[x]` |
| **TASK-2.2** | Phase 2 | Audio / STT | Ring-Buffered Audio Capture Recorder | `[x]` |
| **TASK-2.3** | Phase 2 | Audio / STT | Abstract STT Engine Interface & Model Manager | `[x]` |
| **TASK-2.4** | Phase 2 | Audio / STT | faster-whisper Local Engine Implementation | `[x]` |
| **TASK-3.1** | Phase 3 | Input | Global Hotkey Hook & Tap vs. Hold Engine | `[x]` |
| **TASK-3.2** | Phase 3 | Dictation | Win32 Clipboard Manager (Format Preservation) | `[x]` |
| **TASK-3.3** | Phase 3 | Dictation | Text Normalizer & Linguistic Cleaner | `[x]` |
| **TASK-3.4** | Phase 3 | Dictation | Dictation Formatting Command Parser | `[x]` |
| **TASK-3.5** | Phase 3 | Dictation | Hybrid Text Inserter & Fallback Notifier | `[x]` |
| **TASK-3.6** | Phase 3 | Dictation | Dictation Pipeline Coordinator & State Machine | `[x]` |
| **TASK-4.1** | Phase 4 | UI | Floating Status Overlay Widget | `[x]` |
| **TASK-4.2** | Phase 4 | UI | Windows System Tray Integration | `[x]` |
| **TASK-5.1** | Phase 5 | Control Core| Structured Action Request Models & Base Action | `[x]` |
| **TASK-5.2** | Phase 5 | Control Core| Local Rule-Based Command Parser | `[x]` |
| **TASK-5.3** | Phase 5 | Control Core| Action Parameter & Path Validator | `[ ]` |
| **TASK-5.4** | Phase 5 | Control Core| Risk Classification Engine | `[ ]` |
| **TASK-5.5** | Phase 5 | Control Core| Risk Confirmation Modal Dialog | `[ ]` |
| **TASK-6.1** | Phase 6 | Actions | Application Control Actions (Launch, Close, Switch)| `[ ]` |
| **TASK-6.2** | Phase 6 | Actions | Keyboard & Typing Actions | `[ ]` |
| **TASK-6.3** | Phase 6 | Actions | Mouse Movement & Click Actions | `[ ]` |
| **TASK-6.4** | Phase 6 | Actions | Browser & Web Search Actions | `[ ]` |
| **TASK-6.5** | Phase 6 | Actions | File & Folder System Actions | `[ ]` |
| **TASK-6.6** | Phase 6 | Actions | Clipboard Control Actions | `[ ]` |
| **TASK-6.7** | Phase 6 | Control Core| Multi-Step Command Router & Execution Pipeline | `[ ]` |
| **TASK-7.1** | Phase 7 | Management | History Repository & SQLite Storage | `[ ]` |
| **TASK-7.2** | Phase 7 | UI | History Viewer Window (Search, Inspect, Delete) | `[ ]` |
| **TASK-7.3** | Phase 7 | UI | Settings Dialog (Preferences Configuration) | `[ ]` |
| **TASK-7.4** | Phase 7 | Windows | Windows Startup (Run at Startup) Registry Helper | `[ ]` |
| **TASK-8.1** | Phase 8 | Quality | Comprehensive Unit & Integration Test Suite | `[ ]` |
| **TASK-8.2** | Phase 8 | Quality | End-to-End Pipeline & Stress Testing | `[ ]` |
| **TASK-8.3** | Phase 8 | Distribution| PyInstaller Executable Build Pipeline | `[ ]` |
| **TASK-8.4** | Phase 8 | Distribution| Inno Setup Windows Installer Script | `[ ]` |

---

## 3. Detailed Task Specifications

### Phase 1: Foundation & Application Architecture

---

#### `TASK-1.1`: Project Environment & Dependency Setup
- **Component**: Project Infrastructure
- **Objective**: Establish the Python 3.12+ environment, dependencies, folder structure, and code quality toolchain.
- **Specifications & Requirements**:
  - Configure `pyproject.toml` with project metadata, dependencies, and entrypoints.
  - Dependencies: `PySide6`, `faster-whisper`, `sounddevice`, `numpy`, `pynput`, `pywin32`.
  - Development tools: `pytest`, `pytest-qt`, `pytest-mock`, `mypy`, `ruff`.
  - Configure `ruff` for linting, formatting, and import sorting.
  - Configure `mypy` with strict typing settings.
  - Initialize the complete package directory structure under `voice_agent/`.
- **Target Files**:
  - `pyproject.toml`
  - `requirements.txt` (or dev dependencies in `pyproject.toml`)
  - `voice_agent/__init__.py`
- **Dependencies**: None
- **Verification**: Run `ruff check .` and `mypy voice_agent` cleanly.

---

#### `TASK-1.2`: Configuration System (TOML & Models)
- **Component**: `voice_agent/app/config.py`
- **Objective**: Implement strongly typed configuration loading, validation, saving, and defaults using TOML.
- **Specifications & Requirements**:
  - Store config at `%APPDATA%/PCVoiceAgent/config.toml` (with fallback to local working directory).
  - Default settings matching spec:
    - Dictation: Hotkey = `"ctrl_r"`, mode = `"both"`, model = `"base"`, language = `"en"`, format_commands = `true`, restore_clipboard = `true`.
    - Control: Hotkey = `"alt_r"`, mode = `"both"`, confirm_medium = `false`, confirm_high = `true`.
    - Audio: Selected microphone = `null` (system default).
    - UI: Overlay position = `{"x": -1, "y": -1}` (bottom-right default), overlay enabled = `true`.
    - Storage: History retention days = `30`.
    - General: Run at startup = `false`.
  - Atomic writing to prevent corruption during crashes.
- **Target Files**:
  - `voice_agent/app/config.py`
  - `tests/test_config.py`
- **Dependencies**: `TASK-1.1`
- **Verification**: Unit tests verifying config file generation, deserialization, serialization, and default fallback.

---

#### `TASK-1.3`: Application Logging & Diagnostic Subsystem
- **Component**: `voice_agent/app/lifecycle.py`, `voice_agent/app/logging.py`
- **Objective**: Set up structured, privacy-safe application logging with rotating file handlers.
- **Specifications & Requirements**:
  - Rotating file logger in `%APPDATA%/PCVoiceAgent/logs/voice_agent.log` (max 5MB, 3 backups) + stdout handler.
  - **Strict Privacy Guard**: Never log raw audio data, sensitive dictated text, or user passwords.
  - Record diagnostic events: Lifecycle events, microphone state changes, hotkey triggers, STT timings, action execution errors, unexpected exceptions.
- **Target Files**:
  - `voice_agent/app/logging.py`
  - `tests/test_logging.py`
- **Dependencies**: `TASK-1.2`
- **Verification**: Test logger initialization, file rotation, and verify no transcription strings appear in log outputs.

---

#### `TASK-1.4`: SQLite Database & Schema Migration Engine
- **Component**: `voice_agent/storage/database.py`
- **Objective**: Create lightweight SQLite connection manager with migration support for history and app metadata.
- **Specifications & Requirements**:
  - Database stored at `%APPDATA%/PCVoiceAgent/data.db`.
  - Schema tables:
    - `history`: `id`, `timestamp`, `mode` (dictation/control), `raw_text`, `processed_text`, `status` (success/failed/cancelled), `details` (JSON metadata).
    - `app_metadata`: Key-value store for internal state and migrations.
  - WAL mode enabled for concurrent read/write safety without blocking the UI thread.
  - Retention purge method: delete records older than `N` days.
- **Target Files**:
  - `voice_agent/storage/database.py`
  - `voice_agent/storage/models.py`
  - `tests/test_database.py`
- **Dependencies**: `TASK-1.2`
- **Verification**: Test database initialization, migrations, CRUD operations, and retention cleanup.

---

#### `TASK-1.5`: PySide6 Application Skeleton & Lifecycle
- **Component**: `voice_agent/app/main.py`, `voice_agent/app/lifecycle.py`
- **Objective**: Create the core PySide6 application lifecycle, event loop, single-instance lock, and graceful shutdown handler.
- **Specifications & Requirements**:
  - Single-instance enforcement using a Windows named mutex or local QLocalServer/QLocalSocket.
  - Handle OS signals (`SIGINT`, `SIGTERM`, Windows shutdown messages).
  - Background worker thread infrastructure for asynchronous audio/STT/action execution without freezing Qt event loop.
  - Clean shutdown sequence: stop hotkeys → terminate audio recorder → wait for active threads → close DB.
- **Target Files**:
  - `voice_agent/app/main.py`
  - `voice_agent/app/lifecycle.py`
  - `tests/test_lifecycle.py`
- **Dependencies**: `TASK-1.1`, `TASK-1.2`, `TASK-1.3`, `TASK-1.4`
- **Verification**: Launch app, verify single-instance check prevents duplicate launch, verify clean exit.

---

### Phase 2: Audio Capture & Local Speech-to-Text Subsystem

---

#### `TASK-2.1`: Microphone Enumerator & Fallback Handler
- **Component**: `voice_agent/audio/microphone.py`
- **Objective**: Interface with `sounddevice` to query, select, and manage microphone devices.
- **Specifications & Requirements**:
  - Enumerate all available audio input devices with their Windows device IDs and host APIs (MME, DirectSound, WASAPI).
  - Validate selected microphone availability.
  - Graceful fallback: If the configured microphone is disconnected, automatically fall back to Windows system default input and dispatch a notification signal.
  - Provide a safe callback/polling mechanism for hot-plugged or disconnected audio devices.
- **Target Files**:
  - `voice_agent/audio/microphone.py`
  - `tests/test_microphone.py`
- **Dependencies**: `TASK-1.1`, `TASK-1.2`
- **Verification**: Unit tests with mocked `sounddevice` device queries and fallback triggers.

---

#### `TASK-2.2`: Ring-Buffered Audio Capture Recorder
- **Component**: `voice_agent/audio/recorder.py`
- **Objective**: Capture audio from the microphone into an in-memory buffer ready for Whisper processing.
- **Specifications & Requirements**:
  - Standard audio format: 16,000 Hz, 1 channel (mono), 32-bit float or 16-bit PCM numpy array.
  - Methods: `start_recording()`, `stop_recording() -> np.ndarray`, `is_recording() -> bool`.
  - Non-blocking audio capture using `sounddevice.InputStream` with a thread-safe memory buffer / queue.
  - Zero permanent disk writes by default (in-memory only).
  - Minimum/maximum audio length protection (ignore clicks < 0.1s; handle safety cutoffs > 60s).
- **Target Files**:
  - `voice_agent/audio/recorder.py`
  - `tests/test_recorder.py`
- **Dependencies**: `TASK-2.1`
- **Verification**: Test audio recording start/stop lifecycle with synthetic and mocked streams.

---

#### `TASK-2.3`: Abstract STT Engine Interface & Model Manager
- **Component**: `voice_agent/stt/engine.py`, `voice_agent/stt/models.py`
- **Objective**: Define the STT abstraction and manage local Whisper model files.
- **Specifications & Requirements**:
  - `SpeechToTextEngine` ABC with method `transcribe(audio: np.ndarray, language: str | None) -> str`.
  - `ModelManager`:
    - Manage standard models: `tiny`, `base` (default), `small`, `medium`.
    - Model caching directory in `%APPDATA%/PCVoiceAgent/models/`.
    - Check model local presence, compute file hashes, report download status/progress.
    - Provide metadata on model tradeoffs (RAM/VRAM consumption, CPU vs. GPU speed).
- **Target Files**:
  - `voice_agent/stt/engine.py`
  - `voice_agent/stt/models.py`
  - `tests/test_stt_models.py`
- **Dependencies**: `TASK-1.2`
- **Verification**: Unit tests verifying model resolution, path checks, and interface contracts.

---

#### `TASK-2.4`: faster-whisper Local Engine Implementation
- **Component**: `voice_agent/stt/whisper_engine.py`
- **Objective**: Implement local Whisper inference using `faster-whisper` (CTranslate2).
- **Specifications & Requirements**:
  - Automatic device detection: CUDA/GPU with `float16` if available, fallback to CPU with `int8`.
  - Thread-safe inference execution off the UI thread.
  - Handle language parameter (default English `"en"`).
  - Beam size and temperature configuration for low-latency transcription.
  - Error handling: Model loading errors, out-of-memory errors, corrupted audio buffers.
- **Target Files**:
  - `voice_agent/stt/whisper_engine.py`
  - `tests/test_whisper_engine.py`
- **Dependencies**: `TASK-2.2`, `TASK-2.3`
- **Verification**: Run transcription on synthetic WAV sample; assert output string returned correctly.

---

### Phase 3: Dictation Mode & Text Insertion Engine

---

#### `TASK-3.1`: Global Hotkey Hook & Tap vs. Hold Engine
- **Component**: `voice_agent/input/hotkeys.py`, `voice_agent/input/gesture.py`
- **Objective**: Global detection of Right Ctrl and Right Alt with reliable discrimination between tap and hold.
- **Specifications & Requirements**:
  - Use `pynput.keyboard` (or Win32 low-level hook `WH_KEYBOARD_LL`) to capture keys globally even when unfocused.
  - Gesture recognition algorithm:
    - Key down: Start timer.
    - Key up within threshold (e.g. < 300ms): Treat as **Tap** (Toggle mode: Start or Stop).
    - Key held past threshold: Treat as **Hold** (Push-to-talk: Started on down, Stops on release).
  - Independent hotkeys for:
    - Dictation (default `Right Ctrl`).
    - Control (default `Right Alt`).
  - Hotkey reconfiguration support without restarting the application.
- **Target Files**:
  - `voice_agent/input/hotkeys.py`
  - `voice_agent/input/gesture.py`
  - `tests/test_hotkeys.py`
- **Dependencies**: `TASK-1.2`
- **Verification**: Unit tests simulating key press/release timestamps verifying tap vs. hold state events.

---

#### `TASK-3.2`: Win32 Clipboard Manager (Format Preservation)
- **Component**: `voice_agent/clipboard/manager.py`
- **Objective**: Robust Windows clipboard preservation, restoration, and injection.
- **Specifications & Requirements**:
  - Use `pywin32` (`win32clipboard`) for native Windows clipboard access.
  - Save snapshot of existing clipboard formats (text, rich text, bitmap DIB, HTML, custom formats).
  - Place transcribed text into `CF_UNICODETEXT`.
  - Restore snapshot completely after paste operation.
  - Configurable option: `"Keep dictated text in clipboard"` (bypasses restoration when enabled).
  - Retry logic for clipboard locking conflicts (Windows clipboard lock timeout/backoff).
- **Target Files**:
  - `voice_agent/clipboard/manager.py`
  - `tests/test_clipboard.py`
- **Dependencies**: `TASK-1.2`
- **Verification**: Test clipboard save -> replace -> restore flow with text, image, and multi-format data.

---

#### `TASK-3.3`: Text Normalizer & Linguistic Cleaner
- **Component**: `voice_agent/dictation/normalizer.py`
- **Objective**: Clean and normalize transcribed text without semantic alteration.
- **Specifications & Requirements**:
  - Capitalization of initial letters and sentences.
  - Spacing cleanup (trim double spaces, punctuation spacing).
  - Repeated-word transcription glitch removal (e.g., "I think I think" → "I think"), while **preserving legitimate repetition** (e.g., "No, no, that's not what I meant").
  - **Critical spec rule**: Linguistic cleanup allowed; semantic rewriting strictly prohibited (No LLM).
- **Target Files**:
  - `voice_agent/dictation/normalizer.py`
  - `tests/test_normalizer.py`
- **Dependencies**: `TASK-1.1`
- **Verification**: Exhaustive test suite covering all cases, quotes, contractions, and repetition edge cases.

---

#### `TASK-3.4`: Dictation Formatting Command Parser
- **Component**: `voice_agent/dictation/formatter.py`
- **Objective**: Convert spoken formatting phrases into literal formatting and punctuation.
- **Specifications & Requirements**:
  - Supported phrases:
    - `"new line"` → `\n`
    - `"new paragraph"` → `\n\n`
    - `"comma"` → `,`
    - `"period"` → `.`
    - `"question mark"` → `?`
    - `"exclamation mark"` → `!`
  - Case-insensitive matching at word boundaries.
  - Spacing adjustments (e.g., remove space before punctuation, capitalize next letter after period/question mark).
  - Must never trigger computer control commands.
- **Target Files**:
  - `voice_agent/dictation/formatter.py`
  - `tests/test_formatter.py`
- **Dependencies**: `TASK-3.3`
- **Verification**: Unit tests verifying formatting transformations with varied phrases and sentence positions.

---

#### `TASK-3.5`: Hybrid Text Inserter & Fallback Notifier
- **Component**: `voice_agent/dictation/inserter.py`
- **Objective**: Insert normalized text into the active Windows application with zero data loss.
- **Specifications & Requirements**:
  - Primary strategy:
    1. Capture current clipboard.
    2. Write transcription to clipboard.
    3. Simulate `Ctrl+V` key combination via `SendInput` (Win32 API).
    4. Small delay (~20-50ms).
    5. Restore original clipboard contents.
  - Fallback strategy:
    - If clipboard paste fails or no focused window is available:
    - Keep text in clipboard.
    - Trigger UI notification: `"No text field detected — copied to clipboard"`.
    - Never silently discard dictated text.
- **Target Files**:
  - `voice_agent/dictation/inserter.py`
  - `tests/test_inserter.py`
- **Dependencies**: `TASK-3.2`
- **Verification**: Test paste execution, fallback triggers, and clipboard retention on simulated failure.

---

#### `TASK-3.6`: Dictation Pipeline Coordinator & State Machine
- **Component**: `voice_agent/dictation/processor.py`
- **Objective**: Coordinate audio capture, STT, normalization, formatting, and insertion with state transitions.
- **Specifications & Requirements**:
  - State machine: `READY → LISTENING → PROCESSING → TYPING → READY`.
  - Asynchronous execution: Audio processing & STT run on background worker thread.
  - Emit Qt signals on each state transition: `state_changed(DictationState)`, `text_ready(str)`, `error_occurred(str)`.
  - Record completed dictation transcripts to SQLite history repository.
  - Graceful recovery: On any error, return to `READY` and display notification.
- **Target Files**:
  - `voice_agent/dictation/processor.py`
  - `tests/test_dictation_processor.py`
- **Dependencies**: `TASK-2.2`, `TASK-2.4`, `TASK-3.1`, `TASK-3.3`, `TASK-3.4`, `TASK-3.5`, `TASK-1.4`
- **Verification**: Test complete dictation cycle from hotkey trigger to insertion with mock audio input.

---

### Phase 4: UI Subsystem (Floating Overlay & System Tray)

---

#### `TASK-4.1`: Floating Status Overlay Widget
- **Component**: `voice_agent/ui/overlay.py`
- **Objective**: Provide an unobtrusive, always-on-top, non-stealing floating status overlay.
- **Specifications & Requirements**:
  - PySide6 frameless window (`Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool`).
  - Does not steal focus from active applications (`Qt.WindowDoesNotAcceptFocus`, `WA_ShowWithoutActivating`).
  - States visualized: `Ready`, `Listening…`, `Processing…`, `Typing…`, `No text field detected`, `Error`.
  - Visual differentiation: Distinct style/color/badge for **Dictation Mode** vs. **Control Mode**.
  - Drag-and-drop repositioning with position saved in `config.toml`.
  - Subtle animations (fade-in, fade-out, pulsing listening indicator).
- **Target Files**:
  - `voice_agent/ui/overlay.py`
  - `tests/test_overlay.py`
- **Dependencies**: `TASK-1.2`, `TASK-1.5`
- **Verification**: Test overlay display, non-stealing window flags, state change slots, and position persistence.

---

#### `TASK-4.2`: Windows System Tray Integration
- **Component**: `voice_agent/ui/tray.py`
- **Objective**: Implement Windows notification area (system tray) icon and context menu.
- **Specifications & Requirements**:
  - `QSystemTrayIcon` with high-DPI icon assets.
  - Context menu items:
    - Status Indicator (`"Status: Ready"` / `"Status: Disabled"`)
    - Quick Toggle (Enable/Disable Agent)
    - Settings… (opens Settings dialog)
    - History… (opens History window)
    - Separator
    - Exit
  - Native Windows notifications (tray balloons/toasts) for errors and fallback messages.
  - Left-click toggles status/settings; right-click opens context menu.
- **Target Files**:
  - `voice_agent/ui/tray.py`
  - `voice_agent/resources/` (tray icons)
  - `tests/test_tray.py`
- **Dependencies**: `TASK-1.5`
- **Verification**: Test tray creation, menu action triggers, and notification signals.

---

### Phase 5: Local Command Parser & Safety Engine

---

#### `TASK-5.1`: Structured Action Request Models & Base Action
- **Component**: `voice_agent/control/actions/base.py`
- **Objective**: Define strong typed Action data models, execution context, and result structures.
- **Specifications & Requirements**:
  - Action models using Python dataclasses or Pydantic:
    - `ActionType` enum: `OPEN_APP`, `CLOSE_APP`, `SWITCH_WINDOW`, `TYPE_TEXT`, `PRESS_KEY`, `HOTKEY`, `MOVE_MOUSE`, `CLICK`, `OPEN_URL`, `SEARCH_WEB`, `READ_CLIPBOARD`, `COPY`, `PASTE`, `OPEN_FILE`, `RENAME_FILE`, `MOVE_FILE`, `DELETE_FILE`, `OPEN_FOLDER`.
    - `RiskLevel` enum: `LOW`, `MEDIUM`, `HIGH`.
    - `ActionRequest`: `action_type`, `params: dict[str, Any]`, `risk_level`, `raw_command`, `confirmed: bool`.
    - `ActionResult`: `success: bool`, `output: Any`, `error_message: str | None`.
  - Base `Action` interface with `validate(params)` and `execute(params) -> ActionResult`.
- **Target Files**:
  - `voice_agent/control/actions/base.py`
  - `tests/test_action_models.py`
- **Dependencies**: `TASK-1.1`
- **Verification**: Test model serialization, schema validation, and error reporting.

---

#### `TASK-5.2`: Local Rule-Based Command Parser
- **Component**: `voice_agent/control/parser.py`
- **Objective**: Implement a fast, local-first rule/regex parser to convert speech to structured actions.
- **Specifications & Requirements**:
  - **No cloud LLM**. Uses pattern matching, regex, and intent rules.
  - Parse intents:
    - Application control: `"open notepad"`, `"launch chrome"`, `"close window"`, `"switch to slack"`.
    - Keyboard/typing: `"press enter"`, `"press backspace"`, `"type Hello world"`, `"shortcut ctrl c"`.
    - Mouse: `"click"`, `"double click"`, `"right click"`.
    - Web/URL: `"open github.com"`, `"search for python documentation"`.
    - File operations: `"open file report.txt"`, `"delete file draft.doc"`, `"rename file a to b"`.
  - Multi-command chaining with `"and"` / `"then"` (e.g., `"open notepad and type Hello"`).
  - Ambiguous / unsupported commands: Return `UnsupportedCommandResult` (no guessing).
- **Target Files**:
  - `voice_agent/control/parser.py`
  - `tests/test_parser.py`
- **Dependencies**: `TASK-5.1`
- **Verification**: Comprehensive unit test suite covering dozens of command phrases and unsupported edge cases.

---

#### `TASK-5.3`: Action Parameter & Path Validator
- **Component**: `voice_agent/control/action_validator.py`
- **Objective**: Enforce strict security boundaries by validating all action parameters before execution.
- **Specifications & Requirements**:
  - Path validation: Prevent path traversal attacks (`..`), normalize Windows paths, ensure file exists when required.
  - Prohibit arbitrary shell command injection (do not pass raw strings to `cmd.exe` or `powershell.exe`).
  - Validate application names against allowed/recognized binaries or Windows Start Menu shortcuts.
  - Validate URLs: Ensure valid schemes (`http://`, `https://`).
- **Target Files**:
  - `voice_agent/control/action_validator.py`
  - `tests/test_action_validator.py`
- **Dependencies**: `TASK-5.1`
- **Verification**: Test rejection of malicious paths, malformed URLs, and invalid parameters.

---

#### `TASK-5.4`: Risk Classification Engine
- **Component**: `voice_agent/control/risk.py`
- **Objective**: Classify every ActionRequest into Low, Medium, or High risk based on potential impact.
- **Specifications & Requirements**:
  - **Low Risk** (Immediate execution): Open app, open URL, switch window, type text, basic keypress.
  - **Medium Risk** (Contextual confirmation): Move file, rename file, close application, browser form submissions.
  - **High Risk** (Mandatory confirmation): Delete file, system shutdown, restart, emptying trash.
  - Evaluate dynamic parameter context (e.g., deleting a file in user directory vs. temp directory).
- **Target Files**:
  - `voice_agent/control/risk.py`
  - `tests/test_risk.py`
- **Dependencies**: `TASK-5.1`
- **Verification**: Unit tests verifying correct classification across all action types and parameters.

---

#### `TASK-5.5`: Risk Confirmation Modal Dialog
- **Component**: `voice_agent/ui/confirmation.py`
- **Objective**: Display an explicit, accessible confirmation dialog for Medium and High risk actions.
- **Specifications & Requirements**:
  - PySide6 modal dialog displaying exact action description (e.g., `"Delete file 'report.docx'?"`).
  - Clear buttons: `Confirm` (default focus) and `Cancel` (Esc key).
  - Visual indicators matching risk severity (Yellow for Medium, Red warning for High).
  - Timeout countdown: Automatically cancel if unattended for `N` seconds.
  - Never execute high-risk operations without explicit user confirmation.
- **Target Files**:
  - `voice_agent/ui/confirmation.py`
  - `tests/test_confirmation_dialog.py`
- **Dependencies**: `TASK-5.4`, `TASK-1.5`
- **Verification**: Test dialog rendering, keyboard shortcut handling (Enter/Esc), and timeout cancellation.

---

### Phase 6: Computer Control Action Implementations

---

#### `TASK-6.1`: Application Control Actions (Launch, Close, Switch)
- **Component**: `voice_agent/control/actions/applications.py`
- **Objective**: Implement Windows application opening, switching, and closing using `pywin32` and `subprocess`.
- **Specifications & Requirements**:
  - `open_application(app_name)`: Search registered Windows apps / App Paths / Start Menu and launch via `subprocess.Popen`.
  - `close_application(app_name or window_title)`: Gracefully request window close (`WM_CLOSE`) via Win32 API.
  - `switch_window(window_title)`: Enumerate top-level windows, find match, bring to foreground (`SetForegroundWindow`).
  - Graceful failure when window or application is not found.
- **Target Files**:
  - `voice_agent/control/actions/applications.py`
  - `tests/test_action_applications.py`
- **Dependencies**: `TASK-5.1`, `TASK-5.3`
- **Verification**: Unit tests mocking Win32 window APIs and verifying parameters.

---

#### `TASK-6.2`: Keyboard & Typing Actions
- **Component**: `voice_agent/control/actions/keyboard.py`
- **Objective**: Implement single key presses, keyboard shortcuts, and text typing.
- **Specifications & Requirements**:
  - Use `pynput` / Win32 `SendInput` for reliable simulation.
  - `type_text(text)`: Type explicitly requested text strings.
  - `press_key(key_name)`: Press and release special keys (`Enter`, `Tab`, `Escape`, `Backspace`, `Space`, arrow keys).
  - `hotkey(keys)`: Press composite hotkey chords (e.g. `["ctrl", "c"]`, `["alt", "tab"]`, `["win", "d"]`).
- **Target Files**:
  - `voice_agent/control/actions/keyboard.py`
  - `tests/test_action_keyboard.py`
- **Dependencies**: `TASK-5.1`, `TASK-5.3`
- **Verification**: Test key chord parsing, virtual key code resolution, and simulated execution.

---

#### `TASK-6.3`: Mouse Movement & Click Actions
- **Component**: `voice_agent/control/actions/mouse.py`
- **Objective**: Implement basic mouse movement and clicking.
- **Specifications & Requirements**:
  - `click(button="left"|"right"|"middle", double=False)`: Perform click at current cursor position.
  - `move_mouse(x, y)`: Move cursor to coordinates or offset.
  - Safe boundary checks (keep cursor within virtual desktop geometry).
- **Target Files**:
  - `voice_agent/control/actions/mouse.py`
  - `tests/test_action_mouse.py`
- **Dependencies**: `TASK-5.1`, `TASK-5.3`
- **Verification**: Test mouse coordinate calculation and boundary constraint enforcement.

---

#### `TASK-6.4`: Browser & Web Search Actions
- **Component**: `voice_agent/control/actions/browser.py`
- **Objective**: Implement web URL navigation and search engine queries.
- **Specifications & Requirements**:
  - `open_url(url)`: Validate URL and open in user's default browser via `webbrowser.open(url)`.
  - `search_web(query)`: Encode search term and open default search provider (Google/Bing/DuckDuckGo from config).
  - Sanitize query string against injection attacks.
- **Target Files**:
  - `voice_agent/control/actions/browser.py`
  - `tests/test_action_browser.py`
- **Dependencies**: `TASK-5.1`, `TASK-5.3`
- **Verification**: Unit tests verifying URL generation, escaping, and browser launcher dispatch.

---

#### `TASK-6.5`: File & Folder System Actions
- **Component**: `voice_agent/control/actions/files.py`
- **Objective**: Implement file and folder operations using Python standard library (`pathlib`, `shutil`).
- **Specifications & Requirements**:
  - `open_file(path)` / `open_folder(path)`: Open using Windows shell (`os.startfile`).
  - `rename_file(old_path, new_path)`: Atomic file rename with existence check.
  - `move_file(source, destination)`: Move file/folder to target directory.
  - `delete_file(path, send_to_trash=True)`: Delete file (preferably move to Recycle Bin via `send2trash` or `SHFileOperation`).
  - Strict sandboxing: Reject system directory targets (`C:\Windows`, `Program Files`, etc.).
- **Target Files**:
  - `voice_agent/control/actions/files.py`
  - `tests/test_action_files.py`
- **Dependencies**: `TASK-5.1`, `TASK-5.3`
- **Verification**: Test file manipulation within isolated temporary directory fixture.

---

#### `TASK-6.6`: Clipboard Control Actions
- **Component**: `voice_agent/control/actions/clipboard.py`
- **Objective**: Control mode clipboard operations (copy, paste, read).
- **Specifications & Requirements**:
  - `copy()`: Trigger standard `Ctrl+C` shortcut to copy selection.
  - `paste()`: Trigger standard `Ctrl+V` shortcut to paste clipboard.
  - `read_clipboard() -> str`: Read text currently in clipboard.
- **Target Files**:
  - `voice_agent/control/actions/clipboard.py`
  - `tests/test_action_clipboard.py`
- **Dependencies**: `TASK-3.2`, `TASK-5.1`
- **Verification**: Test copy and paste action dispatches with mocked system input.

---

#### `TASK-6.7`: Multi-Step Command Router & Control Pipeline
- **Component**: `voice_agent/control/command_router.py`
- **Objective**: Full Control Mode pipeline coordination: STT → Parse → Validate → Risk → Confirm → Execute → Report.
- **Specifications & Requirements**:
  - Control state machine: `READY → LISTENING → PROCESSING → VALIDATING → CONFIRMING → EXECUTING → RESULT → READY`.
  - Sequential execution of multi-step action chains with short pauses.
  - Abort execution immediately if any step fails or user cancels confirmation.
  - Store command results and execution status in SQLite history database.
  - Emit status updates to the floating overlay.
- **Target Files**:
  - `voice_agent/control/command_router.py`
  - `tests/test_command_router.py`
- **Dependencies**: `TASK-5.2`, `TASK-5.3`, `TASK-5.4`, `TASK-5.5`, `TASK-6.1` through `TASK-6.6`
- **Verification**: End-to-end unit test of chained commands (`"open notepad and type Hello"`).

---

### Phase 7: History, Settings & Windows System Integration

---

#### `TASK-7.1`: History Repository & SQLite Storage
- **Component**: `voice_agent/storage/history.py`
- **Objective**: Repository pattern for recording, searching, and managing user interaction history.
- **Specifications & Requirements**:
  - Methods: `add_entry()`, `get_entries(limit, offset, query, mode)`, `delete_entry(id)`, `clear_history()`.
  - Filter by date range and operational mode (Dictation vs. Control).
  - Background auto-cleanup based on configured retention limit (default 30 days).
  - Export history to JSON/CSV for user transparency.
- **Target Files**:
  - `voice_agent/storage/history.py`
  - `tests/test_history_repo.py`
- **Dependencies**: `TASK-1.4`
- **Verification**: Test insertion, multi-criteria filtering, pagination, deletion, and retention cleanup.

---

#### `TASK-7.2`: History Viewer Window
- **Component**: `voice_agent/ui/history.py`
- **Objective**: PySide6 desktop window for viewing, searching, and deleting past interactions.
- **Specifications & Requirements**:
  - Clean table/list view with columns: Timestamp, Mode, Spoken Text, Result/Status.
  - Search bar with live filtering.
  - Filter by Mode: All, Dictation Only, Control Only.
  - Buttons: `"Copy to Clipboard"`, `"Delete Entry"`, `"Clear All History"`.
  - Responsive pagination or lazy loading for thousands of entries.
- **Target Files**:
  - `voice_agent/ui/history.py`
  - `tests/test_history_ui.py`
- **Dependencies**: `TASK-7.1`, `TASK-1.5`
- **Verification**: Test UI rendering, search query filtering, and single/bulk deletion.

---

#### `TASK-7.3`: Settings Dialog (Preferences Configuration)
- **Component**: `voice_agent/ui/settings.py`
- **Objective**: Multi-tab graphical settings window reflecting all spec requirements.
- **Specifications & Requirements**:
  - **Dictation Tab**: Hotkey selector (Right Ctrl default), Activation mode (Push-to-talk / Toggle / Both), STT Model picker (`tiny`, `base`, `small`, `medium`) with resource indicators, Language picker, Formatting toggle, Clipboard restoration toggle.
  - **Control Tab**: Hotkey selector (Right Alt default), Activation mode, Confirmation preferences (Medium risk confirm toggle).
  - **Audio Tab**: Microphone dropdown with live device enumeration and test meter.
  - **General Tab**: Run at Windows startup checkbox, History retention days, Overlay toggle & reset position.
  - Save, Apply, and Cancel actions syncing directly with `config.toml`.
- **Target Files**:
  - `voice_agent/ui/settings.py`
  - `tests/test_settings_ui.py`
- **Dependencies**: `TASK-1.2`, `TASK-2.1`, `TASK-2.3`, `TASK-1.5`
- **Verification**: Test loading settings into widgets, modifying values, and verifying saved TOML output.

---

#### `TASK-7.4`: Windows Startup (Run at Startup) Registry Helper
- **Component**: `voice_agent/app/startup.py`
- **Objective**: Enable/disable automatic application launch on Windows user login.
- **Specifications & Requirements**:
  - Use `winreg` to interact with `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`.
  - Methods: `is_startup_enabled() -> bool`, `set_startup_enabled(enabled: bool)`.
  - Register path to executable with `--minimized` or `--tray` argument.
  - Clean unregistration without corrupting other startup registry keys.
- **Target Files**:
  - `voice_agent/app/startup.py`
  - `tests/test_startup.py`
- **Dependencies**: `TASK-1.2`
- **Verification**: Test registry entry read/write in mock environment or isolated test key.

---

### Phase 8: Quality Assurance, Packaging & Distribution

---

#### `TASK-8.1`: Comprehensive Unit & Integration Test Suite
- **Component**: `tests/`
- **Objective**: Build a high-coverage automated test suite covering all modules without external hardware dependencies.
- **Specifications & Requirements**:
  - Unit tests for all pure logic: normalizer, formatter, command parser, risk engine, validator, config, history repository.
  - Mocked hardware tests: Simulated sounddevice audio stream, synthetic Whisper transcription, mocked Win32 clipboard and keystrokes.
  - State machine transition tests for both Dictation and Control modes.
  - Fast test execution (`pytest` completes under 30 seconds).
- **Target Files**:
  - `tests/conftest.py`
  - `tests/test_*.py`
- **Dependencies**: All Phase 1–7 tasks
- **Verification**: Run `pytest --cov=voice_agent tests/` with high test coverage and zero failures.

---

#### `TASK-8.2`: End-to-End Pipeline & Stress Testing
- **Component**: `tests/e2e/`
- **Objective**: Verify end-to-end interaction loops, rapid key-tapping, and failure resilience.
- **Specifications & Requirements**:
  - Test rapid tap vs. hold sequences to guarantee no deadlocks or state desynchronization.
  - Test clipboard restoration with multiple concurrent applications.
  - Verify error handling: Disconnected microphone, STT out-of-memory, invalid window targets.
  - Ensure zero silent loss of text in all dictation failure scenarios.
- **Target Files**:
  - `tests/e2e/test_dictation_e2e.py`
  - `tests/e2e/test_control_e2e.py`
- **Dependencies**: `TASK-8.1`
- **Verification**: Stress test runner passing 100 consecutive simulated dictations without leaks or crashes.

---

#### `TASK-8.3`: PyInstaller Executable Build Pipeline
- **Component**: `packaging/`
- **Objective**: Package the entire application into a standalone Windows executable.
- **Specifications & Requirements**:
  - PyInstaller spec file (`voice_agent.spec`).
  - Bundle PySide6 binaries, CTranslate2/faster-whisper DLLs, and default icon assets.
  - Exclude unnecessary test files and build caches to minimize binary size.
  - Windowless background execution with tray icon support (`noconsole` option).
  - External model storage: Do not bloat executable with large Whisper weights; download on first run or package separately.
- **Target Files**:
  - `packaging/voice_agent.spec`
  - `scripts/build.py`
- **Dependencies**: `TASK-8.1`
- **Verification**: Run build script, execute output binary on a clean Windows environment, verify tray and hotkeys function.

---

#### `TASK-8.4`: Inno Setup Windows Installer Script
- **Component**: `packaging/installer.iss`
- **Objective**: Create a production-ready Windows installer with uninstaller, desktop shortcut, and Start Menu entry.
- **Specifications & Requirements**:
  - Inno Setup `.iss` script configuring:
    - Application name: "PC Voice Agent"
    - Install directory: `{autopf}\PC Voice Agent`
    - Start Menu shortcut and optional Desktop shortcut
    - Optional "Run on Windows startup" checkbox during install
    - Automatic process termination if updating an existing running version
    - Clean uninstallation removing files while leaving user database/config optional
- **Target Files**:
  - `packaging/installer.iss`
  - `scripts/build_installer.ps1`
- **Dependencies**: `TASK-8.3`
- **Verification**: Compile installer using ISCC (Inno Setup Compiler) and verify installation and uninstallation on Windows.

---

## 4. Definition of Done (DoD) Checklist

For any task to be marked as complete:
- [ ] Code strictly follows Python 3.12+ type hinting and passes `mypy --strict`.
- [ ] Code passes `ruff check` and `ruff format` without errors.
- [ ] Comprehensive unit tests written and passing in `pytest`.
- [ ] No regression introduced to existing components.
- [ ] Architecture preserves separation of concerns (no UI logic in core processing; no LLM in dictation).
- [ ] Privacy constraints maintained (no remote network calls; no audio data persisted).
- [ ] Task checkbox updated in this document.
