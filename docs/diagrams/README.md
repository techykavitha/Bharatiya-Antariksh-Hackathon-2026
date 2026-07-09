# Architecture Diagrams Index

> **Last Updated:** 2026-07-09 | **Version:** 0.3.0

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
| Specialized Agent Architecture | [specialized_agent_architecture.md](./specialized_agent_architecture.md) | Framework hierarchy, pipeline, cross-cutting services |
| Flood Agent Workflow | [flood_agent_workflow.md](./flood_agent_workflow.md) | Flood agent sequence, reasoning, decision engine |
| Water Resource Workflow | [water_resource_workflow.md](./water_resource_workflow.md) | Water agent pipeline, inter-agent coordination |
| Heatwave Workflow | [heatwave_workflow.md](./heatwave_workflow.md) | Heatwave agent with unified decision + RL |
| Decision Framework | [decision_framework.md](./decision_framework.md) | DecisionManager lifecycle, validation, priority queue |
| RL Optimization Flow | [rl_optimization_flow.md](./rl_optimization_flow.md) | RLOptimizationService pipeline |
| Explainability Pipeline | [explainability_pipeline.md](./explainability_pipeline.md) | XAI sub-engine data flow |
| Agent → Decision → RL Flow | [agent_decision_rl_flow.md](./agent_decision_rl_flow.md) | Cross-layer decision and RL integration |
| Knowledge Graph Reasoning | [knowledge_graph_reasoning_flow.md](./knowledge_graph_reasoning_flow.md) | CKG query and reasoning APIs |
| Cyclone Workflow | [cyclone_workflow.md](./cyclone_workflow.md) | Cyclone agent 12-tool pipeline |
| Disaster Response Workflow | [disaster_response_workflow.md](./disaster_response_workflow.md) | Multi-hazard coordination |
| Urban Planning Workflow | [urban_planning_workflow.md](./urban_planning_workflow.md) | Long-term adaptation planning |
| Agriculture Workflow | [agriculture_workflow.md](./agriculture_workflow.md) | Agriculture agent + RAG pipeline |
| Air Quality Workflow | [air_quality_workflow.md](./air_quality_workflow.md) | AQI assessment and mitigation |
| Supervisor Agent Hierarchy | [supervisor_agent_hierarchy.md](./supervisor_agent_hierarchy.md) | Three supervisors, 8 agents |
| Agent Interaction Map | [agent_interaction_map.md](./agent_interaction_map.md) | Inter-agent peer communication |

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
