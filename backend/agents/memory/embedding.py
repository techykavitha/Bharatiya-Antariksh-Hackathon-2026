"""Pluggable embedding providers for vector memory."""

from __future__ import annotations

import hashlib
import math
from typing import Any, Protocol, runtime_checkable

from backend.config.settings import EmbeddingConfig, GlobalConfig, get_config


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for text embedding generation."""

    @property
    def dimension(self) -> int:
        """Return the embedding vector dimension."""

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string."""

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple text strings."""


class DeterministicEmbeddingProvider:
    """
    Deterministic local embedding provider for development and testing.

    Produces unit-normalized vectors from SHA-256 hashes. Consistent
    across runs without external API dependencies.
    """

    def __init__(self, dimension: int = 1536) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, text: str) -> list[float]:
        return self._hash_to_vector(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_to_vector(t) for t in texts]

    def _hash_to_vector(self, text: str) -> list[float]:
        """Token-hashed bag-of-words embedding for consistent cross-text similarity."""
        tokens = text.lower().split()
        if not tokens:
            return self._hash_bytes_to_vector(hashlib.sha256(b"").digest())

        values = [0.0] * self._dimension
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for byte_idx, byte in enumerate(digest):
                index = (byte + byte_idx) % self._dimension
                values[index] += (byte / 255.0) * 2.0 - 1.0

        magnitude = math.sqrt(sum(v * v for v in values))
        if magnitude == 0:
            return self._hash_bytes_to_vector(hashlib.sha256(text.encode("utf-8")).digest())
        return [v / magnitude for v in values]

    def _hash_bytes_to_vector(self, digest: bytes) -> list[float]:
        values: list[float] = []
        while len(values) < self._dimension:
            for byte in digest:
                values.append((byte / 255.0) * 2.0 - 1.0)
                if len(values) >= self._dimension:
                    break
            digest = hashlib.sha256(digest).digest()
        magnitude = math.sqrt(sum(v * v for v in values))
        if magnitude == 0:
            return values
        return [v / magnitude for v in values]


class ConfigurableEmbeddingProvider:
    """
    Embedding provider that selects implementation based on configuration.

    Uses OpenAI embeddings when an API key is available; otherwise falls
    back to deterministic local embeddings.
    """

    def __init__(
        self,
        config: EmbeddingConfig | None = None,
        *,
        fallback: EmbeddingProvider | None = None,
    ) -> None:
        cfg = config or get_config().embedding
        self._config = cfg
        self._fallback: EmbeddingProvider = fallback or DeterministicEmbeddingProvider(
            dimension=cfg.dimension,
        )
        self._openai_provider: EmbeddingProvider | None = None
        self._init_openai_if_available()

    def _init_openai_if_available(self) -> None:
        global_config = get_config()
        api_key = global_config.llm.api_key
        if api_key is None:
            return
        try:
            from langchain_openai import OpenAIEmbeddings

            embeddings = OpenAIEmbeddings(
                model=self._config.model_name,
                api_key=api_key.get_secret_value(),
            )
            self._openai_provider = _LangChainEmbeddingAdapter(
                embeddings,
                dimension=self._config.dimension,
            )
        except ImportError:
            pass

    @property
    def dimension(self) -> int:
        return self._config.dimension

    @property
    def _provider(self) -> EmbeddingProvider:
        return self._openai_provider or self._fallback

    async def embed(self, text: str) -> list[float]:
        return await self._provider.embed(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return await self._provider.embed_batch(texts)


class _LangChainEmbeddingAdapter:
    """Adapter wrapping LangChain embeddings to the EmbeddingProvider protocol."""

    def __init__(self, embeddings: Any, *, dimension: int) -> None:
        self._embeddings = embeddings
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, text: str) -> list[float]:
        import asyncio

        vector = await asyncio.to_thread(self._embeddings.embed_query, text)
        return list(vector)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import asyncio

        vectors = await asyncio.to_thread(self._embeddings.embed_documents, texts)
        return [list(v) for v in vectors]


def create_embedding_provider(config: GlobalConfig | None = None) -> EmbeddingProvider:
    """Factory for the default embedding provider."""
    if config is not None:
        return ConfigurableEmbeddingProvider(config.embedding)
    return ConfigurableEmbeddingProvider()
