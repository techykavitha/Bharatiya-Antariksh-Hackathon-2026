"""Central memory manager — single entry point for all agent memory operations."""

from __future__ import annotations

from typing import Any

from backend.agents.memory.conversation_memory import ConversationMemory
from backend.agents.memory.digital_twin_memory import DigitalTwinMemoryStore
from backend.agents.memory.embedding import EmbeddingProvider, create_embedding_provider
from backend.agents.memory.hybrid_retriever import HybridRetriever
from backend.agents.memory.interfaces import MemoryEntry
from backend.agents.memory.knowledge_graph import NetworkXKnowledgeGraph
from backend.agents.memory.memory_cache import AsyncLRUMemoryCache
from backend.agents.memory.memory_ranker import MemoryRanker
from backend.agents.memory.memory_types import (
    CheckpointRecord,
    HybridRetrievalResult,
    MemoryDomain,
    MemoryRetrieveRequest,
    MemorySearchRequest,
    MemoryStoreRequest,
    MemorySummary,
    RankedMemory,
    StateComparisonResult,
)
from backend.agents.memory.redis_memory import InMemoryRedisClient, RedisMemoryStore
from backend.agents.memory.serialization import pydantic_to_dict
from backend.agents.memory.session_memory import SessionMemory
from backend.agents.memory.vector_memory import InMemoryQdrantClient, QdrantVectorMemory
from backend.agents.memory.working_memory import WorkingMemory
from backend.agents.state.climate_state import ClimateState
from backend.agents.state.conversation_state import ConversationTurn
from backend.config.logger import get_logger
from backend.config.settings import GlobalConfig, get_config
from backend.utils.errors import MemoryNotFoundError, MemoryWriteError

logger = get_logger(__name__)


class MemoryManager:
    """
    Unified memory facade for the Hyperion Climate Twin multi-agent system.

    All agents must interact with memory exclusively through this class.
    Routes operations to the appropriate backend based on memory domain.
    """

    def __init__(
        self,
        *,
        redis: RedisMemoryStore,
        vector: QdrantVectorMemory,
        graph: NetworkXKnowledgeGraph,
        digital_twin: DigitalTwinMemoryStore,
        working: WorkingMemory,
        conversation: ConversationMemory,
        session: SessionMemory,
        retriever: HybridRetriever,
        ranker: MemoryRanker,
        cache: AsyncLRUMemoryCache[MemoryEntry] | None = None,
        config: GlobalConfig | None = None,
    ) -> None:
        self._redis = redis
        self._vector = vector
        self._graph = graph
        self._digital_twin = digital_twin
        self._working = working
        self._conversation = conversation
        self._session = session
        self._retriever = retriever
        self._ranker = ranker
        self._cache = cache or AsyncLRUMemoryCache[MemoryEntry](max_size=4096)
        self._config = config or get_config()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    async def create(
        cls,
        config: GlobalConfig | None = None,
        *,
        embedding_provider: EmbeddingProvider | None = None,
        redis_client: Any | None = None,
        qdrant_client: Any | None = None,
    ) -> MemoryManager:
        """Construct a fully-wired MemoryManager with all backends."""
        cfg = config or get_config()
        embedder = embedding_provider or create_embedding_provider(cfg)

        redis = await RedisMemoryStore.from_config(cfg.redis, client=redis_client)
        vector = await QdrantVectorMemory.from_config(
            cfg.qdrant,
            client=qdrant_client,
            embedding_provider=embedder,
        )
        if isinstance(vector._client, InMemoryQdrantClient):
            for name in QdrantVectorMemory.DEFAULT_COLLECTIONS:
                await vector._client.create_collection(name)

        graph = NetworkXKnowledgeGraph()
        digital_twin = DigitalTwinMemoryStore()
        working = WorkingMemory()
        conversation = ConversationMemory(redis)
        session = SessionMemory(redis)
        ranker = MemoryRanker()
        retriever = HybridRetriever(
            vector=vector,
            graph=graph,
            redis=redis,
            digital_twin=digital_twin,
            conversation=conversation,
            ranker=ranker,
            embedding_provider=embedder,
        )

        manager = cls(
            redis=redis,
            vector=vector,
            graph=graph,
            digital_twin=digital_twin,
            working=working,
            conversation=conversation,
            session=session,
            retriever=retriever,
            ranker=ranker,
            config=cfg,
        )
        logger.info("memory_manager_initialized")
        return manager

    # ------------------------------------------------------------------
    # Unified API
    # ------------------------------------------------------------------

    async def store(self, request: MemoryStoreRequest) -> str:
        """Store a value in the appropriate memory domain."""
        domain = request.domain
        key = request.key
        value = request.value
        meta = dict(request.metadata)

        if request.session_id:
            meta["session_id"] = request.session_id

        if domain == MemoryDomain.CONVERSATION:
            if request.session_id and isinstance(value, dict) and "role" in value and "content" in value:
                turn = ConversationTurn.model_validate(value)
                await self._conversation.append_turn(request.session_id, turn)
            elif request.session_id and isinstance(value, dict) and "conversation_id" in value:
                from backend.agents.state.conversation_state import ConversationState

                await self._conversation.save_conversation_state(
                    request.session_id,
                    ConversationState.model_validate(value),
                )
            elif request.session_id and hasattr(value, "model_dump"):
                await self._conversation.save_conversation_state(request.session_id, value)
            else:
                await self._redis.write(key, value, metadata=meta, ttl_seconds=request.ttl_seconds)

        elif domain == MemoryDomain.SESSION:
            if not request.session_id:
                raise MemoryWriteError("Session memory requires session_id")
            if key == "preferences":
                await self._session.update_preferences(request.session_id, value)
            elif key == "dashboard":
                await self._session.set_active_dashboard(request.session_id, value)
            elif key == "simulation":
                await self._session.set_active_simulation(request.session_id, str(value))
            else:
                await self._redis.write(key, value, session_id=request.session_id, ttl_seconds=request.ttl_seconds)

        elif domain == MemoryDomain.CLIMATE:
            if isinstance(value, ClimateState):
                value = pydantic_to_dict(value)
            await self._redis.write(key, value, metadata=meta, session_id=request.session_id, ttl_seconds=request.ttl_seconds)
            if request.session_id:
                await self._redis.store_workflow_state({"climate_state": value}, session_id=request.session_id)

        elif domain == MemoryDomain.WORKFLOW:
            await self._redis.store_workflow_state(pydantic_to_dict(value), session_id=request.session_id)

        elif domain == MemoryDomain.WORKING:
            agent_id = meta.get("agent_id")
            await self._working.write(key, value, metadata=meta, ttl_seconds=request.ttl_seconds, agent_id=agent_id)

        elif domain == MemoryDomain.VECTOR:
            if request.embedding:
                meta["embedding"] = request.embedding
            text = meta.get("text", str(value))
            meta["text"] = text
            await self._vector.write(key, value, metadata=meta)

        elif domain == MemoryDomain.KNOWLEDGE_GRAPH:
            await self._graph.write(key, value, metadata=meta)

        elif domain == MemoryDomain.DIGITAL_TWIN:
            twin_id = meta.get("twin_id", key)
            await self._digital_twin.write(key, value, metadata={**meta, "twin_id": twin_id})

        else:
            await self._redis.write(key, value, metadata=meta, session_id=request.session_id, ttl_seconds=request.ttl_seconds)

        cache_key = self._cache_key(domain, key, request.session_id)
        entry = MemoryEntry(key=key, value=value, metadata=meta)
        await self._cache.set(cache_key, entry, ttl_seconds=float(request.ttl_seconds) if request.ttl_seconds else None)
        logger.debug("memory_stored", domain=domain.value, key=key)
        return key

    async def retrieve(self, request: MemoryRetrieveRequest) -> MemoryEntry | None:
        """Retrieve a value from the specified memory domain."""
        cache_key = self._cache_key(request.domain, request.key, request.session_id)
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        entry: MemoryEntry | None = None
        domain = request.domain

        if domain == MemoryDomain.CONVERSATION and request.session_id:
            state = await self._conversation.get_conversation_state(request.session_id)
            entry = MemoryEntry(key=request.key, value=pydantic_to_dict(state))

        elif domain == MemoryDomain.SESSION and request.session_id:
            session = await self._session.get_session(request.session_id)
            entry = MemoryEntry(key=request.key, value=pydantic_to_dict(session)) if session else None

        elif domain == MemoryDomain.WORKING:
            entry = await self._working.read(request.key)

        elif domain == MemoryDomain.VECTOR:
            entry = await self._vector.read(request.key)

        elif domain == MemoryDomain.KNOWLEDGE_GRAPH:
            entry = await self._graph.read(request.key)

        elif domain == MemoryDomain.DIGITAL_TWIN:
            if request.layer_name and request.twin_id:
                entry = await self._digital_twin.get_layer(request.twin_id, request.layer_name)
            elif request.twin_id:
                entry = await self._digital_twin.read(request.twin_id)
            else:
                entry = await self._digital_twin.read(request.key)

        elif domain == MemoryDomain.CLIMATE:
            entry = await self._redis.read(request.key, session_id=request.session_id)

        elif domain == MemoryDomain.WORKFLOW:
            entry = await self._redis.get_workflow_state(session_id=request.session_id)

        else:
            entry = await self._redis.read(request.key, session_id=request.session_id)

        if entry:
            await self._cache.set(cache_key, entry)
        return entry

    async def update(self, request: MemoryStoreRequest) -> str:
        """Update an existing memory entry (delegates to store with merge semantics)."""
        existing = await self.retrieve(
            MemoryRetrieveRequest(
                domain=request.domain,
                key=request.key,
                session_id=request.session_id,
            ),
        )
        if existing is None:
            raise MemoryNotFoundError(
                f"Cannot update missing key '{request.key}' in domain '{request.domain}'",
            )

        if request.domain == MemoryDomain.VECTOR:
            text = request.metadata.get("text")
            await self._vector.update(request.key, text=text, value=request.value, metadata=request.metadata)
        elif isinstance(existing.value, dict) and isinstance(request.value, dict):
            merged = {**existing.value, **request.value}
            request.value = merged
            await self.store(request)
        else:
            await self.store(request)

        return request.key

    async def delete(self, domain: MemoryDomain, key: str, *, session_id: str | None = None) -> bool:
        """Delete a memory entry from the specified domain."""
        cache_key = self._cache_key(domain, key, session_id)
        await self._cache.delete(cache_key)

        if domain == MemoryDomain.WORKING:
            return await self._working.delete(key)
        if domain == MemoryDomain.VECTOR:
            return await self._vector.delete(key)
        if domain == MemoryDomain.KNOWLEDGE_GRAPH:
            return await self._graph.delete(key)
        if domain == MemoryDomain.DIGITAL_TWIN:
            return await self._digital_twin.delete(key)
        if domain == MemoryDomain.SESSION and session_id:
            return await self._session.delete_session(session_id)
        return await self._redis.delete(key, session_id=session_id)

    async def search(self, request: MemorySearchRequest) -> list[RankedMemory]:
        """Search across memory domains using hybrid retrieval."""
        result = await self._retriever.retrieve(request)
        return result.results

    async def similar(
        self,
        embedding: list[float],
        *,
        limit: int = 10,
        collection: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[MemoryEntry]:
        """Retrieve semantically similar entries from vector memory."""
        return await self._vector.similarity_search(
            embedding,
            limit=limit,
            collection=collection,
            filters=filters,
        )

    async def checkpoint(self, twin_id: str, *, label: str | None = None) -> CheckpointRecord:
        """Create a digital twin state checkpoint."""
        return await self._digital_twin.checkpoint(twin_id, label=label)

    async def rollback(self, twin_id: str, version: str) -> MemoryEntry:
        """Rollback digital twin to a previous checkpoint version."""
        return await self._digital_twin.rollback(twin_id, version)

    async def merge(
        self,
        twin_id: str,
        other_state: dict[str, Any],
        *,
        strategy: str = "override",
    ) -> MemoryEntry:
        """Merge external state into a digital twin."""
        return await self._digital_twin.merge_state(twin_id, other_state, strategy=strategy)

    async def summarize(
        self,
        request: MemorySearchRequest,
        *,
        max_entries: int = 5,
    ) -> MemorySummary:
        """Retrieve and condense relevant memories into a summary."""
        ranked = await self.search(request)
        top = ranked[:max_entries]
        if not top:
            return MemorySummary(
                domain=request.domains[0] if request.domains else None,
                content="No relevant memories found.",
            )

        lines: list[str] = []
        source_keys: list[str] = []
        for item in top:
            source_keys.append(item.entry.key)
            domain_label = item.domain.value
            value_preview = str(item.entry.value)[:200]
            lines.append(f"[{domain_label}] {item.entry.key}: {value_preview}")

        content = "\n".join(lines)
        token_estimate = len(content.split())
        return MemorySummary(
            domain=request.domains[0] if len(request.domains) == 1 else None,
            content=content,
            source_keys=source_keys,
            token_estimate=token_estimate,
        )

    # ------------------------------------------------------------------
    # Direct backend accessors (for advanced use, still via manager)
    # ------------------------------------------------------------------

    @property
    def redis(self) -> RedisMemoryStore:
        return self._redis

    @property
    def vector(self) -> QdrantVectorMemory:
        return self._vector

    @property
    def graph(self) -> NetworkXKnowledgeGraph:
        return self._graph

    @property
    def digital_twin(self) -> DigitalTwinMemoryStore:
        return self._digital_twin

    @property
    def working(self) -> WorkingMemory:
        return self._working

    @property
    def conversation(self) -> ConversationMemory:
        return self._conversation

    @property
    def session(self) -> SessionMemory:
        return self._session

    @property
    def retriever(self) -> HybridRetriever:
        return self._retriever

    async def hybrid_retrieve(self, request: MemorySearchRequest) -> HybridRetrievalResult:
        """Full hybrid retrieval result with source counts."""
        return await self._retriever.retrieve(request)

    async def compare_states(self, twin_id: str, version_a: str, version_b: str) -> StateComparisonResult:
        return await self._digital_twin.compare_state(twin_id, version_a, version_b)

    async def clone_twin(self, twin_id: str, new_twin_id: str) -> MemoryEntry:
        return await self._digital_twin.clone_state(twin_id, new_twin_id)

    @staticmethod
    def _cache_key(domain: MemoryDomain, key: str, session_id: str | None) -> str:
        parts = [domain.value, key]
        if session_id:
            parts.insert(1, session_id)
        return ":".join(parts)

    @classmethod
    async def create_in_memory(cls) -> MemoryManager:
        """Create a MemoryManager backed entirely by in-memory stores (for tests)."""
        return await cls.create(
            redis_client=InMemoryRedisClient(),
            qdrant_client=InMemoryQdrantClient(),
        )
