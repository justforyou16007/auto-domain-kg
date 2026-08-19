"""Tests for the embedding module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from auto_domain_kg.embedding import EmbeddingClient, EmbeddingConfig


@pytest.fixture
def config():
    """Create a test embedding config."""
    return EmbeddingConfig(
        endpoint="http://test:8000/v1/embeddings",
        model="test-model",
        dimensions=4,
        api_key="",
        cache_dir="/tmp/test_embedding_cache",
    )


@pytest.fixture
def client(config):
    """Create an EmbeddingClient with a mocked HTTP client."""
    with patch("auto_domain_kg.embedding.Path.mkdir"):
        with patch("auto_domain_kg.embedding.Path.exists", return_value=False):
            c = EmbeddingClient(config)
            c._client = AsyncMock()
            return c


@pytest.mark.asyncio
async def test_embed_single(client):
    """Test embedding a single text."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(
        return_value={
            "data": [
                {"index": 0, "embedding": [0.1, 0.2, 0.3, 0.4]},
            ]
        }
    )
    client._client.post = AsyncMock(return_value=mock_response)

    result = await client.embed("test text")
    assert result == [0.1, 0.2, 0.3, 0.4]


@pytest.mark.asyncio
async def test_embed_batch(client):
    """Test embedding a batch of texts."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(
        return_value={
            "data": [
                {"index": 0, "embedding": [0.1, 0.0, 0.0, 0.0]},
                {"index": 1, "embedding": [0.0, 0.2, 0.0, 0.0]},
            ]
        }
    )
    client._client.post = AsyncMock(return_value=mock_response)

    results = await client.embed_batch(["text one", "text two"])
    assert len(results) == 2
    assert results[0] == [0.1, 0.0, 0.0, 0.0]
    assert results[1] == [0.0, 0.2, 0.0, 0.0]


@pytest.mark.asyncio
async def test_embed_caching(client):
    """Test that embedding results are cached."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(
        return_value={
            "data": [
                {"index": 0, "embedding": [0.1, 0.2, 0.3, 0.4]},
            ]
        }
    )
    client._client.post = AsyncMock(return_value=mock_response)

    # First call should hit the API
    result1 = await client.embed("test text")
    assert result1 == [0.1, 0.2, 0.3, 0.4]
    assert client._client.post.call_count == 1

    # Second call should use cache
    result2 = await client.embed("test text")
    assert result2 == [0.1, 0.2, 0.3, 0.4]
    assert client._client.post.call_count == 1  # No additional API call


@pytest.mark.asyncio
async def test_embed_api_error(client):
    """Test that API errors are properly raised."""
    mock_response = AsyncMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=mock_response
        )
    )
    client._client.post = AsyncMock(return_value=mock_response)

    with pytest.raises(RuntimeError, match="Embedding API error"):
        await client.embed("test text")


@pytest.mark.asyncio
async def test_embed_request_error(client):
    """Test that request errors are properly raised."""
    client._client.post = AsyncMock(
        side_effect=httpx.RequestError("Connection failed")
    )

    with pytest.raises(RuntimeError, match="Embedding API request failed"):
        await client.embed("test text")


@pytest.mark.asyncio
async def test_embed_empty_batch(client):
    """Test embedding an empty batch."""
    results = await client.embed_batch([])
    assert results == []


@pytest.mark.asyncio
async def test_close(client):
    """Test closing the client."""
    await client.close()
    client._client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_config_defaults():
    """Test default config values."""
    with patch.dict("os.environ", {}, clear=True):
        config = EmbeddingConfig()
        assert config.endpoint == "http://localhost:8000/v1/embeddings"
        assert config.model == "BAAI/bge-m3"
        assert config.dimensions == 768
        assert config.api_key == ""