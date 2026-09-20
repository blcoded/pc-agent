# Windows Local Voice Agent (`pc-agent`)

A Windows desktop voice agent designed primarily for **speech-to-text typing** with a secondary **computer-control mode**.

## Features

- **Dictation Mode**: Speech-to-text directly inserted into the active application. Zero cloud LLM, offline-first. Default hotkey: `Right Ctrl` (Push-to-talk hold and Toggle tap).
- **Control Mode**: Speech-to-command via structured Action API and risk-based confirmation. Default hotkey: `Right Alt`.
- **Privacy First**: All processing runs locally with `faster-whisper`. No microphone audio is stored permanently.

## Requirements

- Windows 10 or 11
- Python 3.11+
