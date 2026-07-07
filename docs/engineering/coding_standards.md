# Coding Standards

> **Last Updated:** 2026-07-07  
> **Applies To:** All `backend/` Python source code

---

## Language & Runtime

| Standard | Value |
|----------|-------|
| Python | 3.12+ (`requires-python = ">=3.12"` in `pyproject.toml`) |
| Package manager | pip / setuptools |
| Line length | 100 characters (ruff) |
| Import style | Absolute: `from backend.agents.memory import MemoryManager` |

---

## Type System

- **Pydantic v2** for all request/response schemas and configuration models
- **TypedDict** for LangGraph `WorkflowState` (not Pydantic — LangGraph requirement)
- **StrEnum** for all enumerations
- **Protocol** / **ABC** for interfaces
- **Dataclasses** for immutable policy objects (e.g., `FailurePolicy`)
- `mypy` strict mode enabled in `pyproject.toml`

---

## Async Conventions

- All I/O operations must be `async def`
- Use `asyncio.Lock` for thread-safe in-process state
- Use `asyncio.gather(..., return_exceptions=True)` for parallel execution
- Use `asyncio.wait_for()` for timeouts
- Never block the event loop with synchronous I/O in agent paths

---

## SOLID Principles

| Principle | Application |
|-----------|-------------|
| **S**ingle Responsibility | Each module owns one concern (e.g., `MemoryRanker` only ranks) |
| **O**pen/Closed | Extend via subclassing (`BaseAgent`, `BaseDomainSupervisor`) not modification |
| **L**iskov Substitution | All memory backends implement `AgentMemory` interchangeably |
| **I**nterface Segregation | Separate protocols: `DomainSupervisorHandler`, `DomainAgentHandler`, `RLEngineInterface` |
| **D**ependency Inversion | Depend on `MemoryManager`, not Redis/Qdrant directly |

---

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Modules | `snake_case` | `climate_supervisor.py` |
| Classes | `PascalCase` | `ClimateSupervisor` |
| Functions/methods | `snake_case` | `classify_intent()` |
| Constants | `UPPER_SNAKE` | `MAX_AGENT_RETRIES` |
| Enums | `PascalCase` class, `UPPER_SNAKE` members | `SupervisorIntent.WHAT_IF` |
| Private | Leading underscore | `_resolve_agent()` |
| Supervisor IDs | `snake_case` string | `"environmental_supervisor"` |
| Agent IDs | `snake_case` with `_agent` suffix | `"flood_agent"` |

---

## Error Handling

- Use the `backend.utils.errors` hierarchy — never bare `Exception` in public APIs
- Include `details: dict` in all custom exceptions for structured logging
- Fail fast on configuration errors at startup
- Retry transient failures in executors with exponential backoff
- Allow partial completion where business logic permits

---

## Logging

- Use `get_logger(__name__)` from `backend.config.logger`
- Structured key-value logging: `logger.info("event_name", key=value)`
- Log at every supervisor state transition
- Never log secrets or API keys

---

## Memory Access Rule

```
✅ await memory_manager.store(MemoryStoreRequest(...))
❌ await redis_client.set(...)
❌ await qdrant_client.upsert(...)
```

---

## Documentation in Code

- Module-level docstring explaining purpose
- Class docstring explaining responsibility
- Public method docstrings with Parameters/Returns/Raises sections
- No comments explaining obvious code
- Comments only for non-obvious business logic

---

## Testing Standards

- Test file mirrors source: `backend/agents/memory/redis_memory.py` → `backend/tests/memory/test_redis_memory.py`
- Use `pytest.mark.asyncio` for async tests
- Mock external services with in-memory implementations (`InMemoryRedisClient`, `InMemoryQdrantClient`)
- Fixtures in `conftest.py` per test package
- Test names describe behavior: `test_redis_ttl_expiry`
