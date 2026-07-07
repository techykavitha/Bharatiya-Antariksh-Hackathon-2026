# Future Tests

> **Last Updated:** 2026-07-07

---

## High Priority

| ID | Test | Depends On | Description |
|----|------|-----------|-------------|
| FT-01 | Climate-Domain integration | Domain registration in climate fixture | Verify climate supervisor invokes domain supervisors |
| FT-02 | Flood agent E2E | Flood agent implementation | Full query → flood analysis → response |
| FT-03 | Bootstrap service | — | Test `services/bootstrap.py` initialization |
| FT-04 | Multi-domain WHAT_IF | Domain supervisors registered | Parallel execution across 3 domains |
| FT-05 | Failure cascade | — | Domain failure → climate graceful degradation |
| FT-06 | Memory session continuity | — | Store in request 1, retrieve in request 2 |

---

## Medium Priority

| ID | Test | Depends On | Description |
|----|------|-----------|-------------|
| FT-07 | InfrastructureSupervisor detailed | — | Mirror environmental test coverage |
| FT-08 | EmergencySupervisor detailed | — | Mirror environmental test coverage |
| FT-09 | ParallelExecutor dedicated | — | Direct parallel execution tests |
| FT-10 | FailureHandler dedicated | — | Error recovery and retry tests |
| FT-11 | WorkflowRouter dedicated | — | Routing logic edge cases |
| FT-12 | OpenAI embedding provider | API key | Production embedding tests |
| FT-13 | Production Redis integration | Docker Redis | Real Redis TTL, pub/sub |
| FT-14 | Production Qdrant integration | Docker Qdrant | Real vector search |

---

## Low Priority

| ID | Test | Depends On | Description |
|----|------|-----------|-------------|
| FT-15 | RL engine integration | RL implementation | Policy request/evaluation |
| FT-16 | Digital twin scenario | Twin interface | Scenario create/compare |
| FT-17 | FastAPI endpoint | API layer | HTTP request/response |
| FT-18 | LangGraph checkpointing | Checkpoint store | Workflow replay |
| FT-19 | Conversation token budget | — | Truncation behavior |
| FT-20 | Agent permission model | — | Role-based tool access |

---

## Coverage Tooling

| Task | Description |
|------|-------------|
| Configure `pytest-cov` | Add coverage reporting to CI |
| Set coverage threshold | Minimum 85% line coverage |
| Generate HTML reports | `htmlcov/` for visual inspection |
| Exclude test files | Proper source-only coverage |

---

## Test Infrastructure

| Task | Description |
|------|-------------|
| Docker Compose for tests | Redis + Qdrant containers for integration tests |
| CI pipeline | GitHub Actions with test + coverage gates |
| Performance test marker | `@pytest.mark.performance` exclusion |
| Stress test marker | `@pytest.mark.stress` exclusion |

---

## Related Documents

- [Coverage Report](./coverage_report.md)
- [Integration Test Summary](./integration_test_summary.md)
- [Performance Tests](./performance_tests.md)
