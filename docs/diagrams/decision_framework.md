# Decision Framework

> **Version:** 0.2.0  
> **Last Updated:** 2026-07-07  
> **Source:** `backend/decision/`

---

## Architecture Overview

```mermaid
flowchart TB
    subgraph Agents["Specialized Agents"]
        HA[HeatwaveAgent]
        FA[FloodAgent]
        WA[WaterResourceAgent]
    end

    subgraph LocalEngines["Agent-Local Decision Engines"]
        HDE[HeatwaveDecisionEngine]
        FDE[FloodDecisionEngine]
        WDE[WaterDecisionEngine]
    end

    subgraph Framework["backend/decision/"]
        DM[DecisionManager]
        DV[DecisionValidator]
        DS[DecisionSerializer]
        DP[DecisionPriority]
        DC[DecisionConstraints]
        DA[DecisionActions]
    end

    subgraph Consumers["Downstream Consumers"]
        RL[RLOptimizationService]
        ORCH[Decision Orchestrator]
        DB[(Persistence)]
        XAI[ExplanationEngine]
    end

    HA --> HDE --> DM
    FA --> FDE
    WA --> WDE

    FDE -.->|local schema<br/>migration planned| DM
    WDE -.->|local schema<br/>migration planned| DM

    DM --> DV
    DM --> DS
    DM --> DP
    DM --> DC
    DM --> DA

    DM --> RL
    DM --> ORCH
    DS --> DB
    RL --> DM
    DM --> XAI

    style DM fill:#cce5ff
    style HA fill:#d4edda
```

---

## DecisionRequest Schema

```mermaid
classDiagram
    class DecisionRequest {
        +str decision_id
        +str agent_id
        +DecisionType decision_type
        +DecisionPriority priority
        +DecisionStatus status
        +DecisionContext context
        +list~Objective~ objectives
        +DecisionConstraints constraints
        +list~DecisionAction~ possible_actions
        +RiskAssessment risk
        +float confidence
        +bool need_simulation
        +list need_other_agents
        +bool need_human
        +bool need_rl
        +list rationale
        +to_rl_payload()
    }

    class DecisionResponse {
        +str response_id
        +str decision_id
        +DecisionStatus status
        +DecisionAction chosen_action
        +list~ActionRanking~ ranking
        +float reward
        +float confidence
        +list~RejectedAction~ rejected_actions
        +is_successful()
    }

    class DecisionContext {
        +ScenarioContext scenario
        +ClimateState climate_state
        +ForecastReference forecast_reference
        +SimulationReference simulation_reference
    }

    class Objective {
        +str objective_id
        +str description
        +float weight
        +bool maximize
    }

    class DecisionAction {
        +str action_id
        +str description
        +float cost
        +RiskLevel risk
        +float expected_benefit
        +float net_value
    }

    class RiskAssessment {
        +RiskLevel level
        +float score
        +list factors
        +int affected_population
        +int horizon_hours
    }

    DecisionRequest --> DecisionContext
    DecisionRequest --> Objective
    DecisionRequest --> DecisionAction
    DecisionRequest --> RiskAssessment
    DecisionResponse --> DecisionAction
```

---

## DecisionManager Lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant Agent
    participant DM as DecisionManager
    participant DV as DecisionValidator
    participant DS as DecisionSerializer
    participant Q as Priority Queue
    participant RL as RLOptimizationService

    Agent->>DM: create(agent_id, decision_type, objectives, actions, ...)
    DM->>DM: build DecisionRequest (status=PENDING)
    DM->>DV: validate_request(strict?)
    DV-->>DM: ValidationResult

    alt validation fails (strict)
        DV-->>Agent: DecisionValidationError
    end

    DM->>DM: store in _requests registry

    opt queue for orchestration
        Agent->>DM: queue(request)
        DM->>DV: validate_request()
        DM->>Q: heappush(priority, confidence, id)
        Note over Q: status → QUEUED
    end

    opt dequeue for processing
        DM->>Q: dequeue()
        Q-->>DM: highest-priority request
        Note over DM: status → PROCESSING
    end

    Agent->>RL: optimize(DecisionRequest)
    RL-->>Agent: DecisionResponse
    Agent->>DM: store_response(response)
    DM->>DM: update request status

    opt persistence
        DM->>DS: to_json / to_db_record
        DS-->>DM: serialized payload
    end
```

---

## Validation Pipeline

```mermaid
flowchart TD
    REQ[DecisionRequest] --> VAL[DecisionValidator.validate_request]

    VAL --> OBJ[_validate_objectives]
    VAL --> ACT[_validate_actions]
    VAL --> CON[_validate_constraints]
    VAL --> CONF[_validate_confidence]
    VAL --> RISK[_validate_risk]
    VAL --> CTX[_validate_context]
    VAL --> FLG[_validate_flags]

    OBJ --> O1{duplicate objective_id?}
    OBJ --> O2{positive total weight?}

    ACT --> A1{≥ 1 possible_action?}
    ACT --> A2{action vs budget constraint}
    ACT --> A3{action vs safety constraint}
    ACT --> A4{action vs population constraint}
    ACT --> A5{no-go regions?}

    CTX --> C1{need_simulation without ref?}
    CTX --> C2{need_rl without actions?}

    OBJ --> ISSUES[ValidationIssue list]
    ACT --> ISSUES
    CON --> ISSUES
    CONF --> ISSUES
    RISK --> ISSUES
    CTX --> ISSUES
    FLG --> ISSUES

    ISSUES --> RESULT[ValidationResult]
    RESULT -->|blocking issues = 0| OK[valid = true]
    RESULT -->|strict mode + errors| ERR[DecisionValidationError]

    style OK fill:#d4edda
    style ERR fill:#f8d7da
```

---

## Priority Queue & Scheduling

```mermaid
stateDiagram-v2
    [*] --> DRAFT: initial
    DRAFT --> PENDING: DecisionManager.create()
    PENDING --> QUEUED: queue()
    QUEUED --> PROCESSING: dequeue()
    PROCESSING --> COMPLETED: store_response()
    PROCESSING --> FAILED: optimization error
    QUEUED --> CANCELLED: cancel
    PENDING --> CANCELLED: cancel
    COMPLETED --> [*]
    FAILED --> [*]
    CANCELLED --> [*]

    note right of QUEUED
        Max-heap ordered by:
        -priority (negated)
        -confidence (negated)
        -decision_id
    end note
```

---

## Priority Resolution

```mermaid
flowchart LR
    BASE[base_priority] --> PC[PriorityContext.resolve]

    PC --> OVR{override set?}
    OVR -->|yes| OUT[resolved priority]
    OVR -->|no| ESC

    ESC{risk_escalation?} -->|yes| E1[escalate +1]
    E1 --> HUM
    ESC -->|no| HUM

    HUM{human_waiting?} -->|yes| E2[escalate +1]
    HUM -->|no| OUT
    E2 --> OUT

    subgraph Levels["DecisionPriority (IntEnum)"]
        D0[DEFERRED = 0]
        D1[LOW = 1]
        D2[NORMAL = 2]
        D3[HIGH = 3]
        D4[URGENT = 4]
        D5[CRITICAL = 5]
    end

    OUT --> Levels
```

---

## Merge Multiple Agent Decisions

```mermaid
flowchart TD
    R1[Flood DecisionRequest] --> MERGE[DecisionManager.merge]
    R2[Water DecisionRequest] --> MERGE
    R3[Heatwave DecisionRequest] --> MERGE

    MERGE --> PRI[max priority across requests]
    MERGE --> RISK[max risk level + score]
    MERGE --> CONF[avg confidence]
    MERGE --> OBJ[dedupe objectives]
    MERGE --> ACT[dedupe possible_actions]
    MERGE --> FLAGS[OR need_simulation, need_human, need_rl]
    MERGE --> AGENTS[union need_other_agents]

    PRI --> OUT[Unified DecisionRequest]
    RISK --> OUT
    CONF --> OUT
    OBJ --> OUT
    ACT --> OUT
    FLAGS --> OUT
    AGENTS --> OUT

    OUT --> META[metadata.merged_from: source decision_ids]
    OUT --> ORCH[agent_id = decision_orchestrator]

    style OUT fill:#d4edda
```

---

## Compare Two Decisions

```mermaid
flowchart LR
    A[DecisionRequest A] --> CMP[DecisionManager.compare]
    B[DecisionRequest B] --> CMP

    CMP --> PD[priority_delta]
    CMP --> CD[confidence_delta]
    CMP --> RD[risk_delta]
    CMP --> ST[same_type / same_agent flags]
    CMP --> WIN[higher_priority,<br/>higher_confidence,<br/>higher_risk IDs]

    WIN --> DC[DecisionComparison]
```

---

## Decision Types

```mermaid
flowchart TB
    DT[DecisionType enum]

    DT --> FLOOD[flood]
    DT --> WATER[water]
    DT --> AGRI[agriculture]
    DT --> HEAT[heatwave]
    DT --> URBAN[urban]
    DT --> AQI[aqi]
    DT --> CYCLONE[cyclone]
    DT --> DISASTER[disaster]
    DT --> GEN[general]

    HEAT -->|implemented| HDE[HeatwaveDecisionEngine]
    FLOOD -.->|local schema| FDE[FloodDecisionEngine]
    WATER -.->|local schema| WDE[WaterDecisionEngine]

    style HEAT fill:#d4edda
    style FLOOD fill:#fff3cd
    style WATER fill:#fff3cd
```

---

## RL Payload Flow

```mermaid
sequenceDiagram
    participant Agent
    participant DR as DecisionRequest
    participant RL as RLOptimizationService
    participant DResp as DecisionResponse
    participant DM as DecisionManager

    Agent->>DR: to_rl_payload()
    Note over DR: strips agent_id, metadata,<br/>rationale, timestamps, status

    Agent->>RL: optimize(DecisionRequest)
    RL->>RL: encode state → policy → action ranking
    RL-->>DResp: chosen_action + ranking + reward

    Agent->>DM: store_response(DecisionResponse)
    DM->>DM: validate_response(response, request)
    DM->>DM: sync request.status

    Note over Agent,DResp: Response must reference<br/>matching decision_id
```

---

## Constraint Categories

```mermaid
flowchart TB
    DC[DecisionConstraints]

    DC --> BUD[BudgetConstraint<br/>max_cost, currency]
    DC --> TIME[TimeConstraint<br/>max_hours, deadline]
    DC --> WATER[WaterConstraint<br/>release, reserve, extraction]
    DC --> POWER[PowerConstraint<br/>max_load_mw]
    DC --> POP[PopulationConstraint<br/>max_affected_population]
    DC --> ENV[EnvironmentConstraint<br/>emissions, protected_areas]
    DC --> POL[PolicyConstraint<br/>approval_required]
    DC --> SAFE[SafetyConstraint<br/>max_risk_score, no_go_regions]

    BUD --> VAL[DecisionValidator<br/>action constraint checks]
    TIME --> VAL
    WATER --> VAL
    POP --> VAL
    SAFE --> VAL
```
