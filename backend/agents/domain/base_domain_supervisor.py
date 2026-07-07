"""Base domain supervisor for middle-layer agent orchestration."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from backend.agents.domain.domain_context import (
    DomainAgentRegistration,
    DomainAgentStatus,
    DomainExecutionMetrics,
    DomainExecutionMode,
    DomainExecutionPlan,
    DomainExecutionResult,
    DomainExecutionStep,
    DomainHealthReport,
    DomainMergedResult,
    DomainSelectionResult,
    DomainTask,
    DomainType,
)
from backend.agents.domain.domain_execution import DomainAgentHandler, DomainExecutionPolicy, DomainExecutor
from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.memory.memory_types import MemoryDomain, MemoryStoreRequest
from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import AgentResponse
from backend.agents.state.conversation_state import ConversationTurn
from backend.agents.state.workflow_state import WorkflowState
from backend.config.logger import Logger, get_logger
from backend.utils.enums import AgentRole, AgentStatus
from backend.utils.errors import DependencyNotFoundError, DependencyRegistrationError


class InternalAgentRegistry:
    """Per-domain registry for specialized agents."""

    def __init__(self, *, domain_id: str) -> None:
        self._domain_id = domain_id
        self._handlers: dict[str, DomainAgentHandler] = {}
        self._metadata: dict[str, DomainAgentRegistration] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        handler: DomainAgentHandler,
        *,
        name: str | None = None,
        description: str = "",
        capabilities: list[str] | None = None,
        supported_tasks: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        agent_id = handler.agent_id
        async with self._lock:
            if agent_id in self._handlers:
                raise DependencyRegistrationError(
                    f"Agent '{agent_id}' already registered in domain '{self._domain_id}'",
                    details={"agent_id": agent_id},
                )
            self._handlers[agent_id] = handler
            self._metadata[agent_id] = DomainAgentRegistration(
                agent_id=agent_id,
                name=name or agent_id,
                description=description,
                capabilities=capabilities or [],
                supported_tasks=supported_tasks or [],
                status=DomainAgentStatus.READY,
                metadata=metadata or {},
            )

    async def remove(self, agent_id: str) -> bool:
        async with self._lock:
            if agent_id not in self._handlers:
                return False
            del self._handlers[agent_id]
            self._metadata.pop(agent_id, None)
            return True

    async def resolve(self, agent_id: str) -> DomainAgentHandler:
        async with self._lock:
            handler = self._handlers.get(agent_id)
            if handler is None:
                raise DependencyNotFoundError(
                    f"Agent '{agent_id}' not found in domain '{self._domain_id}'",
                )
            return handler

    async def list_agents(self) -> list[DomainAgentRegistration]:
        async with self._lock:
            return list(self._metadata.values())

    async def list_ids(self) -> list[str]:
        async with self._lock:
            return sorted(self._handlers.keys())

    async def health(self, agent_id: str | None = None) -> dict[str, bool]:
        async with self._lock:
            targets = (
                {agent_id: self._handlers[agent_id]}
                if agent_id and agent_id in self._handlers
                else dict(self._handlers)
            )
        results: dict[str, bool] = {}
        for aid, handler in targets.items():
            try:
                results[aid] = await handler.health_check()
            except Exception:
                results[aid] = False
        return results

    async def status(self, agent_id: str) -> DomainAgentStatus:
        async with self._lock:
            reg = self._metadata.get(agent_id)
            if reg is None:
                raise DependencyNotFoundError(f"Agent '{agent_id}' not found")
            return reg.status

    async def mark_invoked(self, agent_id: str) -> None:
        async with self._lock:
            if agent_id in self._metadata:
                self._metadata[agent_id].last_invoked_at = datetime.now(timezone.utc)
                self._metadata[agent_id].status = DomainAgentStatus.BUSY

    async def is_registered(self, agent_id: str) -> bool:
        async with self._lock:
            return agent_id in self._handlers


class BaseDomainSupervisor(ABC):
    """
    Abstract base for domain-level supervisors in the Hyperion hierarchy.

    Sits between the Climate Supervisor and specialized agents, managing
    agent registration, selection, execution, memory, and workflow state.
    """

    def __init__(
        self,
        *,
        memory: MemoryManager,
        execution_policy: DomainExecutionPolicy | None = None,
    ) -> None:
        self._memory = memory
        self._agent_registry = InternalAgentRegistry(domain_id=self.supervisor_id)
        self._executor = DomainExecutor(
            resolve_agent=self._agent_registry.resolve,
            policy=execution_policy,
        )
        self._logger: Logger = get_logger(f"domain.{self.supervisor_id}")
        self._initialized = False
        self._last_metrics: DomainExecutionMetrics | None = None

    @property
    @abstractmethod
    def supervisor_id(self) -> str:
        """Unique domain supervisor identifier."""

    @property
    @abstractmethod
    def domain_type(self) -> DomainType:
        """Domain classification."""

    @property
    @abstractmethod
    def supported_tasks(self) -> list[DomainTask]:
        """Tasks this domain supervisor can handle."""

    @property
    @abstractmethod
    def agent_slots(self) -> list[DomainAgentRegistration]:
        """Metadata for future specialized agents managed by this domain."""

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def last_metrics(self) -> DomainExecutionMetrics | None:
        return self._last_metrics

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the domain supervisor and seed agent slot metadata."""
        self._logger.info("domain_supervisor_initializing", supervisor_id=self.supervisor_id)
        await self._on_initialize()
        self._initialized = True
        self._logger.info("domain_supervisor_initialized", supervisor_id=self.supervisor_id)

    async def _on_initialize(self) -> None:
        """Hook for subclass-specific initialization."""

    # ------------------------------------------------------------------
    # Agent management
    # ------------------------------------------------------------------

    async def register_agent(
        self,
        handler: DomainAgentHandler,
        *,
        name: str | None = None,
        description: str = "",
        capabilities: list[str] | None = None,
        supported_tasks: list[str] | None = None,
    ) -> None:
        await self._agent_registry.register(
            handler,
            name=name,
            description=description,
            capabilities=capabilities,
            supported_tasks=supported_tasks,
        )

    async def unregister_agent(self, agent_id: str) -> bool:
        return await self._agent_registry.remove(agent_id)

    async def list_agents(self) -> list[DomainAgentRegistration]:
        registered = await self._agent_registry.list_agents()
        registered_ids = {r.agent_id for r in registered}
        slots = [s for s in self.agent_slots if s.agent_id not in registered_ids]
        return registered + slots

    # ------------------------------------------------------------------
    # Selection & execution
    # ------------------------------------------------------------------

    async def select_agents(self, request: AgentRequest) -> DomainSelectionResult:
        """Select specialized agents based on query keywords and task definitions."""
        query_lower = request.query.lower()
        best_task: DomainTask | None = None
        best_score = 0.0
        matched_keywords: list[str] = []

        for task in self.supported_tasks:
            score = 0.0
            task_matches: list[str] = []
            for keyword in task.keywords:
                if keyword.lower() in query_lower:
                    score += 1.0
                    task_matches.append(keyword)
            if score > best_score:
                best_score = score
                best_task = task
                matched_keywords = task_matches

        if best_task is None and self.supported_tasks:
            best_task = self.supported_tasks[0]

        selected: list[str] = []
        if best_task:
            registered_ids = await self._agent_registry.list_ids()
            for agent_id in best_task.preferred_agents:
                if agent_id in registered_ids:
                    selected.append(agent_id)
            if not selected:
                selected = list(best_task.preferred_agents)

        confidence = min(best_score / max(len(best_task.keywords) if best_task else 1, 1), 1.0)

        return DomainSelectionResult(
            domain=self.domain_type,
            task_id=best_task.task_id if best_task else None,
            selected_agents=selected,
            execution_mode=best_task.execution_mode if best_task else DomainExecutionMode.SEQUENTIAL,
            confidence=confidence,
            matched_keywords=matched_keywords,
        )

    def build_plan(
        self,
        selection: DomainSelectionResult,
        request: AgentRequest,
    ) -> DomainExecutionPlan:
        """Build an execution plan from agent selection."""
        steps: list[DomainExecutionStep] = []
        previous_id: str | None = None
        parallel_group = (
            f"{self.domain_type.value}_parallel"
            if selection.execution_mode == DomainExecutionMode.PARALLEL
            else None
        )

        for agent_id in selection.selected_agents:
            slot = next((s for s in self.agent_slots if s.agent_id == agent_id), None)
            step = DomainExecutionStep(
                agent_id=agent_id,
                action=selection.task_id or "invoke",
                dependencies=[previous_id] if previous_id and selection.execution_mode == DomainExecutionMode.SEQUENTIAL else [],
                parallel_group=parallel_group,
                fallback_agent=self._fallback_for(agent_id),
                metadata={"task_id": selection.task_id},
            )
            steps.append(step)
            previous_id = step.step_id

        return DomainExecutionPlan(
            domain=self.domain_type,
            query=request.query,
            task_id=selection.task_id,
            steps=steps,
            execution_mode=selection.execution_mode,
        )

    async def execute(
        self,
        request: AgentRequest,
        *,
        plan: DomainExecutionPlan | None = None,
    ) -> DomainExecutionResult:
        """Select agents (if needed), build plan, and execute."""
        if not self._initialized:
            await self.initialize()

        selection = await self.select_agents(request)
        execution_plan = plan or self.build_plan(selection, request)

        for step in execution_plan.steps:
            if await self._agent_registry.is_registered(step.agent_id):
                await self._agent_registry.mark_invoked(step.agent_id)

        result = await self._executor.execute(execution_plan, request)
        self._last_metrics = DomainExecutionMetrics(
            domain=self.domain_type,
            active_domain=self.supervisor_id,
            completed_agents=result.completed_agents,
            failed_agents=result.failed_agents,
            total_agents_invoked=len(result.agent_results),
            parallel_batches=1 if execution_plan.execution_mode == DomainExecutionMode.PARALLEL else 0,
            retry_count=int(result.metadata.get("retry_count", 0)),
            failure_count=len(result.failed_agents),
            duration_ms=result.total_duration_ms,
        )
        self._logger.info(
            "domain_execution_complete",
            supervisor_id=self.supervisor_id,
            status=result.status.value,
            agents=len(result.agent_results),
        )
        return result

    async def merge_results(self, result: DomainExecutionResult) -> DomainMergedResult:
        """Merge agent responses into a unified domain output."""
        responses = [r.response for r in result.agent_results if r.response]
        parts = [f"[{r.agent_id}] {r.response.content}" for r in result.agent_results if r.response]
        memory_refs: list[str] = []
        structured: dict[str, Any] = {}

        for agent_result in result.agent_results:
            memory_refs.extend(agent_result.memory_references)
            if agent_result.response:
                structured[agent_result.agent_id] = agent_result.response.structured_output

        content = "\n".join(parts) if parts else f"{self.supervisor_id} completed with no agent responses."
        if result.partial_completion:
            content += "\n(Partial completion — some agents failed.)"

        return DomainMergedResult(
            domain=self.domain_type,
            content=content,
            structured_output=structured,
            agent_responses=[r for r in responses if r is not None],
            memory_references=list(dict.fromkeys(memory_refs)),
            metadata={"plan_id": result.plan_id},
        )

    async def update_memory(
        self,
        request: AgentRequest,
        merged: DomainMergedResult,
        *,
        session_id: str | None = None,
    ) -> list[str]:
        """Persist domain outputs via MemoryManager only."""
        refs: list[str] = []
        key = f"domain:{self.supervisor_id}:{request.request_id}"
        await self._memory.store(
            MemoryStoreRequest(
                domain=MemoryDomain.WORKING,
                key=key,
                value=merged.model_dump(mode="json"),
                metadata={"domain": self.domain_type.value, "supervisor_id": self.supervisor_id},
            ),
        )
        refs.append(key)

        if session_id:
            await self._memory.store(
                MemoryStoreRequest(
                    domain=MemoryDomain.CONVERSATION,
                    key="agent_response",
                    value={
                        "role": "assistant",
                        "content": merged.content,
                        "agent_id": self.supervisor_id,
                    },
                    session_id=session_id,
                ),
            )
        if self._last_metrics:
            self._last_metrics.memory_writes = len(refs)
        return refs

    def update_state(
        self,
        state: WorkflowState,
        result: DomainExecutionResult,
        merged: DomainMergedResult,
        *,
        memory_refs: list[str],
    ) -> dict[str, Any]:
        """Return a partial WorkflowState update after domain execution."""
        metrics = self._last_metrics or DomainExecutionMetrics(
            domain=self.domain_type,
            active_domain=self.supervisor_id,
        )
        meta = dict(state.get("metadata") or {})
        meta.update({
            "active_domain": self.supervisor_id,
            "domain_type": self.domain_type.value,
            "completed_agents": result.completed_agents,
            "failed_agents": result.failed_agents,
            "domain_execution_metrics": metrics.model_dump(mode="json"),
            "domain_response": merged.content,
        })

        tool_outputs = {
            r.agent_id: r.response.model_dump(mode="json") if r.response else {}
            for r in result.agent_results
        }

        return {
            "called_agents": [self.supervisor_id, *result.completed_agents],
            "agent_status": result.status,
            "tool_outputs": tool_outputs,
            "memory_references": memory_refs,
            "metadata": meta,
            "error": result.metadata.get("error") if result.status == AgentStatus.FAILED else None,
        }

    async def health(self) -> DomainHealthReport:
        """Check health of the supervisor and all registered agents."""
        agent_health = await self._agent_registry.health()
        registered = await self._agent_registry.list_agents()
        ready = sum(1 for r in registered if r.status == DomainAgentStatus.READY)
        healthy = all(agent_health.values()) if agent_health else True

        return DomainHealthReport(
            supervisor_id=self.supervisor_id,
            domain=self.domain_type,
            healthy=healthy and self._initialized,
            agent_health=agent_health,
            registered_agents=len(registered),
            ready_agents=ready,
        )

    async def health_check(self) -> bool:
        """Protocol method for Climate Supervisor registry compatibility."""
        report = await self.health()
        return report.healthy

    # ------------------------------------------------------------------
    # Climate Supervisor entry point
    # ------------------------------------------------------------------

    async def invoke(self, request: AgentRequest) -> AgentResponse:
        """Primary entry point when called by the Climate Supervisor."""
        session_id = request.context.get("session_id")
        execution = await self.execute(request)
        merged = await self.merge_results(execution)
        memory_refs = await self.update_memory(request, merged, session_id=session_id)

        return AgentResponse(
            request_id=request.request_id,
            agent_id=self.supervisor_id,
            content=merged.content,
            status=execution.status,
            structured_output=merged.structured_output,
            memory_references=memory_refs,
            delegated_to=execution.completed_agents,
            metadata={
                "domain": self.domain_type.value,
                "task_id": execution.metadata.get("task_id"),
                "metrics": self._last_metrics.model_dump(mode="json") if self._last_metrics else {},
            },
            error=execution.metadata.get("error"),
        )

    async def as_graph_node(self, state: WorkflowState) -> dict[str, Any]:
        """Adapt this domain supervisor as a LangGraph node function."""
        conversation = state.get("conversation")
        query = ""
        if conversation:
            query = conversation.last_user_message() or ""
        if not query:
            query = (state.get("metadata") or {}).get("query", "")

        request = AgentRequest(
            query=query or "domain request",
            conversation=conversation,
            active_user=state.get("active_user"),
            climate_state=state.get("climate_state"),
            current_scenario=state.get("current_scenario"),
            scenario_type=state.get("scenario_type"),
            caller_agent_id="climate_supervisor",
            caller_role=AgentRole.SUPERVISOR,
            context=dict(state.get("metadata") or {}),
        )

        execution = await self.execute(request)
        merged = await self.merge_results(execution)
        session_id = (state.get("metadata") or {}).get("session_id")
        memory_refs = await self.update_memory(request, merged, session_id=session_id)
        update = self.update_state(state, execution, merged, memory_refs=memory_refs)

        if conversation:
            conversation.append_turn(
                ConversationTurn(role="assistant", content=merged.content, agent_id=self.supervisor_id),
            )
            update["conversation"] = conversation

        return update

    def _fallback_for(self, agent_id: str) -> str | None:
        """Return a fallback agent ID for the given agent, if configured."""
        ids = [s.agent_id for s in self.agent_slots]
        if agent_id in ids and len(ids) > 1:
            idx = ids.index(agent_id)
            return ids[(idx + 1) % len(ids)]
        return None
