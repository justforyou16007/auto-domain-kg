"""Information extraction API client.

Provides entity-relation extraction over external HTTP APIs, with two modes:

1. **Generic API mode** — send text to a general-purpose LLM chat-completions
   endpoint and parse the structured JSON it returns (entities + relations).
   This is the default mode when ``EXTRACTION_ENDPOINT`` points at an
   OpenAI-compatible chat completions URL.

2. **Dedicated extraction API mode** — send text to a specialized
   entity-relation extraction endpoint that returns a structured
   ``{"entities": [...], "relations": [...]}`` payload directly. Use
   :meth:`InfoExtractionClient.extract_dedicated` for this mode.

The client also **doubles as a translation API client**: it reuses the same
endpoint infrastructure to translate text via the ``TRANSLATION_*`` env vars
(falling back to the ``EXTRACTION_*`` endpoint when no translation endpoint is
configured). This avoids spawning a second HTTP client in flows that already
need extraction.

Configuration (environment variables):
    EXTRACTION_ENDPOINT   — extraction / generic LLM endpoint URL.
    EXTRACTION_API_KEY    — Bearer token sent as ``Authorization``.
    EXTRACTION_MODEL      — model name for the generic LLM mode (default ``gpt-4o``).
    TRANSLATION_ENDPOINT  — translation endpoint URL (optional; falls back to
                            EXTRACTION_ENDPOINT when not set).
    TRANSLATION_API_KEY   — translation Bearer token (falls back to EXTRACTION_API_KEY).
    TRANSLATION_MODEL     — translation model name (default ``gpt-4o-mini``).

Design goals:
- Graceful degradation: if no endpoint is configured, extraction/translation
  return empty structures / original text so the construction flow keeps working.
- Caching: identical inputs are processed once and reused.
- Robust parsing: the generic mode tolerates LLM output wrapped in Markdown
  code fences and repairs trivially broken JSON before giving up.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx


class ExtractionError(RuntimeError):
    """Raised when an extraction or translation API call fails irrecoverably."""


@dataclass
class ExtractionConfig:
    """Extraction + translation configuration read from environment variables."""

    extraction_endpoint: str = field(
        default_factory=lambda: os.environ.get("EXTRACTION_ENDPOINT", "")
    )
    extraction_api_key: str = field(
        default_factory=lambda: os.environ.get("EXTRACTION_API_KEY", "")
    )
    extraction_model: str = field(
        default_factory=lambda: os.environ.get("EXTRACTION_MODEL", "gpt-4o")
    )
    # Translation may reuse a separate endpoint or fall back to the extraction
    # endpoint when unset.
    translation_endpoint: str = field(
        default_factory=lambda: os.environ.get("TRANSLATION_ENDPOINT", "")
    )
    translation_api_key: str = field(
        default_factory=lambda: os.environ.get("TRANSLATION_API_KEY", "")
    )
    translation_model: str = field(
        default_factory=lambda: os.environ.get("TRANSLATION_MODEL", "gpt-4o-mini")
    )


class InfoExtractionClient:
    """Client for entity-relation extraction and translation via external APIs.

    The client is dual-purpose: it performs structured extraction in either a
    generic-LLM mode (:meth:`extract`) or a dedicated-extraction mode
    (:meth:`extract_dedicated`), and also performs translation
    (:meth:`translate`) reusing the same HTTP infrastructure.
    """

    _CHAT_COMPLETIONS_HINTS = ("chat/completions", "/v1/chat", "openai")
    _EMPTY_RESULT: dict[str, list] = {"entities": [], "relations": []}

    def __init__(self, config: Optional[ExtractionConfig] = None) -> None:
        self._config = config or ExtractionConfig()
        self._extraction_cache: dict[str, dict[str, Any]] = {}
        self._translation_cache: dict[str, str] = {}
        self._client = httpx.AsyncClient(timeout=60.0)

    # ------------------------------------------------------------------ #
    # Availability helpers
    # ------------------------------------------------------------------ #
    def is_extraction_available(self) -> bool:
        """Return True when an extraction endpoint is configured (non-network check)."""
        return bool(self._config.extraction_endpoint and self._config.extraction_endpoint.strip())

    def is_dedicated_available(self) -> bool:
        """Return True when the extraction endpoint is NOT a chat-completions URL.

        Dedicated extraction endpoints return a structured payload directly,
        so they are distinguished from generic LLM chat endpoints.
        """
        if not self.is_extraction_available():
            return False
        endpoint = self._config.extraction_endpoint.lower()
        return not any(hint in endpoint for hint in self._CHAT_COMPLETIONS_HINTS)

    def is_translation_available(self) -> bool:
        """Return True when a translation endpoint is configured."""
        return bool(self._config.translation_endpoint and self._config.translation_endpoint.strip())

    # ------------------------------------------------------------------ #
    # Generic API extraction mode
    # ------------------------------------------------------------------ #
    async def extract(self, text: str) -> dict[str, list]:
        """Extract entities and relations from ``text`` via a generic LLM API.

        Sends the text to the configured chat-completions endpoint with an
        instruction to return strict JSON of the form::

            {"entities": [{"name": ..., "type": ...}],
             "relations": [{"subject": ..., "predicate": ..., "object": ...}]}

        Args:
            text: Input text to extract from.

        Returns:
            A dict with ``"entities"`` and ``"relations"`` lists. When no
            endpoint is configured, an empty structure is returned (graceful
            degradation).
        """
        if not text:
            return dict(self._EMPTY_RESULT)
        if not self.is_extraction_available():
            return dict(self._EMPTY_RESULT)

        cache_key = text.strip().lower()
        if cache_key in self._extraction_cache:
            return self._extraction_cache[cache_key]

        raw = await self._call_chat_api(text)
        parsed = self._parse_extraction_json(raw)
        if parsed is None:
            raise ExtractionError(
                f"Failed to parse extraction response as JSON. Raw output: {raw[:200]!r}"
            )
        self._extraction_cache[cache_key] = parsed
        return parsed

    # ------------------------------------------------------------------ #
    # Dedicated extraction API mode
    # ------------------------------------------------------------------ #
    async def extract_dedicated(self, text: str) -> dict[str, list]:
        """Extract entities and relations via a dedicated extraction endpoint.

        The dedicated endpoint is expected to return a structured
        ``{"entities": [...], "relations": [...]}`` payload directly.

        Args:
            text: Input text to extract from.

        Returns:
            A dict with ``"entities"`` and ``"relations"`` lists. When no
            endpoint is configured, an empty structure is returned (graceful
            degradation).
        """
        if not text:
            return dict(self._EMPTY_RESULT)
        if not self.is_extraction_available():
            return dict(self._EMPTY_RESULT)

        cache_key = "dedicated:" + text.strip().lower()
        if cache_key in self._extraction_cache:
            return self._extraction_cache[cache_key]

        try:
            response = await self._client.post(
                self._config.extraction_endpoint,
                headers=self._build_headers(self._config.extraction_api_key),
                content=json.dumps({"text": text, "model": self._config.extraction_model}),
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            raise ExtractionError(
                f"Dedicated extraction API error: {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise ExtractionError(f"Dedicated extraction request failed: {exc}") from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise ExtractionError(f"Invalid dedicated extraction response: {exc}") from exc

        result = {
            "entities": list(data.get("entities", [])),
            "relations": list(data.get("relations", [])),
        }
        self._extraction_cache[cache_key] = result
        return result

    # ------------------------------------------------------------------ #
    # Translation (dual-purpose client)
    # ------------------------------------------------------------------ #
    async def translate(
        self,
        text: str,
        source_lang: str = "",
        target_lang: str = "zh-CN",
    ) -> str:
        """Translate ``text`` to ``target_lang`` reusing the endpoint infrastructure.

        Uses ``TRANSLATION_ENDPOINT`` when configured, otherwise falls back to
        the ``EXTRACTION_ENDPOINT``. When neither is configured, the original
        text is returned unchanged (graceful degradation).
        """
        if not text:
            return text

        endpoint = self._config.translation_endpoint or self._config.extraction_endpoint
        if not endpoint or not endpoint.strip():
            return text

        cache_key = f"t:{source_lang}->{target_lang}:{text.strip().lower()}"
        if cache_key in self._translation_cache:
            return self._translation_cache[cache_key]

        api_key = self._config.translation_api_key or self._config.extraction_api_key
        model = self._config.translation_model or self._config.extraction_model

        system_prompt = (
            "You are a professional translation engine. Translate the user's "
            f"text into {target_lang}. Preserve meaning, names, and numbers. "
            "Output ONLY the translation, with no explanation or quotes."
        )
        user_prompt = text
        if source_lang:
            user_prompt = f"[source: {source_lang}] {text}"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }

        try:
            response = await self._client.post(
                endpoint,
                headers=self._build_headers(api_key),
                content=json.dumps(payload),
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            content = choices[0].get("message", {}).get("content", "") if choices else ""
            translated = content.strip()
        except httpx.HTTPStatusError as exc:
            raise ExtractionError(
                f"Translation API error: {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise ExtractionError(f"Translation request failed: {exc}") from exc
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            raise ExtractionError(f"Invalid translation response: {exc}") from exc

        if not translated:
            return text
        self._translation_cache[cache_key] = translated
        return translated

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _build_headers(self, api_key: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    async def _call_chat_api(self, text: str) -> str:
        """Send a chat-completions extraction request and return raw content."""
        system_prompt = (
            "You are an information extraction engine. Extract entities and "
            "relations from the user's text. Output ONLY a JSON object with two "
            "keys: \"entities\" (a list of {\"name\", \"type\"}) and \"relations\" "
            "(a list of {\"subject\", \"predicate\", \"object\"}). Do not include "
            "any explanation or Markdown formatting."
        )
        payload = {
            "model": self._config.extraction_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.1,
        }
        try:
            response = await self._client.post(
                self._config.extraction_endpoint,
                headers=self._build_headers(self._config.extraction_api_key),
                content=json.dumps(payload),
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                return ""
            message = choices[0].get("message", {})
            return message.get("content", "") or ""
        except httpx.HTTPStatusError as exc:
            raise ExtractionError(
                f"Extraction API error: {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise ExtractionError(f"Extraction request failed: {exc}") from exc
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            raise ExtractionError(f"Invalid extraction response: {exc}") from exc

    def _parse_extraction_json(self, raw: str) -> Optional[dict[str, list]]:
        """Parse an LLM extraction response into an entities/relations dict.

        Tolerates Markdown code fences and tries a couple of repair strategies
        (extracting the first JSON object, stripping trailing commas) before
        giving up. Returns ``None`` when the response cannot be parsed.
        """
        if not raw:
            return None

        text = raw.strip()

        # Strip Markdown code fences if present.
        fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()

        # Try direct parse first.
        candidate = self._try_load_json(text)
        if candidate is not None:
            return self._normalize_result(candidate)

        # Try to locate the first {...} balanced JSON object in the text.
        obj_match = re.search(r"\{.*\}", text, re.DOTALL)
        if obj_match:
            candidate = self._try_load_json(obj_match.group(0))
            if candidate is not None:
                return self._normalize_result(candidate)

        return None

    @staticmethod
    def _try_load_json(text: str) -> Optional[Any]:
        try:
            return json.loads(text)
        except (ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def _normalize_result(data: Any) -> dict[str, list]:
        """Coerce a parsed JSON value into the {entities, relations} shape."""
        if not isinstance(data, dict):
            return {"entities": [], "relations": []}
        return {
            "entities": list(data.get("entities", []) or []),
            "relations": list(data.get("relations", []) or []),
        }
