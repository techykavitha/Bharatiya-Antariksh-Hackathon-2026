"""Redis-backed memory implementation for Hyperion Climate Twin."""

from __future__ import annotations

import asyncio
import fnmatch
import time
from typing import Any, Protocol, runtime_checkable

from backend.agents.memory.interfaces import MemoryEntry, RedisMemory
from backend.agents.memory.memory_cache import AsyncLRUMemoryCache
from backend.agents.memory.serialization import deserialize_value, serialize_value
from backend.config.settings import RedisConfig
from backend.utils.constants import (
    DEFAULT_MEMORY_TTL_SECONDS,
    REDIS_MEMORY_PREFIX,
    REDIS_SESSION_PREFIX,
)
from backend.utils.errors import MemoryReadError, MemoryWriteError


@runtime_checkable
class RedisClientProtocol(Protocol):
    """Minimal async Redis client protocol for dependency injection."""

    async def get(self, name: str) -> bytes | str | None: ...
    async def set(
        self,
        name: str,
        value: str | bytes,
        *,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool | None: ...
    async def delete(self, *names: str) -> int: ...
    async def exists(self, *names: str) -> int: ...
    async def expire(self, name: str, time: int) -> bool: ...
    async def ttl(self, name: str) -> int: ...
    async def keys(self, pattern: str) -> list[str]: ...
    async def sadd(self, name: str, *values: str) -> int: ...
    async def smembers(self, name: str) -> set[str]: ...
    async def srem(self, name: str, *values: str) -> int: ...
    async def scan_iter(self, match: str | None = None, count: int = 100) -> Any: ...
    async def ping(self) -> bool: ...


class InMemoryRedisClient:
    """
    In-memory Redis-compatible client for unit tests and local development.

    Supports TTL, session index sets, and key pattern scanning.
    """

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._expiry: dict[str, float] = {}
        self._sets: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    async def _purge_expired(self, key: str) -> None:
        if key in self._expiry and time.monotonic() > self._expiry[key]:
            self._data.pop(key, None)
            self._expiry.pop(key, None)

    async def get(self, name: str) -> str | None:
        async with self._lock:
            await self._purge_expired(name)
            return self._data.get(name)

    async def set(
        self,
        name: str,
        value: str | bytes,
        *,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool | None:
        async with self._lock:
            await self._purge_expired(name)
            if nx and name in self._data:
                return False
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            self._data[name] = value
            if ex is not None:
                self._expiry[name] = time.monotonic() + ex
            elif name in self._expiry:
                del self._expiry[name]
            return True

    async def delete(self, *names: str) -> int:
        async with self._lock:
            count = 0
            for name in names:
                if name in self._data or name in self._sets:
                    self._data.pop(name, None)
                    self._expiry.pop(name, None)
                    self._sets.pop(name, None)
                    count += 1
            return count

    async def exists(self, *names: str) -> int:
        async with self._lock:
            return sum(1 for n in names if n in self._data)

    async def expire(self, name: str, seconds: int) -> bool:
        async with self._lock:
            if name not in self._data:
                return False
            self._expiry[name] = time.monotonic() + seconds
            return True

    async def ttl(self, name: str) -> int:
        async with self._lock:
            if name not in self._data:
                return -2
            if name not in self._expiry:
                return -1
            remaining = int(self._expiry[name] - time.monotonic())
            return max(remaining, 0)

    async def keys(self, pattern: str) -> list[str]:
        async with self._lock:
            return [k for k in self._data if fnmatch.fnmatch(k, pattern)]

    async def sadd(self, name: str, *values: str) -> int:
        async with self._lock:
            bucket = self._sets.setdefault(name, set())
            before = len(bucket)
            bucket.update(values)
            return len(bucket) - before

    async def smembers(self, name: str) -> set[str]:
        async with self._lock:
            return set(self._sets.get(name, set()))

    async def srem(self, name: str, *values: str) -> int:
        async with self._lock:
            bucket = self._sets.get(name, set())
            before = len(bucket)
            bucket -= set(values)
            return before - len(bucket)

    async def scan_iter(self, match: str | None = None, count: int = 100) -> Any:
        async with self._lock:
            keys = list(self._data.keys())
        for key in keys:
            if match is None or fnmatch.fnmatch(key, match):
                yield key

    async def ping(self) -> bool:
        return True


class RedisMemoryStore(RedisMemory):
    """
    Production Redis memory backend for conversation, workflow, and session data.

    Provides TTL management, session key indexing, and thread-safe async access.
    """

    WORKFLOW_STATE_KEY = "workflow_state"
    ACTIVE_SCENARIO_KEY = "active_scenario"
    ACTIVE_SIMULATION_KEY = "active_simulation"
    ACTIVE_USER_KEY = "active_user"
    TEMP_CONTEXT_KEY = "temp_context"
    CONVERSATION_HISTORY_KEY = "conversation_history"

    def __init__(
        self,
        client: RedisClientProtocol,
        *,
        config: RedisConfig | None = None,
        namespace: str = REDIS_MEMORY_PREFIX,
        default_ttl: int = DEFAULT_MEMORY_TTL_SECONDS,
        cache: AsyncLRUMemoryCache[MemoryEntry] | None = None,
    ) -> None:
        self._client = client
        self._config = config
        self._namespace = namespace
        self._default_ttl = default_ttl
        self._cache = cache or AsyncLRUMemoryCache[MemoryEntry](max_size=2048)
        self._lock = asyncio.Lock()

    @property
    def backend_name(self) -> str:
        return "redis"

    def _full_key(self, key: str, session_id: str | None = None) -> str:
        if session_id:
            return f"{REDIS_SESSION_PREFIX}:{session_id}:{key}"
        return f"{self._namespace}:{key}"

    def _session_index_key(self, session_id: str) -> str:
        return f"{REDIS_SESSION_PREFIX}:{session_id}:__index__"

    def _session_key_prefix(self, session_id: str) -> str:
        return f"{REDIS_SESSION_PREFIX}:{session_id}:"

    def _extract_session_key(self, full_key: str, session_id: str) -> str:
        prefix = self._session_key_prefix(session_id)
        if full_key.startswith(prefix):
            return full_key[len(prefix):]
        return full_key.rsplit(":", 1)[-1]

    async def write(
        self,
        key: str,
        value: Any,
        *,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        """Persist a value with optional session scoping and TTL."""
        full_key = self._full_key(key, session_id)
        envelope = {
            "value": value,
            "metadata": metadata or {},
            "stored_at": time.time(),
        }
        try:
            payload = serialize_value(envelope)
            ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
            async with self._lock:
                await self._client.set(full_key, payload, ex=ttl)
                if session_id:
                    await self._client.sadd(self._session_index_key(session_id), full_key)
            entry = MemoryEntry(key=key, value=value, metadata=metadata or {})
            await self._cache.set(full_key, entry, ttl_seconds=float(ttl))
        except Exception as exc:
            raise MemoryWriteError(
                f"Failed to write Redis key '{key}': {exc}",
                details={"key": key, "session_id": session_id},
            ) from exc

    async def read(self, key: str, *, session_id: str | None = None) -> MemoryEntry | None:
        """Retrieve a value by key."""
        full_key = self._full_key(key, session_id)
        cached = await self._cache.get(full_key)
        if cached is not None:
            return cached
        try:
            raw = await self._client.get(full_key)
            if raw is None:
                return None
            envelope = deserialize_value(raw)
            entry = MemoryEntry(
                key=key,
                value=envelope.get("value"),
                metadata=envelope.get("metadata", {}),
            )
            ttl_remaining = await self._client.ttl(full_key)
            cache_ttl = float(ttl_remaining) if ttl_remaining > 0 else None
            await self._cache.set(full_key, entry, ttl_seconds=cache_ttl)
            return entry
        except Exception as exc:
            raise MemoryReadError(
                f"Failed to read Redis key '{key}': {exc}",
                details={"key": key, "session_id": session_id},
            ) from exc

    async def delete(self, key: str, *, session_id: str | None = None) -> bool:
        full_key = self._full_key(key, session_id)
        async with self._lock:
            removed = await self._client.delete(full_key)
            if session_id:
                await self._client.srem(self._session_index_key(session_id), full_key)
        await self._cache.delete(full_key)
        return removed > 0

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> list[MemoryEntry]:
        """Search Redis keys by substring match on key and serialized value."""
        pattern = f"{self._namespace}:*" if not session_id else f"{REDIS_SESSION_PREFIX}:{session_id}:*"
        results: list[MemoryEntry] = []
        query_lower = query.lower()
        async for full_key in self._client.scan_iter(match=pattern):
            if full_key.endswith(":__index__"):
                continue
            raw = await self._client.get(full_key)
            if raw is None:
                continue
            envelope = deserialize_value(raw)
            value = envelope.get("value")
            metadata = envelope.get("metadata", {})
            if filters and not all(metadata.get(k) == v for k, v in filters.items()):
                continue
            serialized = serialize_value(value).lower()
            short_key = full_key.split(":", maxsplit=2)[-1]
            if query_lower in short_key.lower() or query_lower in serialized:
                results.append(MemoryEntry(key=short_key, value=value, metadata=metadata))
            if len(results) >= limit:
                break
        return results

    async def clear(self, namespace: str | None = None) -> int:
        prefix = namespace or self._namespace
        count = 0
        async for key in self._client.scan_iter(match=f"{prefix}:*"):
            await self._client.delete(key)
            await self._cache.delete(key)
            count += 1
        return count

    async def set_ttl(self, key: str, ttl_seconds: int, *, session_id: str | None = None) -> None:
        full_key = self._full_key(key, session_id)
        await self._client.expire(full_key, ttl_seconds)
        await self._cache.delete(full_key)

    async def get_session_keys(self, session_id: str) -> list[str]:
        index_key = self._session_index_key(session_id)
        members = await self._client.smembers(index_key)
        return sorted(members)

    async def store_workflow_state(self, state: dict[str, Any], *, session_id: str | None = None) -> None:
        await self.write(self.WORKFLOW_STATE_KEY, state, session_id=session_id)

    async def get_workflow_state(self, *, session_id: str | None = None) -> MemoryEntry | None:
        return await self.read(self.WORKFLOW_STATE_KEY, session_id=session_id)

    async def store_active_scenario(self, scenario: Any, *, session_id: str | None = None) -> None:
        await self.write(self.ACTIVE_SCENARIO_KEY, scenario, session_id=session_id)

    async def get_active_scenario(self, *, session_id: str | None = None) -> MemoryEntry | None:
        return await self.read(self.ACTIVE_SCENARIO_KEY, session_id=session_id)

    async def store_active_simulation(self, simulation: Any, *, session_id: str | None = None) -> None:
        await self.write(self.ACTIVE_SIMULATION_KEY, simulation, session_id=session_id)

    async def get_active_simulation(self, *, session_id: str | None = None) -> MemoryEntry | None:
        return await self.read(self.ACTIVE_SIMULATION_KEY, session_id=session_id)

    async def store_active_user(self, user: Any, *, session_id: str | None = None) -> None:
        await self.write(self.ACTIVE_USER_KEY, user, session_id=session_id)

    async def get_active_user(self, *, session_id: str | None = None) -> MemoryEntry | None:
        return await self.read(self.ACTIVE_USER_KEY, session_id=session_id)

    async def store_temp_context(self, context: dict[str, Any], *, session_id: str | None = None, ttl_seconds: int = 3600) -> None:
        await self.write(self.TEMP_CONTEXT_KEY, context, session_id=session_id, ttl_seconds=ttl_seconds)

    async def get_temp_context(self, *, session_id: str | None = None) -> MemoryEntry | None:
        return await self.read(self.TEMP_CONTEXT_KEY, session_id=session_id)

    async def store_conversation_history(self, history: list[Any], *, session_id: str | None = None) -> None:
        await self.write(self.CONVERSATION_HISTORY_KEY, history, session_id=session_id)

    async def get_conversation_history(self, *, session_id: str | None = None) -> MemoryEntry | None:
        return await self.read(self.CONVERSATION_HISTORY_KEY, session_id=session_id)

    @classmethod
    async def from_config(
        cls,
        config: RedisConfig | None = None,
        *,
        client: RedisClientProtocol | None = None,
    ) -> RedisMemoryStore:
        """Create a RedisMemoryStore from configuration or inject a client."""
        if client is not None:
            return cls(client, config=config)
        try:
            import redis.asyncio as aioredis

            cfg = config
            if cfg is None:
                from backend.config.settings import get_config

                cfg = get_config().redis
            password = cfg.password.get_secret_value() if cfg.password else None
            redis_client = aioredis.Redis(
                host=cfg.host,
                port=cfg.port,
                db=cfg.db,
                password=password,
                ssl=cfg.ssl,
                decode_responses=cfg.decode_responses,
                socket_timeout=cfg.socket_timeout,
            )
            await redis_client.ping()
            return cls(redis_client, config=cfg)
        except Exception:
            return cls(InMemoryRedisClient(), config=config)
