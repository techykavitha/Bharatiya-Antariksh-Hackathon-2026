# ADR-012: Disaster Response Coordination

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-07-09 |
| **Deciders** | Nexora Engineering |
| **Related** | [Development Log 013](../development_logs/013_disaster_response_agent.md), [ADR-005](./ADR-005_domain_supervisors.md), [ADR-011](./ADR-011_cyclone_agent_architecture.md) |

---

## Context

With four hazard-specialized agents (flood, water resource, heatwave, cyclone) operational, Hyperion needs a coordination layer that synthesizes multi-hazard outputs into actionable emergency response plans. Real disasters are compound events — cyclone landfall followed by inland flooding, heatwave coinciding with water stress, or simultaneous multi-hazard emergencies affecting overlapping populations and infrastructure.

A disaster response agent must not duplicate hazard analysis performed by domain specialists. Instead, it consumes their outputs, ranks priorities, allocates resources, and produces evacuation and medical support plans within budget, time, and safety constraints.

---

## Decision

Implement the **Disaster Response Agent** as a meta-agent in `backend/agents/specialized/disaster_response/` that coordinates across hazard specialists via `AgentCommunicationInterface`.

### Meta-agent pattern

| Responsibility | Owner |
|----------------|-------|
| Hazard detection and severity | Specialized hazard agents |
| Priority ranking and resource allocation | Disaster response agent |
| Shelter/hospital/road capacity | Disaster response tools |
| Emergency decision output | `DisasterDecisionEngine` |

### Hazard agent mapping

```python
_AGENT_HAZARD_MAP = {
    "flood_agent": HazardType.FLOOD,
    "cyclone_agent": HazardType.CYCLONE,
    "heatwave_agent": HazardType.HEATWAVE,
    "water_resource_agent": HazardType.WATER_STRESS,
    "agriculture_agent": HazardType.AGRICULTURE,
    "air_quality_agent": HazardType.AIR_QUALITY,
}
```

### Operational tools (11)

Emergency resources, shelter, hospital, road network, population, critical infrastructure, forecast, digital twin, knowledge graph, relief inventory, communication. These model response logistics, not meteorological analysis.

### Live consultation

- `_consult_hazard_agents()` at observe phase pulls fresh `HazardAgentOutput` from active hazard agents.
- Priority ranking in `DisasterReasoningEngine` orders hazards by severity and population exposure.

### Compound scenarios

Test fixtures cover cyclone+flood, heatwave+water stress, and multi-hazard emergency paths.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Supervisor-only coordination (no dedicated agent) | Supervisors route; they do not produce detailed response plans with resource allocation |
| Disaster agent performs its own hazard analysis | Duplicates specialized agent logic; violates single-responsibility |
| Static hazard reports (no live consultation) | Stale data in fast-evolving emergencies |
| Single-hazard-only design | Ignores compound disaster reality (cyclone → flood cascade) |
| External NDMA/NDRF API in v1.0 | Operational complexity; mock agents sufficient for v0.3.0 |
| Graph-only coordination via CKG | CKG provides context but not operational resource planning |

---

## Advantages

- Clean separation: hazard agents analyze, disaster agent coordinates
- Live consultation ensures response plans reflect current hazard state
- Priority ranking handles compound events with configurable hazard weights
- 11 operational tools model shelters, hospitals, relief inventory independently of hazard type
- `DecisionConstraints` (budget, time, population, safety) ground emergency actions in reality
- Emergency Supervisor registration groups cyclone and disaster response under emergency domain
- Compound scenario tests validate cyclone+flood and multi-hazard paths

---

## Disadvantages

- Meta-agent adds latency from sequential hazard agent consultations
- Priority ranking defaults (cyclone > flood) may not fit all scenarios without configuration
- No real GIS routing for evacuation paths in v0.3.0
- Relief inventory and shelter capacity use seeded data, not live databases
- Agent communication interface is mock-based in tests; production wiring needs supervisor orchestration

---

## Trade-offs

| Trade-off | Choice | Rationale |
|-----------|--------|-----------|
| Meta-agent vs supervisor coordination | Dedicated meta-agent | Response planning requires domain-specific tools and decision output |
| Live vs cached hazard reports | Live consultation at observe | Emergency timeliness outweighs consultation latency |
| Fixed vs configurable priority | Default ranking with override support | Sensible defaults for tests; configurable for production |
| 11 operational tools vs fewer | Full logistics coverage | Shelters, hospitals, roads, relief each need independent scoring |
| Mock vs real hazard agents in tests | Mock `AgentCommunicationInterface` | Isolates disaster agent logic; integration tested separately |

---

## Future Impact

- Supervisor-orchestrated live consultation replacing mock agents in production
- CKG cascade reasoning enriches compound disaster detection
- FastAPI endpoints expose multi-hazard emergency workflow
- Simulation engine models evacuation routing and resource depletion over time
- NDMA/NDRF API integration for real shelter and hospital capacity data
- RL state features from multi-hazard priority rankings and resource allocation outcomes
