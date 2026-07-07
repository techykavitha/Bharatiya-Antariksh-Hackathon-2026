"""Conversation memory for chat history and agent interaction records."""

from __future__ import annotations

from typing import Any

from backend.agents.memory.interfaces import MemoryEntry
from backend.agents.memory.redis_memory import RedisMemoryStore
from backend.agents.memory.serialization import pydantic_to_dict
from backend.agents.state.conversation_state import ConversationState, ConversationTurn
from backend.utils.constants import MAX_CONVERSATION_HISTORY


class ConversationMemory:
    """
    Conversation-scoped memory for chat history, reasoning references,
    agent responses, and simulation summaries.
    """

    HISTORY_KEY = "chat_history"
    REASONING_REFS_KEY = "reasoning_refs"
    AGENT_RESPONSES_KEY = "agent_responses"
    SIMULATION_SUMMARIES_KEY = "simulation_summaries"

    def __init__(self, redis: RedisMemoryStore) -> None:
        self._redis = redis

    async def append_turn(self, session_id: str, turn: ConversationTurn) -> None:
        """Append a conversation turn to the session history."""
        state = await self.get_conversation_state(session_id)
        state.append_turn(turn)
        await self.save_conversation_state(session_id, state)

    async def save_conversation_state(self, session_id: str, state: ConversationState) -> None:
        await self._redis.write(
            self.HISTORY_KEY,
            pydantic_to_dict(state),
            session_id=session_id,
        )

    async def get_conversation_state(self, session_id: str) -> ConversationState:
        entry = await self._redis.read(self.HISTORY_KEY, session_id=session_id)
        if entry is None:
            return ConversationState()
        data = entry.value
        if isinstance(data, dict):
            return ConversationState.model_validate(data)
        return ConversationState()

    async def get_history(self, session_id: str, *, limit: int = MAX_CONVERSATION_HISTORY) -> list[ConversationTurn]:
        state = await self.get_conversation_state(session_id)
        return state.turns[-limit:]

    async def add_reasoning_reference(
        self,
        session_id: str,
        agent_id: str,
        reasoning_key: str,
        *,
        summary: str | None = None,
    ) -> None:
        refs = await self._get_list(self.REASONING_REFS_KEY, session_id)
        refs.append({
            "agent_id": agent_id,
            "reasoning_key": reasoning_key,
            "summary": summary,
        })
        await self._redis.write(self.REASONING_REFS_KEY, refs, session_id=session_id)

    async def get_reasoning_references(self, session_id: str) -> list[dict[str, Any]]:
        return await self._get_list(self.REASONING_REFS_KEY, session_id)

    async def add_agent_response(
        self,
        session_id: str,
        agent_id: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        responses = await self._get_list(self.AGENT_RESPONSES_KEY, session_id)
        responses.append({
            "agent_id": agent_id,
            "content": content,
            "metadata": metadata or {},
        })
        await self._redis.write(self.AGENT_RESPONSES_KEY, responses[-MAX_CONVERSATION_HISTORY:], session_id=session_id)

    async def get_agent_responses(self, session_id: str) -> list[dict[str, Any]]:
        return await self._get_list(self.AGENT_RESPONSES_KEY, session_id)

    async def add_simulation_summary(
        self,
        session_id: str,
        simulation_id: str,
        summary: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        summaries = await self._get_list(self.SIMULATION_SUMMARIES_KEY, session_id)
        summaries.append({
            "simulation_id": simulation_id,
            "summary": summary,
            "metadata": metadata or {},
        })
        await self._redis.write(self.SIMULATION_SUMMARIES_KEY, summaries, session_id=session_id)

    async def get_simulation_summaries(self, session_id: str) -> list[dict[str, Any]]:
        return await self._get_list(self.SIMULATION_SUMMARIES_KEY, session_id)

    async def search(self, session_id: str, query: str, *, limit: int = 10) -> list[MemoryEntry]:
        return await self._redis.search(query, limit=limit, session_id=session_id)

    async def clear(self, session_id: str) -> int:
        keys = await self._redis.get_session_keys(session_id)
        count = 0
        for full_key in keys:
            short_key = self._redis._extract_session_key(full_key, session_id)
            if await self._redis.delete(short_key, session_id=session_id):
                count += 1
        return count

    async def _get_list(self, key: str, session_id: str) -> list[Any]:
        entry = await self._redis.read(key, session_id=session_id)
        if entry is None or not isinstance(entry.value, list):
            return []
        return list(entry.value)
