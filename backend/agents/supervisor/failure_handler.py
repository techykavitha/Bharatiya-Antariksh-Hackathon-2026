"""Failure handling for Climate Supervisor workflow execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from backend.agents.supervisor.execution_context import (
    ExecutionPlanStep,
    StepExecutionResult,
    StepStatus,
)
from backend.config.logger import get_logger
from backend.utils.constants import DEFAULT_AGENT_TIMEOUT_SECONDS, MAX_AGENT_RETRIES

logger = get_logger(__name__)


@dataclass(frozen=True)
class FailurePolicy:
    """Configurable failure handling policy."""

    max_retries: int = MAX_AGENT_RETRIES
    retry_delay_seconds: float = 1.0
    enable_fallback: bool = True
    allow_partial_completion: bool = True
    default_timeout_seconds: int = DEFAULT_AGENT_TIMEOUT_SECONDS


class FailureHandler:
    """
    Handles step failures with retries, fallback supervisors,
    partial completion, timeouts, and cancellation.
    """

    def __init__(self, *, policy: FailurePolicy | None = None) -> None:
        self._policy = policy or FailurePolicy()

    async def handle_failure(
        self,
        step: ExecutionPlanStep,
        error: str,
        *,
        attempt: int,
    ) -> StepExecutionResult:
        """Record a failure and determine if retry is warranted."""
        should_retry = attempt < min(step.max_retries, self._policy.max_retries)
        logger.warning(
            "step_failure",
            step_id=step.step_id,
            supervisor_id=step.supervisor_id,
            attempt=attempt,
            error=error,
            will_retry=should_retry,
        )
        return StepExecutionResult(
            step_id=step.step_id,
            supervisor_id=step.supervisor_id,
            status=StepStatus.FAILED,
            error=error,
            retry_attempts=attempt,
            metadata={"retry_eligible": should_retry},
        )

    async def retry_with_backoff(
        self,
        attempt: int,
    ) -> None:
        """Wait before a retry attempt using exponential backoff."""
        delay = self._policy.retry_delay_seconds * (2 ** max(attempt - 1, 0))
        await asyncio.sleep(delay)

    def should_use_fallback(self, step: ExecutionPlanStep, attempt: int) -> bool:
        """Return True when fallback supervisor should be attempted."""
        return (
            self._policy.enable_fallback
            and step.fallback_supervisor is not None
            and attempt >= step.max_retries
        )

    def resolve_fallback_supervisor(self, step: ExecutionPlanStep) -> str | None:
        return step.fallback_supervisor if self._policy.enable_fallback else None

    async def execute_with_timeout(
        self,
        coro,
        *,
        timeout_seconds: int | None = None,
    ):
        """Execute a coroutine with a timeout."""
        timeout = timeout_seconds or self._policy.default_timeout_seconds
        return await asyncio.wait_for(coro, timeout=timeout)

    def allow_partial_completion(self, failed: list[StepExecutionResult], total: int) -> bool:
        """Return True if partial completion is acceptable."""
        if not self._policy.allow_partial_completion:
            return False
        succeeded = total - len(failed)
        return succeeded > 0

    def is_cancelled(self, context_cancelled: bool) -> bool:
        return context_cancelled

    async def mark_cancelled(self, step: ExecutionPlanStep) -> StepExecutionResult:
        return StepExecutionResult(
            step_id=step.step_id,
            supervisor_id=step.supervisor_id,
            status=StepStatus.CANCELLED,
            error="Execution cancelled",
        )
