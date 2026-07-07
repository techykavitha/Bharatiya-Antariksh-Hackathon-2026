# ADR-002: Hierarchical Multi-Agent Supervision

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-07-07 |
| **Deciders** | Nexora Engineering |
| **Related** | [Climate Supervisor](../supervisor/climate_supervisor.md), [Domain Supervisors](../domain/domain_supervisors.md) |

---

## Context

Climate intelligence workflows span multiple hazard domains (flood, cyclone, agriculture, water, emergency). A single monolithic agent cannot maintain expertise across all domains. Flat multi-agent systems (all agents equal peers) create routing complexity and lack domain context isolation.

---

## Decision

Implement a **three-tier hierarchical supervision model**:

```
Tier 1: Climate Supervisor     — intent, planning, cross-domain routing
Tier 2: Domain Supervisors     — Environmental, Infrastructure, Emergency
Tier 3: Specialized Agents     — flood, cyclone, agriculture, etc. (future)
```

Each tier communicates only with its direct parent and children. Memory flows through `MemoryManager` at every tier.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Flat agent pool | No domain isolation; routing complexity grows O(n²) |
| Single super-agent with tools | Context window limits; no specialization |
| Microservice per agent | Premature distribution; adds network latency |
| Human-in-the-loop only routing | Not scalable for automated workflows |

---

## Pros

- Clear separation of concerns per hazard domain
- Domain supervisors can evolve independently
- Climate supervisor handles cross-domain intents (e.g., WHAT_IF spans simulation + agriculture + water + RL)
- Each tier has its own agent registry — no global coupling
- Matches organizational structure of emergency management agencies

---

## Cons

- Additional latency from multi-tier invocation
- More boilerplate (three supervisor layers before specialized agents)
- Cross-domain queries require climate supervisor to coordinate multiple domain supervisors
- Risk of over-routing if intent classifier misclassifies

---

## Consequences

- Climate Supervisor's `AgentRegistry` holds domain supervisor handlers
- Domain Supervisors' `InternalAgentRegistry` holds specialized agent handlers
- Specialized agents never receive requests directly from users
- Each tier must implement `invoke()` and `as_graph_node()`

---

## Future Impact

- Enables domain-specific SLAs and scaling (e.g., emergency supervisor on dedicated compute during cyclone season)
- Supports adding new domains (e.g., `PolicySupervisor`) without modifying existing ones
- Climate supervisor can evolve into a meta-planner that composes domain subgraphs
