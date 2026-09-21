"""Text normalization and linguistic cleaning for spoken dictation.

Ensures proper capitalization, punctuation spacing, stutter/glitch removal,
and whitespace cleanup without modifying semantic meaning or using LLMs.
"""

from __future__ import annotations

import re


class TextNormalizer:
    """Deterministic, rule-based text normalizer for dictation transcripts."""

    def __init__(
        self,
        capitalize_sentences: bool = True,
        clean_stutters: bool = True,
        fix_punctuation: bool = True,
    ) -> None:
        self.capitalize_sentences = capitalize_sentences
        self.clean_stutters = clean_stutters
        self.fix_punctuation = fix_punctuation

    def normalize(self, text: str) -> str:
        """Apply the full normalization pipeline to transcribed text."""
        if not text or not text.strip():
            return ""

        result = text.strip()

        if self.clean_stutters:
            result = self.remove_stutters(result)

        if self.fix_punctuation:
            result = self.normalize_punctuation_spacing(result)

        if self.capitalize_sentences:
            result = self.capitalize(result)

        result = self.clean_whitespace(result)

        return result

    @staticmethod
    def clean_whitespace(text: str) -> str:
        """Collapse redundant horizontal spaces while preserving line breaks."""
        # Replace multiple horizontal spaces/tabs with a single space
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        # Rejoin preserving newlines, but collapsing >2 consecutive newlines into 2
        joined = "\n".join(lines)
        return re.sub(r"\n{3,}", "\n\n", joined).strip()

    @staticmethod
    def remove_stutters(text: str) -> str:
        """Eliminate immediate consecutive word and short phrase repetitions."""
        lines = text.split("\n")
        cleaned_lines: list[str] = []

        valid_doubles = {"had", "that"}

        for line in lines:
            line_result = line
            # 1. Multi-word phrase stutters: 2 to 3 words repeated
            for _ in range(2):
                line_result = re.sub(
                    r"\b([A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){1,2})\s+\1\b",
                    r"\1",
                    line_result,
                    flags=re.IGNORECASE,
                )

            # 2. Single word stutters within line
            tokens = line_result.split()
            cleaned_tokens: list[str] = []
            for token in tokens:
                lower_token = re.sub(r"^\W+|\W+$", "", token).lower()
                if cleaned_tokens:
                    prev_lower = re.sub(r"^\W+|\W+$", "", cleaned_tokens[-1]).lower()
                    if lower_token and lower_token == prev_lower and lower_token not in valid_doubles:
                        continue
                cleaned_tokens.append(token)
            cleaned_lines.append(" ".join(cleaned_tokens))

        return "\n".join(cleaned_lines)

    @staticmethod
    def normalize_punctuation_spacing(text: str) -> str:
        """Standardize spaces around punctuation marks."""
        # 1. Remove space before punctuation marks: , . ! ? ; : ) ] } %
        result = re.sub(r"\s+([,.\!?;\:\)\]}%])", r"\1", text)

        # 2. Remove space after opening brackets: ( [ {
        result = re.sub(r"([\(\[\{])\s+", r"\1", result)

        # 3. Add space after commas, semicolons, and colons if followed directly by a letter
        result = re.sub(r"([,;])([A-Za-z])", r"\1 \2", result)
        # For colons, ensure not a time (e.g. 12:30) or URL (e.g. http://)
        result = re.sub(r"(?<=[A-Za-z]):([A-Za-z])", r": \1", result)

        # 4. Add space after sentence terminators (. ! ?) if followed directly by a letter
        result = re.sub(r"([\.\!\?])([A-Za-z])", r"\1 \2", result)

        # 5. Fix quotes spacing: e.g. " hello " -> "hello"
        result = re.sub(r'"\s+([^"]*?)\s+"', r'"\1"', result)

        return result

    @staticmethod
    def capitalize(text: str) -> str:
        """Capitalize sentence starts, standalone 'I' and contractions."""
        if not text:
            return ""

        # 1. Capitalize standalone 'I' and contractions: i'm, i'll, i've, i'd
        result = re.sub(r"\bi\b", "I", text)
        result = re.sub(r"\bi'(m|ll|ve|d)\b", r"I'\1", result, flags=re.IGNORECASE)

        # 2. Capitalize first character of string
        result = result[0].upper() + result[1:] if len(result) > 1 else result.upper()

        # 3. Capitalize first character after sentence ending (. ! ?) followed by space or newline
        def _cap_match(m: re.Match) -> str:
            return m.group(1) + m.group(2).upper()

        result = re.sub(r"([\.\!\?]\s+)([a-z])", _cap_match, result)

        # 4. Capitalize after newlines
        result = re.sub(r"(\n\s*)([a-z])", _cap_match, result)

        return result
