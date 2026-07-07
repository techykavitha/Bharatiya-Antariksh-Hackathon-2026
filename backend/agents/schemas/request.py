"""Request schemas for agent invocations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.agents.state.climate_state import ClimateState
from backend.agents.state.conversation_state import ActiveUser, ConversationState
from backend.utils.enums import AgentRole, ScenarioType


class AgentRequest(BaseModel):
    """
    Standardized input payload for any agent invocation.

    Encapsulates the user query, session context, climate state,
    and optional routing hints for the multi-agent hierarchy.
    """

    request_id: str = Field(default_factory=lambda: str(uuid4()))
    query: str = Field(..., min_length=1, description="Primary user or system query")
    conversation: ConversationState | None = None
    active_user: ActiveUser | None = None
    climate_state: ClimateState | None = None
    current_scenario: str | None = None
    scenario_type: ScenarioType | None = None
    target_agent: str | None = Field(
        default=None,
        description="Optional explicit agent routing hint",
    )
    caller_agent_id: str | None = Field(
        default=None,
        description="ID of the agent that dispatched this request",
    )
    caller_role: AgentRole | None = None
    tool_names: list[str] = Field(
        default_factory=list,
        description="Subset of tools the agent may use for this request",
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional opaque context passed between agents",
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def has_climate_context(self) -> bool:
        """Return True when climate state is attached to this request."""
        return self.climate_state is not None
