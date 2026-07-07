"""Async LRU memory cache for hot-path memory reads."""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass
class _CacheEntry(Generic[T]):
    """Internal cache entry with expiry tracking."""

    value: T
    expires_at: float | None = None
    hits: int = 0
    created_at: float = field(default_factory=time.monotonic)


class AsyncLRUMemoryCache(Generic[T]):
    """
    Thread-safe async LRU cache with optional per-entry TTL.

    Used by memory backends and MemoryManager to reduce redundant
    reads from Redis, Qdrant, and graph stores.
    """

    def __init__(self, *, max_size: int = 1024, default_ttl_seconds: float | None = None) -> None:
        self._max_size = max(1, max_size)
        self._default_ttl = default_ttl_seconds
        self._store: OrderedDict[str, _CacheEntry[T]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def size(self) -> int:
        return len(self._store)

    async def get(self, key: str) -> T | None:
        """Retrieve a value from cache, returning None on miss or expiry."""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.expires_at is not None and time.monotonic() > entry.expires_at:
                del self._store[key]
                self._misses += 1
                return None
            self._store.move_to_end(key)
            entry.hits += 1
            self._hits += 1
            return entry.value

    async def set(
        self,
        key: str,
        value: T,
        *,
        ttl_seconds: float | None = None,
    ) -> None:
        """Store a value in cache, evicting the LRU entry if at capacity."""
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expires_at = time.monotonic() + ttl if ttl is not None else None
        async with self._lock:
            if key in self._store:
                del self._store[key]
            self._store[key] = _CacheEntry(value=value, expires_at=expires_at)
            self._evict_if_needed()

    async def delete(self, key: str) -> bool:
        """Remove a key from cache. Returns True if it existed."""
        async with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def clear(self) -> int:
        """Remove all entries. Returns the number of entries cleared."""
        async with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    async def invalidate_prefix(self, prefix: str) -> int:
        """Remove all keys starting with the given prefix."""
        async with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for key in keys:
                del self._store[key]
            return len(keys)

    async def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        now = time.monotonic()
        async with self._lock:
            expired = [k for k, e in self._store.items() if e.expires_at is not None and now > e.expires_at]
            for key in expired:
                del self._store[key]
            return len(expired)

    def _evict_if_needed(self) -> None:
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)
