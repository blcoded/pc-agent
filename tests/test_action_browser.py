"""Unit tests for Browser and Web Search Actions (TASK-6.4)."""

import unittest
from unittest.mock import MagicMock

from voice_agent.control.actions.browser import (
    OpenUrlAction,
    SEARCH_PROVIDERS,
    SearchWebAction,
)
from voice_agent.control.models import ActionType


class TestActionBrowser(unittest.TestCase):
    """Test suite for OpenUrlAction and SearchWebAction."""

    def test_open_url_success(self) -> None:
        """Test opening valid URLs with mock browser opener."""
        mock_opener = MagicMock(return_value=True)
        action = OpenUrlAction(browser_opener=mock_opener)
        self.assertEqual(action.action_type, ActionType.OPEN_URL)

        result = action.run({"url": "https://github.com/blcoded"})
        self.assertTrue(result.success)
        self.assertEqual(result.output["url"], "https://github.com/blcoded")
        mock_opener.assert_called_once_with("https://github.com/blcoded")

    def test_open_url_auto_scheme_and_validation(self) -> None:
        """Test URL normalization and protocol enforcement."""
        mock_opener = MagicMock(return_value=True)
        action = OpenUrlAction(browser_opener=mock_opener)

        # Domain without scheme should get https:// prepended
        res_scheme = action.run({"url": "python.org"})
        self.assertTrue(res_scheme.success)
        self.assertEqual(res_scheme.output["url"], "https://python.org")

        # Disallowed schemes
        for bad_url in ("javascript:alert(1)", "file:///C:/secrets.txt", "ftp://files.org"):
            res_bad = action.run({"url": bad_url})
            self.assertFalse(res_bad.success, f"Should reject {bad_url}")
            self.assertIn("Validation failed", res_bad.error_message or "")

    def test_open_url_error_handling(self) -> None:
        """Test error handling when browser opener fails."""
        def bad_opener(url: str) -> bool:
            raise RuntimeError("Browser not configured")

        action = OpenUrlAction(browser_opener=bad_opener)
        result = action.run({"url": "https://google.com"})
        self.assertFalse(result.success)
        self.assertIn("Browser not configured", result.error_message or "")

    def test_search_web_google_default(self) -> None:
        """Test searching with default Google provider and URL encoding."""
        mock_opener = MagicMock(return_value=True)
        action = SearchWebAction(browser_opener=mock_opener)
        self.assertEqual(action.action_type, ActionType.SEARCH_WEB)

        result = action.run({"query": "python async await"})
        self.assertTrue(result.success)
        self.assertEqual(result.output["query"], "python async await")
        self.assertEqual(result.output["provider"], "google")
        self.assertIn("https://www.google.com/search?q=python+async+await", result.output["search_url"])
        mock_opener.assert_called_once_with("https://www.google.com/search?q=python+async+await")

    def test_search_web_alternative_providers(self) -> None:
        """Test searching via Bing and DuckDuckGo."""
        mock_opener = MagicMock(return_value=True)
        action = SearchWebAction(browser_opener=mock_opener)

        # Bing
        res_bing = action.run({"query": "weather today", "provider": "bing"})
        self.assertTrue(res_bing.success)
        self.assertIn("https://www.bing.com/search?q=weather+today", res_bing.output["search_url"])

        # DuckDuckGo
        res_ddg = action.run({"query": "privacy search", "provider": "duckduckgo"})
        self.assertTrue(res_ddg.success)
        self.assertIn("https://duckduckgo.com/?q=privacy+search", res_ddg.output["search_url"])

    def test_search_web_special_characters(self) -> None:
        """Test proper percent-encoding of special characters and symbols."""
        action = SearchWebAction()
        url = action.build_search_url("C++ & Python: which is faster?", provider="google")
        self.assertIn("C%2B%2B+%26+Python%3A+which+is+faster%3F", url)

    def test_search_web_validation_failure(self) -> None:
        """Test rejection of blank or malformed search queries."""
        action = SearchWebAction()

        # Missing query
        res_missing = action.run({})
        self.assertFalse(res_missing.success)

        # Blank query
        res_blank = action.run({"query": "   "})
        self.assertFalse(res_blank.success)

        # Null byte or newline in query
        res_null = action.run({"query": "bad\0query"})
        self.assertFalse(res_null.success)

        res_newline = action.run({"query": "bad\nquery"})
        self.assertFalse(res_newline.success)


if __name__ == "__main__":
    unittest.main()
