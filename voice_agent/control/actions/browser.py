"""Browser and Web Search Actions for PC Voice Agent.

Provides URL navigation and search engine query execution using the user's
default system web browser.
"""

from __future__ import annotations

import logging
import urllib.parse
import webbrowser
from typing import Any, Callable

from voice_agent.control.actions.base import (
    Action,
    ActionResult,
    ActionType,
    ActionValidationError,
)
from voice_agent.control.action_validator import ActionValidator

logger = logging.getLogger(__name__)

# Search provider template URLs
SEARCH_PROVIDERS: dict[str, str] = {
    "google": "https://www.google.com/search?q={query}",
    "bing": "https://www.bing.com/search?q={query}",
    "duckduckgo": "https://duckduckgo.com/?q={query}",
}


class OpenUrlAction(Action):
    """Action that validates and opens a URL in the default web browser."""

    def __init__(
        self,
        browser_opener: Callable[[str], bool] | None = None,
        validator: ActionValidator | None = None,
    ) -> None:
        """Initialize OpenUrlAction.

        Args:
            browser_opener: Callable that opens a URL (defaults to webbrowser.open).
            validator: Parameter validator.
        """
        self.browser_opener = browser_opener or webbrowser.open
        self.validator = validator or ActionValidator()

    @property
    def action_type(self) -> ActionType:
        return ActionType.OPEN_URL

    def validate(self, params: dict[str, Any]) -> bool:
        if "url" not in params:
            raise ActionValidationError("Missing 'url' parameter for OPEN_URL.")
        self.validator.validate_url(params["url"])
        return True

    def execute(self, params: dict[str, Any]) -> ActionResult:
        raw_url = str(params["url"]).strip()
        validated_url = self.validator.validate_url(raw_url)

        try:
            opened = self.browser_opener(validated_url)
            logger.info("Opened URL '%s' in browser (opened=%s)", validated_url, opened)
            return ActionResult(
                success=True,
                output={"url": validated_url, "opened": opened},
            )
        except Exception as exc:
            logger.error("Failed to open URL '%s': %s", validated_url, exc)
            return ActionResult(success=False, output=None, error_message=str(exc))


class SearchWebAction(Action):
    """Action that safely encodes search queries and opens them in the search engine."""

    def __init__(
        self,
        browser_opener: Callable[[str], bool] | None = None,
        validator: ActionValidator | None = None,
        default_provider: str = "google",
    ) -> None:
        """Initialize SearchWebAction.

        Args:
            browser_opener: Callable that opens a URL.
            validator: Parameter validator.
            default_provider: Default search engine ('google', 'bing', 'duckduckgo').
        """
        self.browser_opener = browser_opener or webbrowser.open
        self.validator = validator or ActionValidator()
        self.default_provider = default_provider.lower()

    @property
    def action_type(self) -> ActionType:
        return ActionType.SEARCH_WEB

    def validate(self, params: dict[str, Any]) -> bool:
        if "query" not in params:
            raise ActionValidationError("Missing 'query' parameter for SEARCH_WEB.")
        query = str(params["query"]).strip()
        if not query:
            raise ActionValidationError("Search 'query' cannot be blank.")
        # Reject control characters
        for char in query:
            if char in ("\0", "\r", "\n"):
                raise ActionValidationError("Control characters not allowed in search query.")
        return True

    def build_search_url(self, query: str, provider: str = "google") -> str:
        """Construct the search provider URL with encoded query parameter.

        Args:
            query: Raw search query text.
            provider: Search provider name.

        Returns:
            Fully-qualified search URL.
        """
        prov_key = provider.lower().strip()
        template = SEARCH_PROVIDERS.get(prov_key, SEARCH_PROVIDERS["google"])
        encoded_query = urllib.parse.quote_plus(query.strip())
        return template.format(query=encoded_query)

    def execute(self, params: dict[str, Any]) -> ActionResult:
        query = str(params["query"]).strip()
        provider = str(params.get("provider", self.default_provider)).lower().strip()
        search_url = self.build_search_url(query, provider)

        try:
            opened = self.browser_opener(search_url)
            logger.info("Dispatched search for '%s' to '%s' (url=%s)", query, provider, search_url)
            return ActionResult(
                success=True,
                output={
                    "query": query,
                    "provider": provider,
                    "search_url": search_url,
                    "opened": opened,
                },
            )
        except Exception as exc:
            logger.error("Failed to execute web search for '%s': %s", query, exc)
            return ActionResult(success=False, output=None, error_message=str(exc))


__all__ = ["OpenUrlAction", "SEARCH_PROVIDERS", "SearchWebAction"]
