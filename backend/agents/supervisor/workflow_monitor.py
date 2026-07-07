"""Workflow execution monitor and metrics collector."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from backend.agents.supervisor.execution_context import (
    StepExecutionResult,
    StepStatus,
    WorkflowMetrics,
)
from backend.config.logger import get_logger

logger = get_logger(__name__)


@dataclass
class _MonitorState:
    """Mutable internal monitor state."""

    start_time: float = field(default_factory=time.perf_counter)
    memory_retrieval_count: int = 0
    supervisor_invocations: int = 0
    parallel_task_count: int = 0
    failure_count: int = 0
    retry_count: int = 0
    tool_usage_count: int = 0
    rl_usage_count: int = 0
    active_supervisors: set[str] = field(default_factory=set)
    completed_supervisors: set[str] = field(default_factory=set)
    step_durations: list[float] = field(default_factory=list)


class WorkflowMonitor:
    """
    Tracks execution time, active supervisors, success rate,
    failures, retries, tool usage, memory usage, and RL usage.
    """

    def __init__(self) -> None:
        self._state = _MonitorState()
        self._logger = get_logger("supervisor.monitor")

    def start_execution(self) -> None:
        """Reset monitor state for a new workflow execution."""
        self._state = _MonitorState()
        self._logger.info("workflow_execution_started")

    def record_supervisor_start(self, supervisor_id: str) -> None:
        self._state.active_supervisors.add(supervisor_id)
        self._state.supervisor_invocations += 1
        self._logger.debug("supervisor_started", supervisor_id=supervisor_id)

    def record_supervisor_end(self, supervisor_id: str, *, duration_ms: float, success: bool) -> None:
        self._state.active_supervisors.discard(supervisor_id)
        self._state.completed_supervisors.add(supervisor_id)
        self._state.step_durations.append(duration_ms)
        if not success:
            self._state.failure_count += 1
        self._logger.debug(
            "supervisor_completed",
            supervisor_id=supervisor_id,
            duration_ms=round(duration_ms, 2),
            success=success,
        )

    def record_parallel_batch(self, count: int) -> None:
        self._state.parallel_task_count += count
        self._logger.debug("parallel_batch_recorded", count=count)

    def record_retry(self) -> None:
        self._state.retry_count += 1

    def record_memory_retrieval(self, count: int = 1) -> None:
        self._state.memory_retrieval_count += count

    def record_tool_usage(self, count: int = 1) -> None:
        self._state.tool_usage_count += count

    def record_rl_usage(self, count: int = 1) -> None:
        self._state.rl_usage_count += count

    def record_step_results(self, results: list[StepExecutionResult]) -> None:
        for result in results:
            if result.status == StepStatus.FAILED:
                self._state.failure_count += 1
            if result.retry_attempts > 0:
                self._state.retry_count += result.retry_attempts

    def get_metrics(self) -> WorkflowMetrics:
        """Return current workflow metrics snapshot."""
        elapsed_ms = (time.perf_counter() - self._state.start_time) * 1000
        total_steps = len(self._state.completed_supervisors) or 1
        failures = self._state.failure_count
        success_rate = max(0.0, min(1.0, (total_steps - failures) / total_steps))

        return WorkflowMetrics(
            execution_duration_ms=round(elapsed_ms, 2),
            memory_retrieval_count=self._state.memory_retrieval_count,
            supervisor_count=self._state.supervisor_invocations,
            parallel_task_count=self._state.parallel_task_count,
            failure_count=self._state.failure_count,
            retry_count=self._state.retry_count,
            tool_usage_count=self._state.tool_usage_count,
            rl_usage_count=self._state.rl_usage_count,
            active_supervisors=sorted(self._state.active_supervisors),
            success_rate=round(success_rate, 4),
        )

    def log_summary(self) -> None:
        metrics = self.get_metrics()
        self._logger.info(
            "workflow_execution_summary",
            duration_ms=metrics.execution_duration_ms,
            supervisors=metrics.supervisor_count,
            failures=metrics.failure_count,
            success_rate=metrics.success_rate,
        )
