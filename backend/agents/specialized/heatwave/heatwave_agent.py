"""Heatwave Agent — autonomous thermal stress and heatwave analysis."""

from __future__ import annotations

from typing import Any

from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import AgentResponse
from backend.agents.specialized.agent_capabilities import AgentCapability, CapabilityCategory
from backend.agents.specialized.agent_context import AgentContext, AgentReport
from backend.agents.specialized.agent_execution import (
    AgentCommunicationInterface,
    SpecializedRLEngineInterface,
)
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.specialized.agent_tools import ToolCallSpec
from backend.agents.specialized.base_specialized_agent import BaseSpecializedAgent
from backend.agents.specialized.heatwave.heatwave_context import HeatwaveInputs
from backend.agents.specialized.heatwave.heatwave_decision_engine import HeatwaveDecisionEngine
from backend.agents.specialized.heatwave.heatwave_metrics import HeatwaveMetricsCollector
from backend.agents.specialized.heatwave.heatwave_models import (
    HEATWAVE_AGENT_ID,
    HeatRiskLevel,
    HeatwaveSeverity,
)
from backend.agents.specialized.heatwave.heatwave_reasoning import HeatwaveReasoningEngine
from backend.agents.specialized.heatwave.heatwave_reflection import HeatwaveReflectionEngine
from backend.agents.specialized.heatwave.heatwave_report import HeatwaveReport, HeatwaveReportBuilder
from backend.agents.specialized.heatwave.heatwave_tools import ALL_HEATWAVE_TOOL_NAMES, create_heatwave_tools
from backend.agents.specialized.heatwave.heatwave_validator import HeatwaveValidator
from backend.agents.state.workflow_state import WorkflowState
from backend.agents.supervisor.execution_context import DigitalTwinInterface
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.rl import RLOptimizationError, RLOptimizationService
from backend.utils.enums import AgentStatus
from backend.utils.errors import AgentInvocationError

logger = get_logger(__name__)


class HeatwaveAgent(BaseSpecializedAgent):
    """
    Production-grade autonomous heatwave and urban thermal stress agent.

    Analyzes heatwave evolution, urban heat island effects, human vulnerability,
    and critical infrastructure risk. Produces unified DecisionRequest objects
    and optionally optimizes mitigation via RLOptimizationService.
    """

    AGENT_ID = HEATWAVE_AGENT_ID

    def __init__(
        self,
        *,
        memory: MemoryManager,
        rl_engine: SpecializedRLEngineInterface | None = None,
        rl_service: RLOptimizationService | None = None,
        agent_communication: AgentCommunicationInterface | None = None,
        digital_twin: DigitalTwinInterface | None = None,
        confidence_threshold: float = 0.45,
    ) -> None:
        super().__init__(
            HEATWAVE_AGENT_ID,
            description="Autonomous heatwave detection, thermal stress, and urban heat island analysis agent",
            memory=memory,
            tools=create_heatwave_tools(),
            rl_engine=rl_engine,
            agent_communication=agent_communication,
            digital_twin=digital_twin,
            confidence_threshold=confidence_threshold,
        )
        self._rl_service = rl_service
        self._heatwave_reasoning = HeatwaveReasoningEngine(agent_id=HEATWAVE_AGENT_ID)
        self._heatwave_reflection = HeatwaveReflectionEngine(
            agent_id=HEATWAVE_AGENT_ID,
            confidence_threshold=confidence_threshold,
        )
        self._heatwave_validator = HeatwaveValidator(agent_id=HEATWAVE_AGENT_ID)
        self._decision_engine = HeatwaveDecisionEngine(agent_id=HEATWAVE_AGENT_ID)
        self._report_builder = HeatwaveReportBuilder(agent_id=HEATWAVE_AGENT_ID)
        self._last_heatwave_report: HeatwaveReport | None = None
        self._last_heatwave_metrics: HeatwaveMetricsCollector | None = None

    @property
    def last_heatwave_report(self) -> HeatwaveReport | None:
        return self._last_heatwave_report

    @property
    def last_heatwave_metrics(self) -> HeatwaveMetricsCollector | None:
        return self._last_heatwave_metrics

    @classmethod
    async def create(
        cls,
        memory: MemoryManager,
        *,
        rl_engine: SpecializedRLEngineInterface | None = None,
        rl_service: RLOptimizationService | None = None,
        agent_communication: AgentCommunicationInterface | None = None,
        digital_twin: DigitalTwinInterface | None = None,
    ) -> HeatwaveAgent:
        agent = cls(
            memory=memory,
            rl_engine=rl_engine,
            rl_service=rl_service,
            agent_communication=agent_communication,
            digital_twin=digital_twin,
        )
        await agent.initialize()
        return agent

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    async def declare_capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                capability_id="heatwave_detection",
                name="Heatwave Detection",
                category=CapabilityCategory.MONITORING,
                keywords=["heatwave", "heat", "thermal", "detect"],
                required_tools=["temperature_tool", "humidity_tool", "forecast_tool"],
            ),
            AgentCapability(
                capability_id="urban_heat_island",
                name="Urban Heat Island Analysis",
                category=CapabilityCategory.ANALYSIS,
                keywords=["uhi", "urban", "heat island", "lst"],
                required_tools=["lst_tool", "urban_density_tool", "ndvi_tool"],
            ),
            AgentCapability(
                capability_id="heat_stress_assessment",
                name="Heat Stress Assessment",
                category=CapabilityCategory.ANALYSIS,
                keywords=["stress", "heat index", "discomfort", "thermal"],
                required_tools=["temperature_tool", "humidity_tool", "health_risk_tool"],
            ),
            AgentCapability(
                capability_id="wet_bulb_estimation",
                name="Wet Bulb Temperature Estimation",
                category=CapabilityCategory.ANALYSIS,
                keywords=["wet bulb", "humidity", "wbgt"],
                required_tools=["humidity_tool"],
            ),
            AgentCapability(
                capability_id="human_vulnerability",
                name="Human Vulnerability Assessment",
                category=CapabilityCategory.ANALYSIS,
                keywords=["vulnerability", "population", "health", "elderly"],
                required_tools=["population_tool", "health_risk_tool"],
            ),
            AgentCapability(
                capability_id="infrastructure_heat_risk",
                name="Critical Infrastructure Heat Risk",
                category=CapabilityCategory.ANALYSIS,
                keywords=["infrastructure", "power", "hospital", "grid"],
                required_tools=["temperature_tool", "lst_tool"],
            ),
            AgentCapability(
                capability_id="urban_cooling_recommendation",
                name="Urban Cooling Recommendation",
                category=CapabilityCategory.PLANNING,
                keywords=["cooling", "shade", "green", "mitigation"],
                required_tools=["ndvi_tool", "urban_density_tool"],
            ),
            AgentCapability(
                capability_id="thermal_trend_analysis",
                name="Thermal Trend Analysis",
                category=CapabilityCategory.FORECAST,
                keywords=["trend", "temperature", "forecast", "trajectory"],
                required_tools=["temperature_tool", "forecast_tool"],
                requires_forecast=True,
            ),
            AgentCapability(
                capability_id="heatwave_severity",
                name="Heatwave Severity Classification",
                category=CapabilityCategory.INTERPRETATION,
                keywords=["severity", "extreme", "classification"],
            ),
            AgentCapability(
                capability_id="heatwave_probability",
                name="Heatwave Probability Forecast",
                category=CapabilityCategory.PREDICTION,
                keywords=["probability", "likelihood", "forecast"],
                required_tools=["forecast_tool", "historical_heatwave_tool"],
            ),
        ]

    # ------------------------------------------------------------------
    # Internal LangGraph-style workflow
    # ------------------------------------------------------------------

    async def invoke(self, request: AgentRequest) -> AgentResponse:
        """
        Heatwave workflow:
        Observe → Analyze (tools) → Reason → Reflect → Validate →
        Decision Framework → RL Service → Report
        """
        if not self._initialized:
            await self.initialize()

        metrics = HeatwaveMetricsCollector(agent_id=self.agent_id, request_id=request.request_id)
        self._last_metrics = metrics
        self._last_heatwave_metrics = metrics
        self._status = AgentStatus.REASONING

        try:
            context = await self._run_observe(request)
            tool_results = await self._run_analyze(context, metrics)
            reasoning, _signals = await self._run_reason(context, tool_results, metrics)
            reflection = await self._run_reflect(context, reasoning, tool_results)
            validation = await self._run_validate(context, tool_results)
            decision = await self._run_decision_engine(context, reasoning, reflection)
            metrics.record_decision_request()

            if decision.need_other_agents and self._agent_communication:
                await self.call_other_agents(context, decision.need_other_agents, request)

            rl_response = await self._run_rl_service(decision, metrics)

            if decision.need_rl and self._rl_engine and not rl_response:
                await self.request_rl(context)
                metrics.record_rl_call()

            heatwave_report = await self._run_report(
                context, reasoning, tool_results, reflection, validation, decision, rl_response,
            )
            self._last_heatwave_report = heatwave_report
            self._last_report = self._to_agent_report(heatwave_report)

            severity = HeatwaveSeverity(reasoning.metadata.get("severity", HeatwaveSeverity.NONE.value))
            metrics.set_severity(severity)
            metrics.set_risk_level(heatwave_report.risk_level)
            metrics.set_confidence(heatwave_report.confidence)
            heat_metrics = metrics.finalize_heatwave()
            heatwave_report.metrics = heat_metrics

            memory_refs = await self.update_memory(context, self._last_report)
            await self._persist_heatwave_report(context, heatwave_report)
            await self.update_state(context, self._last_report)

            self._status = AgentStatus.COMPLETED
            return self._heatwave_report_to_response(heatwave_report, heat_metrics, memory_refs)

        except Exception as exc:
            self._status = AgentStatus.FAILED
            metrics.finalize()
            logger.error("heatwave_agent_failed", request_id=request.request_id, error=str(exc))
            raise AgentInvocationError(
                f"Heatwave agent failed: {exc}",
                details={"agent_id": self.agent_id, "request_id": request.request_id},
            ) from exc

    async def _run_observe(self, request: AgentRequest) -> AgentContext:
        context = await self.retrieve_context(request)
        inputs = HeatwaveInputs.from_request_context(request.context)
        inputs.climate_state_available = request.climate_state is not None
        inputs.forecast_available = bool(
            request.context.get("forecast_available")
            or inputs.temperature.forecast_max_24h_c
        )
        inputs.digital_twin_available = bool(
            request.context.get("digital_twin_available")
            or request.context.get("twin_id")
        )
        context.metadata["heatwave_inputs"] = inputs
        context.metadata["requires_climate_state"] = True

        await self.preprocess(context)
        await self.retrieve_memory(context)
        await self.retrieve_climate_state(context)
        await self.retrieve_forecast(context)
        await self._hydrate_digital_twin(context)

        if context.digital_twin_state:
            context.request.context["digital_twin_state"] = context.digital_twin_state

        logger.info("heatwave_observe_complete", region_id=inputs.region_id)
        return context

    async def _run_analyze(
        self,
        context: AgentContext,
        metrics: HeatwaveMetricsCollector,
    ) -> list[ToolResult]:
        tool_specs = await self._build_tool_specs(context)
        results = await self.execute_tools(context, tool_specs, parallel=True)
        context.tool_outputs = results
        metrics.record_tools(len(results), sum(r.duration_ms for r in results))
        for r in results:
            if r.success:
                metrics.record_tool_name(r.tool_name)
        return results

    async def _run_reason(
        self,
        context: AgentContext,
        tool_results: list[ToolResult],
        metrics: HeatwaveMetricsCollector,
    ) -> tuple[ReasoningResult, Any]:
        reasoning, signals = await self._heatwave_reasoning.run(context, tool_results)
        metrics.record_reasoning(sum(s.duration_ms for s in reasoning.steps))
        return reasoning, signals

    async def _run_reflect(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        tool_results: list[ToolResult],
    ) -> Any:
        reflection = await self._heatwave_reflection.evaluate(context, reasoning, tool_results)
        self._last_metrics and self._last_metrics.record_reflection()
        return reflection

    async def _run_validate(
        self,
        context: AgentContext,
        tool_results: list[ToolResult],
    ) -> Any:
        validation = await self._heatwave_validator.validate(context, tool_results)
        self._last_metrics and self._last_metrics.record_validation()
        return validation

    async def _run_decision_engine(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        reflection: Any,
    ) -> DecisionRequest:
        return await self._decision_engine.evaluate(context, reasoning, reflection)

    async def _run_rl_service(
        self,
        decision: DecisionRequest,
        metrics: HeatwaveMetricsCollector,
    ) -> DecisionResponse | None:
        if not decision.need_rl or not self._rl_service:
            return None
        try:
            rl_response = await self._rl_service.optimize(decision)
            metrics.record_rl_call()
            return rl_response
        except RLOptimizationError as exc:
            logger.warning(
                "heatwave_rl_optimization_failed",
                decision_id=decision.decision_id,
                error=str(exc),
            )
            return None

    async def _run_report(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        tool_results: list[ToolResult],
        reflection: Any,
        validation: Any,
        decision: DecisionRequest,
        rl_response: DecisionResponse | None = None,
    ) -> HeatwaveReport:
        return self._report_builder.build(
            context,
            reasoning,
            tool_results,
            reflection,
            validation,
            decision,
            rl_response,
        )

    # ------------------------------------------------------------------
    # Tool selection
    # ------------------------------------------------------------------

    async def _build_tool_specs(self, context: AgentContext) -> list[ToolCallSpec]:
        params = dict(context.request.context)
        params["digital_twin_state"] = context.digital_twin_state
        return [
            ToolCallSpec(tool_name=name, parameters=params)
            for name in ALL_HEATWAVE_TOOL_NAMES
            if self.tool_manager.has_tool(name)
        ]

    async def _on_select_tools(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
    ) -> list[ToolCallSpec]:
        return await self._build_tool_specs(context)

    async def required_inputs(self) -> list[str]:
        return ["query"]

    # ------------------------------------------------------------------
    # Memory / report helpers
    # ------------------------------------------------------------------

    async def _persist_heatwave_report(self, context: AgentContext, report: HeatwaveReport) -> None:
        from backend.agents.memory.memory_types import MemoryDomain, MemoryStoreRequest

        session_id = context.user.session_id
        key = f"heatwave_report:{context.request_id}"
        await self.memory_manager.store(
            MemoryStoreRequest(
                domain=MemoryDomain.WORKING,
                key=key,
                value=report.model_dump(),
                session_id=session_id,
                metadata={"agent_id": self.agent_id, "type": "heatwave_report"},
            ),
        )
        self._last_metrics and self._last_metrics.record_memory_write()

    def _to_agent_report(self, heatwave_report: HeatwaveReport) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            request_id=heatwave_report.request_id,
            summary=heatwave_report.executive_summary,
            reasoning=heatwave_report.reasoning,
            risk={
                "level": heatwave_report.risk_level.value,
                "severity": heatwave_report.severity.value,
                "classification": heatwave_report.classification.value,
            },
            confidence=heatwave_report.confidence,
            recommendations=heatwave_report.recommendations,
            references=heatwave_report.references,
            tool_outputs=heatwave_report.tool_outputs,
            structured_output=heatwave_report.model_dump(),
            metadata={
                "heatwave_report_id": heatwave_report.report_id,
                "need_rl": heatwave_report.need_rl,
                "need_simulation": heatwave_report.need_simulation,
                "need_other_agents": heatwave_report.need_other_agents,
            },
        )

    def _heatwave_report_to_response(
        self,
        report: HeatwaveReport,
        metrics: Any,
        memory_refs: list[str],
    ) -> AgentResponse:
        return AgentResponse(
            request_id=report.request_id,
            agent_id=self.agent_id,
            content=report.executive_summary,
            status=AgentStatus.COMPLETED,
            structured_output=report.model_dump(),
            tool_outputs=report.tool_outputs,
            memory_references=memory_refs,
            delegated_to=report.need_other_agents,
            reasoning_trace=report.reasoning,
            metadata={
                "heatwave_report_id": report.report_id,
                "risk_level": report.risk_level.value,
                "severity": report.severity.value,
                "classification": report.classification.value,
                "confidence": report.confidence,
                "heat_index_c": report.heat_index.heat_index_c,
                "wet_bulb_c": report.wet_bulb_c,
                "uhi_score": report.uhi_score,
                "probability": report.probability.model_dump(),
                "population_at_risk": [p.model_dump() for p in report.population_at_risk],
                "recommendations": report.recommendations,
                "need_rl": report.need_rl,
                "need_simulation": report.need_simulation,
                "decision_request": report.decision_request.model_dump() if report.decision_request else {},
                "rl_response": report.rl_response.model_dump() if report.rl_response else None,
                "metrics": metrics.model_dump(),
            },
        )

    async def as_graph_node(self, state: WorkflowState) -> dict[str, Any]:
        """Expose heatwave agent as a LangGraph node."""
        update = await super().as_graph_node(state)
        if self._last_heatwave_report:
            update["metadata"] = {
                **update.get("metadata", {}),
                "heatwave_risk_level": self._last_heatwave_report.risk_level.value,
                "heatwave_severity": self._last_heatwave_report.severity.value,
                "heatwave_classification": self._last_heatwave_report.classification.value,
            }
        return update
