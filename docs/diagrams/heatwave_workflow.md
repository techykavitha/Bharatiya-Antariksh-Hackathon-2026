# Heatwave Agent Workflow

> **Version:** 0.2.0  
> **Last Updated:** 2026-07-07  
> **Source:** `backend/agents/specialized/heatwave/`

---

## End-to-End Invocation Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant HA as HeatwaveAgent
    participant MM as MemoryManager
    participant DT as DigitalTwinInterface
    participant TM as ToolManager
    participant HRE as HeatwaveReasoningEngine
    participant HRef as HeatwaveReflectionEngine
    participant HVal as HeatwaveValidator
    participant HDE as HeatwaveDecisionEngine
    participant DM as DecisionManager
    participant AC as AgentCommunicationInterface
    participant RLS as RLOptimizationService
    participant RLE as SpecializedRLEngineInterface
    participant HRB as HeatwaveReportBuilder

    Client->>HA: invoke(AgentRequest)
    HA->>HA: HeatwaveMetricsCollector.start()

    rect rgb(230, 245, 255)
        Note over HA,DT: Observe Phase
        HA->>HA: retrieve_context + HeatwaveInputs
        HA->>MM: memory + climate + forecast retrieval
        opt twin_id
            HA->>DT: get_state(twin_id)
        end
    end

    rect rgb(255, 245, 230)
        Note over HA,TM: Analyze Phase (parallel)
        HA->>TM: execute(ALL_HEATWAVE_TOOL_NAMES, PARALLEL)
        TM-->>HA: ToolResult[]
        Note right of TM: temperature_tool, humidity_tool,<br/>lst_tool, ndvi_tool, urban_density_tool,<br/>population_tool, forecast_tool,<br/>historical_heatwave_tool,<br/>digital_twin_tool, health_risk_tool
    end

    HA->>HRE: run(context, tool_results)
    HRE-->>HA: ReasoningResult + HeatAnalysisSignals

    HA->>HRef: evaluate(context, reasoning, tool_results)
    HRef-->>HA: ReflectionResult

    HA->>HVal: validate(context, tool_results)
    HVal-->>HA: ValidationResult

    rect rgb(255, 240, 245)
        Note over HA,DM: Unified Decision Framework
        HA->>HDE: evaluate(context, reasoning, reflection)
        HDE->>DM: create(DecisionType.HEATWAVE, actions, constraints)
        DM->>DM: validate_request()
        DM-->>HDE: DecisionRequest
        HDE-->>HA: DecisionRequest
    end

    opt decision.need_other_agents
        HA->>AC: call_other_agents(need_other_agents)
    end

    rect rgb(240, 255, 240)
        Note over HA,RLS: RL Optimization
        alt decision.need_rl and rl_service
            HA->>RLS: optimize(DecisionRequest)
            RLS-->>HA: DecisionResponse
        else need_rl and rl_engine only
            HA->>RLE: request_policy(scenario_id)
            RLE-->>HA: policy
        end
    end

    HA->>HRB: build(..., decision, rl_response)
    HRB-->>HA: HeatwaveReport

    HA->>MM: store(working:heatwave_report:{request_id})
    HA-->>Client: AgentResponse (decision_request + rl_response)
```

---

## Workflow State Machine

```mermaid
stateDiagram-v2
    [*] --> Initializing: invoke()
    Initializing --> Reasoning: HeatwaveMetricsCollector

    state Reasoning {
        [*] --> Observe
        Observe --> Analyze: HeatwaveInputs hydrated
        Analyze --> Reason: thermal tool outputs
        Reason --> Reflect: heat_signals + severity
        Reflect --> Validate: heat index / forecast checks
        Validate --> Decide: HeatwaveDecisionEngine
        Decide --> Delegate: need_other_agents
        Delegate --> RLOptimize: need_rl + RLOptimizationService
        RLOptimize --> RLFallback: rl_engine fallback
        RLFallback --> Report: HeatwaveReport + rl_response
        Report --> Persist: memory + workflow state
        Persist --> [*]
    }

    Reasoning --> Completed: success
    Reasoning --> Failed: AgentInvocationError
    Completed --> [*]
    Failed --> [*]

    note right of Decide
        Produces unified DecisionRequest
        via DecisionManager.create()
    end note
```

---

## Reasoning Pipeline

```mermaid
flowchart TD
    START([HeatwaveReasoningEngine.run]) --> OBS[observe]
    OBS --> TEMP[temperature_trend]
    TEMP --> HUM[humidity]
    HUM --> HI[heat_index]
    HI --> UHI[urban_heat_island]
    UHI --> POP[population_exposure]
    POP --> HIST[historical_comparison]
    HIST --> SEV[estimate_severity]
    SEV --> DUR[estimate_duration]
    DUR --> VUL[estimate_vulnerability]
    VUL --> REC[generate_recommendations]

    TEMP -.->|temperature_tool, forecast_tool| TR[Tool Outputs]
    HUM -.->|humidity_tool| TR
    UHI -.->|lst_tool, ndvi_tool, urban_density_tool| TR
    POP -.->|population_tool, health_risk_tool| TR
    HIST -.->|historical_heatwave_tool| TR

    REC --> OUT[ReasoningResult]
    OUT --> META[heat_signals, severity,<br/>heat_index, duration_days]

    style START fill:#e8f4fc
    style HI fill:#ffe0b2
    style OUT fill:#d4edda
```

---

## Unified Decision Request Construction

```mermaid
flowchart TB
    SIG[heat_signals + severity] --> HDE[HeatwaveDecisionEngine]

    HDE --> OBJ[build_objectives]
    OBJ --> O1[minimize_heat_mortality 35%]
    OBJ --> O2[protect_vulnerable 30%]
    OBJ --> O3[reduce_thermal_stress 20%]
    OBJ --> O4[maintain_critical_infra OR minimize_cost 15%]

    HDE --> ACT[build_actions from ACTION_CATALOG]
    ACT --> A1[PUBLIC_ALERTS]
    ACT --> A2[COOLING_CENTERS + WATER_DISTRIBUTION]
    ACT --> A3[SCHOOL_CLOSURE + WORK_HOUR_MODIFICATION]
    ACT --> A4[URBAN_COOLING if UHI]
    ACT --> A5[TREE_PLANTATION if low_vegetation]
    ACT --> A6[EMERGENCY_RESPONSE if SEVERE/EXTREME]

    HDE --> CON[build_constraints]
    CON --> C1[BudgetConstraint max_cost]
    CON --> C2[TimeConstraint max_hours]
    CON --> C3[PopulationConstraint]
    CON --> C4[SafetyConstraint max_risk_score]

    HDE --> DM[DecisionManager.create]
    DM --> VAL[DecisionValidator.validate_request]
    VAL --> DR[DecisionRequest]

    DR --> FLAGS[need_rl, need_simulation,<br/>need_human, need_other_agents]

    style DR fill:#d4edda
    style DM fill:#cce5ff
```

---

## RL Optimization Branch

```mermaid
flowchart TD
    DR[DecisionRequest] --> CHECK{need_rl?}

    CHECK -->|false| SKIP[rl_response = None]
    CHECK -->|true| SVC{rl_service available?}

    SVC -->|yes| OPT[RLOptimizationService.optimize]
    OPT -->|success| RESP[DecisionResponse]
    OPT -->|RLOptimizationError| WARN[log warning, return None]

    SVC -->|no| ENG{rl_engine available?}
    ENG -->|yes| POL[request_rl via SpecializedRLEngineInterface]
    ENG -->|no| SKIP

    RESP --> REP[HeatwaveReportBuilder]
    POL --> REP
    SKIP --> REP
    WARN --> ENG

    REP --> OUT[HeatwaveReport with rl_response optional]

    style RESP fill:#d4edda
    style WARN fill:#fff3cd
```

---

## Severity → Priority & Risk Mapping

```mermaid
flowchart LR
    subgraph Severity["HeatwaveSeverity"]
        NONE[NONE]
        MOD[MODERATE]
        HIGH[HIGH]
        SEV[SEVERE]
        EXT[EXTREME]
    end

    subgraph Priority["DecisionPriority"]
        LOW_P[LOW]
        NORM[NORMAL]
        HIGH_P[HIGH]
        URG[URGENT]
        CRIT[CRITICAL]
    end

    subgraph Risk["RiskLevel"]
        NEG[NEGLIGIBLE]
        LOW_R[LOW]
        MOD_R[MODERATE]
        HIGH_R[HIGH]
        SEV_R[SEVERE]
        CRIT_R[CRITICAL]
    end

    NONE --> LOW_P
    MOD --> NORM
    HIGH --> HIGH_P
    SEV --> URG
    EXT --> CRIT

    NONE --> NEG
    MOD --> MOD_R
    HIGH --> HIGH_R
    SEV --> SEV_R
    EXT --> CRIT_R

    EXT --> HUMAN[need_human = true]
    HI[dangerous heat_index] --> CRIT
    HI --> HUMAN
```

---

## Suggested Agent Delegation

```mermaid
flowchart TB
    HRef[HeatwaveReflectionEngine] --> SUG[suggested_agents]

    SUG --> UP[urban_planning_agent<br/>UHI / cooling infrastructure]
    SUG --> WR[water_resource_agent<br/>water distribution stress]
    SUG --> AQ[air_quality_agent<br/>compound heat-AQI risk]
    SUG --> FL[flood_agent<br/>extreme rainfall compound]
    SUG --> DR[disaster_agent<br/>EXTREME severity]

    HDE[HeatwaveDecisionEngine] --> SUG2[need_other_agents]
    SUG2 --> SUG

    style HRef fill:#ffe0b2
    style HDE fill:#cce5ff
```
