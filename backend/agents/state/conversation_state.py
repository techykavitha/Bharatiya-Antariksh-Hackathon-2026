"""Conversation state models for multi-turn agent interactions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.utils.constants import MAX_CONVERSATION_HISTORY


class ConversationTurn(BaseModel):
    """A single turn in a multi-turn conversation."""

    turn_id: str = Field(default_factory=lambda: str(uuid4()))
    role: str = Field(..., description="speaker role: user, assistant, system, or agent")
    content: str
    agent_id: str | None = Field(default=None, description="Agent that produced this turn")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActiveUser(BaseModel):
    """Currently authenticated or contextualized user."""

    user_id: str
    display_name: str | None = None
    roles: list[str] = Field(default_factory=list)
    session_id: str | None = None
    preferences: dict[str, Any] = Field(default_factory=dict)


class ConversationState(BaseModel):
    """
    Multi-turn conversation context shared across agents.

    Maintains ordered history, active user identity, and session metadata.
    """

    conversation_id: str = Field(default_factory=lambda: str(uuid4()))
    turns: list[ConversationTurn] = Field(default_factory=list)
    active_user: ActiveUser | None = None
    language: str = Field(default="en")
    metadata: dict[str, Any] = Field(default_factory=dict)

    def append_turn(self, turn: ConversationTurn) -> None:
        """Append a turn and enforce the maximum history limit."""
        self.turns.append(turn)
        if len(self.turns) > MAX_CONVERSATION_HISTORY:
            self.turns = self.turns[-MAX_CONVERSATION_HISTORY:]

    def last_user_message(self) -> str | None:
        """Return the content of the most recent user turn, if any."""
        for turn in reversed(self.turns):
            if turn.role == "user":
                return turn.content
        return None

    @property
    def message_count(self) -> int:
        """Return the total number of conversation turns."""
        return len(self.turns)
