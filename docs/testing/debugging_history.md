# Debugging History

> **Last Updated:** 2026-07-07

---

## Bug Registry

| Bug ID | Component | Severity | Status |
|--------|-----------|----------|--------|
| BUG-001 | Memory / Redis | Medium | ✅ Fixed |
| BUG-002 | Memory / Redis | Medium | ✅ Fixed |
| BUG-003 | Memory / Vector | High | ✅ Fixed |
| BUG-004 | Memory / Cache | Medium | ✅ Fixed |
| BUG-005 | Memory / Vector | Medium | ✅ Fixed |
| BUG-006 | Memory / Embedding | Low | ✅ Fixed |
| BUG-007 | Supervisor | High | ✅ Fixed |
| BUG-008 | Domain | Low | ✅ Fixed |

---

## BUG-001: Redis expire() Parameter Shadowing

| Field | Value |
|-------|-------|
| **Bug ID** | BUG-001 |
| **Date Found** | 2026-07-07 |
| **Component** | `InMemoryRedisClient.expire()` |
| **Severity** | Medium |

### Description

The `expire()` method parameter was named `time`, which shadowed the imported `time` module, causing `AttributeError` when computing TTL expiry.

### Affected Files

- `backend/agents/memory/redis_memory.py`

### Symptoms

- `test_redis_ttl` failed with `AttributeError: 'int' object has no attribute 'time'`
- TTL-based key expiration did not work in in-memory Redis mock

### Root Cause

Parameter name `time` collided with `import time` at module level. Inside `expire()`, `time.time()` resolved to the integer parameter instead of the module.

### Fix

Renamed parameter from `time` to `seconds` in `InMemoryRedisClient.expire()`.

### Validation

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| `test_redis_ttl` | Key expires after TTL | Key not found after sleep | ✅ Pass |

### Regression Testing

All 8 `test_redis_memory.py` tests re-run — all pass.

### Lessons Learned

Avoid naming parameters after imported module names. Use descriptive names like `seconds`, `ttl_seconds`.

---

## BUG-002: Session Key Extraction

| Field | Value |
|-------|-------|
| **Bug ID** | BUG-002 |
| **Date Found** | 2026-07-07 |
| **Component** | `RedisMemoryStore._extract_session_key()` |
| **Severity** | Medium |

### Description

Session key extraction used `split(":", 2)` which incorrectly truncated multi-segment session keys.

### Affected Files

- `backend/agents/memory/redis_memory.py`
- `backend/agents/memory/session_memory.py`

### Symptoms

- `test_redis_session_keys` returned wrong keys
- Session-scoped operations failed for keys with multiple colon segments

### Root Cause

`split(":", 2)` limits splits to 2, but session keys like `hyperion:session:abc:preferences` have more segments. The prefix-aware extraction was missing.

### Fix

Implemented `_extract_session_key()` that strips the known prefix (`hyperion:session:{session_id}:`) before returning the key suffix.

### Validation

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| `test_redis_session_keys` | Correct key list | Matching keys returned | ✅ Pass |
| `test_session_create_and_preferences` | Preferences stored/retrieved | Roundtrip successful | ✅ Pass |

### Regression Testing

All Redis and session memory tests re-run — all pass.

### Lessons Learned

Key schema design must be documented. Prefix-based extraction is safer than positional splitting.

---

## BUG-003: Vector Search Wrong Collection

| Field | Value |
|-------|-------|
| **Bug ID** | BUG-003 |
| **Date Found** | 2026-07-07 |
| **Component** | `QdrantVectorMemory.search()` |
| **Severity** | High |

### Description

Vector search only queried the default collection, missing documents stored in domain-specific collections.

### Affected Files

- `backend/agents/memory/vector_memory.py`
- `backend/agents/memory/hybrid_retriever.py`

### Symptoms

- `test_manager_vector_and_search` failed — search returned empty results
- `test_vector_semantic_search` passed for single collection but failed in multi-collection scenarios

### Root Cause

`search()` hardcoded the default collection name. Documents stored in `climate_docs`, `forecasts`, etc. were invisible to search.

### Fix

Extended search to iterate all registered collections when no specific collection is requested, merging and re-ranking results.

### Validation

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| `test_manager_vector_and_search` | Non-empty search results | Results returned | ✅ Pass |
| `test_vector_semantic_search` | Ranked by similarity | Correct ordering | ✅ Pass |

### Regression Testing

All 7 vector memory tests + 10 memory manager tests re-run — all pass.

### Lessons Learned

Multi-collection search is essential for domain-separated vector stores. Document collection naming conventions.

---

## BUG-004: LRU Cache Stale After TTL

| Field | Value |
|-------|-------|
| **Bug ID** | BUG-004 |
| **Date Found** | 2026-07-07 |
| **Component** | `AsyncLRUMemoryCache` + `RedisMemoryStore` |
| **Severity** | Medium |

### Description

LRU cache served stale entries after the underlying Redis key expired via TTL.

### Affected Files

- `backend/agents/memory/memory_cache.py`
- `backend/agents/memory/redis_memory.py`

### Symptoms

- `test_cache_ttl_expiry` intermittent failures
- `retrieve()` returned expired data from cache

### Root Cause

`set_ttl()` on Redis did not invalidate the corresponding cache entry. Cache had its own TTL but could outlive the Redis TTL.

### Fix

Added cache invalidation call in `RedisMemoryStore.set_ttl()` and on `delete()` operations.

### Validation

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| `test_cache_ttl_expiry` | Cache miss after TTL | None returned | ✅ Pass |
| `test_redis_ttl` | Key expired in Redis | Key not found | ✅ Pass |

### Regression Testing

All 5 cache tests + 8 Redis tests re-run — all pass.

### Lessons Learned

Cache invalidation must be coupled with backend TTL changes. Consider unified TTL management.

---

## BUG-005: Vector Metadata Value Overwrite

| Field | Value |
|-------|-------|
| **Bug ID** | BUG-005 |
| **Date Found** | 2026-07-07 |
| **Component** | `QdrantVectorMemory.write()` |
| **Severity** | Medium |

### Description

The `value` key in metadata overwrote the document payload during vector write.

### Affected Files

- `backend/agents/memory/vector_memory.py`

### Symptoms

- `test_vector_insert_and_read` — retrieved document had wrong content
- Metadata field `value` clobbered the actual stored value

### Root Cause

Payload construction used `metadata.get("value", content)` but then stored the full metadata dict including the `value` key, causing double-write of the value field.

### Fix

Added `meta.pop("value", None)` before payload construction to prevent metadata from overwriting document content.

### Validation

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| `test_vector_insert_and_read` | Original content preserved | Content matches | ✅ Pass |
| `test_vector_update` | Updated content stored | Update successful | ✅ Pass |

### Regression Testing

All vector tests re-run — all pass.

### Lessons Learned

Reserved metadata keys must be documented. Use namespaced metadata keys to avoid collisions.

---

## BUG-006: Deterministic Embedder Low Similarity

| Field | Value |
|-------|-------|
| **Bug ID** | BUG-006 |
| **Date Found** | 2026-07-07 |
| **Component** | `DeterministicEmbeddingProvider` |
| **Severity** | Low |

### Description

Deterministic embedder produced vectors with insufficient similarity for related texts, causing semantic search tests to fail.

### Affected Files

- `backend/agents/memory/embedding.py`

### Symptoms

- `test_vector_semantic_search` — unrelated texts scored higher than related texts
- `test_vector_similarity_search` — low similarity scores for obvious matches

### Root Cause

Original hash-based embedding did not consider token overlap, producing near-random similarity for short texts.

### Fix

Improved embedder to use token overlap weighting with position encoding for better semantic proximity in test scenarios.

### Validation

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| `test_vector_semantic_search` | Related texts rank higher | Correct ordering | ✅ Pass |
| `test_vector_similarity_search` | High similarity for match | Score > threshold | ✅ Pass |

### Regression Testing

All vector and ranker tests re-run — all pass.

### Lessons Learned

Test embedders need reasonable semantic fidelity. Production will use OpenAI or domain-specific embeddings.

---

## BUG-007: Circular Import Climate Supervisor

| Field | Value |
|-------|-------|
| **Bug ID** | BUG-007 |
| **Date Found** | 2026-07-07 |
| **Component** | `climate_supervisor.py` ↔ `graph_builder.py` |
| **Severity** | High |

### Description

Circular import between `ClimateSupervisor` and `graph_builder` prevented module loading.

### Affected Files

- `backend/agents/supervisor/climate_supervisor.py`
- `backend/agents/supervisor/graph_builder.py`

### Symptoms

- `ImportError: cannot import name 'ClimateSupervisor' from partially initialized module`
- All supervisor tests failed to collect

### Root Cause

`climate_supervisor.py` imported `build_graph` at module level, and `graph_builder.py` imported `ClimateSupervisor` at module level.

### Fix

Moved `build_graph` / `compile_graph` imports to lazy imports inside `initialize()` and `process_request()` methods.

### Validation

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| `test_supervisor_initialize` | Graph compiles | No import error | ✅ Pass |
| `test_graph_build_and_compile` | Graph builds | Compiled graph returned | ✅ Pass |
| All supervisor tests | 22 pass | 22 pass | ✅ Pass |

### Regression Testing

Full test suite re-run — 106 tests pass (at time of fix).

### Lessons Learned

LangGraph builder modules should use lazy imports. Consider separating graph definition from supervisor class.

---

## BUG-008: DomainAgentResult Missing Metadata

| Field | Value |
|-------|-------|
| **Bug ID** | BUG-008 |
| **Date Found** | 2026-07-07 |
| **Component** | `DomainExecutionResult` / domain context models |
| **Severity** | Low |

### Description

`DomainAgentResult` model was missing a `metadata` field, causing validation errors when agents returned metadata.

### Affected Files

- `backend/agents/domain/domain_context.py`

### Symptoms

- `test_execute_with_registered_agents` — Pydantic validation error on agent result
- `test_merge_results` — metadata lost during merge

### Root Cause

Model defined without optional `metadata` field that executor populated.

### Fix

Added `metadata: dict[str, Any] = Field(default_factory=dict)` to `DomainAgentResult`.

### Validation

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| `test_execute_with_registered_agents` | Execution completes | AgentResponse returned | ✅ Pass |
| `test_merge_results` | Metadata preserved | Metadata in merged result | ✅ Pass |

### Regression Testing

All 18 domain tests re-run — all pass.

### Lessons Learned

Pydantic models for execution results should always include `metadata` for extensibility.

---

## Related Documents

- [Development Log 001](../development_logs/001_shared_memory.md)
- [Development Log 002](../development_logs/002_climate_supervisor.md)
- [Development Log 003](../development_logs/003_domain_supervisors.md)
