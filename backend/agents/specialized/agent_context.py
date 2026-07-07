"""Execution context models for specialized climate agents."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.agents.memory.memory_types import MemoryEntry, RankedMemory
from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import ToolOutputRecord
from backend.agents.state.climate_state import ClimateState, ForecastReference
from backend.agents.state.conversation_state import ActiveUser, ConversationState
from backend.agents.tools.abstract_tool import ToolResult
from backend.utils.enums import AgentStatus, ScenarioType


class ContextPhase(StrEnum):
    """Lifecycle phase of an agent execution context."""

    CREATED = "created"
    PREPROCESSING = "preprocessing"
    RETRIEVING = "retrieving"
    REASONING = "reasoning"
    REFLECTING = "reflecting"
    VALIDATING = "validating"
    EXECUTING_TOOLS = "executing_tools"
    DELEGATING = "delegating"
    GENERATING_REPORT = "generating_report"
    PERSISTING = "persisting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ForecastContext(BaseModel):
    """Forecast artifacts available to a specialized agent."""

    forecast_id: str | None = None
    model_name: str | None = None
    horizon_hours: int | None = None
    references: list[ForecastReference] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SimulationContext(BaseModel):
    """Active or historical simulation context."""

    simulation_id: str | None = None
    name: str | None = None
    status: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScenarioContext(BaseModel):
    """Scenario branch metadata for what-if and planning workflows."""

    scenario_id: str | None = None
    scenario_type: ScenarioType | None = None
    label: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UserContext(BaseModel):
    """Resolved user/session identity for the invocation."""

    user_id: str | None = None
    session_id: str | None = None
    active_user: ActiveUser | None = None
    preferences: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryContext(BaseModel):
    """Memory artifacts retrieved for the current invocation."""

    entries: list[MemoryEntry] = Field(default_factory=list)
    ranked_results: list[RankedMemory] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RLOutputContext(BaseModel):
    """RL engine outputs attached to the agent context."""

    policy: dict[str, Any] = Field(default_factory=dict)
    evaluated_actions: dict[str, Any] = Field(default_factory=dict)
    ranked_actions: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentDelegationResult(BaseModel):
    """Result of invoking another specialized agent."""

    agent_id: str
    success: bool
    content: str = ""
    structured_output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentReport(BaseModel):
    """
    Standardized report object returned by specialized agents.

  Sections map to enterprise reporting requirements for auditability.
    """

    report_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    request_id: str
    summary: str = ""
    reasoning: list[str] = Field(default_factory=list)
    risk: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    recommendations: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    tool_outputs: list[ToolOutputRecord] = Field(default_factory=list)
    structured_output: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_response_content(self) -> str:
        """Render the primary natural-language response from the report."""
        if self.summary:
            return self.summary
        if self.recommendations:
            return self.recommendations[0]
        return "Analysis completed."


class AgentContext(BaseModel):
    """
    Unified execution context for specialized agent invocations.

    Aggregates workflow, climate, memory, tool, RL, and digital twin state
    for the full Observe → Think → Act → Reflect → Verify pipeline.
    """

    context_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    request: AgentRequest
    phase: ContextPhase = ContextPhase.CREATED
    status: AgentStatus = AgentStatus.IDLE

    workflow_state: dict[str, Any] | None = None
    climate_state: ClimateState | None = None
    forecast: ForecastContext = Field(default_factory=ForecastContext)
    simulation: SimulationContext = Field(default_factory=SimulationContext)
    scenario: ScenarioContext = Field(default_factory=ScenarioContext)
    user: UserContext = Field(default_factory=UserContext)
    conversation: ConversationState | None = None
    memory: MemoryContext = Field(default_factory=MemoryContext)
    tool_outputs: list[ToolResult] = Field(default_factory=list)
    rl_outputs: RLOutputContext = Field(default_factory=RLOutputContext)
    digital_twin_state: dict[str, Any] = Field(default_factory=dict)
    delegation_results: list[AgentDelegationResult] = Field(default_factory=list)
    reasoning_trace: list[str] = Field(default_factory=list)
    reflection_notes: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    cancelled: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}

    @property
    def query(self) -> str:
        return self.request.query

    @property
    def request_id(self) -> str:
        return self.request.request_id

    def mark_phase(self, phase: ContextPhase) -> None:
        self.phase = phase

    def add_reasoning(self, step: str) -> None:
        self.reasoning_trace.append(step)

    def add_reflection(self, note: str) -> None:
        self.reflection_notes.append(note)

    def add_validation_error(self, error: str) -> None:
        self.validation_errors.append(error)
