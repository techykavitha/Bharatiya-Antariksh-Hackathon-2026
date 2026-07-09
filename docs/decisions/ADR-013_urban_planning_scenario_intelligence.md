# ADR-013: Urban Planning Scenario Intelligence

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-07-09 |
| **Deciders** | Nexora Engineering |
| **Related** | [Development Log 014](../development_logs/014_urban_planning_agent.md), [ADR-006](./ADR-006_specialized_agent_framework.md), [ADR-012](./ADR-012_disaster_response_coordination.md) |

---

## Context

Hyperion's specialized agents initially focused on acute hazards (flood, cyclone, heatwave) and resource stress (water). Urban climate resilience requires a fundamentally different time horizon — adaptation planning spans years to decades, with budget-constrained investment prioritization across drainage, green cover, building density, and infrastructure upgrades.

Indian megacities present distinct vulnerability profiles: Chennai flooding from inadequate drainage, Delhi urban heat island from high building density, Bengaluru green cover deficit, Hyderabad drainage capacity gaps. A single generic urban model cannot capture these differences.

---

## Decision

Implement the **Urban Planning Agent** in `backend/agents/specialized/urban_planning/` as a long-horizon scenario intelligence agent with structured mitigation and investment output models.

### Scenario intelligence model

| Model | Purpose |
|-------|---------|
| `MitigationOption` | Individual adaptation strategy with cost, benefit, and timeline |
| `InvestmentPriority` | Ranked investment with population impact and ROI scoring |
| `GreenCoverAnalysis` | Vegetation deficit and restoration potential |
| `UrbanResilienceLevel` | Composite resilience score for plan comparison |
| `ScenarioContext` | Multi-year time horizon in decision framework |

### Tool architecture (11 tools)

Land use, NDVI, building density, road network, drainage, green cover, population, forecast, digital twin, knowledge graph, infrastructure. Tools quantify urban vulnerability signals; reasoning engine synthesizes mitigation options.

### Constraint model

- `BudgetConstraint` — total adaptation budget ceiling
- `TimeConstraint` — planning horizon (years)
- `PopulationConstraint` — residents affected by each mitigation
- `SafetyConstraint` — minimum safety standards for infrastructure upgrades

### Peer consultation

- `_consult_peer_agents()` enriches urban signals with flood and heatwave domain expertise.
- Reflection identifies when peer consultation is needed for incomplete urban profiles.

### City scenario fixtures

Chennai (flooding), Delhi (UHI), Bengaluru (green cover), Hyderabad (drainage) — each emphasizes different tool weightings in reasoning.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Urban planning as disaster response sub-module | Different time horizon and constraint model; conflates emergency and adaptation |
| LLM-generated master plans | Non-deterministic; structured `MitigationOption` output is testable and actionable |
| Single generic city model | Cannot capture Chennai flood vs Delhi UHI distinct profiles |
| Real municipal GIS integration in v1.0 | External dependency; scenario fixtures sufficient for v0.3.0 |
| On-demand tool selection vs parallel execution | Parallel execution consistent with agent framework; 11 tools manageable |
| Infrastructure Supervisor vs Climate Supervisor | Urban infrastructure belongs on Infrastructure Supervisor per ADR-005 |

---

## Advantages

- Structured `MitigationOption` and `InvestmentPriority` output enables downstream budget workflows
- Per-city scenario fixtures validate distinct vulnerability profiles
- Long-horizon constraint model (budget, time) distinct from emergency agents
- Peer consultation with flood/heatwave agents enriches cross-domain signals
- `UrbanResilienceLevel` composite enables plan comparison across scenarios
- Infrastructure Supervisor registration groups urban planning with agriculture domain
- `ACTION_CATALOG` maps urban actions to canonical `DecisionAction` entries

---

## Disadvantages

- 11 parallel tools may overweight signals irrelevant to specific city scenarios
- Investment ROI scoring uses simplified parametric model
- No real municipal budget or project pipeline data in v0.3.0
- Green cover analysis depends on NDVI thresholds not calibrated per city
- Peer consultation adds latency to already long-horizon planning invoke

---

## Trade-offs

| Trade-off | Choice | Rationale |
|-----------|--------|-----------|
| Long-horizon vs emergency agent | Dedicated long-horizon agent | Different constraints, outputs, and supervisor domain |
| Structured vs free-text plans | `MitigationOption` + `InvestmentPriority` | Machine-readable; testable; budget-workflow compatible |
| Per-city vs generic scenarios | Per-city fixtures | Validates tool weighting diversity |
| Parallel vs selective tools | Parallel (11 tools) | Framework consistency; acceptable latency for planning |
| Parametric vs simulation ROI | Parametric scoring | Sufficient for v0.3.0; simulation engine planned |

---

## Future Impact

- Simulation engine models adaptation investment outcomes over multi-year horizons
- Municipal GIS integration for real drainage and building density data
- CKG expansion with urban infrastructure entity nodes per megacity
- FastAPI endpoints for urban adaptation planning workflow
- Cross-reference with disaster response agent for acute-vs-chronic risk framing
- Digital twin integration for scenario comparison (with/without mitigation)
