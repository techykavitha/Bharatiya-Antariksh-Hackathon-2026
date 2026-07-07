"""Hybrid retrieval across vector, graph, Redis, and climate state."""

from __future__ import annotations

from typing import Any

from backend.agents.memory.conversation_memory import ConversationMemory
from backend.agents.memory.digital_twin_memory import DigitalTwinMemoryStore
from backend.agents.memory.embedding import EmbeddingProvider
from backend.agents.memory.interfaces import MemoryEntry
from backend.agents.memory.knowledge_graph import NetworkXKnowledgeGraph
from backend.agents.memory.memory_ranker import MemoryRanker
from backend.agents.memory.memory_types import HybridRetrievalResult, MemoryDomain, MemorySearchRequest
from backend.agents.memory.redis_memory import RedisMemoryStore
from backend.agents.memory.serialization import pydantic_to_dict
from backend.agents.memory.vector_memory import QdrantVectorMemory
from backend.agents.state.climate_state import ClimateState
from backend.config.logger import get_logger

logger = get_logger(__name__)


class HybridRetriever:
    """
    Fuses vector search, knowledge graph traversal, Redis session context,
    and live climate state into a single ranked retrieval result.
    """

    def __init__(
        self,
        *,
        vector: QdrantVectorMemory,
        graph: NetworkXKnowledgeGraph,
        redis: RedisMemoryStore,
        digital_twin: DigitalTwinMemoryStore,
        conversation: ConversationMemory,
        ranker: MemoryRanker | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._vector = vector
        self._graph = graph
        self._redis = redis
        self._digital_twin = digital_twin
        self._conversation = conversation
        self._ranker = ranker or MemoryRanker()
        self._embedding = embedding_provider

    async def retrieve(self, request: MemorySearchRequest) -> HybridRetrievalResult:
        """Execute hybrid retrieval and return ranked context."""
        candidates: list[tuple[MemoryEntry, MemoryDomain]] = []
        vector_count = graph_count = redis_count = climate_count = 0

        domains = request.domains or [
            MemoryDomain.VECTOR,
            MemoryDomain.KNOWLEDGE_GRAPH,
            MemoryDomain.CONVERSATION,
            MemoryDomain.CLIMATE,
            MemoryDomain.DIGITAL_TWIN,
        ]

        if MemoryDomain.VECTOR in domains:
            vector_results = await self._vector.hybrid_search(
                request.query,
                limit=request.limit,
                filters=request.filters,
                collection=request.collection,
            )
            for entry in vector_results:
                candidates.append((entry, MemoryDomain.VECTOR))
            vector_count = len(vector_results)

        if MemoryDomain.KNOWLEDGE_GRAPH in domains:
            graph_results = await self._graph.query(
                request.query,
                node_type=request.filters.get("node_type") if request.filters else None,
                limit=request.limit,
            )
            for entry in graph_results:
                candidates.append((entry, MemoryDomain.KNOWLEDGE_GRAPH))
            graph_count = len(graph_results)

        if MemoryDomain.CONVERSATION in domains and request.session_id:
            redis_results = await self._conversation.search(
                request.session_id,
                request.query,
                limit=request.limit,
            )
            for entry in redis_results:
                candidates.append((entry, MemoryDomain.CONVERSATION))
            redis_count = len(redis_results)

        if request.session_id and MemoryDomain.SESSION in domains:
            session_results = await self._redis.search(
                request.query,
                limit=request.limit,
                session_id=request.session_id,
            )
            for entry in session_results:
                candidates.append((entry, MemoryDomain.SESSION))
            redis_count += len(session_results)

        if MemoryDomain.CLIMATE in domains:
            climate_entries = await self._retrieve_climate_context(
                request.climate_context,
                request.query,
            )
            for entry in climate_entries:
                candidates.append((entry, MemoryDomain.CLIMATE))
            climate_count = len(climate_entries)

        if MemoryDomain.DIGITAL_TWIN in domains and request.twin_id:
            twin_entry = await self._digital_twin.read(request.twin_id)
            if twin_entry:
                candidates.append((twin_entry, MemoryDomain.DIGITAL_TWIN))
                climate_count += 1

        if request.embedding and MemoryDomain.VECTOR in domains:
            similar = await self._vector.similarity_search(
                request.embedding,
                limit=request.limit,
                collection=request.collection,
            )
            for entry in similar:
                candidates.append((entry, MemoryDomain.VECTOR))
            vector_count += len(similar)

        ranked = self._ranker.rank(
            candidates,
            query=request.query,
            target_domains=request.domains or None,
            limit=request.limit,
        )

        logger.info(
            "hybrid_retrieval_complete",
            query=request.query[:80],
            vector_count=vector_count,
            graph_count=graph_count,
            redis_count=redis_count,
            climate_count=climate_count,
            total_ranked=len(ranked),
        )

        return HybridRetrievalResult(
            query=request.query,
            results=ranked,
            vector_count=vector_count,
            graph_count=graph_count,
            redis_count=redis_count,
            climate_count=climate_count,
        )

    async def _retrieve_climate_context(
        self,
        climate_context: dict[str, Any] | None,
        query: str,
    ) -> list[MemoryEntry]:
        entries: list[MemoryEntry] = []
        if climate_context is None:
            workflow = await self._redis.get_workflow_state()
            if workflow and workflow.value:
                climate_data = workflow.value.get("climate_state")
                if climate_data:
                    climate_context = (
                        pydantic_to_dict(climate_data)
                        if hasattr(climate_data, "model_dump")
                        else climate_data
                    )

        if climate_context is None:
            return entries

        try:
            state = ClimateState.model_validate(climate_context)
        except Exception:
            state = None

        if state:
            serialized = pydantic_to_dict(state)
            query_lower = query.lower()
            if any(query_lower in str(v).lower() for v in serialized.values()):
                entries.append(
                    MemoryEntry(
                        key="climate_state",
                        value=serialized,
                        metadata={"type": "climate_state", "importance": 0.95},
                        score=0.9,
                    ),
                )
            if state.active_simulation:
                sim = pydantic_to_dict(state.active_simulation)
                entries.append(
                    MemoryEntry(
                        key=f"simulation:{state.active_simulation.simulation_id}",
                        value=sim,
                        metadata={"type": "active_simulation", "importance": 0.85},
                        score=0.8,
                    ),
                )
            for forecast in state.forecast_references[:5]:
                entries.append(
                    MemoryEntry(
                        key=f"forecast:{forecast.forecast_id}",
                        value=pydantic_to_dict(forecast),
                        metadata={"type": "forecast_reference", "importance": 0.8},
                    ),
                )
        elif climate_context:
            entries.append(
                MemoryEntry(
                    key="climate_state",
                    value=climate_context,
                    metadata={"type": "climate_state"},
                ),
            )
        return entries
