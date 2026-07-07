# Configuration Architecture

> **Status:** Active  
> **Version:** 0.1.0  
> **Last Updated:** 2026-07-07

---

## Purpose

Centralized configuration management for the Hyperion Climate Twin AI layer using Pydantic Settings v2 with environment variable overrides.

---

## GlobalConfig

**Location:** `backend/config/settings.py`

Singleton configuration loaded via `get_config()` with `@lru_cache` for process-lifetime caching.

### Top-Level Sections

| Section | Class | Purpose |
|---------|-------|---------|
| `app` | `AppConfig` | Application name, environment, debug |
| `redis` | `RedisConfig` | Redis connection parameters |
| `qdrant` | `QdrantConfig` | Qdrant vector store parameters |
| `embedding` | `EmbeddingConfig` | Embedding provider settings |
| `memory` | `MemoryConfig` | Cache size, TTL defaults |
| `supervisor` | `SupervisorConfig` | Orchestration timeouts and limits |
| `logging` | `LoggingConfig` | Log level and format |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HYPERION_ENV` | `development` | Deployment environment |
| `HYPERION_DEBUG` | `false` | Debug mode flag |
| `HYPERION_REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `HYPERION_QDRANT_HOST` | `localhost` | Qdrant host |
| `HYPERION_QDRANT_PORT` | `6333` | Qdrant port |
| `HYPERION_EMBEDDING_PROVIDER` | `deterministic` | Embedding provider name |
| `HYPERION_OPENAI_API_KEY` | — | OpenAI API key (if using OpenAI embeddings) |
| `HYPERION_LOG_LEVEL` | `INFO` | Application log level |
| `HYPERION_MEMORY_CACHE_SIZE` | `4096` | LRU cache max entries |

---

## DependencyRegistry

**Location:** `backend/config/dependency_registry.py`

Thread-safe singleton registry for dependency injection.

| Method | Visibility | Purpose |
|--------|-----------|---------|
| `register(name, instance)` | Public | Register singleton instance |
| `register_factory(name, factory)` | Public | Register lazy factory |
| `resolve(name)` | Public | Resolve registered dependency |
| `is_registered(name)` | Public | Check registration |
| `reset()` | Public | Clear all registrations (testing) |

**Errors:**
- `DependencyRegistrationError` — Duplicate registration
- `DependencyNotFoundError` — Unregistered dependency

---

## Logger

**Location:** `backend/config/logger.py`

Structured logging wrapper around `structlog`.

| Function | Purpose |
|----------|---------|
| `get_logger(name)` | Get named logger instance |
| `configure_logging(config)` | Initialize logging from config |

Log output includes: timestamp, level, logger name, message, structured context fields.

---

## Bootstrap Service

**Location:** `backend/services/bootstrap.py`

Application initialization sequence:

1. Load `GlobalConfig` from environment
2. Configure structured logging
3. Create `MemoryManager` (in-memory or production backends)
4. Register dependencies in `DependencyRegistry`
5. Initialize `ClimateSupervisor`
6. Register domain supervisors in `DomainRegistry`

---

## Configuration in Tests

Tests use `MemoryManager.create_in_memory()` which bypasses production Redis/Qdrant configuration entirely. `GlobalConfig` defaults are sufficient for all current tests.

---

## Security Considerations

- API keys loaded from environment only — never hardcoded
- Redis URL may contain credentials — use secrets management in production
- `HYPERION_DEBUG=true` exposes additional log detail — disable in production

---

## Future Extensions

- `pyproject.toml` / `.env.example` alignment documentation
- Kubernetes ConfigMap / Secret mapping guide
- Feature flags section in GlobalConfig
- Per-domain supervisor configuration overrides
