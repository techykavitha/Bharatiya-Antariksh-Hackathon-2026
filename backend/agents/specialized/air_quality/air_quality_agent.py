"""Air Quality Agent — atmospheric pollution and environmental health analysis."""

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
from backend.agents.specialized.air_quality.air_quality_context import (
    AirQualityInputs,
    KnowledgeGraphInsights,
    PeerAgentOutput,
)
from backend.agents.specialized.air_quality.air_quality_metrics import AirQualityMetricsCollector
from backend.agents.specialized.air_quality.air_quality_models import (
    AGENT_AGRICULTURE,
    AGENT_CYCLONE,
    AGENT_DISASTER,
    AGENT_HEATWAVE,
    AGENT_URBAN_PLANNING,
    AIR_QUALITY_AGENT_ID,
    AQICategory,
)
from backend.agents.specialized.air_quality.air_quality_reasoning import (
    AirQualityDecisionEngine,
    AirQualityReasoningEngine,
)
from backend.agents.specialized.air_quality.air_quality_reflection import AirQualityReflectionEngine
from backend.agents.specialized.air_quality.air_quality_report import AirQualityReport, AirQualityReportBuilder
from backend.agents.specialized.air_quality.air_quality_tools import (
    ALL_AIR_QUALITY_TOOL_NAMES,
    create_air_quality_tools,
)
from backend.agents.specialized.air_quality.air_quality_validator import AirQualityValidator
from backend.agents.specialized.base_specialized_agent import BaseSpecializedAgent
from backend.agents.state.workflow_state import WorkflowState
from backend.agents.supervisor.execution_context import DigitalTwinInterface
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.knowledge_graph.graph_engine import GraphEngine
from backend.rl import RLOptimizationError, RLOptimizationService
from backend.utils.enums import AgentStatus
from backend.utils.errors import AgentInvocationError
from backend.xai import ExplanationEngine, ExplanationInput, ExplanationType

logger = get_logger(__name__)

_PEER_DOMAIN_MAP: dict[str, str] = {
    AGENT_HEATWAVE: "heatwave",
    AGENT_URBAN_PLANNING: "urban",
    AGENT_DISASTER: "disaster",
    AGENT_AGRICULTURE: "agriculture",
    AGENT_CYCLONE: "cyclone",
}


class AirQualityAgent(BaseSpecializedAgent):
    """
    Production-grade air quality and environmental health agent.

    Evaluates atmospheric pollution, smoke transport, dust events, ozone formation,
    population exposure, and compound climate hazards to generate actionable
    mitigation recommendations for policymakers and public health officials.
    """

    AGENT_ID = AIR_QUALITY_AGENT_ID

    def __init__(
        self,
        *,
        memory: MemoryManager,
        rl_engine: SpecializedRLEngineInterface | None = None,
        rl_service: RLOptimizationService | None = None,
        explanation_engine: ExplanationEngine | None = None,
        graph_engine: GraphEngine | None = None,
        agent_communication: AgentCommunicationInterface | None = None,
        digital_twin: DigitalTwinInterface | None = None,
        confidence_threshold: float = 0.45,
    ) -> None:
        super().__init__(
            AIR_QUALITY_AGENT_ID,
            description="Atmospheric pollution analysis, health risk assessment, and air quality mitigation agent",
            memory=memory,
            tools=create_air_quality_tools(),
            rl_engine=rl_engine,
            agent_communication=agent_communication,
            digital_twin=digital_twin,
            confidence_threshold=confidence_threshold,
        )
        self._rl_service = rl_service
        self._explanation_engine = explanation_engine
        self._graph_engine = graph_engine
        self._air_quality_reasoning = AirQualityReasoningEngine(agent_id=AIR_QUALITY_AGENT_ID)
        self._air_quality_reflection = AirQualityReflectionEngine(
            agent_id=AIR_QUALITY_AGENT_ID,
            confidence_threshold=confidence_threshold,
        )
        self._air_quality_validator = AirQualityValidator(agent_id=AIR_QUALITY_AGENT_ID)
        self._decision_engine = AirQualityDecisionEngine(agent_id=AIR_QUALITY_AGENT_ID)
        self._report_builder = AirQualityReportBuilder(agent_id=AIR_QUALITY_AGENT_ID)
        self._last_air_quality_report: AirQualityReport | None = None
        self._last_air_quality_metrics: AirQualityMetricsCollector | None = None

    @property
    def last_air_quality_report(self) -> AirQualityReport | None:
        return self._last_air_quality_report

    @property
    def last_air_quality_metrics(self) -> AirQualityMetricsCollector | None:
        return self._last_air_quality_metrics

    @classmethod
    async def create(
        cls,
        memory: MemoryManager,
        *,
        rl_engine: SpecializedRLEngineInterface | None = None,
        rl_service: RLOptimizationService | None = None,
        explanation_engine: ExplanationEngine | None = None,
        graph_engine: GraphEngine | None = None,
        agent_communication: AgentCommunicationInterface | None = None,
        digital_twin: DigitalTwinInterface | None = None,
    ) -> AirQualityAgent:
        agent = cls(
            memory=memory,
            rl_engine=rl_engine,
            rl_service=rl_service,
            explanation_engine=explanation_engine,
            graph_engine=graph_engine,
            agent_communication=agent_communication,
            digital_twin=digital_twin,
        )
        await agent.initialize()
        return agent

    async def declare_capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                capability_id="aqi_assessment",
                name="AQI Assessment",
                category=CapabilityCategory.ANALYSIS,
                keywords=["aqi", "air quality", "pollution"],
                required_tools=["aqi_tool"],
            ),
            AgentCapability(
                capability_id="pm25_analysis",
                name="PM2.5 Analysis",
                category=CapabilityCategory.ANALYSIS,
                keywords=["pm2.5", "particulate", "fine"],
                required_tools=["pm_tool"],
            ),
            AgentCapability(
                capability_id="pm10_analysis",
                name="PM10 Analysis",
                category=CapabilityCategory.ANALYSIS,
                keywords=["pm10", "particulate", "coarse"],
                required_tools=["pm_tool"],
            ),
            AgentCapability(
                capability_id="gas_concentration_analysis",
                name="Gas Concentration Analysis",
                category=CapabilityCategory.ANALYSIS,
                keywords=["no2", "so2", "o3", "co", "gas"],
                required_tools=["gas_concentration_tool"],
            ),
            AgentCapability(
                capability_id="dust_storm_detection",
                name="Dust Storm Detection",
                category=CapabilityCategory.MONITORING,
                keywords=["dust", "storm", "aerosol"],
                required_tools=["satellite_aerosol_tool", "pm_tool"],
            ),
            AgentCapability(
                capability_id="biomass_burning_impact",
                name="Biomass Burning Impact",
                category=CapabilityCategory.ANALYSIS,
                keywords=["stubble", "biomass", "burning", "smoke"],
                required_tools=["satellite_aerosol_tool", "emission_tool"],
            ),
            AgentCapability(
                capability_id="wildfire_smoke_analysis",
                name="Wildfire Smoke Analysis",
                category=CapabilityCategory.ANALYSIS,
                keywords=["wildfire", "smoke", "fire"],
                required_tools=["satellite_aerosol_tool"],
            ),
            AgentCapability(
                capability_id="pollution_transport",
                name="Pollution Transport",
                category=CapabilityCategory.ANALYSIS,
                keywords=["transport", "wind", "dispersion"],
                required_tools=["wind_tool"],
            ),
            AgentCapability(
                capability_id="health_risk_assessment",
                name="Health Risk Assessment",
                category=CapabilityCategory.ANALYSIS,
                keywords=["health", "exposure", "respiratory"],
                required_tools=["health_risk_tool", "population_tool"],
            ),
            AgentCapability(
                capability_id="air_quality_forecast",
                name="Air Quality Forecast",
                category=CapabilityCategory.PREDICTION,
                keywords=["forecast", "trend", "prediction"],
                required_tools=["forecast_tool"],
            ),
            AgentCapability(
                capability_id="emission_inventory_analysis",
                name="Emission Inventory Analysis",
                category=CapabilityCategory.ANALYSIS,
                keywords=["emission", "source", "inventory"],
                required_tools=["emission_tool"],
            ),
            AgentCapability(
                capability_id="mitigation_strategy",
                name="Mitigation Strategy Generation",
                category=CapabilityCategory.PLANNING,
                keywords=["mitigation", "grap", "advisory"],
                required_tools=["aqi_tool", "health_risk_tool"],
            ),
        ]

    async def invoke(self, request: AgentRequest) -> AgentResponse:
        """
        Air quality workflow:
        Observe → Analyze → Reason → Validate →
        Decision Framework → RL → Explainability → Report
        """
        if not self._initialized:
            await self.initialize()

        metrics = AirQualityMetricsCollector(agent_id=self.agent_id, request_id=request.request_id)
        self._last_metrics = metrics
        self._last_air_quality_metrics = metrics
        self._status = AgentStatus.REASONING

        try:
            context = await self._run_observe(request, metrics)
            await self._collect_peer_inputs(context, request, metrics)
            tool_results = await self._run_analyze(context, metrics)
            reasoning, signals = await self._run_reason(context, tool_results, metrics)
            validation = await self._run_validate(context, tool_results)
            reflection = await self._air_quality_reflection.evaluate(context, reasoning, tool_results)
            decision = await self._run_decision_engine(context, reasoning, reflection)
            metrics.record_decision_request()

            if decision.need_other_agents and self._agent_communication:
                await self.call_other_agents(context, decision.need_other_agents, request)

            rl_response = await self._run_rl_service(decision, metrics)
            explainability = await self._run_explainability(
                context, reasoning, tool_results, reflection, validation,
                decision, rl_response, metrics,
            )

            air_quality_report = await self._run_report(
                context, reasoning, tool_results, reflection, validation,
                decision, rl_response, explainability,
            )
            self._last_air_quality_report = air_quality_report
            self._last_report = self._to_agent_report(air_quality_report)

            aqi_data = reasoning.metadata.get("aqi_assessment", {})
            aqi = int(aqi_data.get("aqi", 0))
            category = AQICategory(aqi_data.get("category", AQICategory.MODERATE.value))
            metrics.set_aqi(aqi, category)
            metrics.set_health_risk_score(float(signals.health_risk_score))
            metrics.set_confidence(air_quality_report.confidence)
            aq_metrics = metrics.finalize_air_quality()
            air_quality_report.metrics = aq_metrics

            memory_refs = await self.update_memory(context, self._last_report)
            await self._persist_air_quality_report(context, air_quality_report)
            await self.update_state(context, self._last_report)

            self._status = AgentStatus.COMPLETED
            return self._air_quality_report_to_response(air_quality_report, aq_metrics, memory_refs)

        except Exception as exc:
            self._status = AgentStatus.FAILED
            metrics.finalize()
            logger.error("air_quality_agent_failed", request_id=request.request_id, error=str(exc))
            raise AgentInvocationError(
                f"Air quality agent failed: {exc}",
                details={"agent_id": self.agent_id, "request_id": request.request_id},
            ) from exc

    async def _run_observe(
        self, request: AgentRequest, metrics: AirQualityMetricsCollector,
    ) -> AgentContext:
        context = await self.retrieve_context(request)
        inputs = AirQualityInputs.from_request_context(request.context)
        inputs.climate_state_available = request.climate_state is not None
        inputs.forecast_available = bool(
            request.context.get("forecast_available") or context.forecast.references,
        )
        inputs.digital_twin_available = bool(
            request.context.get("digital_twin_available") or request.context.get("twin_id"),
        )
        context.metadata["air_quality_inputs"] = inputs
        context.metadata["requires_climate_state"] = True

        await self.preprocess(context)
        await self.retrieve_memory(context)
        await self.retrieve_climate_state(context)
        await self.retrieve_forecast(context)
        await self._hydrate_digital_twin(context)

        if context.digital_twin_state:
            context.request.context["digital_twin_state"] = context.digital_twin_state

        ckg_insights = await self._query_knowledge_graph(inputs, metrics)
        context.metadata["ckg_insights"] = ckg_insights
        context.request.context["ckg_insights"] = ckg_insights.model_dump()

        logger.info(
            "air_quality_observe_complete",
            region_id=inputs.region_id,
            city=inputs.city_name,
        )
        return context

    async def _collect_peer_inputs(
        self,
        context: AgentContext,
        request: AgentRequest,
        metrics: AirQualityMetricsCollector,
    ) -> None:
        inputs: AirQualityInputs = context.metadata["air_quality_inputs"]
        missing = [
            agent_id for agent_id in inputs.consult_agents
            if agent_id not in inputs.peer_agent_outputs
        ]
        if missing and self._agent_communication:
            delegations = await self.call_other_agents(context, missing, request)
            for result in delegations:
                if result.success:
                    peer = self._peer_from_delegation(
                        result.agent_id, result.structured_output, result.content,
                    )
                    inputs.peer_agent_outputs[result.agent_id] = peer

        context.metadata["air_quality_inputs"] = inputs
        context.request.context["peer_agent_outputs"] = {
            k: v.model_dump() for k, v in inputs.peer_agent_outputs.items()
        }
        metrics.record_peer_agents_consulted(len(inputs.peer_agent_outputs))

    def _peer_from_delegation(
        self,
        agent_id: str,
        structured: dict[str, Any] | None,
        content: str | None,
    ) -> PeerAgentOutput:
        data = structured or {}
        return PeerAgentOutput(
            agent_id=agent_id,
            domain=_PEER_DOMAIN_MAP.get(agent_id, "unknown"),
            severity=str(data.get("severity") or data.get("risk_level") or "moderate"),
            risk_level=str(data.get("risk_level", "moderate")),
            confidence=float(data.get("confidence", 0.7)),
            summary=str(data.get("executive_summary") or data.get("summary") or content or ""),
            affected_regions=list(data.get("affected_regions", data.get("districts", []))),
            recommendations=list(data.get("recommendations", [])),
            structured_output=data,
            consulted_live=True,
        )

    async def _query_knowledge_graph(
        self, inputs: AirQualityInputs, metrics: AirQualityMetricsCollector,
    ) -> KnowledgeGraphInsights:
        if not self._graph_engine:
            return KnowledgeGraphInsights()

        insights = KnowledgeGraphInsights()
        entity_id = inputs.region_id or "heatwave_delhi_2024"
        query_count = 0

        try:
            neighbors = await self._graph_engine.query.neighbors(entity_id)
            query_count += 1
            for n in neighbors:
                etype = n.entity.entity_type.value
                if etype in ("industrial", "power_grid", "transport"):
                    insights.emission_sources.append(n.entity.entity_id)
                if etype == "population":
                    insights.population_nodes.append(n.entity.entity_id)
                if etype in ("infrastructure", "hospital", "urban_area"):
                    insights.infrastructure_nodes.append(n.entity.entity_id)
        except Exception as exc:
            logger.debug("ckg_neighbors_skipped", error=str(exc))

        try:
            chain = await self._graph_engine.query.impact_chain(entity_id, max_depth=3)
            query_count += 1
            if chain.chain:
                insights.historical_pollution = [e.entity_id for e in chain.chain[:5]]
        except Exception as exc:
            logger.debug("ckg_impact_chain_skipped", error=str(exc))

        try:
            similar = await self._graph_engine.query.historical_similarity(entity_id, limit=3)
            query_count += 1
            insights.compound_hazards = [c.entity_id for c in similar.candidates]
        except Exception as exc:
            logger.debug("ckg_historical_similarity_skipped", error=str(exc))

        insights.query_count = query_count
        metrics.record_ckg_query(query_count)
        return insights

    async def _run_analyze(
        self, context: AgentContext, metrics: AirQualityMetricsCollector,
    ) -> list[ToolResult]:
        tool_specs = await self._build_tool_specs(context)
        mid = 10
        batch_a = tool_specs[:mid]
        batch_b = tool_specs[mid:]
        results_a = await self.execute_tools(context, batch_a, parallel=True)
        results_b = await self.execute_tools(context, batch_b, parallel=True) if batch_b else []
        results = list(results_a) + list(results_b)
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
        metrics: AirQualityMetricsCollector,
    ) -> tuple[ReasoningResult, Any]:
        reasoning, signals = await self._air_quality_reasoning.run(context, tool_results)
        metrics.record_reasoning(sum(s.duration_ms for s in reasoning.steps))
        return reasoning, signals

    async def _run_validate(
        self, context: AgentContext, tool_results: list[ToolResult],
    ) -> Any:
        strict = bool(context.request.context.get("strict_validation"))
        validation = await self._air_quality_validator.validate(context, tool_results, strict=strict)
        self._last_metrics and self._last_metrics.record_validation()
        return validation

    async def _run_decision_engine(
        self, context: AgentContext, reasoning: ReasoningResult, reflection: Any,
    ) -> DecisionRequest:
        return await self._decision_engine.evaluate(context, reasoning, reflection)

    async def _run_rl_service(
        self, decision: DecisionRequest, metrics: AirQualityMetricsCollector,
    ) -> DecisionResponse | None:
        if not decision.need_rl or not self._rl_service:
            return None
        try:
            rl_response = await self._rl_service.optimize(decision)
            metrics.record_rl_call()
            return rl_response
        except RLOptimizationError as exc:
            logger.warning("air_quality_rl_optimization_failed", decision_id=decision.decision_id, error=str(exc))
            return None

    async def _run_explainability(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        tool_results: list[ToolResult],
        reflection: Any,
        validation: Any,
        decision: DecisionRequest,
        rl_response: DecisionResponse | None,
        metrics: AirQualityMetricsCollector,
    ) -> Any:
        if not self._explanation_engine:
            return None
        explanation_input = ExplanationInput(
            request_id=context.request_id,
            agent_id=self.agent_id,
            explanation_type=ExplanationType.FULL_PIPELINE,
            query=context.query,
            reasoning=reasoning,
            tool_results=tool_results,
            reflection=reflection,
            validation=validation,
            decision_request=decision,
            decision_response=rl_response,
            recommendations=[
                s.content for s in reasoning.steps if s.metadata.get("recommendations")
            ] or [s.content for s in reasoning.steps[-2:]],
        )
        report = await self._explanation_engine.explain(explanation_input)
        metrics.record_explainability_call()
        return report

    async def _run_report(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        tool_results: list[ToolResult],
        reflection: Any,
        validation: Any,
        decision: DecisionRequest,
        rl_response: DecisionResponse | None = None,
        explainability: Any = None,
    ) -> AirQualityReport:
        return self._report_builder.build(
            context, reasoning, tool_results, validation, decision,
            reflection, rl_response, explainability,
        )

    async def _build_tool_specs(self, context: AgentContext) -> list[ToolCallSpec]:
        params = dict(context.request.context)
        params["digital_twin_state"] = context.digital_twin_state
        params["ckg_insights"] = context.metadata.get("ckg_insights")
        return [
            ToolCallSpec(tool_name=name, parameters=params)
            for name in ALL_AIR_QUALITY_TOOL_NAMES
            if self.tool_manager.has_tool(name)
        ]

    async def _on_select_tools(
        self, context: AgentContext, reasoning: ReasoningResult,
    ) -> list[ToolCallSpec]:
        return await self._build_tool_specs(context)

    async def required_inputs(self) -> list[str]:
        return ["query"]

    async def _persist_air_quality_report(
        self, context: AgentContext, report: AirQualityReport,
    ) -> None:
        from backend.agents.memory.memory_types import MemoryDomain, MemoryStoreRequest

        await self.memory_manager.store(
            MemoryStoreRequest(
                domain=MemoryDomain.WORKING,
                key=f"air_quality_report:{context.request_id}",
                value=report.model_dump(),
                session_id=context.user.session_id,
                metadata={"agent_id": self.agent_id, "type": "air_quality_report"},
            ),
        )
        self._last_metrics and self._last_metrics.record_memory_write()

    def _to_agent_report(self, report: AirQualityReport) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            request_id=report.request_id,
            summary=report.executive_summary,
            reasoning=report.reasoning,
            risk={
                "aqi": report.aqi_assessment.aqi,
                "aqi_category": report.aqi_assessment.category.value,
                "health_risk_level": report.health_risk.risk_level.value,
            },
            confidence=report.confidence,
            recommendations=report.recommendations,
            references=report.references,
            tool_outputs=report.tool_outputs,
            structured_output=report.model_dump(),
            metadata={
                "air_quality_report_id": report.report_id,
                "aqi": report.aqi_assessment.aqi,
                "need_rl": report.need_rl,
            },
        )

    def _air_quality_report_to_response(
        self, report: AirQualityReport, metrics: Any, memory_refs: list[str],
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
                "air_quality_report_id": report.report_id,
                "aqi": report.aqi_assessment.aqi,
                "aqi_category": report.aqi_assessment.category.value,
                "dominant_pollutant": report.aqi_assessment.dominant_pollutant.value,
                "health_risk_level": report.health_risk.risk_level.value,
                "confidence": report.confidence,
                "recommendations": report.recommendations,
                "evidence": report.evidence,
                "need_rl": report.need_rl,
                "chosen_action": report.chosen_action,
                "decision_request": report.decision_request.model_dump() if report.decision_request else {},
                "rl_response": report.rl_response.model_dump() if report.rl_response else None,
                "explainability_summary": (
                    report.explainability_report.executive_summary
                    if report.explainability_report else None
                ),
                "metrics": metrics.model_dump(),
            },
        )

    async def as_graph_node(self, state: WorkflowState) -> dict[str, Any]:
        update = await super().as_graph_node(state)
        if self._last_air_quality_report:
            update["metadata"] = {
                **update.get("metadata", {}),
                "aqi": self._last_air_quality_report.aqi_assessment.aqi,
                "aqi_category": self._last_air_quality_report.aqi_assessment.category.value,
                "health_risk_level": self._last_air_quality_report.health_risk.risk_level.value,
            }
        return update
