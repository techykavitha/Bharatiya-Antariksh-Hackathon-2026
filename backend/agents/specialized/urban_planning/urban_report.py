"""Urban planning report generation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.agents.schemas.response import ToolOutputRecord
from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.specialized.agent_reflection import ReflectionResult
from backend.agents.specialized.agent_validator import ValidationResult
from backend.agents.specialized.urban_planning.urban_context import (
    GreenCoverAnalysis,
    InvestmentPriority,
    MitigationOption,
    UrbanInputs,
)
from backend.agents.specialized.urban_planning.urban_metrics import UrbanExecutionMetrics
from backend.agents.specialized.urban_planning.urban_models import UrbanResilienceLevel
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.xai.explanation_report import ExplainabilityReport

logger = get_logger(__name__)


class RequiredAction(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    priority: str = "normal"
    category: str = "planning"
    target_agent: str | None = None


class UrbanPlanningReport(BaseModel):
    """Professional urban climate adaptation planning report."""

    report_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    request_id: str
    executive_summary: str = ""
    urban_resilience_score: float = Field(default=0.0, ge=0.0, le=1.0)
    resilience_level: UrbanResilienceLevel = UrbanResilienceLevel.MODERATE
    heat_mitigation_opportunities: list[str] = Field(default_factory=list)
    flood_mitigation_opportunities: list[str] = Field(default_factory=list)
    green_cover_analysis: GreenCoverAnalysis = Field(default_factory=GreenCoverAnalysis)
    infrastructure_risk: dict[str, Any] = Field(default_factory=dict)
    adaptation_strategy: list[MitigationOption] = Field(default_factory=list)
    investment_priorities: list[InvestmentPriority] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    required_actions: list[RequiredAction] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    references: list[str] = Field(default_factory=list)
    tool_outputs: list[ToolOutputRecord] = Field(default_factory=list)
    decision_request: DecisionRequest | None = None
    rl_response: DecisionResponse | None = None
    explainability_report: ExplainabilityReport | None = None
    chosen_action: str | None = None
    need_rl: bool = False
    need_simulation: bool = False
    need_other_agents: list[str] = Field(default_factory=list)
    alternative_strategies: list[str] = Field(default_factory=list)
    counterfactuals: list[str] = Field(default_factory=list)
    metrics: UrbanExecutionMetrics | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UrbanReportBuilder:
    """Assembles an UrbanPlanningReport from analysis artifacts."""

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id

    def build(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        tool_results: list[ToolResult],
        validation: ValidationResult,
        decision: DecisionRequest,
        reflection: ReflectionResult | None = None,
        rl_response: DecisionResponse | None = None,
        explainability: ExplainabilityReport | None = None,
    ) -> UrbanPlanningReport:
        inputs = self._resolve_inputs(context)
        signals = reasoning.metadata.get("urban_signals", {})
        outputs = self._index_outputs(tool_results)

        green = GreenCoverAnalysis.model_validate(
            reasoning.metadata.get("green_cover_analysis", {}),
        )
        mitigations = [
            MitigationOption.model_validate(m)
            for m in reasoning.metadata.get("mitigation_options", [])
            if isinstance(m, dict)
        ]
        investments = [
            InvestmentPriority.model_validate(i)
            for i in reasoning.metadata.get("investment_priorities", [])
            if isinstance(i, dict)
        ]

        resilience = float(reasoning.metadata.get("resilience_score", signals.get("resilience_score", 0.5)))
        level = UrbanResilienceLevel(
            reasoning.metadata.get("resilience_level", signals.get("resilience_level", UrbanResilienceLevel.MODERATE.value)),
        )
        heat_opps = self._heat_opportunities(outputs, signals)
        flood_opps = self._flood_opportunities(outputs, signals)
        infra_risk = outputs.get("infrastructure_tool", {})
        recommendations = self._extract_recommendations(reasoning)
        evidence = self._build_evidence(tool_results, reasoning, inputs)
        alternatives, counterfactuals = self._extract_xai(explainability)
        summary = self._build_summary(inputs, resilience, level, mitigations, decision)

        chosen = None
        if rl_response and rl_response.chosen_action:
            chosen = rl_response.chosen_action.description

        confidence = reasoning.overall_confidence
        if not validation.valid:
            confidence = min(confidence, 0.55)

        return UrbanPlanningReport(
            agent_id=self._agent_id,
            request_id=context.request_id,
            executive_summary=summary,
            urban_resilience_score=resilience,
            resilience_level=level,
            heat_mitigation_opportunities=heat_opps,
            flood_mitigation_opportunities=flood_opps,
            green_cover_analysis=green,
            infrastructure_risk=infra_risk if isinstance(infra_risk, dict) else {},
            adaptation_strategy=mitigations,
            investment_priorities=investments,
            recommendations=recommendations,
            required_actions=self._build_required_actions(decision),
            reasoning=[s.content for s in reasoning.steps],
            evidence=evidence,
            confidence=confidence,
            references=self._build_references(inputs),
            tool_outputs=[
                ToolOutputRecord(tool_name=r.tool_name, output=r.output or {}, success=r.success)
                for r in tool_results
            ],
            decision_request=decision,
            rl_response=rl_response,
            explainability_report=explainability,
            chosen_action=chosen,
            need_rl=decision.need_rl,
            need_simulation=decision.need_simulation,
            need_other_agents=list(decision.need_other_agents),
            alternative_strategies=alternatives,
            counterfactuals=counterfactuals,
            metadata={
                "validation_valid": validation.valid,
                "urban_signals": signals,
                "reflection_confidence": reflection.confidence if reflection else None,
                "city_name": inputs.city_name,
                "planning_horizon_years": inputs.planning_horizon_years,
            },
        )

    def _resolve_inputs(self, context: AgentContext) -> UrbanInputs:
        stored = context.metadata.get("urban_inputs")
        if isinstance(stored, UrbanInputs):
            return stored
        return UrbanInputs.from_request_context(context.request.context)

    def _index_outputs(self, tool_results: list[ToolResult]) -> dict[str, Any]:
        return {r.tool_name: r.output for r in tool_results if r.success and r.output}

    def _heat_opportunities(self, outputs: dict[str, Any], signals: dict[str, Any]) -> list[str]:
        opps: list[str] = []
        if outputs.get("building_tool", {}).get("cool_roof_candidate"):
            opps.append("Cool roof deployment on high heat-exposure buildings")
        if outputs.get("building_tool", {}).get("green_roof_candidate"):
            opps.append("Green roof installation on dense commercial blocks")
        if outputs.get("ndvi_tool", {}).get("tree_planting_priority"):
            opps.append("Street tree plantation in low-NDVI corridors")
        if signals.get("urban_heat_island"):
            opps.append("UHI hotspot mitigation via combined cool roofs and canopy expansion")
        return opps

    def _flood_opportunities(self, outputs: dict[str, Any], signals: dict[str, Any]) -> list[str]:
        opps: list[str] = []
        if outputs.get("drainage_tool", {}).get("stormwater_upgrade_required"):
            opps.append("Stormwater detention and conveyance system upgrade")
        if outputs.get("drainage_tool", {}).get("rain_garden_opportunity"):
            opps.append("Distributed rain garden network in micro-catchments")
        if outputs.get("road_tool", {}).get("permeable_pavement_opportunity"):
            opps.append("Permeable pavement replacement on high-impervious road segments")
        if signals.get("flood_vulnerability"):
            opps.append("Integrated blue-green flood mitigation in flood-prone zones")
        return opps

    def _extract_recommendations(self, reasoning: ReasoningResult) -> list[str]:
        for step in reversed(reasoning.steps):
            recs = step.metadata.get("recommendations")
            if recs:
                return list(recs)
        return [s.content for s in reasoning.steps if s.phase.value in ("act", "verify")]

    def _build_evidence(
        self,
        tool_results: list[ToolResult],
        reasoning: ReasoningResult,
        inputs: UrbanInputs,
    ) -> list[str]:
        evidence: list[str] = []
        if inputs.city_name:
            evidence.append(f"city:{inputs.city_name}")
        for agent_id, peer in inputs.peer_agent_outputs.items():
            evidence.append(f"peer:{agent_id} severity={peer.severity}")
        for r in tool_results:
            if r.success and r.output:
                evidence.append(f"{r.tool_name}: {list(r.output.keys())[:4]}")
        evidence.append(f"resilience_score={reasoning.metadata.get('resilience_score', 0):.2f}")
        evidence.append(f"reasoning_confidence={reasoning.overall_confidence:.2f}")
        return evidence

    def _build_required_actions(self, decision: DecisionRequest) -> list[RequiredAction]:
        return [
            RequiredAction(
                description=action.description,
                priority=decision.priority.name.lower(),
                category=action.category or "planning",
            )
            for action in decision.possible_actions
        ]

    def _extract_xai(
        self, explainability: ExplainabilityReport | None,
    ) -> tuple[list[str], list[str]]:
        if not explainability:
            return [], []
        alternatives = [
            (alt.action.description if alt.action else "") or alt.rationale or alt.why_not_chosen
            for alt in explainability.alternatives.alternatives
            if (alt.action and alt.action.description) or alt.rationale or alt.why_not_chosen
        ]
        counterfactuals = [
            scenario.description or scenario.title
            for scenario in explainability.counterfactuals.scenarios
            if scenario.description or scenario.title
        ]
        return alternatives, counterfactuals

    def _build_references(self, inputs: UrbanInputs) -> list[str]:
        refs = [f"region:{inputs.region_id or 'unknown'}"]
        if inputs.city_name:
            refs.append(f"city:{inputs.city_name}")
        for agent_id in inputs.peer_agent_outputs:
            refs.append(f"peer:{agent_id}")
        return refs

    def _build_summary(
        self,
        inputs: UrbanInputs,
        resilience: float,
        level: UrbanResilienceLevel,
        mitigations: list[MitigationOption],
        decision: DecisionRequest,
    ) -> str:
        city = inputs.city_name or inputs.region_id or "urban area"
        top = mitigations[0].title if mitigations else "baseline adaptation"
        return (
            f"Urban climate adaptation plan for {city}: resilience {resilience:.2f} ({level.value}), "
            f"{inputs.planning_horizon_years}-year horizon. "
            f"Lead intervention: {top}. "
            f"{len(decision.possible_actions)} mitigation actions evaluated."
        )
