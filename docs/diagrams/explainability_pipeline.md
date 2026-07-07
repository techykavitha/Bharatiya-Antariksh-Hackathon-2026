# Explainability Pipeline

> **Version:** 1.0.0  
> **Last Updated:** 2026-07-07  
> **Source:** `backend/xai/`

---

## Overview

The Explainability Pipeline transforms agent pipeline artifacts into a standardized `ExplainabilityReport`. Six sub-engines run under `ExplanationEngine` orchestration, producing executive summary, reasoning trace, evidence, confidence, uncertainty, alternatives, and counterfactuals.

---

## High-Level Pipeline

```mermaid
flowchart TB
    subgraph Input["ExplanationInput"]
        RE[ReasoningResult]
        TR[ToolResults]
        RF[ReflectionResult]
        VAL[ValidationResult]
        DR[DecisionRequest]
        DResp[DecisionResponse]
        MEM[Memory References]
    end

    subgraph Engine["ExplanationEngine"]
        direction TB
        EX[explain / explain_pipeline / explain_decision]
        EX --> TRACE[_maybe_trace]
        EX --> EVID[_maybe_evidence]
        EX --> CONF[_maybe_confidence]
        EX --> UNCERT[_maybe_uncertainty]
        EX --> ALT[_maybe_alternatives]
        EX --> CF[_maybe_counterfactuals]
        EX --> SUM[_build_executive_summary]
        EX --> CAV[_build_caveats]
    end

    subgraph SubEngines["Sub-Engines"]
        RTB[ReasoningTraceBuilder]
        EV[EvidenceEngine]
        CE[ConfidenceEngine]
        UE[UncertaintyEngine]
        AA[AlternativeActionsEngine]
        CFE[CounterfactualEngine]
    end

    subgraph Output["ExplainabilityReport"]
        ES[executive_summary]
        RT[reasoning_trace]
        EB[evidence]
        CONF_OUT[confidence]
        UNCERT_OUT[uncertainty]
        ALT_OUT[alternatives]
        CF_OUT[counterfactuals]
        CAS[chosen_action_summary]
        REC[recommendations]
        CAV_OUT[caveats]
    end

    RE --> EX
    TR --> EX
    RF --> EX
    VAL --> EX
    DR --> EX
    DResp --> EX
    MEM --> EX

    TRACE --> RTB
    EVID --> EV
    CONF --> CE
    UNCERT --> UE
    ALT --> AA
    CF --> CFE

    RTB --> RT
    EV --> EB
    CE --> CONF_OUT
    UE --> UNCERT_OUT
    AA --> ALT_OUT
    CFE --> CF_OUT
    SUM --> ES
    AA --> CAS
    CAV --> CAV_OUT

    EX --> Output
```

---

## Entry Points

```mermaid
flowchart LR
    subgraph APIs["ExplanationEngine APIs"]
        E1["explain(input)"]
        E2["explain_pipeline(input)"]
        E3["explain_decision(request, response?)"]
    end

    subgraph Types["ExplanationType"]
        T1[REASONING]
        T2[DECISION]
        T3[RL]
        T4[FULL_PIPELINE]
    end

    E1 -->|uses input.explanation_type| Types
    E2 -->|forces| T4
    E3 -->|response present| T3
    E3 -->|no response| T2
```

| API | Sets Type | Typical Caller |
|-----|-----------|----------------|
| `explain()` | From `ExplanationInput.explanation_type` | Custom scope control |
| `explain_pipeline()` | `FULL_PIPELINE` | Agent post-invoke |
| `explain_decision()` | `RL` or `DECISION` | Decision/RL post-hoc |

---

## Sub-Engine Data Flow

```mermaid
flowchart TB
    EI[ExplanationInput]

    EI --> RTB[ReasoningTraceBuilder]
    RTB --> RTR["ReasoningTraceReport<br/>steps, narrative, stage_sequence"]

    EI --> EV[EvidenceEngine]
    EV --> EB["EvidenceBundle<br/>climate, forecast, tools, historical, twin, memory"]

    EI --> CE[ConfidenceEngine]
    CE --> CE_OUT["ConfidenceEstimate<br/>5 dimensions, weighted overall"]

    EI --> UE[UncertaintyEngine]
    UE --> UE_OUT["UncertaintyEstimate<br/>4 dimensions, mitigations"]

    EI --> AA[AlternativeActionsEngine]
    AA --> AA_OUT["AlternativeActionsAnalysis<br/>chosen, alternatives, rejected, ranking"]

    EI --> CF[CounterfactualEngine]
    CF --> CF_OUT["CounterfactualAnalysis<br/>action, decision, scenario what-ifs"]
```

---

## Reasoning Trace Pipeline

```mermaid
sequenceDiagram
    participant EE as ExplanationEngine
    participant RTB as ReasoningTraceBuilder
    participant RR as ReasoningResult
    participant TR as ToolResults

    EE->>RTB: build(reasoning, tool_results)
    alt reasoning present with steps
        RTB->>RR: enumerate steps
        RTB->>TR: map stages to supporting tools
        RTB->>RTB: _build_narrative(steps)
        RTB-->>EE: ReasoningTraceReport (full)
    else no reasoning
        RTB-->>EE: ReasoningTraceReport (empty narrative)
    end
```

---

## Evidence Collection Pipeline

```mermaid
flowchart TD
    EI[ExplanationInput] --> EV[EvidenceEngine.collect]

    EV --> C1[_collect_climate]
    EV --> C2[_collect_forecast]
    EV --> C3[_collect_tool_evidence]
    EV --> C4[_collect_reasoning]
    EV --> C5[_collect_decision_rationale]
    EV --> C6[memory_references]

    C1 --> CL[Climate Variables]
    C2 --> FC[Forecast Outputs]
    C3 --> TE[Tool Evidence]
    C3 --> HIST[_collect_historical]
    C3 --> TWIN[_collect_digital_twin]
    C4 --> RE[Reasoning Evidence]
    C5 --> DR[Rationale Lines]
    C6 --> MEM[Memory References]

    CL --> BUNDLE[EvidenceBundle]
    FC --> BUNDLE
    TE --> BUNDLE
    HIST --> BUNDLE
    TWIN --> BUNDLE
    RE --> BUNDLE
    DR --> BUNDLE
    MEM --> BUNDLE
```

---

## Confidence & Uncertainty Pipeline

```mermaid
flowchart LR
    subgraph Confidence["ConfidenceEngine (5 dimensions)"]
        C1[MODEL 0.25]
        C2[DATA_QUALITY 0.25]
        C3[FORECAST_RELIABILITY 0.20]
        C4[TOOL_CONSISTENCY 0.15]
        C5[HISTORICAL_SIMILARITY 0.15]
    end

    subgraph Uncertainty["UncertaintyEngine (4 dimensions)"]
        U1[MISSING_DATA 0.30]
        U2[FORECAST 0.25]
        U3[MODEL 0.25]
        U4[SIMULATION 0.20]
    end

    EI[ExplanationInput] --> Confidence
    EI --> Uncertainty

    Confidence --> CO["confidence.overall<br/>(weighted sum)"]
    Uncertainty --> UO["uncertainty.overall<br/>(weighted sum)"]

    CO --> GATE["is_high_confidence<br/>conf ≥ 0.7 AND uncert ≤ 0.4"]
    UO --> GATE
```

---

## Alternatives & Counterfactuals Pipeline

```mermaid
flowchart TB
    DR[DecisionRequest] --> AA[AlternativeActionsEngine]
    DResp[DecisionResponse] --> AA

    AA --> CHOSEN[chosen_action]
    AA --> ALTS[alternatives from ranking]
    AA --> REJ[rejected_actions explanations]
    AA --> RANK[ranking echo]

    DR --> CF[CounterfactualEngine]
    DResp --> CF

    CF --> A1["ALTERNATIVE_ACTION<br/>(max 5 scenarios)"]
    CF --> A2["ALTERNATIVE_DECISION<br/>(RL bypass, simulation)"]
    CF --> A3["ALTERNATIVE_SCENARIO<br/>(worsening / improving)"]
```

---

## Report Assembly

```mermaid
sequenceDiagram
    participant EE as ExplanationEngine
    participant SUB as Sub-Engines

    EE->>SUB: parallel async calls (trace, evidence, confidence, uncertainty, alternatives, counterfactuals)
    SUB-->>EE: sub-reports

    EE->>EE: _build_executive_summary(query, confidence, uncertainty, alternatives)
    EE->>EE: _chosen_action_summary(alternatives)
    EE->>EE: _build_caveats(validation, reflection, uncertainty)

    EE->>EE: assemble ExplainabilityReport
    EE->>EE: cache _last_report
    EE-->>Caller: ExplainabilityReport
```

---

## Agent Integration Flow

```mermaid
sequenceDiagram
    participant AG as Specialized Agent
    participant TM as ToolManager
    participant RE as ReasoningEngine
    participant RF as ReflectionEngine
    participant DE as Decision Engine
    participant RL as RLOptimizationService
    participant EE as ExplanationEngine
    participant API as API / Audit

    AG->>TM: execute tools
    TM-->>AG: ToolResults
    AG->>RE: reason(context, tools)
    RE-->>AG: ReasoningResult
    AG->>RF: reflect(reasoning)
    RF-->>AG: ReflectionResult
    AG->>DE: build DecisionRequest
    DE-->>AG: DecisionRequest

    opt need_rl
        AG->>RL: optimize(request)
        RL-->>AG: DecisionResponse
    end

    AG->>EE: explain_pipeline(ExplanationInput)
    EE-->>AG: ExplainabilityReport
    AG->>API: attach report / to_audit_trace()
```

---

## ExplanationType Scope

```mermaid
flowchart TD
    TYPE{ExplanationType}

    TYPE -->|REASONING| R1[Full reasoning trace]
    TYPE -->|REASONING| R2[Full evidence]
    TYPE -->|REASONING| R3[Empty trace fallback for others]

    TYPE -->|DECISION| D1[Empty reasoning trace]
    TYPE -->|DECISION| D2[Full evidence + decision engines]

    TYPE -->|RL| RL1[Empty reasoning trace]
    TYPE -->|RL| RL2[Full evidence + RL ranking analysis]

    TYPE -->|FULL_PIPELINE| F1[All components full]
```

---

## Audit Trace Export

```mermaid
flowchart LR
    ER[ExplainabilityReport] --> TAU[to_audit_trace]

    TAU --> L1[executive_summary]
    TAU --> L2["reasoning_trace.narrative (max 5)"]
    TAU --> L3[chosen_action_summary]
    TAU --> L4["caveats (max 3)"]

    L1 --> OUT["list[str] for API / compliance"]
    L2 --> OUT
    L3 --> OUT
    L4 --> OUT
```

---

## Test Coverage Map

```mermaid
flowchart TB
    subgraph Unit["7 Unit Tests"]
        U1[ReasoningTraceBuilder]
        U2[EvidenceEngine]
        U3[ConfidenceEngine]
        U4[UncertaintyEngine]
        U5[AlternativeActionsEngine]
        U6[CounterfactualEngine]
        U7[ExplanationInput validation]
    end

    subgraph Integration["6 Integration Tests"]
        I1[full_pipeline]
        I2[decision_only]
        I3[rl_convenience]
        I4[audit_trace]
        I5[heatwave_decision]
        I6[minimal_input]
    end

    U1 --> EE[ExplanationEngine]
    U2 --> EE
    U3 --> EE
    U4 --> EE
    U5 --> EE
    U6 --> EE
    U7 --> EE

    EE --> I1
    EE --> I2
    EE --> I3
    EE --> I4
    EE --> I5
    EE --> I6
```
