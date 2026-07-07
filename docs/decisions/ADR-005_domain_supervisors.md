# ADR-005: Domain Supervisor Middle Tier

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-07-07 |
| **Deciders** | Nexora Engineering |
| **Related** | [Domain Supervisors](../domain/domain_supervisors.md) |

---

## Context

ADR-002 established a three-tier hierarchy. The Climate Supervisor handles cross-domain intents but lacks domain-specific knowledge for agent selection, task routing, and execution topology within a hazard domain. Specialized agents (future) need a manager that understands their capabilities without the Climate Supervisor knowing about every agent.

---

## Decision

Introduce a **Domain Supervisor middle tier** with three concrete implementations:

| Supervisor | Domain | Future Agents |
|------------|--------|---------------|
| `EnvironmentalSupervisor` | Weather, climate, air quality | flood, heatwave, air_quality |
| `InfrastructureSupervisor` | Agriculture, water, urban | agriculture, water_resource, urban_planning |
| `EmergencySupervisor` | Cyclone, disaster response | cyclone, disaster_response |

Each extends `BaseDomainSupervisor` with its own `InternalAgentRegistry`, task definitions, and agent slot metadata.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Climate Supervisor routes directly to specialized agents | Climate supervisor becomes too complex; no domain isolation |
| One domain supervisor per agent | Too many supervisors; overhead |
| Plugin system without supervisors | No execution orchestration within domain |
| Hardcoded agent lists in Climate Supervisor | Violates open/closed principle |

---

## Pros

- Domain-specific task → agent keyword routing without climate logic in climate layer
- Internal agent registry per domain — agents register independently
- `DomainExecutor` supports sequential, parallel, conditional execution within domain
- `DomainRegistry` provides discovery for Climate Supervisor
- Agent slots pre-declared for future agents (metadata only, no implementation)
- `as_graph_node()` enables LangGraph subgraph embedding

---

## Cons

- Additional hop latency (Climate → Domain → Specialized)
- Three more classes to maintain
- Task keyword routing is rule-based (may need LLM classifier later)
- Unregistered agents fail at execution time (no agents implemented yet)

---

## Consequences

- Climate Supervisor's `AgentRegistry` will register domain supervisors (not specialized agents)
- Specialized agents register via `domain_supervisor.register_agent()`
- `DomainSupervisorHandler` protocol at climate level; `DomainAgentHandler` at domain level
- WorkflowState metadata tracks `active_domain`, `completed_agents`, `failed_agents`

---

## Future Impact

- New domains (e.g., Policy) added by creating new `BaseDomainSupervisor` subclass
- Domain supervisors can be scaled independently
- Task routing can be upgraded to LLM-based without changing architecture
- Domain subgraphs composable in LangGraph meta-graph
