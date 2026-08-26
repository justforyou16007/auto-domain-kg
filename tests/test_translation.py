"""Tests for the TranslationClient module (Issue #25)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from auto_domain_kg.news_adapter import NewsItem
from auto_domain_kg.translation import TranslationClient


def _mock_openai_response(text: str) -> MagicMock:
    """Build a mock httpx response carrying an OpenAI chat completion payload."""
    payload = {
        "choices": [
            {"message": {"role": "assistant", "content": text}, "index": 0}
        ]
    }
    resp = MagicMock()
    resp.status_code = 200
    resp.json = MagicMock(return_value=payload)
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def translation_env():
    """Configure a translation endpoint via env vars."""
    with patch.dict(
        "os.environ",
        {
            "TRANSLATION_ENDPOINT": "https://example.com/v1/chat/completions",
            "TRANSLATION_API_KEY": "test-translation-key",
            "TRANSLATION_MODEL": "gpt-4o-mini",
        },
    ):
        yield


@pytest.fixture
def client(translation_env):
    """Create a TranslationClient with a mocked HTTP client."""
    c = TranslationClient()
    c._client = AsyncMock()
    return c


@pytest.mark.asyncio
async def test_translate_translates_text(client):
    """translate() should call the OpenAI-compatible endpoint and return content."""
    client._client.post = AsyncMock(
        return_value=_mock_openai_response("Translated text")
    )

    result = await client.translate("Hello", source_lang="en", target_lang="zh-CN")
    assert result == "Translated text"
    client._client.post.assert_awaited()
    # Ensure the endpoint and model were used
    call_kwargs = client._client.post.call_args
    assert "example.com" in call_kwargs.args[0]
    body = call_kwargs.kwargs.get("content") or call_kwargs.kwargs.get("data")
    assert "gpt-4o-mini" in body


@pytest.mark.asyncio
async def test_translate_caches_results(client):
    """translate() should cache and not re-call the API for the same text."""
    client._client.post = AsyncMock(
        return_value=_mock_openai_response("Cached translation")
    )

    first = await client.translate("Hello", source_lang="en", target_lang="zh-CN")
    second = await client.translate("Hello", source_lang="en", target_lang="zh-CN")
    assert first == second == "Cached translation"
    # API should only be called once due to caching
    assert client._client.post.await_count == 1


@pytest.mark.asyncio
async def test_translate_news_item_updates_fields(client):
    """translate_news_item() returns a NewsItem with translated title/content."""
    item = NewsItem(
        title="Hello World",
        url="https://example.com/news/1",
        content="This is an article about supply chains.",
        source="example.com",
        language="en",
    )

    def post_side_effect(endpoint, **kwargs):
        content = kwargs.get("content") or kwargs.get("data") or ""
        if "Hello World" in content:
            return _mock_openai_response("Translated Title")
        return _mock_openai_response("Translated Content")

    client._client.post = AsyncMock(side_effect=post_side_effect)

    translated = await client.translate_news_item(item, target_lang="zh-CN")
    assert translated.title == "Translated Title"
    assert translated.content == "Translated Content"
    # Preserved fields
    assert translated.url == item.url
    assert translated.source == item.source
    assert translated.published_at == item.published_at
    # original_language populated
    assert translated.original_language == "en"
    assert translated.language == "zh-CN"


@pytest.mark.asyncio
async def test_translate_news_item_graceful_degradation():
    """When endpoint is not configured, the item is returned unchanged."""
    with patch.dict("os.environ", {}, clear=True):
        c = TranslationClient()
        assert not c.is_available()

    item = NewsItem(
        title="Hello World",
        url="https://example.com/news/1",
        content="Some content",
        source="example.com",
        language="en",
    )
    translated = await c.translate_news_item(item, target_lang="zh-CN")
    # Unchanged item
    assert translated.title == item.title
    assert translated.content == item.content
    assert translated.url == item.url


@pytest.mark.asyncio
async def test_translate_graceful_degradation():
    """translate() returns original text when endpoint not configured."""
    with patch.dict("os.environ", {}, clear=True):
        c = TranslationClient()
    result = await c.translate("Hello", source_lang="en", target_lang="zh-CN")
    assert result == "Hello"


def test_default_model():
    """TranslationClient defaults to gpt-4o-mini."""
    with patch.dict(
        "os.environ",
        {"TRANSLATION_ENDPOINT": "https://x.com", "TRANSLATION_API_KEY": "k"},
        clear=True,
    ):
        c = TranslationClient()
        assert c._config.model == "gpt-4o-mini"


def test_is_available_true_when_configured(translation_env):
    c = TranslationClient()
    assert c.is_available() is True


def test_is_available_false_when_not_configured():
    with patch.dict("os.environ", {}, clear=True):
        c = TranslationClient()
        assert c.is_available() is False


@pytest.mark.asyncio
async def test_close(client):
    """close() closes the underlying HTTP client."""
    await client.close()
    client._client.aclose.assert_called_once()
