"""Dynamic workflow router for Climate Supervisor task dispatch."""

from __future__ import annotations

from pydantic import BaseModel

from backend.agents.supervisor.agent_registry import AgentRegistry
from backend.agents.supervisor.execution_context import (
    ExecutionMode,
    ExecutionPlan,
    ExecutionPlanStep,
    SupervisorExecutionContext,
)
from backend.config.logger import get_logger

logger = get_logger(__name__)


class RouteDecision(BaseModel):
    """Routing decision for a plan or step."""

    execution_mode: ExecutionMode
    steps: list[ExecutionPlanStep]
    use_parallel: bool
    retry_step_ids: list[str]
    fallback_map: dict[str, str]
    skip_step_ids: list[str]


class WorkflowRouter:
    """
    Routes execution plans to the appropriate execution strategy.

    Supports single supervisor, multi-supervisor, parallel, conditional,
    retry, and fallback routing patterns.
    """

    def __init__(self, *, registry: AgentRegistry) -> None:
        self._registry = registry

    async def route_plan(
        self,
        plan: ExecutionPlan,
        context: SupervisorExecutionContext,
    ) -> RouteDecision:
        """Determine how to execute the given plan."""
        available = await self._registry.list_ids()
        executable_steps: list[ExecutionPlanStep] = []
        skip_ids: list[str] = []
        fallback_map: dict[str, str] = {}

        for step in plan.steps:
            if await self._should_skip(step, context):
                skip_ids.append(step.step_id)
                continue

            if await self._registry.is_registered(step.supervisor_id):
                executable_steps.append(step)
            elif step.fallback_supervisor and await self._registry.is_registered(step.fallback_supervisor):
                fallback_map[step.step_id] = step.fallback_supervisor
                executable_steps.append(step.model_copy(update={"supervisor_id": step.fallback_supervisor}))
            else:
                logger.warning(
                    "supervisor_not_registered",
                    supervisor_id=step.supervisor_id,
                    step_id=step.step_id,
                )
                if step.fallback_supervisor:
                    fallback_map[step.step_id] = step.fallback_supervisor
                executable_steps.append(step)

        use_parallel = plan.execution_mode == ExecutionMode.PARALLEL and len(executable_steps) > 1
        retry_ids = [s.step_id for s in executable_steps if s.retry_count > 0]

        decision = RouteDecision(
            execution_mode=plan.execution_mode,
            steps=executable_steps,
            use_parallel=use_parallel,
            retry_step_ids=retry_ids,
            fallback_map=fallback_map,
            skip_step_ids=skip_ids,
        )
        logger.info(
            "workflow_routed",
            plan_id=plan.plan_id,
            mode=decision.execution_mode.value,
            parallel=decision.use_parallel,
            step_count=len(executable_steps),
            skipped=len(skip_ids),
        )
        return decision

    async def route_next_step(
        self,
        plan: ExecutionPlan,
        completed_step_ids: list[str],
        *,
        condition_results: dict[str, bool] | None = None,
    ) -> ExecutionPlanStep | None:
        """Return the next step to execute in sequential/conditional mode."""
        condition_results = condition_results or {}
        completed = set(completed_step_ids)

        for step in plan.steps:
            if step.step_id in completed:
                continue
            if step.condition and not condition_results.get(step.condition, True):
                continue
            if all(dep in completed for dep in step.dependencies):
                return step
        return None

    async def resolve_supervisor_id(
        self,
        step: ExecutionPlanStep,
        fallback_map: dict[str, str],
    ) -> str:
        """Resolve the effective supervisor ID for a step."""
        if step.step_id in fallback_map:
            return fallback_map[step.step_id]
        if await self._registry.is_registered(step.supervisor_id):
            return step.supervisor_id
        if step.fallback_supervisor and await self._registry.is_registered(step.fallback_supervisor):
            return step.fallback_supervisor
        return step.supervisor_id

    async def _should_skip(self, step: ExecutionPlanStep, context: SupervisorExecutionContext) -> bool:
        if context.cancelled:
            return True
        if step.condition:
            return not context.metadata.get(f"condition:{step.condition}", True)
        return False
