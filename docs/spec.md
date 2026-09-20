# Windows Local Voice Agent
## Implementation-Ready Product Specification

## 1. Product Summary

A Windows desktop voice agent designed primarily for **speech-to-text typing**, with a secondary **computer-control mode**.

The product has two clearly separated operating modes:

1. **Dictation Mode**
   - Speech → lightly normalized text → immediately inserted into the active application.
   - Never interprets speech as commands.
   - Never uses an LLM.
   - Runs locally.

2. **Control Mode**
   - Speech → command interpretation → validated computer action.
   - Uses a local command parser/rules engine.
   - Executes only through a predefined Action API.
   - Uses risk-based confirmation for consequential actions.

The product is **local-first and fully offline-capable**. No cloud AI service, API key, or ongoing AI credit is required.

---

# 2. Product Principles

1. **Voice-first, keyboard-friendly**
2. **Local-first**
3. **AI is not required**
4. **Dictation and control are strictly separated**
5. **Fast feedback**
6. **Never silently lose dictated text**
7. **Explicit, validated computer actions**
8. **Risk-based confirmation**
9. **Simple Windows-native UX**
10. **Extend functionality without changing the core architecture**

---

# 3. Platform

### Target

- Windows only for the initial implementation.

### Future

The architecture should avoid unnecessary Windows-specific coupling in the core business logic so other platforms could theoretically be supported later.

Cross-platform support is **not an MVP requirement**.

---

# 4. Core User Experience

## 4.1 Dictation

Default hotkey:

**Right Ctrl**

Two activation behaviors:

### Push-to-talk

Hold Right Ctrl:

`READY → LISTENING`

Release:

`LISTENING → PROCESSING → TYPING → READY`

### Toggle

Tap Right Ctrl:

`READY → LISTENING`

Tap again:

`LISTENING → PROCESSING → TYPING → READY`

No automatic silence detection is required.

The user explicitly controls when recording stops.

---

# 5. Dictation Mode

## 5.1 Purpose

Convert speech into text and insert it into the currently active application.

Example:

User says:

> "I think the meeting is tomorrow"

Application inserts:

> I think the meeting is tomorrow.

It must **not** reinterpret the sentence.

If the user says:

> "Write an email to John telling him I'm coming late"

Dictation Mode outputs the spoken meaning as text rather than composing an email.

---

# 6. Dictation Processing Pipeline

```text
Hotkey
   ↓
Microphone Capture
   ↓
Local STT
   ↓
Light Text Normalization
   ↓
Formatting
   ↓
Clipboard/Text Insertion
   ↓
Restore Clipboard
   ↓
READY
```

---

# 7. Speech-to-Text

## Requirements

- Local speech recognition.
- No cloud STT.
- No API key.
- No internet dependency.

Recommended implementation:

- `faster-whisper` or equivalent local Whisper implementation.

The application should ship with a sensible medium-sized model.

Settings should allow the user to choose between:

- Smaller/faster model
- Default balanced model
- Larger/more accurate model

The UI should communicate the trade-off between:

- Accuracy
- Processing speed
- RAM/CPU/GPU usage

---

# 8. Language

Default:

**English**

Settings should allow the user to select another supported STT language.

MVP does **not** require automatic language detection.

The selected language is explicitly passed to the STT engine.

---

# 9. Text Normalization

Dictation should not be completely raw.

Allowed normalization includes:

- Capitalization
- Punctuation
- Sentence boundaries
- Paragraph boundaries
- Obvious repeated-word transcription errors
- Whitespace cleanup

Example:

Spoken:

> "I think I think the meeting is tomorrow."

Possible output:

> "I think the meeting is tomorrow."

However, legitimate repetition must be preserved.

Example:

> "No, no, that's not what I meant."

Should remain essentially:

> "No, no, that's not what I meant."

### Critical rule

**Linguistic cleanup is allowed. Semantic rewriting is not.**

---

# 10. Dictation Formatting Commands

Supported explicit formatting commands:

- "new line"
- "new paragraph"
- "comma"
- "period"
- "question mark"
- "exclamation mark"

These are formatting instructions only.

They must never become computer-control commands.

---

# 11. Text Insertion

Use a hybrid insertion strategy.

### Normal dictated text

Preferred:

```text
Save clipboard
    ↓
Put transcription in clipboard
    ↓
Paste
    ↓
Restore clipboard
```

This provides fast and reliable insertion.

### Keyboard/control operations

Use simulated keyboard events.

### Fallback

If clipboard insertion is unsuitable or fails:

- Fall back to simulated typing where practical.

---

# 12. Clipboard Handling

Default behavior:

1. Save current clipboard.
2. Put dictated text into clipboard.
3. Paste into active application.
4. Restore previous clipboard.

The restoration should preserve the previous clipboard as closely as Windows permits, including non-text clipboard content where practical.

Optional setting:

**Keep dictated text in clipboard**

If enabled, the application does not restore the previous clipboard.

---

# 13. No Text Input Available

Dictation must never silently lose text.

If insertion fails or there is no usable text target:

1. Keep the transcription.
2. Copy it to the clipboard.
3. Display a brief notification.

Example:

> No text field detected — copied to clipboard.

The user can then paste manually.

---

# 14. Dictation Overlay

A small floating overlay provides immediate status feedback.

Possible states:

- Ready
- Listening…
- Processing…
- Typing…
- No text field detected
- Error

The overlay should be:

- Small
- Unobtrusive
- Movable
- Configurable
- Always understandable at a glance

The user must be able to distinguish Dictation Mode from Control Mode.

---

# 15. Control Mode

Default hotkey:

**Right Alt**

Activation supports both:

### Push-to-talk

Hold Right Alt → speak → release.

### Toggle

Tap Right Alt → listening → tap again → process command.

Control Mode has its own overlay/state indicator.

---

# 16. Control Mode Pipeline

```text
Control Hotkey
      ↓
Microphone Capture
      ↓
Local STT
      ↓
Command Parser
      ↓
Structured Action Request
      ↓
Risk Classification
      ↓
Confirmation if Required
      ↓
Action Validator
      ↓
Action Executor
      ↓
Result
```

---

# 17. Control Mode Scope

MVP supports:

### Applications

- Open applications
- Close applications
- Switch windows

### Keyboard

- Individual key presses
- Keyboard shortcuts
- Hotkeys

### Typing

- Type explicitly requested text

### Mouse

- Basic movement
- Clicking

### URLs

- Open URLs
- Open websites

### Clipboard

- Copy
- Paste
- Related clipboard operations

### Files

- Open
- Rename
- Move
- Delete

### Folders

- Open folders
- Navigate folders

### Browser

- Basic navigation
- Perform web searches

### Multi-step commands

Multiple supported actions can be chained when the requested operation can be represented through the defined Action API.

---

# 18. Explicit Action API

The command interpreter must never receive unrestricted access to the computer.

Instead, it produces structured actions.

Example conceptual actions:

```text
open_application()
close_application()
switch_window()
type_text()
press_key()
hotkey()
move_mouse()
click()
open_url()
search_web()
read_clipboard()
copy()
paste()
open_file()
rename_file()
move_file()
delete_file()
open_folder()
```

The application validates each action before execution.

This provides a clear security boundary between:

**Speech interpretation**

and

**Actual computer control**

---

# 19. Safety / Confirmation

Use risk-based confirmation.

## Low risk

Execute immediately:

- Open application
- Open URL
- Switch window
- Type text
- Press ordinary keyboard shortcuts

## Medium risk

Confirmation may be required depending on context:

- Move files
- Rename files
- Close applications
- Browser actions that could submit something

## High risk

Always confirm:

- Delete files
- Shutdown
- Restart
- Other potentially irreversible operations

Confirmation must describe the specific intended action.

Example:

> Delete `report.docx`?

Buttons:

- Confirm
- Cancel

The user must be able to cancel before execution.

---

# 20. AI / LLM Strategy

The system uses a **fully local architecture**.

### Required AI

Local STT.

### Command interpretation

Local parser/rules.

### Cloud AI

Not required.

The MVP does **not** depend on:

- OpenAI API
- Gemini API
- Claude API
- Other cloud LLM APIs
- API keys
- Paid AI credits

Complex commands that cannot be safely interpreted through the local command system can simply be reported as unsupported.

The architecture should nevertheless isolate command interpretation behind an interface so a local or external AI provider could potentially be added in a future version.

---

# 21. Microphone

Default:

**Windows system microphone**

Settings should allow the user to select a specific microphone.

The selected microphone is remembered.

If the selected device disappears:

1. Fall back to the Windows default microphone.
2. Notify the user.

---

# 22. Hotkeys

## Dictation

Default:

**Right Ctrl**

Configurable.

Supports:

- Push-to-talk
- Toggle

## Control

Default:

**Right Alt**

Configurable.

Supports:

- Push-to-talk
- Toggle

The implementation must reliably distinguish a tap from a held key.

---

# 23. Privacy & History

The application stores:

- Dictation transcripts
- Control Mode commands

History is stored **locally**.

No microphone audio is stored by default.

History should have configurable retention/cleanup settings.

The user must be able to:

- View history
- Delete individual history entries where practical
- Clear all history

Diagnostic logs are separate from user history.

---

# 24. Startup & System Tray

The application supports:

**Run at Windows startup**

but this is optional.

The user can enable/disable it in Settings.

When running, the application provides a Windows system-tray icon.

Tray menu should provide:

- Current status
- Settings
- History
- Enable/disable functionality where appropriate
- Exit

Manual launching must also work.

---

# 25. Settings

Minimum settings:

### Dictation

- Dictation hotkey
- Push-to-talk/toggle behavior
- STT model
- Language
- Formatting behavior
- Clipboard restoration behavior

### Control

- Control hotkey
- Push-to-talk/toggle behavior
- Confirmation preferences where safely configurable

### Microphone

- Selected microphone

### History

- Retention
- Clear history

### Startup

- Run at Windows startup

### Appearance

- Overlay position
- Overlay visibility/options

---

# 26. Error Handling

The application must fail visibly and safely.

Examples:

### Microphone unavailable

Show:

> Microphone unavailable.

Do not attempt to process empty audio.

### STT failure

Show:

> Speech recognition failed.

Do not insert garbage/empty text.

### Text insertion failure

Copy transcription to clipboard and notify the user.

### Unsupported Control command

Show:

> Command not supported.

Do not guess or perform an unrelated action.

### Risky action cannot be confidently understood

Do not execute.

Ask for clarification or cancel the action.

---

# 27. Suggested Technical Stack

## Language

**Python**

## Desktop UI

**PySide6**

Used for:

- Settings
- Overlay
- System tray
- History
- Confirmation dialogs

## Speech recognition

**faster-whisper**

or an equivalent local Whisper implementation.

## Global hotkeys

Potential implementation:

- `pynput`
- Windows keyboard APIs where greater reliability is required

## Keyboard/mouse control

- `pynput`
- Windows APIs where appropriate

## Clipboard

- `pyperclip`
- Windows clipboard APIs where richer clipboard preservation is required

## Process/application control

- Python `subprocess`
- Windows APIs

## Persistence

A lightweight local database such as:

**SQLite**

Suitable for:

- History
- Settings metadata where necessary
- Application state

Configuration can also use a simple structured configuration format.

---

# 28. Proposed Architecture

```text
voice_agent/
│
├── app/
│   ├── main.py
│   ├── lifecycle.py
│   └── config.py
│
├── audio/
│   ├── microphone.py
│   └── recorder.py
│
├── stt/
│   ├── engine.py
│   ├── whisper_engine.py
│   └── models.py
│
├── dictation/
│   ├── processor.py
│   ├── normalizer.py
│   ├── formatter.py
│   └── inserter.py
│
├── control/
│   ├── parser.py
│   ├── command_router.py
│   ├── action_validator.py
│   ├── risk.py
│   └── actions/
│       ├── applications.py
│       ├── keyboard.py
│       ├── mouse.py
│       ├── browser.py
│       ├── clipboard.py
│       └── files.py
│
├── input/
│   └── hotkeys.py
│
├── clipboard/
│   └── manager.py
│
├── ui/
│   ├── overlay.py
│   ├── tray.py
│   ├── settings.py
│   ├── history.py
│   └── confirmation.py
│
├── storage/
│   ├── database.py
│   ├── history.py
│   └── settings.py
│
└── tests/
```

The exact module layout can change during implementation as long as the architectural boundaries remain clear.

---

# 29. Core State Machines

## Dictation

```text
READY
  ↓
LISTENING
  ↓
PROCESSING
  ↓
TYPING
  ↓
READY
```

Failure states should return safely to `READY`.

## Control

```text
READY
  ↓
LISTENING
  ↓
PROCESSING
  ↓
VALIDATING
  ↓
CONFIRMING (when required)
  ↓
EXECUTING
  ↓
RESULT
  ↓
READY
```

---

# 30. MVP Requirements

The first usable release must include:

- Windows desktop application
- System tray
- Configurable Dictation hotkey
- Configurable Control hotkey
- Push-to-talk
- Toggle activation
- Local microphone capture
- Local Whisper-based STT
- English language support
- Dictation normalization
- Dictation formatting commands
- Immediate text insertion
- Clipboard preservation/restoration
- Clipboard fallback
- Dictation overlay
- Local Control Mode
- Application control
- Keyboard control
- Mouse control
- Basic browser/URL control
- File/folder operations
- Explicit Action API
- Risk-based confirmation
- Local command/history storage
- History management
- Settings
- Optional Windows startup
- No cloud AI requirement

---

# 31. Explicit MVP Non-Goals

The MVP does **not** include:

- Cloud-only AI
- Mandatory API keys
- Paid AI services
- Automatic silence detection
- Fully autonomous computer operation
- Unrestricted screen-reading agents
- Unrestricted LLM computer control
- Cross-platform support
- Mobile applications
- Web application
- Automatic language detection
- Automatic execution of ambiguous commands
- Permanent microphone recordings

---

# 32. Performance Goals

The system should prioritize a fast interaction loop.

Target experience:

```text
Press hotkey
      ↓
Speak
      ↓
Release/stop
      ↓
STT
      ↓
Text appears
```

The UI should visibly communicate processing so the user never has to wonder whether the application is still listening.

STT model selection should allow users with weaker hardware to prioritize speed and users with stronger hardware to prioritize accuracy.

---

# 33. Security Boundaries

The most important architectural security boundary is:

```text
Speech
  ↓
STT
  ↓
Command Parser
  ↓
Structured Action
  ↓
Validation
  ↓
Risk Check
  ↓
Execution
```

No component should be able to translate arbitrary speech directly into unrestricted OS operations.

High-risk operations require explicit confirmation.

Ambiguous commands should not be guessed.

---

# 34. Acceptance Criteria

## Dictation

- Holding Right Ctrl records speech.
- Releasing Right Ctrl stops recording.
- Tapping Right Ctrl twice also starts/stops dictation.
- Speech is processed locally.
- Text is inserted into the active application.
- Dictation never executes computer commands.
- Punctuation/capitalization work.
- Formatting commands work.
- Existing clipboard content is restored by default.
- Failed insertion results in clipboard fallback.
- No dictated text is silently discarded.

## Control

- Right Alt activates Control Mode.
- Control Mode is visually distinguishable.
- Basic computer actions execute through the Action API.
- Unsupported commands do not trigger guessed actions.
- Risky operations trigger confirmation.
- High-risk operations cannot execute without confirmation.

## Privacy

- Audio is not permanently stored by default.
- History is stored locally.
- History can be cleared.
- No cloud service is required for core functionality.

## Windows

- Application runs as a Windows desktop application.
- System tray is available.
- Windows startup is optional.
- Settings persist between launches.

---

# 35. Development Priority

Implementation should proceed roughly in this order:

### Phase 1 — Foundation

- Python project
- Windows application lifecycle
- PySide6
- System tray
- Configuration
- Logging

### Phase 2 — Dictation MVP

- Microphone
- Local Whisper
- Right Ctrl hotkey
- Push-to-talk
- Toggle
- Overlay
- Text normalization
- Clipboard insertion
- Clipboard restoration
- Fallback behavior

### Phase 3 — Dictation refinement

- Formatting commands
- Language settings
- Model selection
- History
- Settings UI

### Phase 4 — Control Mode

- Right Alt
- Command parser
- Action API
- Application control
- Keyboard control
- Mouse control
- Browser/URL operations
- File operations

### Phase 5 — Safety

- Risk classification
- Confirmation UI
- Action validation
- Ambiguity handling

### Phase 6 — Packaging

- Windows executable
- Installer
- Startup option
- Final settings
- Error handling
- End-to-end testing

---

# 36. Final Product Definition

The finished application is a **Windows-local voice agent with two deliberately separated modes**:

### Dictation Mode

> Speak → text appears.

Fast, literal, local, and predictable.

### Control Mode

> Speak → command is interpreted → validated action occurs.

Controlled, structured, and confirmation-aware.

The core product does not depend on paid AI infrastructure.

The guiding architecture is:

**Local STT + local command system + explicit Action API + risk-based execution + optional future extensibility.**

---

# 37. Recommended Technology Stack

This section recommends the concrete stack for implementation based on the requirements above.

## 37.1 Core Language — Python 3.12+

**Recommendation: Python 3.12 or newer stable Python 3.x supported by the chosen dependencies.**

Python is a strong fit because the project needs:

- Local ML/STT integration
- Windows automation
- Global keyboard hooks
- Audio capture
- Clipboard access
- Desktop UI
- SQLite
- Fast iteration

Python also keeps the implementation approachable while providing mature libraries for nearly every required subsystem.

---

## 37.2 Desktop UI — PySide6

**Recommendation: PySide6**

Use PySide6 for:

- Floating voice overlay
- System-tray application
- Settings window
- History window
- Confirmation dialogs
- Application status
- Notifications

Why:

- Mature Qt desktop framework
- Good Windows support
- Suitable for tray/background applications
- Strong separation between UI and application logic
- Better long-term structure than building the UI around a webview

The UI should remain thin: business logic, STT, command parsing, and action execution should live outside the UI layer.

---

## 37.3 Speech Recognition — faster-whisper

**Recommendation: faster-whisper**

Use it as the primary local STT engine.

Benefits:

- Local/offline processing
- Whisper model compatibility
- Good performance
- Supports multiple languages
- Can use CPU or GPU depending on hardware
- No API key

The STT layer should be hidden behind an internal interface such as:

```python
class SpeechToTextEngine:
    def transcribe(self, audio, language=None) -> str:
        ...
```

This makes the STT implementation replaceable later.

---

## 37.4 Audio Capture — sounddevice

**Recommendation: sounddevice**

Use `sounddevice` for microphone capture.

It provides a relatively straightforward Python interface for recording audio and works well with a local STT pipeline.

The audio subsystem should expose a clean abstraction:

```text
Microphone
    ↓
Audio Recorder
    ↓
Audio Buffer
    ↓
STT Engine
```

Avoid coupling the recorder directly to Whisper.

---

## 37.5 Global Hotkeys — Windows API + pynput

**Recommendation: use a small abstraction with `pynput` initially, while keeping the hotkey implementation replaceable.**

The project needs reliable global detection of:

- Right Ctrl
- Right Alt
- Configurable alternatives

For a first implementation, `pynput` is reasonable.

If reliability problems appear around Windows-specific keyboard behavior, replace the implementation with the appropriate Windows keyboard APIs without changing the rest of the application.

The application should expose:

```text
HotkeyManager
    ├── register()
    ├── unregister()
    └── callbacks
```

---

## 37.6 Keyboard and Mouse Automation — pynput + Windows APIs

**Recommendation: `pynput` for basic input automation, with Windows APIs for operations requiring greater control.**

Use this for:

- Key presses
- Keyboard shortcuts
- Mouse movement
- Mouse clicks

Keep these operations behind the Action API rather than calling `pynput` directly from the command parser.

---

## 37.7 Clipboard — Windows Clipboard API

**Recommendation: use the Windows clipboard APIs for robust clipboard preservation, with `pyperclip` only where appropriate.**

Because this application specifically requires restoring the user's previous clipboard, clipboard handling is more important than in a typical desktop application.

The clipboard manager should be responsible for:

```text
capture()
save()
set_text()
paste()
restore()
```

It should preserve supported clipboard formats where practical rather than assuming the clipboard contains plain text.

---

## 37.8 Windows Process and Application Control — subprocess + pywin32

**Recommendation: `subprocess` plus `pywin32`.**

Use:

- `subprocess` for launching known applications/processes.
- `pywin32` for Windows-specific window/process operations.

Potential responsibilities include:

- Launch application
- Find windows
- Switch windows
- Close windows
- Inspect basic window state

Keep Windows-specific functionality behind an OS abstraction.

---

## 37.9 File Operations — pathlib + shutil

**Recommendation: Python standard library.**

Use:

- `pathlib`
- `shutil`
- `os`

for:

- Opening files
- Moving files
- Renaming files
- Deleting files
- Folder operations

Do not allow the command parser to directly execute arbitrary filesystem commands.

All operations should flow through validated Action API methods.

---

## 37.10 Browser / URL Operations — webbrowser

**Recommendation: Python `webbrowser` for opening URLs, with Windows/browser automation added only where required.**

For MVP:

- Open URL
- Open search URL
- Basic browser launching/navigation where reliably achievable

Avoid building a full browser automation system into the initial version.

---

## 37.11 Persistence — SQLite

**Recommendation: SQLite**

SQLite is sufficient for:

- Dictation history
- Control command history
- Retention metadata
- Application metadata where useful

Use Python's built-in `sqlite3` module initially.

An ORM is not necessary for this project unless the data model becomes substantially more complex.

Suggested tables:

```text
history
settings
```

Potential future tables can be added without changing the overall architecture.

---

## 37.12 Configuration — TOML

**Recommendation: TOML configuration for user-facing/local configuration where appropriate.**

Python's TOML support makes this a simple choice for readable configuration.

Use the database for structured historical records and TOML/config files for application preferences where practical.

Do not duplicate settings across multiple persistence systems without a reason.

---

## 37.13 Logging — Python logging

**Recommendation: standard-library `logging`.**

Use structured application logs for:

- Startup/shutdown
- Microphone errors
- STT errors
- Hotkey registration errors
- Action execution errors
- Unexpected exceptions

Do not put full microphone recordings into logs.

Avoid logging sensitive dictated text by default.

Diagnostic logging should remain separate from user-visible history.

---

## 37.14 Packaging — PyInstaller

**Recommendation: PyInstaller**

Use PyInstaller to create the Windows executable.

The final distribution should provide an installer or packaged application that does not require the user to manually install Python.

The build process should eventually produce:

```text
PC Voice Agent
    ├── Application executable
    ├── Required Python dependencies
    ├── Configuration
    └── Local STT model management
```

STT model files should be handled separately from the main executable where practical because of their size.

---

## 37.15 Installer — Inno Setup

**Recommendation: Inno Setup**

Use Inno Setup for the Windows installer.

The installer should eventually handle:

- Application installation
- Start Menu shortcut
- Optional desktop shortcut
- Optional Windows startup configuration
- Uninstallation
- Application data directories

The installer should not force Windows startup on the user.

---

## 37.16 Testing — pytest

**Recommendation: pytest**

Use pytest for:

- Text normalization tests
- Formatting tests
- Command parser tests
- Risk classification tests
- Action validation tests
- Clipboard manager tests where practical
- Configuration tests
- State-machine tests

The most important logic should be testable without launching the entire desktop UI.

---

## 37.17 Type Checking — mypy

**Recommendation: mypy**

Use type hints throughout the application.

Mypy should gradually enforce type correctness around:

- Action objects
- Parser results
- STT interfaces
- Configuration
- Storage
- State transitions

This is particularly valuable because the project has several boundaries between asynchronous/interactive components.

---

## 37.18 Code Quality — Ruff

**Recommendation: Ruff**

Use Ruff for:

- Linting
- Import organization
- Basic code-quality checks
- Fast development feedback

A simple development toolchain can therefore be:

```text
pytest
mypy
ruff
```

---

## 37.19 Recommended Final Stack

| Area | Recommended Technology |
|---|---|
| Language | Python 3.12+ |
| Desktop UI | PySide6 |
| STT | faster-whisper |
| Audio | sounddevice |
| Global hotkeys | pynput initially, Windows API if needed |
| Keyboard/mouse | pynput + Windows APIs |
| Clipboard | Windows Clipboard API |
| Windows integration | pywin32 |
| Files | pathlib + shutil |
| URLs | webbrowser |
| Database | SQLite |
| Configuration | TOML |
| Logging | Python logging |
| Packaging | PyInstaller |
| Installer | Inno Setup |
| Testing | pytest |
| Type checking | mypy |
| Linting | Ruff |

---

## 37.20 Architecture Recommendation

The most important stack decision is not an individual library but the separation of responsibilities.

Recommended architecture:

```text
                    ┌─────────────────────┐
                    │      PySide6 UI     │
                    │ Overlay / Tray / UI │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Application Core  │
                    │ State / Routing /    │
                    │ Configuration        │
                    └───────┬───────┬──────┘
                            │       │
                 ┌──────────▼──┐ ┌──▼────────────┐
                 │  Dictation  │ │   Control     │
                 │   Engine    │ │    Engine     │
                 └──────┬──────┘ └──────┬────────┘
                        │                │
                 ┌──────▼──────┐  ┌─────▼─────────┐
                 │ faster-     │  │ Command       │
                 │ whisper     │  │ Parser        │
                 └─────────────┘  └─────┬─────────┘
                                        │
                                 ┌──────▼─────────┐
                                 │ Action API     │
                                 │ + Validation   │
                                 │ + Risk Engine  │
                                 └──────┬─────────┘
                                        │
                              ┌─────────▼─────────┐
                              │ Windows Actions   │
                              │ Keyboard / Mouse  │
                              │ Apps / Files etc. │
                              └───────────────────┘

             ┌────────────────────────────────────┐
             │ SQLite / Config / Logging / Audio │
             └────────────────────────────────────┘
```

### Overall recommendation

Use a **Python + PySide6 + faster-whisper + sounddevice + pynput + pywin32 + SQLite** stack, packaged with **PyInstaller and Inno Setup**.

This stack fits the project's Windows-only, local-first requirements without introducing unnecessary web infrastructure, cloud AI dependencies, or paid services.
