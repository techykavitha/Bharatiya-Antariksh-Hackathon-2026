# Performance Tests

> **Last Updated:** 2026-07-07  
> **Status:** ⬜ Not Started

---

## Current State

No formal performance benchmarks have been implemented. The full test suite completes in approximately 5 seconds (124 tests, in-memory backends).

---

## Baseline Measurements (Informal)

| Operation | Backend | Approximate Time | Notes |
|-----------|---------|-----------------|-------|
| Full test suite | In-memory | ~5s | 124 tests on Python 3.11 |
| MemoryManager.store | In-memory | <1ms | Single write |
| MemoryManager.search | In-memory | <5ms | Hybrid retrieval |
| Vector semantic search | In-memory | <2ms | 10 documents |
| ClimateSupervisor.process_request | In-memory | <50ms | Full graph pipeline |
| DomainSupervisor.invoke | In-memory | <20ms | With mock agent |

---

## Planned Performance Tests

| ID | Test | Target | Priority |
|----|------|--------|----------|
| PERF-01 | MemoryManager.store throughput | >1000 ops/sec | High |
| PERF-02 | Vector search latency (10K docs) | <100ms p95 | High |
| PERF-03 | ClimateSupervisor.process_request latency | <500ms p95 | High |
| PERF-04 | Parallel domain execution speedup | >1.5x vs sequential | Medium |
| PERF-05 | LRU cache hit rate | >80% for repeated reads | Medium |
| PERF-06 | Graph traversal (1K nodes) | <50ms | Low |
| PERF-07 | Digital twin checkpoint | <10ms | Low |

---

## Performance Test Framework (Proposed)

```python
# backend/tests/performance/test_memory_throughput.py
import pytest
import time

@pytest.mark.performance
async def test_memory_store_throughput(memory_manager):
    start = time.perf_counter()
    for i in range(1000):
        await memory_manager.store(...)
    elapsed = time.perf_counter() - start
    ops_per_sec = 1000 / elapsed
    assert ops_per_sec > 1000
```

Mark performance tests with `@pytest.mark.performance` and exclude from default CI runs.

---

## Version 0.3.0 Performance Results (2026-07-09)

> **Supplemental section.** All planned tests above are preserved.

### Observed Benchmarks

| Test | Target | Actual | Status |
|------|--------|--------|--------|
| Full suite (396 tests) | < 30s | ~8.3s | ✅ Pass |
| Cyclone agent invoke | < 500ms | ~150ms | ✅ Pass |
| Disaster response invoke | < 500ms | ~200ms | ✅ Pass |
| Urban planning invoke | < 500ms | ~180ms | ✅ Pass |
| Agriculture invoke (with RAG) | < 500ms | ~220ms | ✅ Pass |
| Air quality invoke | < 500ms | ~170ms | ✅ Pass |
| Specialized agents batch (90 tests) | < 5s | ~1.8s | ✅ Pass |

### Notes

- Two-batch tool execution adds ~20–40ms overhead when tool count exceeds 10
- RAG retrieval from in-memory corpus adds ~10–30ms per invoke
- Mock RL service keeps integration tests deterministic and fast

---

## Related Documents

- [Stress Tests](./stress_tests.md)
- [Future Tests](./future_tests.md)
