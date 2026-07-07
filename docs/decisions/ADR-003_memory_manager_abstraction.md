# ADR-003: MemoryManager Abstraction Layer

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-07-07 |
| **Deciders** | Nexora Engineering |
| **Related** | [Shared Memory](../memory/shared_memory.md) |

---

## Context

Agents require diverse memory types: short-term session data (Redis), semantic retrieval (Qdrant), relational knowledge (NetworkX), versioned twin state, ephemeral working memory, and conversation history. Direct access to storage backends from agents creates tight coupling, inconsistent key schemas, and untestable code.

---

## Decision

All memory operations flow through a single **`MemoryManager`** facade that routes to backend-specific stores based on `MemoryDomain` enum. Agents, supervisors, and tools are **prohibited** from accessing Redis, Qdrant, or NetworkX directly.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Direct Redis/Qdrant per agent | Coupling, inconsistent schemas, untestable |
| LangChain memory classes | Too simplistic for multi-domain climate memory |
| Single vector store for everything | Loses TTL, graph relationships, twin versioning |
| Event-sourced memory bus | Over-engineered for current scale |

---

## Pros

- Single API surface: `store()`, `retrieve()`, `search()`, `checkpoint()`, `rollback()`, `merge()`, `summarize()`
- Domain routing via `MemoryDomain` enum prevents misuse
- In-memory mocks (`InMemoryRedisClient`, `InMemoryQdrantClient`) enable fast testing
- `HybridRetriever` fuses multi-backend search with ranking
- LRU cache reduces redundant reads
- Future backend swaps (e.g., PostGIS for graph) require only MemoryManager changes

---

## Cons

- MemoryManager becomes a god-object risk if not kept modular internally
- Additional indirection latency (mitigated by LRU cache)
- All memory schemas must be designed upfront

---

## Consequences

- `MemoryStoreRequest` / `MemoryRetrieveRequest` / `MemorySearchRequest` are the only input types
- Backend implementations (`RedisMemoryStore`, etc.) are internal to `backend/agents/memory/`
- Tests use `MemoryManager.create_in_memory()` factory
- Coding standards enforce the no-direct-access rule

---

## Future Impact

- PostGIS can replace NetworkX by implementing the same internal interface
- Distributed memory (Redis Cluster, Qdrant Cloud) configured only in MemoryManager factory
- Memory access audit logging can be added at the facade layer
