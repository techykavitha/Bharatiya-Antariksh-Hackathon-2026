# Climate Knowledge Graph — Reasoning Flow

> **Diagram:** CKG query and reasoning pipelines  
> **Component:** `backend.knowledge_graph`  
> **Last Updated:** 2026-07-07

---

## Overview

This document visualizes how `GraphEngine` routes requests through `GraphQueryEngine` and `GraphReasoningEngine`, and how the India seed graph (`ClimateGraphBuilder.build_india_climate_graph()`) connects climate events to infrastructure, agents, and historical analogs.

**Distinction:** `GraphEngine` (`backend/knowledge_graph/`) is separate from `NetworkXKnowledgeGraph` (`backend/agents/memory/knowledge_graph.py`).

---

## System Architecture

```mermaid
flowchart TB
    subgraph Client["Consumers"]
        AGT[Specialized Agents]
        SUP[Environmental Supervisor]
        SVC[Future CKG Service]
    end

    subgraph GraphEngine["GraphEngine"]
        CRUD[Entity / Relationship CRUD]
        VAL[GraphValidator]
        SER[GraphSerializer]
        MET[GraphMetricsCollector]
    end

    subgraph QueryLayer["GraphQueryEngine"]
        N[neighbors]
        SP[shortest_path]
        IC[impact_chain]
        AA[affected_agents]
        RE[related_events]
        HS[historical_similarity]
    end

    subgraph ReasonLayer["GraphReasoningEngine"]
        SI[infer_secondary_impacts]
        CF[infer_cascading_failures]
        CD[infer_compound_disasters]
        MA[infer_multi_agent_dependencies]
        R[reason — full pipeline]
    end

    subgraph Data["In-Process Graph"]
        NX[(nx.DiGraph)]
        ENT[(ClimateEntity dict)]
        REL[(GraphRelationship dict)]
    end

    AGT --> GraphEngine
    SUP --> GraphEngine
    SVC --> GraphEngine

    GraphEngine --> QueryLayer
    GraphEngine --> ReasonLayer
    GraphEngine --> NX
    GraphEngine --> ENT
    GraphEngine --> REL

    QueryLayer --> NX
    ReasonLayer --> QueryLayer
    R --> SI & CF & CD & MA
```

---

## Query API Flow

Six core query APIs exposed via `engine.query`:

```mermaid
flowchart LR
    EID[entity_id] --> Q{GraphQueryEngine}

    Q --> N[neighbors]
    Q --> SP[shortest_path]
    Q --> IC[impact_chain]
    Q --> AA[affected_agents]
    Q --> RE[related_events]
    Q --> HS[historical_similarity]

    N --> NR[NeighborResult list]
    SP --> PR[PathResult]
    IC --> ICR[ImpactChainResult]
    AA --> ADR[AgentDependencyResult]
    RE --> RER[RelatedEventResult]
    HS --> HSR[HistoricalSimilarityResult]

    style N fill:#e3f2fd
    style SP fill:#e3f2fd
    style IC fill:#e3f2fd
    style AA fill:#e3f2fd
    style RE fill:#e3f2fd
    style HS fill:#e3f2fd
```

### `impact_chain` BFS Traversal

```mermaid
flowchart TD
    START[Source Entity] --> Q0[Queue: entity_id depth=0]
    Q0 --> VISIT{Visited?}
    VISIT -->|No| ADD[Add to chain if not source]
    VISIT -->|Yes| SKIP[Skip]
    ADD --> NB[neighbors direction=out]
    NB --> FILTER{relationship in filter?}
    FILTER -->|CAUSES AFFECTS BLOCKS FEEDS| ENQ[Enqueue target depth+1]
    FILTER -->|Other| SKIP
    ENQ --> DEPTH{depth < max_depth?}
    DEPTH -->|Yes| Q0
    DEPTH -->|No| DONE[ImpactChainResult]

    style FILTER fill:#fff3e0
```

Default relationship filter: `IMPACT_RELATIONSHIPS` = `{CAUSES, AFFECTS, BLOCKS, FEEDS}`.

---

## Full Reasoning Pipeline

`GraphReasoningEngine.reason(entity_id)` orchestrates four inference stages:

```mermaid
flowchart TB
    INPUT[entity_id] --> REASON[GraphReasoningEngine.reason]

    REASON --> S1[infer_secondary_impacts]
    REASON --> S2[infer_cascading_failures]
    REASON --> S3[infer_compound_disasters]
    REASON --> S4[infer_multi_agent_dependencies]

    S1 --> Q1[impact_chain max_depth=2]
    Q1 --> F1{AFFECTS / CAUSES}
    F1 --> I1[ReasoningInsight: infrastructure / population / secondary]

    S2 --> Q2[impact_chain max_depth=3 CASCADE_RELATIONSHIPS]
    S2 --> Q3[neighbors BLOCKS out]
    S2 --> Q4[neighbors DEPENDS_ON in]
    Q2 --> I2[ReasoningInsight: cascading_failure]
    Q3 --> I3[ReasoningInsight: service_disruption]
    Q4 --> I4[ReasoningInsight: dependency_failure]

    S3 --> SCAN[Scan COMPOUND_EVENT_TYPES in same region_id]
    SCAN --> I5[ReasoningInsight: compound_disaster]
    SCAN --> HD{Heatwave + Drought?}
    HD -->|Yes| I6[Heat-drought compound 0.85]
    SCAN --> HF{Heatwave + Flood?}
    HF -->|Yes| I7[Heat-flood compound 0.60]

    S4 --> Q5[affected_agents]
    Q5 --> I8[ReasoningInsight: agent_dependency]
    Q5 --> MAC{≥ 2 agents?}
    MAC -->|Yes| I9[ReasoningInsight: multi_agent_coordination]

    I1 & I2 & I3 & I4 & I5 & I6 & I7 & I8 & I9 --> RESULT[GraphReasoningResult]
    RESULT --> SUM[summary string]
```

---

## Reasoning Sequence Diagram

```mermaid
sequenceDiagram
    participant Client
    participant GR as GraphReasoningEngine
    participant GQ as GraphQueryEngine
    participant GE as GraphEngine

    Client->>GR: reason("flood_chennai_2015")
    GR->>GE: _ensure_entity("flood_chennai_2015")

    Note over GR,GQ: Stage 1 — Secondary Impacts
    GR->>GQ: impact_chain(id, max_depth=2, {AFFECTS, CAUSES})
    GQ->>GE: neighbors (BFS)
    GQ-->>GR: ImpactChainResult
    GR->>GR: Classify infrastructure / population impacts

    Note over GR,GQ: Stage 2 — Cascading Failures
    GR->>GQ: impact_chain(id, max_depth=3, CASCADE_RELATIONSHIPS)
    GQ-->>GR: ImpactChainResult
    GR->>GQ: neighbors(id, BLOCKS, out)
    GQ-->>GR: NeighborResult list
    GR->>GQ: neighbors(id, DEPENDS_ON, in)
    GQ-->>GR: NeighborResult list

    Note over GR,GE: Stage 3 — Compound Disasters
    GR->>GE: Scan entities by region_id
    GR->>GR: Match COMPOUND_EVENT_TYPES co-occurrence

    Note over GR,GQ: Stage 4 — Agent Dependencies
    GR->>GQ: affected_agents(id)
    GQ->>GQ: neighbors + shortest_path (≤ 3 hops)
    GQ-->>GR: AgentDependencyResult

    GR->>GE: record_reasoning()
    GR-->>Client: GraphReasoningResult
```

---

## `affected_agents` Resolution

```mermaid
flowchart TD
    EID[entity_id] --> IN[Inbound neighbors]
    EID --> OUT[Outbound neighbors]

    IN --> F1{entity_type == specialized_agent?}
    F1 -->|Yes| CHK1{rel in SUPPORTS MITIGATES DEPENDS_ON?}
    CHK1 -->|Yes| ADD[Add agent]

    OUT --> F2{entity_type == specialized_agent?}
    F2 -->|Yes| ADD

    ADD --> PATH[For each agent entity not yet found]
    PATH --> SP[shortest_path agent → entity_id]
    SP --> HOPS{hops ≤ 3?}
    HOPS -->|Yes| ADD
    HOPS -->|No| SKIP[Skip]

    ADD --> DEDUP[Deduplicate by entity_id]
    DEDUP --> RESULT[AgentDependencyResult]
```

---

## `related_events` and `historical_similarity`

```mermaid
flowchart TB
    EID[entity_id] --> RE[related_events]

    RE --> H1[HISTORICALLY_RELATED neighbors out/in]
    RE --> C1[CAUSES neighbors out]
    RE --> C2[AFFECTS neighbors out]
    C1 --> EVT{target in EVENT_ENTITY_TYPES?}
    C2 --> EVT
    EVT -->|Yes| ADD[Add event with confidence]

    H1 --> FALLBACK{events < limit?}
    C1 --> FALLBACK
    ADD --> FALLBACK

    FALLBACK -->|Yes| SIM[_event_similarity scan]
    SIM --> SCORE{score ≥ 0.5?}
    SCORE -->|Yes| ADD2[Add candidate event]

    ADD2 --> RER[RelatedEventResult]

    EID --> HS[historical_similarity]
    HS --> SAME[Same entity_type + EVENT_ENTITY_TYPES]
    SAME --> RANK[Rank by _event_similarity]
    RANK --> HSRE[HistoricalSimilarityResult]
    HS --> MERGE[Merge related_events scores]
```

### Event Similarity Scoring

```mermaid
flowchart LR
    SRC[Source Entity] --> T[+0.30 same type]
    SRC --> R[+0.25 same region_id]
    SRC --> N[+0.15 × numeric ratio]
    SRC --> Y[+0.15 − 0.02 × year gap]
    T & R & N & Y --> CAP[min score 1.0]
```

**Note:** `RAINFALL` is not in `EVENT_ENTITY_TYPES`. Rainfall entities resolve related events via `CAUSES` edges to `FLOOD` nodes and the similarity fallback loop.

---

## India Seed Graph — Example Paths

```mermaid
flowchart TB
    subgraph Events["Weather Events"]
        RAIN[rainfall_chennai_2024]
        FLOOD[flood_chennai_2015]
        HEAT[heatwave_delhi_2024]
        UHI[heatwave_ahmedabad_2023]
    end

    subgraph Geography["Geography"]
        CHN[district_chennai]
        TN[state_tamil_nadu]
        DL[district_delhi_central]
        DEL[state_delhi]
    end

    subgraph Infrastructure["Infrastructure"]
        HOSP[hospital_chennai_cluster]
        PWR[power_grid_chennai]
        POP[population_chennai]
        DPWR[power_grid_delhi]
        DPOP[population_delhi]
    end

    subgraph Hydrology["Hydrology"]
        COOUM[river_cooum]
        CHEMB[reservoir_chembarambakkam]
    end

    subgraph Agents["Specialized Agents"]
        FA[agent_flood]
        HA[agent_heatwave]
        WA[agent_water_resource]
    end

    RAIN -->|CAUSES| FLOOD
    RAIN -->|HISTORICALLY_RELATED| FLOOD
    COOUM -->|CAUSES| FLOOD
    FLOOD -->|AFFECTS| POP
    FLOOD -->|AFFECTS| HOSP
    FLOOD -->|BLOCKS| HOSP
    HOSP -->|DEPENDS_ON| PWR
    POP -->|DEPENDS_ON| HOSP

    HEAT -->|AFFECTS| DPOP
    HEAT -->|AFFECTS| DPWR
    HEAT -->|HISTORICALLY_RELATED| UHI

    CHN -->|LOCATED_IN| TN
    COOUM -->|LOCATED_IN| CHN

    FA -->|SUPPORTS| FLOOD
    FA -->|SUPPORTS| RAIN
    HA -->|SUPPORTS| HEAT
    HA -->|MITIGATES| DPOP
    WA -->|SUPPORTS| CHEMB

    FA -.->|CONNECTED_TO| WA
    HA -.->|CONNECTED_TO| WA
```

---

## GraphEngine vs NetworkXKnowledgeGraph

```mermaid
flowchart LR
    subgraph CKG["GraphEngine (Domain)"]
        GE[backend/knowledge_graph/]
        TE[Typed ClimateEntity]
        TR[RelationshipType + Schema]
        GR[GraphReasoningEngine]
    end

    subgraph MEM["NetworkXKnowledgeGraph (Memory)"]
        NX[backend/agents/memory/]
        GN[Generic node dicts]
        GR2[GraphEdgeType strings]
        TR2[traverse only]
    end

    subgraph MM["MemoryManager"]
        MGR[MemoryManager]
    end

    GE -.->|future bridge| MGR
    NX --> MGR

    style CKG fill:#e8f4fd,stroke:#1976D2
    style MEM fill:#f5f5f5,stroke:#9e9e9e
```

---

## Validation Gate on Mutations

```mermaid
flowchart TD
    MUTATE[add_entity / add_relationship] --> VAL[GraphValidator]
    VAL --> SELF{source_id == target_id?}
    SELF -->|Yes| ERR[ERROR: Self-referential not allowed]
    SELF -->|No| SCHEMA{Valid type triple?}
    SCHEMA -->|Unusual| WARN[WARNING logged]
    SCHEMA -->|Valid| OK[Proceed with lock + graph insert]
    ERR --> REJECT[GraphEngineError]
```

---

## Related Documents

- [Climate Knowledge Graph Documentation](../knowledge_graph/climate_knowledge_graph.md)
- [Memory Architecture](./memory_architecture.md)
- [Agent → Decision → RL Flow](./agent_decision_rl_flow.md)
