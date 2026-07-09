# Specialized Agent Architecture Diagram

> **Version:** 0.2.0  
> **Last Updated:** 2026-07-07

---

## Hierarchical Placement

```mermaid
flowchart TB
    CS[Climate Supervisor]
    ES[Environmental Supervisor]
    IS[Infrastructure Supervisor]
    EM[Emergency Supervisor]

    CS --> ES
    CS --> IS
    CS --> EM

    ES --> FA[Flood Agent]
    ES --> HA[Heatwave Agent]
    IS --> WA[Water Resource Agent]

    subgraph Framework["BaseSpecializedAgent Framework"]
        BSA[Shared Pipeline]
    end

    FA --> BSA
    WA --> BSA
    HA --> BSA
```

---

## Internal Pipeline

```mermaid
stateDiagram-v2
    [*] --> Observe
    Observe --> Analyze
    Analyze --> Reason
    Reason --> Reflect
    Reflect --> Validate
    Validate --> Decide
    Decide --> RL
    RL --> Report
    Report --> [*]

    Reflect --> Analyze: low confidence retry
    Validate --> Reason: validation failure retry
```

---

## Cross-Cutting Services

```mermaid
flowchart LR
    SA[Specialized Agent] --> MM[MemoryManager]
    SA --> DF[Decision Framework]
    SA --> RL[RLOptimizationService]
    SA --> XAI[ExplanationEngine]
    SA --> CKG[GraphEngine]
```

---

## Version 0.3.0 Update — All 8 Agents Complete (2026-07-09)

```mermaid
flowchart TB
    subgraph Environmental["Environmental Supervisor"]
        FA[flood_agent]
        HA[heatwave_agent]
        AQ[air_quality_agent]
    end

    subgraph Infrastructure["Infrastructure Supervisor"]
        WA[water_resource_agent]
        UP[urban_planning_agent]
        AG[agriculture_agent + RAG]
    end

    subgraph Emergency["Emergency Supervisor"]
        CY[cyclone_agent]
        DR[disaster_response_agent]
    end

    BSA[BaseSpecializedAgent] --> FA
    BSA --> HA
    BSA --> AQ
    BSA --> WA
    BSA --> UP
    BSA --> AG
    BSA --> CY
    BSA --> DR

    BSA --> DF[Decision Framework]
    BSA --> RL[RLOptimizationService]
    BSA --> XAI[ExplanationEngine]
    BSA --> CKG[GraphEngine]
    AG --> RAG[AgricultureRagService]
```

**Test count:** 172 specialized agent tests (396 total suite).

See [Specialized Agents Overview](../agents/specialized_agents_overview.md) for per-agent details.
