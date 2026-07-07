"""Async execution engine for domain supervisor agent orchestration."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import AgentResponse
from backend.agents.domain.domain_context import (
    DomainAgentResult,
    DomainExecutionMode,
    DomainExecutionPlan,
    DomainExecutionResult,
    DomainExecutionStep,
)
from backend.config.logger import get_logger
from backend.utils.constants import DEFAULT_AGENT_TIMEOUT_SECONDS, MAX_AGENT_RETRIES
from backend.utils.enums import AgentStatus

logger = get_logger(__name__)


@runtime_checkable
class DomainAgentHandler(Protocol):
    """Protocol for specialized agents managed by domain supervisors."""

    @property
    def agent_id(self) -> str: ...

    async def invoke(self, request: AgentRequest) -> AgentResponse: ...

    async def health_check(self) -> bool: ...


@dataclass(frozen=True)
class DomainExecutionPolicy:
    """Failure and retry policy for domain execution."""

    max_retries: int = MAX_AGENT_RETRIES
    retry_delay_seconds: float = 0.5
    enable_fallback: bool = True
    allow_partial_completion: bool = True
    default_timeout_seconds: int = DEFAULT_AGENT_TIMEOUT_SECONDS


class DomainExecutor:
    """
    Executes domain plans with sequential, parallel, and conditional
    topologies, including retry and fallback support.
    """

    def __init__(
        self,
        *,
        resolve_agent: Any,
        policy: DomainExecutionPolicy | None = None,
    ) -> None:
        self._resolve_agent = resolve_agent
        self._policy = policy or DomainExecutionPolicy()

    async def execute(
        self,
        plan: DomainExecutionPlan,
        request: AgentRequest,
        *,
        cancelled: bool = False,
    ) -> DomainExecutionResult:
        """Execute a domain plan using the configured topology."""
        if cancelled:
            return DomainExecutionResult(
                plan_id=plan.plan_id,
                domain=plan.domain,
                status=AgentStatus.FAILED,
                metadata={"error": "Execution cancelled"},
            )

        start = time.perf_counter()
        if plan.execution_mode == DomainExecutionMode.PARALLEL:
            results = await self._execute_parallel(plan, request)
        elif plan.execution_mode == DomainExecutionMode.CONDITIONAL:
            results = await self._execute_conditional(plan, request)
        else:
            results = await self._execute_sequential(plan, request)

        elapsed = (time.perf_counter() - start) * 1000
        failed = [r for r in results if not r.success]
        partial = bool(failed) and self._policy.allow_partial_completion and len(failed) < len(results)
        status = AgentStatus.COMPLETED if not failed or partial else AgentStatus.FAILED

        return DomainExecutionResult(
            plan_id=plan.plan_id,
            domain=plan.domain,
            agent_results=results,
            status=status,
            partial_completion=partial,
            total_duration_ms=elapsed,
            metadata={"failed_count": len(failed), "retry_count": sum(r.retry_attempts for r in results)},
        )

    async def _execute_sequential(
        self,
        plan: DomainExecutionPlan,
        request: AgentRequest,
    ) -> list[DomainAgentResult]:
        results: list[DomainAgentResult] = []
        completed: set[str] = set()

        for step in plan.steps:
            if not all(dep in completed for dep in step.dependencies):
                results.append(
                    DomainAgentResult(
                        step_id=step.step_id,
                        agent_id=step.agent_id,
                        success=False,
                        error="Unmet dependencies",
                    ),
                )
                continue
            result = await self._execute_step(step, request)
            results.append(result)
            if result.success:
                completed.add(step.step_id)
        return results

    async def _execute_parallel(
        self,
        plan: DomainExecutionPlan,
        request: AgentRequest,
    ) -> list[DomainAgentResult]:
        groups: dict[str | None, list[DomainExecutionStep]] = {}
        for step in plan.steps:
            groups.setdefault(step.parallel_group, []).append(step)

        all_results: list[DomainAgentResult] = []
        for group_steps in groups.values():
            tasks = [self._execute_step(step, request) for step in group_steps]
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
            for step, outcome in zip(group_steps, outcomes, strict=True):
                if isinstance(outcome, Exception):
                    all_results.append(
                        DomainAgentResult(
                            step_id=step.step_id,
                            agent_id=step.agent_id,
                            success=False,
                            error=str(outcome),
                        ),
                    )
                else:
                    all_results.append(outcome)
        return all_results

    async def _execute_conditional(
        self,
        plan: DomainExecutionPlan,
        request: AgentRequest,
    ) -> list[DomainAgentResult]:
        results: list[DomainAgentResult] = []
        condition_state: dict[str, bool] = dict(plan.metadata.get("conditions", {}))

        for step in plan.steps:
            if step.condition and not condition_state.get(step.condition, True):
                results.append(
                    DomainAgentResult(
                        step_id=step.step_id,
                        agent_id=step.agent_id,
                        success=True,
                        error="Condition not met — skipped",
                        metadata={"skipped": True},
                    ),
                )
                continue
            result = await self._execute_step(step, request)
            results.append(result)
            if step.condition:
                condition_state[step.condition] = result.success
        return results

    async def _execute_step(
        self,
        step: DomainExecutionStep,
        request: AgentRequest,
    ) -> DomainAgentResult:
        agent_id = step.agent_id
        used_fallback = False
        start = time.perf_counter()
        attempt = 0

        while attempt <= step.max_retries:
            attempt += 1
            try:
                handler = await self._resolve_agent(agent_id)
                agent_request = request.model_copy(
                    update={
                        "target_agent": agent_id,
                        "context": {**request.context, "domain_action": step.action},
                    },
                )
                response = await asyncio.wait_for(
                    handler.invoke(agent_request),
                    timeout=step.timeout_seconds or self._policy.default_timeout_seconds,
                )
                duration_ms = (time.perf_counter() - start) * 1000
                return DomainAgentResult(
                    step_id=step.step_id,
                    agent_id=agent_id,
                    success=response.is_success,
                    response=response,
                    duration_ms=duration_ms,
                    retry_attempts=attempt - 1,
                    used_fallback=used_fallback,
                    memory_references=response.memory_references,
                    error=response.error,
                )
            except Exception as exc:
                if attempt <= min(step.max_retries, self._policy.max_retries):
                    delay = self._policy.retry_delay_seconds * (2 ** max(attempt - 1, 0))
                    await asyncio.sleep(delay)
                    continue

                if (
                    self._policy.enable_fallback
                    and step.fallback_agent
                    and not used_fallback
                ):
                    agent_id = step.fallback_agent
                    used_fallback = True
                    attempt = 0
                    continue

                duration_ms = (time.perf_counter() - start) * 1000
                return DomainAgentResult(
                    step_id=step.step_id,
                    agent_id=step.agent_id,
                    success=False,
                    error=str(exc),
                    duration_ms=duration_ms,
                    retry_attempts=attempt,
                    used_fallback=used_fallback,
                )

        duration_ms = (time.perf_counter() - start) * 1000
        return DomainAgentResult(
            step_id=step.step_id,
            agent_id=step.agent_id,
            success=False,
            error="Max retries exceeded",
            duration_ms=duration_ms,
            retry_attempts=attempt,
        )
