# Testing Documentation

> **Last Updated:** 2026-07-07  
> **Total Tests:** 124 passing  
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
