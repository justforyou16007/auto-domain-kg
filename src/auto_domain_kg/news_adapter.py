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
    original_language: str = ""


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

    async def bilingual_search(
        self,
        query: str,
        english_query: Optional[str] = None,
        target_language: str = "zh-CN",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_results: int = 10,
    ) -> list[NewsItem]:
        """Search using BOTH a Chinese and an English query, then merge.

        Issue #25: retrieval results vary by search language, which limited
        graph completeness. This method issues searches for both the
        Chinese and English versions of the query, merges the results and
        deduplicates them by URL so downstream Schema/entity exploration is
        not constrained by the query language.

        Args:
            query: The primary query string (any language). If it is already
                Chinese, it is used directly; if it is English,
                ``english_query`` is ignored for the English search.
            english_query: Explicit English version of the query. If not
                provided, a simple heuristic is used to derive one (the
                caller — typically the agent — may pass both).
            target_language: The working language used to tag the merged
                results metadata (default "zh-CN").
            date_from: Optional start date (YYYY-MM-DD) forwarded to
                ``search_news``.
            date_to: Optional end date (YYYY-MM-DD) forwarded to
                ``search_news``.
            max_results: Maximum results per language search.

        Returns:
            Merged, URL-deduplicated list of NewsItem. Each item carries a
            ``language`` field reflecting the search it came from.
        """
        zh_query, en_query = self._make_bilingual_queries(query, english_query)

        results: list[NewsItem] = []
        seen_urls: set[str] = set()
        for lang, q in (("zh-CN", zh_query), ("en", en_query)):
            if not q:
                continue
            items = await self.search_news(
                query=q,
                language=lang,
                date_from=date_from,
                date_to=date_to,
                max_results=max_results,
            )
            for item in items:
                if item.url and item.url in seen_urls:
                    continue
                if item.url:
                    seen_urls.add(item.url)
                # Preserve the item's detected language but fall back to the
                # search language used.
                if not item.language:
                    item.language = lang
                results.append(item)
        return results

    async def translate_content(
        self,
        item: NewsItem,
        target_lang: str = "zh-CN",
    ) -> NewsItem:
        """Translate a NewsItem's title and content to ``target_lang``.

        Issue #25: search results returned in a foreign language are
        translated to the working language *before* Schema and entity
        exploration so the downstream steps operate on a unified corpus.

        Uses the external OpenAI-compatible translation endpoint configured
        via ``TRANSLATION_ENDPOINT`` / ``TRANSLATION_API_KEY`` /
        ``TRANSLATION_MODEL``. If no endpoint is configured, the item is
        returned unchanged (graceful degradation).

        Args:
            item: News item to translate.
            target_lang: Target language code (default "zh-CN").

        Returns:
            A new NewsItem with translated ``title`` and ``content``,
            preserving ``url``, ``source`` and ``published_at`` and setting
            ``original_language``.
        """
        from auto_domain_kg.translation import TranslationClient

        client = TranslationClient()
        try:
            return await client.translate_news_item(item, target_lang=target_lang)
        finally:
            await client.close()

    async def bilingual_search_and_translate(
        self,
        query: str,
        english_query: Optional[str] = None,
        target_language: str = "zh-CN",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_results: int = 10,
    ) -> list[NewsItem]:
        """Run bilingual search then translate all results.

        Orchestrates the Issue #25 pipeline:
        1. ``bilingual_search`` issues zh + en queries and dedupes by URL.
        2. Every returned item is translated to ``target_language`` before
           being handed back for Schema/entity exploration.

        When translation is not configured, results are returned with their
        original language content (graceful degradation).

        Args:
            query: Primary query string (any language).
            english_query: Explicit English query (optional).
            target_language: Working language to translate results into.
            date_from / date_to / max_results: Forwarded to ``search_news``.

        Returns:
            Unified, translated list of NewsItem.
        """
        from auto_domain_kg.translation import TranslationClient

        results = await self.bilingual_search(
            query=query,
            english_query=english_query,
            target_language=target_language,
            date_from=date_from,
            date_to=date_to,
            max_results=max_results,
        )
        if not results:
            return results

        client = TranslationClient()
        try:
            if not client.is_available():
                return results
            translated: list[NewsItem] = []
            for item in results:
                translated.append(
                    await client.translate_news_item(item, target_lang=target_language)
                )
            return translated
        finally:
            await client.close()

    @staticmethod
    def _make_bilingual_queries(
        query: str,
        english_query: Optional[str] = None,
    ) -> tuple[str, str]:
        """Return (chinese_query, english_query) for a bilingual search.

        Heuristically detect whether ``query`` is Chinese (contains CJK
        characters). If an explicit ``english_query`` is provided it is
        used for the English search; otherwise a simple mapping is applied.
        The calling agent is free to pass both queries directly.
        """
        def _has_cjk(text: str) -> bool:
            return any("\u4e00" <= ch <= "\u9fff" for ch in text)

        if english_query:
            zh_query = query if _has_cjk(query) else query
            en_query = english_query
        elif _has_cjk(query):
            # Query is Chinese; without an explicit English version we use it
            # for both searches (the caller should ideally supply both).
            zh_query = query
            en_query = query
        else:
            # Query is (likely) English; use it for the English search and
            # reuse it for the Chinese search too.
            zh_query = query
            en_query = query
        return zh_query, en_query


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