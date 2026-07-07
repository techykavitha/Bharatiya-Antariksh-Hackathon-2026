# ADR-006: Specialized Agent Framework

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-07-07 |
| **Deciders** | Nexora Engineering |
| **Related** | [Specialized Agent Framework](../agents/specialized_framework.md), [ADR-002](./ADR-002_hierarchical_supervisors.md), [ADR-005](./ADR-005_domain_supervisors.md) |

---

## Context

ADR-002 and ADR-005 established a three-tier supervisor hierarchy with domain supervisors as the middle tier. Tier 3 requires specialized agents (flood, heatwave, water resource, cyclone, etc.) that share climate workflows—memory access, tool execution, reasoning, validation, delegation, RL handoff, and LangGraph embedding—without duplicating infrastructure per hazard.

Each hazard domain has distinct data sources, decision logic, and report formats. A monolithic agent base class cannot enforce a single pipeline ordering; flood analysis requires tools-before-reasoning, while a generic observe→reason→act sequence would produce under-evidenced recommendations.

---

## Decision

Introduce a **Specialized Agent Framework** in `backend/agents/specialized/` built on `BaseSpecializedAgent`, extending `BaseAgent` from the supervisor layer.

### Framework components

| Component | Module | Responsibility |
|-----------|--------|----------------|
| Context & reporting | `agent_context.py` | `AgentContext`, `AgentReport`, phase tracking, delegation/RL sub-contexts |
| Capabilities | `agent_capabilities.py` | `CapabilityRegistry` for discovery and routing keywords |
| Reasoning | `agent_reasoning.py` | Observe → Think → Act → Reflect → Verify lifecycle |
| Reflection | `agent_reflection.py` | Confidence-gated self-evaluation; delegation/RL signals |
| Validation | `agent_validator.py` | Schema and business-rule checks |
| Tools | `agent_tools.py` | `ToolManager` with sequential/parallel execution |
| Execution | `agent_execution.py` | `AgentExecutionEngine`, `SpecializedAgentHandler` protocol |
| Registry | `agent_registry.py` | App-level `SpecializedAgentRegistry` |
| Operations | `agent_health.py`, `agent_metrics.py` | Health reports and latency/throughput metrics |

### Domain agent pattern

Each hazard agent lives in its own subpackage (`flood/`, `heatwave/`, `water_resource/`) with a consistent 10-module layout: agent orchestrator, context, models, tools, reasoning, reflection, validator, decision engine, report, and metrics.

Domain agents **override `invoke()`** with an evidence-first pipeline:

```
Observe → Analyze (tools, parallel) → Reason → Reflect → Validate
→ Decision Engine → [delegate] → [RL] → Report → memory/state
```

Tools run **before** domain reasoning so inference is evidence-backed. Flood is the reference implementation.

### Registration model

- **App-level:** `SpecializedAgentRegistry.register(handler)` for bootstrap, health, and cross-domain discovery
- **Domain-level:** `InternalAgentRegistry` inside each `BaseDomainSupervisor` for production routing
- Agents are **stateless**; persistent state flows through `MemoryManager` and `WorkflowState`

### Integration contracts

- **Memory:** Only via `MemoryManager` (WORKING, VECTOR, CONVERSATION, CLIMATE domains)—no direct store access
- **Inter-agent:** `AgentCommunicationInterface` injected at construction; no implicit global agent calls
- **RL:** `SpecializedRLEngineInterface` (legacy) or unified `RLOptimizationService` (preferred; see ADR-008)
- **LangGraph:** `as_graph_node(WorkflowState)` converts workflow state to `AgentRequest`, invokes agent, merges updates

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Per-agent standalone classes without shared framework | Duplicated memory, tool, metrics, and LangGraph wiring across every hazard |
| Rigid template method with no `invoke()` override | Cannot enforce domain-specific tools-first ordering or decision engine placement |
| Plugin-only architecture (capabilities without base class) | No shared lifecycle, health, metrics, or supervisor protocol compliance |
| Domain logic in domain supervisors | Violates single responsibility; supervisors orchestrate, agents analyze |
| Global singleton registry for all routing | Bypasses domain isolation established in ADR-005 |

---

## Pros

- Shared infrastructure (context, tools, memory, metrics, health) across all hazard agents
- `BaseSpecializedAgent` default pipeline available for simpler future agents
- Domain agents override `invoke()` for hazard-specific evidence-first workflows
- Dual registry aligns with ADR-005 domain supervisor routing
- `SpecializedAgentHandler` protocol decouples registry from concrete implementations
- Abstract comm/RL interfaces keep framework independent of mesh and RL implementations
- Flood reference pattern accelerates onboarding for new hazard agents
- LangGraph subgraph embedding via `as_graph_node()` without custom glue per agent

---

## Cons

- Domain agents must maintain ~10 modules each; higher upfront cost than a single-file agent
- `AgentExecutionEngine` exists but is not wired into the main `invoke()` hot path yet
- Dual decision schemas persist: flood/water use local `DecisionRequest`; heatwave uses unified `backend.decision` (migration in progress)
- Dual RL paths coexist: legacy `SpecializedRLEngineInterface` vs `RLOptimizationService`
- Override of `invoke()` means framework default pipeline documentation can mislead new contributors
- Confidence-gated reflection thresholds (0.4–0.45) require per-domain tuning

---

## Trade-offs

| Trade-off | Choice | Rationale |
|-----------|--------|-----------|
| Flexibility vs. uniformity | Toolkit + override | Hazards differ too much for one rigid pipeline; shared components still reduce duplication |
| App vs. domain registry | Both | Global discovery/health vs. domain-isolated production routing |
| Synchronous pipeline vs. sub-plan engine | Explicit `_run_*` steps in domain agents | Simpler to debug today; `AgentExecutionEngine` reserved for future sub-plan orchestration |
| Local vs. unified decision schema | Migrating to unified | Flood/water shipped first with local engines; heatwave proves unified path |
| Stateless agents vs. in-agent cache | Stateless | Horizontal scaling and supervisor replay safety outweigh per-instance caching |

---

## Consequences

- New hazard agents must extend `BaseSpecializedAgent`, follow the 10-module layout, and register via domain supervisor
- Production routing goes through domain supervisors, not direct `SpecializedAgentRegistry` access
- Agents migrating to unified decision/RL must update `DecisionEngine` and RL injection (heatwave is reference)
- Tests for framework live in `backend/tests/`; flood tests serve as agent integration reference
- Documentation in `docs/agents/specialized_framework.md` is the canonical framework guide

---

## Future Impact

- New hazards (cyclone, air quality, urban planning) added by cloning flood pattern and registering agent slots in domain supervisors
- `AgentExecutionEngine` can replace explicit `_run_*` steps for complex multi-phase sub-plans without API changes
- Full migration to unified `DecisionRequest` and `RLOptimizationService` removes dual-schema technical debt
- LLM-based capability routing can replace keyword matching without changing agent internals
- Domain agents can be scaled independently behind supervisor load balancing
