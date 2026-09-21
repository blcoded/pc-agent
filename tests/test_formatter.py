"""Unit tests for DictationFormatter spoken punctuation and formatting command parser."""

import unittest

from voice_agent.dictation.formatter import DictationFormatter
from voice_agent.dictation.normalizer import TextNormalizer


class TestDictationFormatter(unittest.TestCase):
    """Test suite for DictationFormatter spoken command conversion."""

    def setUp(self) -> None:
        self.formatter = DictationFormatter(enabled=True)
        self.normalizer = TextNormalizer()

    def test_basic_punctuation_commands(self) -> None:
        """Verify period, comma, question mark, and exclamation marks."""
        text = "Hello comma world period How are you question mark Great exclamation mark"
        formatted = self.formatter.format(text)
        self.assertEqual(formatted, "Hello, world. How are you? Great!")

    def test_alternative_punctuation_aliases(self) -> None:
        """Verify full stop and exclamation point aliases."""
        text = "End of sentence full stop Wow exclamation point"
        formatted = self.formatter.format(text)
        self.assertEqual(formatted, "End of sentence. Wow!")

    def test_colons_and_semicolons(self) -> None:
        """Verify colon and semicolon conversions."""
        text = "Note colon first item semicolon second item period"
        formatted = self.formatter.format(text)
        self.assertEqual(formatted, "Note: first item; second item.")

    def test_line_and_paragraph_breaks(self) -> None:
        """Verify new line and new paragraph conversions."""
        text = "Heading new line First line new paragraph Second paragraph"
        formatted = self.formatter.format(text)
        self.assertEqual(formatted, "Heading\nFirst line\n\nSecond paragraph")

    def test_quotes_and_hyphens(self) -> None:
        """Verify quotation marks and hyphens."""
        text = "She said open quote welcome close quote period Thirty hyphen five"
        formatted = self.formatter.format(text)
        self.assertEqual(formatted, 'She said "welcome". Thirty-five')

    def test_case_insensitivity(self) -> None:
        """Verify commands match regardless of capitalization."""
        text = "Item one COMMA item two PERIOD"
        formatted = self.formatter.format(text)
        self.assertEqual(formatted, "Item one, item two.")

    def test_disabled_formatting_leaves_text_literal(self) -> None:
        """Verify enabled=False preserves spoken words literally."""
        disabled_formatter = DictationFormatter(enabled=False)
        text = "Please add a comma and a period."
        self.assertEqual(disabled_formatter.format(text), text)

    def test_combined_pipeline_with_normalizer(self) -> None:
        """Verify formatter output feeds cleanly into normalizer."""
        raw_spoken = "hello comma how are you question mark new line i'm doing fine period"
        formatted = self.formatter.format(raw_spoken)
        normalized = self.normalizer.normalize(formatted)

        expected = "Hello, how are you?\nI'm doing fine."
        self.assertEqual(normalized, expected)


if __name__ == "__main__":
    unittest.main()
