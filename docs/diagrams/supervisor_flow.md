# Supervisor Flow

> **Last Updated:** 2026-07-07

---

## LangGraph Pipeline

```mermaid
graph LR
    START([START]) --> CI[classify_intent]
    CI --> PL[plan]
    PL --> EX[execute]
    EX --> MR[merge_results]
    MR --> SM[store_memory]
    SM --> RR[return_response]
    RR --> END([END])
```

---

## Node Responsibilities

| Node | Input State Fields | Output State Fields |
|------|-------------------|-------------------|
| `classify_intent` | `query` | `intent`, `metadata.intent_classification` |
| `plan` | `intent`, `query` | `plan`, `metadata.execution_plan` |
| `execute` | `plan` | `execution_results`, `metadata.supervisor_results` |
| `merge_results` | `execution_results` | `merged_result` |
| `store_memory` | `merged_result`, `messages` | `metadata.memory_stored` |
| `return_response` | `merged_result` | `status`, `messages` (response) |

---

## Intent Classification Flow

```mermaid
flowchart TD
    Q[User Query] --> IC{IntentClassifier}
    IC -->|flood, rain, water level| NOWCAST
    IC -->|forecast, predict, tomorrow| FORECAST
    IC -->|what if, scenario, simulate| WHAT_IF
    IC -->|risk, vulnerability, hazard| RISK_ASSESSMENT
    IC -->|resource, allocation, supply| RESOURCE_PLANNING
    IC -->|emergency, disaster, evacuate| EMERGENCY_RESPONSE
    IC -->|policy, regulation, compliance| POLICY_ANALYSIS
    IC -->|data, dataset, retrieve| DATA_QUERY
    IC -->|default| GENERAL_QA
```

---

## Planning and Routing

```mermaid
flowchart TD
    INTENT[Classified Intent] --> PL[Planner]
    PL --> MAP{Intent → Supervisor Map}
    MAP --> AVAIL[Filter Available Supervisors]
    AVAIL --> MODE{Execution Mode}
    MODE -->|sequential| SEQ[Sequential Plan]
    MODE -->|parallel| PAR[Parallel Plan]
    SEQ --> EP[ExecutionPlan]
    PAR --> EP
```

---

## Execution Flow

```mermaid
sequenceDiagram
    participant CS as ClimateSupervisor
    participant EX as Executor
    participant AR as AgentRegistry
    participant DS as DomainSupervisor

    CS->>EX: execute(plan, context)
    alt Sequential Mode
        loop Each supervisor in plan
            EX->>AR: resolve(supervisor_id)
            AR-->>EX: DomainSupervisorHandler
            EX->>DS: invoke(request)
            DS-->>EX: AgentResponse
        end
    else Parallel Mode
        EX->>AR: resolve(all supervisors)
        par Concurrent invocation
            EX->>DS: invoke(request)
        end
        DS-->>EX: AgentResponse(s)
    end
    EX-->>CS: ExecutionResult
```

---

## Failure Handling

```mermaid
flowchart TD
    INV[Supervisor Invocation] --> OK{Success?}
    OK -->|Yes| RECORD[Record in execution_results]
    OK -->|No| FH[FailureHandler]
    FH --> RETRY{Retryable?}
    RETRY -->|Yes| INV
    RETRY -->|No| FAIL[Mark failed in metadata]
    FAIL --> CONTINUE[Continue with remaining supervisors]
    RECORD --> CONTINUE
```

---

## Related Documents

- [Climate Supervisor](../supervisor/climate_supervisor.md)
- [ADR-001](../decisions/ADR-001_langgraph_over_langchain.md)
- [Request Flow](./request_flow.md)
