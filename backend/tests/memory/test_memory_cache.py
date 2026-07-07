"""Unit tests for AsyncLRUMemoryCache."""

import pytest

from backend.agents.memory.memory_cache import AsyncLRUMemoryCache


@pytest.mark.asyncio
async def test_cache_set_and_get() -> None:
    cache: AsyncLRUMemoryCache[str] = AsyncLRUMemoryCache(max_size=10)
    await cache.set("a", "value")
    assert await cache.get("a") == "value"


@pytest.mark.asyncio
async def test_cache_miss() -> None:
    cache: AsyncLRUMemoryCache[str] = AsyncLRUMemoryCache()
    assert await cache.get("missing") is None
    assert cache.misses == 1


@pytest.mark.asyncio
async def test_cache_lru_eviction() -> None:
    cache: AsyncLRUMemoryCache[int] = AsyncLRUMemoryCache(max_size=2)
    await cache.set("a", 1)
    await cache.set("b", 2)
    await cache.set("c", 3)
    assert await cache.get("a") is None
    assert await cache.get("b") == 2
    assert await cache.get("c") == 3


@pytest.mark.asyncio
async def test_cache_ttl_expiry() -> None:
    cache: AsyncLRUMemoryCache[str] = AsyncLRUMemoryCache()
    await cache.set("key", "val", ttl_seconds=0.01)
    import asyncio
    await asyncio.sleep(0.02)
    assert await cache.get("key") is None


@pytest.mark.asyncio
async def test_cache_delete_and_clear() -> None:
    cache: AsyncLRUMemoryCache[str] = AsyncLRUMemoryCache()
    await cache.set("a", "1")
    await cache.set("b", "2")
    assert await cache.delete("a") is True
    cleared = await cache.clear()
    assert cleared == 1
