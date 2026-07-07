# ADR-010: Climate Knowledge Graph

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-07-07 |
| **Deciders** | Nexora Engineering |
| **Related** | [Climate Knowledge Graph](../knowledge_graph/climate_knowledge_graph.md), [ADR-005](./ADR-005_domain_supervisors.md), [ADR-009](./ADR-009_explainability_framework.md) |

---

## Context

Hyperion agents and supervisors reason about climate hazards, geography, infrastructure, population exposure, and inter-agent dependencies. Session memory (ADR-003, ADR-004) captures conversation and working context but is not an authoritative domain ontology. Agents need structural reasoning—impact chains, compound disasters, cascading failures, and affected-agent discovery—for observe-phase context and supervisor routing.

A dedicated climate knowledge graph must be separate from the memory manager's runtime graph, typed for domain entities, and queryable without external graph database infrastructure in v1.0.

---

## Decision

Introduce a **Climate Knowledge Graph (CKG)** in `backend/knowledge_graph/` as an enterprise domain ontology for climate intelligence, orchestrated by `GraphEngine`.

### Entity and relationship model

- **22 entity types** via `EntityType` enum and typed `ClimateEntity` subclasses (`entity_models.py`)
- **10 relationship types** via `RelationshipType` and `GraphRelationship` (`relationship_models.py`)
- **Schema constraints** in `graph_schema.py` — valid source→relationship→target triples enforced at write time
- **Factory registry** — `ENTITY_MODEL_REGISTRY` + `create_entity()` for polymorphic deserialization

Entity categories include hazards, geography, infrastructure, population, agents, forecasts, and digital twins.

### Engine architecture

| Component | Module | Responsibility |
|-----------|--------|----------------|
| Orchestrator | `graph_engine.py` | CRUD, lifecycle, metrics, snapshot I/O; exposes `.query` and `.reasoning` |
| Query | `graph_query.py` | Neighbors, shortest path, impact chain, affected agents, related events, historical similarity, search |
| Reasoning | `graph_reasoning.py` | Secondary impacts, cascading failures, compound disasters, agent dependencies |
| Builder | `graph_builder.py` | `ClimateGraphBuilder.build_india_climate_graph()` — India seed data (~27+ entities) |
| Validation | `graph_validator.py` | Entity, relationship, and graph-level validation |
| Serialization | `graph_serializer.py` | Snapshot and NetworkX node-link format |
| Metrics | `graph_metrics.py` | Operation timing and counts |

### Storage model

- **Dual-store in-process:** `nx.DiGraph` for topology + `_entities` / `_relationships` dicts for full Pydantic models
- **Async mutations** guarded by `asyncio.Lock`; read paths use engine reference
- **No external graph DB in v1.0** — persistence via serializer snapshots only

### Two-graph architecture

| Graph | Location | Purpose |
|-------|----------|---------|
| Climate Knowledge Graph | `backend/knowledge_graph/` | Authoritative domain ontology; structural reasoning |
| Memory graph | `backend/agents/memory/knowledge_graph.py` | Session/runtime context via `MemoryManager` |

These **must not be conflated.** CKG is read-heavy domain truth; memory graph is write-heavy session state.

### Reasoning output bridge

`GraphReasoningEngine` produces `ReasoningInsight` objects with confidence, entity IDs, and supporting relationships—structured for downstream XAI evidence (ADR-009) and future RL state features (ADR-008).

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Single graph for memory and domain ontology | Conflates session state with authoritative domain truth; different lifecycles and access patterns |
| Neo4j or external graph database in v1.0 | Operational complexity; in-process NetworkX sufficient for current scale and testability |
| Generic untyped nodes (string labels only) | Loses domain validation, schema constraints, and typed query safety |
| Embed graph in each specialized agent | Duplicated ontology; no cross-agent impact chain or compound disaster detection |
| Graph reasoning inside domain supervisors | Supervisors orchestrate; graph is shared infrastructure consumed by agents and supervisors |
| Global static graph singleton | Prevents testing isolation and per-request graph snapshots |

---

## Pros

- Typed 22-entity ontology with schema-constrained relationships
- Query and reasoning engines separated—traversal vs. inference rules
- Impact chains and compound disaster detection support multi-hazard workflows
- `affected_agents()` enables supervisor routing without hardcoded agent lists
- India-first seed data (`build_india_climate_graph()`) provides realistic development scenarios
- In-process NetworkX enables fast tests and zero external dependencies
- `ReasoningInsight` bridges to explainability without tight XAI coupling
- Snapshot serialization supports graph versioning and reproducible scenarios

---

## Cons

- No agent imports `backend.knowledge_graph` in production yet; integration is planned
- In-process storage does not scale to national-scale graphs without external DB migration
- India seed data limits out-of-box utility for other regions until builders expand
- Async lock serializes all mutations; high write concurrency would bottleneck
- No incremental sync from live sensor or forecast feeds in v1.0
- RL state encoder integration (graph features) not implemented yet

---

## Trade-offs

| Trade-off | Choice | Rationale |
|-----------|--------|-----------|
| NetworkX vs. graph DB | NetworkX in-process v1.0 | Simplicity, testability; migrate when scale demands |
| Two graphs vs. one | Separate CKG and memory graph | Different lifecycles, schemas, and ownership |
| Typed entities vs. generic | 22 Pydantic subtypes | Domain validation and query safety worth maintenance cost |
| Query vs. reasoning split | Separate engines | Traversal algorithms independent of inference rule evolution |
| Seed data scope | India-first | Matches initial deployment; builder pattern supports expansion |
| Persistence | Snapshot serialization | Sufficient for v1.0; no live replication complexity |

---

## Consequences

- Agents query CKG during `_run_observe` / `_run_reason` for geographic and infrastructure context (when wired)
- Domain supervisors use `affected_agents()` and impact chains for routing beyond keyword matching
- `DecisionRequest` can be enriched with impact-chain-derived constraints and `need_other_agents` flags
- Memory manager graph remains session-scoped; CKG updates go through `GraphEngine` API only
- Tests in `backend/tests/knowledge_graph/` validate schema, query, reasoning, and builder

---

## Future Impact

- Live feed ingestion (forecasts, sensor data) via graph builder extensions or sync jobs
- External graph database migration path when entity count exceeds in-process limits
- RL state encoder augmentation with graph-derived features (centrality, cascade depth)
- XAI evidence enrichment from `ReasoningInsight` passed by agents at explanation time
- Regional graph builders beyond India (Southeast Asia, global climate corridors)
- Compound disaster workflows compose CKG reasoning with multi-agent supervisor orchestration
