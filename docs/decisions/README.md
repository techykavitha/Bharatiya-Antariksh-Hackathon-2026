# Architecture Decision Records (ADR)

> **Last Updated:** 2026-07-07

---

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-001](./ADR-001_langgraph_over_langchain.md) | LangGraph for Workflow Orchestration | Accepted | 2026-07-07 |
| [ADR-002](./ADR-002_hierarchical_supervisors.md) | Hierarchical Multi-Agent Supervision | Accepted | 2026-07-07 |
| [ADR-003](./ADR-003_memory_manager_abstraction.md) | MemoryManager Abstraction Layer | Accepted | 2026-07-07 |
| [ADR-004](./ADR-004_redis_plus_qdrant.md) | Redis + Qdrant Dual-Store Memory | Accepted | 2026-07-07 |
| [ADR-005](./ADR-005_domain_supervisors.md) | Domain Supervisor Middle Tier | Accepted | 2026-07-07 |

---

## ADR Template

When creating a new ADR, copy this structure:

```markdown
# ADR-NNN: Title

| Field | Value |
|-------|-------|
| **Status** | Proposed / Accepted / Deprecated / Superseded |
| **Date** | YYYY-MM-DD |
| **Deciders** | Team / individuals |
| **Related** | Links to component docs |

## Context
## Decision
## Alternatives Considered
## Pros
## Cons
## Consequences
## Future Impact
```

---

## When to Create an ADR

- Choosing between architectural alternatives
- Changing a public API contract
- Adding a new external dependency
- Modifying the supervisor hierarchy
- Changing memory backend technology
