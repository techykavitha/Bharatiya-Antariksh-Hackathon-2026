"""Parallel workflow executor for Climate Supervisor."""

from __future__ import annotations

import asyncio
import time

from backend.agents.supervisor.execution_context import (
    ExecutionPlan,
    ExecutionResult,
    StepExecutionResult,
    StepStatus,
    SupervisorExecutionContext,
)
from backend.agents.supervisor.executor import Executor
from backend.agents.supervisor.workflow_monitor import WorkflowMonitor
from backend.agents.supervisor.workflow_router import RouteDecision
from backend.config.logger import get_logger
from backend.utils.enums import AgentStatus

logger = get_logger(__name__)


class ParallelExecutor:
    """
    Executes independent workflow steps concurrently using asyncio.

    Collects outputs and handles partial failures gracefully.
    """

    def __init__(self, *, executor: Executor, monitor: WorkflowMonitor) -> None:
        self._executor = executor
        self._monitor = monitor

    async def execute(
        self,
        plan: ExecutionPlan,
        context: SupervisorExecutionContext,
        *,
        route_decision: RouteDecision,
    ) -> ExecutionResult:
        """Execute plan steps in parallel where possible."""
        start = time.perf_counter()
        steps = route_decision.steps

        if not steps:
            return ExecutionResult(plan_id=plan.plan_id, status=AgentStatus.COMPLETED)

        # Group steps by parallel_group (or run all concurrently if no groups)
        groups: dict[str | None, list] = {}
        for step in steps:
            if step.step_id in route_decision.skip_step_ids:
                continue
            key = step.parallel_group
            groups.setdefault(key, []).append(step)

        all_results: list[StepExecutionResult] = []

        for group_key, group_steps in groups.items():
            self._monitor.record_parallel_batch(len(group_steps))
            tasks = [
                self._executor._execute_step(step, context, route_decision.fallback_map)
                for step in group_steps
            ]
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)

            for step, outcome in zip(group_steps, outcomes, strict=True):
                if isinstance(outcome, Exception):
                    all_results.append(
                        StepExecutionResult(
                            step_id=step.step_id,
                            supervisor_id=step.supervisor_id,
                            status=StepStatus.FAILED,
                            error=str(outcome),
                        ),
                    )
                else:
                    all_results.append(outcome)
                    if outcome.response:
                        context.step_outputs[step.step_id] = outcome.response.model_dump(mode="json")

        elapsed = (time.perf_counter() - start) * 1000
        failed = [r for r in all_results if r.status == StepStatus.FAILED]
        partial = bool(failed) and len(failed) < len(all_results)
        status = AgentStatus.COMPLETED if not failed else (
            AgentStatus.COMPLETED if partial else AgentStatus.FAILED
        )

        result = ExecutionResult(
            plan_id=plan.plan_id,
            step_results=all_results,
            status=status,
            partial_completion=partial,
            total_duration_ms=elapsed,
            metadata={"parallel_groups": len(groups), "failed_count": len(failed)},
        )
        self._monitor.record_step_results(all_results)
        logger.info(
            "parallel_execution_complete",
            plan_id=plan.plan_id,
            steps=len(all_results),
            parallel_groups=len(groups),
            duration_ms=round(elapsed, 2),
        )
        return result
