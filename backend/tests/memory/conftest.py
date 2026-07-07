"""Shared test fixtures for memory subsystem tests."""

from __future__ import annotations

import pytest

from backend.agents.memory.digital_twin_memory import DigitalTwinMemoryStore
from backend.agents.memory.embedding import DeterministicEmbeddingProvider
from backend.agents.memory.knowledge_graph import NetworkXKnowledgeGraph
from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.memory.memory_ranker import MemoryRanker
from backend.agents.memory.redis_memory import InMemoryRedisClient, RedisMemoryStore
from backend.agents.memory.vector_memory import InMemoryQdrantClient, QdrantVectorMemory
from backend.agents.memory.working_memory import WorkingMemory
from backend.agents.memory.conversation_memory import ConversationMemory
from backend.agents.memory.session_memory import SessionMemory
from backend.agents.memory.hybrid_retriever import HybridRetriever


@pytest.fixture
def redis_client() -> InMemoryRedisClient:
    return InMemoryRedisClient()


@pytest.fixture
def qdrant_client() -> InMemoryQdrantClient:
    return InMemoryQdrantClient(vector_size=128)


@pytest.fixture
def embedding_provider() -> DeterministicEmbeddingProvider:
    return DeterministicEmbeddingProvider(dimension=128)


@pytest.fixture
async def redis_store(redis_client: InMemoryRedisClient) -> RedisMemoryStore:
    return RedisMemoryStore(redis_client)


@pytest.fixture
async def vector_store(qdrant_client: InMemoryQdrantClient, embedding_provider: DeterministicEmbeddingProvider) -> QdrantVectorMemory:
    for name in QdrantVectorMemory.DEFAULT_COLLECTIONS:
        await qdrant_client.create_collection(name)
    return QdrantVectorMemory(qdrant_client, embedding_provider=embedding_provider)


@pytest.fixture
def graph_store() -> NetworkXKnowledgeGraph:
    return NetworkXKnowledgeGraph()


@pytest.fixture
def twin_store() -> DigitalTwinMemoryStore:
    return DigitalTwinMemoryStore()


@pytest.fixture
def working_store() -> WorkingMemory:
    return WorkingMemory(default_ttl_seconds=60)


@pytest.fixture
async def memory_manager() -> MemoryManager:
    return await MemoryManager.create_in_memory()
