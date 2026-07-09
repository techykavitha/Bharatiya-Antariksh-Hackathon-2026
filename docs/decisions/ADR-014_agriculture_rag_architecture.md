# ADR-014: Agriculture RAG Architecture

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-07-09 |
| **Deciders** | Nexora Engineering |
| **Related** | [Development Log 015](../development_logs/015_agriculture_agent.md), [ADR-004](./ADR-004_redis_plus_qdrant.md), [ADR-006](./ADR-006_specialized_agent_framework.md) |

---

## Context

Agricultural advisory in Hyperion requires domain knowledge beyond quantitative remote sensing signals — crop calendars, government advisories (ICAR, IMD), irrigation best practices, and drought management protocols. This knowledge is textual, seasonal, and region-specific. Hard-coding all advisories into reasoning rules would be unmaintainable; embedding everything in tool logic would prevent knowledge updates without code changes.

ADR-004 established Redis + Qdrant for session memory and vector retrieval at the platform level. The agriculture agent needs a domain-specific RAG layer that can operate independently in tests (no external vector DB) while supporting future Qdrant integration.

---

## Decision

Introduce a **provider-agnostic RAG subsystem** in `backend/agents/specialized/agriculture/agriculture_rag.py` orchestrated by `AgricultureRagService`.

### Architecture layers

| Component | Responsibility |
|-----------|----------------|
| `AgricultureKnowledgeRetriever` | Protocol defining `retrieve()` contract |
| `BaseAgricultureRAG` | Abstract base class for RAG implementations |
| `InMemoryAgricultureRAG` | Keyword + filter retrieval from seeded corpus |
| `AgricultureRagService` | Facade delegating to configured retriever |
| `SEEDED_AGRICULTURE_KNOWLEDGE` | In-memory document corpus for v0.3.0 |

### Retrieval interface

```python
async def retrieve(
    query: str,
    *,
    crop_type: str | None = None,
    region: str | None = None,
    season: str | None = None,
    limit: int = 5,
    categories: list[str] | None = None,
) -> RagRetrievalResult
```

Filters by crop, region, season, and document category (crop_calendar, government_advisory, best_practice).

### Pipeline placement

- RAG retrieval executes at **observe phase** (`_run_rag_retrieval()`), enriching `AgentContext` before tool analysis.
- `GovernmentAdvisoryTool` provides structured advisory output; RAG provides free-text knowledge retrieval.
- Retrieved `RagDocument` entries attached to context for reasoning and XAI evidence.

### Seeded corpus

Documents cover wheat rabi calendar (Punjab), paddy kharif (Tamil Nadu), cotton kharif (Maharashtra), ICAR drought advisory, IMD heatwave crop protection, and micro-irrigation best practices.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Hard-coded advisories in reasoning engine only | Unmaintainable; knowledge updates require code changes |
| RAG as a tool (`RagTool`) in the 12-tool set | Retrieval is context enrichment, not quantitative analysis; observe phase is correct placement |
| Direct Qdrant integration in v1.0 | External dependency; blocks test isolation |
| Global platform RAG service | Agriculture knowledge is domain-specific; coupling to platform RAG premature |
| LLM-based retrieval (no corpus) | Non-deterministic; seeded corpus enables regression testing |
| Embed knowledge in `CropCalendarTool` only | Misses government advisories and best practices beyond calendar data |

---

## Advantages

- Provider-agnostic Protocol enables `InMemoryAgricultureRAG` now, `QdrantAgricultureRAG` later without agent changes
- Observe-phase retrieval enriches context before quantitative tool analysis
- Seeded corpus provides deterministic, testable advisory content
- Crop/region/season filters enable precise retrieval for regional scenarios
- `RagDocument` model bridges to XAI evidence chain
- Dual path (RAG + `GovernmentAdvisoryTool`) covers both free-text and structured advisories
- Zero external dependencies in v0.3.0 test suite

---

## Disadvantages

- In-memory keyword retrieval lacks semantic similarity of vector embeddings
- Seeded corpus limited to ~10 documents; production needs orders of magnitude more
- No incremental knowledge update mechanism in v0.3.0
- RAG observe-phase adds latency before tool execution
- Keyword scoring may miss semantically related but lexically different documents

---

## Trade-offs

| Trade-off | Choice | Rationale |
|-----------|--------|-----------|
| In-memory vs Qdrant v1.0 | In-memory with Protocol | Testability; zero deps; migration path preserved |
| Observe vs analyze phase | Observe phase | Context enrichment before quantitative analysis |
| Protocol vs concrete class | Protocol + ABC | Maximum implementation flexibility |
| Keyword vs vector retrieval | Keyword + filter v1.0 | Deterministic; sufficient for seeded corpus |
| Domain RAG vs platform RAG | Domain-specific module | Agriculture knowledge schema differs from general retrieval |

---

## Future Impact

- `QdrantAgricultureRAG` implementation using ADR-004 vector store infrastructure
- Live ICAR/IMD advisory feed ingestion via corpus builder extension
- RAG pattern reusable for other knowledge-intensive agents (policy, regulation)
- XAI evidence enrichment from `RagDocument` citations in explanation reports
- Multilingual corpus expansion (Hindi, regional languages) for farmer-facing advisories
- Embedding-based semantic retrieval when corpus exceeds keyword matching effectiveness
