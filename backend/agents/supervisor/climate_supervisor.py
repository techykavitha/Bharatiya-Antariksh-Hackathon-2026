"""Climate Supervisor — central orchestration engine for Hyperion Climate Twin."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage

from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.memory.memory_types import MemoryDomain, MemorySearchRequest, MemoryStoreRequest
from backend.agents.schemas.request import AgentRequest
from backend.agents.state.conversation_state import ConversationTurn
from backend.agents.state.workflow_state import WorkflowState, create_initial_workflow_state
from backend.agents.supervisor.agent_registry import AgentRegistry
from backend.agents.supervisor.execution_context import (
    DigitalTwinInterface,
    ExecutionPlan,
    ExecutionResult,
    IntentClassification,
    MergedSupervisorResult,
    RLEngineInterface,
    SupervisorExecutionContext,
    SupervisorResponse,
)
from backend.agents.supervisor.executor import Executor
from backend.agents.supervisor.failure_handler import FailureHandler
from backend.agents.supervisor.intent_classifier import IntentClassifier
from backend.agents.supervisor.parallel_executor import ParallelExecutor
from backend.agents.supervisor.planner import Planner
from backend.agents.supervisor.state_manager import StateManager
from backend.agents.supervisor.workflow_monitor import WorkflowMonitor
from backend.agents.supervisor.workflow_router import WorkflowRouter
from backend.agents.tools.abstract_tool import AbstractTool
from backend.config.logger import get_logger
from backend.utils.enums import AgentStatus

logger = get_logger(__name__)


class ClimateSupervisor:
    """
    Enterprise-grade orchestration engine for the Hyperion Climate Twin AI ecosystem.

    Every user request passes through this supervisor, which classifies intent,
    plans execution, routes to domain supervisors, merges results, and persists
    memory — all via a LangGraph ``StateGraph``.
    """

    SUPERVISOR_ID = "climate_supervisor"

    def __init__(
        self,
        *,
        memory: MemoryManager,
        registry: AgentRegistry | None = None,
        intent_classifier: IntentClassifier | None = None,
        planner: Planner | None = None,
        rl_engine: RLEngineInterface | None = None,
        digital_twin: DigitalTwinInterface | None = None,
        tools: dict[str, AbstractTool] | None = None,
    ) -> None:
        self._memory = memory
        self._registry = registry or AgentRegistry()
        self._classifier = intent_classifier or IntentClassifier()
        self._planner = planner or Planner(classifier=self._classifier)
        self._router = WorkflowRouter(registry=self._registry)
        self._state_manager = StateManager()
        self._monitor = WorkflowMonitor()
        self._failure_handler = FailureHandler()
        self._executor = Executor(
            registry=self._registry,
            router=self._router,
            memory=memory,
            state_manager=self._state_manager,
            monitor=self._monitor,
            failure_handler=self._failure_handler,
            rl_engine=rl_engine,
            digital_twin=digital_twin,
            tools=tools,
        )
        self._parallel_executor = ParallelExecutor(executor=self._executor, monitor=self._monitor)
        self._rl_engine = rl_engine
        self._digital_twin = digital_twin
        self._tools = tools or {}
        self._logger = get_logger("supervisor.climate")
        self._initialized = False
        self._compiled_graph = None

        # Per-request execution cache (keyed by request_id)
        self._contexts: dict[str, SupervisorExecutionContext] = {}
        self._classifications: dict[str, IntentClassification] = {}
        self._plans: dict[str, ExecutionPlan] = {}
        self._execution_results: dict[str, ExecutionResult] = {}
        self._merged_results: dict[str, MergedSupervisorResult] = {}
        self._responses: dict[str, SupervisorResponse] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the supervisor and compile the LangGraph workflow."""
        from backend.agents.supervisor.graph_builder import build_graph, compile_graph

        self._logger.info("climate_supervisor_initializing")
        graph = build_graph(self)
        self._compiled_graph = compile_graph(graph)
        await self._registry.health()
        self._initialized = True
        self._logger.info("climate_supervisor_initialized")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def registry(self) -> AgentRegistry:
        return self._registry

    @property
    def monitor(self) -> WorkflowMonitor:
        return self._monitor

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    async def classify_intent(self, query: str) -> IntentClassification:
        """Classify user intent from the query string."""
        return await self._classifier.classify(query)

    async def plan(
        self,
        classification: IntentClassification,
        *,
        query: str,
    ) -> ExecutionPlan:
        """Generate an execution plan for the classified intent."""
        available = await self._registry.list_ids()
        return await self._planner.plan(
            classification,
            query=query,
            available_supervisors=available if available else None,
        )

    async def select_domain_supervisors(self, plan: ExecutionPlan) -> list[str]:
        """Return the unique domain supervisor IDs in the plan."""
        return list({step.supervisor_id for step in plan.steps})

    async def execute(
        self,
        plan: ExecutionPlan,
        context: SupervisorExecutionContext,
    ) -> ExecutionResult:
        """Execute a plan using sequential or parallel strategy."""
        self._monitor.start_execution()
        route_decision = await self._router.route_plan(plan, context)

        if route_decision.use_parallel:
            return await self._parallel_executor.execute(plan, context, route_decision=route_decision)
        return await self._executor.execute(plan, context, route_decision=route_decision)

    async def merge_results(self, execution_result: ExecutionResult) -> MergedSupervisorResult:
        """Merge step execution results into a unified output."""
        responses = [r.response for r in execution_result.step_results if r.response]
        content_parts: list[str] = []
        structured: dict[str, Any] = {}
        memory_refs: list[str] = []
        kg_refs: list[str] = []
        forecast_refs: list[str] = []
        rl_outputs: dict[str, Any] = {}

        for result in execution_result.step_results:
            if result.memory_references:
                memory_refs.extend(result.memory_references)

        for response in responses:
            if response.content:
                content_parts.append(f"[{response.agent_id}] {response.content}")
            structured[response.agent_id] = response.structured_output
            memory_refs.extend(response.memory_references)
            kg_refs.extend(response.knowledge_graph_references)
            forecast_refs.extend(response.forecast_references)
            if response.metadata.get("rl_output"):
                rl_outputs[response.agent_id] = response.metadata["rl_output"]

        content = "\n\n".join(content_parts) if content_parts else "Workflow completed with no domain responses."
        if execution_result.partial_completion:
            content += "\n\n(Partial completion — some steps failed.)"

        return MergedSupervisorResult(
            content=content,
            structured_output=structured,
            agent_responses=responses,
            memory_references=list(dict.fromkeys(memory_refs)),
            knowledge_graph_references=list(dict.fromkeys(kg_refs)),
            forecast_references=list(dict.fromkeys(forecast_refs)),
            rl_outputs=rl_outputs,
            metadata={"step_count": len(execution_result.step_results)},
        )

    async def store_memory(
        self,
        context: SupervisorExecutionContext,
        merged: MergedSupervisorResult,
        *,
        session_id: str | None = None,
    ) -> list[str]:
        """Persist supervisor outputs to memory via MemoryManager only."""
        refs: list[str] = []
        sid = session_id or context.session_id

        summary_key = f"supervisor:response:{context.request_id}"
        await self._memory.store(
            MemoryStoreRequest(
                domain=MemoryDomain.WORKING,
                key=summary_key,
                value=merged.model_dump(mode="json"),
                metadata={"type": "supervisor_response", "request_id": context.request_id},
            ),
        )
        refs.append(summary_key)

        if sid:
            await self._memory.store(
                MemoryStoreRequest(
                    domain=MemoryDomain.CONVERSATION,
                    key="agent_response",
                    value={
                        "role": "assistant",
                        "content": merged.content,
                        "agent_id": self.SUPERVISOR_ID,
                    },
                    session_id=sid,
                ),
            )
            self._monitor.record_memory_retrieval()

        if context.query:
            await self._memory.search(
                MemorySearchRequest(
                    query=context.query,
                    domains=[MemoryDomain.VECTOR, MemoryDomain.KNOWLEDGE_GRAPH],
                    session_id=sid,
                    limit=5,
                ),
            )
            self._monitor.record_memory_retrieval()

        return refs

    async def return_response(
        self,
        context: SupervisorExecutionContext,
        classification: IntentClassification,
        plan: ExecutionPlan,
        execution_result: ExecutionResult,
        merged: MergedSupervisorResult,
        *,
        memory_refs: list[str] | None = None,
    ) -> SupervisorResponse:
        """Build the unified supervisor response."""
        metrics = self._monitor.get_metrics()
        response = SupervisorResponse(
            request_id=context.request_id,
            content=merged.content,
            status=execution_result.status,
            intent=classification.intent,
            plan_id=plan.plan_id,
            execution_result=execution_result,
            merged_result=merged,
            metrics=metrics.model_dump(),
            memory_references=memory_refs or merged.memory_references,
            error=execution_result.metadata.get("error"),
        )
        self._monitor.log_summary()
        self._logger.info(
            "supervisor_response_ready",
            request_id=context.request_id,
            intent=classification.intent.value,
            status=response.status.value,
        )
        return response

    async def process_request(
        self,
        request: AgentRequest,
        *,
        session_id: str | None = None,
        initial_state: WorkflowState | None = None,
    ) -> SupervisorResponse:
        """
        High-level entry point: run the full supervisor pipeline.

        Builds workflow state, executes the LangGraph, and returns
        the unified ``SupervisorResponse``.
        """
        if not self._initialized:
            await self.initialize()

        from backend.agents.supervisor.graph_builder import run_graph

        state = initial_state or self._build_initial_state(request)
        request_id = request.request_id

        async with self._lock:
            self._contexts[request_id] = SupervisorExecutionContext(
                request_id=request_id,
                session_id=session_id,
                query=request.query,
                agent_request=request,
            )

        state.setdefault("metadata", {})["supervisor_request_id"] = request_id
        if session_id:
            state["metadata"]["session_id"] = session_id

        final_state = await run_graph(self._compiled_graph, state)

        async with self._lock:
            response = self._responses.get(request_id)
            if response is None:
                raise RuntimeError(f"No supervisor response produced for request {request_id}")

        # Attach final workflow state snapshot to response metadata
        response.metrics["final_agent_status"] = str(final_state.get("agent_status"))
        return response

    # ------------------------------------------------------------------
    # LangGraph node functions
    # ------------------------------------------------------------------

    async def node_classify_intent(self, state: WorkflowState) -> dict[str, Any]:
        """LangGraph node: classify user intent."""
        request_id = self._request_id_from_state(state)
        query = self._extract_query(state)
        context = self._get_context(request_id, query)

        classification = await self.classify_intent(query)
        self._classifications[request_id] = classification
        context.intent = classification.intent

        update = self._state_manager.apply_classification(state, classification)
        update.update(self._state_manager.apply_node_complete(state, "classify_intent"))
        self._logger.info("node_classify_intent", intent=classification.intent.value)
        return update

    async def node_plan(self, state: WorkflowState) -> dict[str, Any]:
        """LangGraph node: generate execution plan."""
        request_id = self._request_id_from_state(state)
        context = self._contexts[request_id]
        classification = self._classifications[request_id]

        plan = await self.plan(classification, query=context.query)
        self._plans[request_id] = plan
        context.plan = plan

        update = self._state_manager.apply_plan(state, plan)
        update.update(self._state_manager.apply_node_complete(state, "plan"))
        self._logger.info("node_plan", plan_id=plan.plan_id, steps=len(plan.steps))
        return update

    async def node_execute(self, state: WorkflowState) -> dict[str, Any]:
        """LangGraph node: execute the plan."""
        request_id = self._request_id_from_state(state)
        context = self._contexts[request_id]
        plan = self._plans[request_id]

        execution_result = await self.execute(plan, context)
        self._execution_results[request_id] = execution_result

        called_agents = [r.supervisor_id for r in execution_result.step_results]
        tool_outputs = {
            r.supervisor_id: r.response.model_dump() if r.response else {}
            for r in execution_result.step_results
        }
        memory_refs = []
        for r in execution_result.step_results:
            memory_refs.extend(r.memory_references)

        update = self._state_manager.apply_execution_result(
            state,
            execution_result,
            called_agents=called_agents,
            tool_outputs=tool_outputs,
            memory_refs=memory_refs,
        )
        update.update(self._state_manager.apply_node_complete(state, "execute"))
        self._logger.info("node_execute", plan_id=plan.plan_id, status=execution_result.status.value)
        return update

    async def node_merge_results(self, state: WorkflowState) -> dict[str, Any]:
        """LangGraph node: merge step outputs."""
        request_id = self._request_id_from_state(state)
        execution_result = self._execution_results[request_id]

        merged = await self.merge_results(execution_result)
        self._merged_results[request_id] = merged

        update = self._state_manager.apply_node_complete(
            state,
            "merge_results",
            result_summary={"content_length": len(merged.content)},
        )
        self._logger.info("node_merge_results", responses=len(merged.agent_responses))
        return update

    async def node_store_memory(self, state: WorkflowState) -> dict[str, Any]:
        """LangGraph node: persist results to memory."""
        request_id = self._request_id_from_state(state)
        context = self._contexts[request_id]
        merged = self._merged_results[request_id]
        session_id = (state.get("metadata") or {}).get("session_id")

        memory_refs = await self.store_memory(context, merged, session_id=session_id)

        update = {
            "memory_references": memory_refs,
        }
        update.update(self._state_manager.apply_node_complete(state, "store_memory"))
        self._logger.info("node_store_memory", refs=len(memory_refs))
        return update

    async def node_return_response(self, state: WorkflowState) -> dict[str, Any]:
        """LangGraph node: build and finalize the response."""
        request_id = self._request_id_from_state(state)
        context = self._contexts[request_id]
        classification = self._classifications[request_id]
        plan = self._plans[request_id]
        execution_result = self._execution_results[request_id]
        merged = self._merged_results[request_id]
        session_id = (state.get("metadata") or {}).get("session_id")

        memory_refs = state.get("memory_references", [])
        response = await self.return_response(
            context,
            classification,
            plan,
            execution_result,
            merged,
            memory_refs=memory_refs,
        )
        self._responses[request_id] = response

        update = self._state_manager.apply_response(state, content=response.content)
        update["messages"] = [HumanMessage(content=context.query), HumanMessage(content=response.content)]

        if session_id and state.get("conversation"):
            conv = state["conversation"]
            conv.append_turn(ConversationTurn(role="user", content=context.query))
            conv.append_turn(
                ConversationTurn(role="assistant", content=response.content, agent_id=self.SUPERVISOR_ID),
            )
            update["conversation"] = conv

        self._logger.info("node_return_response", response_id=response.response_id)
        return update

    # ------------------------------------------------------------------
    # RL interface delegation (no implementation)
    # ------------------------------------------------------------------

    async def request_policy(self, scenario_id: str, *, context: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._rl_engine is None:
            return {"status": "unavailable", "scenario_id": scenario_id}
        self._monitor.record_rl_usage()
        return await self._rl_engine.request_policy(scenario_id, context=context)

    async def evaluate_actions(
        self,
        actions: list[dict[str, Any]],
        *,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._rl_engine is None:
            return {"status": "unavailable", "actions": actions}
        return await self._rl_engine.evaluate_actions(actions, state=state)

    async def rank_actions(
        self,
        actions: list[dict[str, Any]],
        *,
        criteria: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if self._rl_engine is None:
            return actions
        return await self._rl_engine.rank_actions(actions, criteria=criteria)

    # ------------------------------------------------------------------
    # Digital Twin interface delegation (no implementation)
    # ------------------------------------------------------------------

    async def get_twin_state(self, twin_id: str) -> dict[str, Any]:
        if self._digital_twin is None:
            from backend.agents.memory.memory_types import MemoryDomain, MemoryRetrieveRequest

            entry = await self._memory.retrieve(
                MemoryRetrieveRequest(
                    domain=MemoryDomain.DIGITAL_TWIN,
                    key=twin_id,
                    twin_id=twin_id,
                ),
            )
            return entry.value if entry else {}
        return await self._digital_twin.get_state(twin_id)

    async def update_twin_state(self, twin_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        if self._digital_twin is None:
            return updates
        return await self._digital_twin.update_state(twin_id, updates)

    async def create_twin_scenario(self, twin_id: str, scenario: dict[str, Any]) -> str:
        if self._digital_twin is None:
            return str(uuid4())
        return await self._digital_twin.create_scenario(twin_id, scenario)

    async def compare_twin_scenarios(self, twin_id: str, scenario_a: str, scenario_b: str) -> dict[str, Any]:
        if self._digital_twin is None:
            return {"twin_id": twin_id, "scenario_a": scenario_a, "scenario_b": scenario_b}
        return await self._digital_twin.compare_scenarios(twin_id, scenario_a, scenario_b)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_initial_state(self, request: AgentRequest) -> WorkflowState:
        return create_initial_workflow_state(
            conversation=request.conversation,
            active_user=request.active_user,
            climate_state=request.climate_state,
            current_scenario=request.current_scenario,
            scenario_type=request.scenario_type,
            metadata={"supervisor_request_id": request.request_id, "query": request.query},
        )

    def _request_id_from_state(self, state: WorkflowState) -> str:
        meta = state.get("metadata") or {}
        return meta.get("supervisor_request_id", str(uuid4()))

    def _extract_query(self, state: WorkflowState) -> str:
        meta = state.get("metadata") or {}
        if meta.get("query"):
            return meta["query"]
        conversation = state.get("conversation")
        if conversation and conversation.last_user_message():
            return conversation.last_user_message() or ""
        messages = state.get("messages") or []
        if messages:
            return str(getattr(messages[-1], "content", ""))
        return ""

    def _get_context(self, request_id: str, query: str) -> SupervisorExecutionContext:
        if request_id not in self._contexts:
            self._contexts[request_id] = SupervisorExecutionContext(request_id=request_id, query=query)
        return self._contexts[request_id]

    @classmethod
    async def create(
        cls,
        memory: MemoryManager | None = None,
        **kwargs: Any,
    ) -> ClimateSupervisor:
        """Factory that wires a MemoryManager and initializes the supervisor."""
        mem = memory or await MemoryManager.create_in_memory()
        supervisor = cls(memory=mem, **kwargs)
        await supervisor.initialize()
        return supervisor
