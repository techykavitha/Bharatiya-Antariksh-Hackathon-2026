# Mock Components

> **Last Updated:** 2026-07-07

---

## Overview

All tests use in-memory mock implementations of external dependencies. No Redis, Qdrant, or network services are required to run the test suite.

---

## In-Memory Mocks

### InMemoryRedisClient

**Location:** `backend/agents/memory/redis_memory.py`  
**Implements:** Redis-like KV operations in a Python dict

| Method | Behavior |
|--------|----------|
| `get(key)` | Dict lookup |
| `set(key, value, ex=seconds)` | Dict store with optional TTL |
| `delete(key)` | Dict removal |
| `expire(key, seconds)` | Set TTL timestamp |
| `keys(pattern)` | Pattern matching via fnmatch |
| `ping()` | Returns `True` |

**Used by:** `RedisMemoryStore`, all Redis tests, `MemoryManager.create_in_memory()`

---

### InMemoryQdrantClient

**Location:** `backend/agents/memory/vector_memory.py`  
**Implements:** Qdrant-like vector operations in Python data structures

| Method | Behavior |
|--------|----------|
| `upsert(collection, points)` | Store vectors in dict |
| `search(collection, vector, limit)` | Cosine similarity search |
| `delete(collection, ids)` | Remove points |
| `get_collections()` | List collection names |

**Used by:** `QdrantVectorMemory`, all vector tests, `MemoryManager.create_in_memory()`

---

### DeterministicEmbeddingProvider

**Location:** `backend/agents/memory/embedding.py`  
**Implements:** Token-overlap based embedding for reproducible tests

| Method | Behavior |
|--------|----------|
| `embed(text)` | Hash-based vector from token overlap |
| `embed_batch(texts)` | Batch embedding |
| `dimensions` | Fixed dimension count |

**Used by:** All vector memory tests, hybrid retrieval tests

---

### NetworkXKnowledgeGraph

**Location:** `backend/agents/memory/knowledge_graph.py`  
**Note:** NetworkX is used directly (in-process), not mocked. Graph is created fresh per test.

---

### DigitalTwinMemoryStore

**Location:** `backend/agents/memory/digital_twin_memory.py`  
**Note:** In-process dict store — inherently a test-friendly implementation.

---

## Test Fixtures

### Memory Layer (`backend/tests/memory/conftest.py`)

| Fixture | Provides |
|---------|----------|
| `memory_manager` | `MemoryManager.create_in_memory()` |
| `redis_store` | Standalone `RedisMemoryStore` with mock client |
| `vector_store` | Standalone `QdrantVectorMemory` with mock client |
| `graph_store` | Empty `NetworkXKnowledgeGraph` |
| `populated_graph` | Pre-populated graph with climate nodes |
| `twin_store` | Empty `DigitalTwinMemoryStore` |
| `twin_with_data` | Pre-populated twin with checkpoints |
| `working_store` | Empty `WorkingMemory` |
| `conversation_memory` | Empty `ConversationMemory` |
| `session_memory` | Empty `SessionMemory` |
| `embedding_provider` | `DeterministicEmbeddingProvider` |

### Supervisor Layer (`backend/tests/supervisor/conftest.py`)

| Fixture | Provides |
|---------|----------|
| `memory_manager` | In-memory MemoryManager |
| `supervisor` | Initialized `ClimateSupervisor` |
| `classifier` | `IntentClassifier` instance |

### Domain Layer (`backend/tests/domain/conftest.py`)

| Fixture | Provides |
|---------|----------|
| `memory_manager` | In-memory MemoryManager |
| `environmental_supervisor` | Initialized `EnvironmentalSupervisor` |

---

## Mock Agent Handlers

Domain tests use inline mock agents implementing `DomainAgentHandler`:

```python
class _MockFloodAgent:
    @property
    def agent_id(self) -> str:
        return "flood_agent"

    async def invoke(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(
            agent_id=self.agent_id,
            content="Mock flood analysis result",
            status=AgentStatus.COMPLETED,
        )

    async def health_check(self) -> bool:
        return True
```

---

## Factory Methods

| Factory | Location | Purpose |
|---------|----------|---------|
| `MemoryManager.create_in_memory()` | `memory_manager.py` | Full in-memory memory stack |
| `ClimateSupervisor.create(memory)` | `climate_supervisor.py` | Supervisor with dependencies |
| `EnvironmentalSupervisor.create(memory)` | `environmental_supervisor.py` | Domain supervisor |
| `DomainRegistry.register_all_defaults(memory)` | `domain_registry.py` | All three domain supervisors |

---

## Related Documents

- [Unit Test Summary](./unit_test_summary.md)
- [Shared Memory](../memory/shared_memory.md)
