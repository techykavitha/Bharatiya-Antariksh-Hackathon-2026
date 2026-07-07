# ADR-008: RL Optimization Service

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-07-07 |
| **Deciders** | Nexora Engineering |
| **Related** | [RL Optimization Service](../rl/rl_optimization_service.md), [ADR-007](./ADR-007_decision_framework.md), [ADR-006](./ADR-006_specialized_agent_framework.md) |

---

## Context

Specialized agents (ADR-006) produce ranked climate actions via decision engines (ADR-007). When reflection confidence is low or objectives conflict, agents need optimization beyond rule-based ranking. Early agents (flood, water resource) used per-agent `SpecializedRLEngineInterface.request_rl()` with ad hoc payloads.

Without a unified RL layer, each hazard would reimplement state encoding, constraint filtering, reward composition, policy selection, and metrics. RL output would not feed explainability (ADR-009) or persistence consistently.

---

## Decision

Introduce an **RL Optimization Service** in `backend/rl/` as an agent-agnostic reinforcement learning layer with a single public API:

```
optimize(DecisionRequest) → DecisionResponse
```

### Layered architecture

| Layer | Module | Responsibility |
|-------|--------|----------------|
| Service | `rl_service.py` | Public facade: `optimize`, `rank_actions`, `evaluate`, `simulate_reward`, policy switching |
| Inference | `rl_inference.py` | Pipeline orchestration |
| Encoding | `rl_state_encoder.py` | `DecisionRequest` → `EncodedState` (one-hot types, climate vars, constraints, need-flags) |
| Constraints | `rl_constraints.py` | `RLConstraintEngine` pre-filters infeasible actions |
| Reward | `rl_reward_engine.py` | Eight configurable domain components (flood, water, safety, economic, etc.) |
| Multi-objective | `rl_multi_objective.py` | Weighted objectives + Pareto ranking (`0.6 × reward + 0.4 × objectives`) |
| Policy | `rl_engine.py`, `rl_policy_manager.py` | `RLPolicy` ABC; PPO/SAC/DQN/A2C/MAPPO via factory; JSON artifacts on disk |
| Environment | `rl_environment.py` | Stateless single-step MDP (one request = one episode step, `done=True`) |
| Training | `rl_training_manager.py` | Abstract interface + `InMemoryTrainingManager` for episode recording |
| Registry & metrics | `rl_registry.py`, `rl_metrics.py` | Algorithm registry, policy metadata, per-invocation metrics |

### Optimization pipeline

```
DecisionRequest
  → StateEncoder (observation)
  → RLConstraintEngine (feasible actions)
  → MultiObjectiveOptimizer + RewardEngine (scores)
  → RLEngine / RLPolicy (action selection)
  → DecisionResponse (chosen action, ranking, rejections, reward)
```

### Key defaults

- **Default algorithm:** PPO (`DEFAULT_ALGORITHM = RLAlgorithm.PPO`); others available but staged
- **Constraint-before-policy:** Hard constraints remove infeasible actions; policy selects only from feasible set
- **Inference-first policies:** Softmax/epsilon-greedy over pre-computed multi-objective scores; full neural training deferred
- **Agent decoupling:** `backend/rl/` never imports specialized agent modules

### Architectural boundary

Input and output are exclusively `DecisionRequest` and `DecisionResponse` from ADR-007. Shared `DecisionValidator` runs at RL handoff.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Per-agent RL engines (`SpecializedRLEngineInterface`) | Duplicated encoding, rewards, and metrics; blocks unified XAI |
| Full neural RL training in v1.0 | Premature without production decision volume; inference-first sufficient |
| Multi-step MDP rollouts per request | Climate decisions are single-shot action selection; adds complexity without benefit |
| External RL platform (Ray RLlib, etc.) | Operational overhead; in-process service matches current scale and testability needs |
| RL inside `DecisionManager` | Violates separation—decision owns lifecycle; RL owns optimization |
| Skip constraint pre-filtering | Policy could select infeasible actions; constraints are hard operational limits |

---

## Pros

- Single API for all agents; heatwave is reference integration
- Constraint-before-policy guarantees feasible action sets
- Hybrid reward model balances domain expertise (60%) with agent-declared objectives (40%)
- Policy artifacts as versioned JSON enable hot-swapping without redeploy
- `RLMetricsCollector` on every `optimize()` call; metrics embedded in response metadata
- Algorithm registry supports future PPO → SAC/DQN upgrades without API changes
- Single-step environment simplifies testing and explainability trace mapping

---

## Cons

- Inference-first policies are not trained neural networks; optimization quality depends on reward engineering
- Flood and water resource still use legacy `SpecializedRLEngineInterface`; migration incomplete
- `InMemoryTrainingManager` records episodes only; `schedule_training()` is interface-only
- Single-step MDP cannot model multi-horizon reservoir or crop planning without extension
- Policy artifacts on local disk require deployment strategy for multi-node clusters
- Eight reward components require domain tuning; misconfiguration affects all agents sharing a policy

---

## Trade-offs

| Trade-off | Choice | Rationale |
|-----------|--------|-----------|
| Training vs. inference | Inference-first v1.0 | Ship optimization pipeline; collect episodes for future training |
| Algorithm complexity | PPO default, others staged | One well-tested path; registry allows incremental rollout |
| Single-step vs. multi-step MDP | Single-step | Matches current decision-request granularity |
| In-process vs. external RL | In-process service | Lower latency, simpler tests; revisit at scale |
| Reward generality vs. accuracy | Hybrid 60/40 model | Domain rewards capture hazard physics; agent objectives capture local goals |
| Policy storage | JSON on disk | Human-readable, versionable; not ideal for large neural weights later |

---

## Consequences

- Agents call `RLOptimizationService.optimize()` when `DecisionRequest.need_rl` is set and reflection signals low confidence
- `DecisionRequest.to_rl_payload()` must be used; agent identity must not leak into RL state
- `DecisionResponse` ranking and rejections feed XAI alternative-action analysis (ADR-009)
- Legacy `SpecializedRLEngineInterface` deprecated; flood/water migration planned
- Tests in `backend/tests/rl/` validate pipeline stages independently and end-to-end

---

## Future Impact

- Production episode collection enables real PPO/SAC training via `RLTrainingManager` implementations
- Multi-step environment extension for reservoir and agricultural planning horizons
- Graph reasoning insights (ADR-010) can augment `StateEncoder` features
- Distributed policy store (object storage or model registry) when neural policies ship
- MAPPO path supports multi-agent coordinated optimization across domain supervisors
