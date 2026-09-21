"""Dictation formatting command parser for spoken punctuation and paragraph breaks."""

from __future__ import annotations

import re


class DictationFormatter:
    """Parses spoken formatting keywords into actual punctuation and whitespace."""

    # Map spoken commands (ordered from longest/multi-word to shortest) to replacement tokens
    FORMAT_RULES: list[tuple[str, str]] = [
        ("new paragraph", "\n\n"),
        ("new line", "\n"),
        ("exclamation point", "!"),
        ("exclamation mark", "!"),
        ("question mark", "?"),
        ("full stop", "."),
        ("period", "."),
        ("open quote", '"'),
        ("open quotes", '"'),
        ("close quote", '"'),
        ("close quotes", '"'),
        ("semicolon", ";"),
        ("colon", ":"),
        ("comma", ","),
        ("hyphen", "-"),
        ("dash", " - "),
    ]

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def format(self, text: str) -> str:
        """Parse spoken formatting keywords into symbols and structure.

        If disabled, returns original text unmodified.
        """
        if not self.enabled or not text:
            return text

        result = text

        # Replace spoken keywords with word boundary matching
        for spoken, symbol in self.FORMAT_RULES:
            pattern = rf"\b{re.escape(spoken)}\b"
            result = re.sub(pattern, symbol, result, flags=re.IGNORECASE)

        # Affix punctuation to preceding word: e.g. "word ." -> "word."
        result = re.sub(r"\s+([,.\!?;\:])", r"\1", result)

        # Handle newlines: remove space before \n, and trim extra space right after \n
        result = re.sub(r"[ \t]*\n[ \t]*", "\n", result)

        # Handle quotes spacing: e.g. ' " word ' -> ' "word'
        result = re.sub(r'"\s+([^"\n]+?)\s+"', r'"\1"', result)

        # Handle hyphen spacing: e.g. "twenty - five" -> "twenty-five"
        result = re.sub(r"(\w)\s*-\s*(\w)", r"\1-\2", result)

        return result
