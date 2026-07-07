# State Flow

> **Last Updated:** 2026-07-07

---

## WorkflowState Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Created: create_initial_workflow_state()
    Created --> Classifying: node_classify_intent
    Classifying --> Planning: node_plan
    Planning --> Executing: node_execute
    Executing --> Merging: node_merge_results
    Merging --> Storing: node_store_memory
    Storing --> Responding: node_return_response
    Responding --> Completed: status = completed
    Completed --> [*]

    Classifying --> Failed: error
    Planning --> Failed: error
    Executing --> Failed: error
    Merging --> Failed: error
    Storing --> Failed: error
    Responding --> Failed: error
    Failed --> [*]
```

---

## State Field Evolution

```mermaid
flowchart TD
    subgraph Initial
        I1[request_id]
        I2[session_id]
        I3[query]
        I4[messages: empty]
        I5[status: pending]
    end

    subgraph After classify_intent
        A1[intent]
        A2[metadata.intent_classification]
    end

    subgraph After plan
        B1[plan]
        B2[metadata.execution_plan]
    end

    subgraph After execute
        C1[execution_results]
        C2[metadata.supervisor_results]
    end

    subgraph After merge
        D1[merged_result]
    end

    subgraph After store_memory
        E1[metadata.memory_stored = true]
    end

    subgraph After return_response
        F1[status = completed]
        F2[messages: response added]
    end

    Initial --> After classify_intent
    After classify_intent --> After plan
    After plan --> After execute
    After execute --> After merge
    After merge --> After store_memory
    After store_memory --> After return_response
```

---

## LangGraph Reducers

```mermaid
flowchart LR
    subgraph messages
        M1[add_messages reducer]
        M1 --> APPEND[Append new messages]
    end

    subgraph metadata
        MD1[merge_dicts reducer]
        MD1 --> DEEP[Deep merge keys]
    end

    subgraph execution_results
        ER1[append_lists reducer]
        ER1 --> LIST[Append to list]
    end
```

---

## Domain State Extensions

```mermaid
flowchart TD
    WS[WorkflowState] --> META[metadata]
    META --> AD[active_domain: str]
    META --> CA[completed_agents: list]
    META --> FA[failed_agents: list]
    META --> DR[domain_results: dict]
```

---

## ClimateState and ConversationState

```mermaid
classDiagram
    class ClimateState {
        +str twin_id
        +str scenario_id
        +dict variables
        +dict layers
        +dict metadata
        +datetime timestamp
    }

    class ConversationState {
        +str session_id
        +list~ConversationTurn~ turns
        +str active_agent
        +list reasoning_refs
        +list simulation_refs
    }

    class ConversationTurn {
        +str role
        +str content
        +str agent_id
        +datetime timestamp
        +dict metadata
    }

    ConversationState --> ConversationTurn
```

---

## Related Documents

- [State Management](../architecture/state_management.md)
- [Supervisor Flow](./supervisor_flow.md)
