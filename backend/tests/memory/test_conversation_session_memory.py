"""Unit tests for conversation and session memory."""

import pytest

from backend.agents.memory.conversation_memory import ConversationMemory
from backend.agents.memory.redis_memory import RedisMemoryStore
from backend.agents.memory.session_memory import SessionMemory
from backend.agents.state.conversation_state import ActiveUser, ConversationTurn


@pytest.fixture
def conversation_memory(redis_store: RedisMemoryStore) -> ConversationMemory:
    return ConversationMemory(redis_store)


@pytest.fixture
def session_memory(redis_store: RedisMemoryStore) -> SessionMemory:
    return SessionMemory(redis_store)


@pytest.mark.asyncio
async def test_conversation_append_and_history(conversation_memory: ConversationMemory) -> None:
    turn = ConversationTurn(role="user", content="What is the flood risk in Chennai?")
    await conversation_memory.append_turn("sess-1", turn)
    history = await conversation_memory.get_history("sess-1")
    assert len(history) == 1
    assert history[0].content == "What is the flood risk in Chennai?"


@pytest.mark.asyncio
async def test_conversation_reasoning_refs(conversation_memory: ConversationMemory) -> None:
    await conversation_memory.add_reasoning_reference("sess-1", "agent-1", "reason-key-1", summary="Analyzed flood data")
    refs = await conversation_memory.get_reasoning_references("sess-1")
    assert len(refs) == 1
    assert refs[0]["reasoning_key"] == "reason-key-1"


@pytest.mark.asyncio
async def test_conversation_agent_responses(conversation_memory: ConversationMemory) -> None:
    await conversation_memory.add_agent_response("sess-1", "flood-agent", "Risk is moderate.")
    responses = await conversation_memory.get_agent_responses("sess-1")
    assert len(responses) == 1


@pytest.mark.asyncio
async def test_conversation_simulation_summary(conversation_memory: ConversationMemory) -> None:
    await conversation_memory.add_simulation_summary("sess-1", "sim-1", "Flood depth reached 2m.")
    summaries = await conversation_memory.get_simulation_summaries("sess-1")
    assert summaries[0]["simulation_id"] == "sim-1"


@pytest.mark.asyncio
async def test_session_create_and_preferences(session_memory: SessionMemory) -> None:
    user = ActiveUser(user_id="u1", display_name="Analyst")
    session = await session_memory.create_session(user)
    await session_memory.update_preferences(session.session_id, {"units": "metric"})
    prefs = await session_memory.get_preferences(session.session_id)
    assert prefs["units"] == "metric"


@pytest.mark.asyncio
async def test_session_dashboard_and_simulation(session_memory: SessionMemory) -> None:
    session = await session_memory.create_session()
    await session_memory.set_active_dashboard(session.session_id, {"view": "flood_map"})
    await session_memory.set_active_simulation(session.session_id, "sim-42")
    dashboard = await session_memory.get_active_dashboard(session.session_id)
    sim = await session_memory.get_active_simulation(session.session_id)
    assert dashboard["view"] == "flood_map"
    assert sim == "sim-42"


@pytest.mark.asyncio
async def test_session_delete(session_memory: SessionMemory) -> None:
    session = await session_memory.create_session()
    await session_memory.update_preferences(session.session_id, {"lang": "en"})
    assert await session_memory.delete_session(session.session_id) is True
    assert await session_memory.get_session(session.session_id) is None
