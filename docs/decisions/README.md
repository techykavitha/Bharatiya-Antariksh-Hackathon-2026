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
| [ADR-006](./ADR-006_specialized_agent_framework.md) | Specialized Agent Framework | Accepted | 2026-07-07 |
| [ADR-007](./ADR-007_decision_framework.md) | Unified Decision Framework | Accepted | 2026-07-07 |
| [ADR-008](./ADR-008_rl_optimization_service.md) | RL Optimization Service | Accepted | 2026-07-07 |
| [ADR-009](./ADR-009_explainability_framework.md) | Explainability Framework | Accepted | 2026-07-07 |
| [ADR-010](./ADR-010_climate_knowledge_graph.md) | Climate Knowledge Graph | Accepted | 2026-07-07 |

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
- Introducing cross-cutting frameworks (decision, RL, XAI, knowledge graph)
