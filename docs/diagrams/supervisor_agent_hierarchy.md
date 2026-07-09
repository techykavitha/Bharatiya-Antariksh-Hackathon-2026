# Supervisor Agent Hierarchy

> **Version:** 0.3.0 | **Last Updated:** 2026-07-09

```mermaid
flowchart TB
    CS[Climate Supervisor]

    CS --> ES[Environmental Supervisor]
    CS --> IS[Infrastructure Supervisor]
    CS --> EMS[Emergency Supervisor]

    ES --> FA[flood_agent ✅]
    ES --> HA[heatwave_agent ✅]
    ES --> AQ[air_quality_agent ✅]

    IS --> WA[water_resource_agent ✅]
    IS --> UP[urban_planning_agent ✅]
    IS --> AG[agriculture_agent ✅]

    EMS --> CY[cyclone_agent ✅]
    EMS --> DR[disaster_response_agent ✅]
```

## Supervisor Responsibilities

| Supervisor | Agent Slots | Task Keywords |
|------------|-------------|---------------|
| Environmental | flood, heatwave, air_quality | flood, heat, pollution, AQI, environment |
| Infrastructure | water, urban, agriculture | water, urban, agriculture, planning, crop |
| Emergency | cyclone, disaster | cyclone, disaster, emergency, evacuation |

---

## Environmental Supervisor Workflow

```mermaid
flowchart TB
    CS[Climate Supervisor] --> ES[Environmental Supervisor]
    ES --> IC{Intent Classifier}
    IC -->|flood / rainfall| FA[flood_agent]
    IC -->|heat / temperature| HA[heatwave_agent]
    IC -->|AQI / pollution / smog| AQ[air_quality_agent]
    FA --> DF[Decision Framework]
    HA --> DF
    AQ --> DF
    FA <--> HA
    HA <--> AQ
    FA <--> AQ
    DF --> RL[RLOptimizationService]
    RL --> XAI[ExplanationEngine]
```

| Agent | Primary Inputs | Primary Outputs | Peer Agents |
|-------|----------------|-----------------|-------------|
| `flood_agent` | Rainfall, river discharge, soil moisture | Flood risk, evacuation zones | heatwave, air_quality |
| `heatwave_agent` | Temperature, humidity, UHI | Heat stress, cooling advisories | flood, air_quality |
| `air_quality_agent` | PM2.5, gases, wind, emissions | AQI category, health risk | heatwave, urban_planning, agriculture |

---

## Infrastructure Supervisor Workflow

```mermaid
flowchart TB
    CS[Climate Supervisor] --> IS[Infrastructure Supervisor]
    IS --> IC{Intent Classifier}
    IC -->|water / reservoir| WA[water_resource_agent]
    IC -->|urban / planning| UP[urban_planning_agent]
    IC -->|crop / agriculture| AG[agriculture_agent]
    WA --> DF[Decision Framework]
    UP --> DF
    AG --> RAG[AgricultureRagService]
    RAG --> AG
    AG --> DF
    WA <--> AG
    UP <--> WA
    DF --> RL[RLOptimizationService]
    RL --> XAI[ExplanationEngine]
```

| Agent | Primary Inputs | Primary Outputs | Peer Agents |
|-------|----------------|-----------------|-------------|
| `water_resource_agent` | Reservoir levels, demand, rainfall | Allocation, release schedules | agriculture, flood |
| `urban_planning_agent` | Land use, UHI, flood zones | Adaptation scenarios, zoning | flood, heatwave, water |
| `agriculture_agent` | Soil moisture, crop stage, weather | Irrigation, harvest advisories | water, heatwave, flood |

---

## Emergency Supervisor Workflow

```mermaid
flowchart TB
    CS[Climate Supervisor] --> EMS[Emergency Supervisor]
    EMS --> IC{Intent Classifier}
    IC -->|cyclone / storm| CY[cyclone_agent]
    IC -->|disaster / response| DR[disaster_response_agent]
    CY --> DF[Decision Framework]
    DR --> CONSULT[Consult Hazard Agents]
    CONSULT --> FA[flood_agent]
    CONSULT --> HA[heatwave_agent]
    CONSULT --> AQ[air_quality_agent]
    CONSULT --> CY
    DR --> DF
    CY --> FA
    DF --> RL[RLOptimizationService]
    RL --> XAI[ExplanationEngine]
```

| Agent | Primary Inputs | Primary Outputs | Peer Agents |
|-------|----------------|-----------------|-------------|
| `cyclone_agent` | SST, wind, pressure, INSAT | Track, landfall, surge, evacuation | flood, disaster_response |
| `disaster_response_agent` | Multi-hazard signals, population | Coordinated response plan | all hazard agents |
