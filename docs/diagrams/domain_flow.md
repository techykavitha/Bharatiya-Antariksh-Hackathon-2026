# Domain Flow

> **Last Updated:** 2026-07-07

---

## Domain Hierarchy

```mermaid
graph TD
    CS[Climate Supervisor] --> DR[DomainRegistry]
    DR --> ES[Environmental Supervisor]
    DR --> IS[Infrastructure Supervisor]
    DR --> EMS[Emergency Supervisor]

    ES --> FA[flood_agent - future]
    ES --> HA[heatwave_agent - future]
    ES --> AQ[air_quality_agent - future]

    IS --> AG[agriculture_agent - future]
    IS --> WR[water_resource_agent - future]
    IS --> UP[urban_planning_agent - future]

    EMS --> CA[cyclone_agent - future]
    EMS --> DR2[disaster_response_agent - future]
```

---

## Domain Invocation Pipeline

```mermaid
graph LR
    REQ[AgentRequest] --> SEL[select_agents]
    SEL --> PLAN[build_plan]
    PLAN --> EXEC[DomainExecutor]
    EXEC --> MERGE[merge_results]
    MERGE --> MEM[update_memory]
    MEM --> RESP[AgentResponse]
```

---

## Agent Selection (Keyword Matching)

```mermaid
flowchart TD
    Q[Query Text] --> KW[Extract Keywords]
    KW --> MATCH{Match Agent Slots}
    MATCH -->|flood, inundation| FA[flood_agent]
    MATCH -->|heat, temperature| HA[heatwave_agent]
    MATCH -->|air, pollution, AQI| AQ[air_quality_agent]
    MATCH -->|crop, farm, yield| AG[agriculture_agent]
    MATCH -->|water, reservoir, drought| WR[water_resource_agent]
    MATCH -->|urban, city, planning| UP[urban_planning_agent]
    MATCH -->|cyclone, hurricane, typhoon| CA[cyclone_agent]
    MATCH -->|disaster, evacuation, relief| DR[disaster_response_agent]
    MATCH -->|no match| FALLBACK[Domain Fallback Response]
```

---

## DomainExecutor Modes

```mermaid
flowchart TD
    PLAN[DomainExecutionPlan] --> MODE{Execution Mode}
    MODE -->|SEQUENTIAL| S1[Agent 1] --> S2[Agent 2] --> S3[Agent 3]
    MODE -->|PARALLEL| P1[Agent 1]
    MODE -->|PARALLEL| P2[Agent 2]
    MODE -->|PARALLEL| P3[Agent 3]
    P1 --> JOIN[asyncio.gather]
    P2 --> JOIN
    P3 --> JOIN
    MODE -->|CONDITIONAL| C1[Agent 1] --> CHECK{Result OK?}
    CHECK -->|Yes| C2[Agent 2]
    CHECK -->|No| SKIP[Skip remaining]
```

---

## Domain Registry

```mermaid
sequenceDiagram
    participant Bootstrap
    participant DR as DomainRegistry
    participant ES as EnvironmentalSupervisor
    participant IS as InfrastructureSupervisor
    participant EMS as EmergencySupervisor

    Bootstrap->>DR: register_all_defaults(memory)
    DR->>ES: create + initialize
    DR->>IS: create + initialize
    DR->>EMS: create + initialize
    DR->>DR: store all three

    Note over DR: Climate Supervisor resolves via DomainRegistry
```

---

## State Updates

```mermaid
flowchart LR
    RESULT[DomainExecutionResult] --> MERGE[DomainMergedResult]
    MERGE --> WS[WorkflowState.metadata]
    MERGE --> MM[MemoryManager]
    WS --> |active_domain| META[metadata]
    WS --> |completed_agents| META
    WS --> |failed_agents| META
    WS --> |domain_results| META
```

---

## Related Documents

- [Domain Supervisors](../domain/domain_supervisors.md)
- [ADR-005](../decisions/ADR-005_domain_supervisors.md)
- [Supervisor Flow](./supervisor_flow.md)
