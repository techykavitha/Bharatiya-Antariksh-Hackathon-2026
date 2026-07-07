# Execution Flow

> **Last Updated:** 2026-07-07

---

## Full System Execution Flow

```mermaid
flowchart TD
    START([User Query]) --> AR[AgentRequest]
    AR --> CS[ClimateSupervisor.process_request]

    subgraph Climate Layer
        CS --> CI[IntentClassifier]
        CI --> PL[Planner]
        PL --> WR[WorkflowRouter]
        WR --> EX{Execution Mode}
        EX -->|sequential| SEQ[Executor]
        EX -->|parallel| PAR[ParallelExecutor]
    end

    subgraph Domain Layer
        SEQ --> DS[DomainSupervisor.invoke]
        PAR --> DS
        DS --> SEL[select_agents]
        SEL --> BP[build_plan]
        BP --> DE[DomainExecutor]
        DE --> AG[Specialized Agent - future]
    end

    subgraph Memory Layer
        AG --> DM[Domain merge_results]
        DM --> UM[update_memory]
        SEQ --> CM[Climate merge_results]
        PAR --> CM
        CM --> SM[store_memory]
        SM --> MM[MemoryManager]
    end

    CM --> RR[return_response]
    RR --> END([SupervisorResponse])
```

---

## Parallel vs. Sequential Execution

```mermaid
flowchart TD
    PLAN[ExecutionPlan] --> CHECK{mode?}

    CHECK -->|sequential| S1[Supervisor 1]
    S1 --> S2[Supervisor 2]
    S2 --> S3[Supervisor 3]
    S3 --> RESULT[ExecutionResult]

    CHECK -->|parallel| P1[Supervisor 1]
    CHECK -->|parallel| P2[Supervisor 2]
    CHECK -->|parallel| P3[Supervisor 3]
    P1 --> GATHER[asyncio.gather]
    P2 --> GATHER
    P3 --> GATHER
    GATHER --> RESULT
```

---

## Domain-Level Execution

```mermaid
flowchart TD
    DS[DomainSupervisor] --> SEL[select_agents]
    SEL --> REG{Agents Registered?}
    REG -->|Yes| EXEC[DomainExecutor.execute]
    REG -->|No| FALLBACK[Fallback Response]
    EXEC --> MODE{Mode}
    MODE -->|SEQUENTIAL| SA1[Agent 1 → Agent 2]
    MODE -->|PARALLEL| SA2[Agent 1 + Agent 2 concurrent]
    MODE -->|CONDITIONAL| SA3[Agent 1 → check → Agent 2]
    SA1 --> MERGE[merge_results]
    SA2 --> MERGE
    SA3 --> MERGE
    FALLBACK --> MERGE
    MERGE --> RESP[AgentResponse]
```

---

## Retry Execution

```mermaid
sequenceDiagram
    participant DE as DomainExecutor
    participant Agent
    participant Policy as ExecutionPolicy

    DE->>Agent: invoke(request)
    Agent-->>DE: Exception
    DE->>Policy: should_retry(attempt=1)
    Policy-->>DE: true
    Note over DE: wait(retry_delay)
    DE->>Agent: invoke(request)
    Agent-->>DE: AgentResponse
```

---

## Bootstrap Execution Sequence

```mermaid
sequenceDiagram
    participant App
    participant Boot as bootstrap.py
    participant Config
    participant MM as MemoryManager
    participant CS as ClimateSupervisor
    participant DR as DomainRegistry

    App->>Boot: initialize()
    Boot->>Config: get_config()
    Boot->>MM: create_in_memory()
    Boot->>CS: create(memory)
    Boot->>DR: register_all_defaults(memory)
    Boot->>CS: initialize()
    CS-->>Boot: graph compiled
    Boot-->>App: ready
```

---

## Related Documents

- [Supervisor Flow](./supervisor_flow.md)
- [Domain Flow](./domain_flow.md)
- [Request Flow](./request_flow.md)
