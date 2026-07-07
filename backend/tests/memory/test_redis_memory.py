"""Unit tests for Redis memory store."""

import pytest

from backend.agents.memory.redis_memory import InMemoryRedisClient, RedisMemoryStore


@pytest.mark.asyncio
async def test_redis_write_read(redis_store: RedisMemoryStore) -> None:
    await redis_store.write("key1", {"data": 42})
    entry = await redis_store.read("key1")
    assert entry is not None
    assert entry.value == {"data": 42}


@pytest.mark.asyncio
async def test_redis_session_scoped(redis_store: RedisMemoryStore) -> None:
    await redis_store.write("ctx", "session-data", session_id="sess-1")
    entry = await redis_store.read("ctx", session_id="sess-1")
    assert entry is not None
    assert entry.value == "session-data"
    assert await redis_store.read("ctx") is None


@pytest.mark.asyncio
async def test_redis_ttl(redis_store: RedisMemoryStore) -> None:
    await redis_store.write("temp", "value", ttl_seconds=3600)
    await redis_store.set_ttl("temp", 1)
    import asyncio
    await asyncio.sleep(1.1)
    assert await redis_store.read("temp") is None


@pytest.mark.asyncio
async def test_redis_session_keys(redis_store: RedisMemoryStore) -> None:
    await redis_store.write("a", 1, session_id="s1")
    await redis_store.write("b", 2, session_id="s1")
    keys = await redis_store.get_session_keys("s1")
    assert len(keys) == 2


@pytest.mark.asyncio
async def test_redis_workflow_state(redis_store: RedisMemoryStore) -> None:
    state = {"agent_status": "idle", "climate_state": {"scenario_id": "s1"}}
    await redis_store.store_workflow_state(state, session_id="ws-1")
    entry = await redis_store.get_workflow_state(session_id="ws-1")
    assert entry is not None
    assert entry.value["climate_state"]["scenario_id"] == "s1"


@pytest.mark.asyncio
async def test_redis_search(redis_store: RedisMemoryStore) -> None:
    await redis_store.write("flood_risk", {"level": "high"})
    results = await redis_store.search("flood")
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_redis_delete(redis_store: RedisMemoryStore) -> None:
    await redis_store.write("del", "x")
    assert await redis_store.delete("del") is True
    assert await redis_store.read("del") is None


@pytest.mark.asyncio
async def test_in_memory_redis_client_ping() -> None:
    client = InMemoryRedisClient()
    assert await client.ping() is True
