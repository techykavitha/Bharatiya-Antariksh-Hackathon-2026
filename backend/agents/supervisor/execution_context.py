"""Execution context models and external service interfaces for the Climate Supervisor."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import AgentResponse
from backend.agents.state.workflow_state import WorkflowState
from backend.utils.enums import AgentStatus


class SupervisorIntent(StrEnum):
    """Canonical user intent categories routed by the Climate Supervisor."""

    NOWCAST = "nowcast"
    FORECAST = "forecast"
    WHAT_IF = "what_if"
    ALERT = "alert"
    ANALYTICS = "analytics"
    SIMULATION = "simulation"
    POLICY = "policy"
    REPORT = "report"
    GENERAL_QA = "general_qa"


class ExecutionMode(StrEnum):
    """Workflow execution topology."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


class StepStatus(StrEnum):
    """Status of an individual plan step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ExecutionPlanStep(BaseModel):
    """Atomic step in a supervisor execution plan."""

    step_id: str = Field(default_factory=lambda: str(uuid4()))
    supervisor_id: str
    action: str
    description: str = ""
    dependencies: list[str] = Field(default_factory=list)
    parallel_group: str | None = None
    condition: str | None = None
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    fallback_supervisor: str | None = None
    timeout_seconds: int = Field(default=120, ge=1)
    requires_rl: bool = False
    requires_digital_twin: bool = False
    tool_names: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionPlan(BaseModel):
    """Complete execution plan produced by the workflow planner."""

    plan_id: str = Field(default_factory=lambda: str(uuid4()))
    intent: SupervisorIntent
    query: str
    steps: list[ExecutionPlanStep] = Field(default_factory=list)
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntentClassification(BaseModel):
    """Result of intent classification."""

    intent: SupervisorIntent
    confidence: float = Field(ge=0.0, le=1.0)
    matched_signals: list[str] = Field(default_factory=list)
    raw_query: str


class StepExecutionResult(BaseModel):
    """Outcome of executing a single plan step."""

    step_id: str
    supervisor_id: str
    status: StepStatus
    response: AgentResponse | None = None
    error: str | None = None
    duration_ms: float = 0.0
    retry_attempts: int = 0
    used_fallback: bool = False
    memory_references: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    """Aggregated outcome of a full plan execution."""

    plan_id: str
    step_results: list[StepExecutionResult] = Field(default_factory=list)
    status: AgentStatus = AgentStatus.COMPLETED
    partial_completion: bool = False
    total_duration_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.status == AgentStatus.COMPLETED and not self.partial_completion

    @property
    def failed_steps(self) -> list[StepExecutionResult]:
        return [r for r in self.step_results if r.status == StepStatus.FAILED]


class MergedSupervisorResult(BaseModel):
    """Merged output from multiple domain supervisor invocations."""

    content: str
    structured_output: dict[str, Any] = Field(default_factory=dict)
    agent_responses: list[AgentResponse] = Field(default_factory=list)
    memory_references: list[str] = Field(default_factory=list)
    knowledge_graph_references: list[str] = Field(default_factory=list)
    forecast_references: list[str] = Field(default_factory=list)
    rl_outputs: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SupervisorResponse(BaseModel):
    """Unified response returned by the Climate Supervisor to the caller."""

    response_id: str = Field(default_factory=lambda: str(uuid4()))
    request_id: str
    content: str
    status: AgentStatus = AgentStatus.COMPLETED
    intent: SupervisorIntent
    plan_id: str
    execution_result: ExecutionResult
    merged_result: MergedSupervisorResult
    metrics: dict[str, Any] = Field(default_factory=dict)
    memory_references: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None


class SupervisorExecutionContext(BaseModel):
    """Runtime context propagated through supervisor execution."""

    request_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str | None = None
    query: str = ""
    intent: SupervisorIntent | None = None
    plan: ExecutionPlan | None = None
    workflow_state: dict[str, Any] = Field(default_factory=dict)
    agent_request: AgentRequest | None = None
    step_outputs: dict[str, Any] = Field(default_factory=dict)
    cancelled: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


class WorkflowMetrics(BaseModel):
    """Exposed supervisor execution metrics."""

    execution_duration_ms: float = 0.0
    memory_retrieval_count: int = 0
    supervisor_count: int = 0
    parallel_task_count: int = 0
    failure_count: int = 0
    retry_count: int = 0
    tool_usage_count: int = 0
    rl_usage_count: int = 0
    active_supervisors: list[str] = Field(default_factory=list)
    success_rate: float = Field(default=1.0, ge=0.0, le=1.0)


@runtime_checkable
class DomainSupervisorHandler(Protocol):
    """Protocol for domain supervisor implementations registered at runtime."""

    @property
    def supervisor_id(self) -> str: ...

    async def invoke(self, request: AgentRequest) -> AgentResponse: ...

    async def health_check(self) -> bool: ...


class RLEngineInterface(ABC):
    """
    Abstract interface for RL engine integration.

    Implementation deferred to the RL subsystem.
    """

    @abstractmethod
    async def request_policy(
        self,
        scenario_id: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Request an RL policy for the given scenario."""

    @abstractmethod
    async def evaluate_actions(
        self,
        actions: list[dict[str, Any]],
        *,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate candidate actions against the current state."""

    @abstractmethod
    async def rank_actions(
        self,
        actions: list[dict[str, Any]],
        *,
        criteria: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Rank actions by expected utility."""


class DigitalTwinInterface(ABC):
    """
    Abstract interface for digital twin integration.

    Implementation deferred to the digital twin subsystem.
    """

    @abstractmethod
    async def get_state(self, twin_id: str) -> dict[str, Any]:
        """Retrieve the current digital twin state."""

    @abstractmethod
    async def update_state(self, twin_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Apply updates to the digital twin state."""

    @abstractmethod
    async def create_scenario(self, twin_id: str, scenario: dict[str, Any]) -> str:
        """Create a new scenario branch on the digital twin."""

    @abstractmethod
    async def compare_scenarios(
        self,
        twin_id: str,
        scenario_a: str,
        scenario_b: str,
    ) -> dict[str, Any]:
        """Compare two scenario branches."""
