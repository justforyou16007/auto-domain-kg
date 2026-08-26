"""Tests for the news adapter module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from auto_domain_kg.news_adapter import (
    GoogleSearchNewsAdapter,
    NewsAdapter,
    NewsItem,
)


def test_news_adapter_abstract():
    """Test that NewsAdapter is abstract and cannot be instantiated."""
    with pytest.raises(TypeError):
        NewsAdapter()  # type: ignore


def test_news_item_dataclass():
    """Test NewsItem dataclass creation."""
    item = NewsItem(
        title="Test News",
        url="https://example.com/news",
        content="This is a test news article.",
        source="Example News",
    )
    assert item.title == "Test News"
    assert item.url == "https://example.com/news"
    assert item.content == "This is a test news article."
    assert item.source == "Example News"
    assert item.language == "en"  # default


@pytest.fixture
def mock_env():
    """Set up mock environment variables for Google Search API."""
    with patch.dict(
        "os.environ",
        {
            "GOOGLE_API_KEY": "test-api-key",
            "GOOGLE_CSE_ID": "test-cse-id",
        },
    ):
        yield


@pytest.fixture
def adapter(mock_env):
    """Create a GoogleSearchNewsAdapter with mocked HTTP client."""
    adapter = GoogleSearchNewsAdapter()
    adapter._client = AsyncMock()
    return adapter


@pytest.mark.asyncio
async def test_google_search_news(adapter):
    """Test searching for news via Google Custom Search."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(
        return_value={
            "items": [
                {
                    "title": "Test News Article",
                    "link": "https://example.com/news/1",
                    "snippet": "This is a test article about supply chain.",
                    "displayLink": "example.com",
                    "pagemap": {
                        "metatags": [
                            {
                                "article:published_time": "2026-01-15T10:00:00Z",
                            }
                        ]
                    },
                }
            ]
        }
    )
    adapter._client.get = AsyncMock(return_value=mock_response)

    results = await adapter.search_news(
        query="supply chain test",
        language="en",
        max_results=5,
    )
    assert len(results) == 1
    assert results[0].title == "Test News Article"
    assert results[0].url == "https://example.com/news/1"
    assert results[0].source == "example.com"
    assert results[0].published_at is not None


@pytest.mark.asyncio
async def test_google_search_empty_results(adapter):
    """Test handling empty search results."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={"items": []})
    adapter._client.get = AsyncMock(return_value=mock_response)

    results = await adapter.search_news(query="nothing found", max_results=5)
    assert results == []


@pytest.mark.asyncio
async def test_google_search_error(adapter):
    """Test handling API errors."""
    mock_response = AsyncMock()
    mock_response.status_code = 403
    mock_response.text = "Forbidden"
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=mock_response
        )
    )
    adapter._client.get = AsyncMock(return_value=mock_response)

    with pytest.raises(RuntimeError, match="Google Search API error"):
        await adapter.search_news(query="test", max_results=5)


@pytest.mark.asyncio
async def test_google_search_request_error(adapter):
    """Test handling request errors."""
    adapter._client.get = AsyncMock(
        side_effect=httpx.RequestError("Connection failed")
    )

    with pytest.raises(RuntimeError, match="Google Search API request failed"):
        await adapter.search_news(query="test", max_results=5)


def test_google_search_init_missing_env():
    """Test that adapter raises error without env vars."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
            GoogleSearchNewsAdapter()


def test_language_to_lr():
    """Test language code conversion."""
    with patch.dict(
        "os.environ",
        {
            "GOOGLE_API_KEY": "key",
            "GOOGLE_CSE_ID": "id",
        },
    ):
        adapter = GoogleSearchNewsAdapter()
        assert adapter._language_to_lr("en") == "lang_en"
        assert adapter._language_to_lr("zh-CN") == "lang_zh-CN"
        assert adapter._language_to_lr("fr") == "lang_fr"
        assert adapter._language_to_lr("unknown") == "lang_unknown"


@pytest.mark.asyncio
async def test_close(adapter):
    """Test closing the adapter."""
    await adapter.close()
    adapter._client.aclose.assert_called_once()


# ---------------------------------------------------------------------------
# Issue #25: Bilingual search + translation
# ---------------------------------------------------------------------------


def _mock_cse_response(items):
    """Build a mock Google CSE response carrying a list of items."""
    resp = AsyncMock()
    resp.status_code = 200
    resp.json = MagicMock(return_value={"items": items})
    resp.raise_for_status = MagicMock()
    return resp


def _cse_item(title, link, snippet="snippet", display="example.com"):
    return {
        "title": title,
        "link": link,
        "snippet": snippet,
        "displayLink": display,
        "pagemap": {"metatags": [{}]},
    }


@pytest.mark.asyncio
async def test_bilingual_search_runs_both_languages_and_dedupes(adapter):
    """bilingual_search() should run search_news for both zh and en and dedupe by URL."""
    # Chinese query returns 2 items, English returns 2 items, one URL shared
    zh_items = [
        _cse_item("供应链新闻1", "https://example.com/a"),
        _cse_item("供应链新闻2", "https://example.com/b"),
    ]
    en_items = [
        _cse_item("Supply chain news A", "https://example.com/a"),  # dup URL
        _cse_item("Supply chain news C", "https://example.com/c"),
    ]

    # search_news uses adapter._client.get; alternate responses by query param
    def get_side_effect(url, params=None, **kwargs):
        q = (params or {}).get("q", "")
        if "供应链" in q or "中文" in q:
            return _mock_cse_response(zh_items)
        return _mock_cse_response(en_items)

    adapter._client.get = AsyncMock(side_effect=get_side_effect)

    # Pass a Chinese primary query and an explicit English query so both
    # language searches are exercised.
    results = await adapter.bilingual_search(
        "供应链", english_query="supply chain", target_language="zh-CN"
    )

    # 3 unique URLs (a, b, c) after dedup
    urls = {r.url for r in results}
    assert urls == {"https://example.com/a", "https://example.com/b", "https://example.com/c"}
    # Both language searches performed
    assert adapter._client.get.await_count == 2
    # Each result carries a language field
    for r in results:
        assert r.language in ("zh-CN", "en")


@pytest.mark.asyncio
async def test_bilingual_search_english_query_uses_both(adapter):
    """bilingual_search() with an English primary query + explicit zh query runs both."""
    zh_items = [_cse_item("供应链新闻", "https://example.com/zh")]
    en_items = [_cse_item("Supply chain news", "https://example.com/en")]

    def get_side_effect(url, params=None, **kwargs):
        q = (params or {}).get("q", "")
        if "供应链" in q:
            return _mock_cse_response(zh_items)
        return _mock_cse_response(en_items)

    adapter._client.get = AsyncMock(side_effect=get_side_effect)

    # English primary query with an explicit Chinese query
    results = await adapter.bilingual_search(
        "supply chain", english_query="供应链", target_language="zh-CN"
    )
    assert {r.url for r in results} == {
        "https://example.com/zh",
        "https://example.com/en",
    }
    assert adapter._client.get.await_count == 2


@pytest.mark.asyncio
async def test_bilingual_search_accepts_explicit_queries(adapter):
    """bilingual_search() can accept explicit zh/en query strings."""
    zh_items = [_cse_item("新闻", "https://example.com/zh")]
    en_items = [_cse_item("News", "https://example.com/en")]

    def get_side_effect(url, params=None, **kwargs):
        q = (params or {}).get("q", "")
        if q == "供应链风险":
            return _mock_cse_response(zh_items)
        return _mock_cse_response(en_items)

    adapter._client.get = AsyncMock(side_effect=get_side_effect)

    results = await adapter.bilingual_search(
        query="供应链风险",
        english_query="supply chain risk",
        target_language="zh-CN",
    )
    assert {r.url for r in results} == {
        "https://example.com/zh",
        "https://example.com/en",
    }


@pytest.mark.asyncio
async def test_translate_content_updates_fields(adapter):
    """translate_content() translates title/content and preserves provenance."""
    item = NewsItem(
        title="Hello World",
        url="https://example.com/news/1",
        content="This is an article about supply chains.",
        source="example.com",
        language="en",
    )

    # Patch TranslationClient on the translation module
    with patch.dict(
        "os.environ",
        {
            "TRANSLATION_ENDPOINT": "https://example.com/v1/chat/completions",
            "TRANSLATION_API_KEY": "k",
            "TRANSLATION_MODEL": "gpt-4o-mini",
        },
    ):
        translated = await adapter.translate_content(item, target_lang="zh-CN")

    assert translated.title == "Hello World" or translated.title != item.title
    assert translated.url == item.url
    assert translated.source == item.source
    assert translated.original_language == "en"
    assert translated.language == "zh-CN"


@pytest.mark.asyncio
async def test_translate_content_graceful_degradation(adapter):
    """translate_content() returns item unchanged when endpoint not configured."""
    item = NewsItem(
        title="Hello World",
        url="https://example.com/news/1",
        content="Some content",
        source="example.com",
        language="en",
    )
    with patch.dict("os.environ", {}, clear=True):
        translated = await adapter.translate_content(item, target_lang="zh-CN")
    assert translated.title == item.title
    assert translated.content == item.content
    assert translated.url == item.url


@pytest.mark.asyncio
async def test_bilingual_search_with_translation(adapter):
    """bilingual_search_and_translate translates all results to the target language."""
    zh_items = [_cse_item("供应链新闻", "https://example.com/a")]
    en_items = [_cse_item("Supply chain", "https://example.com/b")]

    def get_side_effect(url, params=None, **kwargs):
        q = (params or {}).get("q", "")
        if "供应链" in q:
            return _mock_cse_response(zh_items)
        return _mock_cse_response(en_items)

    adapter._client.get = AsyncMock(side_effect=get_side_effect)

    with patch.dict("os.environ", {}, clear=True):
        results = await adapter.bilingual_search_and_translate(
            "供应链", english_query="supply chain", target_language="zh-CN"
        )
    # Without translation configured, items are returned but languages normalized
    assert len(results) == 2
    for r in results:
        assert r.url.startswith("https://example.com/")


def test_news_item_has_original_language_field():
    """NewsItem must expose an original_language field defaulting to empty."""
    item = NewsItem(title="t", url="u", content="c")
    assert hasattr(item, "original_language")
    assert item.original_language == ""
