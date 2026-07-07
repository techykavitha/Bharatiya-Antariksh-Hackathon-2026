# Coverage Report

> **Last Updated:** 2026-07-07  
> **Note:** Formal coverage tooling (`pytest-cov`) has not been configured. This report is based on manual analysis of test files vs. source modules.

---

## Coverage by Module

| Module | Source Files | Test Files | Tests | Estimated Coverage |
|--------|-------------|-----------|-------|-----------------|
| `agents/base/` | 1 | 1 | 5 | ~85% |
| `agents/tools/` | 1 | (via base_agent) | — | ~60% |
| `agents/schemas/` | 2 | (via all tests) | — | ~90% |
| `agents/prompts/` | 1 | 1 | 4 | ~80% |
| `agents/state/` | 3 | 1 | 4 | ~70% |
| `agents/memory/` | 14 | 9 | 64 | ~85% |
| `agents/supervisor/` | 12 | 5 | 22 | ~75% |
| `agents/domain/` | 7 | 3 | 18 | ~80% |
| `config/` | 3 | 2 | 7 | ~75% |
| `services/` | 1 | 0 | 0 | 0% |
| `utils/` | 3 | (via all tests) | — | ~60% |

**Overall estimated coverage:** ~75%

---

## Well-Covered Areas

| Area | Coverage | Notes |
|------|----------|-------|
| MemoryManager public API | High | All 10 manager tests |
| Redis operations | High | 8 dedicated tests |
| Vector search | High | 7 dedicated tests |
| Knowledge graph | High | 9 dedicated tests |
| Digital twin versioning | High | 8 dedicated tests |
| Intent classification | High | 4 dedicated tests |
| Domain execution modes | Medium-High | Sequential, parallel, retry |
| Agent registry | High | Both climate and domain registries |

---

## Under-Covered Areas

| Area | Coverage | Gap |
|------|----------|-----|
| `services/bootstrap.py` | None | No bootstrap tests |
| `ParallelExecutor` | Low | Only tested via planner parallel mode |
| `FailureHandler` | Low | No dedicated failure tests |
| `WorkflowRouter` | Low | Tested indirectly via executor |
| `InfrastructureSupervisor` | Low | Only environmental tested in detail |
| `EmergencySupervisor` | Low | Only environmental tested in detail |
| `embedding.py` OpenAI provider | None | Only deterministic tested |
| `AbstractTool` standalone | Low | Tested via BaseAgent only |
| Climate → Domain integration | None | Not wired in tests |

---

## Coverage Goals

| Target | Current | Goal |
|--------|---------|------|
| Overall line coverage | ~75% (estimated) | 85% |
| Public API coverage | ~85% | 95% |
| Error path coverage | ~60% | 80% |
| Integration flows | 5 flows | 10+ flows |

---

## Enabling Formal Coverage

To generate automated coverage reports, add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "--cov=backend --cov-report=term-missing --cov-report=html"
```

Then run:

```powershell
$env:PYTHONPATH="."
python -m pytest backend/tests --cov=backend --cov-report=html
```

Coverage HTML report will be generated in `htmlcov/`.

---

## Related Documents

- [Unit Test Summary](./unit_test_summary.md)
- [Future Tests](./future_tests.md)
