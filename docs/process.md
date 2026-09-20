# Engineering & Issue Resolution Process

This document outlines the standard engineering workflow for systematically addressing and closing project issues.

## Issue Resolution Lifecycle

For each issue (processed sequentially from #1 to #37):

1. **Issue Selection & Planning**
   - Identify the next open issue in sequential order.
   - Review the requirements, target files, acceptance criteria, and dependencies in `tasks.md` and `docs/spec.md`.

2. **Implementation (Software Engineer)**
   - Implement the necessary components, data models, interfaces, or logic in `voice_agent/`.
   - Adhere strictly to the project specification (offline-first, no cloud LLM, clean separation of concerns).
   - Maintain strict Python 3.12+ type hints.

3. **Verification & Quality Assurance (QA Engineer)**
   - Write comprehensive unit and/or integration tests under `tests/`.
   - Execute the test suite with `pytest`.
   - Run linter and type-checker to ensure zero defects:
     - `ruff check .`
     - `mypy voice_agent`

4. **Git Commit & Issue Closure**
   - Stage all relevant implementation and test files.
   - Commit with a clear, conventional message referencing the issue (e.g., `feat(core): TASK-1.1 Project Environment Setup (Closes #1)`).
   - Push commit to GitHub `main` branch.
   - Close the corresponding GitHub issue via the GitHub API with a resolution comment.
   - Update the task status in `tasks.md` and `docs/tasks.md` to `[x]`.

5. **Proceed to Next Task**
   - Advance to the subsequent task in the milestone sequence until all issues are completed.
