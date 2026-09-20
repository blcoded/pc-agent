# QA Engineer Role & Responsibilities

- Writes automated test suites for every unit and integration component under `tests/`.
- Tests both nominal and edge cases (e.g. repetition preservation in dictation, path traversal in control mode).
- Mocks hardware and OS dependencies (audio streams, Windows clipboard, keystrokes).
- Ensures code quality standards: `pytest` passes with high coverage, `ruff` reports zero lints, and `mypy` passes type checks.
- Validates failure resilience: ensures no silent text loss during dictation failures.
