# Urban Planning Workflow

> **Version:** 0.3.0 | **Last Updated:** 2026-07-09

```mermaid
flowchart TB
    REQ[AgentRequest] --> OBS[Observe + CKG Query]
    OBS --> PEER[Collect Peer Inputs]
    PEER --> ANA[Analyze - 11 Urban Tools]
    ANA --> REA[UrbanReasoningEngine]
    REA --> VAL[UrbanValidator]
    VAL --> REF[UrbanReflectionEngine]
    REF --> DEC[UrbanDecisionEngine]
    DEC --> RL[RLOptimizationService]
    RL --> XAI[ExplanationEngine]
    XAI --> RPT[UrbanPlanningReport]
    RPT --> RES[AgentResponse]

    subgraph Reasoning["Long-Term Adaptation Reasoning"]
        R1[Urban Environment]
        R2[Heat Risk / UHI]
        R3[Flood Risk]
        R4[Green Cover Gap]
        R5[Mitigation Portfolio]
        R6[Investment Priorities]
    end

    REA --> Reasoning
```
