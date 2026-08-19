"""News source adapter specification and implementations.

Provides an abstract base class for news adapters and a concrete
implementation using Google Custom Search JSON API.

## How to Implement a New Adapter

1. Create a subclass of `NewsAdapter`.
2. Implement the `search_news()` method.
3. Return a list of `NewsItem` dataclass instances.
4. Register your adapter in the factory or use it directly.

Example:
    ```python
    class MyNewsAdapter(NewsAdapter):
        async def search_news(self, query, language="en", date_from=None, date_to=None):
            # Your implementation
            return [NewsItem(...)]
    ```
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx


@dataclass
class NewsItem:
    """A single news item/article."""

    title: str
    url: str
    content: str
    published_at: Optional[datetime] = None
    language: str = "en"
    source: str = ""


class NewsAdapter(ABC):
    """Abstract base class for news source adapters.

    Implement search_news() to integrate with different news sources.
    """

    @abstractmethod
    async def search_news(
        self,
        query: str,
        language: str = "en",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_results: int = 10,
    ) -> list[NewsItem]:
        """Search for news articles matching the query.

        Args:
            query: Search query string.
            language: Language code (e.g., "en", "zh-CN").
            date_from: Start date in YYYY-MM-DD format.
            date_to: End date in YYYY-MM-DD format.
            max_results: Maximum number of results to return.

        Returns:
            List of NewsItem objects matching the search.
        """
        ...


class GoogleSearchNewsAdapter(NewsAdapter):
    """News adapter using Google Custom Search JSON API.

    Environment variables required:
        GOOGLE_API_KEY: Google Custom Search API key.
        GOOGLE_CSE_ID: Google Custom Search Engine ID.

    The adapter filters results to news-like sources and returns
    structured NewsItem objects.
    """

    def __init__(self) -> None:
        """Initialize the Google Search adapter.

        Raises:
            ValueError: If required environment variables are missing.
        """
        self.api_key = os.environ.get("GOOGLE_API_KEY", "")
        self.cse_id = os.environ.get("GOOGLE_CSE_ID", "")
        if not self.api_key or not self.cse_id:
            raise ValueError(
                "Google Custom Search API requires GOOGLE_API_KEY and "
                "GOOGLE_CSE_ID environment variables."
            )
        self._client = httpx.AsyncClient(timeout=30.0)

    async def search_news(
        self,
        query: str,
        language: str = "en",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_results: int = 10,
    ) -> list[NewsItem]:
        """Search for news using Google Custom Search.

        Args:
            query: Search query string.
            language: Language code for results.
            date_from: Not directly supported by Google CSE; use query modifiers.
            date_to: Not directly supported by Google CSE; use query modifiers.
            max_results: Maximum number of results (max 10 per Google CSE limit).

        Returns:
            List of NewsItem objects.
        """
        params: dict[str, str | int] = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": query,
            "num": min(max_results, 10),
            "lr": self._language_to_lr(language),
        }

        try:
            response = await self._client.get(
                "https://www.googleapis.com/customsearch/v1",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            items = data.get("items", [])
            results: list[NewsItem] = []
            for item in items:
                published = None
                # Google CSE may return pagemap with metatags
                pagemap = item.get("pagemap", {})
                metatags = pagemap.get("metatags", [{}])
                if metatags and metatags[0].get("article:published_time"):
                    try:
                        published = datetime.fromisoformat(
                            metatags[0]["article:published_time"].replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

                snippet = item.get("snippet", "")
                results.append(
                    NewsItem(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        content=snippet,
                        published_at=published,
                        language=language,
                        source=item.get("displayLink", ""),
                    )
                )

            return results

        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Google Search API error: {e.response.status_code} - {e.response.text}"
            )
        except httpx.RequestError as e:
            raise RuntimeError(f"Google Search API request failed: {e}")
        except (KeyError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Invalid Google Search API response: {e}")

    def _language_to_lr(self, language: str) -> str:
        """Convert language code to Google CSE 'lr' parameter.

        Args:
            language: Language code (e.g., "en", "zh-CN").

        Returns:
            Google CSE language restriction string.
        """
        mapping = {
            "en": "lang_en",
            "zh-CN": "lang_zh-CN",
            "zh-TW": "lang_zh-TW",
            "ja": "lang_ja",
            "ko": "lang_ko",
            "fr": "lang_fr",
            "de": "lang_de",
            "es": "lang_es",
        }
        return mapping.get(language, f"lang_{language}")

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()