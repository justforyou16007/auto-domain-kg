"""Tests for the info_extraction module.

The ``InfoExtractionClient`` supports two modes:
1. Generic API mode — send text to a general-purpose LLM endpoint and get
   structured entity-relation extraction back.
2. Dedicated extraction API mode — send text to a specialized
   entity-relation extraction endpoint.

It also doubles as a translation API client (reusing the same endpoint
infrastructure). All network access is mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from auto_domain_kg.info_extraction import (
    ExtractionConfig,
    InfoExtractionClient,
    ExtractionError,
)


def _mock_openai_response(content: str) -> MagicMock:
    """Build a mock httpx response carrying an OpenAI chat completion payload."""
    payload = {
        "choices": [
            {"message": {"role": "assistant", "content": content}, "index": 0}
        ]
    }
    resp = MagicMock()
    resp.status_code = 200
    resp.json = MagicMock(return_value=payload)
    resp.raise_for_status = MagicMock()
    return resp


def _mock_dedicated_response(entities: list, relations: list) -> MagicMock:
    """Build a mock httpx response for the dedicated extraction endpoint."""
    payload = {"entities": entities, "relations": relations}
    resp = MagicMock()
    resp.status_code = 200
    resp.json = MagicMock(return_value=payload)
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def test_extraction_config_reads_env():
    """ExtractionConfig reads EXTRACTION_* env vars with sensible defaults."""
    with patch.dict(
        "os.environ",
        {
            "EXTRACTION_ENDPOINT": "https://example.com/v1/chat/completions",
            "EXTRACTION_API_KEY": "sk-extr",
            "EXTRACTION_MODEL": "gpt-4o",
            "TRANSLATION_ENDPOINT": "https://example.com/v1/translate",
            "TRANSLATION_API_KEY": "sk-trans",
            "TRANSLATION_MODEL": "gpt-4o-mini",
        },
        clear=True,
    ):
        cfg = ExtractionConfig()
        assert cfg.extraction_endpoint == "https://example.com/v1/chat/completions"
        assert cfg.extraction_api_key == "sk-extr"
        assert cfg.extraction_model == "gpt-4o"
        # Translation config reuses TRANSLATION_* env vars.
        assert cfg.translation_endpoint == "https://example.com/v1/translate"
        assert cfg.translation_api_key == "sk-trans"
        assert cfg.translation_model == "gpt-4o-mini"


def test_extraction_config_defaults():
    """ExtractionConfig defaults are empty strings (graceful degradation)."""
    with patch.dict("os.environ", {}, clear=True):
        cfg = ExtractionConfig()
        assert cfg.extraction_endpoint == ""
        assert cfg.extraction_api_key == ""
        assert cfg.extraction_model == "gpt-4o"
        assert cfg.translation_endpoint == ""
        assert cfg.translation_api_key == ""
        assert cfg.translation_model == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# Availability checks
# ---------------------------------------------------------------------------


def test_is_available_true_when_extraction_configured():
    with patch.dict(
        "os.environ",
        {"EXTRACTION_ENDPOINT": "https://example.com/v1/chat/completions"},
        clear=True,
    ):
        client = InfoExtractionClient()
        assert client.is_extraction_available() is True


def test_is_available_false_when_not_configured():
    with patch.dict("os.environ", {}, clear=True):
        client = InfoExtractionClient()
        assert client.is_extraction_available() is False


def test_translation_available_when_translation_configured():
    with patch.dict(
        "os.environ",
        {"TRANSLATION_ENDPOINT": "https://example.com/v1/translate"},
        clear=True,
    ):
        client = InfoExtractionClient()
        assert client.is_translation_available() is True


def test_dedicated_mode_available_when_dedicated_endpoint_configured():
    """Dedicated extraction endpoint is inferred from EXTRACTION_ENDPOINT when it
    is not a chat-completions URL."""
    with patch.dict(
        "os.environ",
        {"EXTRACTION_ENDPOINT": "https://example.com/v1/extract"},
        clear=True,
    ):
        client = InfoExtractionClient()
        assert client.is_dedicated_available() is True


# ---------------------------------------------------------------------------
# Generic API extraction mode
# ---------------------------------------------------------------------------


@pytest.fixture
def extraction_env():
    with patch.dict(
        "os.environ",
        {
            "EXTRACTION_ENDPOINT": "https://example.com/v1/chat/completions",
            "EXTRACTION_API_KEY": "sk-extr",
            "EXTRACTION_MODEL": "gpt-4o",
        },
    ):
        yield


@pytest.fixture
def client(extraction_env):
    c = InfoExtractionClient()
    c._client = AsyncMock()
    return c


@pytest.mark.asyncio
async def test_extract_generic_parses_entities_and_relations(client):
    """extract() in generic mode returns parsed entities and relations from the
    LLM's JSON response."""
    llm_json = (
        '{"entities": [{"name": "TSMC", "type": "Supplier"}], '
        '"relations": [{"subject": "TSMC", "predicate": "SUPPLIES", '
        '"object": "Silicon Wafers"}]}'
    )
    client._client.post = AsyncMock(return_value=_mock_openai_response(llm_json))

    result = await client.extract("Apple contracts with TSMC to make chips.")

    assert "entities" in result
    assert result["entities"][0]["name"] == "TSMC"
    assert result["relations"][0]["predicate"] == "SUPPLIES"
    client._client.post.assert_awaited()


@pytest.mark.asyncio
async def test_extract_generic_caches_results(client):
    """extract() caches identical text so the API is only hit once."""
    llm_json = '{"entities": [], "relations": []}'
    client._client.post = AsyncMock(return_value=_mock_openai_response(llm_json))

    await client.extract("some text")
    await client.extract("some text")

    assert client._client.post.await_count == 1


@pytest.mark.asyncio
async def test_extract_generic_graceful_degradation():
    """extract() returns empty structure when no endpoint is configured."""
    with patch.dict("os.environ", {}, clear=True):
        c = InfoExtractionClient()
    result = await c.extract("some text")
    assert result == {"entities": [], "relations": []}


@pytest.mark.asyncio
async def test_extract_generic_handles_malformed_json(client):
    """extract() raises ExtractionError when the LLM returns invalid JSON after
    exhausting repair attempts."""
    client._client.post = AsyncMock(
        return_value=_mock_openai_response("not json at all")
    )
    with pytest.raises(ExtractionError):
        await client.extract("some text")


# ---------------------------------------------------------------------------
# Dedicated extraction API mode
# ---------------------------------------------------------------------------


@pytest.fixture
def dedicated_env():
    with patch.dict(
        "os.environ",
        {
            "EXTRACTION_ENDPOINT": "https://example.com/v1/extract",
            "EXTRACTION_API_KEY": "sk-extr",
            "EXTRACTION_MODEL": "gpt-4o",
        },
        clear=True,
    ):
        yield


@pytest.fixture
def dedicated_client(dedicated_env):
    c = InfoExtractionClient()
    c._client = AsyncMock()
    return c


@pytest.mark.asyncio
async def test_extract_dedicated_returns_structured(dedicated_client):
    """extract_dedicated() returns the dedicated endpoint's structured payload."""
    entities = [{"name": "TSMC", "type": "Supplier"}]
    relations = [
        {"subject": "TSMC", "predicate": "SUPPLIES", "object": "Silicon Wafers"}
    ]
    dedicated_client._client.post = AsyncMock(
        return_value=_mock_dedicated_response(entities, relations)
    )

    result = await dedicated_client.extract_dedicated("some text")

    assert result["entities"] == entities
    assert result["relations"] == relations


@pytest.mark.asyncio
async def test_extract_dedicated_graceful_degradation():
    """extract_dedicated() returns empty structure when no endpoint configured."""
    with patch.dict("os.environ", {}, clear=True):
        c = InfoExtractionClient()
    result = await c.extract_dedicated("some text")
    assert result == {"entities": [], "relations": []}


@pytest.mark.asyncio
async def test_extract_dedicated_raises_on_http_error(dedicated_client):
    """extract_dedicated() raises ExtractionError on a non-2xx HTTP response."""
    import httpx

    bad = MagicMock()
    bad.status_code = 500
    bad.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError(
        "err", request=MagicMock(), response=bad
    ))
    dedicated_client._client.post = AsyncMock(return_value=bad)
    with pytest.raises(ExtractionError):
        await dedicated_client.extract_dedicated("some text")


# ---------------------------------------------------------------------------
# Translation (dual-purpose client)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_translate_uses_translation_config():
    """translate() reuses the TRANSLATION_* endpoint config."""
    with patch.dict(
        "os.environ",
        {
            "TRANSLATION_ENDPOINT": "https://example.com/v1/translate",
            "TRANSLATION_API_KEY": "sk-trans",
            "TRANSLATION_MODEL": "gpt-4o-mini",
        },
        clear=True,
    ):
        c = InfoExtractionClient()
        c._client = AsyncMock()
        c._client.post = AsyncMock(return_value=_mock_openai_response("翻译文本"))

        result = await c.translate("Hello", source_lang="en", target_lang="zh-CN")
        assert result == "翻译文本"

        call = c._client.post.call_args
        assert "example.com/v1/translate" in call.args[0]


@pytest.mark.asyncio
async def test_translate_graceful_degradation():
    """translate() returns original text when no endpoint configured."""
    with patch.dict("os.environ", {}, clear=True):
        c = InfoExtractionClient()
    result = await c.translate("Hello", source_lang="en", target_lang="zh-CN")
    assert result == "Hello"


@pytest.mark.asyncio
async def test_translate_caches(dedicated_client):
    """translate() caches repeated identical requests."""
    with patch.dict(
        "os.environ",
        {
            "EXTRACTION_ENDPOINT": "https://example.com/v1/extract",
            "TRANSLATION_ENDPOINT": "https://example.com/v1/translate",
            "TRANSLATION_API_KEY": "sk-trans",
        },
        clear=True,
    ):
        c = InfoExtractionClient()
        c._client = AsyncMock()
        c._client.post = AsyncMock(return_value=_mock_openai_response("译文"))

        await c.translate("Hello", source_lang="en", target_lang="zh-CN")
        await c.translate("Hello", source_lang="en", target_lang="zh-CN")

        assert c._client.post.await_count == 1


# ---------------------------------------------------------------------------
# Error handling / lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_generic_raises_on_request_error(client):
    """extract() raises ExtractionError on a transport-level request error."""
    import httpx

    client._client.post = AsyncMock(side_effect=httpx.RequestError("boom"))
    with pytest.raises(ExtractionError):
        await client.extract("some text")


@pytest.mark.asyncio
async def test_close(client):
    """close() closes the underlying HTTP client."""
    await client.close()
    client._client.aclose.assert_called_once()
