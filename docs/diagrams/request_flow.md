# Request Flow

> **Last Updated:** 2026-07-07

---

## End-to-End Request Flow

```mermaid
sequenceDiagram
    actor User
    participant API as API Layer (future)
    participant CS as ClimateSupervisor
    participant LG as LangGraph
    participant DS as DomainSupervisor
    participant MM as MemoryManager

    User->>API: HTTP Request (future)
    API->>CS: AgentRequest
    CS->>LG: ainvoke(initial_state)

    LG->>CS: node_classify_intent
    CS-->>LG: intent

    LG->>CS: node_plan
    CS-->>LG: execution_plan

    LG->>CS: node_execute
    CS->>DS: invoke(request)
    DS-->>CS: AgentResponse
    CS-->>LG: execution_results

    LG->>CS: node_merge_results
    CS-->>LG: merged_result

    LG->>CS: node_store_memory
    CS->>MM: store(conversation + workflow)
    MM-->>CS: keys
    CS-->>LG: memory_stored

    LG->>CS: node_return_response
    CS-->>LG: response message

    LG-->>CS: final WorkflowState
    CS-->>API: SupervisorResponse
    API-->>User: HTTP Response (future)
```

---

## Request Object Transformation

```mermaid
flowchart LR
    AR[AgentRequest] --> WS[WorkflowState]
    WS --> IC[IntentClassification]
    IC --> EP[ExecutionPlan]
    EP --> ER[ExecutionResult]
    ER --> MR[MergedSupervisorResult]
    MR --> SR[SupervisorResponse]
```

---

## AgentRequest Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | `str` | Yes | User query text |
| `session_id` | `str` | Yes | Session identifier |
| `request_id` | `str` | No (auto-generated) | Unique request ID |
| `context` | `dict` | No | Additional context |
| `metadata` | `dict` | No | Extensible metadata |

---

## SupervisorResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | `str` | Request identifier |
| `content` | `str` | Response text |
| `intent` | `str` | Classified intent |
| `supervisors_invoked` | `list[str]` | Domain supervisors called |
| `metadata` | `dict` | Execution metadata |
| `status` | `str` | Final status |

---

## Current vs. Future Entry Points

| Entry Point | Status | Description |
|-------------|--------|-------------|
| `ClimateSupervisor.process_request()` | ✅ Implemented | Direct Python API |
| FastAPI HTTP endpoint | ⬜ Not started | REST API wrapper |
| Climate Copilot | ⬜ Not started | Conversational UI |
| WebSocket streaming | ⬜ Not started | Real-time response streaming |

---

## Related Documents

- [Supervisor Flow](./supervisor_flow.md)
- [Climate Supervisor](../supervisor/climate_supervisor.md)
- [Execution Flow](./execution_flow.md)
