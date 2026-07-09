# ADR-015: Air Quality Environmental Intelligence

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-07-09 |
| **Deciders** | Nexora Engineering |
| **Related** | [Development Log 016](../development_logs/016_air_quality_agent.md), [Development Log 009](../development_logs/009_heatwave_agent.md), [ADR-009](./ADR-009_explainability_framework.md) |

---

## Context

Air quality is Hyperion's final specialized agent domain, completing the 8-agent suite. Indian air quality challenges are regionally diverse: Delhi winter severe AQI from vehicular and industrial emissions with temperature inversion, Punjab post-harvest stubble burning elevating PM2.5/PM10, Rajasthan pre-monsoon dust storms detected via satellite aerosol optical depth, and Mumbai coastal moderation with salt aerosol influence.

The heatwave agent (Log 009) identified compound heat–AQI health risk as a cross-domain concern. The air quality agent must consume heatwave temperature data via peer consultation to model amplified health impacts. This completes the bidirectional compound event architecture started in the heatwave agent.

---

## Decision

Implement the **Air Quality Agent** in `backend/agents/specialized/air_quality/` as an environmental intelligence agent with 12 tools, multi-pollutant reasoning, source attribution, and compound heat–AQI health risk assessment.

### Tool architecture (12 tools)

| Tool | Signal |
|------|--------|
| `AQITool` | Composite AQI from sub-indices (PM2.5, PM10, NO2, SO2) |
| `PMTool` | Particulate matter concentrations and stubble signature |
| `GasConcentrationTool` | NO2, SO2, CO, O3 concentrations |
| `WindTool` | Dispersion potential, stagnation detection |
| `ForecastTool` | AQI forecast trajectory |
| `EmissionTool` | Source attribution (stubble, industrial, vehicular) |
| `SatelliteAerosolTool` | AOD for dust storm detection |
| `HealthRiskTool` | Population health risk assessment |
| `DigitalTwinTool` | Urban air quality scenario overlay |
| `KnowledgeGraphTool` | CKG population and emission context |
| `PopulationTool` | Exposed population by AQI category |
| `HistoricalAQITool` | Seasonal and episodic trend comparison |

### Multi-pollutant AQI

- Per-pollutant sub-index calculation with max-dominant AQI selection.
- `AQICategory` enum (Good, Satisfactory, Moderate, Poor, Very Poor, Severe).

### Source attribution

- `PollutionSourceType` enum: stubble, dust, industrial, vehicular, construction, coastal, unknown.
- `EmissionTool` + `PMTool` composite for Punjab stubble and Rajasthan dust scenarios.

### Compound heat–AQI risk

- `_consult_peer_agents()` pulls heatwave temperature data at observe phase.
- `HealthRiskAssessment` amplified when temperature exceeds 40°C and AQI exceeds Severe threshold.
- Bidirectional compound event link with heatwave agent (Log 009 `test_compound_aqi_reasoning`).

### Supervisor registration

- `air_quality_agent` slot on Environmental Supervisor alongside heatwave agent.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| AQI-only tool (no pollutant breakdown) | Loses source attribution and sub-index granularity |
| Air quality as heatwave sub-module | Distinct domain with own tools, scenarios, and supervisor slot |
| Real CPCB/SAFAR API in v1.0 | External dependency; scenario fixtures sufficient |
| Single-city model | Cannot capture Delhi severe vs Punjab stubble vs Rajasthan dust |
| No satellite aerosol tool | Dust storms are primary Rajasthan hazard; ground sensors insufficient |
| Static temperature for compound risk | Peer consultation provides live heatwave data |

---

## Advantages

- Completes 8-agent specialized suite with full enterprise invoke pipeline
- Multi-pollutant sub-index model enables source-specific mitigation recommendations
- `SatelliteAerosolTool` detects dust storms independent of ground sensor coverage
- Compound heat–AQI risk validates bidirectional cross-agent consultation architecture
- Regional scenario diversity (Delhi, Punjab, Rajasthan, Mumbai) exercises distinct tool weightings
- `HealthRiskTool` gates mitigation action severity on population health impact
- Environmental Supervisor groups air quality with heatwave for compound event orchestration
- `HistoricalAQITool` provides seasonal context for episodic vs chronic pollution

---

## Disadvantages

- 12 parallel tools increase per-invocation latency
- AQI sub-index breakpoints use national standards; local calibration may differ
- Emission source attribution uses heuristic signatures, not dispersion modeling
- No real emission inventory database in v0.3.0
- Compound risk threshold (40°C + Severe AQI) is simplified; health impact curves are non-linear
- Satellite AOD retrieval uses seeded values, not live MODIS/VIIRS feeds

---

## Trade-offs

| Trade-off | Choice | Rationale |
|-----------|--------|-----------|
| Multi-pollutant vs AQI-only | Multi-pollutant sub-indices | Source attribution requires pollutant granularity |
| Peer consultation vs embedded temperature | Live heatwave consultation | Bidirectional compound architecture; fresh data |
| Heuristic vs dispersion source attribution | Heuristic signatures | Testable; sufficient for scenario validation |
| 12 parallel tools vs selective | Parallel execution | Framework consistency; full signal coverage |
| National vs local AQI breakpoints | National standards (CPCB) | Standard reference; local calibration deferred |

---

## Future Impact

- Live CPCB/SAFAR sensor feed integration via tool extensions
- Dispersion modeling in simulation engine for source attribution refinement
- CKG expansion with emission source entity nodes and population exposure edges
- FastAPI endpoints for air quality monitoring and mitigation workflow
- XAI evidence chain enriched with pollutant source attribution and health risk curves
- Completing the agent suite shifts project focus to API layer and end-to-end climate workflow demo
- RL state features from AQI trajectory, source type, and compound health risk scores
