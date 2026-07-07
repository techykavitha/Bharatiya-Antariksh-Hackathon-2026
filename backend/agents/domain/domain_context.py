"""Domain-layer context models and type definitions."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.agents.schemas.response import AgentResponse
from backend.utils.enums import AgentStatus


class DomainType(StrEnum):
    """Top-level domain supervisor classification."""

    ENVIRONMENTAL = "environmental"
    INFRASTRUCTURE = "infrastructure"
    EMERGENCY = "emergency"


class DomainExecutionMode(StrEnum):
    """Execution topology within a domain supervisor."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


class DomainAgentStatus(StrEnum):
    """Lifecycle status of a specialized agent under a domain supervisor."""

    REGISTERED = "registered"
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    UNHEALTHY = "unhealthy"
    REMOVED = "removed"


class DomainTask(BaseModel):
    """A task category supported by a domain supervisor."""

    task_id: str
    name: str
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    preferred_agents: list[str] = Field(default_factory=list)
    execution_mode: DomainExecutionMode = DomainExecutionMode.SEQUENTIAL


class DomainAgentRegistration(BaseModel):
    """Metadata for a specialized agent registered under a domain supervisor."""

    agent_id: str
    name: str
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    supported_tasks: list[str] = Field(default_factory=list)
    status: DomainAgentStatus = DomainAgentStatus.REGISTERED
    healthy: bool = True
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_invoked_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DomainSelectionResult(BaseModel):
    """Output of agent selection for a domain request."""

    domain: DomainType
    task_id: str | None = None
    selected_agents: list[str] = Field(default_factory=list)
    execution_mode: DomainExecutionMode = DomainExecutionMode.SEQUENTIAL
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_keywords: list[str] = Field(default_factory=list)


class DomainExecutionStep(BaseModel):
    """Single step in a domain-level execution plan."""

    step_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    action: str = "invoke"
    dependencies: list[str] = Field(default_factory=list)
    parallel_group: str | None = None
    condition: str | None = None
    fallback_agent: str | None = None
    max_retries: int = Field(default=3, ge=0)
    timeout_seconds: int = Field(default=120, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DomainExecutionPlan(BaseModel):
    """Execution plan for a domain supervisor invocation."""

    plan_id: str = Field(default_factory=lambda: str(uuid4()))
    domain: DomainType
    query: str
    task_id: str | None = None
    steps: list[DomainExecutionStep] = Field(default_factory=list)
    execution_mode: DomainExecutionMode = DomainExecutionMode.SEQUENTIAL
    metadata: dict[str, Any] = Field(default_factory=dict)


class DomainAgentResult(BaseModel):
    """Result of invoking a single specialized agent."""

    step_id: str
    agent_id: str
    success: bool
    response: AgentResponse | None = None
    error: str | None = None
    duration_ms: float = 0.0
    retry_attempts: int = 0
    used_fallback: bool = False
    memory_references: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DomainExecutionResult(BaseModel):
    """Aggregated result of a domain supervisor execution."""

    plan_id: str
    domain: DomainType
    agent_results: list[DomainAgentResult] = Field(default_factory=list)
    status: AgentStatus = AgentStatus.COMPLETED
    partial_completion: bool = False
    total_duration_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def completed_agents(self) -> list[str]:
        return [r.agent_id for r in self.agent_results if r.success]

    @property
    def failed_agents(self) -> list[str]:
        return [r.agent_id for r in self.agent_results if not r.success]


class DomainMergedResult(BaseModel):
    """Merged output from domain agent invocations."""

    domain: DomainType
    content: str
    structured_output: dict[str, Any] = Field(default_factory=dict)
    agent_responses: list[AgentResponse] = Field(default_factory=list)
    memory_references: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DomainExecutionMetrics(BaseModel):
    """Execution metrics tracked in WorkflowState metadata."""

    domain: DomainType
    active_domain: str
    completed_agents: list[str] = Field(default_factory=list)
    failed_agents: list[str] = Field(default_factory=list)
    total_agents_invoked: int = 0
    parallel_batches: int = 0
    retry_count: int = 0
    failure_count: int = 0
    duration_ms: float = 0.0
    memory_writes: int = 0


class DomainHealthReport(BaseModel):
    """Health status for a domain supervisor and its agents."""

    supervisor_id: str
    domain: DomainType
    healthy: bool
    agent_health: dict[str, bool] = Field(default_factory=dict)
    registered_agents: int = 0
    ready_agents: int = 0
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
