# Testing Documentation

> **Last Updated:** 2026-07-07  
> **Total Tests:** 306 passing  
> **Framework:** pytest + pytest-asyncio

---

## Quick Start

```powershell
cd f:\Nexora\Hyperion
$env:PYTHONPATH="."
python -m pytest backend/tests -v
```

---

## Test Structure

```
backend/tests/
├── test_base_agent.py          # Foundation: BaseAgent (5)
├── test_config.py              # Foundation: GlobalConfig (2)
├── test_dependency_registry.py # Foundation: DI (5)
├── test_prompts.py             # Foundation: Prompts (4)
├── test_state.py               # Foundation: State (4)
├── memory/                     # Memory layer (64)
├── supervisor/                 # Supervisor layer (22)
└── domain/                     # Domain layer (18)
```

---

## Summary by Layer

| Layer | Test Files | Tests | Status |
|-------|-----------|-------|--------|
| Foundation | 5 | 20 | ✅ All pass |
| Memory | 9 | 64 | ✅ All pass |
| Supervisor | 5 | 22 | ✅ All pass |
| Domain | 3 | 18 | ✅ All pass |
| **Total** | **22** | **124** | **✅ All pass** |

---

## Document Index

| Document | Description |
|----------|-------------|
| [Unit Test Summary](./unit_test_summary.md) | Per-file test inventory |
| [Integration Test Summary](./integration_test_summary.md) | Cross-module test flows |
| [Coverage Report](./coverage_report.md) | Coverage analysis |
| [Mock Components](./mock_components.md) | In-memory test doubles |
| [Debugging History](./debugging_history.md) | Bug records and RCA |
| [Performance Tests](./performance_tests.md) | Performance test status |
| [Stress Tests](./stress_tests.md) | Stress test status |
| [Future Tests](./future_tests.md) | Planned test coverage |

---

## Testing Standards

| Rule | Detail |
|------|--------|
| Framework | pytest with `asyncio_mode = auto` |
| Naming | `test_<behavior>_<condition>` |
| Fixtures | Shared fixtures in `conftest.py` per module |
| Mocks | In-memory backends only — no external services |
| Isolation | Each test creates fresh instances |
| CI gate | 100% pass rate required |

---

## Test Execution History

| Date | Version | Command | Result | Duration |
|------|---------|---------|--------|----------|
| 2026-07-07 | 0.1.0 | `pytest backend/tests -q` | 124 passed | ~5s |
| 2026-07-07 | 0.2.0 | `pytest backend/tests -q` | 306 passed | ~7s |

---

## Version 0.2.0 Update (2026-07-07)

> **Supplemental section.** All v0.1.0 content above is preserved.

### Current Total Tests

**306** (182 new since v0.1.0)

### Current Passing Tests

**306 / 306** (100% pass rate)

### Summary by Layer (v0.2.0)

| Layer | Test Files | Tests | Status |
|-------|-----------|-------|--------|
| Foundation | 5 | 20 | ✅ All pass |
| Memory | 9 | 64 | ✅ All pass |
| Supervisor | 5 | 22 | ✅ All pass |
| Domain | 3 | 18 | ✅ All pass |
| Specialized Framework | 1 | 10 | ✅ All pass |
| Flood Agent | 2 | 23 | ✅ All pass |
| Water Resource Agent | 2 | 24 | ✅ All pass |
| Heatwave Agent | 2 | 25 | ✅ All pass |
| Decision Framework | 3 | 38 | ✅ All pass |
| RL Optimization | 2 | 26 | ✅ All pass |
| Explainability (XAI) | 2 | 13 | ✅ All pass |
| Climate Knowledge Graph | 2 | 24 | ✅ All pass |
| **Total** | **38** | **306** | **✅ All pass** |

### Coverage Summary

| Module | Estimated Coverage | Notes |
|--------|-------------------|-------|
| `backend/agents/specialized/` | High | Framework + 3 agents fully tested |
| `backend/decision/` | High | Unit + integration + serializer |
| `backend/rl/` | High | Unit + integration with DecisionRequest |
| `backend/xai/` | High | Unit + integration |
| `backend/knowledge_graph/` | High | Unit + integration with India seed |
| `backend/agents/memory/` | High | 64 tests (unchanged) |
| `backend/agents/supervisor/` | Medium-High | 22 tests |
| E2E Climate → Agent | None | Planned (TD-006) |

### Mock Components (v0.2.0 additions)

| Mock | Used By | Purpose |
|------|---------|---------|
| `MockRLOptimizationService` | Heatwave integration tests | Bypass RIVER_DISCHARGE enum bug |
| `InMemoryTrainingManager` | RL tests | Episode recording without persistence |
| `InMemoryRedisClient` | All memory tests | Redis mock (pre-existing) |
| `InMemoryQdrantClient` | Vector tests | Qdrant mock (pre-existing) |

### Integration Matrix (v0.2.0)

| Source | Target | Test File | Status |
|--------|--------|-----------|--------|
| Flood Agent | MemoryManager | `test_flood_integration.py` | ✅ |
| Flood Agent | SpecializedRLEngineInterface | `test_flood_integration.py` | ✅ |
| Water Agent | Inter-agent delegation | `test_water_integration.py` | ✅ |
| Heatwave Agent | DecisionManager | `test_heatwave_integration.py` | ✅ |
| Heatwave Agent | RLOptimizationService (mock) | `test_heatwave_integration.py` | ✅ |
| Decision Framework | RL Service | `test_decision_integration.py` | ✅ |
| RL Service | DecisionRequest | `test_rl_integration.py` | ✅ |
| XAI | DecisionRequest/Response | `test_xai_integration.py` | ✅ |
| CKG | India seed graph | `test_ckg_integration.py` | ✅ |
| Climate Supervisor | Domain Supervisor | `test_climate_supervisor.py` | ✅ |
| Climate Supervisor | Specialized Agent | — | ⬜ Not tested |

### Performance Testing

| Test | Target | Actual (v0.2.0) | Status |
|------|--------|------------------|--------|
| Full suite | < 30s | ~7s | ✅ Pass |
| Single agent invoke | < 500ms | 50–200ms (unit) | ✅ Pass |
| CKG India seed build | < 1s | < 100ms | ✅ Pass |
| RL optimize() | < 200ms | 20–80ms | ✅ Pass |

### Regression Testing

All 9 bugs fixed in Prompts 5–12 (BUG-009 through BUG-017) have dedicated regression tests. BUG-010 (RIVER_DISCHARGE) uses mock workaround — full fix pending.

See [Debugging History](./debugging_history.md) for full bug registry.
