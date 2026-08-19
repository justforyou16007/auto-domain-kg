"""External API embedding client (OpenAI-compatible / vLLM API).

Provides configurable embedding generation via external HTTP APIs,
batch embedding support, and caching to avoid re-embedding.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx


@dataclass
class EmbeddingConfig:
    """Embedding configuration from environment variables."""

    endpoint: str = field(
        default_factory=lambda: os.environ.get(
            "EMBEDDING_ENDPOINT", "http://localhost:8000/v1/embeddings"
        )
    )
    model: str = field(
        default_factory=lambda: os.environ.get(
            "EMBEDDING_MODEL", "BAAI/bge-m3"
        )
    )
    dimensions: int = int(
        os.environ.get("EMBEDDING_DIMENSIONS", "768")
    )
    api_key: str = field(
        default_factory=lambda: os.environ.get("EMBEDDING_API_KEY", "")
    )
    cache_dir: str = field(
        default_factory=lambda: os.environ.get(
            "EMBEDDING_CACHE_DIR", str(Path("tmp") / "embedding_cache")
        )
    )


class EmbeddingClient:
    """Client for generating embeddings via an external API.

    Supports OpenAI-compatible / vLLM API endpoints. Provides caching
    to avoid re-embedding the same text.
    """

    def __init__(self, config: Optional[EmbeddingConfig] = None) -> None:
        """Initialize the embedding client.

        Args:
            config: Embedding configuration. If None, reads from env vars.
        """
        self._config = config or EmbeddingConfig()
        self._cache: dict[str, list[float]] = {}
        self._cache_dir = Path(self._config.cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._load_cache()
        self._client = httpx.AsyncClient(timeout=60.0)

    def _cache_path(self) -> Path:
        """Get the cache file path."""
        # Use a safe filename from the model name
        model_slug = self._config.model.replace("/", "_").replace(":", "_")
        return self._cache_dir / f"{model_slug}.json"

    def _load_cache(self) -> None:
        """Load the embedding cache from disk."""
        cache_file = self._cache_path()
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                self._cache = {k: v for k, v in data.items()}
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    def _save_cache(self) -> None:
        """Save the embedding cache to disk."""
        cache_file = self._cache_path()
        try:
            cache_file.write_text(json.dumps(self._cache, ensure_ascii=False))
        except OSError:
            pass  # Silently fail if cache can't be written

    def _make_cache_key(self, text: str) -> str:
        """Create a cache key for a text string."""
        return text.strip().lower()

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Input text to embed.

        Returns:
            Embedding vector as a list of floats.
        """
        cache_key = self._make_cache_key(text)
        if cache_key in self._cache:
            return self._cache[cache_key]

        vector = await self._embed_batch([text])
        if vector:
            self._cache[cache_key] = vector[0]
            self._save_cache()
            return vector[0]
        return []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Checks cache first, then embeds any uncached texts.

        Args:
            texts: List of input texts to embed.

        Returns:
            List of embedding vectors corresponding to each input text.
        """
        results: list[Optional[list[float]]] = [None] * len(texts)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        for i, text in enumerate(texts):
            cache_key = self._make_cache_key(text)
            if cache_key in self._cache:
                results[i] = self._cache[cache_key]
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        if uncached_texts:
            vectors = await self._embed_batch(uncached_texts)
            for idx, vector in zip(uncached_indices, vectors):
                if vector:
                    cache_key = self._make_cache_key(texts[idx])
                    self._cache[cache_key] = vector
                    results[idx] = vector
                else:
                    results[idx] = []

            self._save_cache()

        return [r or [] for r in results]

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Send a batch embedding request to the API.

        Args:
            texts: Texts to embed.

        Returns:
            List of embedding vectors.

        Raises:
            RuntimeError: If the API request fails.
        """
        if not texts:
            return []

        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        payload = {
            "input": texts,
            "model": self._config.model,
        }

        try:
            response = await self._client.post(
                self._config.endpoint,
                headers=headers,
                content=json.dumps(payload),
            )
            response.raise_for_status()
            data = response.json()

            # Sort by index to maintain order
            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in sorted_data]

        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Embedding API error: {e.response.status_code} - {e.response.text}"
            )
        except httpx.RequestError as e:
            raise RuntimeError(f"Embedding API request failed: {e}")
        except (KeyError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Invalid embedding API response: {e}")

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()