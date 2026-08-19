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