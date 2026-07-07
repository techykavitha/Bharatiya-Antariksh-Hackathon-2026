# Water Resource Agent Workflow

> **Version:** 0.2.0  
> **Last Updated:** 2026-07-07  
> **Source:** `backend/agents/specialized/water_resource/`

---

## End-to-End Invocation Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant WA as WaterResourceAgent
    participant MM as MemoryManager
    participant DT as DigitalTwinInterface
    participant TM as ToolManager
    participant WRE as WaterReasoningEngine
    participant WRef as WaterReflectionEngine
    participant WVal as WaterValidator
    participant WDE as WaterDecisionEngine
    participant AC as AgentCommunicationInterface
    participant RL as SpecializedRLEngineInterface
    participant WRB as WaterReportBuilder

    Client->>WA: invoke(AgentRequest)
    WA->>WA: initialize() if needed
    WA->>WA: WaterMetricsCollector.start()

    rect rgb(230, 245, 255)
        Note over WA,DT: Observe Phase
        WA->>WA: retrieve_context(request)
        WA->>WA: WaterInputs.from_request_context()
        Note right of WA: reservoir_available,<br/>groundwater_available flags
        WA->>WA: preprocess(context)
        WA->>MM: search + retrieve(working, climate, forecast)
        opt twin_id present
            WA->>DT: get_state(twin_id)
            DT-->>WA: digital_twin_state
        end
    end

    rect rgb(255, 245, 230)
        Note over WA,TM: Analyze Phase (parallel tools)
        WA->>TM: execute(ALL_WATER_TOOL_NAMES, PARALLEL)
        TM-->>WA: ToolResult[]
        Note right of TM: reservoir_tool, river_tool,<br/>groundwater_tool, rainfall_tool,<br/>soil_moisture_tool, population_tool,<br/>demand_tool, forecast_tool,<br/>digital_twin_tool, historical_water_tool
    end

    rect rgb(240, 255, 240)
        Note over WA,WRE: Reason Phase
        WA->>WRE: run(context, tool_results)
        WRE-->>WA: ReasoningResult + WaterAnalysisSignals
    end

    WA->>WRef: evaluate(context, reasoning, tool_results)
    WRef-->>WA: ReflectionResult

    WA->>WVal: validate(context, tool_results)
    WVal-->>WA: ValidationResult

    WA->>WDE: evaluate(context, reasoning, reflection)
    WDE-->>WA: local DecisionRequest

    opt decision.suggested_agents
        WA->>AC: call_other_agents(suggested_agents)
        AC-->>WA: AgentDelegationResult[]
    end

    opt decision.need_rl
        WA->>RL: request_policy(scenario_id, context)
        RL-->>WA: policy
    end

    WA->>WRB: build(context, reasoning, tools, reflection, validation, decision)
    WRB-->>WA: WaterResourceReport

    WA->>MM: store(working:water_report:{request_id})
    WA->>WA: set_stress_level + finalize_water metrics
    WA->>WA: update_memory() + update_state()
    WA-->>Client: AgentResponse
```

---

## Workflow State Machine

```mermaid
stateDiagram-v2
    [*] --> Initializing: invoke()
    Initializing --> Reasoning: WaterMetricsCollector

    state Reasoning {
        [*] --> Observe
        Observe --> Analyze: WaterInputs + basin context
        Analyze --> Reason: parallel tool execution
        Reason --> Reflect: water_signals + stress_level
        Reflect --> Validate: reservoir/groundwater checks
        Validate --> Decide: WaterDecisionEngine
        Decide --> Delegate: inter-agent coordination
        Delegate --> RLRequest: multi-basin RL
        RLRequest --> Report: WaterResourceReport
        Report --> Persist: memory + workflow state
        Persist --> [*]
    }

    Reasoning --> Completed: AgentStatus.COMPLETED
    Reasoning --> Failed: AgentInvocationError
    Completed --> [*]
    Failed --> [*]

    note right of Reason
        Outputs: water_stress,
        availability_band,
        release_strategy
    end note
```

---

## Reasoning Pipeline

```mermaid
flowchart TD
    START([WaterReasoningEngine.run]) --> OBS[observe]
    OBS --> STOR[current_storage]
    STOR --> RAIN[forecast_rainfall]
    RAIN --> RIV[river_conditions]
    RIV --> GW[groundwater]
    GW --> URB[urban_demand]
    URB --> AGR[agricultural_demand]
    AGR --> AVAIL[estimate_water_availability]
    AVAIL --> STRESS[estimate_water_stress]
    STRESS --> STRAT[determine_reservoir_strategy]
    STRAT --> REC[generate_recommendations]

    STOR -.->|reservoir_tool| TR[Tool Outputs]
    RAIN -.->|rainfall_tool, forecast_tool| TR
    RIV -.->|river_tool| TR
    GW -.->|groundwater_tool| TR
    URB -.->|demand_tool, population_tool| TR
    AGR -.->|demand_tool, soil_moisture_tool| TR

    REC --> OUT[ReasoningResult]
    OUT --> META[water_signals, stress_level,<br/>availability, release_strategy]

    style START fill:#e8f4fc
    style OUT fill:#d4edda
    style STRAT fill:#fff3cd
```

---

## Water Decision Engine Rules

```mermaid
flowchart TD
    IN[ReasoningResult + ReflectionResult] --> EVAL

    subgraph EVAL["WaterDecisionEngine.evaluate"]
        RL{need_rl?}
        RL -->|SEVERE/CRITICAL stress<br/>stress_score ≥ 0.6<br/>availability < 0.5| RL_T[RL optimization]

        FLOOD{need_flood_agent?}
        FLOOD -->|overflow_risk<br/>or reservoir ≥ 95%| FLOOD_T[suggest flood_agent]

        AGRI{need_agriculture?}
        AGRI -->|agricultural_demand_high<br/>or crop_area > 1000 ha| AGRI_T[suggest agriculture_agent]

        URBAN{need_urban?}
        URBAN -->|urban_demand_high<br/>or population > 1M| URBAN_T[suggest urban_planning_agent]

        DIS{need_disaster?}
        DIS -->|SEVERE/CRITICAL stress| DIS_T[suggest disaster_agent]

        SIM{need_simulation?}
        SIM -->|HIGH+ stress<br/>dependent_basins<br/>overflow_risk| SIM_T[basin simulation]

        FC{need_forecast_update?}
        FC -->|no forecast<br/>rainfall_deficit<br/>stress_score ≥ 0.4| FC_T[forecast refresh]
    end

    RL_T --> PRI[priority resolution]
    FLOOD_T --> PRI
    AGRI_T --> PRI
    URBAN_T --> PRI
    DIS_T --> PRI

    PRI -->|CRITICAL: overflow or CRITICAL stress| P_CRIT[critical]
    PRI -->|HIGH: SEVERE/HIGH stress| P_HIGH[high]
    PRI -->|else| P_NORM[normal]

    P_CRIT --> OUT[local DecisionRequest]
    P_HIGH --> OUT
    P_NORM --> OUT

    style OUT fill:#d4edda
```

---

## Inter-Agent Coordination

```mermaid
flowchart LR
    WA[Water Resource Agent] -->|overflow risk| FA[Flood Agent]
    WA -->|crop irrigation demand| AA[Agriculture Agent]
    WA -->|urban supply stress| UP[Urban Planning Agent]
    WA -->|SEVERE/CRITICAL stress| DR[Disaster Agent]

    subgraph Triggers["Delegation Triggers"]
        T1[reservoir.level_pct ≥ 95%]
        T2[crop_area_ha > 1000]
        T3[population > 1,000,000]
        T4[stress_level SEVERE/CRITICAL]
    end

    T1 --> FA
    T2 --> AA
    T3 --> UP
    T4 --> DR

    style WA fill:#cce5ff
```

---

## Report & Metrics Finalization

```mermaid
flowchart TB
    REP[WaterResourceReport] --> STRESS[water_stress level]
    REP --> AVAIL[water_availability band]
    REP --> REL[release_strategy]
    REP --> CONF[confidence]

    STRESS --> MET[WaterMetricsCollector]
    AVAIL --> MET
    REL --> MET
    CONF --> MET

    MET -->|reservoir_tool success| RA[record_reservoir_analysis]
    MET --> FIN[finalize_water]

  FIN --> RESP[AgentResponse metadata]
    RESP --> M1[supply_m3d / demand_m3d]
    RESP --> M2[decision_request]
    RESP --> M3[need_rl / need_simulation]

    style FIN fill:#d4edda
```
