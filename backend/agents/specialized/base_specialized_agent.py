"""Base class for all specialized Hyperion climate agents."""

from __future__ import annotations

import time
from abc import abstractmethod
from typing import Any

from backend.agents.base.base_agent import BaseAgent
from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.memory.memory_types import (
    MemoryDomain,
    MemoryRetrieveRequest,
    MemorySearchRequest,
    MemoryStoreRequest,
)
from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import AgentResponse, ToolOutputRecord
from backend.agents.specialized.agent_capabilities import (
    AgentCapability,
    CapabilityRegistry,
)
from backend.agents.specialized.agent_context import (
    AgentContext,
    AgentDelegationResult,
    AgentReport,
    ContextPhase,
    ForecastContext,
    MemoryContext,
    ScenarioContext,
    SimulationContext,
    UserContext,
)
from backend.agents.specialized.agent_execution import (
    AgentCommunicationInterface,
    AgentExecutionEngine,
    AgentExecutionPolicy,
    SpecializedRLEngineInterface,
)
from backend.agents.specialized.agent_health import AgentHealthChecker, AgentHealthReport
from backend.agents.specialized.agent_metrics import AgentMetricsCollector
from backend.agents.specialized.agent_reasoning import (
    ReasoningEngine,
    ReasoningPhase,
    ReasoningResult,
    ReasoningStep,
)
from backend.agents.specialized.agent_reflection import ReflectionEngine, ReflectionResult
from backend.agents.specialized.agent_tools import ToolCallSpec, ToolExecutionMode, ToolManager
from backend.agents.specialized.agent_validator import AgentValidator, ValidationResult
from backend.agents.state.climate_state import ClimateState
from backend.agents.state.conversation_state import ConversationTurn
from backend.agents.state.workflow_state import WorkflowState
from backend.agents.supervisor.execution_context import DigitalTwinInterface
from backend.agents.tools.abstract_tool import AbstractTool, ToolResult
from backend.config.logger import Logger, get_logger
from backend.utils.constants import VECTOR_SEARCH_TOP_K
from backend.utils.enums import AgentRole, AgentStatus
from backend.utils.errors import AgentInvocationError


class BaseSpecializedAgent(BaseAgent):
    """
    Enterprise base class for all specialized climate agents.

    Provides the full invocation pipeline: context retrieval, reasoning,
    reflection, validation, tool execution, inter-agent delegation, RL
    requests, standardized reporting, memory/state persistence, and health.
    """

    def __init__(
        self,
        agent_id: str,
        *,
        description: str = "",
        memory: MemoryManager,
        tools: list[AbstractTool] | None = None,
        capabilities: list[AgentCapability] | None = None,
        rl_engine: SpecializedRLEngineInterface | None = None,
        agent_communication: AgentCommunicationInterface | None = None,
        digital_twin: DigitalTwinInterface | None = None,
        execution_policy: AgentExecutionPolicy | None = None,
        confidence_threshold: float = 0.4,
    ) -> None:
        self._memory_manager = memory
        self._tool_manager = ToolManager(agent_id=agent_id)
        for tool in tools or []:
            self._tool_manager.register(tool)

        super().__init__(
            agent_id,
            AgentRole.SPECIALIZED,
            description=description,
            tools=tools,
        )

        self._capability_registry = CapabilityRegistry(agent_id=agent_id)
        self._reasoning_engine = ReasoningEngine(agent_id=agent_id)
        self._reflection_engine = ReflectionEngine(
            agent_id=agent_id,
            confidence_threshold=confidence_threshold,
        )
        self._validator = AgentValidator(agent_id=agent_id)
        self._execution_engine = AgentExecutionEngine(
            agent_id=agent_id,
            policy=execution_policy,
        )
        self._health_checker = AgentHealthChecker(agent_id=agent_id)
        self._rl_engine = rl_engine
        self._agent_communication = agent_communication
        self._digital_twin = digital_twin
        self._last_metrics: AgentMetricsCollector | None = None
        self._last_report: AgentReport | None = None
        self._framework_logger: Logger = get_logger(f"specialized.{agent_id}")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def memory_manager(self) -> MemoryManager:
        return self._memory_manager

    @property
    def tool_manager(self) -> ToolManager:
        return self._tool_manager

    @property
    def capability_registry(self) -> CapabilityRegistry:
        return self._capability_registry

    @property
    def last_metrics(self) -> AgentMetricsCollector | None:
        return self._last_metrics

    @property
    def last_report(self) -> AgentReport | None:
        return self._last_report

  # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _on_initialize(self) -> None:
        for capability in await self.declare_capabilities():
            await self._capability_registry.register(capability)
        await self._on_specialized_initialize()

    async def _on_specialized_initialize(self) -> None:
        """Hook for subclass-specific async initialization."""

    # ------------------------------------------------------------------
    # Primary entry point (overrides BaseAgent.invoke)
    # ------------------------------------------------------------------

    async def invoke(self, request: AgentRequest) -> AgentResponse:
        if not self._initialized:
            await self.initialize()

        metrics = AgentMetricsCollector(agent_id=self.agent_id, request_id=request.request_id)
        self._last_metrics = metrics
        self._status = AgentStatus.REASONING

        try:
            context = await self.retrieve_context(request)
            await self.preprocess(context)

            await self.retrieve_memory(context)
            await self.retrieve_climate_state(context)
            await self.retrieve_forecast(context)
            await self._hydrate_digital_twin(context)

            reasoning = await self.run_reasoning_pipeline(context)
            metrics.record_reasoning(
                sum(s.duration_ms for s in reasoning.steps),
            )

            reflection = await self.reflect(context, reasoning)
            metrics.record_reflection()

            tool_specs = await self.select_tools(context, reasoning)
            tool_results = await self.execute_tools(context, tool_specs)
            context.tool_outputs = tool_results
            metrics.record_tools(len(tool_results), sum(r.duration_ms for r in tool_results))

            validation = await self.validate(context, tool_results)
            metrics.record_validation()

            if reflection.needs_another_agent and self._agent_communication:
                await self.call_other_agents(context, reflection.suggested_agents, request)

            if reflection.needs_rl and self._rl_engine:
                await self.request_rl(context)

            report = await self.generate_report(context, reasoning, tool_results, reflection, validation)
            self._last_report = report
            metrics.set_confidence(report.confidence)

            memory_refs = await self.update_memory(context, report)
            await self.update_state(context, report)

            self._status = AgentStatus.COMPLETED
            metrics.finalize()

            delegated = [d.agent_id for d in context.delegation_results if d.success]
            return self._report_to_response(
                report,
                memory_refs=memory_refs,
                reasoning=reasoning,
                delegated_to=delegated,
            )

        except Exception as exc:
            self._status = AgentStatus.FAILED
            metrics.finalize()
            self._framework_logger.error(
                "specialized_agent_failed",
                agent_id=self.agent_id,
                request_id=request.request_id,
                error=str(exc),
            )
            raise AgentInvocationError(
                f"Specialized agent '{self.agent_id}' failed: {exc}",
                details={"agent_id": self.agent_id, "request_id": request.request_id},
            ) from exc

    # ------------------------------------------------------------------
    # Context pipeline
    # ------------------------------------------------------------------

    async def retrieve_context(self, request: AgentRequest) -> AgentContext:
        workflow_state: dict[str, Any] | None = None
        if isinstance(request.context.get("workflow_state"), dict):
            workflow_state = request.context["workflow_state"]

        user = UserContext(
            session_id=request.context.get("session_id"),
            active_user=request.active_user,
            preferences=dict(request.context.get("user_preferences", {})),
        )
        if request.active_user:
            user.user_id = request.active_user.user_id

        scenario = ScenarioContext(
            scenario_id=request.current_scenario or request.context.get("scenario_id"),
            scenario_type=request.scenario_type,
            label=request.context.get("scenario_label"),
            parameters=dict(request.context.get("scenario_parameters", {})),
        )

        context = AgentContext(
            agent_id=self.agent_id,
            request=request,
            workflow_state=workflow_state,
            climate_state=request.climate_state,
            scenario=scenario,
            user=user,
            conversation=request.conversation,
            metadata=dict(request.context),
        )
        context.mark_phase(ContextPhase.RETRIEVING)
        return context

    async def preprocess(self, context: AgentContext) -> AgentContext:
        context.mark_phase(ContextPhase.PREPROCESSING)
        await self._on_preprocess(context)
        return context

    async def retrieve_memory(self, context: AgentContext) -> MemoryContext:
        session_id = context.user.session_id or context.request.context.get("session_id")
        query = context.query

        ranked = await self._memory_manager.search(
            MemorySearchRequest(
                query=query,
                session_id=session_id,
                limit=VECTOR_SEARCH_TOP_K,
            ),
        )
        self._last_metrics and self._last_metrics.record_memory_read()

        entry = await self._memory_manager.retrieve(
            MemoryRetrieveRequest(
                domain=MemoryDomain.WORKING,
                key=f"{self.agent_id}:latest",
                session_id=session_id,
            ),
        )
        if entry:
            self._last_metrics and self._last_metrics.record_memory_read()

        memory_ctx = MemoryContext(
            entries=[entry] if entry else [],
            ranked_results=ranked,
            references=[r.entry.key for r in ranked if r.entry.key],
        )
        context.memory = memory_ctx
        return memory_ctx

    async def retrieve_climate_state(self, context: AgentContext) -> ClimateState | None:
        if context.climate_state:
            return context.climate_state

        session_id = context.user.session_id
        entry = await self._memory_manager.retrieve(
            MemoryRetrieveRequest(
                domain=MemoryDomain.CLIMATE,
                key="current_state",
                session_id=session_id,
            ),
        )
        self._last_metrics and self._last_metrics.record_memory_read()

        if entry and isinstance(entry.value, dict):
            context.climate_state = ClimateState.model_validate(entry.value)
        elif entry and isinstance(entry.value, ClimateState):
            context.climate_state = entry.value

        return context.climate_state

    async def retrieve_forecast(self, context: AgentContext) -> ForecastContext:
        forecast = ForecastContext()
        climate = context.climate_state

        if climate and climate.forecast_references:
            forecast.references = list(climate.forecast_references)
            if climate.forecast_references:
                primary = climate.forecast_references[0]
                forecast.forecast_id = primary.forecast_id
                forecast.model_name = primary.model_name
                forecast.horizon_hours = primary.horizon_hours

        session_id = context.user.session_id
        results = await self._memory_manager.search(
            MemorySearchRequest(
                query=context.query,
                domains=[MemoryDomain.VECTOR],
                session_id=session_id,
                limit=5,
                filters={"document_type": "forecast_summary"},
            ),
        )
        self._last_metrics and self._last_metrics.record_memory_read()

        if results:
            forecast.payload = {
                r.entry.key: r.entry.value
                for r in results
                if r.entry.value is not None
            }

        if climate and climate.active_simulation:
            sim = climate.active_simulation
            context.simulation = SimulationContext(
                simulation_id=sim.simulation_id,
                name=sim.name,
                status=sim.status.value,
                parameters=sim.parameters,
                outputs=sim.outputs,
            )

        context.forecast = forecast
        return forecast

    async def _hydrate_digital_twin(self, context: AgentContext) -> dict[str, Any]:
        twin_id = context.request.context.get("twin_id")
        if twin_id and self._digital_twin:
            state = await self._digital_twin.get_state(str(twin_id))
            context.digital_twin_state = state
            return state

        if context.workflow_state is not None:
            twin_state = context.workflow_state.get("digital_twin_state", {})
            if isinstance(twin_state, dict):
                context.digital_twin_state = twin_state
        return context.digital_twin_state

    # ------------------------------------------------------------------
    # Reasoning / reflection / validation
    # ------------------------------------------------------------------

    async def run_reasoning_pipeline(self, context: AgentContext) -> ReasoningResult:
        context.mark_phase(ContextPhase.REASONING)
        return await self._reasoning_engine.run(
            context,
            observe=self._phase_observe,
            think=self._phase_think,
            act=self._phase_act,
            reflect=self._phase_reflect,
            verify=self._phase_verify,
        )

    async def reflect(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
    ) -> ReflectionResult:
        context.mark_phase(ContextPhase.REFLECTING)
        return await self._reflection_engine.evaluate(context, reasoning)

    async def validate(
        self,
        context: AgentContext,
        tool_results: list[ToolResult],
    ) -> ValidationResult:
        context.mark_phase(ContextPhase.VALIDATING)
        required = await self.required_inputs()
        return await self._validator.validate(
            context,
            tool_results,
            required_inputs=required,
            require_forecast=bool(context.metadata.get("requires_forecast")),
            require_memory=bool(context.metadata.get("requires_memory")),
        )

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    async def select_tools(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
    ) -> list[ToolCallSpec]:
        explicit = [
            ToolCallSpec(tool_name=name, parameters=dict(context.request.context))
            for name in context.request.tool_names
            if self._tool_manager.has_tool(name)
        ]
        if explicit:
            return explicit

        recommended = [
            ToolCallSpec(tool_name=name, parameters={"query": context.query})
            for name in reasoning.recommended_tools
            if self._tool_manager.has_tool(name)
        ]
        if recommended:
            return recommended

        return await self._on_select_tools(context, reasoning)

    async def execute_tools(
        self,
        context: AgentContext,
        tool_specs: list[ToolCallSpec],
        *,
        parallel: bool = False,
    ) -> list[ToolResult]:
        context.mark_phase(ContextPhase.EXECUTING_TOOLS)
        if not tool_specs:
            return []

        mode = ToolExecutionMode.PARALLEL if parallel else ToolExecutionMode.SEQUENTIAL
        outcome = await self._tool_manager.execute(
            tool_specs,
            context={
                "agent_id": self.agent_id,
                "request_id": context.request_id,
                "query": context.query,
                **context.request.context,
            },
            mode=mode,
        )
        return outcome.results

    # ------------------------------------------------------------------
    # Inter-agent and RL
    # ------------------------------------------------------------------

    async def call_other_agents(
        self,
        context: AgentContext,
        agent_ids: list[str],
        request: AgentRequest,
    ) -> list[AgentDelegationResult]:
        if not self._agent_communication or not agent_ids:
            return []

        context.mark_phase(ContextPhase.DELEGATING)
        results: list[AgentDelegationResult] = []

        for target_id in agent_ids:
            start = time.perf_counter()
            try:
                delegated = request.model_copy(
                    update={
                        "caller_agent_id": self.agent_id,
                        "caller_role": AgentRole.SPECIALIZED,
                        "target_agent": target_id,
                    },
                )
                response = await self._agent_communication.call_agent(target_id, delegated)
                elapsed = (time.perf_counter() - start) * 1000
                self._last_metrics and self._last_metrics.record_agent_call()
                result = AgentDelegationResult(
                    agent_id=target_id,
                    success=response.is_success,
                    content=response.content,
                    structured_output=response.structured_output,
                    duration_ms=elapsed,
                )
            except Exception as exc:
                elapsed = (time.perf_counter() - start) * 1000
                result = AgentDelegationResult(
                    agent_id=target_id,
                    success=False,
                    error=str(exc),
                    duration_ms=elapsed,
                )
            results.append(result)

        context.delegation_results = results
        return results

    async def request_rl(self, context: AgentContext) -> dict[str, Any]:
        if not self._rl_engine:
            return {}

        scenario_id = (
            context.scenario.scenario_id
            or context.request.current_scenario
            or context.request_id
        )
        policy = await self._rl_engine.request_policy(
            str(scenario_id),
            context={
                "query": context.query,
                "agent_id": self.agent_id,
                "climate_state": (
                    context.climate_state.model_dump() if context.climate_state else {}
                ),
            },
        )
        self._last_metrics and self._last_metrics.record_rl_call()
        context.rl_outputs.policy = policy
        return policy

    # ------------------------------------------------------------------
    # Report / memory / state
    # ------------------------------------------------------------------

    async def generate_report(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        tool_results: list[ToolResult],
        reflection: ReflectionResult,
        validation: ValidationResult,
    ) -> AgentReport:
        context.mark_phase(ContextPhase.GENERATING_REPORT)
        tool_records = self._tool_results_to_records(tool_results)
        confidence = reflection.confidence

        report = AgentReport(
            agent_id=self.agent_id,
            request_id=context.request_id,
            summary=await self._on_generate_summary(context, reasoning, tool_results),
            reasoning=reasoning.trace,
            risk=await self._on_assess_risk(context, reasoning, tool_results),
            confidence=confidence if validation.valid else min(confidence, 0.5),
            recommendations=await self._on_generate_recommendations(context, reasoning, reflection),
            references=list(context.memory.references),
            tool_outputs=tool_records,
            structured_output=await self._on_structured_output(context, reasoning, tool_results),
            metadata={
                "validation_valid": validation.valid,
                "reflection_signals": [f.signal.value for f in reflection.findings],
            },
        )
        return report

    async def update_memory(self, context: AgentContext, report: AgentReport) -> list[str]:
        context.mark_phase(ContextPhase.PERSISTING)
        session_id = context.user.session_id
        refs: list[str] = []

        working_key = f"{self.agent_id}:{context.request_id}"
        await self._memory_manager.store(
            MemoryStoreRequest(
                domain=MemoryDomain.WORKING,
                key=working_key,
                value=report.model_dump(),
                session_id=session_id,
                metadata={"agent_id": self.agent_id, "type": "agent_report"},
            ),
        )
        refs.append(working_key)
        self._last_metrics and self._last_metrics.record_memory_write()

        if context.conversation:
            await self._memory_manager.store(
                MemoryStoreRequest(
                    domain=MemoryDomain.CONVERSATION,
                    key=f"turn:{context.request_id}",
                    value={
                        "role": "assistant",
                        "content": report.summary,
                        "agent_id": self.agent_id,
                    },
                    session_id=session_id,
                ),
            )
            self._last_metrics and self._last_metrics.record_memory_write()

        await self._on_update_memory(context, report)
        context.memory.references.extend(refs)
        return refs

    async def update_state(
        self,
        context: AgentContext,
        report: AgentReport,
    ) -> dict[str, Any]:
        update: dict[str, Any] = {
            "called_agents": [self.agent_id],
            "agent_status": AgentStatus.COMPLETED,
            "tool_outputs": {r.tool_name: r.output for r in report.tool_outputs},
            "memory_references": report.references,
            "metadata": {
                "specialized_agent": self.agent_id,
                "confidence": report.confidence,
                "report_id": report.report_id,
            },
        }

        if context.rl_outputs.policy:
            update["rl_outputs"] = context.rl_outputs.policy

        if context.workflow_state is not None:
            merged = dict(context.workflow_state)
            merged.update(update)
            context.workflow_state = merged

        return update

    async def health(self) -> AgentHealthReport:
        return await self._health_checker.check(
            initialized=self._initialized,
            tool_healthy=True,
            memory_healthy=True,
            capability_count=len(await self._capability_registry.list_capabilities()),
            tool_count=len(self._tool_manager.tool_names),
        )

    async def health_check(self) -> bool:
        report = await self.health()
        return report.status.value in ("healthy", "degraded")

    # ------------------------------------------------------------------
    # LangGraph
    # ------------------------------------------------------------------

    async def as_graph_node(self, state: WorkflowState) -> dict[str, Any]:
        query = ""
        conversation = state.get("conversation")
        if conversation:
            query = conversation.last_user_message() or ""
        if not query and state.get("messages"):
            last_msg = state["messages"][-1]
            query = getattr(last_msg, "content", str(last_msg))
        if not query:
            query = str(state.get("metadata", {}).get("query", ""))

        request = AgentRequest(
            query=query,
            conversation=conversation,
            active_user=state.get("active_user"),
            climate_state=state.get("climate_state"),
            current_scenario=state.get("current_scenario"),
            scenario_type=state.get("scenario_type"),
            context={
                "workflow_state": dict(state),
                "session_id": state.get("metadata", {}).get("session_id"),
            },
        )

        response = await self.invoke(request)
        state_update = await self.update_state(
            AgentContext(
                agent_id=self.agent_id,
                request=request,
                workflow_state=dict(state),
            ),
            self._last_report or AgentReport(
                agent_id=self.agent_id,
                request_id=request.request_id,
                summary=response.content,
            ),
        )

        if conversation:
            conversation.append_turn(
                ConversationTurn(
                    role="assistant",
                    content=response.content,
                    agent_id=self.agent_id,
                ),
            )
            state_update["conversation"] = conversation

        if response.failed:
            state_update["error"] = response.error

        return state_update

    # ------------------------------------------------------------------
    # BaseAgent abstract method implementations
    # ------------------------------------------------------------------

    async def reason(self, request: AgentRequest) -> list[str]:
        """BaseAgent hook — delegates to the full reasoning pipeline."""
        context = await self.retrieve_context(request)
        result = await self.run_reasoning_pipeline(context)
        return result.trace

    async def generate_response(
        self,
        request: AgentRequest,
        *,
        reasoning: list[str],
        tool_results: list[ToolResult],
        memory_references: list[str],
    ) -> AgentResponse:
        report = self._last_report or AgentReport(
            agent_id=self.agent_id,
            request_id=request.request_id,
            summary="Analysis completed.",
            reasoning=reasoning,
            references=memory_references,
            tool_outputs=self._tool_results_to_records(tool_results),
        )
        return self._report_to_response(report, memory_refs=memory_references)

    # ------------------------------------------------------------------
    # Subclass hooks
    # ------------------------------------------------------------------

    @abstractmethod
    async def declare_capabilities(self) -> list[AgentCapability]:
        """Return the capabilities this agent provides."""

    async def required_inputs(self) -> list[str]:
        """Return required input field names for validation."""
        return ["query"]

    async def _on_preprocess(self, context: AgentContext) -> None:
        """Hook for subclass preprocessing."""

    async def _on_select_tools(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
    ) -> list[ToolCallSpec]:
        """Hook for subclass tool selection."""
        return []

    async def _on_generate_summary(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        tool_results: list[ToolResult],
    ) -> str:
        """Hook for subclass summary generation."""
        if tool_results and tool_results[0].output:
            return str(tool_results[0].output)
        return f"Completed analysis for: {context.query}"

    async def _on_assess_risk(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        tool_results: list[ToolResult],
    ) -> dict[str, Any]:
        """Hook for subclass risk assessment."""
        return {"level": "unknown", "confidence": reasoning.overall_confidence}

    async def _on_generate_recommendations(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        reflection: ReflectionResult,
    ) -> list[str]:
        """Hook for subclass recommendations."""
        return []

    async def _on_structured_output(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        tool_results: list[ToolResult],
    ) -> dict[str, Any]:
        """Hook for subclass structured output."""
        return {"agent_id": self.agent_id, "tool_count": len(tool_results)}

    async def _on_update_memory(self, context: AgentContext, report: AgentReport) -> None:
        """Hook for subclass memory persistence."""

    # ------------------------------------------------------------------
    # Reasoning phase handlers (override for domain logic)
    # ------------------------------------------------------------------

    async def _phase_observe(
        self,
        context: AgentContext,
        phase: ReasoningPhase,
    ) -> ReasoningStep:
        caps = await self._capability_registry.capability_names()
        content = (
            f"Observing request with {len(caps)} capabilities; "
            f"climate_attached={context.climate_state is not None}"
        )
        return ReasoningStep(
            phase=phase,
            content=content,
            confidence=0.6,
            metadata={"capabilities": caps},
        )

    async def _phase_think(
        self,
        context: AgentContext,
        phase: ReasoningPhase,
    ) -> ReasoningStep:
        matched = await self._capability_registry.match_query(context.query)
        confidence = matched[0].matches_query(context.query) if matched else 0.3
        return ReasoningStep(
            phase=phase,
            content=f"Analyzing query against {len(matched)} matched capabilities",
            confidence=confidence,
            metadata={"matched": [c.capability_id for c in matched]},
        )

    async def _phase_act(
        self,
        context: AgentContext,
        phase: ReasoningPhase,
    ) -> ReasoningStep:
        tools = self._tool_manager.tool_names
        recommended = context.request.tool_names or tools[:3]
        return ReasoningStep(
            phase=phase,
            content=f"Planning tool execution ({len(recommended)} tools)",
            confidence=0.7,
            metadata={"recommended_tools": recommended},
        )

    async def _phase_reflect(
        self,
        context: AgentContext,
        phase: ReasoningPhase,
    ) -> ReasoningStep:
        return ReasoningStep(
            phase=phase,
            content="Reviewing reasoning completeness",
            confidence=0.65,
            metadata={"needs_followup": False},
        )

    async def _phase_verify(
        self,
        context: AgentContext,
        phase: ReasoningPhase,
    ) -> ReasoningStep:
        verified = bool(context.query) and not context.cancelled
        return ReasoningStep(
            phase=phase,
            content="Verification step completed" if verified else "Verification failed",
            confidence=0.9 if verified else 0.2,
            metadata={"verified": verified},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _report_to_response(
        self,
        report: AgentReport,
        *,
        memory_refs: list[str] | None = None,
        reasoning: ReasoningResult | None = None,
        delegated_to: list[str] | None = None,
    ) -> AgentResponse:
        metrics_payload: dict[str, Any] = {}
        if self._last_metrics:
            metrics_payload = self._last_metrics.metrics.model_dump()

        return AgentResponse(
            request_id=report.request_id,
            agent_id=self.agent_id,
            content=report.to_response_content(),
            status=AgentStatus.COMPLETED,
            structured_output=report.structured_output,
            tool_outputs=report.tool_outputs,
            memory_references=memory_refs or report.references,
            delegated_to=delegated_to or [],
            reasoning_trace=report.reasoning,
            metadata={
                "report_id": report.report_id,
                "confidence": report.confidence,
                "risk": report.risk,
                "recommendations": report.recommendations,
                "metrics": metrics_payload,
                **report.metadata,
            },
        )

    def register_tool(self, tool: AbstractTool) -> None:
        super().register_tool(tool)
        self._tool_manager.register(tool)
