# RL Optimization Flow

> **Version:** 0.2.0  
> **Last Updated:** 2026-07-07  
> **Source:** `backend/rl/`

---

## End-to-End Optimization Pipeline

```mermaid
flowchart TB
    subgraph Input["Input Layer"]
        DR[DecisionRequest]
        MM[MemoryManager]
    end

    subgraph Service["RLOptimizationService"]
        VAL[DecisionValidator]
        MEM[_retrieve_memory_context]
        MET[RLMetricsCollector]
        TRN[InMemoryTrainingManager]
    end

    subgraph Inference["RLInference"]
        ENV[RLEnvironment.reset]
        SE[StateEncoder]
        OBS[ObservationSpace]
        AS[ActionSpace]
        RC[RLConstraintEngine.filter_feasible]
        MO[MultiObjectiveOptimizer]
        ENG[RLEngine.run_policy]
        RE[RewardEngine]
    end

    subgraph Policy["Policy Layer"]
        PM[PolicyManager]
        REG[RLRegistry]
        PPO[PPOPolicy]
        SAC[SACPolicy]
        DQN[DQNPolicy]
        A2C[A2CPolicy]
        MAPPO[MAPPOPolicy]
    end

    subgraph Output["Output Layer"]
        DResp[DecisionResponse]
        EP[TrainingEpisode]
    end

    DR --> VAL
    DR --> MEM
    MM --> MEM
    MEM --> ENV
    DR --> ENV
    ENV --> SE
    SE --> OBS
    ENV --> AS
    SE --> RC
    RC --> MO
    MO --> RE
    MO --> ENG
    PM --> ENG
    REG --> PM
    ENG --> PPO
    ENG --> SAC
    ENG --> DQN
    ENG --> A2C
    ENG --> MAPPO
    ENG --> DResp
    MET --> DResp
    DResp --> TRN
    TRN --> EP
    EP --> MM
```

---

## Sequence: optimize(DecisionRequest)

```mermaid
sequenceDiagram
    participant Agent as Specialized Agent
    participant Svc as RLOptimizationService
    participant Val as DecisionValidator
    participant Mem as MemoryManager
    participant Inf as RLInference
    participant Env as RLEnvironment
    participant Enc as StateEncoder
    participant Con as RLConstraintEngine
    participant MO as MultiObjectiveOptimizer
    participant Eng as RLEngine
    participant Pol as RLPolicy

    Agent->>Svc: optimize(DecisionRequest)
    Svc->>Val: validate_request (optional)
    Svc->>Mem: search rl_episode history
    Mem-->>Svc: historical_rewards
    Svc->>Inf: optimize(request, memory_context)
    Inf->>Env: reset(request, memory_context)
    Env->>Enc: encode(request)
    Enc-->>Env: EncodedState (48-dim vector)
    Env-->>Inf: state + ActionSpace
    Inf->>Con: filter_feasible(request)
    Con-->>Inf: feasible actions + violations
    alt No feasible actions
        Inf-->>Svc: DecisionResponse FAILED
    else Feasible actions exist
        Inf->>MO: evaluate_all(feasible, state)
        MO-->>Inf: MultiObjectiveResult scores
        Inf->>Eng: run_policy(state, scores, algorithm)
        Eng->>Pol: select(state, action_space, scores)
        Pol-->>Eng: PolicyOutput
        Eng-->>Inf: selected_index, confidence
        Inf->>MO: evaluate_action(chosen)
        Inf-->>Svc: DecisionResponse COMPLETED
    end
    Svc->>Svc: finalize metrics
    Svc->>Svc: record_episode (if successful)
    Svc-->>Agent: DecisionResponse
```

---

## State Encoding Detail

```mermaid
flowchart LR
    DR[DecisionRequest] -->|to_rl_payload| P[Stripped Payload]
    P --> SE[StateEncoder]

    subgraph Features["Encoded Features → 48-dim Vector"]
        DT[decision_type one-hot ×9]
        PR[priority scalar]
        CF[confidence scalar]
        RS[risk_score scalar]
        RL[risk_level one-hot ×6]
        OW[objective_weights ×8]
        CB[constraint_budget]
        CS[constraint_safety]
        CV[climate_variables ×12]
        FP[forecast_present]
        SP[simulation_present]
        AC[action_count]
        NF[need_flags ×4]
        HR[historical_reward]
    end

    SE --> Features
    Features --> ES[EncodedState]
```

---

## Constraint & Reward Gates

```mermaid
flowchart TD
    ACTIONS[All possible_actions] --> BUDGET{Budget OK?}
    BUDGET -->|No| REJ1[Rejected: budget]
    BUDGET -->|Yes| SAFETY{Safety OK?}
    SAFETY -->|No| REJ2[Rejected: safety / no-go]
    SAFETY -->|Yes| POP{Population OK?}
    POP -->|No| REJ3[Rejected: population]
    POP -->|Yes| ENV{Environment OK?}
    ENV -->|No| REJ4[Rejected: protected area]
    ENV -->|Yes| FEAS[Feasible Action Set]

    FEAS --> REW[RewardEngine.compute]
    REW --> OBJ[Objective scoring]
    OBJ --> COMB[0.6×reward + 0.4×objectives]
    COMB --> POL[Policy selection]
    POL --> CHOSEN[chosen_action]
```

---

## Policy Algorithm Selection

```mermaid
flowchart TB
    REQ[algorithm param or DEFAULT=PPO] --> PM[PolicyManager.get_active_artifact]
    PM --> FACTORY[create_policy]
    FACTORY --> PPO[PPOPolicy — softmax + entropy]
    FACTORY --> SAC[SACPolicy — temperature scaling]
    FACTORY --> DQN[DQNPolicy — epsilon-greedy]
    FACTORY --> A2C[A2CPolicy — advantage baseline]
    FACTORY --> MAPPO[MAPPOPolicy — cooperation factor]
    PPO --> OUT[PolicyOutput]
    SAC --> OUT
    DQN --> OUT
    A2C --> OUT
    MAPPO --> OUT
```

---

## Agent-Agnostic Contract

```mermaid
flowchart LR
    subgraph Agents["Any Specialized Agent"]
        HA[HeatwaveAgent]
        FA[FloodAgent]
        WA[WaterResourceAgent]
    end

    subgraph Contract["Unified Contract"]
        DR[DecisionRequest]
        DResp[DecisionResponse]
    end

    subgraph Forbidden["Never Imported"]
        X1[flood_agent]
        X2[water_resource_agent]
        X3[heatwave_agent]
    end

    HA --> DR
    FA --> DR
    WA --> DR
    DR --> RL[RLOptimizationService]
    RL --> DResp
    RL -.->|no imports| Forbidden
```

---

## Related Documents

- [RL Optimization Service](../rl/rl_optimization_service.md)
- [Decision Framework](../decision/decision_framework.md)
- [Agent → Decision → RL Flow](./agent_decision_rl_flow.md)
