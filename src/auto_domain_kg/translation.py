"""External API translation client (OpenAI-compatible chat completions).

Provides configurable text translation via external HTTP APIs that follow
the OpenAI Chat Completions schema. Used by the news adapter (Issue #25)
to translate search results to a working language before Schema/entity
exploration, so that retrieval is not limited by the search query language.

Design goals:
- Graceful degradation: if no endpoint is configured, the original text is
  returned unchanged (the graph construction flow must keep working even
  without a translation backend).
- Caching: identical (text, source_lang, target_lang) tuples are translated
  once and reused to avoid re-translating the same content.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import httpx

if TYPE_CHECKING:
    from auto_domain_kg.news_adapter import NewsItem


@dataclass
class TranslationConfig:
    """Translation configuration read from environment variables."""

    endpoint: str = field(
        default_factory=lambda: os.environ.get("TRANSLATION_ENDPOINT", "")
    )
    api_key: str = field(
        default_factory=lambda: os.environ.get("TRANSLATION_API_KEY", "")
    )
    model: str = field(
        default_factory=lambda: os.environ.get("TRANSLATION_MODEL", "gpt-4o-mini")
    )


class TranslationClient:
    """Client for translating text via an OpenAI-compatible chat API.

    Environment variables:
        TRANSLATION_ENDPOINT: Chat completions endpoint URL (e.g.
            ``https://api.openai.com/v1/chat/completions``).
        TRANSLATION_API_KEY: Bearer token sent as ``Authorization``.
        TRANSLATION_MODEL: Model name (default ``gpt-4o-mini``).

    When ``TRANSLATION_ENDPOINT`` is not set, the client degrades
    gracefully: :meth:`translate` returns the original text unchanged and
    :meth:`translate_news_item` returns the item unchanged.
    """

    def __init__(self, config: Optional[TranslationConfig] = None) -> None:
        """Initialize the translation client.

        Args:
            config: Translation configuration. If None, reads from env vars.
        """
        self._config = config or TranslationConfig()
        self._cache: dict[str, str] = {}
        self._client = httpx.AsyncClient(timeout=60.0)

    def is_available(self) -> bool:
        """Return True when a translation endpoint is configured.

        This is a lightweight, non-network check — it only verifies the
        endpoint URL is present and non-empty.
        """
        return bool(self._config.endpoint and self._config.endpoint.strip())

    def _make_cache_key(self, text: str, source_lang: str, target_lang: str) -> str:
        """Create a cache key for a translation request."""
        return f"{source_lang}->{target_lang}:{text.strip().lower()}"

    async def translate(
        self,
        text: str,
        source_lang: str = "",
        target_lang: str = "zh-CN",
    ) -> str:
        """Translate ``text`` from ``source_lang`` to ``target_lang``.

        Args:
            text: Input text to translate.
            source_lang: Source language code (e.g. "en", "zh-CN"). May be
                empty/unknown — the model will infer it.
            target_lang: Target language code (default "zh-CN").

        Returns:
            Translated text. If no endpoint is configured, returns the
            original ``text`` unchanged (graceful degradation).
        """
        if not text:
            return text
        if not self.is_available():
            return text

        cache_key = self._make_cache_key(text, source_lang, target_lang)
        if cache_key in self._cache:
            return self._cache[cache_key]

        translated = await self._call_api(text, source_lang, target_lang)
        if translated:
            self._cache[cache_key] = translated
        return translated or text

    async def translate_news_item(
        self,
        item: "NewsItem",
        target_lang: str = "zh-CN",
    ) -> "NewsItem":
        """Translate a :class:`NewsItem`'s ``title`` and ``content``.

        Preserves ``url``, ``source`` and ``published_at``, sets
        ``language`` to ``target_lang`` and records the original language
        in ``original_language``.

        Args:
            item: News item to translate.
            target_lang: Target language code.

        Returns:
            A new ``NewsItem``. If no endpoint is configured, a copy of the
            original item is returned unchanged (graceful degradation).
        """
        # Local import to avoid a circular import at module load time.
        from auto_domain_kg.news_adapter import NewsItem

        if not self.is_available():
            return NewsItem(
                title=item.title,
                url=item.url,
                content=item.content,
                published_at=item.published_at,
                language=item.language,
                source=item.source,
                original_language=item.original_language or item.language,
            )

        original_language = item.original_language or item.language or ""
        translated_title = await self.translate(
            item.title, source_lang=original_language, target_lang=target_lang
        )
        translated_content = await self.translate(
            item.content, source_lang=original_language, target_lang=target_lang
        )

        return NewsItem(
            title=translated_title,
            url=item.url,
            content=translated_content,
            published_at=item.published_at,
            language=target_lang,
            source=item.source,
            original_language=original_language,
        )

    async def _call_api(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> str:
        """Send a chat-completions translation request to the API.

        Returns:
            Translated text, or empty string on failure.
        """
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        system_prompt = (
            "You are a professional translation engine. Translate the user's "
            f"text into {target_lang}. Preserve meaning, names, and numbers. "
            "Output ONLY the translation, with no explanation or quotes."
        )
        user_prompt = text
        if source_lang:
            user_prompt = f"[source: {source_lang}] {text}"

        payload = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }

        try:
            response = await self._client.post(
                self._config.endpoint,
                headers=headers,
                content=json.dumps(payload),
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                return ""
            message = choices[0].get("message", {})
            content = message.get("content", "")
            return content.strip()
        except httpx.HTTPStatusError:
            return ""
        except httpx.RequestError:
            return ""
        except (KeyError, json.JSONDecodeError):
            return ""

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
