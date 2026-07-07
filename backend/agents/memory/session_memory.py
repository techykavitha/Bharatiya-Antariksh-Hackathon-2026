"""Session memory for user context, preferences, and active workspace state."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.agents.memory.interfaces import MemoryEntry
from backend.agents.memory.redis_memory import RedisMemoryStore
from backend.agents.memory.serialization import pydantic_to_dict
from backend.agents.state.conversation_state import ActiveUser, ConversationState


class SessionRecord(BaseModel):
    """Complete user session state."""

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    user: ActiveUser | None = None
    preferences: dict[str, Any] = Field(default_factory=dict)
    conversation_id: str | None = None
    active_dashboard: dict[str, Any] = Field(default_factory=dict)
    active_simulation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionMemory:
    """
    Session-scoped memory for user identity, preferences, active dashboard,
    current conversation, and active simulation tracking.
    """

    SESSION_KEY = "session_record"
    PREFERENCES_KEY = "preferences"
    DASHBOARD_KEY = "active_dashboard"
    ACTIVE_SIMULATION_KEY = "active_simulation"
    CONVERSATION_KEY = "active_conversation"

    def __init__(self, redis: RedisMemoryStore, *, session_ttl_seconds: int = 86_400) -> None:
        self._redis = redis
        self._session_ttl = session_ttl_seconds

    async def create_session(self, user: ActiveUser | None = None) -> SessionRecord:
        session = SessionRecord(user=user)
        if user and user.session_id:
            session.session_id = user.session_id
        await self.save_session(session)
        return session

    async def save_session(self, session: SessionRecord) -> None:
        session.last_accessed_at = datetime.now(timezone.utc)
        await self._redis.write(
            self.SESSION_KEY,
            pydantic_to_dict(session),
            session_id=session.session_id,
            ttl_seconds=self._session_ttl,
        )

    async def get_session(self, session_id: str) -> SessionRecord | None:
        entry = await self._redis.read(self.SESSION_KEY, session_id=session_id)
        if entry is None:
            return None
        return SessionRecord.model_validate(entry.value)

    async def update_preferences(self, session_id: str, preferences: dict[str, Any]) -> None:
        session = await self.get_session(session_id)
        if session is None:
            session = SessionRecord(session_id=session_id)
        session.preferences.update(preferences)
        await self.save_session(session)
        await self._redis.write(
            self.PREFERENCES_KEY,
            session.preferences,
            session_id=session_id,
            ttl_seconds=self._session_ttl,
        )

    async def get_preferences(self, session_id: str) -> dict[str, Any]:
        entry = await self._redis.read(self.PREFERENCES_KEY, session_id=session_id)
        if entry and isinstance(entry.value, dict):
            return entry.value
        session = await self.get_session(session_id)
        return session.preferences if session else {}

    async def set_active_dashboard(self, session_id: str, dashboard: dict[str, Any]) -> None:
        await self._redis.write(
            self.DASHBOARD_KEY,
            dashboard,
            session_id=session_id,
            ttl_seconds=self._session_ttl,
        )
        session = await self.get_session(session_id)
        if session:
            session.active_dashboard = dashboard
            await self.save_session(session)

    async def get_active_dashboard(self, session_id: str) -> dict[str, Any]:
        entry = await self._redis.read(self.DASHBOARD_KEY, session_id=session_id)
        return entry.value if entry and isinstance(entry.value, dict) else {}

    async def set_active_simulation(self, session_id: str, simulation_id: str) -> None:
        await self._redis.write(
            self.ACTIVE_SIMULATION_KEY,
            {"simulation_id": simulation_id},
            session_id=session_id,
            ttl_seconds=self._session_ttl,
        )
        session = await self.get_session(session_id)
        if session:
            session.active_simulation_id = simulation_id
            await self.save_session(session)

    async def get_active_simulation(self, session_id: str) -> str | None:
        entry = await self._redis.read(self.ACTIVE_SIMULATION_KEY, session_id=session_id)
        if entry and isinstance(entry.value, dict):
            return entry.value.get("simulation_id")
        session = await self.get_session(session_id)
        return session.active_simulation_id if session else None

    async def set_active_conversation(self, session_id: str, conversation: ConversationState) -> None:
        await self._redis.write(
            self.CONVERSATION_KEY,
            pydantic_to_dict(conversation),
            session_id=session_id,
            ttl_seconds=self._session_ttl,
        )
        session = await self.get_session(session_id)
        if session:
            session.conversation_id = conversation.conversation_id
            await self.save_session(session)

    async def get_active_conversation(self, session_id: str) -> ConversationState | None:
        entry = await self._redis.read(self.CONVERSATION_KEY, session_id=session_id)
        if entry is None:
            return None
        return ConversationState.model_validate(entry.value)

    async def touch(self, session_id: str) -> None:
        session = await self.get_session(session_id)
        if session:
            await self.save_session(session)

    async def delete_session(self, session_id: str) -> bool:
        keys = await self._redis.get_session_keys(session_id)
        count = 0
        for full_key in keys:
            short_key = self._redis._extract_session_key(full_key, session_id)
            if await self._redis.delete(short_key, session_id=session_id):
                count += 1
        await self._redis.delete("__index__", session_id=session_id)
        return count > 0

    async def search(self, session_id: str, query: str, *, limit: int = 10) -> list[MemoryEntry]:
        return await self._redis.search(query, limit=limit, session_id=session_id)
