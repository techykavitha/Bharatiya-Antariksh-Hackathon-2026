# Flood Agent Workflow

> **Version:** 0.2.0  
> **Last Updated:** 2026-07-07  
> **Source:** `backend/agents/specialized/flood/`

---

## End-to-End Invocation Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant FA as FloodAgent
    participant MM as MemoryManager
    participant DT as DigitalTwinInterface
    participant TM as ToolManager
    participant FRE as FloodReasoningEngine
    participant FRef as FloodReflectionEngine
    participant FVal as FloodValidator
    participant FDE as FloodDecisionEngine
    participant AC as AgentCommunicationInterface
    participant RL as SpecializedRLEngineInterface
    participant FRB as FloodReportBuilder
    participant WS as WorkflowState

    Client->>FA: invoke(AgentRequest)
    FA->>FA: initialize() if needed
    FA->>FA: FloodMetricsCollector.start()

    rect rgb(230, 245, 255)
        Note over FA,DT: Observe Phase
        FA->>FA: retrieve_context(request)
        FA->>FA: FloodInputs.from_request_context()
        FA->>FA: preprocess(context)
        FA->>MM: search(vector) + retrieve(working:latest)
        FA->>MM: retrieve(climate:current_state)
        FA->>MM: search(forecast_summary)
        opt twin_id present
            FA->>DT: get_state(twin_id)
            DT-->>FA: digital_twin_state
        end
    end

    rect rgb(255, 245, 230)
        Note over FA,TM: Analyze Phase (parallel tools)
        FA->>TM: execute(ALL_FLOOD_TOOL_NAMES, PARALLEL)
        TM-->>FA: ToolResult[]
        Note right of TM: rainfall_tool, river_tool,<br/>reservoir_tool, terrain_tool,<br/>dem_tool, historical_flood_tool,<br/>population_tool, forecast_tool,<br/>digital_twin_tool
    end

    rect rgb(240, 255, 240)
        Note over FA,FRE: Reason Phase
        FA->>FRE: run(context, tool_results)
        FRE-->>FA: ReasoningResult + FloodAnalysisSignals
    end

    FA->>FRef: evaluate(context, reasoning, tool_results)
    FRef-->>FA: ReflectionResult

    FA->>FVal: validate(context, tool_results)
    FVal-->>FA: ValidationResult

    FA->>FDE: evaluate(context, reasoning, reflection)
    FDE-->>FA: local DecisionRequest

    opt decision.suggested_agents
        FA->>AC: call_other_agents(suggested_agents)
        AC-->>FA: AgentDelegationResult[]
    end

    opt decision.need_rl
        FA->>RL: request_policy(scenario_id, context)
        RL-->>FA: policy
    end

    FA->>FRB: build(context, reasoning, tools, reflection, validation, decision)
    FRB-->>FA: FloodReport

    FA->>MM: store(working:flood_report:{request_id})
    FA->>FA: update_memory() + update_state()
    FA-->>Client: AgentResponse (structured_output, metrics)
```

---

## Workflow State Machine

```mermaid
stateDiagram-v2
    [*] --> Initializing: invoke()
    Initializing --> Reasoning: metrics.start()

    state Reasoning {
        [*] --> Observe
        Observe --> Analyze: context hydrated
        Analyze --> Reason: tool_outputs set
        Reason --> Reflect: flood_signals computed
        Reflect --> Validate: confidence assessed
        Validate --> Decide: inputs verified
        Decide --> Delegate: local DecisionRequest
        Delegate --> RLRequest: suggested_agents handled
        RLRequest --> Report: need_rl handled
        Report --> Persist: FloodReport built
        Persist --> [*]
    }

    Reasoning --> Completed: success
    Reasoning --> Failed: AgentInvocationError
    Completed --> [*]
    Failed --> [*]

    note right of Observe
        FloodInputs, climate_state,
        forecast, digital_twin
    end note

    note right of Decide
        FloodDecisionEngine rules:
        RL, simulation, agent delegation
    end note
```

---

## Reasoning Pipeline

```mermaid
flowchart TD
    START([FloodReasoningEngine.run]) --> OBS[observe]
    OBS --> RAIN[identify_heavy_rainfall]
    RAIN --> RIV[identify_river_overflow]
    RIV --> TER[check_terrain]
    TER --> RES[check_reservoirs]
    RES --> HIST[compare_historical_events]
    HIST --> PROB[estimate_flood_probability]
    PROB --> SEV[estimate_severity]
    SEV --> UNC[estimate_uncertainty]
    UNC --> REC[generate_recommendations]

    RAIN -.->|rainfall_tool| TR[Tool Outputs]
    RIV -.->|river_tool| TR
    TER -.->|terrain_tool, dem_tool| TR
    RES -.->|reservoir_tool| TR
    HIST -.->|historical_flood_tool| TR

    REC --> OUT[ReasoningResult]
    OUT --> META[flood_signals, severity,<br/>probability, stages]

    style START fill:#e8f4fc
    style OUT fill:#d4edda
    style META fill:#fff3cd
```

---

## Flood Decision Engine Rules

```mermaid
flowchart LR
    IN[ReasoningResult + ReflectionResult] --> RL{need_rl?}
    RL -->|MAJOR/CATASTROPHIC<br/>composite ≥ 0.65<br/>uncertainty < 0.5| RL_Y[need_rl = true]

    IN --> WR{need_water_resource?}
    WR -->|reservoir_stressed<br/>or level ≥ 80%| WR_Y[suggest water_resource_agent]

    IN --> DIS{need_disaster?}
    DIS -->|MAJOR/CATASTROPHIC| DIS_Y[suggest disaster_agent]

    IN --> CY{need_cyclone?}
    CY -->|cyclone/storm surge/coastal query| CY_Y[suggest cyclone_agent]

    IN --> URB{need_urban?}
    URB -->|urban_pluvial_risk<br/>or density > 0.5| URB_Y[suggest urban_planning_agent]

    IN --> SIM{need_simulation?}
    SIM -->|MODERATE+ severity<br/>or composite ≥ 0.45| SIM_Y[need_simulation = true]

    IN --> FC{need_forecast_update?}
    FC -->|no forecast or high rainfall| FC_Y[need_forecast_update = true]

    RL_Y --> PRI[priority: critical/high/normal]
    WR_Y --> PRI
    DIS_Y --> PRI
    PRI --> OUT[local DecisionRequest]

    style OUT fill:#d4edda
```

---

## Context & Memory Hydration (Observe)

```mermaid
flowchart TB
    REQ[AgentRequest] --> CTX[AgentContext]
    CTX --> FI[FloodInputs]

    subgraph Memory["MemoryManager"]
        VS[Vector search: query]
        WK[Working: agent_id:latest]
        CL[Climate: current_state]
        FC[Vector: forecast_summary]
    end

    CTX --> VS
    CTX --> WK
    CTX --> CL
    CTX --> FC

    subgraph Optional["Optional Enrichment"]
        DT[Digital Twin state]
        SIM[Active simulation from climate_state]
    end

    CL --> SIM
    REQ --> DT

    FI --> META[context.metadata.flood_inputs]
    META --> DONE[Observe complete]

    style DONE fill:#d4edda
```

---

## LangGraph Node Integration

```mermaid
sequenceDiagram
    participant LG as LangGraph
    participant FA as FloodAgent
    participant WS as WorkflowState

    LG->>FA: as_graph_node(state)
    FA->>FA: build AgentRequest from conversation/messages
    FA->>FA: invoke(request)
    FA->>FA: update_state(context, report)
    FA->>WS: append conversation turn
    FA-->>LG: state_update + flood metadata
    Note over LG,FA: metadata: flood_risk_level,<br/>flood_severity, flood_type
```
