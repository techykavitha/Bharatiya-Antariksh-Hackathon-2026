# Changelog

All notable changes to the Hyperion Climate Twin AI layer are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2026-07-07

### Added

- **Project Foundation (Milestone 0)**
  - `BaseAgent` abstract lifecycle with LangGraph `as_graph_node()` integration
  - `AbstractTool` interface with validated execution pipeline
  - `AgentRequest` / `AgentResponse` Pydantic schemas
  - LangGraph-compatible `WorkflowState`, `ClimateState`, `ConversationState`
  - `GlobalConfig` with environment-variable loading (Pydantic Settings v2)
  - Structured logging via `structlog` wrapper (`Logger`)
  - Thread-safe `DependencyRegistry` for dependency injection
  - Shared enums, constants, and custom exception hierarchy
  - Reusable prompt templates (system, reasoning, planning, simulation, reflection)
  - Memory subsystem interfaces (`AgentMemory`, `RedisMemory`, `VectorMemory`, etc.)
  - Application bootstrap service (`backend/services/bootstrap.py`)
  - 20 foundation unit tests

- **Shared Memory Layer (Milestone 1)**
  - `MemoryManager` — unified memory facade for all agents
  - `RedisMemoryStore` with TTL, session indexing, and `InMemoryRedisClient` mock
  - `QdrantVectorMemory` with semantic/hybrid search and `InMemoryQdrantClient` mock
  - `NetworkXKnowledgeGraph` with typed nodes and edges
  - `DigitalTwinMemoryStore` with checkpoint, rollback, clone, compare, merge
  - `WorkingMemory`, `ConversationMemory`, `SessionMemory`
  - `HybridRetriever` fusing vector, graph, Redis, and climate context
  - `MemoryRanker` with weighted multi-factor scoring
  - `AsyncLRUMemoryCache` for hot-path reads
  - Pluggable `EmbeddingProvider` (deterministic + OpenAI adapter)
  - 64 memory subsystem tests (84 cumulative)

- **Climate Supervisor (Milestone 2)**
  - `ClimateSupervisor` LangGraph orchestration engine
  - `IntentClassifier` with 9 intent categories
  - `Planner`, `WorkflowRouter`, `Executor`, `ParallelExecutor`
  - `FailureHandler`, `WorkflowMonitor`, `StateManager`
  - `AgentRegistry` for domain supervisor discovery
  - `build_graph()` / `compile_graph()` / `run_graph()` LangGraph pipeline
  - `RLEngineInterface` and `DigitalTwinInterface` (interfaces only)
  - 22 supervisor tests (106 cumulative)

- **Domain Supervisors (Milestone 3)**
  - `BaseDomainSupervisor` with internal agent registry
  - `EnvironmentalSupervisor`, `InfrastructureSupervisor`, `EmergencySupervisor`
  - `DomainRegistry` for domain-level supervisor registration
  - `DomainExecutor` with sequential, parallel, conditional execution
  - 18 domain tests (124 cumulative)

- **Engineering Documentation (Milestone 4)**
  - Complete `docs/` documentation system
  - Architecture Decision Records (ADR-001 through ADR-005)
  - Development logs, test documentation, diagrams, progress tracker

### Changed

- Nothing in prior releases (initial release).

### Fixed

- Memory: Redis `expire()` parameter shadowing `time` module (`InMemoryRedisClient`)
- Memory: Session key extraction using incorrect `split(":", 2)` for multi-segment keys
- Memory: Vector search defaulting to wrong Qdrant collection — extended to multi-collection search
- Memory: LRU cache serving stale entries after Redis TTL expiry — cache invalidation on `set_ttl()`
- Memory: `DomainAgentResult` metadata field missing from model (domain layer)
- Supervisor: Circular import between `climate_supervisor.py` and `graph_builder.py` — lazy imports

### Removed

- Nothing.

### Deprecated

- Nothing.

---

## [Unreleased]

### Planned

- Specialized climate agents (flood, cyclone, heatwave, etc.)
- RL policy engine integration
- Climate Copilot conversational interface
- Prithvi WxC API integration
- FastAPI HTTP layer
- PostgreSQL/PostGIS persistence
- Stable Baselines3 reinforcement learning
- Production Redis and Qdrant deployment configurations
