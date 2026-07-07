# ADR-001: LangGraph for Workflow Orchestration

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-07-07 |
| **Deciders** | Nexora Engineering |
| **Related** | [Climate Supervisor](../supervisor/climate_supervisor.md) |

---

## Context

Hyperion Climate Twin requires a multi-step AI workflow where user requests pass through intent classification, planning, multi-agent execution, result merging, memory persistence, and response generation. Steps have conditional branching (sequential vs. parallel), state must persist across steps, and the system must be auditable.

Plain LangChain chains are linear and lack native state management. Custom asyncio orchestration would require rebuilding checkpointing, branching, and observability.

---

## Decision

Use **LangGraph `StateGraph`** with the existing `WorkflowState` TypedDict as the shared state schema. The Climate Supervisor compiles a graph with nodes: `classify_intent → plan → execute → merge_results → store_memory → return_response`.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Plain LangChain LCEL chains | No native state reducers, poor branching, no checkpointing |
| Custom asyncio pipeline | High maintenance, reinventing LangGraph features |
| Temporal / Airflow | Overkill for in-process agent orchestration; adds infrastructure dependency |
| AutoGen / CrewAI | Less control over state schema; opinionated agent models |

---

## Pros

- Native `TypedDict` state with reducers (`add_messages`, `merge_dicts`, `append_lists`)
- Built-in checkpointing and replay (future)
- Conditional edges for parallel vs. sequential routing
- `as_graph_node()` pattern allows embedding domain supervisors as subgraph nodes
- Strong ecosystem alignment with LangChain tool and message types
- Industry adoption in production agent systems

---

## Cons

- Learning curve for graph node/reducer patterns
- Debugging graph execution is less linear than imperative code
- LangGraph API still evolving across versions
- Tight coupling to LangChain message types for conversation channel

---

## Consequences

- All orchestration logic must be expressible as graph nodes returning partial state updates
- `WorkflowState` is the contract between all graph nodes — changes require ADR
- Domain supervisors expose `as_graph_node()` for future subgraph composition
- Testing requires invoking individual node functions or full `compiled.ainvoke()`

---

## Future Impact

- Enables supervisor subgraph nesting (Climate → Domain → Specialized)
- Supports human-in-the-loop interrupts via LangGraph checkpoints
- Allows visual graph debugging as LangGraph tooling matures
- May require migration if LangGraph makes breaking API changes
