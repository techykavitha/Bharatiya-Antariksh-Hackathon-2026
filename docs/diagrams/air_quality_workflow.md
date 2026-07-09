# Air Quality Agent Workflow

> **Version:** 0.3.0 | **Last Updated:** 2026-07-09

```mermaid
flowchart TB
    REQ[AgentRequest] --> OBS[Observe + CKG Query]
    OBS --> PEER[Collect Peer Inputs]
    PEER --> ANA[Analyze - 12 AQ Tools]
    ANA --> REA[AirQualityReasoningEngine]
    REA --> VAL[AirQualityValidator]
    VAL --> REF[AirQualityReflectionEngine]
    REF --> DEC[AirQualityDecisionEngine]
    DEC --> RL[RLOptimizationService]
    RL --> XAI[ExplanationEngine]
    XAI --> RPT[AirQualityReport]
    RPT --> RES[AgentResponse]

    subgraph Reasoning["Pollution Reasoning Chain"]
        M[Meteorology]
        S[Pollution Sources]
        T[Transport]
        D[Dispersion]
        A[AQI Assessment]
        E[Population Exposure]
        H[Health Risk]
        MIT[Mitigation Strategy]
    end

    REA --> Reasoning
```
