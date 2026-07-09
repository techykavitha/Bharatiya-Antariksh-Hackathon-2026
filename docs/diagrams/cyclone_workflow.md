# Cyclone Agent Workflow

> **Version:** 0.3.0 | **Last Updated:** 2026-07-09

```mermaid
flowchart TB
    REQ[AgentRequest] --> OBS[Observe]
    OBS --> PEER[Collect Peer Inputs]
    PEER --> ANA[Analyze - 12 Tools]
    ANA --> REA[Reason - CycloneReasoningEngine]
    REA --> REF[Reflect - CycloneReflectionEngine]
    REF --> VAL[Validate - CycloneValidator]
    VAL --> DEC[Decision - CycloneDecisionEngine]
    DEC --> RL[RL - RLOptimizationService]
    RL --> XAI[Explainability - ExplanationEngine]
    XAI --> RPT[Report - CycloneReportBuilder]
    RPT --> MEM[Memory + State Update]
    MEM --> RES[AgentResponse]

    subgraph Tools["12 Cyclone Tools"]
        T1[SST Tool]
        T2[Pressure Tool]
        T3[Wind Tool]
        T4[Ocean Heat Tool]
        T5[INSAT Tool]
        T6[Forecast Tool]
        T7[Historical Cyclone Tool]
        T8[Storm Surge Tool]
        T9[Digital Twin Tool]
        T10[Knowledge Graph Tool]
        T11[Population Tool]
        T12[Infrastructure Tool]
    end

    ANA --> Tools
```
