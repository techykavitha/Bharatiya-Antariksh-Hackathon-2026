"""Cyclone Agent — autonomous tropical cyclone monitoring and forecasting."""

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
from backend.agents.specialized.cyclone.cyclone_context import CycloneInputs, KnowledgeGraphInsights
from backend.agents.specialized.cyclone.cyclone_metrics import CycloneMetricsCollector
from backend.agents.specialized.cyclone.cyclone_models import (
    CYCLONE_AGENT_ID,
    CycloneRiskLevel,
    CycloneSeverity,
)
from backend.agents.specialized.cyclone.cyclone_reasoning import CycloneDecisionEngine, CycloneReasoningEngine
from backend.agents.specialized.cyclone.cyclone_reflection import CycloneReflectionEngine
from backend.agents.specialized.cyclone.cyclone_report import CycloneReport, CycloneReportBuilder
from backend.agents.specialized.cyclone.cyclone_tools import ALL_CYCLONE_TOOL_NAMES, create_cyclone_tools
from backend.agents.specialized.cyclone.cyclone_validator import CycloneValidator
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


class CycloneAgent(BaseSpecializedAgent):
    """
    Production-grade autonomous tropical cyclone agent for India.

    Monitors cyclone genesis, track evolution, intensity, landfall probability,
    storm surge, rainfall impact, and cascading hazards. Integrates Decision
    Framework, RL Optimization Service, Explainability Framework, and CKG.
    """

    AGENT_ID = CYCLONE_AGENT_ID

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
            CYCLONE_AGENT_ID,
            description="Autonomous tropical cyclone detection, forecasting, and coastal hazard assessment agent",
            memory=memory,
            tools=create_cyclone_tools(),
            rl_engine=rl_engine,
            agent_communication=agent_communication,
            digital_twin=digital_twin,
            confidence_threshold=confidence_threshold,
        )
        self._rl_service = rl_service
        self._explanation_engine = explanation_engine
        self._graph_engine = graph_engine
        self._cyclone_reasoning = CycloneReasoningEngine(agent_id=CYCLONE_AGENT_ID)
        self._cyclone_reflection = CycloneReflectionEngine(
            agent_id=CYCLONE_AGENT_ID,
            confidence_threshold=confidence_threshold,
        )
        self._cyclone_validator = CycloneValidator(agent_id=CYCLONE_AGENT_ID)
        self._decision_engine = CycloneDecisionEngine(agent_id=CYCLONE_AGENT_ID)
        self._report_builder = CycloneReportBuilder(agent_id=CYCLONE_AGENT_ID)
        self._last_cyclone_report: CycloneReport | None = None
        self._last_cyclone_metrics: CycloneMetricsCollector | None = None

    @property
    def last_cyclone_report(self) -> CycloneReport | None:
        return self._last_cyclone_report

    @property
    def last_cyclone_metrics(self) -> CycloneMetricsCollector | None:
        return self._last_cyclone_metrics

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
    ) -> CycloneAgent:
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
                capability_id="cyclone_detection",
                name="Cyclone Detection",
                category=CapabilityCategory.MONITORING,
                keywords=["cyclone", "storm", "detect", "tropical"],
                required_tools=["pressure_tool", "wind_tool", "sst_tool"],
            ),
            AgentCapability(
                capability_id="cyclone_genesis",
                name="Cyclone Genesis Assessment",
                category=CapabilityCategory.ANALYSIS,
                keywords=["genesis", "formation", "cyclogenesis"],
                required_tools=["sst_tool", "ocean_heat_tool", "pressure_tool"],
            ),
            AgentCapability(
                capability_id="track_prediction",
                name="Track Prediction",
                category=CapabilityCategory.FORECAST,
                keywords=["track", "path", "trajectory", "forecast"],
                required_tools=["forecast_tool", "insat_tool"],
                requires_forecast=True,
            ),
            AgentCapability(
                capability_id="intensity_classification",
                name="Intensity Classification",
                category=CapabilityCategory.INTERPRETATION,
                keywords=["intensity", "category", "wind", "imd"],
                required_tools=["wind_tool", "insat_tool"],
            ),
            AgentCapability(
                capability_id="rapid_intensification",
                name="Rapid Intensification Detection",
                category=CapabilityCategory.ANALYSIS,
                keywords=["rapid", "intensification", "ri"],
                required_tools=["ocean_heat_tool", "wind_tool", "insat_tool"],
            ),
            AgentCapability(
                capability_id="landfall_prediction",
                name="Landfall Prediction",
                category=CapabilityCategory.PREDICTION,
                keywords=["landfall", "coast", "impact"],
                required_tools=["forecast_tool"],
                requires_forecast=True,
            ),
            AgentCapability(
                capability_id="storm_surge",
                name="Storm Surge Estimation",
                category=CapabilityCategory.ANALYSIS,
                keywords=["surge", "inundation", "coastal"],
                required_tools=["storm_surge_tool", "wind_tool"],
            ),
            AgentCapability(
                capability_id="rainfall_impact",
                name="Rainfall Impact Estimation",
                category=CapabilityCategory.ANALYSIS,
                keywords=["rainfall", "precipitation", "flood"],
                required_tools=["forecast_tool"],
            ),
            AgentCapability(
                capability_id="wind_hazard",
                name="Wind Hazard Assessment",
                category=CapabilityCategory.ANALYSIS,
                keywords=["wind", "gust", "destructive"],
                required_tools=["wind_tool"],
            ),
            AgentCapability(
                capability_id="coastal_vulnerability",
                name="Coastal Vulnerability Assessment",
                category=CapabilityCategory.ANALYSIS,
                keywords=["coastal", "vulnerability", "exposure"],
                required_tools=["population_tool", "storm_surge_tool"],
            ),
            AgentCapability(
                capability_id="infrastructure_risk",
                name="Infrastructure Risk",
                category=CapabilityCategory.ANALYSIS,
                keywords=["infrastructure", "port", "power", "hospital"],
                required_tools=["infrastructure_tool"],
            ),
            AgentCapability(
                capability_id="evacuation_recommendation",
                name="Evacuation Recommendation",
                category=CapabilityCategory.PLANNING,
                keywords=["evacuation", "shelter", "relief"],
                required_tools=["population_tool", "storm_surge_tool", "forecast_tool"],
            ),
        ]

    async def invoke(self, request: AgentRequest) -> AgentResponse:
        """
        Cyclone workflow:
        Observe → Analyze → Reason → Reflect → Validate →
        Decision Framework → RL Service → Explainability → Report
        """
        if not self._initialized:
            await self.initialize()

        metrics = CycloneMetricsCollector(agent_id=self.agent_id, request_id=request.request_id)
        self._last_metrics = metrics
        self._last_cyclone_metrics = metrics
        self._status = AgentStatus.REASONING

        try:
            context = await self._run_observe(request, metrics)
            tool_results = await self._run_analyze(context, metrics)
            reasoning, _signals = await self._run_reason(context, tool_results, metrics)
            reflection = await self._run_reflect(context, reasoning, tool_results)
            validation = await self._run_validate(context, tool_results)
            decision = await self._run_decision_engine(context, reasoning, reflection)
            metrics.record_decision_request()

            if decision.need_other_agents and self._agent_communication:
                await self.call_other_agents(context, decision.need_other_agents, request)

            rl_response = await self._run_rl_service(decision, metrics)
            explainability = await self._run_explainability(
                context, reasoning, tool_results, reflection, validation, decision, rl_response, metrics,
            )

            cyclone_report = await self._run_report(
                context, reasoning, tool_results, reflection, validation,
                decision, rl_response, explainability,
            )
            self._last_cyclone_report = cyclone_report
            self._last_report = self._to_agent_report(cyclone_report)

            severity = CycloneSeverity(reasoning.metadata.get("severity", CycloneSeverity.NONE.value))
            metrics.set_severity(severity)
            metrics.set_risk_level(cyclone_report.risk_level)
            metrics.set_confidence(cyclone_report.confidence)
            cyclone_metrics = metrics.finalize_cyclone()
            cyclone_report.metrics = cyclone_metrics

            memory_refs = await self.update_memory(context, self._last_report)
            await self._persist_cyclone_report(context, cyclone_report)
            await self.update_state(context, self._last_report)

            self._status = AgentStatus.COMPLETED
            return self._cyclone_report_to_response(cyclone_report, cyclone_metrics, memory_refs)

        except Exception as exc:
            self._status = AgentStatus.FAILED
            metrics.finalize()
            logger.error("cyclone_agent_failed", request_id=request.request_id, error=str(exc))
            raise AgentInvocationError(
                f"Cyclone agent failed: {exc}",
                details={"agent_id": self.agent_id, "request_id": request.request_id},
            ) from exc

    async def _run_observe(
        self, request: AgentRequest, metrics: CycloneMetricsCollector,
    ) -> AgentContext:
        context = await self.retrieve_context(request)
        inputs = CycloneInputs.from_request_context(request.context)
        inputs.climate_state_available = request.climate_state is not None
        inputs.forecast_available = bool(
            request.context.get("forecast_available") or inputs.forecast.track_points,
        )
        inputs.digital_twin_available = bool(
            request.context.get("digital_twin_available") or request.context.get("twin_id"),
        )
        inputs.insat_available = bool(request.context.get("insat_available"))
        context.metadata["cyclone_inputs"] = inputs
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

        logger.info("cyclone_observe_complete", region_id=inputs.region_id, basin=inputs.basin.value)
        return context

    async def _query_knowledge_graph(
        self, inputs: CycloneInputs, metrics: CycloneMetricsCollector,
    ) -> KnowledgeGraphInsights:
        if not self._graph_engine:
            return KnowledgeGraphInsights()

        insights = KnowledgeGraphInsights()
        entity_id = inputs.region_id or "cyclone-bay-of-bengal"
        query_count = 0

        try:
            agents_result = await self._graph_engine.query.affected_agents(entity_id)
            query_count += 1
            insights.dependent_agents = [
                aid for a in agents_result.agents
                if (aid := getattr(a, "agent_id", None) or a.entity_id)
            ]
        except Exception as exc:
            logger.debug("ckg_affected_agents_skipped", error=str(exc))

        try:
            chain = await self._graph_engine.query.impact_chain(entity_id, max_depth=4)
            query_count += 1
            if chain.chain:
                insights.cascade_chains = [[e.entity_id for e in chain.chain[:5]]]
                insights.affected_regions = [e.entity_id for e in chain.chain[:10]]
        except Exception as exc:
            logger.debug("ckg_impact_chain_skipped", error=str(exc))

        try:
            similar = await self._graph_engine.query.historical_similarity(entity_id, limit=3)
            query_count += 1
            insights.historical_analogs = [c.entity_id for c in similar.candidates]
        except Exception as exc:
            logger.debug("ckg_historical_similarity_skipped", error=str(exc))

        try:
            neighbors = await self._graph_engine.query.neighbors(entity_id)
            query_count += 1
            for n in neighbors:
                if n.entity.entity_type.value in ("infrastructure", "port", "power_plant"):
                    insights.affected_infrastructure.append(n.entity.entity_id)
        except Exception as exc:
            logger.debug("ckg_neighbors_skipped", error=str(exc))

        insights.query_count = query_count
        metrics.record_ckg_query(query_count)
        return insights

    async def _run_analyze(
        self, context: AgentContext, metrics: CycloneMetricsCollector,
    ) -> list[ToolResult]:
        tool_specs = await self._build_tool_specs(context)
        # Execute in two batches to respect MAX_TOOL_CALLS_PER_INVOCATION (10) without
        # modifying the shared ToolManager limit.
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
        metrics: CycloneMetricsCollector,
    ) -> tuple[ReasoningResult, Any]:
        reasoning, signals = await self._cyclone_reasoning.run(context, tool_results)
        metrics.record_reasoning(sum(s.duration_ms for s in reasoning.steps))
        return reasoning, signals

    async def _run_reflect(
        self, context: AgentContext, reasoning: ReasoningResult, tool_results: list[ToolResult],
    ) -> Any:
        reflection = await self._cyclone_reflection.evaluate(context, reasoning, tool_results)
        self._last_metrics and self._last_metrics.record_reflection()
        return reflection

    async def _run_validate(
        self, context: AgentContext, tool_results: list[ToolResult],
    ) -> Any:
        strict = bool(context.request.context.get("strict_validation"))
        validation = await self._cyclone_validator.validate(context, tool_results, strict=strict)
        self._last_metrics and self._last_metrics.record_validation()
        return validation

    async def _run_decision_engine(
        self, context: AgentContext, reasoning: ReasoningResult, reflection: Any,
    ) -> DecisionRequest:
        return await self._decision_engine.evaluate(context, reasoning, reflection)

    async def _run_rl_service(
        self, decision: DecisionRequest, metrics: CycloneMetricsCollector,
    ) -> DecisionResponse | None:
        if not decision.need_rl or not self._rl_service:
            return None
        try:
            rl_response = await self._rl_service.optimize(decision)
            metrics.record_rl_call()
            return rl_response
        except RLOptimizationError as exc:
            logger.warning("cyclone_rl_optimization_failed", decision_id=decision.decision_id, error=str(exc))
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
        metrics: CycloneMetricsCollector,
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
            recommendations=reasoning.metadata.get("recommendations", []) or [
                s.content for s in reasoning.steps if s.metadata.get("recommendations")
            ],
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
    ) -> CycloneReport:
        return self._report_builder.build(
            context, reasoning, tool_results, reflection, validation,
            decision, rl_response, explainability,
        )

    async def _build_tool_specs(self, context: AgentContext) -> list[ToolCallSpec]:
        params = dict(context.request.context)
        params["digital_twin_state"] = context.digital_twin_state
        params["ckg_insights"] = context.metadata.get("ckg_insights")
        return [
            ToolCallSpec(tool_name=name, parameters=params)
            for name in ALL_CYCLONE_TOOL_NAMES
            if self.tool_manager.has_tool(name)
        ]

    async def _on_select_tools(
        self, context: AgentContext, reasoning: ReasoningResult,
    ) -> list[ToolCallSpec]:
        return await self._build_tool_specs(context)

    async def required_inputs(self) -> list[str]:
        return ["query"]

    async def _persist_cyclone_report(self, context: AgentContext, report: CycloneReport) -> None:
        from backend.agents.memory.memory_types import MemoryDomain, MemoryStoreRequest

        await self.memory_manager.store(
            MemoryStoreRequest(
                domain=MemoryDomain.WORKING,
                key=f"cyclone_report:{context.request_id}",
                value=report.model_dump(),
                session_id=context.user.session_id,
                metadata={"agent_id": self.agent_id, "type": "cyclone_report"},
            ),
        )
        self._last_metrics and self._last_metrics.record_memory_write()

    def _to_agent_report(self, cyclone_report: CycloneReport) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            request_id=cyclone_report.request_id,
            summary=cyclone_report.executive_summary,
            reasoning=cyclone_report.reasoning,
            risk={
                "level": cyclone_report.risk_level.value,
                "severity": cyclone_report.severity.value,
                "category": cyclone_report.category.value,
            },
            confidence=cyclone_report.confidence,
            recommendations=cyclone_report.recommendations,
            references=cyclone_report.references,
            tool_outputs=cyclone_report.tool_outputs,
            structured_output=cyclone_report.model_dump(),
            metadata={
                "cyclone_report_id": cyclone_report.report_id,
                "cyclone_name": cyclone_report.cyclone_name,
                "need_rl": cyclone_report.need_rl,
                "need_other_agents": cyclone_report.need_other_agents,
            },
        )

    def _cyclone_report_to_response(
        self, report: CycloneReport, metrics: Any, memory_refs: list[str],
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
                "cyclone_report_id": report.report_id,
                "cyclone_name": report.cyclone_name,
                "basin": report.basin.value,
                "risk_level": report.risk_level.value,
                "severity": report.severity.value,
                "category": report.category.value,
                "confidence": report.confidence,
                "landfall_probability": report.landfall_probability,
                "estimated_intensity_kt": report.estimated_intensity_kt,
                "storm_surge_m": report.storm_surge.surge_height_m,
                "recommendations": report.recommendations,
                "evidence": report.evidence,
                "need_rl": report.need_rl,
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
        if self._last_cyclone_report:
            update["metadata"] = {
                **update.get("metadata", {}),
                "cyclone_risk_level": self._last_cyclone_report.risk_level.value,
                "cyclone_severity": self._last_cyclone_report.severity.value,
                "cyclone_category": self._last_cyclone_report.category.value,
            }
        return update
