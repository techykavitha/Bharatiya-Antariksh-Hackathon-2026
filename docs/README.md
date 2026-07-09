# Hyperion Climate Twin — Engineering Documentation

> **Document Status:** Active  
> **Last Updated:** 2026-07-07  
> **Version:** 0.1.0  
> **Maintainer:** Nexora Engineering

---

## Purpose of This Documentation

This documentation system is the authoritative engineering record for the Hyperion Climate Twin AI layer. It is designed for long-term maintainability: a developer joining six months from now should be able to understand what was built, why it was built, how to extend it, and what remains unfinished.

**This documentation grows after every implementation.** See [Documentation Growth Protocol](./engineering/documentation_growth_protocol.md).

---

## Project Vision

Hyperion Climate Twin is an enterprise-grade AI platform for climate intelligence, digital twin modeling, and multi-hazard decision support. The AI layer provides:

- A **hierarchical multi-agent system** orchestrated via LangGraph
- A **unified memory architecture** spanning Redis, Qdrant, NetworkX, and in-process stores
- **Domain-aware supervision** for environmental, infrastructure, and emergency workflows
- Extensibility for specialized agents, RL policy optimization, and simulation engines

The long-term goal is a production system serving scientists, emergency responders, and policy decision-makers with grounded, auditable climate intelligence.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     User / API (Future)                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                   Climate Supervisor (LangGraph)                   │
│   classify → plan → execute → merge → memory → respond          │
└──────┬──────────────────┬──────────────────┬────────────────────┘
       │                  │                  │
┌──────▼──────┐  ┌────────▼────────┐  ┌─────▼──────┐
│Environmental│  │ Infrastructure  │  │ Emergency  │
│ Supervisor  │  │  Supervisor     │  │ Supervisor │
└──────┬──────┘  └────────┬────────┘  └─────┬──────┘
       │                  │                  │
┌──────▼──────────────────▼──────────────────▼────────────────────┐
│              Specialized Agents (Future)                         │
│   flood │ cyclone │ agriculture │ water │ urban │ disaster     │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      MemoryManager                                 │
│  Redis │ Qdrant │ NetworkX │ DigitalTwin │ Working │ Session     │
└───────────────────────────────────────────────────────────────────┘
```

See [Architecture Diagrams](./diagrams/) for detailed Mermaid diagrams.

---

## Current Progress

| Milestone | Component | Status | Tests | Version |
|-----------|-----------|--------|-------|---------|
| M0 | Project Foundation | ✅ Complete | 20 | 0.1.0 |
| M1 | Shared Memory Layer | ✅ Complete | 64 | 0.1.0 |
| M2 | Climate Supervisor | ✅ Complete | 22 | 0.1.0 |
| M3 | Domain Supervisors | ✅ Complete | 18 | 0.1.0 |
| M4 | Engineering Documentation | ✅ Complete | — | 0.1.0 |
| M5 | Specialized Agents | ⬜ Not Started | — | — |
| M6 | RL Engine | ⬜ Not Started | — | — |
| M7 | Climate Copilot | ⬜ Not Started | — | — |
| M8 | Simulation Engine | ⬜ Not Started | — | — |
| M9 | FastAPI / Deployment | ⬜ Not Started | — | — |

**Total automated tests passing:** 124 (as of 2026-07-07)

---

## Completed Components

| Component | Location | Documentation |
|-----------|----------|---------------|
| Base Agent & Tools | `backend/agents/base/`, `tools/` | [agents/foundation.md](./agents/foundation.md) |
| State Definitions | `backend/agents/state/` | [architecture/state_management.md](./architecture/state_management.md) |
| Configuration & DI | `backend/config/` | [architecture/configuration.md](./architecture/configuration.md) |
| Shared Memory | `backend/agents/memory/` | [memory/shared_memory.md](./memory/shared_memory.md) |
| Climate Supervisor | `backend/agents/supervisor/` | [supervisor/climate_supervisor.md](./supervisor/climate_supervisor.md) |
| Domain Supervisors | `backend/agents/domain/` | [domain/domain_supervisors.md](./domain/domain_supervisors.md) |

---

## Pending Components

| Component | Blocked By | Estimated Effort |
|-----------|-----------|------------------|
| Flood Agent | Domain supervisor registration | 2–3 days |
| Cyclone Agent | Domain supervisor registration | 2–3 days |
| Heatwave Agent | Domain supervisor registration | 2 days |
| Agriculture Agent | Domain supervisor registration | 2 days |
| Water Resource Agent | Domain supervisor registration | 2 days |
| RL Engine | Simulation engine, policy schema | 1–2 weeks |
| Climate Copilot | Specialized agents, FastAPI | 1–2 weeks |
| Simulation Engine | Prithvi WxC APIs, PostGIS | 2–3 weeks |
| FastAPI Layer | Core agent wiring complete | 3–5 days |
| Production Deployment | FastAPI, infra provisioning | 1 week |

---

## Milestone Timeline

```
2026-Q3  [████████████████░░░░░░░░] Foundation + Memory + Supervisor + Domain
2026-Q4  [░░░░░░░░░░░░░░░░████████] Specialized Agents + Simulation
2027-Q1  [░░░░░░░░░░░░░░░░░░░░████] RL + Copilot + Production Deployment
```

| Date | Milestone | Deliverable |
|------|-----------|-------------|
| 2026-07-07 | M0 | Project foundation, 20 tests |
| 2026-07-07 | M1 | Shared memory layer, 84 tests |
| 2026-07-07 | M2 | Climate supervisor, 106 tests |
| 2026-07-07 | M3 | Domain supervisors, 124 tests |
| 2026-07-07 | M4 | Engineering documentation |
| TBD | M5 | First specialized agent (flood) |
| TBD | M6 | RL engine interface implementation |
| TBD | M7 | Climate Copilot MVP |
| TBD | M8 | Simulation engine |
| TBD | M9 | FastAPI + production deployment |

---

## Repository Structure

```
Hyperion/
├── backend/
│   ├── agents/
│   │   ├── base/           # BaseAgent abstract class
│   │   ├── domain/         # Domain supervisors (Environmental, Infrastructure, Emergency)
│   │   ├── memory/         # MemoryManager and all memory backends
│   │   ├── prompts/        # Reusable prompt templates
│   │   ├── schemas/        # AgentRequest, AgentResponse
│   │   ├── specialized/    # (empty — future specialized agents)
│   │   ├── state/          # WorkflowState, ClimateState, ConversationState
│   │   ├── supervisor/     # ClimateSupervisor orchestration
│   │   └── tools/          # AbstractTool interface
│   ├── config/             # GlobalConfig, Logger, DependencyRegistry
│   ├── services/           # Application bootstrap
│   ├── tests/              # 124 automated tests
│   └── utils/              # Enums, constants, errors
├── docs/                   # This documentation system
├── assets/                 # Branding assets
├── CHANGELOG.md
├── pyproject.toml
└── requirements.txt
```

---

## Development Workflow

1. **Read** the relevant component documentation and ADRs before implementing.
2. **Implement** in the appropriate `backend/` module without modifying unrelated code.
3. **Write tests** in `backend/tests/` mirroring the module structure.
4. **Run** `PYTHONPATH=. python -m pytest backend/tests -v` — all tests must pass.
5. **Document** by creating/updating the development log in `docs/development_logs/`.
6. **Update** `CHANGELOG.md`, progress tracker, and component docs.
7. **Do not commit** unless explicitly requested by the project owner.

See [Development Workflow](./engineering/development_workflow.md) for full details.

---

## Coding Standards

| Standard | Requirement |
|----------|-------------|
| Python version | 3.12+ (see `pyproject.toml`) |
| Typing | Strict typing; Pydantic v2 for schemas |
| Async | All I/O-bound operations must be `async` |
| SOLID | Single responsibility per module |
| Documentation | Docstrings on all public classes and methods |
| Linting | `ruff` target `py312`, line length 100 |
| Type checking | `mypy` strict mode |
| Imports | Absolute imports from `backend.*` |
| Memory access | **Only** through `MemoryManager` — never direct Redis/Qdrant |
| Agent access | **Only** through supervisor hierarchy |

See [Coding Standards](./engineering/coding_standards.md).

---

## Testing Standards

| Requirement | Detail |
|-------------|--------|
| Framework | `pytest` with `pytest-asyncio` (`asyncio_mode = auto`) |
| Location | `backend/tests/` mirroring source structure |
| Mocks | In-memory clients for Redis, Qdrant, NetworkX |
| Coverage | All public APIs must have unit tests |
| Integration | Cross-module flows tested via `MemoryManager` and supervisor `process_request()` |
| CI gate | 100% of tests must pass before merge |
| Naming | `test_<behavior>_<condition>` |

See [Testing Documentation](./testing/README.md).

---

## Documentation Standards

| Rule | Detail |
|------|--------|
| Format | Markdown with Mermaid diagrams where applicable |
| Location | `docs/` hierarchy — never inline in source code |
| Growth | New implementation → new development log + component doc update |
| ADRs | Required for architectural decisions |
| Tables | Required for test results, APIs, and comparisons |
| Versioning | Semantic versioning in `CHANGELOG.md` |
| Status tags | `✅ Complete`, `🔄 In Progress`, `⬜ Not Started`, `🚫 Blocked` |

See [Documentation Growth Protocol](./engineering/documentation_growth_protocol.md).

---

## Quick Navigation

| Topic | Document |
|-------|----------|
| Agent foundation | [agents/foundation.md](./agents/foundation.md) |
| Memory architecture | [memory/shared_memory.md](./memory/shared_memory.md) |
| Climate supervisor | [supervisor/climate_supervisor.md](./supervisor/climate_supervisor.md) |
| Domain supervisors | [domain/domain_supervisors.md](./domain/domain_supervisors.md) |
| Architecture decisions | [decisions/](./decisions/) |
| Development history | [development_logs/](./development_logs/) |
| Test results | [testing/](./testing/) |
| Diagrams | [diagrams/](./diagrams/) |
| Progress tracker | [engineering/progress_tracker.md](./engineering/progress_tracker.md) |
| Changelog | [../CHANGELOG.md](../CHANGELOG.md) |
| Specialized agents overview | [agents/specialized_agents_overview.md](./agents/specialized_agents_overview.md) |
| Backend architecture status | [architecture/backend_architecture_status.md](./architecture/backend_architecture_status.md) |

---

## Version 0.2.0 Update (2026-07-07)

> **Supplemental section.** All v0.1.0 content above is preserved. This section reflects engineering work completed in Prompts 5–12.

### Current Progress (v0.2.0)

| Milestone | Component | Status | Tests | Version |
|-----------|-----------|--------|-------|---------|
| M0 | Project Foundation | ✅ Complete | 20 | 0.1.0 |
| M1 | Shared Memory Layer | ✅ Complete | 64 | 0.1.0 |
| M2 | Climate Supervisor | ✅ Complete | 22 | 0.1.0 |
| M3 | Domain Supervisors | ✅ Complete | 18 | 0.1.0 |
| M4 | Engineering Documentation | ✅ Complete | — | 0.1.0 |
| M5a | Specialized Agent Framework | ✅ Complete | 10 | 0.2.0 |
| M5b | Flood Agent | ✅ Complete | 23 | 0.2.0 |
| M5c | Water Resource Agent | ✅ Complete | 24 | 0.2.0 |
| M5d | Heatwave Agent | ✅ Complete | 25 | 0.2.0 |
| M5e | Decision Framework | ✅ Complete | 38 | 0.2.0 |
| M6 | RL Optimization Service | ✅ Complete | 26 | 0.2.0 |
| M7a | Explainability Framework | ✅ Complete | 13 | 0.2.0 |
| M7b | Climate Knowledge Graph | ✅ Complete | 24 | 0.2.0 |
| M8 | Climate Copilot | ⬜ Not Started | — | — |
| M9 | Simulation Engine | ⬜ Not Started | — | — |
| M10 | FastAPI / Deployment | ⬜ Not Started | — | — |

**Total automated tests passing:** 306 (as of 2026-07-07)

**Estimated project completion:** ~62%

### Completed Components (v0.2.0 additions)

| Component | Location | Documentation |
|-----------|----------|---------------|
| Specialized Agent Framework | `backend/agents/specialized/` | [agents/specialized_framework.md](./agents/specialized_framework.md) |
| Flood Agent | `backend/agents/specialized/flood/` | [agents/flood_agent.md](./agents/flood_agent.md) |
| Water Resource Agent | `backend/agents/specialized/water_resource/` | [agents/water_resource_agent.md](./agents/water_resource_agent.md) |
| Heatwave Agent | `backend/agents/specialized/heatwave/` | [agents/heatwave_agent.md](./agents/heatwave_agent.md) |
| Decision Framework | `backend/decision/` | [decision/decision_framework.md](./decision/decision_framework.md) |
| RL Optimization Service | `backend/rl/` | [rl/rl_optimization_service.md](./rl/rl_optimization_service.md) |
| Explainability Framework | `backend/xai/` | [xai/explainability_framework.md](./xai/explainability_framework.md) |
| Climate Knowledge Graph | `backend/knowledge_graph/` | [knowledge_graph/climate_knowledge_graph.md](./knowledge_graph/climate_knowledge_graph.md) |

### Architecture Overview (v0.2.0)

See [System Evolution](./architecture/system_evolution.md) for the full Mermaid timeline. The specialized agent tier, decision framework, RL service, explainability layer, and climate knowledge graph now sit between domain supervisors and the memory layer.

### Repository Structure (v0.2.0 additions)

New backend modules: `agents/specialized/`, `decision/`, `rl/`, `xai/`, `knowledge_graph/`. Test count: **306**.

### Technology Stack (v0.2.0)

NetworkX DiGraph for CKG; in-memory heuristic RL policies (Stable Baselines3 planned); centralized XAI via `ExplanationEngine`.

### Development Timeline (v0.2.0 additions)

| Date | Milestone | Deliverable |
|------|-----------|-------------|
| 2026-07-07 | M5a–M7b | Framework, 3 agents, decision, RL, XAI, CKG — 306 tests |

### Current AI Architecture (v0.2.0)

8-tier stack: Foundation → Memory → Orchestration → Specialized Agents → Decision → RL → XAI → Knowledge Graph.

### Current Specialized Agents

| Agent ID | Domain | Status | Tests |
|----------|--------|--------|-------|
| `flood_agent` | Environmental | ✅ | 23 |
| `water_resource_agent` | Infrastructure | ✅ | 24 |
| `heatwave_agent` | Environmental | ✅ | 25 |
| 5 remaining slots | Various | ⬜ Declared | — |

### Current Test Counts (v0.2.0)

| Layer | Tests |
|-------|-------|
| Foundation + Memory + Supervisor + Domain | 124 |
| Specialized (framework + agents) | 82 |
| Decision | 38 |
| RL | 26 |
| XAI | 13 |
| CKG | 24 |
| **Total** | **306** |

### Current Documentation Status (v0.2.0)

14 component docs, 12 development logs, 10 ADRs, 15+ diagrams, technical debt register, system evolution doc.

### Quick Navigation (v0.2.0 additions)

| Topic | Document |
|-------|----------|
| Specialized framework | [agents/specialized_framework.md](./agents/specialized_framework.md) |
| Flood agent | [agents/flood_agent.md](./agents/flood_agent.md) |
| Water resource agent | [agents/water_resource_agent.md](./agents/water_resource_agent.md) |
| Heatwave agent | [agents/heatwave_agent.md](./agents/heatwave_agent.md) |
| Decision framework | [decision/decision_framework.md](./decision/decision_framework.md) |
| RL optimization | [rl/rl_optimization_service.md](./rl/rl_optimization_service.md) |
| Explainability | [xai/explainability_framework.md](./xai/explainability_framework.md) |
| Climate knowledge graph | [knowledge_graph/climate_knowledge_graph.md](./knowledge_graph/climate_knowledge_graph.md) |
| System evolution | [architecture/system_evolution.md](./architecture/system_evolution.md) |
| Technical debt | [engineering/technical_debt.md](./engineering/technical_debt.md) |

---

## Version 0.3.0 Update (2026-07-09)

> **Supplemental section.** All v0.1.0 and v0.2.0 content above is preserved. This section reflects engineering work completed in Prompts 13–17.

### Current Progress (v0.3.0)

| Milestone | Component | Status | Tests | Version |
|-----------|-----------|--------|-------|---------|
| M0–M7b | Foundation through CKG | ✅ Complete | 306 | 0.2.0 |
| M5f | Cyclone Agent | ✅ Complete | 24 | 0.3.0 |
| M5g | Disaster Response Agent | ✅ Complete | 16 | 0.3.0 |
| M5h | Urban Planning Agent | ✅ Complete | 16 | 0.3.0 |
| M5i | Agriculture Agent | ✅ Complete | 17 | 0.3.0 |
| M5j | Air Quality Agent | ✅ Complete | 17 | 0.3.0 |
| M8 | Climate Copilot | ⬜ Not Started | — | — |
| M9 | Simulation Engine | ⬜ Not Started | — | — |
| M10 | FastAPI / Deployment | ⬜ Not Started | — | — |

**Total automated tests passing:** 396 (as of 2026-07-09)

**Estimated project completion:** ~78%

**Backend AI layer completion:** ~85%

### Completed Components (v0.3.0 additions)

| Component | Location | Documentation |
|-----------|----------|---------------|
| Cyclone Agent | `backend/agents/specialized/cyclone/` | [agents/cyclone_agent.md](./agents/cyclone_agent.md) |
| Disaster Response Agent | `backend/agents/specialized/disaster_response/` | [agents/disaster_response_agent.md](./agents/disaster_response_agent.md) |
| Urban Planning Agent | `backend/agents/specialized/urban_planning/` | [agents/urban_planning_agent.md](./agents/urban_planning_agent.md) |
| Agriculture Agent | `backend/agents/specialized/agriculture/` | [agents/agriculture_agent.md](./agents/agriculture_agent.md) |
| Air Quality Agent | `backend/agents/specialized/air_quality/` | [agents/air_quality_agent.md](./agents/air_quality_agent.md) |
| Specialized Agents Overview | `docs/agents/` | [agents/specialized_agents_overview.md](./agents/specialized_agents_overview.md) |
| Backend Architecture Status | `docs/architecture/` | [architecture/backend_architecture_status.md](./architecture/backend_architecture_status.md) |

### Current AI Architecture (v0.3.0)

All **8 specialized agent slots** are now implemented across three domain supervisors. Every new agent (Prompts 13–17) adopts the unified `DecisionRequest` schema, `RLOptimizationService`, `ExplanationEngine`, and `GraphEngine` integration patterns established in v0.2.0. Agriculture adds a provider-agnostic RAG layer (`agriculture_rag.py`). Urban Planning is positioned as long-term scenario intelligence for future What-If Simulation.

### Repository Structure (v0.3.0 additions)

```
backend/agents/specialized/
├── cyclone/              # 12 tools, EmergencySupervisor
├── disaster_response/    # 11 tools, EmergencySupervisor
├── urban_planning/       # 11 tools, InfrastructureSupervisor
├── agriculture/          # 12 tools + RAG, InfrastructureSupervisor
└── air_quality/          # 12 tools, EnvironmentalSupervisor
```

Test count: **396** (+90 since v0.2.0).

### Technology Stack (v0.3.0)

No new runtime dependencies. Agriculture RAG uses protocol-based `AgricultureKnowledgeRetriever` with `InMemoryAgricultureRAG` seed corpus. Air Quality uses CPCB AQI sub-index calculation. All agents use two-batch tool execution when tool count exceeds 10.

### Current Specialized Agents (v0.3.0)

| Agent ID | Domain Supervisor | Status | Tests | DecisionType |
|----------|-------------------|--------|-------|--------------|
| `flood_agent` | Environmental | ✅ | 23 | FLOOD |
| `heatwave_agent` | Environmental | ✅ | 25 | HEATWAVE |
| `air_quality_agent` | Environmental | ✅ | 17 | AQI |
| `water_resource_agent` | Infrastructure | ✅ | 24 | WATER |
| `urban_planning_agent` | Infrastructure | ✅ | 16 | URBAN |
| `agriculture_agent` | Infrastructure | ✅ | 17 | AGRICULTURE |
| `cyclone_agent` | Emergency | ✅ | 24 | CYCLONE |
| `disaster_response_agent` | Emergency | ✅ | 16 | DISASTER |

### Current Test Counts (v0.3.0)

| Layer | Tests |
|-------|-------|
| Foundation + Memory + Supervisor + Domain | 124 |
| Specialized framework | 10 |
| Flood + Water + Heatwave | 72 |
| Cyclone + Disaster + Urban + Agriculture + Air Quality | 90 |
| Decision | 38 |
| RL | 26 |
| XAI | 13 |
| CKG | 24 |
| **Total** | **396** |

### Current Sprint Status (v0.3.0)

| ID | Task | Status |
|----|------|--------|
| AGT-03 | Cyclone Agent (Prompt 13) | ✅ Complete |
| AGT-04 | Disaster Response Agent (Prompt 14) | ✅ Complete |
| AGT-05 | Urban Planning Agent (Prompt 15) | ✅ Complete |
| AGT-06 | Agriculture Agent (Prompt 16) | ✅ Complete |
| AGT-07 | Air Quality Agent (Prompt 17) | ✅ Complete |
| DOC-03 | v0.3.0 documentation (Prompts 13–17) | ✅ Complete |

### Backend Completion Status

| Area | Status |
|------|--------|
| Specialized agent tier (8/8) | ✅ Complete |
| Decision + RL + XAI + CKG integration | ✅ Complete (all 5 new agents) |
| Flood/Water schema migration | ⬜ Pending |
| Climate Copilot | ⬜ Not started |
| Simulation Engine | ⬜ Not started |
| FastAPI layer | ⬜ Not started |

### Architecture Maturity (v0.3.0)

| Dimension | Score | Notes |
|-----------|-------|-------|
| Agent patterns | 5/5 | Consistent `BaseSpecializedAgent` pipeline across all 8 agents |
| Decision integration | 4/5 | Unified schema; Flood/Water still on local schemas |
| Inter-agent communication | 4/5 | `call_agent()` wired; live delegation tested |
| Knowledge graph | 4/5 | CKG queried in observe phase for all new agents |
| Explainability | 4/5 | Full pipeline XAI on all Prompt 13–17 agents |
| Production readiness | 3/5 | No API layer, mock RL in tests, heuristic policies |
| **Overall** | **4.2/5** | Hackathon-ready via direct agent invocation |

### Quick Navigation (v0.3.0 additions)

| Topic | Document |
|-------|----------|
| Cyclone agent | [agents/cyclone_agent.md](./agents/cyclone_agent.md) |
| Disaster response agent | [agents/disaster_response_agent.md](./agents/disaster_response_agent.md) |
| Urban planning agent | [agents/urban_planning_agent.md](./agents/urban_planning_agent.md) |
| Agriculture agent | [agents/agriculture_agent.md](./agents/agriculture_agent.md) |
| Air quality agent | [agents/air_quality_agent.md](./agents/air_quality_agent.md) |
| Specialized agents overview | [agents/specialized_agents_overview.md](./agents/specialized_agents_overview.md) |
| Backend architecture status | [architecture/backend_architecture_status.md](./architecture/backend_architecture_status.md) |
| Agent interaction map | [diagrams/agent_interaction_map.md](./diagrams/agent_interaction_map.md) |
| Supervisor architecture | [diagrams/supervisor_agent_hierarchy.md](./diagrams/supervisor_agent_hierarchy.md) |
| Cyclone agent | [agents/cyclone_agent.md](./agents/cyclone_agent.md) |
| Disaster response agent | [agents/disaster_response_agent.md](./agents/disaster_response_agent.md) |
| Urban planning agent | [agents/urban_planning_agent.md](./agents/urban_planning_agent.md) |
| Agriculture agent | [agents/agriculture_agent.md](./agents/agriculture_agent.md) |
| Air quality agent | [agents/air_quality_agent.md](./agents/air_quality_agent.md) |
