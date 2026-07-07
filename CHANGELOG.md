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

## [0.2.0] — 2026-07-07

### Added

- **Specialized Agent Framework (Prompt 5)**
  - `BaseSpecializedAgent` enterprise lifecycle with reasoning, reflection, validation, tools, metrics, health
  - `AgentContext`, `ReasoningEngine`, `ReflectionEngine`, `AgentValidator`, `ToolManager`
  - `AgentExecutionEngine` with inter-agent delegation and `SpecializedRLEngineInterface`
  - `SpecializedAgentRegistry` for agent discovery
  - 10 framework tests (133 cumulative with prior layers)

- **Flood Agent (Prompt 6)**
  - Reference specialized agent: `FloodAgent` with 9 domain tools
  - Full pipeline: Observe → Analyze → Reason → Reflect → Validate → Decide → RL → Report
  - `FloodDecisionEngine`, `FloodReport`, Delhi and Mumbai integration scenarios
  - 23 flood tests (156 cumulative)

- **Water Resource Agent (Prompt 7)**
  - `WaterResourceAgent` for reservoir, drought, and allocation analysis
  - 10 domain tools, inter-agent coordination with flood/agriculture agents
  - 24 water resource tests (180 cumulative)

- **Decision Framework (Prompt 8)**
  - Unified `DecisionRequest` / `DecisionResponse` schemas in `backend/decision/`
  - `DecisionManager` with evaluate, compare, queue, prioritize, merge
  - `DecisionValidator`, `DecisionConstraints`, `DecisionPriority`, `DecisionSerializer`
  - `to_rl_payload()` standardization for RL integration
  - 38 decision tests (218 cumulative)

- **RL Optimization Service (Prompt 9)**
  - `RLOptimizationService.optimize(DecisionRequest) → DecisionResponse`
  - Agent-agnostic pipeline: state encoding, policy inference, reward estimation, constraint validation
  - `RLEngine`, `RLInference`, `PolicyManager`, `RewardEngine`, `RLMetricsCollector`
  - 26 RL tests (244 cumulative)

- **Heatwave Agent (Prompt 10)**
  - `HeatwaveAgent` with unified decision schema and direct RL service integration
  - 10 domain tools, UHI analysis, compound heat+AQI scenarios
  - Delhi, Ahmedabad integration test scenarios
  - 25 heatwave tests (269 cumulative)

- **Explainability Framework (Prompt 11)**
  - `ExplanationEngine` with `explain()`, `explain_pipeline()`, `explain_decision()`
  - `ExplainabilityReport` with reasoning trace, evidence, confidence, uncertainty, alternatives, counterfactuals
  - Sub-engines: `ConfidenceEngine`, `UncertaintyEngine`, `EvidenceEngine`, `ReasoningTraceBuilder`, `AlternativeActionsEngine`, `CounterfactualEngine`
  - 13 XAI tests (282 cumulative)

- **Climate Knowledge Graph (Prompt 12)**
  - `GraphEngine` with async CRUD, validation, export/import
  - Query APIs: `neighbors`, `shortest_path`, `impact_chain`, `affected_agents`, `related_events`, `historical_similarity`
  - `GraphReasoningEngine` for cascading failures and compound disasters
  - `ClimateGraphBuilder.build_india_climate_graph()` seed data
  - 24 CKG tests (306 cumulative)

- **Documentation (v0.2.0)**
  - Component docs for all Prompt 5–12 modules
  - Development logs 004–011
  - ADR-006 through ADR-010
  - System evolution, technical debt register, workflow diagrams
  - Bug history BUG-009 through BUG-017

### Changed

- `docs/README.md` updated with v0.2.0 progress, architecture, and test counts
- Heatwave agent uses unified `backend.decision` schemas (migration path for Flood/Water documented)
- RL integration standardized on `DecisionRequest` at service boundary

### Improved

- Inter-agent delegation with reciprocal flag consistency in Water Resource agent
- Heatwave decision engine vegetation signal accuracy (NDVI-derived `low_vegetation`)
- CKG query coverage for historical event relationships
- Test suite expanded from 124 to 306 tests (+147%)

### Fixed

- Flood `invoke()` signature mismatch with `BaseAgent` contract
- Water Resource reciprocal decision flags inconsistency
- Heatwave `low_vegetation or True` logic bug causing spurious tree plantation recommendations
- Missing `get_input_schema()` on all heatwave tools
- `heatwave_tools.py` file corruption from bad edit
- Decision Framework RL payload standardization via `to_rl_payload()`
- CKG self-reference validation failure in seed graph builder
- CKG `related_events` empty for RAINFALL entity types

### Architecture

- Three-tier hierarchy now populated with 3 specialized agents (flood, water, heatwave)
- Decision layer decouples agent reasoning from RL optimization
- Standalone Climate Knowledge Graph separate from memory-layer NetworkX graph
- Centralized explainability framework for audit-ready decision reports

### Documentation

- 8 new component documents under `docs/agents/`, `docs/decision/`, `docs/rl/`, `docs/xai/`, `docs/knowledge_graph/`
- 8 new development logs (004–011)
- 5 new ADRs (006–010)
- `docs/architecture/system_evolution.md` and `docs/engineering/technical_debt.md`

### Tests

- **306 tests passing** (182 new since v0.1.0)
- Specialized: 81 | Decision: 38 | RL: 26 | XAI: 13 | Knowledge Graph: 24

---

## [Unreleased]

### Planned

- Remaining specialized agents (cyclone, agriculture, air quality, urban, disaster response)
- Flood/Water migration to unified DecisionRequest
- `ClimateVariable.RIVER_DISCHARGE` enum fix for RL state encoder
- CKG wiring into agent context assembly
- Auto-invoke ExplanationEngine in agent pipelines
- Climate Copilot conversational interface
- Prithvi WxC API integration
- FastAPI HTTP layer
- PostgreSQL/PostGIS persistence
- Stable Baselines3 reinforcement learning
- Production Redis and Qdrant deployment configurations
