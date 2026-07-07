# ADR-004: Redis + Qdrant Dual-Store Memory

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-07-07 |
| **Deciders** | Nexora Engineering |
| **Related** | [Shared Memory](../memory/shared_memory.md) |

---

## Context

The memory layer must support both fast session-scoped key-value storage (conversation history, workflow state, user preferences) and semantic similarity search over historical climate documents, forecasts, and disaster records. No single database optimally serves both access patterns.

---

## Decision

Use a **dual-store architecture**:

| Store | Technology | Purpose |
|-------|-----------|---------|
| Session / workflow memory | **Redis** | TTL-based KV, session indexing, workflow state |
| Semantic retrieval | **Qdrant** | Vector embeddings, hybrid search, metadata filtering |
| Knowledge graph | **NetworkX** (in-process) | Relational climate domain knowledge |
| Twin versioning | **In-process** (DigitalTwinMemoryStore) | Checkpoint/rollback (future: Redis/PostGIS) |

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Redis only with RediSearch | Weaker vector search vs. Qdrant; less mature hybrid search |
| PostgreSQL + pgvector | Heavier ops overhead; Redis better for session TTL |
| Pinecone / Weaviate | Vendor lock-in; Qdrant is self-hostable |
| Elasticsearch | Overkill for current scale; complex ops |
| Single Qdrant for everything | No native TTL; poor session key management |

---

## Pros

- Redis: sub-millisecond session reads, native TTL, pub/sub ready for future real-time alerts
- Qdrant: purpose-built vector search, metadata filtering, collection isolation
- Both have mature Python async clients
- In-memory mocks available for both in tests
- Self-hostable — no cloud vendor dependency

---

## Cons

- Two systems to deploy and monitor in production
- Data consistency across stores requires application-level coordination
- NetworkX is in-process only (not distributed) — migration needed at scale
- Embedding generation adds latency to vector writes

---

## Consequences

- `GlobalConfig` has separate `RedisConfig` and `QdrantConfig` sections
- `MemoryManager.create()` wires both backends with fallback to in-memory mocks
- Collection naming standardized in `backend/utils/constants.py`
- Embedding provider is pluggable (`DeterministicEmbeddingProvider` for dev/test)

---

## Future Impact

- Redis Cluster for HA session storage
- Qdrant Cloud or self-hosted cluster for production vector scale
- NetworkX → PostGIS migration for distributed knowledge graph (ADR pending)
- Redis pub/sub for real-time alert propagation to Emergency Supervisor
