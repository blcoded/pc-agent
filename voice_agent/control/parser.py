"""Local Rule-Based Command Parser for PC Voice Agent Control Core.

Parses natural speech commands into structured ActionRequest objects using
fast, deterministic regular expressions and pattern matching.
Zero cloud LLM dependency.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from voice_agent.control.models import (
    ActionRequest,
    ActionType,
    RiskLevel,
)

logger = logging.getLogger(__name__)


@dataclass
class UnsupportedCommandResult:
    """Represents a command that could not be mapped to any supported action."""

    raw_command: str
    reason: str = "Unrecognized or unsupported voice command"

    def to_dict(self) -> dict[str, Any]:
        """Convert UnsupportedCommandResult to a dictionary."""
        return {
            "raw_command": self.raw_command,
            "reason": self.reason,
            "unsupported": True,
        }


class CommandParser:
    """Rule-based local parser converting natural language commands into ActionRequests."""

    # Keywords that indicate the start of a new chained command
    CHAIN_VERBS = {
        "open",
        "launch",
        "start",
        "close",
        "quit",
        "exit",
        "switch",
        "focus",
        "press",
        "hit",
        "type",
        "write",
        "shortcut",
        "hotkey",
        "click",
        "double",
        "right",
        "middle",
        "move",
        "search",
        "google",
        "browse",
        "go",
        "copy",
        "paste",
        "read",
        "delete",
        "remove",
        "rename",
    }

    # URL detection pattern
    URL_PATTERN = re.compile(
        r"^(?:https?://)?(?:www\.)?[a-zA-Z0-9-]+(?:\.[a-zA-Z]{2,})+(?:/\S*)?$",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        """Initialize parser rules."""

    def split_chained_commands(self, text: str) -> list[str]:
        """Split a multi-step command on 'and then', 'then', or 'and'.

        - 'then' and 'and then' are always command separators.
        - 'and' is a separator unless the preceding clause is a free-text input
          (like 'type' or 'search') and the token after 'and' is not a recognized command verb.

        Args:
            text: Raw input text.

        Returns:
            List of individual command strings.
        """
        raw_text = text.strip()
        if not raw_text:
            return []

        # Split preserving delimiter indicators
        # First split on 'and then' or 'then'
        then_parts = re.split(r"\s+(?:and\s+then|then)\s+", raw_text, flags=re.IGNORECASE)
        clauses: list[str] = []

        for part in then_parts:
            and_tokens = re.split(r"\s+and\s+", part, flags=re.IGNORECASE)
            if len(and_tokens) <= 1:
                if part.strip():
                    clauses.append(part.strip())
                continue

            current = and_tokens[0].strip()
            for next_tok in and_tokens[1:]:
                next_clean = next_tok.strip()
                first_word = next_clean.split()[0].lower() if next_clean else ""
                current_lower = current.lower()

                # If current starts with free-text command ('search', 'google', 'type', 'write')
                is_free_text = any(
                    current_lower.startswith(prefix)
                    for prefix in ("search", "google", "type", "write")
                )

                if is_free_text and first_word not in self.CHAIN_VERBS:
                    # Keep as part of the query / typed text
                    current = f"{current} and {next_clean}"
                else:
                    if current:
                        clauses.append(current)
                    current = next_clean

            if current:
                clauses.append(current)

        return clauses

    def parse_single_command(self, cmd_text: str) -> ActionRequest | UnsupportedCommandResult:
        """Parse an individual command clause into an ActionRequest or UnsupportedCommandResult.

        Args:
            cmd_text: A single command clause string.

        Returns:
            ActionRequest if recognized, or UnsupportedCommandResult if unsupported.
        """
        clean_text = cmd_text.strip()
        if not clean_text:
            return UnsupportedCommandResult(raw_command="", reason="Empty command")

        text_lower = clean_text.lower()

        # 1. Clipboard operations
        if text_lower in ("copy", "copy this", "copy that", "copy selection"):
            return ActionRequest(
                action_type=ActionType.COPY,
                params={},
                risk_level=RiskLevel.LOW,
                raw_command=clean_text,
            )

        if text_lower in ("paste", "paste this", "paste that", "paste clipboard"):
            return ActionRequest(
                action_type=ActionType.PASTE,
                params={},
                risk_level=RiskLevel.LOW,
                raw_command=clean_text,
            )

        if text_lower in ("read clipboard", "get clipboard", "show clipboard"):
            return ActionRequest(
                action_type=ActionType.READ_CLIPBOARD,
                params={},
                risk_level=RiskLevel.LOW,
                raw_command=clean_text,
            )

        # 2. Mouse operations
        if text_lower in ("double click", "double-click"):
            return ActionRequest(
                action_type=ActionType.CLICK,
                params={"button": "left", "click_count": 2},
                risk_level=RiskLevel.LOW,
                raw_command=clean_text,
            )

        if text_lower in ("right click", "right-click"):
            return ActionRequest(
                action_type=ActionType.CLICK,
                params={"button": "right", "click_count": 1},
                risk_level=RiskLevel.LOW,
                raw_command=clean_text,
            )

        if text_lower in ("middle click", "middle-click"):
            return ActionRequest(
                action_type=ActionType.CLICK,
                params={"button": "middle", "click_count": 1},
                risk_level=RiskLevel.LOW,
                raw_command=clean_text,
            )

        if text_lower in ("click", "left click", "single click"):
            return ActionRequest(
                action_type=ActionType.CLICK,
                params={"button": "left", "click_count": 1},
                risk_level=RiskLevel.LOW,
                raw_command=clean_text,
            )

        # Move mouse absolute: "move mouse to 500 400" or "move mouse to 500, 400"
        m_mouse_abs = re.match(r"^move\s+mouse\s+to\s+(\d+)(?:\s*,\s*|\s+)(\d+)$", text_lower)
        if m_mouse_abs:
            x, y = int(m_mouse_abs.group(1)), int(m_mouse_abs.group(2))
            return ActionRequest(
                action_type=ActionType.MOVE_MOUSE,
                params={"x": x, "y": y, "mode": "absolute"},
                risk_level=RiskLevel.LOW,
                raw_command=clean_text,
            )

        # Move mouse relative: "move mouse left 50" or "move mouse up"
        m_mouse_rel = re.match(r"^move\s+mouse\s+(up|down|left|right)(?:\s+by)?(?:\s+(\d+))?(?:\s*(?:pixels|px))?$", text_lower)
        if m_mouse_rel:
            direction = m_mouse_rel.group(1)
            dist_str = m_mouse_rel.group(2)
            distance = int(dist_str) if dist_str else 50
            return ActionRequest(
                action_type=ActionType.MOVE_MOUSE,
                params={"direction": direction, "distance": distance, "mode": "relative"},
                risk_level=RiskLevel.LOW,
                raw_command=clean_text,
            )

        # 3. Web search
        m_search = re.match(r"^(?:search\s+for|search|google)\s+(.+)$", clean_text, re.IGNORECASE)
        if m_search:
            query = m_search.group(1).strip()
            return ActionRequest(
                action_type=ActionType.SEARCH_WEB,
                params={"query": query},
                risk_level=RiskLevel.LOW,
                raw_command=clean_text,
            )

        # 4. Filesystem operations
        # Open file
        m_open_file = re.match(r"^open\s+(?:file|document)\s+(.+)$", clean_text, re.IGNORECASE)
        if m_open_file:
            path = m_open_file.group(1).strip().strip('"\'')
            return ActionRequest(
                action_type=ActionType.OPEN_FILE,
                params={"path": path},
                risk_level=RiskLevel.LOW,
                raw_command=clean_text,
            )

        # Open folder
        m_open_folder = re.match(r"^open\s+(?:folder|directory)\s+(.+)$", clean_text, re.IGNORECASE)
        if m_open_folder:
            path = m_open_folder.group(1).strip().strip('"\'')
            return ActionRequest(
                action_type=ActionType.OPEN_FOLDER,
                params={"path": path},
                risk_level=RiskLevel.LOW,
                raw_command=clean_text,
            )

        # Delete file (High risk)
        m_del_file = re.match(r"^(?:delete|remove)\s+file\s+(.+)$", clean_text, re.IGNORECASE)
        if m_del_file:
            path = m_del_file.group(1).strip().strip('"\'')
            return ActionRequest(
                action_type=ActionType.DELETE_FILE,
                params={"path": path},
                risk_level=RiskLevel.HIGH,
                raw_command=clean_text,
            )

        # Rename file: "rename file a to b" or "rename a to b"
        m_ren_file = re.match(r"^rename\s+(?:file\s+)?(.+?)\s+to\s+(.+)$", clean_text, re.IGNORECASE)
        if m_ren_file:
            src = m_ren_file.group(1).strip().strip('"\'')
            dst = m_ren_file.group(2).strip().strip('"\'')
            return ActionRequest(
                action_type=ActionType.RENAME_FILE,
                params={"source": src, "destination": dst},
                risk_level=RiskLevel.MEDIUM,
                raw_command=clean_text,
            )

        # Move file: "move file a to b" or "move a to b"
        m_mv_file = re.match(r"^move\s+(?:file\s+)?(.+?)\s+to\s+(.+)$", clean_text, re.IGNORECASE)
        if m_mv_file and not text_lower.startswith("move mouse"):
            src = m_mv_file.group(1).strip().strip('"\'')
            dst = m_mv_file.group(2).strip().strip('"\'')
            return ActionRequest(
                action_type=ActionType.MOVE_FILE,
                params={"source": src, "destination": dst},
                risk_level=RiskLevel.MEDIUM,
                raw_command=clean_text,
            )

        # 5. URLs / Web browsing
        # "open github.com" or "browse to https://google.com" or "go to reddit.com"
        m_url = re.match(r"^(?:open|browse\s+to|go\s+to)\s+(.+)$", clean_text, re.IGNORECASE)
        if m_url:
            candidate_url = m_url.group(1).strip()
            # Check if candidate_url resembles a web URL or domain
            if (
                candidate_url.startswith(("http://", "https://"))
                or self.URL_PATTERN.match(candidate_url)
                or any(candidate_url.lower().endswith(tld) for tld in (".com", ".org", ".net", ".io", ".dev", ".gov", ".edu", ".ai"))
            ):
                # Ensure scheme
                full_url = candidate_url if candidate_url.startswith(("http://", "https://")) else f"https://{candidate_url}"
                return ActionRequest(
                    action_type=ActionType.OPEN_URL,
                    params={"url": full_url},
                    risk_level=RiskLevel.LOW,
                    raw_command=clean_text,
                )

        # 6. Keyboard & Typing
        # "press enter", "press backspace", "hit escape"
        m_press = re.match(r"^(?:press\s+key|press|hit)\s+(.+)$", clean_text, re.IGNORECASE)
        if m_press:
            key_name = m_press.group(1).strip().lower()
            return ActionRequest(
                action_type=ActionType.PRESS_KEY,
                params={"key": key_name},
                risk_level=RiskLevel.LOW,
                raw_command=clean_text,
            )

        # "shortcut ctrl c", "hotkey alt f4", "press shortcut win r"
        m_hotkey = re.match(r"^(?:press\s+shortcut|shortcut|hotkey)\s+(.+)$", clean_text, re.IGNORECASE)
        if m_hotkey:
            hotkey_str = m_hotkey.group(1).strip()
            # Normalize split into keys
            keys = [k.strip().lower() for k in re.split(r"[\s\+]+", hotkey_str) if k.strip()]
            return ActionRequest(
                action_type=ActionType.HOTKEY,
                params={"hotkey": hotkey_str, "keys": keys},
                risk_level=RiskLevel.LOW,
                raw_command=clean_text,
            )

        # "type Hello world", "write text here"
        m_type = re.match(r"^(?:type\s+text|type|write)\s+(.+)$", clean_text, re.IGNORECASE)
        if m_type:
            typed_content = m_type.group(1)
            # Unquote if enclosed in quotes
            if (typed_content.startswith('"') and typed_content.endswith('"')) or (
                typed_content.startswith("'") and typed_content.endswith("'")
            ):
                typed_content = typed_content[1:-1]
            return ActionRequest(
                action_type=ActionType.TYPE_TEXT,
                params={"text": typed_content},
                risk_level=RiskLevel.LOW,
                raw_command=clean_text,
            )

        # 7. Application control
        # Switch window: "switch to slack", "switch window to chrome", "focus discord"
        m_switch = re.match(r"^(?:switch\s+(?:window\s+)?to|focus)\s+(.+)$", clean_text, re.IGNORECASE)
        if m_switch:
            win_name = m_switch.group(1).strip()
            return ActionRequest(
                action_type=ActionType.SWITCH_WINDOW,
                params={"window_name": win_name},
                risk_level=RiskLevel.LOW,
                raw_command=clean_text,
            )

        # Close window / app: "close window", "close current window", "quit notepad"
        if text_lower in ("close window", "close current window", "close active window"):
            return ActionRequest(
                action_type=ActionType.CLOSE_APP,
                params={"target": "current_window"},
                risk_level=RiskLevel.MEDIUM,
                raw_command=clean_text,
            )

        m_close = re.match(r"^(?:close|quit|exit)\s+(?:app|application|program)?\s*(.+)$", clean_text, re.IGNORECASE)
        if m_close:
            target = m_close.group(1).strip()
            return ActionRequest(
                action_type=ActionType.CLOSE_APP,
                params={"target": target},
                risk_level=RiskLevel.MEDIUM,
                raw_command=clean_text,
            )

        # Open / launch app: "open notepad", "launch chrome", "start spotify"
        m_open = re.match(r"^(?:open|launch|start)\s+(?:app|application|program)?\s*(.+)$", clean_text, re.IGNORECASE)
        if m_open:
            app_name = m_open.group(1).strip()
            return ActionRequest(
                action_type=ActionType.OPEN_APP,
                params={"app_name": app_name},
                risk_level=RiskLevel.LOW,
                raw_command=clean_text,
            )

        # If nothing matched, return UnsupportedCommandResult (no guessing)
        return UnsupportedCommandResult(
            raw_command=clean_text,
            reason=f"No matching action rule for command '{clean_text}'",
        )

    def parse(self, text: str) -> list[ActionRequest | UnsupportedCommandResult]:
        """Parse natural language command text into a list of actions or unsupported results.

        Args:
            text: Speech-to-text transcript or typed command string.

        Returns:
            List of ActionRequest and/or UnsupportedCommandResult objects.
        """
        clauses = self.split_chained_commands(text)
        results: list[ActionRequest | UnsupportedCommandResult] = []
        for clause in clauses:
            res = self.parse_single_command(clause)
            results.append(res)
        return results

    def parse_actions(self, text: str) -> list[ActionRequest]:
        """Parse command text and return strictly valid ActionRequests.

        If any component is unsupported, returns empty list or raises depending on usage.

        Args:
            text: Command text.

        Returns:
            List of ActionRequest objects if all are valid; otherwise empty list.
        """
        results = self.parse(text)
        actions: list[ActionRequest] = []
        for item in results:
            if isinstance(item, UnsupportedCommandResult):
                logger.warning("Command segment unsupported: %s (reason: %s)", item.raw_command, item.reason)
                return []
            actions.append(item)
        return actions

    def is_supported(self, text: str) -> bool:
        """Check whether the entire command can be parsed into valid actions.

        Args:
            text: Command string.

        Returns:
            bool: True if all chained clauses are supported actions.
        """
        results = self.parse(text)
        if not results:
            return False
        return all(isinstance(item, ActionRequest) for item in results)


__all__ = ["CommandParser", "UnsupportedCommandResult"]
