# Agent → Decision → RL Flow

> **Version:** 0.2.0  
> **Last Updated:** 2026-07-07

---

## Unified Pipeline (Heatwave Agent)

```mermaid
sequenceDiagram
    participant HA as HeatwaveAgent
    participant DE as HeatwaveDecisionEngine
    participant DM as DecisionManager
    participant RL as RLOptimizationService
    participant XAI as ExplanationEngine

    HA->>DE: build DecisionRequest
    DE->>DM: validate constraints
    DM-->>DE: validated request
    HA->>RL: optimize(DecisionRequest)
    RL->>RL: encode state → policy → action
    RL-->>HA: DecisionResponse
    HA->>HA: build HeatwaveReport
    Note over HA,XAI: Optional post-hoc
    HA->>XAI: explain_decision(request, response)
    XAI-->>HA: ExplainabilityReport
```

---

## Legacy Pipeline (Flood / Water Agents)

```mermaid
sequenceDiagram
    participant AG as Flood/Water Agent
    participant LDE as Local Decision Engine
    participant RL as SpecializedRLEngineInterface

    AG->>LDE: build local decision payload
    LDE-->>AG: ranked actions
    AG->>RL: request_rl(context)
    RL-->>AG: policy recommendation
    AG->>AG: merge into report
```

---

## Decision Payload Standardization Roadmap

```mermaid
flowchart LR
    A[Flood Local Schema] -->|migrate| U[Unified DecisionRequest]
    B[Water Local Schema] -->|migrate| U
    C[Heatwave Unified Schema] --> U
    U --> RL[RLOptimizationService]
    U --> XAI[ExplanationEngine]
```
