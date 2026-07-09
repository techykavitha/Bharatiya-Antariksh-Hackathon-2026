"""Urban Planning Agent — long-term climate adaptation and resilience planning."""

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
from backend.agents.specialized.urban_planning.urban_context import (
    KnowledgeGraphInsights,
    PeerAgentOutput,
    UrbanInputs,
)
from backend.agents.specialized.urban_planning.urban_metrics import UrbanMetricsCollector
from backend.agents.specialized.urban_planning.urban_models import (
    AGENT_FLOOD,
    AGENT_HEATWAVE,
    AGENT_WATER_RESOURCE,
    URBAN_PLANNING_AGENT_ID,
    UrbanResilienceLevel,
)
from backend.agents.specialized.urban_planning.urban_reasoning import (
    UrbanDecisionEngine,
    UrbanReasoningEngine,
)
from backend.agents.specialized.urban_planning.urban_reflection import UrbanReflectionEngine
from backend.agents.specialized.urban_planning.urban_report import UrbanPlanningReport, UrbanReportBuilder
from backend.agents.specialized.urban_planning.urban_tools import ALL_URBAN_TOOL_NAMES, create_urban_tools
from backend.agents.specialized.urban_planning.urban_validator import UrbanValidator
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
    AGENT_FLOOD: "flood",
    AGENT_WATER_RESOURCE: "water_stress",
    "air_quality_agent": "air_quality",
    "agriculture_agent": "agriculture",
}


class UrbanPlanningAgent(BaseSpecializedAgent):
    """
    Production-grade urban climate adaptation and planning agent.

    Evaluates long-term mitigation strategies for cities including UHI analysis,
    green infrastructure, drainage, and resilience scoring. Designed as core
    intelligence for Hyperion's future What-If Scenario Simulator.
    """

    AGENT_ID = URBAN_PLANNING_AGENT_ID

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
            URBAN_PLANNING_AGENT_ID,
            description="Urban climate adaptation, resilience planning, and long-term mitigation strategy agent",
            memory=memory,
            tools=create_urban_tools(),
            rl_engine=rl_engine,
            agent_communication=agent_communication,
            digital_twin=digital_twin,
            confidence_threshold=confidence_threshold,
        )
        self._rl_service = rl_service
        self._explanation_engine = explanation_engine
        self._graph_engine = graph_engine
        self._urban_reasoning = UrbanReasoningEngine(agent_id=URBAN_PLANNING_AGENT_ID)
        self._urban_reflection = UrbanReflectionEngine(
            agent_id=URBAN_PLANNING_AGENT_ID,
            confidence_threshold=confidence_threshold,
        )
        self._urban_validator = UrbanValidator(agent_id=URBAN_PLANNING_AGENT_ID)
        self._decision_engine = UrbanDecisionEngine(agent_id=URBAN_PLANNING_AGENT_ID)
        self._report_builder = UrbanReportBuilder(agent_id=URBAN_PLANNING_AGENT_ID)
        self._last_urban_report: UrbanPlanningReport | None = None
        self._last_urban_metrics: UrbanMetricsCollector | None = None

    @property
    def last_urban_report(self) -> UrbanPlanningReport | None:
        return self._last_urban_report

    @property
    def last_urban_metrics(self) -> UrbanMetricsCollector | None:
        return self._last_urban_metrics

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
    ) -> UrbanPlanningAgent:
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
                capability_id="urban_heat_island_analysis",
                name="Urban Heat Island Analysis",
                category=CapabilityCategory.ANALYSIS,
                keywords=["uhi", "heat island", "lst", "thermal"],
                required_tools=["building_tool", "ndvi_tool"],
            ),
            AgentCapability(
                capability_id="green_cover_assessment",
                name="Green Cover Assessment",
                category=CapabilityCategory.ANALYSIS,
                keywords=["green cover", "canopy", "vegetation"],
                required_tools=["green_cover_tool", "ndvi_tool"],
            ),
            AgentCapability(
                capability_id="green_roof_analysis",
                name="Green Roof Analysis",
                category=CapabilityCategory.PLANNING,
                keywords=["green roof", "cooling", "building"],
                required_tools=["building_tool"],
            ),
            AgentCapability(
                capability_id="cool_roof_recommendation",
                name="Cool Roof Recommendation",
                category=CapabilityCategory.PLANNING,
                keywords=["cool roof", "reflective", "mitigation"],
                required_tools=["building_tool"],
            ),
            AgentCapability(
                capability_id="tree_plantation_optimization",
                name="Tree Plantation Optimization",
                category=CapabilityCategory.OPTIMIZATION,
                keywords=["trees", "plantation", "canopy"],
                required_tools=["ndvi_tool", "green_cover_tool"],
            ),
            AgentCapability(
                capability_id="land_use_analysis",
                name="Land Use Analysis",
                category=CapabilityCategory.ANALYSIS,
                keywords=["land use", "zoning", "impervious"],
                required_tools=["land_use_tool"],
            ),
            AgentCapability(
                capability_id="drainage_capacity_assessment",
                name="Drainage Capacity Assessment",
                category=CapabilityCategory.ANALYSIS,
                keywords=["drainage", "stormwater", "capacity"],
                required_tools=["drainage_tool"],
            ),
            AgentCapability(
                capability_id="stormwater_management",
                name="Stormwater Management",
                category=CapabilityCategory.PLANNING,
                keywords=["stormwater", "rain garden", "detention"],
                required_tools=["drainage_tool", "road_tool"],
            ),
            AgentCapability(
                capability_id="road_network_climate_risk",
                name="Road Network Climate Risk",
                category=CapabilityCategory.ANALYSIS,
                keywords=["road", "transport", "permeable"],
                required_tools=["road_tool"],
            ),
            AgentCapability(
                capability_id="building_heat_exposure",
                name="Building Heat Exposure",
                category=CapabilityCategory.ANALYSIS,
                keywords=["building", "heat exposure", "density"],
                required_tools=["building_tool", "population_tool"],
            ),
            AgentCapability(
                capability_id="climate_adaptation_planning",
                name="Climate Adaptation Planning",
                category=CapabilityCategory.PLANNING,
                keywords=["adaptation", "mitigation", "resilience", "planning"],
                required_tools=["forecast_tool", "knowledge_graph_tool"],
            ),
            AgentCapability(
                capability_id="resilience_scoring",
                name="Resilience Scoring",
                category=CapabilityCategory.INTERPRETATION,
                keywords=["resilience", "score", "vulnerability"],
                required_tools=["infrastructure_tool", "drainage_tool", "green_cover_tool"],
            ),
        ]

    async def invoke(self, request: AgentRequest) -> AgentResponse:
        """
        Urban planning workflow:
        Observe → Analyze → Reason → Validate →
        Decision Framework → RL → Explainability → Report
        """
        if not self._initialized:
            await self.initialize()

        metrics = UrbanMetricsCollector(agent_id=self.agent_id, request_id=request.request_id)
        self._last_metrics = metrics
        self._last_urban_metrics = metrics
        self._status = AgentStatus.REASONING

        try:
            context = await self._run_observe(request, metrics)
            await self._collect_peer_inputs(context, request, metrics)
            tool_results = await self._run_analyze(context, metrics)
            reasoning, signals = await self._run_reason(context, tool_results, metrics)
            validation = await self._run_validate(context, tool_results)
            reflection = await self._urban_reflection.evaluate(context, reasoning, tool_results)
            decision = await self._run_decision_engine(context, reasoning, reflection)
            metrics.record_decision_request()

            if decision.need_other_agents and self._agent_communication:
                await self.call_other_agents(context, decision.need_other_agents, request)

            rl_response = await self._run_rl_service(decision, metrics)
            explainability = await self._run_explainability(
                context, reasoning, tool_results, reflection, validation,
                decision, rl_response, metrics,
            )

            urban_report = await self._run_report(
                context, reasoning, tool_results, reflection, validation,
                decision, rl_response, explainability,
            )
            self._last_urban_report = urban_report
            self._last_report = self._to_agent_report(urban_report)

            resilience_level = UrbanResilienceLevel(
                reasoning.metadata.get("resilience_level", UrbanResilienceLevel.MODERATE.value),
            )
            metrics.set_resilience_score(float(signals.resilience_score))
            metrics.set_resilience_level(resilience_level)
            metrics.set_confidence(urban_report.confidence)
            urban_metrics = metrics.finalize_urban()
            urban_report.metrics = urban_metrics

            memory_refs = await self.update_memory(context, self._last_report)
            await self._persist_urban_report(context, urban_report)
            await self.update_state(context, self._last_report)

            self._status = AgentStatus.COMPLETED
            return self._urban_report_to_response(urban_report, urban_metrics, memory_refs)

        except Exception as exc:
            self._status = AgentStatus.FAILED
            metrics.finalize()
            logger.error("urban_planning_agent_failed", request_id=request.request_id, error=str(exc))
            raise AgentInvocationError(
                f"Urban planning agent failed: {exc}",
                details={"agent_id": self.agent_id, "request_id": request.request_id},
            ) from exc

    async def _run_observe(
        self, request: AgentRequest, metrics: UrbanMetricsCollector,
    ) -> AgentContext:
        context = await self.retrieve_context(request)
        inputs = UrbanInputs.from_request_context(request.context)
        inputs.climate_state_available = request.climate_state is not None
        inputs.forecast_available = bool(
            request.context.get("forecast_available") or context.forecast.references,
        )
        inputs.digital_twin_available = bool(
            request.context.get("digital_twin_available") or request.context.get("twin_id"),
        )
        context.metadata["urban_inputs"] = inputs
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
            "urban_observe_complete",
            region_id=inputs.region_id,
            city=inputs.city_name,
        )
        return context

    async def _collect_peer_inputs(
        self,
        context: AgentContext,
        request: AgentRequest,
        metrics: UrbanMetricsCollector,
    ) -> None:
        inputs: UrbanInputs = context.metadata["urban_inputs"]
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

        context.metadata["urban_inputs"] = inputs
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
        self, inputs: UrbanInputs, metrics: UrbanMetricsCollector,
    ) -> KnowledgeGraphInsights:
        if not self._graph_engine:
            return KnowledgeGraphInsights()

        insights = KnowledgeGraphInsights()
        entity_id = inputs.region_id or "urban_ahmedabad"
        query_count = 0

        try:
            neighbors = await self._graph_engine.query.neighbors(entity_id)
            query_count += 1
            for n in neighbors:
                etype = n.entity.entity_type.value
                if etype in ("infrastructure", "power_grid", "hospital", "urban_area"):
                    insights.infrastructure_nodes.append(n.entity.entity_id)
                if etype == "population":
                    insights.population_nodes.append(n.entity.entity_id)
        except Exception as exc:
            logger.debug("ckg_neighbors_skipped", error=str(exc))

        try:
            agents_result = await self._graph_engine.query.affected_agents(entity_id)
            query_count += 1
            insights.urban_dependencies = [
                aid for a in agents_result.agents
                if (aid := getattr(a, "agent_id", None) or a.entity_id)
            ]
        except Exception as exc:
            logger.debug("ckg_affected_agents_skipped", error=str(exc))

        try:
            similar = await self._graph_engine.query.historical_similarity(entity_id, limit=3)
            query_count += 1
            insights.historical_mitigation_projects = [c.entity_id for c in similar.candidates]
        except Exception as exc:
            logger.debug("ckg_historical_similarity_skipped", error=str(exc))

        try:
            events = await self._graph_engine.query.related_events(entity_id, limit=5)
            query_count += 1
            for event in events.events:
                insights.historical_mitigation_projects.append(event.entity_id)
        except Exception as exc:
            logger.debug("ckg_related_events_skipped", error=str(exc))

        insights.query_count = query_count
        metrics.record_ckg_query(query_count)
        return insights

    async def _run_analyze(
        self, context: AgentContext, metrics: UrbanMetricsCollector,
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
        metrics: UrbanMetricsCollector,
    ) -> tuple[ReasoningResult, Any]:
        reasoning, signals = await self._urban_reasoning.run(context, tool_results)
        metrics.record_reasoning(sum(s.duration_ms for s in reasoning.steps))
        return reasoning, signals

    async def _run_validate(
        self, context: AgentContext, tool_results: list[ToolResult],
    ) -> Any:
        strict = bool(context.request.context.get("strict_validation"))
        validation = await self._urban_validator.validate(context, tool_results, strict=strict)
        self._last_metrics and self._last_metrics.record_validation()
        return validation

    async def _run_decision_engine(
        self, context: AgentContext, reasoning: ReasoningResult, reflection: Any,
    ) -> DecisionRequest:
        return await self._decision_engine.evaluate(context, reasoning, reflection)

    async def _run_rl_service(
        self, decision: DecisionRequest, metrics: UrbanMetricsCollector,
    ) -> DecisionResponse | None:
        if not decision.need_rl or not self._rl_service:
            return None
        try:
            rl_response = await self._rl_service.optimize(decision)
            metrics.record_rl_call()
            return rl_response
        except RLOptimizationError as exc:
            logger.warning("urban_rl_optimization_failed", decision_id=decision.decision_id, error=str(exc))
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
        metrics: UrbanMetricsCollector,
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
    ) -> UrbanPlanningReport:
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
            for name in ALL_URBAN_TOOL_NAMES
            if self.tool_manager.has_tool(name)
        ]

    async def _on_select_tools(
        self, context: AgentContext, reasoning: ReasoningResult,
    ) -> list[ToolCallSpec]:
        return await self._build_tool_specs(context)

    async def required_inputs(self) -> list[str]:
        return ["query"]

    async def _persist_urban_report(
        self, context: AgentContext, report: UrbanPlanningReport,
    ) -> None:
        from backend.agents.memory.memory_types import MemoryDomain, MemoryStoreRequest

        await self.memory_manager.store(
            MemoryStoreRequest(
                domain=MemoryDomain.WORKING,
                key=f"urban_report:{context.request_id}",
                value=report.model_dump(),
                session_id=context.user.session_id,
                metadata={"agent_id": self.agent_id, "type": "urban_report"},
            ),
        )
        self._last_metrics and self._last_metrics.record_memory_write()

    def _to_agent_report(self, urban_report: UrbanPlanningReport) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            request_id=urban_report.request_id,
            summary=urban_report.executive_summary,
            reasoning=urban_report.reasoning,
            risk={
                "level": urban_report.resilience_level.value,
                "resilience_score": urban_report.urban_resilience_score,
            },
            confidence=urban_report.confidence,
            recommendations=urban_report.recommendations,
            references=urban_report.references,
            tool_outputs=urban_report.tool_outputs,
            structured_output=urban_report.model_dump(),
            metadata={
                "urban_report_id": urban_report.report_id,
                "resilience_level": urban_report.resilience_level.value,
                "need_rl": urban_report.need_rl,
                "need_other_agents": urban_report.need_other_agents,
                "city_name": urban_report.metadata.get("city_name"),
            },
        )

    def _urban_report_to_response(
        self, report: UrbanPlanningReport, metrics: Any, memory_refs: list[str],
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
                "urban_report_id": report.report_id,
                "resilience_level": report.resilience_level.value,
                "urban_resilience_score": report.urban_resilience_score,
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
        if self._last_urban_report:
            update["metadata"] = {
                **update.get("metadata", {}),
                "resilience_level": self._last_urban_report.resilience_level.value,
                "urban_resilience_score": self._last_urban_report.urban_resilience_score,
                "city_name": self._last_urban_report.metadata.get("city_name"),
            }
        return update
