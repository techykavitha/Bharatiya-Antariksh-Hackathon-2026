# ADR-007: Unified Decision Framework

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-07-07 |
| **Deciders** | Nexora Engineering |
| **Related** | [Decision Framework](../decision/decision_framework.md), [ADR-006](./ADR-006_specialized_agent_framework.md), [ADR-008](./ADR-008_rl_optimization_service.md) |

---

## Context

Specialized agents (ADR-006) each need to propose climate actions—evacuations, reservoir releases, cooling centers, irrigation cuts—with objectives, constraints, risk assessments, and ranked alternatives. Early implementations (flood, water resource) embedded decision schemas inside agent context modules. Heatwave adopted a separate unified model.

This fragmentation blocks shared RL optimization (ADR-008), explainability over decisions (ADR-009), persistence, multi-agent merge, and supervisor priority queuing. Downstream systems cannot consume agent output without per-domain adapters.

---

## Decision

Introduce a **unified Decision Framework** in `backend/decision/` as an agent-agnostic contract layer. Every specialized agent produces the same `DecisionRequest`; orchestration, RL, XAI, and persistence consume it without domain-specific schemas.

### Core schema

| Model | Module | Role |
|-------|--------|------|
| `DecisionRequest` | `decision_request.py` | Canonical input: actions, objectives, constraints, context, orchestration flags |
| `DecisionResponse` | `decision_response.py` | Chosen action, ranking, rejections, reward, confidence |
| `DecisionContext` | `decision_context.py` | Scenario, climate state refs, forecast/simulation links |
| `DecisionAction` | `decision_actions.py` | Action definitions with parameters and metadata |
| Constraints | `decision_constraints.py` | Eight typed categories: budget, time, water, power, population, environment, policy, safety |
| Types & priority | `decision_types.py`, `decision_priority.py` | Domain enums, escalation, async priority queue |

### Central orchestration

`DecisionManager` provides the lifecycle API:

- `create()` / `create_from_builder()` — construct and validate requests
- `validate()` — boundary checks (soft and strict modes)
- `merge()` — combine multi-agent decisions
- `queue()` / `dequeue()` — async max-heap priority queue on `(priority, confidence, decision_id)`
- `serialize()` — JSON, Pydantic, and flat DB record formats via `DecisionSerializer`

### Orchestration flags

`DecisionRequest` exposes routing flags consumed by supervisors and downstream services:

- `need_rl` — hand off to RL optimization
- `need_simulation` — trigger digital twin / forecast simulation
- `need_human` — escalate for human-in-the-loop approval
- `need_other_agents` — request inter-agent coordination

### RL payload sanitization

`DecisionRequest.to_rl_payload()` strips agent identity, metadata, and rationale before RL encoding so the optimization layer remains agent-agnostic.

### Architectural boundary

`backend/decision/` must **not** import specialized agent modules. The only upstream dependency is `ClimateState` from the shared agent state layer.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Per-agent decision schemas | Blocks RL, XAI, persistence, and merge; adapter sprawl |
| Decision logic inside `DecisionManager` | Violates separation—agents decide *what*; manager handles *lifecycle* |
| JSON Schema only (no Pydantic models) | Loses type safety, builder patterns, and in-process validation |
| Single flat action list without constraints | Cannot express operational limits shared by validation and RL filtering |
| Embedded decision engine per hazard forever | Heatwave migration proves unified path; debt compounds with each new agent |

---

## Pros

- Single contract for all specialized agents and downstream consumers
- Typed constraints enable shared validation and RL pre-filtering
- `DecisionManager` unifies create, validate, serialize, merge, and queue in one facade
- Orchestration flags drive supervisor routing without domain-specific branching
- `to_rl_payload()` enforces RL agent-agnosticism at the boundary
- Multi-format serialization supports API wire format, in-process use, and DB persistence
- Priority queue supports emergency escalation without custom supervisor logic

---

## Cons

- Flood and water resource agents still use local decision engines; migration incomplete
- `DecisionContext.from_climate_state()` creates a dependency from decision layer to agent state
- Strict validation mode may reject partially specified requests during agent development
- Merge semantics for conflicting multi-agent decisions require careful priority rules
- Flat DB serialization loses nested structure; round-trip requires explicit deserialization

---

## Trade-offs

| Trade-off | Choice | Rationale |
|-----------|--------|-----------|
| Rich schema vs. simplicity | Rich typed schema | Climate decisions need constraints, risk, and objectives; flat payloads insufficient |
| Validation strictness | Soft default, strict at boundaries | Agents iterate quickly; queue and RL handoff enforce hard validation |
| Manager scope | Lifecycle only, not decision logic | Keeps agent domain expertise in agent decision engines |
| Climate state coupling | Accept `ClimateState` import | Shared state model cheaper than duplicating climate context in decision layer |
| Queue vs. synchronous | Async priority queue | Supports emergency preemption without blocking supervisor event loop |

---

## Consequences

- Heatwave is the reference integration: `HeatwaveDecisionEngine` → `DecisionManager` → `RLOptimizationService`
- Flood and water resource must migrate local `DecisionRequest` types to `backend.decision`
- RL service (ADR-008) and XAI (ADR-009) depend on this schema; partial migration limits their coverage
- Persistence tables (`decision_requests`, `decision_responses`) use `DecisionSerializer` flat records
- New agents must use `DecisionManager.create_from_builder()` or equivalent; no new local decision schemas

---

## Future Impact

- Full agent migration removes per-domain decision adapters and enables uniform audit trails
- Supervisor workflows can merge decisions from multiple agents in the same hazard event
- Human-in-the-loop gates keyed on `need_human` and decision priority
- Policy engine can inject constraints at `DecisionManager.create()` without agent changes
- Simulation service integration via `need_simulation` flag and `DecisionContext` scenario refs
