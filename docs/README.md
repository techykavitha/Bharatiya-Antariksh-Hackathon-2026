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
