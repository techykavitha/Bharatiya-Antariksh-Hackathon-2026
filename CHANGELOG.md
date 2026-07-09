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

- Flood/Water migration to unified DecisionRequest
- `ClimateVariable.RIVER_DISCHARGE` enum fix for RL state encoder
- FastAPI HTTP layer
- Climate Copilot conversational interface
- Prithvi WxC API integration / Scenario Simulation Engine
- PostgreSQL/PostGIS persistence
- Stable Baselines3 reinforcement learning
- Production Redis and Qdrant deployment configurations
- CesiumJS digital twin visualization

---

## [0.3.0] — 2026-07-09

### Added

- **Cyclone Agent (Prompt 13)**
  - `CycloneAgent` with 12 domain tools (SST, pressure, wind, ocean heat, INSAT, storm surge, etc.)
  - `DecisionType.CYCLONE`, EmergencySupervisor registration
  - India scenarios: Odisha Fani, Gujarat Tauktae, Chennai coastal, Bengal landfall
  - 24 cyclone tests (12 unit + 12 integration)

- **Disaster Response Agent (Prompt 14)**
  - `DisasterResponseAgent` multi-hazard coordination meta-agent
  - 11 domain tools, live hazard consultation via `call_agent()`
  - `DecisionType.DISASTER`, EmergencySupervisor registration
  - 16 disaster response tests (7 unit + 9 integration)

- **Urban Planning Agent (Prompt 15)**
  - `UrbanPlanningAgent` for long-term climate adaptation planning
  - 11 domain tools, resilience scoring, investment prioritization
  - `DecisionType.URBAN`, InfrastructureSupervisor registration
  - Scenarios: Chennai flooding, Delhi UHI, Bengaluru green cover, Hyderabad drainage
  - 16 urban planning tests (7 unit + 9 integration)

- **Agriculture Agent (Prompt 16)**
  - `AgricultureAgent` precision agriculture with provider-agnostic RAG
  - `agriculture_rag.py` — `AgricultureKnowledgeRetriever` protocol, `InMemoryAgricultureRAG`
  - 12 domain tools + RAG retrieval step in workflow
  - `DecisionType.AGRICULTURE`, InfrastructureSupervisor registration
  - Scenarios: Punjab wheat, Tamil Nadu paddy, Maharashtra cotton, Karnataka drought
  - 17 agriculture tests (8 unit + 9 integration)

- **Air Quality Agent (Prompt 17)**
  - `AirQualityAgent` atmospheric pollution and environmental health
  - CPCB AQI sub-index calculation, 12 domain tools
  - `DecisionType.AQI`, EnvironmentalSupervisor registration
  - Scenarios: Delhi severe, Punjab stubble, Rajasthan dust, Mumbai coastal
  - 17 air quality tests (8 unit + 9 integration)

- **Documentation (v0.3.0)**
  - 5 component docs, 5 development logs (012–016), 5 ADRs (011–015)
  - `specialized_agents_overview.md`, `backend_architecture_status.md`
  - Workflow diagrams for all new agents, supervisor hierarchy, agent interaction map
  - Bug history BUG-018 through BUG-024

### Changed

- `docs/README.md` updated with v0.3.0 progress (396 tests, 8/8 agents)
- All Prompt 13–17 agents use two-batch tool execution when tool count > 10
- CKG queried in observe phase for all new agents with region_id fallbacks

### Improved

- Inter-agent peer consultation tested across all new agents
- XAI full pipeline on Cyclone, Disaster, Urban, Agriculture, Air Quality
- Agriculture reasoning fallbacks when tools not executed (unit test compatibility)
- Air Quality reasoning input fallbacks for dust/biomass detection without tools

### Fixed

- Cyclone tool batching for 12-tool agents (BUG-018)
- CKG entity fallback when region_id not in seed graph (BUG-019)
- Heatwave/urban/cyclone air quality peer coordination (BUG-020)
- Agriculture critical deficit not setting `water_stress` (BUG-021)
- Air Quality `Objective` schema validation in decision engine (BUG-022)
- Air Quality XAI counterfactual string extraction (BUG-023)
- Air Quality PM biomass burning indicator threshold (BUG-024)

### Architecture

- **All 8 specialized agent slots now implemented** across Environmental, Infrastructure, and Emergency supervisors
- Agriculture introduces provider-agnostic RAG as first knowledge retrieval layer in specialized agents
- Urban Planning positioned as scenario intelligence foundation for future Simulation Engine
- Disaster Response operates as meta-agent coordinating hazard-specific agents

### Documentation

- 5 new agent component docs under `docs/agents/`
- 5 new development logs (012–016)
- 5 new ADRs (011–015)
- 7 new workflow/architecture diagrams
- `specialized_agents_overview.md` and `backend_architecture_status.md`

### Tests

- **396 tests passing** (+90 since v0.2.0)
- Cyclone: 24 | Disaster: 16 | Urban: 16 | Agriculture: 17 | Air Quality: 17
