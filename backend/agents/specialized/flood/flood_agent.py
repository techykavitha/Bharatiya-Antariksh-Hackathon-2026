"""Flood Agent — reference implementation for specialized climate agents."""

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
from backend.agents.specialized.flood.flood_context import FloodInputs
from backend.agents.specialized.flood.flood_decision_engine import FloodDecisionEngine
from backend.agents.specialized.flood.flood_metrics import FloodMetricsCollector
from backend.agents.specialized.flood.flood_models import FLOOD_AGENT_ID, FloodSeverity
from backend.agents.specialized.flood.flood_reasoning import FloodReasoningEngine
from backend.agents.specialized.flood.flood_reflection import FloodReflectionEngine
from backend.agents.specialized.flood.flood_report import FloodReport, FloodReportBuilder
from backend.agents.specialized.flood.flood_tools import ALL_FLOOD_TOOL_NAMES, create_flood_tools
from backend.agents.specialized.flood.flood_validator import FloodValidator
from backend.agents.state.workflow_state import WorkflowState
from backend.agents.supervisor.execution_context import DigitalTwinInterface
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger
from backend.utils.enums import AgentStatus
from backend.utils.errors import AgentInvocationError

logger = get_logger(__name__)


class FloodAgent(BaseSpecializedAgent):
    """
    Production-grade autonomous flood risk analysis agent.

    Serves as the reference implementation for all future specialized
    climate agents in the Hyperion ecosystem.
    """

    AGENT_ID = FLOOD_AGENT_ID

    def __init__(
        self,
        *,
        memory: MemoryManager,
        rl_engine: SpecializedRLEngineInterface | None = None,
        agent_communication: AgentCommunicationInterface | None = None,
        digital_twin: DigitalTwinInterface | None = None,
        confidence_threshold: float = 0.45,
    ) -> None:
        super().__init__(
            FLOOD_AGENT_ID,
            description="Autonomous flood risk assessment and inundation analysis agent",
            memory=memory,
            tools=create_flood_tools(),
            rl_engine=rl_engine,
            agent_communication=agent_communication,
            digital_twin=digital_twin,
            confidence_threshold=confidence_threshold,
        )
        self._flood_reasoning = FloodReasoningEngine(agent_id=FLOOD_AGENT_ID)
        self._flood_reflection = FloodReflectionEngine(
            agent_id=FLOOD_AGENT_ID,
            confidence_threshold=confidence_threshold,
        )
        self._flood_validator = FloodValidator(agent_id=FLOOD_AGENT_ID)
        self._decision_engine = FloodDecisionEngine(agent_id=FLOOD_AGENT_ID)
        self._report_builder = FloodReportBuilder(agent_id=FLOOD_AGENT_ID)
        self._last_flood_report: FloodReport | None = None
        self._last_flood_metrics: FloodMetricsCollector | None = None

    @property
    def last_flood_report(self) -> FloodReport | None:
        return self._last_flood_report

    @property
    def last_flood_metrics(self) -> FloodMetricsCollector | None:
        return self._last_flood_metrics

    @classmethod
    async def create(
        cls,
        memory: MemoryManager,
        *,
        rl_engine: SpecializedRLEngineInterface | None = None,
        agent_communication: AgentCommunicationInterface | None = None,
        digital_twin: DigitalTwinInterface | None = None,
    ) -> FloodAgent:
        agent = cls(
            memory=memory,
            rl_engine=rl_engine,
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
                capability_id="flood_risk_assessment",
                name="Flood Risk Assessment",
                category=CapabilityCategory.ANALYSIS,
                keywords=["flood", "risk", "inundation", "assess"],
                required_tools=["rainfall_tool", "river_tool", "terrain_tool"],
            ),
            AgentCapability(
                capability_id="flash_flood_detection",
                name="Flash Flood Detection",
                category=CapabilityCategory.MONITORING,
                keywords=["flash", "sudden", "intensity", "pluvial"],
                required_tools=["rainfall_tool", "terrain_tool"],
            ),
            AgentCapability(
                capability_id="river_flood_analysis",
                name="River Flood Analysis",
                category=CapabilityCategory.ANALYSIS,
                keywords=["river", "overflow", "bank", "discharge"],
                required_tools=["river_tool", "historical_flood_tool"],
            ),
            AgentCapability(
                capability_id="urban_flood_analysis",
                name="Urban Flood Analysis",
                category=CapabilityCategory.ANALYSIS,
                keywords=["urban", "city", "drainage", "pluvial"],
                required_tools=["terrain_tool", "population_tool"],
            ),
            AgentCapability(
                capability_id="coastal_flood_analysis",
                name="Coastal Flood Analysis",
                category=CapabilityCategory.ANALYSIS,
                keywords=["coastal", "surge", "sea", "tide"],
                required_tools=["forecast_tool", "digital_twin_tool"],
            ),
            AgentCapability(
                capability_id="reservoir_overflow",
                name="Reservoir Overflow Assessment",
                category=CapabilityCategory.ANALYSIS,
                keywords=["reservoir", "dam", "spillway", "overflow"],
                required_tools=["reservoir_tool"],
            ),
            AgentCapability(
                capability_id="rainfall_impact",
                name="Rainfall Impact Assessment",
                category=CapabilityCategory.FORECAST,
                keywords=["rainfall", "precipitation", "rain"],
                required_tools=["rainfall_tool", "forecast_tool"],
                requires_forecast=True,
            ),
            AgentCapability(
                capability_id="flood_severity",
                name="Flood Severity Classification",
                category=CapabilityCategory.INTERPRETATION,
                keywords=["severity", "major", "catastrophic"],
            ),
            AgentCapability(
                capability_id="flood_probability",
                name="Flood Probability",
                category=CapabilityCategory.PREDICTION,
                keywords=["probability", "likelihood", "chance"],
            ),
            AgentCapability(
                capability_id="population_exposure",
                name="Affected Population Estimation",
                category=CapabilityCategory.ANALYSIS,
                keywords=["population", "affected", "exposure", "people"],
                required_tools=["population_tool"],
            ),
        ]

    # ------------------------------------------------------------------
    # Internal LangGraph-style workflow
    # ------------------------------------------------------------------

    async def invoke(self, request: AgentRequest) -> AgentResponse:
        """
        Flood-specific workflow:
        Observe → Analyze (tools) → Reason → Reflect → Validate →
        Decision Engine → Report
        """
        if not self._initialized:
            await self.initialize()

        metrics = FloodMetricsCollector(agent_id=self.agent_id, request_id=request.request_id)
        self._last_metrics = metrics
        self._last_flood_metrics = metrics
        self._status = AgentStatus.REASONING

        try:
            context = await self._run_observe(request)
            tool_results = await self._run_analyze(context, metrics)
            reasoning, signals = await self._run_reason(context, tool_results, metrics)
            reflection = await self._run_reflect(context, reasoning, tool_results)
            validation = await self._run_validate(context, tool_results)
            decision = await self._run_decision_engine(context, reasoning, reflection)
            metrics.record_decision_request()

            if decision.suggested_agents and self._agent_communication:
                await self.call_other_agents(context, decision.suggested_agents, request)

            if decision.need_rl and self._rl_engine:
                await self.request_rl(context)

            flood_report = await self._run_report(
                context, reasoning, tool_results, reflection, validation, decision,
            )
            self._last_flood_report = flood_report
            self._last_report = self._to_agent_report(flood_report)

            severity = FloodSeverity(reasoning.metadata.get("severity", FloodSeverity.NONE.value))
            metrics.set_severity(severity)
            metrics.set_risk_level(flood_report.risk_level)
            metrics.set_confidence(flood_report.confidence)
            flood_metrics = metrics.finalize_flood()
            flood_report.metrics = flood_metrics

            memory_refs = await self.update_memory(context, self._last_report)
            await self._persist_flood_report(context, flood_report)
            await self.update_state(context, self._last_report)

            self._status = AgentStatus.COMPLETED
            return self._flood_report_to_response(flood_report, flood_metrics, memory_refs)

        except Exception as exc:
            self._status = AgentStatus.FAILED
            metrics.finalize()
            logger.error("flood_agent_failed", request_id=request.request_id, error=str(exc))
            raise AgentInvocationError(
                f"Flood agent failed: {exc}",
                details={"agent_id": self.agent_id, "request_id": request.request_id},
            ) from exc

    async def _run_observe(self, request: AgentRequest) -> AgentContext:
        context = await self.retrieve_context(request)
        inputs = FloodInputs.from_request_context(request.context)
        inputs.climate_state_available = request.climate_state is not None
        inputs.forecast_available = bool(
            request.context.get("forecast_available")
            or inputs.rainfall.forecast_24h_mm
        )
        inputs.digital_twin_available = bool(
            request.context.get("digital_twin_available")
            or request.context.get("twin_id")
        )
        context.metadata["flood_inputs"] = inputs
        context.metadata["requires_climate_state"] = True

        await self.preprocess(context)
        await self.retrieve_memory(context)
        await self.retrieve_climate_state(context)
        await self.retrieve_forecast(context)
        await self._hydrate_digital_twin(context)

        if context.digital_twin_state:
            context.request.context["digital_twin_state"] = context.digital_twin_state

        logger.info("flood_observe_complete", region_id=inputs.region_id)
        return context

    async def _run_analyze(
        self,
        context: AgentContext,
        metrics: FloodMetricsCollector,
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
        metrics: FloodMetricsCollector,
    ) -> tuple[ReasoningResult, Any]:
        reasoning, signals = await self._flood_reasoning.run(context, tool_results)
        metrics.record_reasoning(sum(s.duration_ms for s in reasoning.steps))
        return reasoning, signals

    async def _run_reflect(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        tool_results: list[ToolResult],
    ) -> Any:
        reflection = await self._flood_reflection.evaluate(context, reasoning, tool_results)
        self._last_metrics and self._last_metrics.record_reflection()
        return reflection

    async def _run_validate(
        self,
        context: AgentContext,
        tool_results: list[ToolResult],
    ) -> Any:
        validation = await self._flood_validator.validate(context, tool_results)
        self._last_metrics and self._last_metrics.record_validation()
        return validation

    async def _run_decision_engine(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        reflection: Any,
    ) -> Any:
        return await self._decision_engine.evaluate(context, reasoning, reflection)

    async def _run_report(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        tool_results: list[ToolResult],
        reflection: Any,
        validation: Any,
        decision: Any,
    ) -> FloodReport:
        return self._report_builder.build(
            context,
            reasoning,
            tool_results,
            reflection,
            validation,
            decision,
        )

    # ------------------------------------------------------------------
    # Tool selection
    # ------------------------------------------------------------------

    async def _build_tool_specs(self, context: AgentContext) -> list[ToolCallSpec]:
        params = dict(context.request.context)
        params["digital_twin_state"] = context.digital_twin_state
        return [
            ToolCallSpec(tool_name=name, parameters=params)
            for name in ALL_FLOOD_TOOL_NAMES
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

    async def _persist_flood_report(self, context: AgentContext, report: FloodReport) -> None:
        from backend.agents.memory.memory_types import MemoryDomain, MemoryStoreRequest

        session_id = context.user.session_id
        key = f"flood_report:{context.request_id}"
        await self.memory_manager.store(
            MemoryStoreRequest(
                domain=MemoryDomain.WORKING,
                key=key,
                value=report.model_dump(),
                session_id=session_id,
                metadata={"agent_id": self.agent_id, "type": "flood_report"},
            ),
        )
        self._last_metrics and self._last_metrics.record_memory_write()

    def _to_agent_report(self, flood_report: FloodReport) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            request_id=flood_report.request_id,
            summary=flood_report.executive_summary,
            reasoning=flood_report.reasoning,
            risk={
                "level": flood_report.risk_level.value,
                "severity": flood_report.severity.value,
                "flood_type": flood_report.flood_type.value,
            },
            confidence=flood_report.confidence,
            recommendations=flood_report.recommendations,
            references=flood_report.references,
            tool_outputs=flood_report.tool_outputs,
            structured_output=flood_report.model_dump(),
            metadata={
                "flood_report_id": flood_report.report_id,
                "need_rl": flood_report.need_rl,
                "need_simulation": flood_report.need_simulation,
                "need_other_agents": flood_report.need_other_agents,
            },
        )

    def _flood_report_to_response(
        self,
        report: FloodReport,
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
                "flood_report_id": report.report_id,
                "risk_level": report.risk_level.value,
                "severity": report.severity.value,
                "flood_type": report.flood_type.value,
                "confidence": report.confidence,
                "expected_water_depth_m": report.expected_water_depth_m,
                "probability": report.probability.model_dump(),
                "affected_districts": [d.model_dump() for d in report.affected_districts],
                "recommendations": report.recommendations,
                "need_rl": report.need_rl,
                "need_simulation": report.need_simulation,
                "decision_request": report.decision_request.model_dump(),
                "metrics": metrics.model_dump(),
            },
        )

    async def as_graph_node(self, state: WorkflowState) -> dict[str, Any]:
        """Expose flood agent as a LangGraph node."""
        update = await super().as_graph_node(state)
        if self._last_flood_report:
            update["metadata"] = {
                **update.get("metadata", {}),
                "flood_risk_level": self._last_flood_report.risk_level.value,
                "flood_severity": self._last_flood_report.severity.value,
                "flood_type": self._last_flood_report.flood_type.value,
            }
        return update
