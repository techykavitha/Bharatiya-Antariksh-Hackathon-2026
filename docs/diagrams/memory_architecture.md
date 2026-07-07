# Memory Architecture

> **Last Updated:** 2026-07-07

---

## Overview

The Hyperion memory system uses a facade pattern where all agents interact exclusively through `MemoryManager`, which routes operations to domain-specific backends.

---

## Component Diagram

```mermaid
graph TB
    subgraph Agents
        CS[Climate Supervisor]
        DS[Domain Supervisors]
        SA[Specialized Agents]
    end

    subgraph MemoryManager Facade
        MM[MemoryManager]
        CACHE[AsyncLRUMemoryCache]
        RANK[MemoryRanker]
        HYBRID[HybridRetriever]
    end

    subgraph Backends
        REDIS[(Redis / InMemory)]
        QDRANT[(Qdrant / InMemory)]
        GRAPH[(NetworkX)]
        TWIN[(DigitalTwin In-Process)]
        WORKING[(Working Memory)]
        CONV[(Conversation Memory)]
        SESS[(Session Memory)]
    end

    CS --> MM
    DS --> MM
    SA --> MM
    MM --> CACHE
    MM --> RANK
    MM --> HYBRID
    MM --> REDIS
    MM --> QDRANT
    MM --> GRAPH
    MM --> TWIN
    MM --> WORKING
    MM --> CONV
    MM --> SESS
    HYBRID --> REDIS
    HYBRID --> QDRANT
    HYBRID --> GRAPH
```

---

## Memory Domain Routing

```mermaid
flowchart LR
    REQ[MemoryStoreRequest] --> MM{MemoryManager}
    MM -->|WORKING| WM[WorkingMemory]
    MM -->|CONVERSATION| CM[ConversationMemory]
    MM -->|SESSION| SM[SessionMemory]
    MM -->|REDIS / CLIMATE| RS[RedisMemoryStore]
    MM -->|VECTOR| VM[QdrantVectorMemory]
    MM -->|KNOWLEDGE_GRAPH| KG[NetworkXKnowledgeGraph]
    MM -->|DIGITAL_TWIN| DT[DigitalTwinMemoryStore]
```

---

## Read Path with Cache

```mermaid
sequenceDiagram
    participant Agent
    participant MM as MemoryManager
    participant Cache as LRU Cache
    participant Backend

    Agent->>MM: retrieve(request)
    MM->>Cache: get(cache_key)
    alt Cache Hit
        Cache-->>MM: MemoryEntry
    else Cache Miss
        MM->>Backend: read(key)
        Backend-->>MM: MemoryEntry
        MM->>Cache: set(cache_key, entry)
    end
    MM-->>Agent: MemoryEntry
```

---

## Search / Hybrid Retrieval

```mermaid
flowchart TD
    SEARCH[MemorySearchRequest] --> HR[HybridRetriever]
    HR --> V[Vector Search]
    HR --> G[Graph Traversal]
    HR --> R[Redis Keyword Search]
    V --> FUSE[Result Fusion]
    G --> FUSE
    R --> FUSE
    FUSE --> MR[MemoryRanker]
    MR --> OUT[list of RankedMemory]
```

---

## Digital Twin Versioning

```mermaid
stateDiagram-v2
    [*] --> Active: create twin
    Active --> Checkpoint: checkpoint(label)
    Checkpoint --> Active: continue
    Active --> Rollback: rollback(version)
    Rollback --> Active: restored state
    Active --> Clone: clone_twin(new_id)
    Clone --> [*]: new twin
    Active --> Merge: merge(source)
    Merge --> Active: merged state
```

---

## Key Design Constraints

| Constraint | Enforcement |
|------------|-------------|
| No direct backend access | Coding standard + ADR-003 |
| Session scoping | Redis key prefix with session_id |
| Cache invalidation | On write, update, delete, TTL change |
| Collection isolation | Qdrant collections per document type |

---

## Related Documents

- [Shared Memory Component Doc](../memory/shared_memory.md)
- [ADR-003](../decisions/ADR-003_memory_manager_abstraction.md)
- [ADR-004](../decisions/ADR-004_redis_plus_qdrant.md)
