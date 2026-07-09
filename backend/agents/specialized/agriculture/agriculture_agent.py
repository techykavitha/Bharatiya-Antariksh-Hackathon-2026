"""Agriculture Agent — precision agriculture and climate-informed crop advisory."""

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
from backend.agents.specialized.agriculture.agriculture_context import (
    AgricultureInputs,
    KnowledgeGraphInsights,
    PeerAgentOutput,
    RagRetrievalResult,
)
from backend.agents.specialized.agriculture.agriculture_metrics import AgricultureMetricsCollector
from backend.agents.specialized.agriculture.agriculture_models import (
    AGENT_FLOOD,
    AGENT_HEATWAVE,
    AGENT_URBAN_PLANNING,
    AGENT_WATER_RESOURCE,
    AGRICULTURE_AGENT_ID,
)
from backend.agents.specialized.agriculture.agriculture_rag import AgricultureRagService
from backend.agents.specialized.agriculture.agriculture_reasoning import (
    AgricultureDecisionEngine,
    AgricultureReasoningEngine,
)
from backend.agents.specialized.agriculture.agriculture_reflection import AgricultureReflectionEngine
from backend.agents.specialized.agriculture.agriculture_report import AgricultureReport, AgricultureReportBuilder
from backend.agents.specialized.agriculture.agriculture_tools import (
    ALL_AGRICULTURE_TOOL_NAMES,
    create_agriculture_tools,
)
from backend.agents.specialized.agriculture.agriculture_validator import AgricultureValidator
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
    AGENT_WATER_RESOURCE: "water_stress",
    AGENT_HEATWAVE: "heatwave",
    AGENT_FLOOD: "flood",
    AGENT_URBAN_PLANNING: "urban",
}


class AgricultureAgent(BaseSpecializedAgent):
    """
    Production-grade precision agriculture agent.

    Combines climate intelligence, remote sensing, water resource analysis,
    crop phenology, RAG knowledge retrieval, and government advisories to
    generate actionable recommendations for farmers and policymakers.
    """

    AGENT_ID = AGRICULTURE_AGENT_ID

    def __init__(
        self,
        *,
        memory: MemoryManager,
        rl_engine: SpecializedRLEngineInterface | None = None,
        rl_service: RLOptimizationService | None = None,
        explanation_engine: ExplanationEngine | None = None,
        graph_engine: GraphEngine | None = None,
        rag_service: AgricultureRagService | None = None,
        agent_communication: AgentCommunicationInterface | None = None,
        digital_twin: DigitalTwinInterface | None = None,
        confidence_threshold: float = 0.45,
    ) -> None:
        super().__init__(
            AGRICULTURE_AGENT_ID,
            description="Precision agriculture agent combining remote sensing, climate intelligence, and RAG advisories",
            memory=memory,
            tools=create_agriculture_tools(),
            rl_engine=rl_engine,
            agent_communication=agent_communication,
            digital_twin=digital_twin,
            confidence_threshold=confidence_threshold,
        )
        self._rl_service = rl_service
        self._explanation_engine = explanation_engine
        self._graph_engine = graph_engine
        self._rag_service = rag_service or AgricultureRagService()
        self._agriculture_reasoning = AgricultureReasoningEngine(agent_id=AGRICULTURE_AGENT_ID)
        self._agriculture_reflection = AgricultureReflectionEngine(
            agent_id=AGRICULTURE_AGENT_ID,
            confidence_threshold=confidence_threshold,
        )
        self._agriculture_validator = AgricultureValidator(agent_id=AGRICULTURE_AGENT_ID)
        self._decision_engine = AgricultureDecisionEngine(agent_id=AGRICULTURE_AGENT_ID)
        self._report_builder = AgricultureReportBuilder(agent_id=AGRICULTURE_AGENT_ID)
        self._last_agriculture_report: AgricultureReport | None = None
        self._last_agriculture_metrics: AgricultureMetricsCollector | None = None

    @property
    def last_agriculture_report(self) -> AgricultureReport | None:
        return self._last_agriculture_report

    @property
    def last_agriculture_metrics(self) -> AgricultureMetricsCollector | None:
        return self._last_agriculture_metrics

    @classmethod
    async def create(
        cls,
        memory: MemoryManager,
        *,
        rl_engine: SpecializedRLEngineInterface | None = None,
        rl_service: RLOptimizationService | None = None,
        explanation_engine: ExplanationEngine | None = None,
        graph_engine: GraphEngine | None = None,
        rag_service: AgricultureRagService | None = None,
        agent_communication: AgentCommunicationInterface | None = None,
        digital_twin: DigitalTwinInterface | None = None,
    ) -> AgricultureAgent:
        agent = cls(
            memory=memory,
            rl_engine=rl_engine,
            rl_service=rl_service,
            explanation_engine=explanation_engine,
            graph_engine=graph_engine,
            rag_service=rag_service,
            agent_communication=agent_communication,
            digital_twin=digital_twin,
        )
        await agent.initialize()
        return agent

    async def declare_capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                capability_id="crop_health_assessment",
                name="Crop Health Assessment",
                category=CapabilityCategory.ANALYSIS,
                keywords=["crop", "health", "ndvi", "evi", "vigor"],
                required_tools=["ndvi_tool", "evi_tool"],
            ),
            AgentCapability(
                capability_id="crop_suitability",
                name="Crop Suitability",
                category=CapabilityCategory.ANALYSIS,
                keywords=["suitability", "crop", "land use"],
                required_tools=["land_use_tool", "knowledge_graph_tool"],
            ),
            AgentCapability(
                capability_id="phenology_monitoring",
                name="Phenology Monitoring",
                category=CapabilityCategory.MONITORING,
                keywords=["phenology", "growth stage", "calendar"],
                required_tools=["crop_calendar_tool"],
            ),
            AgentCapability(
                capability_id="soil_moisture_assessment",
                name="Soil Moisture Assessment",
                category=CapabilityCategory.ANALYSIS,
                keywords=["soil", "moisture", "irrigation"],
                required_tools=["soil_moisture_tool"],
            ),
            AgentCapability(
                capability_id="irrigation_recommendation",
                name="Irrigation Recommendation",
                category=CapabilityCategory.PLANNING,
                keywords=["irrigation", "water", "scheduling"],
                required_tools=["irrigation_tool", "soil_moisture_tool"],
            ),
            AgentCapability(
                capability_id="yield_risk_assessment",
                name="Yield Risk Assessment",
                category=CapabilityCategory.PREDICTION,
                keywords=["yield", "risk", "production"],
                required_tools=["yield_estimation_tool"],
            ),
            AgentCapability(
                capability_id="drought_risk",
                name="Drought Risk",
                category=CapabilityCategory.ANALYSIS,
                keywords=["drought", "water stress", "deficit"],
                required_tools=["soil_moisture_tool", "weather_tool", "forecast_tool"],
            ),
            AgentCapability(
                capability_id="flood_impact_assessment",
                name="Flood Impact Assessment",
                category=CapabilityCategory.ANALYSIS,
                keywords=["flood", "waterlogging", "crop damage"],
                required_tools=["weather_tool"],
            ),
            AgentCapability(
                capability_id="heat_stress_crops",
                name="Heat Stress on Crops",
                category=CapabilityCategory.ANALYSIS,
                keywords=["heat", "temperature", "stress"],
                required_tools=["weather_tool"],
            ),
            AgentCapability(
                capability_id="pest_favorability",
                name="Pest Favorability Estimation",
                category=CapabilityCategory.PREDICTION,
                keywords=["pest", "disease", "humidity"],
                required_tools=["weather_tool"],
            ),
            AgentCapability(
                capability_id="climate_adaptation_planning",
                name="Climate Adaptation Planning",
                category=CapabilityCategory.PLANNING,
                keywords=["adaptation", "resilience", "climate"],
                required_tools=["forecast_tool", "knowledge_graph_tool"],
            ),
            AgentCapability(
                capability_id="agricultural_resilience_scoring",
                name="Agricultural Resilience Scoring",
                category=CapabilityCategory.INTERPRETATION,
                keywords=["resilience", "score", "sustainability"],
                required_tools=["yield_estimation_tool", "soil_moisture_tool"],
            ),
        ]

    async def invoke(self, request: AgentRequest) -> AgentResponse:
        """
        Agriculture workflow:
        Observe → Analyze → Retrieve Knowledge (RAG) → Reason → Validate →
        Decision Framework → RL → Explainability → Report
        """
        if not self._initialized:
            await self.initialize()

        metrics = AgricultureMetricsCollector(agent_id=self.agent_id, request_id=request.request_id)
        self._last_metrics = metrics
        self._last_agriculture_metrics = metrics
        self._status = AgentStatus.REASONING

        try:
            context = await self._run_observe(request, metrics)
            await self._collect_peer_inputs(context, request, metrics)
            tool_results = await self._run_analyze(context, metrics)
            rag_result = await self._run_rag_retrieval(context, metrics)
            reasoning, signals = await self._run_reason(context, tool_results, rag_result, metrics)
            validation = await self._run_validate(context, tool_results)
            reflection = await self._agriculture_reflection.evaluate(context, reasoning, tool_results)
            decision = await self._run_decision_engine(context, reasoning, reflection)
            metrics.record_decision_request()

            if decision.need_other_agents and self._agent_communication:
                await self.call_other_agents(context, decision.need_other_agents, request)

            rl_response = await self._run_rl_service(decision, metrics)
            explainability = await self._run_explainability(
                context, reasoning, tool_results, reflection, validation,
                decision, rl_response, metrics,
            )

            agriculture_report = await self._run_report(
                context, reasoning, tool_results, reflection, validation,
                decision, rag_result, rl_response, explainability,
            )
            self._last_agriculture_report = agriculture_report
            self._last_report = self._to_agent_report(agriculture_report)

            metrics.set_resilience_score(float(signals.resilience_score))
            metrics.set_confidence(agriculture_report.confidence)
            ag_metrics = metrics.finalize_agriculture()
            agriculture_report.metrics = ag_metrics

            memory_refs = await self.update_memory(context, self._last_report)
            await self._persist_agriculture_report(context, agriculture_report)
            await self.update_state(context, self._last_report)

            self._status = AgentStatus.COMPLETED
            return self._agriculture_report_to_response(agriculture_report, ag_metrics, memory_refs)

        except Exception as exc:
            self._status = AgentStatus.FAILED
            metrics.finalize()
            logger.error("agriculture_agent_failed", request_id=request.request_id, error=str(exc))
            raise AgentInvocationError(
                f"Agriculture agent failed: {exc}",
                details={"agent_id": self.agent_id, "request_id": request.request_id},
            ) from exc

    async def _run_observe(
        self, request: AgentRequest, metrics: AgricultureMetricsCollector,
    ) -> AgentContext:
        context = await self.retrieve_context(request)
        inputs = AgricultureInputs.from_request_context(request.context)
        inputs.climate_state_available = request.climate_state is not None
        inputs.forecast_available = bool(
            request.context.get("forecast_available") or context.forecast.references,
        )
        inputs.digital_twin_available = bool(
            request.context.get("digital_twin_available") or request.context.get("twin_id"),
        )
        context.metadata["agriculture_inputs"] = inputs
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
            "agriculture_observe_complete",
            region_id=inputs.region_id,
            crop=inputs.crop_type,
        )
        return context

    async def _collect_peer_inputs(
        self,
        context: AgentContext,
        request: AgentRequest,
        metrics: AgricultureMetricsCollector,
    ) -> None:
        inputs: AgricultureInputs = context.metadata["agriculture_inputs"]
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

        context.metadata["agriculture_inputs"] = inputs
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
        self, inputs: AgricultureInputs, metrics: AgricultureMetricsCollector,
    ) -> KnowledgeGraphInsights:
        if not self._graph_engine:
            return KnowledgeGraphInsights()

        insights = KnowledgeGraphInsights()
        entity_id = inputs.region_id or "agriculture_tn_delta"
        query_count = 0

        try:
            neighbors = await self._graph_engine.query.neighbors(entity_id)
            query_count += 1
            for n in neighbors:
                etype = n.entity.entity_type.value
                if etype == "agriculture":
                    insights.crop_dependencies.append(n.entity.entity_id)
                if etype in ("reservoir", "river"):
                    insights.water_dependencies.append(n.entity.entity_id)
        except Exception as exc:
            logger.debug("ckg_neighbors_skipped", error=str(exc))

        try:
            chain = await self._graph_engine.query.impact_chain(entity_id, max_depth=3)
            query_count += 1
            if chain.chain:
                insights.historical_impacts = [e.entity_id for e in chain.chain[:5]]
        except Exception as exc:
            logger.debug("ckg_impact_chain_skipped", error=str(exc))

        try:
            similar = await self._graph_engine.query.historical_similarity(entity_id, limit=3)
            query_count += 1
            insights.regional_suitability = [c.entity_id for c in similar.candidates]
        except Exception as exc:
            logger.debug("ckg_historical_similarity_skipped", error=str(exc))

        insights.query_count = query_count
        metrics.record_ckg_query(query_count)
        return insights

    async def _run_analyze(
        self, context: AgentContext, metrics: AgricultureMetricsCollector,
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

    async def _run_rag_retrieval(
        self, context: AgentContext, metrics: AgricultureMetricsCollector,
    ) -> RagRetrievalResult:
        inputs: AgricultureInputs = context.metadata["agriculture_inputs"]
        query = (
            f"{inputs.crop_type} {inputs.season} agriculture advisory "
            f"{inputs.state or inputs.region_id or ''} climate adaptation"
        )
        rag_result = await self._rag_service.retrieve_for_context(
            query,
            crop_type=inputs.crop_type,
            region=inputs.region_id,
            state=inputs.state,
            season=inputs.season,
        )
        context.metadata["rag_result"] = rag_result
        context.request.context["rag_result"] = rag_result.model_dump()
        metrics.record_rag_retrieval(rag_result.retrieval_count)
        return rag_result

    async def _run_reason(
        self,
        context: AgentContext,
        tool_results: list[ToolResult],
        rag_result: RagRetrievalResult,
        metrics: AgricultureMetricsCollector,
    ) -> tuple[ReasoningResult, Any]:
        reasoning, signals = await self._agriculture_reasoning.run(
            context, tool_results, rag_result,
        )
        metrics.record_reasoning(sum(s.duration_ms for s in reasoning.steps))
        return reasoning, signals

    async def _run_validate(
        self, context: AgentContext, tool_results: list[ToolResult],
    ) -> Any:
        strict = bool(context.request.context.get("strict_validation"))
        validation = await self._agriculture_validator.validate(context, tool_results, strict=strict)
        self._last_metrics and self._last_metrics.record_validation()
        return validation

    async def _run_decision_engine(
        self, context: AgentContext, reasoning: ReasoningResult, reflection: Any,
    ) -> DecisionRequest:
        return await self._decision_engine.evaluate(context, reasoning, reflection)

    async def _run_rl_service(
        self, decision: DecisionRequest, metrics: AgricultureMetricsCollector,
    ) -> DecisionResponse | None:
        if not decision.need_rl or not self._rl_service:
            return None
        try:
            rl_response = await self._rl_service.optimize(decision)
            metrics.record_rl_call()
            return rl_response
        except RLOptimizationError as exc:
            logger.warning("agriculture_rl_optimization_failed", decision_id=decision.decision_id, error=str(exc))
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
        metrics: AgricultureMetricsCollector,
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
        rag_result: RagRetrievalResult,
        rl_response: DecisionResponse | None = None,
        explainability: Any = None,
    ) -> AgricultureReport:
        return self._report_builder.build(
            context, reasoning, tool_results, validation, decision,
            rag_result, reflection, rl_response, explainability,
        )

    async def _build_tool_specs(self, context: AgentContext) -> list[ToolCallSpec]:
        params = dict(context.request.context)
        params["digital_twin_state"] = context.digital_twin_state
        params["ckg_insights"] = context.metadata.get("ckg_insights")
        params["rag_result"] = context.metadata.get("rag_result")
        return [
            ToolCallSpec(tool_name=name, parameters=params)
            for name in ALL_AGRICULTURE_TOOL_NAMES
            if self.tool_manager.has_tool(name)
        ]

    async def _on_select_tools(
        self, context: AgentContext, reasoning: ReasoningResult,
    ) -> list[ToolCallSpec]:
        return await self._build_tool_specs(context)

    async def required_inputs(self) -> list[str]:
        return ["query"]

    async def _persist_agriculture_report(
        self, context: AgentContext, report: AgricultureReport,
    ) -> None:
        from backend.agents.memory.memory_types import MemoryDomain, MemoryStoreRequest

        await self.memory_manager.store(
            MemoryStoreRequest(
                domain=MemoryDomain.WORKING,
                key=f"agriculture_report:{context.request_id}",
                value=report.model_dump(),
                session_id=context.user.session_id,
                metadata={"agent_id": self.agent_id, "type": "agriculture_report"},
            ),
        )
        self._last_metrics and self._last_metrics.record_memory_write()

    def _to_agent_report(self, report: AgricultureReport) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            request_id=report.request_id,
            summary=report.executive_summary,
            reasoning=report.reasoning,
            risk={
                "yield_risk_level": report.yield_risk.risk_level.value,
                "resilience_score": report.resilience_score,
            },
            confidence=report.confidence,
            recommendations=report.recommendations,
            references=report.references,
            tool_outputs=report.tool_outputs,
            structured_output=report.model_dump(),
            metadata={
                "agriculture_report_id": report.report_id,
                "crop_type": report.metadata.get("crop_type"),
                "need_rl": report.need_rl,
                "rag_documents": len(report.rag_documents),
            },
        )

    def _agriculture_report_to_response(
        self, report: AgricultureReport, metrics: Any, memory_refs: list[str],
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
                "agriculture_report_id": report.report_id,
                "crop_type": report.metadata.get("crop_type"),
                "yield_risk_level": report.yield_risk.risk_level.value,
                "resilience_score": report.resilience_score,
                "confidence": report.confidence,
                "recommendations": report.recommendations,
                "evidence": report.evidence,
                "need_rl": report.need_rl,
                "chosen_action": report.chosen_action,
                "rag_document_count": len(report.rag_documents),
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
        if self._last_agriculture_report:
            update["metadata"] = {
                **update.get("metadata", {}),
                "crop_type": self._last_agriculture_report.metadata.get("crop_type"),
                "yield_risk_level": self._last_agriculture_report.yield_risk.risk_level.value,
                "resilience_score": self._last_agriculture_report.resilience_score,
            }
        return update
