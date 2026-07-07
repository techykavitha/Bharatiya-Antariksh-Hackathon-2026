"""Water Resource Agent — central coordination for India's water management."""

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
from backend.agents.specialized.water_resource.water_context import WaterInputs
from backend.agents.specialized.water_resource.water_decision_engine import WaterDecisionEngine
from backend.agents.specialized.water_resource.water_metrics import WaterMetricsCollector
from backend.agents.specialized.water_resource.water_models import WATER_RESOURCE_AGENT_ID, WaterStressLevel
from backend.agents.specialized.water_resource.water_reasoning import WaterReasoningEngine
from backend.agents.specialized.water_resource.water_reflection import WaterReflectionEngine
from backend.agents.specialized.water_resource.water_report import WaterReportBuilder, WaterResourceReport
from backend.agents.specialized.water_resource.water_tools import ALL_WATER_TOOL_NAMES, create_water_tools
from backend.agents.specialized.water_resource.water_validator import WaterValidator
from backend.agents.state.workflow_state import WorkflowState
from backend.agents.supervisor.execution_context import DigitalTwinInterface
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger
from backend.utils.enums import AgentStatus
from backend.utils.errors import AgentInvocationError

logger = get_logger(__name__)


class WaterResourceAgent(BaseSpecializedAgent):
    """
    Production-grade autonomous water resource management agent.

    Central coordination point between Flood, Agriculture, Urban Planning,
    and future RL optimization for India's water availability.
    """

    AGENT_ID = WATER_RESOURCE_AGENT_ID

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
            WATER_RESOURCE_AGENT_ID,
            description="Autonomous water resource management and reservoir operations agent",
            memory=memory,
            tools=create_water_tools(),
            rl_engine=rl_engine,
            agent_communication=agent_communication,
            digital_twin=digital_twin,
            confidence_threshold=confidence_threshold,
        )
        self._water_reasoning = WaterReasoningEngine(agent_id=WATER_RESOURCE_AGENT_ID)
        self._water_reflection = WaterReflectionEngine(
            agent_id=WATER_RESOURCE_AGENT_ID,
            confidence_threshold=confidence_threshold,
        )
        self._water_validator = WaterValidator(agent_id=WATER_RESOURCE_AGENT_ID)
        self._decision_engine = WaterDecisionEngine(agent_id=WATER_RESOURCE_AGENT_ID)
        self._report_builder = WaterReportBuilder(agent_id=WATER_RESOURCE_AGENT_ID)
        self._last_water_report: WaterResourceReport | None = None
        self._last_water_metrics: WaterMetricsCollector | None = None

    @property
    def last_water_report(self) -> WaterResourceReport | None:
        return self._last_water_report

    @property
    def last_water_metrics(self) -> WaterMetricsCollector | None:
        return self._last_water_metrics

    @classmethod
    async def create(
        cls,
        memory: MemoryManager,
        *,
        rl_engine: SpecializedRLEngineInterface | None = None,
        agent_communication: AgentCommunicationInterface | None = None,
        digital_twin: DigitalTwinInterface | None = None,
    ) -> WaterResourceAgent:
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
                capability_id="reservoir_monitoring",
                name="Reservoir Monitoring",
                category=CapabilityCategory.MONITORING,
                keywords=["reservoir", "dam", "storage", "level", "spillway"],
                required_tools=["reservoir_tool"],
            ),
            AgentCapability(
                capability_id="reservoir_overflow",
                name="Reservoir Overflow Assessment",
                category=CapabilityCategory.ANALYSIS,
                keywords=["overflow", "spillway", "release", "flood"],
                required_tools=["reservoir_tool", "river_tool"],
            ),
            AgentCapability(
                capability_id="reservoir_release_planning",
                name="Reservoir Release Planning",
                category=CapabilityCategory.PLANNING,
                keywords=["release", "outflow", "scheduling", "spillway"],
                required_tools=["reservoir_tool", "forecast_tool"],
            ),
            AgentCapability(
                capability_id="river_basin_analysis",
                name="River Basin Analysis",
                category=CapabilityCategory.ANALYSIS,
                keywords=["river", "basin", "discharge", "flow"],
                required_tools=["river_tool"],
            ),
            AgentCapability(
                capability_id="groundwater_assessment",
                name="Groundwater Assessment",
                category=CapabilityCategory.ANALYSIS,
                keywords=["groundwater", "aquifer", "recharge", "extraction"],
                required_tools=["groundwater_tool"],
            ),
            AgentCapability(
                capability_id="water_availability_forecast",
                name="Water Availability Forecast",
                category=CapabilityCategory.FORECAST,
                keywords=["availability", "supply", "forecast", "monsoon"],
                required_tools=["rainfall_tool", "forecast_tool", "reservoir_tool"],
                requires_forecast=True,
            ),
            AgentCapability(
                capability_id="water_stress_detection",
                name="Water Stress Detection",
                category=CapabilityCategory.MONITORING,
                keywords=["stress", "scarcity", "drought", "deficit"],
                required_tools=["demand_tool", "reservoir_tool"],
            ),
            AgentCapability(
                capability_id="water_demand_estimation",
                name="Water Demand Estimation",
                category=CapabilityCategory.ANALYSIS,
                keywords=["demand", "consumption", "allocation"],
                required_tools=["demand_tool", "population_tool"],
            ),
            AgentCapability(
                capability_id="urban_water_supply",
                name="Urban Water Supply",
                category=CapabilityCategory.ANALYSIS,
                keywords=["urban", "city", "supply", "municipal"],
                required_tools=["population_tool", "demand_tool"],
            ),
            AgentCapability(
                capability_id="agricultural_water_demand",
                name="Agricultural Water Demand",
                category=CapabilityCategory.ANALYSIS,
                keywords=["agriculture", "irrigation", "crop", "farm"],
                required_tools=["demand_tool", "soil_moisture_tool"],
            ),
            AgentCapability(
                capability_id="inter_basin_dependency",
                name="Inter-Basin Dependency Analysis",
                category=CapabilityCategory.ANALYSIS,
                keywords=["inter-basin", "transfer", "dependency", "linking"],
                required_tools=["river_tool", "historical_water_tool"],
            ),
        ]

    # ------------------------------------------------------------------
    # Internal LangGraph-style workflow
    # ------------------------------------------------------------------

    async def invoke(self, request: AgentRequest) -> AgentResponse:
        """
        Water resource workflow:
        Observe → Analyze (tools) → Reason → Reflect → Validate →
        Decision Engine → Report
        """
        if not self._initialized:
            await self.initialize()

        metrics = WaterMetricsCollector(agent_id=self.agent_id, request_id=request.request_id)
        self._last_metrics = metrics
        self._last_water_metrics = metrics
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

            water_report = await self._run_report(
                context, reasoning, tool_results, reflection, validation, decision,
            )
            self._last_water_report = water_report
            self._last_report = self._to_agent_report(water_report)

            stress = WaterStressLevel(reasoning.metadata.get("stress_level", WaterStressLevel.NONE.value))
            metrics.set_stress_level(stress)
            metrics.set_confidence(water_report.confidence)
            if any(r.tool_name == "reservoir_tool" and r.success for r in tool_results):
                metrics.record_reservoir_analysis()
            water_metrics = metrics.finalize_water()
            water_report.metrics = water_metrics

            memory_refs = await self.update_memory(context, self._last_report)
            await self._persist_water_report(context, water_report)
            await self.update_state(context, self._last_report)

            self._status = AgentStatus.COMPLETED
            return self._water_report_to_response(water_report, water_metrics, memory_refs)

        except Exception as exc:
            self._status = AgentStatus.FAILED
            metrics.finalize()
            logger.error("water_agent_failed", request_id=request.request_id, error=str(exc))
            raise AgentInvocationError(
                f"Water resource agent failed: {exc}",
                details={"agent_id": self.agent_id, "request_id": request.request_id},
            ) from exc

    async def _run_observe(self, request: AgentRequest) -> AgentContext:
        context = await self.retrieve_context(request)
        inputs = WaterInputs.from_request_context(request.context)
        inputs.climate_state_available = request.climate_state is not None
        inputs.forecast_available = bool(
            request.context.get("forecast_available")
            or inputs.rainfall.forecast_24h_mm
        )
        inputs.digital_twin_available = bool(
            request.context.get("digital_twin_available")
            or request.context.get("twin_id")
        )
        inputs.reservoir_available = bool(
            request.context.get("reservoir_available")
            or inputs.reservoir.level_pct is not None
        )
        inputs.groundwater_available = bool(
            request.context.get("groundwater_available")
            or inputs.groundwater.depth_to_water_m is not None
        )
        context.metadata["water_inputs"] = inputs
        context.metadata["requires_climate_state"] = True

        await self.preprocess(context)
        await self.retrieve_memory(context)
        await self.retrieve_climate_state(context)
        await self.retrieve_forecast(context)
        await self._hydrate_digital_twin(context)

        if context.digital_twin_state:
            context.request.context["digital_twin_state"] = context.digital_twin_state

        logger.info("water_observe_complete", region_id=inputs.region_id, basin_id=inputs.basin_id)
        return context

    async def _run_analyze(
        self,
        context: AgentContext,
        metrics: WaterMetricsCollector,
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
        metrics: WaterMetricsCollector,
    ) -> tuple[ReasoningResult, Any]:
        reasoning, signals = await self._water_reasoning.run(context, tool_results)
        metrics.record_reasoning(sum(s.duration_ms for s in reasoning.steps))
        return reasoning, signals

    async def _run_reflect(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        tool_results: list[ToolResult],
    ) -> Any:
        reflection = await self._water_reflection.evaluate(context, reasoning, tool_results)
        self._last_metrics and self._last_metrics.record_reflection()
        return reflection

    async def _run_validate(
        self,
        context: AgentContext,
        tool_results: list[ToolResult],
    ) -> Any:
        validation = await self._water_validator.validate(context, tool_results)
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
    ) -> WaterResourceReport:
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
            for name in ALL_WATER_TOOL_NAMES
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

    async def _persist_water_report(self, context: AgentContext, report: WaterResourceReport) -> None:
        from backend.agents.memory.memory_types import MemoryDomain, MemoryStoreRequest

        session_id = context.user.session_id
        key = f"water_report:{context.request_id}"
        await self.memory_manager.store(
            MemoryStoreRequest(
                domain=MemoryDomain.WORKING,
                key=key,
                value=report.model_dump(),
                session_id=session_id,
                metadata={"agent_id": self.agent_id, "type": "water_report"},
            ),
        )
        self._last_metrics and self._last_metrics.record_memory_write()

    def _to_agent_report(self, water_report: WaterResourceReport) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            request_id=water_report.request_id,
            summary=water_report.executive_summary,
            reasoning=water_report.reasoning,
            risk={
                "stress_level": water_report.water_stress.value,
                "availability_band": water_report.water_availability.band.value,
                "release_strategy": water_report.release_strategy.value,
            },
            confidence=water_report.confidence,
            recommendations=water_report.recommendations,
            references=water_report.references,
            tool_outputs=water_report.tool_outputs,
            structured_output=water_report.model_dump(),
            metadata={
                "water_report_id": water_report.report_id,
                "need_rl": water_report.need_rl,
                "need_simulation": water_report.need_simulation,
                "need_other_agents": water_report.need_other_agents,
            },
        )

    def _water_report_to_response(
        self,
        report: WaterResourceReport,
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
                "water_report_id": report.report_id,
                "water_stress": report.water_stress.value,
                "availability_band": report.water_availability.band.value,
                "release_strategy": report.release_strategy.value,
                "confidence": report.confidence,
                "supply_m3d": report.water_availability.supply_m3d,
                "demand_m3d": report.water_availability.demand_m3d,
                "recommendations": report.recommendations,
                "need_rl": report.need_rl,
                "need_simulation": report.need_simulation,
                "decision_request": report.decision_request.model_dump(),
                "metrics": metrics.model_dump(),
            },
        )

    async def as_graph_node(self, state: WorkflowState) -> dict[str, Any]:
        """Expose water resource agent as a LangGraph node."""
        update = await super().as_graph_node(state)
        if self._last_water_report:
            update["metadata"] = {
                **update.get("metadata", {}),
                "water_stress": self._last_water_report.water_stress.value,
                "availability_band": self._last_water_report.water_availability.band.value,
                "release_strategy": self._last_water_report.release_strategy.value,
            }
        return update
