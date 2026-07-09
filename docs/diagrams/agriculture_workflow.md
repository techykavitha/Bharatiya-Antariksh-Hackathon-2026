# Agriculture Agent Workflow

> **Version:** 0.3.0 | **Last Updated:** 2026-07-09

```mermaid
flowchart TB
    REQ[AgentRequest] --> OBS[Observe + CKG Query]
    OBS --> PEER[Collect Peer Inputs]
    PEER --> ANA[Analyze - 12 Agriculture Tools]
    ANA --> RAG[Retrieve Knowledge - AgricultureRagService]
    RAG --> REA[AgricultureReasoningEngine]
    REA --> VAL[AgricultureValidator]
    VAL --> REF[AgricultureReflectionEngine]
    REF --> DEC[AgricultureDecisionEngine]
    DEC --> RL[RLOptimizationService]
    RL --> XAI[ExplanationEngine]
    XAI --> RPT[AgricultureReport]
    RPT --> RES[AgentResponse]
```

## Agriculture RAG Pipeline

```mermaid
flowchart LR
    Q[Query + crop/region/season] --> RET[AgricultureKnowledgeRetriever]
    RET --> CORPUS[(Document Corpus)]
    CORPUS --> CAL[Crop Calendars]
    CORPUS --> ADV[Government Advisories]
    CORPUS --> BP[Best Practices]
    CORPUS --> HF[Historical Failures]
    CORPUS --> ADAPT[Adaptation Guidelines]
    RET --> RANK[Relevance Ranking]
    RANK --> OUT[RagRetrievalResult]
    OUT --> REA[AgricultureReasoningEngine]
```
