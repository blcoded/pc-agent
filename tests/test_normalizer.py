"""Unit tests for TextNormalizer linguistic cleaning and formatting."""

import unittest

from voice_agent.dictation.normalizer import TextNormalizer


class TestTextNormalizer(unittest.TestCase):
    """Test suite for TextNormalizer capitalization, stutter cleanup, and punctuation."""

    def setUp(self) -> None:
        self.normalizer = TextNormalizer()

    def test_spec_example_repeated_phrase(self) -> None:
        """Verify the exact example from docs/spec.md is normalized."""
        raw = "I think I think the meeting is tomorrow."
        expected = "I think the meeting is tomorrow."
        self.assertEqual(self.normalizer.normalize(raw), expected)

    def test_single_word_stutters(self) -> None:
        """Verify duplicate consecutive words are removed while preserving valid doubles."""
        raw = "we we need to to go now"
        expected = "We need to go now"
        self.assertEqual(self.normalizer.normalize(raw), expected)

        # Valid English double word "had had" preserved
        valid_raw = "he said he had had enough"
        expected_valid = "He said he had had enough"
        self.assertEqual(self.normalizer.normalize(valid_raw), expected_valid)

    def test_capitalization(self) -> None:
        """Verify capitalization of sentence starts, 'I', and contractions."""
        raw = "hello there. how are you? i'm doing well, and i'll be ready."
        expected = "Hello there. How are you? I'm doing well, and I'll be ready."
        self.assertEqual(self.normalizer.normalize(raw), expected)

    def test_capitalization_across_newlines(self) -> None:
        """Verify line breaks start with a capital letter."""
        raw = "first item\nsecond item\nthird item"
        expected = "First item\nSecond item\nThird item"
        self.assertEqual(self.normalizer.normalize(raw), expected)

    def test_punctuation_spacing(self) -> None:
        """Verify spaces before punctuation are removed and spaces after are ensured."""
        raw = "wait , is this true ? yes , absolutely !"
        expected = "Wait, is this true? Yes, absolutely!"
        self.assertEqual(self.normalizer.normalize(raw), expected)

        # Punctuation missing space after
        raw_missing = "apples,oranges,and bananas.they are fresh."
        expected_missing = "Apples, oranges, and bananas. They are fresh."
        self.assertEqual(self.normalizer.normalize(raw_missing), expected_missing)

    def test_bracket_and_parenthesis_spacing(self) -> None:
        """Verify inner spaces around parentheses are stripped."""
        raw = "this is ( a special case ) for testing."
        expected = "This is (a special case) for testing."
        self.assertEqual(self.normalizer.normalize(raw), expected)

    def test_number_and_time_formatting_preserved(self) -> None:
        """Verify decimals and timestamps are not altered by punctuation rules."""
        raw = "the price is 3.14 and the meeting is at 10:30"
        expected = "The price is 3.14 and the meeting is at 10:30"
        self.assertEqual(self.normalizer.normalize(raw), expected)

    def test_whitespace_collapsing(self) -> None:
        """Verify redundant horizontal spaces are collapsed."""
        raw = "   lots   of    spaces    between words   "
        expected = "Lots of spaces between words"
        self.assertEqual(self.normalizer.normalize(raw), expected)

    def test_empty_and_blank_strings(self) -> None:
        """Verify empty or whitespace strings return empty string."""
        self.assertEqual(self.normalizer.normalize(""), "")
        self.assertEqual(self.normalizer.normalize("   "), "")
        self.assertEqual(self.normalizer.normalize("\n\t  "), "")


if __name__ == "__main__":
    unittest.main()
