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

---

## Version 0.2.0 Coverage Additions

> **Supplemental section.** All v0.1.0 content above is preserved.

| Module | Source Files | Test Files | Tests | Estimated Coverage |
|--------|-------------|-----------|-------|-----------------|
| `agents/specialized/` (framework) | 11 | 1 | 10 | ~85% |
| `agents/specialized/flood/` | 11 | 2 | 23 | ~90% |
| `agents/specialized/water_resource/` | 11 | 2 | 24 | ~90% |
| `agents/specialized/heatwave/` | 11 | 2 | 25 | ~90% |
| `decision/` | 10 | 3 | 38 | ~90% |
| `rl/` | 14 | 2 | 26 | ~85% |
| `xai/` | 9 | 2 | 13 | ~85% |
| `knowledge_graph/` | 10 | 2 | 24 | ~90% |

**v0.2.0 overall estimated coverage:** ~82% (up from ~75%)

### Well-Covered (v0.2.0)

| Area | Tests | Notes |
|------|-------|-------|
| BaseSpecializedAgent pipeline | 10 | Framework unit tests |
| Flood decision engine | 23 | Unit + Delhi integration |
| Water inter-agent delegation | 24 | Reciprocal flags regression |
| Heatwave unified decision + RL | 25 | Mock RL workaround |
| DecisionRequest/Response | 38 | Full validator coverage |
| RL optimize() pipeline | 26 | Without climate_state |
| ExplanationEngine | 13 | All sub-engines |
| GraphEngine query/reasoning | 24 | India seed graph |

### Under-Covered (v0.2.0)

| Area | Gap |
|------|-----|
| RL with climate_state attached | BUG-010 blocks real path |
| CKG → agent integration | Not wired |
| XAI auto-pipeline in agents | Manual invocation only |
| Climate → Domain → Agent E2E | No test fixture |
| `services/bootstrap.py` | Still 0% |
