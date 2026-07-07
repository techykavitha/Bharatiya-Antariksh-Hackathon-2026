"""Unit tests for working memory."""

import pytest

from backend.agents.memory.working_memory import WorkingMemory


@pytest.mark.asyncio
async def test_working_memory_write_read(working_store: WorkingMemory) -> None:
    await working_store.write("key", {"calc": 42})
    entry = await working_store.read("key")
    assert entry is not None
    assert entry.value["calc"] == 42


@pytest.mark.asyncio
async def test_working_memory_reasoning(working_store: WorkingMemory) -> None:
    key = await working_store.store_reasoning("agent-1", ["step 1", "step 2"])
    entry = await working_store.read(key)
    assert entry is not None
    assert len(entry.value) == 2


@pytest.mark.asyncio
async def test_working_memory_tool_output(working_store: WorkingMemory) -> None:
    key = await working_store.store_tool_output("agent-1", "forecast_tool", {"temp": 30})
    entry = await working_store.read(key)
    assert entry is not None
    assert entry.metadata["tool_name"] == "forecast_tool"


@pytest.mark.asyncio
async def test_working_memory_agent_scope(working_store: WorkingMemory) -> None:
    await working_store.store_observation("agent-1", "rain detected")
    await working_store.store_observation("agent-2", "wind detected")
    scope = await working_store.get_agent_scope("agent-1")
    assert len(scope) == 1


@pytest.mark.asyncio
async def test_working_memory_expiry(working_store: WorkingMemory) -> None:
    await working_store.write("exp", "val", ttl_seconds=1)
    import asyncio
    await asyncio.sleep(1.1)
    await working_store.purge_expired()
    assert await working_store.read("exp") is None


@pytest.mark.asyncio
async def test_working_memory_clear_agent(working_store: WorkingMemory) -> None:
    await working_store.store_calculation("agent-1", {"x": 1})
    count = await working_store.clear("agent-1")
    assert count >= 1
