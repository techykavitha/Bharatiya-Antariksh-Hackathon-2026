"""Execution engine and external service interfaces for specialized agents."""

from __future__ import annotations

import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import AgentResponse
from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.specialized.agent_reflection import ReflectionResult
from backend.config.logger import get_logger
from backend.utils.constants import DEFAULT_AGENT_TIMEOUT_SECONDS, MAX_AGENT_RETRIES
from backend.utils.enums import AgentStatus

logger = get_logger(__name__)


class AgentExecutionMode(StrEnum):
    """Execution topology for specialized agent sub-tasks."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


class ExecutionTaskType(StrEnum):
    """Types of tasks executed by the specialized agent engine."""

    REASONING = "reasoning"
    TOOL = "tool"
    REFLECTION = "reflection"
    DELEGATION = "delegation"
    RL = "rl"
    VALIDATION = "validation"


class AgentExecutionStep(BaseModel):
    """Single step in a specialized agent execution plan."""

    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_type: ExecutionTaskType
    name: str
    dependencies: list[str] = Field(default_factory=list)
    parallel_group: str | None = None
    condition: str | None = None
    max_retries: int = Field(default=MAX_AGENT_RETRIES, ge=0)
    timeout_seconds: int = Field(default=DEFAULT_AGENT_TIMEOUT_SECONDS, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentExecutionPlan(BaseModel):
    """Execution plan for a specialized agent sub-pipeline."""

    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    steps: list[AgentExecutionStep] = Field(default_factory=list)
    execution_mode: AgentExecutionMode = AgentExecutionMode.SEQUENTIAL
    metadata: dict[str, Any] = Field(default_factory=dict)


class StepExecutionOutcome(BaseModel):
    """Outcome of executing a single plan step."""

    step_id: str
    task_type: ExecutionTaskType
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    retry_attempts: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentExecutionOutcome(BaseModel):
    """Aggregated outcome of a specialized execution plan."""

    plan_id: str
    agent_id: str
    step_outcomes: list[StepExecutionOutcome] = Field(default_factory=list)
    status: AgentStatus = AgentStatus.COMPLETED
    cancelled: bool = False
    total_duration_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class AgentExecutionPolicy:
    """Retry, timeout, and cancellation policy."""

    max_retries: int = MAX_AGENT_RETRIES
    retry_delay_seconds: float = 0.5
    default_timeout_seconds: int = DEFAULT_AGENT_TIMEOUT_SECONDS
    allow_partial_completion: bool = True
    enable_reflection_between_steps: bool = False


@runtime_checkable
class SpecializedAgentHandler(Protocol):
    """Protocol for specialized agents registered in the specialized registry."""

    @property
    def agent_id(self) -> str: ...

    async def invoke(self, request: AgentRequest) -> AgentResponse: ...

    async def health_check(self) -> bool: ...


class AgentCommunicationInterface(ABC):
    """
    Abstract interface for inter-agent communication.

    Implementation deferred to the agent mesh / messaging subsystem.
    """

    @abstractmethod
    async def call_agent(
        self,
        agent_id: str,
        request: AgentRequest,
        *,
        timeout_seconds: float | None = None,
    ) -> AgentResponse:
        """Invoke a single peer agent and await its response."""

    @abstractmethod
    async def broadcast(
        self,
        agent_ids: list[str],
        request: AgentRequest,
    ) -> list[AgentResponse]:
        """Send the same request to multiple agents concurrently."""

    @abstractmethod
    async def wait_for_response(
        self,
        correlation_id: str,
        *,
        timeout_seconds: float = DEFAULT_AGENT_TIMEOUT_SECONDS,
    ) -> AgentResponse:
        """Await an asynchronous response identified by correlation ID."""


class SpecializedRLEngineInterface(ABC):
    """
    Abstract RL interface for specialized agents.

    Implementation deferred to the RL subsystem.
    """

    @abstractmethod
    async def request_policy(
        self,
        scenario_id: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Request an optimal policy for the given scenario."""

    @abstractmethod
    async def evaluate_action(
        self,
        action: dict[str, Any],
        *,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate a single action against the current state."""

    @abstractmethod
    async def rank_actions(
        self,
        actions: list[dict[str, Any]],
        *,
        criteria: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Rank actions by expected utility."""


class AgentExecutionEngine:
    """
    Executes specialized agent sub-plans with sequential, parallel, and
    conditional topologies, including reflection hooks, retry, and cancellation.
    """

    def __init__(
        self,
        *,
        agent_id: str,
        policy: AgentExecutionPolicy | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._policy = policy or AgentExecutionPolicy()
        self._cancelled = False

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True

    async def execute(
        self,
        plan: AgentExecutionPlan,
        context: AgentContext,
        handlers: dict[ExecutionTaskType, Any],
        *,
        reasoning: ReasoningResult | None = None,
        reflection: ReflectionResult | None = None,
    ) -> AgentExecutionOutcome:
        if self._cancelled or context.cancelled:
            return AgentExecutionOutcome(
                plan_id=plan.plan_id,
                agent_id=plan.agent_id,
                status=AgentStatus.FAILED,
                cancelled=True,
                metadata={"error": "Execution cancelled"},
            )

        start = time.perf_counter()
        if plan.execution_mode == AgentExecutionMode.PARALLEL:
            outcomes = await self._execute_parallel(plan, context, handlers)
        elif plan.execution_mode == AgentExecutionMode.CONDITIONAL:
            outcomes = await self._execute_conditional(plan, context, handlers)
        else:
            outcomes = await self._execute_sequential(
                plan,
                context,
                handlers,
                reasoning=reasoning,
                reflection=reflection,
            )

        elapsed = (time.perf_counter() - start) * 1000
        failed = [o for o in outcomes if not o.success]
        partial = (
            bool(failed)
            and self._policy.allow_partial_completion
            and len(failed) < len(outcomes)
        )
        status = AgentStatus.COMPLETED if not failed or partial else AgentStatus.FAILED

        return AgentExecutionOutcome(
            plan_id=plan.plan_id,
            agent_id=plan.agent_id,
            step_outcomes=outcomes,
            status=status,
            cancelled=self._cancelled,
            total_duration_ms=elapsed,
            metadata={"failed_count": len(failed)},
        )

    async def _execute_sequential(
        self,
        plan: AgentExecutionPlan,
        context: AgentContext,
        handlers: dict[ExecutionTaskType, Any],
        *,
        reasoning: ReasoningResult | None,
        reflection: ReflectionResult | None,
    ) -> list[StepExecutionOutcome]:
        outcomes: list[StepExecutionOutcome] = []
        completed: set[str] = set()

        for step in plan.steps:
            if self._cancelled or context.cancelled:
                break
            if not all(dep in completed for dep in step.dependencies):
                outcomes.append(
                    StepExecutionOutcome(
                        step_id=step.step_id,
                        task_type=step.task_type,
                        success=False,
                        error="Unmet dependencies",
                    ),
                )
                continue

            outcome = await self._execute_step(step, context, handlers)
            outcomes.append(outcome)
            if outcome.success:
                completed.add(step.step_id)

            if (
                self._policy.enable_reflection_between_steps
                and step.task_type == ExecutionTaskType.TOOL
                and reflection is not None
                and reflection.should_retry_reasoning
            ):
                reflect_handler = handlers.get(ExecutionTaskType.REFLECTION)
                if reflect_handler:
                    await reflect_handler(context, reasoning, reflection)

        return outcomes

    async def _execute_parallel(
        self,
        plan: AgentExecutionPlan,
        context: AgentContext,
        handlers: dict[ExecutionTaskType, Any],
    ) -> list[StepExecutionOutcome]:
        groups: dict[str | None, list[AgentExecutionStep]] = {}
        for step in plan.steps:
            groups.setdefault(step.parallel_group, []).append(step)

        all_outcomes: list[StepExecutionOutcome] = []
        for group_steps in groups.values():
            tasks = [
                self._execute_step(step, context, handlers)
                for step in group_steps
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for step, result in zip(group_steps, results, strict=True):
                if isinstance(result, Exception):
                    all_outcomes.append(
                        StepExecutionOutcome(
                            step_id=step.step_id,
                            task_type=step.task_type,
                            success=False,
                            error=str(result),
                        ),
                    )
                else:
                    all_outcomes.append(result)
        return all_outcomes

    async def _execute_conditional(
        self,
        plan: AgentExecutionPlan,
        context: AgentContext,
        handlers: dict[ExecutionTaskType, Any],
    ) -> list[StepExecutionOutcome]:
        outcomes: list[StepExecutionOutcome] = []
        conditions: dict[str, bool] = dict(plan.metadata.get("conditions", {}))

        for step in plan.steps:
            if step.condition and not conditions.get(step.condition, True):
                outcomes.append(
                    StepExecutionOutcome(
                        step_id=step.step_id,
                        task_type=step.task_type,
                        success=True,
                        error="Condition not met — skipped",
                        metadata={"skipped": True},
                    ),
                )
                continue
            outcome = await self._execute_step(step, context, handlers)
            outcomes.append(outcome)
            if step.condition:
                conditions[step.condition] = outcome.success
        return outcomes

    async def _execute_step(
        self,
        step: AgentExecutionStep,
        context: AgentContext,
        handlers: dict[ExecutionTaskType, Any],
    ) -> StepExecutionOutcome:
        handler = handlers.get(step.task_type)
        if handler is None:
            return StepExecutionOutcome(
                step_id=step.step_id,
                task_type=step.task_type,
                success=False,
                error=f"No handler for task type '{step.task_type.value}'",
            )

        start = time.perf_counter()
        attempt = 0
        last_error: str | None = None

        while attempt <= min(step.max_retries, self._policy.max_retries):
            attempt += 1
            try:
                output = await asyncio.wait_for(
                    handler(context, step),
                    timeout=step.timeout_seconds or self._policy.default_timeout_seconds,
                )
                elapsed = (time.perf_counter() - start) * 1000
                return StepExecutionOutcome(
                    step_id=step.step_id,
                    task_type=step.task_type,
                    success=True,
                    output=output,
                    duration_ms=elapsed,
                    retry_attempts=attempt - 1,
                )
            except Exception as exc:
                last_error = str(exc)
                if attempt <= min(step.max_retries, self._policy.max_retries):
                    delay = self._policy.retry_delay_seconds * (2 ** max(attempt - 1, 0))
                    await asyncio.sleep(delay)

        elapsed = (time.perf_counter() - start) * 1000
        return StepExecutionOutcome(
            step_id=step.step_id,
            task_type=step.task_type,
            success=False,
            error=last_error or "Max retries exceeded",
            duration_ms=elapsed,
            retry_attempts=attempt,
        )
