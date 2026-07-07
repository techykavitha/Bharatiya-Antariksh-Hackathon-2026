# Architecture Diagrams Index

> **Last Updated:** 2026-07-07

---

## Available Diagrams

| Diagram | File | Description |
|---------|------|-------------|
| Memory Architecture | [memory_architecture.md](./memory_architecture.md) | MemoryManager facade, backends, cache, search |
| Supervisor Flow | [supervisor_flow.md](./supervisor_flow.md) | LangGraph pipeline, intent, planning, execution |
| Domain Flow | [domain_flow.md](./domain_flow.md) | Domain hierarchy, agent selection, execution modes |
| State Flow | [state_flow.md](./state_flow.md) | WorkflowState lifecycle, reducers, domain extensions |
| Request Flow | [request_flow.md](./request_flow.md) | End-to-end request sequence, schema transformations |
| Execution Flow | [execution_flow.md](./execution_flow.md) | Full system execution, parallel/sequential, retry, bootstrap |

---

## Diagram Conventions

- **Solid boxes** — Implemented components
- **Dashed / "future" labels** — Not yet implemented
- **Mermaid** — All diagrams use Mermaid syntax for version control and rendering
- **Sequence diagrams** — Show temporal ordering of operations
- **Flowcharts** — Show decision points and branching
- **State diagrams** — Show lifecycle transitions

---

## Adding New Diagrams

When adding a new component:

1. Create `docs/diagrams/<component>_flow.md`
2. Include at least one architecture diagram and one sequence/flow diagram
3. Link from this index
4. Cross-reference from the component documentation
