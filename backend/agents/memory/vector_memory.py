"""Qdrant-backed vector memory for semantic retrieval."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Protocol, runtime_checkable

from backend.agents.memory.embedding import DeterministicEmbeddingProvider, EmbeddingProvider
from backend.agents.memory.interfaces import MemoryEntry, VectorMemory
from backend.agents.memory.memory_cache import AsyncLRUMemoryCache
from backend.agents.memory.memory_types import VectorDocumentType
from backend.agents.memory.serialization import pydantic_to_dict
from backend.config.settings import QdrantConfig, get_config
from backend.utils.constants import (
    QDRANT_COLLECTION_CLIMATE,
    QDRANT_COLLECTION_DOCUMENTS,
    QDRANT_COLLECTION_FORECASTS,
    VECTOR_SEARCH_TOP_K,
)
from backend.utils.errors import MemoryNotFoundError, MemoryReadError, MemoryWriteError


@runtime_checkable
class QdrantClientProtocol(Protocol):
    """Minimal async Qdrant client protocol."""

    async def get_collections(self) -> Any: ...
    async def create_collection(self, collection_name: str, **kwargs: Any) -> Any: ...
    async def collection_exists(self, collection_name: str) -> bool: ...
    async def upsert(self, collection_name: str, points: list[Any]) -> Any: ...
    async def retrieve(self, collection_name: str, ids: list[Any], **kwargs: Any) -> list[Any]: ...
    async def delete(self, collection_name: str, points_selector: Any) -> Any: ...
    async def search(self, collection_name: str, query_vector: list[float], **kwargs: Any) -> list[Any]: ...
    async def scroll(self, collection_name: str, **kwargs: Any) -> tuple[list[Any], Any]: ...


class InMemoryQdrantClient:
    """
    In-memory Qdrant-compatible client for unit tests.

    Supports upsert, search, delete, metadata filtering, and hybrid keyword scoring.
    """

    def __init__(self, *, vector_size: int = 1536) -> None:
        self._vector_size = vector_size
        self._collections: dict[str, dict[str, dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    async def get_collections(self) -> Any:
        return type("Collections", (), {"collections": [{"name": n} for n in self._collections]})()

    async def create_collection(self, collection_name: str, **kwargs: Any) -> bool:
        async with self._lock:
            self._collections.setdefault(collection_name, {})
            return True

    async def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self._collections

    async def upsert(self, collection_name: str, points: list[Any]) -> bool:
        async with self._lock:
            bucket = self._collections.setdefault(collection_name, {})
            for point in points:
                pid = str(point.id)
                bucket[pid] = {
                    "id": pid,
                    "vector": list(point.vector),
                    "payload": dict(point.payload or {}),
                }
            return True

    async def retrieve(self, collection_name: str, ids: list[Any], **kwargs: Any) -> list[Any]:
        bucket = self._collections.get(collection_name, {})
        results = []
        for pid in ids:
            record = bucket.get(str(pid))
            if record:
                results.append(type("Record", (), record)())
        return results

    async def delete(self, collection_name: str, points_selector: Any) -> bool:
        async with self._lock:
            bucket = self._collections.get(collection_name, {})
            for pid in points_selector.points:
                bucket.pop(str(pid), None)
            return True

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        *,
        limit: int = 10,
        query_filter: Any = None,
        score_threshold: float | None = None,
        **kwargs: Any,
    ) -> list[Any]:
        bucket = self._collections.get(collection_name, {})
        scored: list[tuple[float, dict[str, Any]]] = []
        for record in bucket.values():
            if query_filter is not None and not self._matches_filter(record["payload"], query_filter):
                continue
            score = _cosine_similarity(query_vector, record["vector"])
            if score_threshold is not None and score < score_threshold:
                continue
            scored.append((score, record))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            type("ScoredPoint", (), {"id": rec["id"], "score": score, "payload": rec["payload"]})()
            for score, rec in scored[:limit]
        ]

    async def scroll(self, collection_name: str, *, limit: int = 100, **kwargs: Any) -> tuple[list[Any], Any]:
        bucket = self._collections.get(collection_name, {})
        records = list(bucket.values())[:limit]
        points = [
            type("Record", (), {"id": r["id"], "payload": r["payload"], "vector": r["vector"]})()
            for r in records
        ]
        return points, None

    def _matches_filter(self, payload: dict[str, Any], query_filter: Any) -> bool:
        if query_filter is None:
            return True
        must = getattr(query_filter, "must", None) or []
        for condition in must:
            key = getattr(getattr(condition, "key", None), "key", None) or getattr(condition, "key", None)
            match = getattr(condition, "match", None)
            if key and match:
                value = getattr(match, "value", None)
                if payload.get(key) != value:
                    return False
        return True


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class QdrantVectorMemory(VectorMemory):
    """
    Production vector memory using Qdrant for semantic and hybrid search.

    Stores embeddings for historical events, simulations, forecasts, policy
    reports, research documents, and disaster history.
    """

    DEFAULT_COLLECTIONS = (
        QDRANT_COLLECTION_CLIMATE,
        QDRANT_COLLECTION_DOCUMENTS,
        QDRANT_COLLECTION_FORECASTS,
    )

    def __init__(
        self,
        client: QdrantClientProtocol,
        *,
        config: QdrantConfig | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        default_collection: str = QDRANT_COLLECTION_DOCUMENTS,
        cache: AsyncLRUMemoryCache[MemoryEntry] | None = None,
    ) -> None:
        self._client = client
        self._config = config or get_config().qdrant
        self._embedding = embedding_provider or DeterministicEmbeddingProvider(
            dimension=get_config().embedding.dimension,
        )
        self._default_collection = default_collection
        self._cache = cache or AsyncLRUMemoryCache[MemoryEntry](max_size=1024)
        self._lock = asyncio.Lock()
        self._collection_map = {
            VectorDocumentType.HISTORICAL_EVENT: self._config.collection_climate,
            VectorDocumentType.PREVIOUS_SIMULATION: self._config.collection_climate,
            VectorDocumentType.FORECAST_SUMMARY: self._config.collection_forecasts,
            VectorDocumentType.POLICY_REPORT: self._config.collection_documents,
            VectorDocumentType.RESEARCH_DOCUMENT: self._config.collection_documents,
            VectorDocumentType.DISASTER_HISTORY: self._config.collection_climate,
            VectorDocumentType.CLIMATE_OBSERVATION: self._config.collection_climate,
            VectorDocumentType.EMBEDDING: self._config.collection_documents,
        }

    @property
    def backend_name(self) -> str:
        return "vector"

    def _resolve_collection(self, collection: str | None, metadata: dict[str, Any] | None = None) -> str:
        if collection:
            return collection
        if metadata:
            doc_type = metadata.get("document_type")
            if doc_type:
                try:
                    return self._collection_map[VectorDocumentType(doc_type)]
                except ValueError:
                    pass
        return self._default_collection

    async def ensure_collections(self) -> None:
        """Create default collections if they do not exist."""
        from qdrant_client.models import Distance, VectorParams

        for name in self.DEFAULT_COLLECTIONS:
            if not await self._client.collection_exists(name):
                await self._client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=self._embedding.dimension,
                        distance=Distance.COSINE,
                    ),
                )

    async def write(
        self,
        key: str,
        value: Any,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        meta = dict(metadata or {})
        text = meta.get("text") or (value if isinstance(value, str) else str(value))
        meta.pop("value", None)
        meta.pop("embedding", None)
        embedding = (metadata or {}).get("embedding")
        if embedding is None:
            embedding = await self._embedding.embed(text)
        payload = {
            "key": key,
            "value": pydantic_to_dict(value),
            "text": text,
            **meta,
        }
        await self.upsert_embedding(key, embedding, payload)

    async def read(self, key: str) -> MemoryEntry | None:
        cached = await self._cache.get(key)
        if cached:
            return cached
        for collection in self.DEFAULT_COLLECTIONS:
            try:
                points = await self._client.retrieve(collection, [key], with_payload=True)
                if points:
                    payload = points[0].payload or {}
                    entry = MemoryEntry(key=key, value=payload.get("value"), metadata=payload)
                    await self._cache.set(key, entry)
                    return entry
            except Exception:
                continue
        return None

    async def delete(self, key: str) -> bool:
        from qdrant_client.models import PointIdsList

        deleted = False
        for collection in self.DEFAULT_COLLECTIONS:
            try:
                await self._client.delete(collection, PointIdsList(points=[key]))
                deleted = True
            except Exception:
                continue
        await self._cache.delete(key)
        return deleted

    async def search(
        self,
        query: str,
        *,
        limit: int = VECTOR_SEARCH_TOP_K,
        filters: dict[str, Any] | None = None,
        collection: str | None = None,
    ) -> list[MemoryEntry]:
        """Semantic search using query text embedding."""
        embedding = await self._embedding.embed(query)
        if collection:
            return await self.similarity_search(
                embedding,
                limit=limit,
                collection=collection,
                filters=filters,
                query_text=query,
            )
        all_results: list[MemoryEntry] = []
        per_collection = max(limit, 5)
        for coll in self.DEFAULT_COLLECTIONS:
            results = await self.similarity_search(
                embedding,
                limit=per_collection,
                collection=coll,
                filters=filters,
                query_text=query,
            )
            all_results.extend(results)
        all_results.sort(key=lambda e: e.score or 0.0, reverse=True)
        return all_results[:limit]

    async def clear(self, namespace: str | None = None) -> int:
        collection = namespace or self._default_collection
        points, _ = await self._client.scroll(collection, limit=10_000)
        if not points:
            return 0
        from qdrant_client.models import PointIdsList

        ids = [p.id for p in points]
        await self._client.delete(collection, PointIdsList(points=ids))
        return len(ids)

    async def upsert_embedding(
        self,
        key: str,
        embedding: list[float],
        payload: dict[str, Any],
    ) -> None:
        from qdrant_client.models import PointStruct

        collection = self._resolve_collection(payload.get("collection"), payload)
        point = PointStruct(id=key, vector=embedding, payload=payload)
        try:
            async with self._lock:
                await self._client.upsert(collection_name=collection, points=[point])
            entry = MemoryEntry(key=key, value=payload.get("value"), metadata=payload)
            await self._cache.set(key, entry)
        except Exception as exc:
            raise MemoryWriteError(
                f"Failed to upsert vector '{key}': {exc}",
                details={"key": key, "collection": collection},
            ) from exc

    async def similarity_search(
        self,
        embedding: list[float],
        *,
        limit: int = VECTOR_SEARCH_TOP_K,
        collection: str | None = None,
        filters: dict[str, Any] | None = None,
        query_text: str | None = None,
    ) -> list[MemoryEntry]:
        if collection:
            return await self._similarity_search_collection(
                embedding,
                limit=limit,
                collection=collection,
                filters=filters,
                query_text=query_text,
            )
        all_results: list[MemoryEntry] = []
        per_collection = max(limit, 5)
        for coll in self.DEFAULT_COLLECTIONS:
            results = await self._similarity_search_collection(
                embedding,
                limit=per_collection,
                collection=coll,
                filters=filters,
                query_text=query_text,
            )
            all_results.extend(results)
        all_results.sort(key=lambda e: e.score or 0.0, reverse=True)
        return all_results[:limit]

    async def _similarity_search_collection(
        self,
        embedding: list[float],
        *,
        limit: int,
        collection: str,
        filters: dict[str, Any] | None = None,
        query_text: str | None = None,
    ) -> list[MemoryEntry]:
        target = collection
        qdrant_filter = self._build_filter(filters) if filters else None
        try:
            results = await self._client.search(
                collection_name=target,
                query_vector=embedding,
                limit=limit,
                query_filter=qdrant_filter,
            )
            entries: list[MemoryEntry] = []
            for point in results:
                payload = point.payload or {}
                score = float(point.score)
                if query_text:
                    score = self._hybrid_score(score, query_text, payload.get("text", ""))
                entries.append(
                    MemoryEntry(
                        key=str(payload.get("key", point.id)),
                        value=payload.get("value"),
                        metadata=payload,
                        score=score,
                    ),
                )
            entries.sort(key=lambda e: e.score or 0.0, reverse=True)
            return entries[:limit]
        except Exception as exc:
            raise MemoryReadError(
                f"Vector similarity search failed: {exc}",
                details={"collection": target},
            ) from exc

    async def hybrid_search(
        self,
        query: str,
        *,
        limit: int = VECTOR_SEARCH_TOP_K,
        filters: dict[str, Any] | None = None,
        collection: str | None = None,
        semantic_weight: float = 0.7,
    ) -> list[MemoryEntry]:
        """Combine semantic vector search with keyword overlap scoring."""
        if collection:
            collections = [collection]
        else:
            collections = list(self.DEFAULT_COLLECTIONS)
        all_entries: list[MemoryEntry] = []
        embedding = await self._embedding.embed(query)
        for coll in collections:
            entries = await self.similarity_search(
                embedding,
                limit=limit * 2,
                collection=coll,
                filters=filters,
                query_text=query,
            )
            all_entries.extend(entries)
        query_tokens = set(query.lower().split())
        for entry in all_entries:
            text = str(entry.metadata.get("text", "")).lower()
            text_tokens = set(text.split())
            keyword_score = len(query_tokens & text_tokens) / max(len(query_tokens), 1)
            semantic_score = entry.score or 0.0
            entry.score = semantic_weight * semantic_score + (1 - semantic_weight) * keyword_score
        all_entries.sort(key=lambda e: e.score or 0.0, reverse=True)
        return all_entries[:limit]

    async def insert(
        self,
        key: str,
        text: str,
        value: Any,
        *,
        document_type: VectorDocumentType,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Insert a new document with auto-generated embedding."""
        point_id = key or str(uuid.uuid4())
        meta = {"document_type": document_type.value, "text": text, **(metadata or {})}
        await self.write(point_id, value, metadata=meta)
        return point_id

    async def update(
        self,
        key: str,
        text: str | None = None,
        value: Any | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        existing = await self.read(key)
        if existing is None:
            raise MemoryNotFoundError(f"Vector entry '{key}' not found", details={"key": key})
        merged_meta = {k: v for k, v in {**existing.metadata, **(metadata or {})}.items() if k != "value"}
        if text is not None:
            merged_meta["text"] = text
        new_value = value if value is not None else existing.value
        await self.write(key, new_value, metadata=merged_meta)

    def _build_filter(self, filters: dict[str, Any]) -> Any:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        conditions = [
            FieldCondition(key=k, match=MatchValue(value=v))
            for k, v in filters.items()
        ]
        return Filter(must=conditions)

    def _hybrid_score(self, semantic_score: float, query: str, text: str) -> float:
        query_tokens = set(query.lower().split())
        text_tokens = set(text.lower().split())
        keyword_score = len(query_tokens & text_tokens) / max(len(query_tokens), 1)
        return 0.7 * semantic_score + 0.3 * keyword_score

    @classmethod
    async def from_config(
        cls,
        config: QdrantConfig | None = None,
        *,
        client: QdrantClientProtocol | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> QdrantVectorMemory:
        if client is not None:
            store = cls(client, config=config, embedding_provider=embedding_provider)
            return store
        cfg = config or get_config().qdrant
        try:
            from qdrant_client import AsyncQdrantClient

            api_key = cfg.api_key.get_secret_value() if cfg.api_key else None
            qdrant = AsyncQdrantClient(
                host=cfg.host,
                port=cfg.port,
                grpc_port=cfg.grpc_port,
                api_key=api_key,
                prefer_grpc=cfg.prefer_grpc,
                timeout=cfg.timeout_seconds,
            )
            store = cls(qdrant, config=cfg, embedding_provider=embedding_provider)
            await store.ensure_collections()
            return store
        except Exception:
            return cls(
                InMemoryQdrantClient(vector_size=get_config().embedding.dimension),
                config=cfg,
                embedding_provider=embedding_provider,
            )
