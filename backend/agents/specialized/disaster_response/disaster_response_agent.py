"""Disaster Response Agent — multi-hazard coordination and emergency planning."""

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
from backend.agents.specialized.disaster_response.disaster_context import (
    DisasterInputs,
    HazardAgentOutput,
    KnowledgeGraphInsights,
)
from backend.agents.specialized.disaster_response.disaster_metrics import DisasterMetricsCollector
from backend.agents.specialized.disaster_response.disaster_models import (
    AGENT_CYCLONE,
    AGENT_FLOOD,
    AGENT_HEATWAVE,
    AGENT_WATER_RESOURCE,
    DISASTER_RESPONSE_AGENT_ID,
    EmergencyPriority,
    HazardType,
)
from backend.agents.specialized.disaster_response.disaster_reasoning import (
    DisasterDecisionEngine,
    DisasterReasoningEngine,
)
from backend.agents.specialized.disaster_response.disaster_reflection import DisasterReflectionEngine
from backend.agents.specialized.disaster_response.disaster_report import (
    DisasterReportBuilder,
    DisasterResponseReport,
)
from backend.agents.specialized.disaster_response.disaster_tools import (
    ALL_DISASTER_TOOL_NAMES,
    create_disaster_tools,
)
from backend.agents.specialized.disaster_response.disaster_validator import DisasterValidator
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

_AGENT_HAZARD_MAP: dict[str, HazardType] = {
    AGENT_FLOOD: HazardType.FLOOD,
    AGENT_CYCLONE: HazardType.CYCLONE,
    AGENT_HEATWAVE: HazardType.HEATWAVE,
    AGENT_WATER_RESOURCE: HazardType.WATER_STRESS,
    "agriculture_agent": HazardType.AGRICULTURE,
    "air_quality_agent": HazardType.AIR_QUALITY,
}


class DisasterResponseAgent(BaseSpecializedAgent):
    """
    Production-grade disaster response coordination agent.

    Combines outputs from specialized hazard agents to generate actionable
    emergency response plans. Integrates Decision Framework, RL Optimization,
    Explainability, and Climate Knowledge Graph.
    """

    AGENT_ID = DISASTER_RESPONSE_AGENT_ID

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
            DISASTER_RESPONSE_AGENT_ID,
            description="Multi-hazard disaster response coordination and emergency planning agent",
            memory=memory,
            tools=create_disaster_tools(),
            rl_engine=rl_engine,
            agent_communication=agent_communication,
            digital_twin=digital_twin,
            confidence_threshold=confidence_threshold,
        )
        self._rl_service = rl_service
        self._explanation_engine = explanation_engine
        self._graph_engine = graph_engine
        self._disaster_reasoning = DisasterReasoningEngine(agent_id=DISASTER_RESPONSE_AGENT_ID)
        self._disaster_reflection = DisasterReflectionEngine(
            agent_id=DISASTER_RESPONSE_AGENT_ID,
            confidence_threshold=confidence_threshold,
        )
        self._disaster_validator = DisasterValidator(agent_id=DISASTER_RESPONSE_AGENT_ID)
        self._decision_engine = DisasterDecisionEngine(agent_id=DISASTER_RESPONSE_AGENT_ID)
        self._report_builder = DisasterReportBuilder(agent_id=DISASTER_RESPONSE_AGENT_ID)
        self._last_disaster_report: DisasterResponseReport | None = None
        self._last_disaster_metrics: DisasterMetricsCollector | None = None

    @property
    def last_disaster_report(self) -> DisasterResponseReport | None:
        return self._last_disaster_report

    @property
    def last_disaster_metrics(self) -> DisasterMetricsCollector | None:
        return self._last_disaster_metrics

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
    ) -> DisasterResponseAgent:
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
                capability_id="multi_hazard_assessment",
                name="Multi-hazard Assessment",
                category=CapabilityCategory.ANALYSIS,
                keywords=["multi-hazard", "compound", "disaster", "assessment"],
                required_tools=["population_tool", "forecast_tool"],
            ),
            AgentCapability(
                capability_id="emergency_prioritization",
                name="Emergency Prioritization",
                category=CapabilityCategory.PLANNING,
                keywords=["priority", "ranking", "emergency"],
                required_tools=["population_tool"],
            ),
            AgentCapability(
                capability_id="resource_allocation",
                name="Resource Allocation",
                category=CapabilityCategory.OPTIMIZATION,
                keywords=["resource", "relief", "allocation"],
                required_tools=["emergency_resource_tool", "relief_inventory_tool"],
            ),
            AgentCapability(
                capability_id="evacuation_planning",
                name="Evacuation Planning",
                category=CapabilityCategory.PLANNING,
                keywords=["evacuation", "shelter", "corridor"],
                required_tools=["shelter_tool", "road_network_tool", "population_tool"],
            ),
            AgentCapability(
                capability_id="relief_distribution",
                name="Relief Distribution",
                category=CapabilityCategory.PLANNING,
                keywords=["relief", "distribution", "supplies"],
                required_tools=["relief_inventory_tool", "emergency_resource_tool"],
            ),
            AgentCapability(
                capability_id="infrastructure_protection",
                name="Critical Infrastructure Protection",
                category=CapabilityCategory.ANALYSIS,
                keywords=["infrastructure", "protection", "lifelines"],
                required_tools=["critical_infrastructure_tool"],
            ),
            AgentCapability(
                capability_id="shelter_planning",
                name="Shelter Planning",
                category=CapabilityCategory.PLANNING,
                keywords=["shelter", "displacement", "camp"],
                required_tools=["shelter_tool"],
            ),
            AgentCapability(
                capability_id="medical_response",
                name="Medical Response Planning",
                category=CapabilityCategory.PLANNING,
                keywords=["medical", "hospital", "trauma"],
                required_tools=["hospital_tool"],
            ),
            AgentCapability(
                capability_id="emergency_logistics",
                name="Emergency Logistics",
                category=CapabilityCategory.PLANNING,
                keywords=["logistics", "transport", "supply"],
                required_tools=["road_network_tool", "relief_inventory_tool"],
            ),
            AgentCapability(
                capability_id="inter_agency_coordination",
                name="Inter-agency Coordination",
                category=CapabilityCategory.COMMUNICATION,
                keywords=["coordination", "agency", "communication"],
                required_tools=["communication_tool"],
            ),
            AgentCapability(
                capability_id="recovery_planning",
                name="Recovery Planning",
                category=CapabilityCategory.PLANNING,
                keywords=["recovery", "rehabilitation", "rebuild"],
                required_tools=["knowledge_graph_tool"],
            ),
        ]

    async def invoke(self, request: AgentRequest) -> AgentResponse:
        """
        Disaster response workflow:
        Observe → Collect Hazard Inputs → Analyze → Reason → Validate →
        Decision Framework → RL Optimization → Explainability → Report
        """
        if not self._initialized:
            await self.initialize()

        metrics = DisasterMetricsCollector(
            agent_id=self.agent_id, request_id=request.request_id,
        )
        self._last_metrics = metrics
        self._last_disaster_metrics = metrics
        self._status = AgentStatus.REASONING

        try:
            context = await self._run_observe(request, metrics)
            await self._collect_hazard_inputs(context, request, metrics)
            tool_results = await self._run_analyze(context, metrics)
            reasoning, signals = await self._run_reason(context, tool_results, metrics)
            validation = await self._run_validate(context, tool_results)
            reflection = await self._disaster_reflection.evaluate(context, reasoning, tool_results)
            decision = await self._run_decision_engine(context, reasoning, reflection)
            metrics.record_decision_request()

            consult_agents = list(decision.need_other_agents)
            if consult_agents and self._agent_communication:
                await self.call_other_agents(context, consult_agents, request)

            rl_response = await self._run_rl_service(decision, metrics)
            explainability = await self._run_explainability(
                context, reasoning, tool_results, reflection, validation,
                decision, rl_response, metrics,
            )

            disaster_report = await self._run_report(
                context, reasoning, tool_results, reflection, validation,
                decision, rl_response, explainability,
            )
            self._last_disaster_report = disaster_report
            self._last_report = self._to_agent_report(disaster_report)

            emergency = EmergencyPriority(
                decision.metadata.get("emergency_priority", EmergencyPriority.ROUTINE.value),
            )
            metrics.set_emergency_priority(emergency)
            metrics.set_priority_score(float(signals.composite_priority_score))
            metrics.set_confidence(disaster_report.confidence)
            disaster_metrics = metrics.finalize_disaster()
            disaster_report.metrics = disaster_metrics

            memory_refs = await self.update_memory(context, self._last_report)
            await self._persist_disaster_report(context, disaster_report)
            await self.update_state(context, self._last_report)

            self._status = AgentStatus.COMPLETED
            return self._disaster_report_to_response(disaster_report, disaster_metrics, memory_refs)

        except Exception as exc:
            self._status = AgentStatus.FAILED
            metrics.finalize()
            logger.error("disaster_response_agent_failed", request_id=request.request_id, error=str(exc))
            raise AgentInvocationError(
                f"Disaster response agent failed: {exc}",
                details={"agent_id": self.agent_id, "request_id": request.request_id},
            ) from exc

    async def _run_observe(
        self, request: AgentRequest, metrics: DisasterMetricsCollector,
    ) -> AgentContext:
        context = await self.retrieve_context(request)
        inputs = DisasterInputs.from_request_context(request.context)
        inputs.climate_state_available = request.climate_state is not None
        inputs.forecast_available = bool(
            request.context.get("forecast_available") or context.forecast.references,
        )
        inputs.digital_twin_available = bool(
            request.context.get("digital_twin_available") or request.context.get("twin_id"),
        )
        context.metadata["disaster_inputs"] = inputs
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
            "disaster_observe_complete",
            region_id=inputs.region_id,
            hazard_count=len(inputs.hazard_agent_outputs),
        )
        return context

    async def _collect_hazard_inputs(
        self,
        context: AgentContext,
        request: AgentRequest,
        metrics: DisasterMetricsCollector,
    ) -> None:
        inputs: DisasterInputs = context.metadata["disaster_inputs"]
        missing = [
            agent_id for agent_id in inputs.consult_agents
            if agent_id not in inputs.hazard_agent_outputs
        ]
        if not missing or not self._agent_communication:
            metrics.record_hazard_agents_consulted(len(inputs.hazard_agent_outputs))
            context.request.context["hazard_agent_outputs"] = {
                k: v.model_dump() for k, v in inputs.hazard_agent_outputs.items()
            }
            return

        delegations = await self.call_other_agents(context, missing, request)
        for result in delegations:
            if not result.success:
                continue
            hazard = self._hazard_from_delegation(result.agent_id, result.structured_output, result.content)
            inputs.hazard_agent_outputs[result.agent_id] = hazard

        context.metadata["disaster_inputs"] = inputs
        context.request.context["hazard_agent_outputs"] = {
            k: v.model_dump() for k, v in inputs.hazard_agent_outputs.items()
        }
        metrics.record_hazard_agents_consulted(len(inputs.hazard_agent_outputs))
        context.add_reasoning(
            f"Collected hazard inputs from {len(inputs.hazard_agent_outputs)} agent(s)",
        )

    def _hazard_from_delegation(
        self,
        agent_id: str,
        structured: dict[str, Any] | None,
        content: str | None,
    ) -> HazardAgentOutput:
        data = structured or {}
        severity = str(data.get("severity") or data.get("risk_level") or "moderate")
        return HazardAgentOutput(
            agent_id=agent_id,
            hazard_type=_AGENT_HAZARD_MAP.get(agent_id, HazardType.UNKNOWN),
            severity=severity,
            risk_level=str(data.get("risk_level", severity)),
            confidence=float(data.get("confidence", 0.7)),
            summary=str(data.get("executive_summary") or data.get("summary") or content or ""),
            affected_regions=list(data.get("affected_regions", data.get("districts", []))),
            affected_population=int(data.get("affected_population", 0)),
            recommendations=list(data.get("recommendations", [])),
            structured_output=data,
            consulted_live=True,
        )

    async def _query_knowledge_graph(
        self, inputs: DisasterInputs, metrics: DisasterMetricsCollector,
    ) -> KnowledgeGraphInsights:
        if not self._graph_engine:
            return KnowledgeGraphInsights()

        insights = KnowledgeGraphInsights()
        entity_id = inputs.region_id or "flood_chennai_2015"
        query_count = 0

        try:
            neighbors = await self._graph_engine.query.neighbors(entity_id)
            query_count += 1
            for n in neighbors:
                etype = n.entity.entity_type.value
                if etype in ("infrastructure", "port", "power_plant", "hospital", "water_treatment"):
                    insights.affected_infrastructure.append(n.entity.entity_id)
        except Exception as exc:
            logger.debug("ckg_neighbors_skipped", error=str(exc))

        try:
            agents_result = await self._graph_engine.query.affected_agents(entity_id)
            query_count += 1
            insights.population_dependencies = [
                aid for a in agents_result.agents
                if (aid := getattr(a, "agent_id", None) or a.entity_id)
            ]
        except Exception as exc:
            logger.debug("ckg_affected_agents_skipped", error=str(exc))

        try:
            chain = await self._graph_engine.query.impact_chain(entity_id, max_depth=4)
            query_count += 1
            if chain.chain:
                insights.cascade_impacts = [[e.entity_id for e in chain.chain[:5]]]
        except Exception as exc:
            logger.debug("ckg_impact_chain_skipped", error=str(exc))

        try:
            similar = await self._graph_engine.query.historical_similarity(entity_id, limit=3)
            query_count += 1
            insights.historical_responses = [c.entity_id for c in similar.candidates]
        except Exception as exc:
            logger.debug("ckg_historical_similarity_skipped", error=str(exc))

        insights.query_count = query_count
        metrics.record_ckg_query(query_count)
        return insights

    async def _run_analyze(
        self, context: AgentContext, metrics: DisasterMetricsCollector,
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
        metrics: DisasterMetricsCollector,
    ) -> tuple[ReasoningResult, Any]:
        reasoning, signals = await self._disaster_reasoning.run(context, tool_results)
        metrics.record_reasoning(sum(s.duration_ms for s in reasoning.steps))
        return reasoning, signals

    async def _run_validate(
        self, context: AgentContext, tool_results: list[ToolResult],
    ) -> Any:
        strict = bool(context.request.context.get("strict_validation"))
        validation = await self._disaster_validator.validate(context, tool_results, strict=strict)
        self._last_metrics and self._last_metrics.record_validation()
        return validation

    async def _run_decision_engine(
        self, context: AgentContext, reasoning: ReasoningResult, reflection: Any,
    ) -> DecisionRequest:
        return await self._decision_engine.evaluate(context, reasoning, reflection)

    async def _run_rl_service(
        self, decision: DecisionRequest, metrics: DisasterMetricsCollector,
    ) -> DecisionResponse | None:
        if not decision.need_rl or not self._rl_service:
            return None
        try:
            rl_response = await self._rl_service.optimize(decision)
            metrics.record_rl_call()
            return rl_response
        except RLOptimizationError as exc:
            logger.warning(
                "disaster_rl_optimization_failed",
                decision_id=decision.decision_id,
                error=str(exc),
            )
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
        metrics: DisasterMetricsCollector,
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
                s.content for s in reasoning.steps
                if s.metadata.get("recommendations")
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
    ) -> DisasterResponseReport:
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
            for name in ALL_DISASTER_TOOL_NAMES
            if self.tool_manager.has_tool(name)
        ]

    async def _on_select_tools(
        self, context: AgentContext, reasoning: ReasoningResult,
    ) -> list[ToolCallSpec]:
        return await self._build_tool_specs(context)

    async def required_inputs(self) -> list[str]:
        return ["query"]

    async def _persist_disaster_report(
        self, context: AgentContext, report: DisasterResponseReport,
    ) -> None:
        from backend.agents.memory.memory_types import MemoryDomain, MemoryStoreRequest

        await self.memory_manager.store(
            MemoryStoreRequest(
                domain=MemoryDomain.WORKING,
                key=f"disaster_report:{context.request_id}",
                value=report.model_dump(),
                session_id=context.user.session_id,
                metadata={"agent_id": self.agent_id, "type": "disaster_report"},
            ),
        )
        self._last_metrics and self._last_metrics.record_memory_write()

    def _to_agent_report(self, disaster_report: DisasterResponseReport) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            request_id=disaster_report.request_id,
            summary=disaster_report.executive_summary,
            reasoning=disaster_report.reasoning,
            risk={
                "level": disaster_report.emergency_priority.value,
                "composite_score": disaster_report.metadata.get("disaster_signals", {}).get(
                    "composite_priority_score", 0.0,
                ),
            },
            confidence=disaster_report.confidence,
            recommendations=disaster_report.recommendations,
            references=disaster_report.references,
            tool_outputs=disaster_report.tool_outputs,
            structured_output=disaster_report.model_dump(),
            metadata={
                "disaster_report_id": disaster_report.report_id,
                "emergency_priority": disaster_report.emergency_priority.value,
                "need_rl": disaster_report.need_rl,
                "need_other_agents": disaster_report.need_other_agents,
                "compound_disaster": disaster_report.metadata.get("compound_disaster", False),
            },
        )

    def _disaster_report_to_response(
        self, report: DisasterResponseReport, metrics: Any, memory_refs: list[str],
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
                "disaster_report_id": report.report_id,
                "emergency_priority": report.emergency_priority.value,
                "confidence": report.confidence,
                "affected_population": report.affected_population,
                "compound_disaster": report.metadata.get("compound_disaster", False),
                "priority_ranking": [r.model_dump() for r in report.priority_ranking],
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
        if self._last_disaster_report:
            update["metadata"] = {
                **update.get("metadata", {}),
                "emergency_priority": self._last_disaster_report.emergency_priority.value,
                "compound_disaster": self._last_disaster_report.metadata.get("compound_disaster", False),
                "affected_population": self._last_disaster_report.affected_population,
            }
        return update
