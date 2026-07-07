# Reinforcement Learning Engine

> **Status:** ✅ RL Optimization Service Complete (v0.2.0)  
> **Version:** 0.2.0  
> **Last Updated:** 2026-07-07

---

## Purpose

The RL layer provides policy optimization for climate decision support. As of v0.2.0, the `RLOptimizationService` is fully implemented and agent-agnostic.

---

## Current State (v0.2.0)

| Component | Status | Location |
|-----------|--------|----------|
| `RLOptimizationService` | ✅ Complete | `backend/rl/rl_service.py` |
| `RLEngine` | ✅ Complete | `backend/rl/rl_engine.py` |
| `RLInference` | ✅ Complete | `backend/rl/rl_inference.py` |
| `PolicyManager` | ✅ Complete | `backend/rl/rl_policy_manager.py` |
| `RLEngineInterface` (supervisor) | ✅ Interface | `execution_context.py` |
| Stable Baselines3 | ⬜ Planned | — |

**Primary API:** `RLOptimizationService.optimize(DecisionRequest) → DecisionResponse`

**Tests:** 26 (11 unit + 15 integration)

See [RL Optimization Service](./rl_optimization_service.md) for full documentation.

---

## Legacy Interface (Supervisor Layer)

`ClimateSupervisor` still exposes `request_policy()`, `evaluate_actions()`, and `rank_actions()` via `RLEngineInterface` protocol. Specialized agents use either:

- `SpecializedRLEngineInterface.request_rl()` — Flood, Water
- `RLOptimizationService.optimize()` — Heatwave

---

## Planned Architecture (Remaining)

```
RLOptimizationService
    └── StableBaselines3Engine (planned)
            ├── PolicyStore (S3 / MemoryManager)
            ├── TrainedModelArtifacts
            └── OnlineLearningPipeline
```

---

## Dependencies

| Dependency | Status |
|------------|--------|
| Decision Framework | ✅ Complete |
| Simulation Engine | ⬜ Not started |
| Stable Baselines3 | ⬜ Not in requirements.txt |

---

## Related Documents

- [RL Optimization Service](./rl_optimization_service.md)
- [Decision Framework](../decision/decision_framework.md)
- [ADR-008](../decisions/ADR-008_rl_optimization_service.md)
- [RL Optimization Flow](../diagrams/rl_optimization_flow.md)
- [Progress Tracker](../engineering/progress_tracker.md)

---

## Historical Note (v0.1.0)

Prior to v0.2.0, only the `RLEngineInterface` protocol was defined with no implementation. That content is superseded by the sections above.
