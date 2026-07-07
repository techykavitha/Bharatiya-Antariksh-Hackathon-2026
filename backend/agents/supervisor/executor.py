"""Sequential workflow executor for Climate Supervisor."""

from __future__ import annotations

import time
from typing import Any

from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.memory.memory_types import MemoryDomain, MemoryStoreRequest
from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import AgentResponse
from backend.agents.supervisor.agent_registry import AgentRegistry
from backend.agents.supervisor.execution_context import (
    DigitalTwinInterface,
    ExecutionPlan,
    ExecutionResult,
    RLEngineInterface,
    StepExecutionResult,
    StepStatus,
    SupervisorExecutionContext,
)
from backend.agents.supervisor.failure_handler import FailureHandler
from backend.agents.supervisor.state_manager import StateManager
from backend.agents.supervisor.workflow_monitor import WorkflowMonitor
from backend.agents.supervisor.workflow_router import RouteDecision, WorkflowRouter
from backend.agents.tools.abstract_tool import AbstractTool, ToolInput
from backend.config.logger import get_logger
from backend.utils.enums import AgentRole, AgentStatus

logger = get_logger(__name__)


class Executor:
    """
    Executes workflow plans sequentially with context propagation,
    memory updates, and state tracking.
    """

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        router: WorkflowRouter,
        memory: MemoryManager,
        state_manager: StateManager,
        monitor: WorkflowMonitor,
        failure_handler: FailureHandler,
        rl_engine: RLEngineInterface | None = None,
        digital_twin: DigitalTwinInterface | None = None,
        tools: dict[str, AbstractTool] | None = None,
    ) -> None:
        self._registry = registry
        self._router = router
        self._memory = memory
        self._state_manager = state_manager
        self._monitor = monitor
        self._failure_handler = failure_handler
        self._rl_engine = rl_engine
        self._digital_twin = digital_twin
        self._tools = tools or {}

    async def execute(
        self,
        plan: ExecutionPlan,
        context: SupervisorExecutionContext,
        *,
        route_decision: RouteDecision | None = None,
    ) -> ExecutionResult:
        """Execute all plan steps sequentially."""
        start = time.perf_counter()
        decision = route_decision or await self._router.route_plan(plan, context)
        results: list[StepExecutionResult] = []
        completed_ids: list[str] = []

        if self._failure_handler.is_cancelled(context.cancelled):
            return ExecutionResult(
                plan_id=plan.plan_id,
                status=AgentStatus.FAILED,
                metadata={"error": "Execution cancelled"},
            )

        while True:
            step = await self._router.route_next_step(plan, completed_ids)
            if step is None:
                break
            if step.step_id in decision.skip_step_ids:
                results.append(
                    StepExecutionResult(
                        step_id=step.step_id,
                        supervisor_id=step.supervisor_id,
                        status=StepStatus.SKIPPED,
                    ),
                )
                completed_ids.append(step.step_id)
                continue

            result = await self._execute_step(step, context, decision.fallback_map)
            results.append(result)
            completed_ids.append(step.step_id)

            if result.response:
                context.step_outputs[step.step_id] = result.response.model_dump(mode="json")

            if result.status == StepStatus.FAILED and not self._failure_handler.allow_partial_completion(
                [r for r in results if r.status == StepStatus.FAILED],
                len(decision.steps),
            ):
                break

        elapsed = (time.perf_counter() - start) * 1000
        failed = [r for r in results if r.status == StepStatus.FAILED]
        status = AgentStatus.COMPLETED if not failed else AgentStatus.FAILED
        partial = bool(failed) and self._failure_handler.allow_partial_completion(failed, len(results))

        execution_result = ExecutionResult(
            plan_id=plan.plan_id,
            step_results=results,
            status=status,
            partial_completion=partial,
            total_duration_ms=elapsed,
            metadata={"failed_count": len(failed)},
        )
        self._monitor.record_step_results(results)
        logger.info(
            "sequential_execution_complete",
            plan_id=plan.plan_id,
            steps=len(results),
            duration_ms=round(elapsed, 2),
        )
        return execution_result

    async def _execute_step(
        self,
        step,
        context: SupervisorExecutionContext,
        fallback_map: dict[str, str],
    ) -> StepExecutionResult:
        supervisor_id = await self._router.resolve_supervisor_id(step, fallback_map)
        self._monitor.record_supervisor_start(supervisor_id)
        step_start = time.perf_counter()
        attempt = 0
        used_fallback = supervisor_id != step.supervisor_id

        while attempt <= step.max_retries:
            attempt += 1
            try:
                if step.requires_digital_twin and self._digital_twin:
                    twin_id = context.metadata.get("twin_id", "default")
                    twin_state = await self._digital_twin.get_state(twin_id)
                    context.metadata["digital_twin_state"] = twin_state

                if step.requires_rl and self._rl_engine:
                    scenario_id = context.metadata.get("scenario_id", plan_scenario_id(context))
                    rl_result = await self._rl_engine.request_policy(scenario_id, context=context.metadata)
                    context.metadata["rl_policy"] = rl_result
                    self._monitor.record_rl_usage()

                for tool_name in step.tool_names:
                    if tool_name in self._tools:
                        tool_result = await self._tools[tool_name].run(
                            ToolInput(parameters=context.step_outputs),
                        )
                        self._monitor.record_tool_usage()
                        context.step_outputs[f"tool:{tool_name}"] = tool_result.model_dump()

                response = await self._invoke_supervisor(supervisor_id, step, context)
                memory_refs = await self._store_step_memory(step, response, context)

                duration_ms = (time.perf_counter() - step_start) * 1000
                self._monitor.record_supervisor_end(supervisor_id, duration_ms=duration_ms, success=True)

                return StepExecutionResult(
                    step_id=step.step_id,
                    supervisor_id=supervisor_id,
                    status=StepStatus.COMPLETED,
                    response=response,
                    duration_ms=duration_ms,
                    retry_attempts=attempt - 1,
                    used_fallback=used_fallback,
                    memory_references=memory_refs,
                )

            except Exception as exc:
                error_msg = str(exc)
                if attempt <= step.max_retries:
                    self._monitor.record_retry()
                    await self._failure_handler.retry_with_backoff(attempt)
                    continue

                if self._failure_handler.should_use_fallback(step, attempt):
                    supervisor_id = self._failure_handler.resolve_fallback_supervisor(step) or supervisor_id
                    used_fallback = True
                    attempt = 0
                    continue

                duration_ms = (time.perf_counter() - step_start) * 1000
                self._monitor.record_supervisor_end(supervisor_id, duration_ms=duration_ms, success=False)
                return await self._failure_handler.handle_failure(step, error_msg, attempt=attempt)

        duration_ms = (time.perf_counter() - step_start) * 1000
        return StepExecutionResult(
            step_id=step.step_id,
            supervisor_id=supervisor_id,
            status=StepStatus.FAILED,
            error="Max retries exceeded",
            duration_ms=duration_ms,
            retry_attempts=attempt,
        )

    async def _invoke_supervisor(
        self,
        supervisor_id: str,
        step,
        context: SupervisorExecutionContext,
    ) -> AgentResponse:
        handler = await self._registry.resolve(supervisor_id)
        request = self._build_request(step, context)
        return await self._failure_handler.execute_with_timeout(
            handler.invoke(request),
            timeout_seconds=step.timeout_seconds,
        )

    def _build_request(self, step, context: SupervisorExecutionContext) -> AgentRequest:
        base = context.agent_request
        if base:
            return base.model_copy(
                update={
                    "target_agent": step.supervisor_id,
                    "caller_agent_id": "climate_supervisor",
                    "caller_role": AgentRole.SUPERVISOR,
                    "tool_names": step.tool_names,
                    "context": {**base.context, **context.step_outputs},
                },
            )
        return AgentRequest(
            query=context.query,
            target_agent=step.supervisor_id,
            caller_agent_id="climate_supervisor",
            caller_role=AgentRole.SUPERVISOR,
            tool_names=step.tool_names,
            context=context.step_outputs,
        )

    async def _store_step_memory(
        self,
        step,
        response: AgentResponse,
        context: SupervisorExecutionContext,
    ) -> list[str]:
        key = f"supervisor:{step.step_id}:{response.response_id}"
        await self._memory.store(
            MemoryStoreRequest(
                domain=MemoryDomain.WORKING,
                key=key,
                value=response.model_dump(mode="json"),
                metadata={"supervisor_id": step.supervisor_id, "agent_id": "climate_supervisor"},
            ),
        )
        self._monitor.record_memory_retrieval()
        return [key, *response.memory_references]


def plan_scenario_id(context: SupervisorExecutionContext) -> str:
    return context.metadata.get("scenario_id", context.request_id)
