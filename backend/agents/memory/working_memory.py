"""Short-lived working memory for agent reasoning and tool outputs."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from backend.agents.memory.interfaces import AgentMemory, MemoryEntry
from backend.agents.memory.memory_cache import AsyncLRUMemoryCache
from backend.utils.errors import MemoryNotFoundError


@dataclass
class _WorkingEntry:
    """Internal working memory record with expiry."""

    value: Any
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.monotonic)
    expires_at: float = 0.0
    access_count: int = 0


class WorkingMemory(AgentMemory):
    """
    Ephemeral in-process memory for active agent reasoning.

    Stores current reasoning steps, observations, temporary calculations,
    and tool outputs with automatic TTL-based expiration.
    """

    DEFAULT_TTL_SECONDS = 300  # 5 minutes

    def __init__(
        self,
        *,
        default_ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_entries: int = 500,
        cache: AsyncLRUMemoryCache[MemoryEntry] | None = None,
    ) -> None:
        self._store: dict[str, _WorkingEntry] = {}
        self._default_ttl = default_ttl_seconds
        self._max_entries = max_entries
        self._cache = cache or AsyncLRUMemoryCache[MemoryEntry](max_size=max_entries)
        self._lock = asyncio.Lock()
        self._agent_scopes: dict[str, set[str]] = {}

    @property
    def backend_name(self) -> str:
        return "working"

    async def write(
        self,
        key: str,
        value: Any,
        *,
        metadata: dict[str, Any] | None = None,
        ttl_seconds: int | None = None,
        agent_id: str | None = None,
    ) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        meta = dict(metadata or {})
        if agent_id:
            meta["agent_id"] = agent_id
        async with self._lock:
            await self._purge_expired_unlocked()
            self._store[key] = _WorkingEntry(
                value=value,
                metadata=meta,
                expires_at=time.monotonic() + ttl,
            )
            if agent_id:
                self._agent_scopes.setdefault(agent_id, set()).add(key)
            if len(self._store) > self._max_entries:
                oldest_key = min(self._store, key=lambda k: self._store[k].created_at)
                del self._store[oldest_key]
        entry = MemoryEntry(key=key, value=value, metadata=meta)
        await self._cache.set(key, entry, ttl_seconds=float(ttl))

    async def read(self, key: str) -> MemoryEntry | None:
        cached = await self._cache.get(key)
        if cached:
            return cached
        async with self._lock:
            record = self._store.get(key)
            if record is None:
                return None
            if time.monotonic() > record.expires_at:
                del self._store[key]
                return None
            record.access_count += 1
            entry = MemoryEntry(key=key, value=record.value, metadata=record.metadata)
        await self._cache.set(key, entry, ttl_seconds=record.expires_at - time.monotonic())
        return entry

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key not in self._store:
                return False
            del self._store[key]
            for scope in self._agent_scopes.values():
                scope.discard(key)
        await self._cache.delete(key)
        return True

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[MemoryEntry]:
        query_lower = query.lower()
        results: list[MemoryEntry] = []
        async with self._lock:
            await self._purge_expired_unlocked()
            for key, record in self._store.items():
                if filters and not all(record.metadata.get(k) == v for k, v in filters.items()):
                    continue
                if query_lower in key.lower() or query_lower in str(record.value).lower():
                    results.append(MemoryEntry(key=key, value=record.value, metadata=record.metadata))
                if len(results) >= limit:
                    break
        return results

    async def clear(self, namespace: str | None = None) -> int:
        async with self._lock:
            if namespace:
                keys = self._agent_scopes.pop(namespace, set())
                for key in keys:
                    self._store.pop(key, None)
                await self._cache.invalidate_prefix(namespace)
                return len(keys)
            count = len(self._store)
            self._store.clear()
            self._agent_scopes.clear()
        await self._cache.clear()
        return count

    async def store_reasoning(self, agent_id: str, steps: list[str]) -> str:
        key = f"reasoning:{agent_id}:{time.time_ns()}"
        await self.write(key, steps, metadata={"type": "reasoning"}, agent_id=agent_id)
        return key

    async def store_observation(self, agent_id: str, observation: Any) -> str:
        key = f"observation:{agent_id}:{time.time_ns()}"
        await self.write(key, observation, metadata={"type": "observation"}, agent_id=agent_id)
        return key

    async def store_calculation(self, agent_id: str, calculation: dict[str, Any]) -> str:
        key = f"calculation:{agent_id}:{time.time_ns()}"
        await self.write(key, calculation, metadata={"type": "calculation"}, agent_id=agent_id)
        return key

    async def store_tool_output(self, agent_id: str, tool_name: str, output: Any) -> str:
        key = f"tool:{agent_id}:{tool_name}:{time.time_ns()}"
        await self.write(
            key,
            output,
            metadata={"type": "tool_output", "tool_name": tool_name},
            agent_id=agent_id,
        )
        return key

    async def get_agent_scope(self, agent_id: str) -> list[MemoryEntry]:
        keys = self._agent_scopes.get(agent_id, set())
        entries: list[MemoryEntry] = []
        for key in keys:
            entry = await self.read(key)
            if entry:
                entries.append(entry)
        return entries

    async def _purge_expired_unlocked(self) -> int:
        now = time.monotonic()
        expired = [k for k, v in self._store.items() if now > v.expires_at]
        for key in expired:
            del self._store[key]
        return len(expired)

    async def purge_expired(self) -> int:
        async with self._lock:
            return await self._purge_expired_unlocked()
