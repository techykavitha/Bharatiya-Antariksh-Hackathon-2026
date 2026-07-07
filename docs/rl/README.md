# Reinforcement Learning Engine

> **Status:** ⬜ Not Started  
> **Version:** —  
> **Last Updated:** 2026-07-07

---

## Purpose

The RL Engine will provide policy optimization for climate decision support, enabling the Climate Supervisor to request optimal action policies for disaster response, resource allocation, and scenario planning.

---

## Current State

Only the `RLEngineInterface` protocol is defined in `backend/agents/supervisor/execution_context.py`. No implementation exists.

### Interface Methods (Defined)

| Method | Description |
|--------|-------------|
| `request_policy(scenario_id, context)` | Request optimal policy |
| `evaluate_actions(scenario_id, actions)` | Evaluate action outcomes |
| `rank_actions(scenario_id, actions)` | Rank actions by expected utility |

### ClimateSupervisor Delegation

`ClimateSupervisor` exposes `request_policy()`, `evaluate_actions()`, and `rank_actions()` methods that delegate to the injected `RLEngineInterface` implementation.

---

## Planned Architecture

```
ClimateSupervisor
    └── RLEngineInterface
            └── StableBaselines3Engine (planned)
                    ├── PolicyStore (MemoryManager)
                    ├── ScenarioEvaluator
                    └── ActionRanker
```

---

## Dependencies

| Dependency | Status |
|------------|--------|
| Simulation Engine | ⬜ Not started |
| Digital Twin Interface | ⬜ Interface only |
| Stable Baselines3 | ⬜ Not in requirements.txt |
| Policy schema design | ⬜ Not started |

---

## Related Documents

- [Climate Supervisor](../supervisor/climate_supervisor.md)
- [ADR-002](../decisions/ADR-002_hierarchical_supervisors.md)
- [Progress Tracker](../engineering/progress_tracker.md)
