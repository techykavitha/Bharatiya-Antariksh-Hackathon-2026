# ADR-011: Cyclone Agent Architecture

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-07-09 |
| **Deciders** | Nexora Engineering |
| **Related** | [Development Log 012](../development_logs/012_cyclone_agent.md), [ADR-006](./ADR-006_specialized_agent_framework.md), [ADR-010](./ADR-010_climate_knowledge_graph.md) |

---

## Context

Hyperion's specialized agent framework (ADR-006) established the OODA pipeline pattern with flood, water resource, and heatwave agents. Tropical cyclones represent India's highest-impact coastal hazard — requiring genesis detection, track forecasting, rapid intensification monitoring, storm surge estimation, and cascading flood risk. The cyclone agent must integrate the full enterprise stack (Decision Framework, RL Optimization, Explainability, Climate Knowledge Graph) and delegate to the flood agent for inland rainfall cascade.

Bay of Bengal and Arabian Sea cyclones differ in genesis thresholds, intensification patterns, and landfall exposure. Historical analogs (Fani 2019, Amphan 2020, Biparjoy 2023, Michaung 2023) provide calibration anchors.

---

## Decision

Implement the **Cyclone Agent** in `backend/agents/specialized/cyclone/` as a `BaseSpecializedAgent` subclass with 12 domain tools, combined reasoning/decision engines, and full RL/XAI/CKG integration.

### Tool architecture

| Tool | Domain Signal |
|------|---------------|
| `SSTTool` | Sea surface temperature, cyclogenesis favorability |
| `PressureTool` | MSLP, pressure gradient, cyclone center detection |
| `WindTool` | Wind speed, cyclone category classification |
| `OceanHeatTool` | Ocean heat content for intensification potential |
| `INSATTool` | Satellite cloud top temperature, convection |
| `ForecastTool` | Track, landfall probability, rainfall forecast |
| `HistoricalCycloneTool` | Analog event matching (Fani, Amphan, etc.) |
| `StormSurgeTool` | Coastal surge height estimation |
| `DigitalTwinTool` | Coastal defense scenario overlay |
| `KnowledgeGraphTool` | CKG impact chains and affected agents |
| `PopulationTool` | Coastal population exposure |
| `InfrastructureTool` | Port, power, road infrastructure exposure |

All 12 tools execute in parallel during the analyze phase. Each implements `get_input_schema()` per the `AbstractTool` contract.

### Reasoning and decision

- `CycloneReasoningEngine` aggregates tool outputs into `CycloneAnalysisSignals` with severity classification (`CycloneSeverity`), rapid intensification status, and risk level.
- `CycloneDecisionEngine` produces canonical `DecisionRequest` with population and time constraints mapped from `CycloneActionType`.
- Decision logic co-located in `cyclone_reasoning.py` following the heatwave agent pattern.

### Inter-agent delegation

- `CycloneReflectionEngine` recommends flood agent consultation when storm surge or inland rainfall exceeds thresholds.
- Delegation via `AgentCommunicationInterface` at reflection phase.

### Supervisor registration

- `cyclone_agent` slot on Emergency Supervisor domain.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Separate `cyclone_decision_engine.py` module | Adds file without benefit; heatwave pattern co-locates reasoning and decision |
| Fewer tools (6–8) with on-demand selection | Inconsistent with parallel execution pattern; misses compound coastal signals |
| Agent-level CKG queries only (no `KnowledgeGraphTool`) | Couples graph access to agent orchestration; tool pattern is more testable |
| Real-time IMD API integration in v1.0 | External dependency; scenario fixtures sufficient for v0.3.0 |
| Cyclone agent on Climate Supervisor | Emergency hazard belongs on Emergency Supervisor per ADR-005 domain model |
| LLM-based track forecasting | Non-deterministic; rule-based classification from wind/SST/pressure is testable |

---

## Advantages

- 12-tool parallel pipeline provides comprehensive coastal hazard signal coverage per invocation
- Rapid intensification detection enables early-warning differentiation from steady-state cyclones
- Historical analog matching (Fani, Amphan) anchors severity classification to real events
- `KnowledgeGraphTool` decouples CKG access from agent orchestration
- Full RL/XAI/CKG integration validates enterprise invoke pipeline as repeatable pattern
- Reflection-driven flood delegation models cascading hazard without duplicating flood analysis
- Emergency Supervisor registration enables multi-hazard orchestration with disaster response agent

---

## Disadvantages

- 12 parallel tools increase per-invocation latency vs selective tool routing
- Combined reasoning/decision module grows large (~400+ lines) in single file
- Scenario fixtures limited to Indian cyclones; other basins need additional seed data
- No real satellite or oceanographic data feeds in v0.3.0
- Storm surge estimation uses simplified parametric model, not hydrodynamic simulation

---

## Trade-offs

| Trade-off | Choice | Rationale |
|-----------|--------|-----------|
| Parallel vs selective tools | Parallel (12 tools) | Consistency with heatwave/flood; full signal coverage |
| Combined vs split decision module | Combined in `cyclone_reasoning.py` | Matches heatwave convention; reduces file count |
| CKG as tool vs agent method | Dedicated `KnowledgeGraphTool` | Testable in isolation; consistent with other agents |
| Historical analogs vs ML forecasting | Rule-based analog matching | Deterministic, testable, no training data required |
| Parametric vs hydrodynamic surge | Parametric model | Sufficient for v0.3.0; simulation engine planned separately |

---

## Future Impact

- Simulation engine integration for hydrodynamic storm surge modeling
- Live IMD/JTWC forecast feed ingestion via `ForecastTool` extension
- CKG India seed graph expansion with cyclone entity nodes and historical event edges
- Disaster response agent consumes cyclone reports for multi-hazard coordination
- RL state encoder augmentation with cyclone severity and RI features
- Arabian Sea cyclone season expansion with additional scenario fixtures
