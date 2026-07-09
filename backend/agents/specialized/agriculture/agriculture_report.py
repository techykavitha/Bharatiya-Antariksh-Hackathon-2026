"""Agriculture report generation."""

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
from backend.agents.specialized.agriculture.agriculture_context import (
    AgricultureInputs,
    CropCondition,
    GovernmentAdvisory,
    IrrigationRecommendation,
    RagRetrievalResult,
    SoilMoistureAssessment,
    YieldRiskAssessment,
)
from backend.agents.specialized.agriculture.agriculture_metrics import AgricultureExecutionMetrics
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.xai.explanation_report import ExplainabilityReport

logger = get_logger(__name__)


class RecommendedAction(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    priority: str = "normal"
    category: str = "agricultural"


class AgricultureReport(BaseModel):
    """Professional precision agriculture analysis report."""

    report_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    request_id: str
    executive_summary: str = ""
    crop_health: CropCondition = Field(default_factory=CropCondition)
    crop_stress: str = "none"
    soil_moisture: SoilMoistureAssessment = Field(default_factory=SoilMoistureAssessment)
    yield_risk: YieldRiskAssessment = Field(default_factory=YieldRiskAssessment)
    irrigation_recommendation: IrrigationRecommendation = Field(default_factory=IrrigationRecommendation)
    climate_risk: dict[str, Any] = Field(default_factory=dict)
    government_advisory: list[GovernmentAdvisory] = Field(default_factory=list)
    rag_documents: list[dict[str, Any]] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    resilience_score: float = Field(default=0.0, ge=0.0, le=1.0)
    references: list[str] = Field(default_factory=list)
    tool_outputs: list[ToolOutputRecord] = Field(default_factory=list)
    decision_request: DecisionRequest | None = None
    rl_response: DecisionResponse | None = None
    explainability_report: ExplainabilityReport | None = None
    chosen_action: str | None = None
    alternative_crop_plans: list[str] = Field(default_factory=list)
    counterfactuals: list[str] = Field(default_factory=list)
    need_rl: bool = False
    need_simulation: bool = False
    need_other_agents: list[str] = Field(default_factory=list)
    metrics: AgricultureExecutionMetrics | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgricultureReportBuilder:
    """Assembles an AgricultureReport from analysis artifacts."""

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id

    def build(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        tool_results: list[ToolResult],
        validation: ValidationResult,
        decision: DecisionRequest,
        rag_result: RagRetrievalResult | None = None,
        reflection: ReflectionResult | None = None,
        rl_response: DecisionResponse | None = None,
        explainability: ExplainabilityReport | None = None,
    ) -> AgricultureReport:
        inputs = self._resolve_inputs(context)
        signals = reasoning.metadata.get("agriculture_signals", {})
        outputs = self._index_outputs(tool_results)

        crop = CropCondition.model_validate(reasoning.metadata.get("crop_condition", {}))
        soil = SoilMoistureAssessment.model_validate(reasoning.metadata.get("soil_moisture", {}))
        yield_risk = YieldRiskAssessment.model_validate(reasoning.metadata.get("yield_risk", {}))
        irrigation = IrrigationRecommendation.model_validate(reasoning.metadata.get("irrigation", {}))

        climate_risk = {
            "heat_stress_score": signals.get("heat_stress_score", 0.0),
            "flood_risk_score": signals.get("flood_risk_score", 0.0),
            "drought_risk": signals.get("drought_risk", False),
            "heat_stress": signals.get("heat_stress", False),
            "flood_impact": signals.get("flood_impact", False),
            "pest_favorability": signals.get("pest_favorability_score", 0.0),
        }
        advisories = list(rag_result.advisories) if rag_result else []
        gov_from_tool = outputs.get("government_advisory_tool", {}).get("advisories", [])
        if gov_from_tool and not advisories:
            advisories = [
                GovernmentAdvisory(title=a.get("title", ""), content=a.get("content", ""), source=a.get("source", ""))
                for a in gov_from_tool if isinstance(a, dict)
            ]

        recommendations = self._extract_recommendations(reasoning)
        evidence = self._build_evidence(tool_results, reasoning, inputs, rag_result)
        alternatives, counterfactuals = self._extract_xai(explainability)
        summary = self._build_summary(inputs, crop, yield_risk, irrigation, decision)
        resilience = float(reasoning.metadata.get("resilience_score", signals.get("resilience_score", 0.5)))

        chosen = None
        if rl_response and rl_response.chosen_action:
            chosen = rl_response.chosen_action.description

        confidence = reasoning.overall_confidence
        if not validation.valid:
            confidence = min(confidence, 0.55)

        return AgricultureReport(
            agent_id=self._agent_id,
            request_id=context.request_id,
            executive_summary=summary,
            crop_health=crop,
            crop_stress=crop.stress_type.value,
            soil_moisture=soil,
            yield_risk=yield_risk,
            irrigation_recommendation=irrigation,
            climate_risk=climate_risk,
            government_advisory=advisories,
            rag_documents=[d.model_dump() for d in rag_result.documents] if rag_result else [],
            recommended_actions=self._build_actions(decision),
            recommendations=recommendations,
            reasoning=[s.content for s in reasoning.steps],
            evidence=evidence,
            confidence=confidence,
            resilience_score=resilience,
            references=self._build_references(inputs, rag_result),
            tool_outputs=[
                ToolOutputRecord(tool_name=r.tool_name, output=r.output or {}, success=r.success)
                for r in tool_results
            ],
            decision_request=decision,
            rl_response=rl_response,
            explainability_report=explainability,
            chosen_action=chosen,
            alternative_crop_plans=alternatives,
            counterfactuals=counterfactuals,
            need_rl=decision.need_rl,
            need_simulation=decision.need_simulation,
            need_other_agents=list(decision.need_other_agents),
            metadata={
                "validation_valid": validation.valid,
                "agriculture_signals": signals,
                "crop_type": inputs.crop_type,
                "season": inputs.season,
                "state": inputs.state,
            },
        )

    def _resolve_inputs(self, context: AgentContext) -> AgricultureInputs:
        stored = context.metadata.get("agriculture_inputs")
        if isinstance(stored, AgricultureInputs):
            return stored
        return AgricultureInputs.from_request_context(context.request.context)

    def _index_outputs(self, tool_results: list[ToolResult]) -> dict[str, Any]:
        return {r.tool_name: r.output for r in tool_results if r.success and r.output}

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
        inputs: AgricultureInputs,
        rag_result: RagRetrievalResult | None,
    ) -> list[str]:
        evidence: list[str] = [
            f"crop:{inputs.crop_type}",
            f"season:{inputs.season}",
            f"ndvi:{inputs.remote_sensing.ndvi:.2f}",
        ]
        for agent_id, peer in inputs.peer_agent_outputs.items():
            evidence.append(f"peer:{agent_id} severity={peer.severity}")
        for r in tool_results:
            if r.success and r.output:
                evidence.append(f"{r.tool_name}: {list(r.output.keys())[:4]}")
        if rag_result:
            evidence.append(f"rag_documents={rag_result.retrieval_count}")
        evidence.append(f"resilience_score={reasoning.metadata.get('resilience_score', 0):.2f}")
        return evidence

    def _build_actions(self, decision: DecisionRequest) -> list[RecommendedAction]:
        return [
            RecommendedAction(
                description=action.description,
                priority=decision.priority.name.lower(),
                category=action.category or "agricultural",
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

    def _build_references(
        self, inputs: AgricultureInputs, rag_result: RagRetrievalResult | None,
    ) -> list[str]:
        refs = [f"region:{inputs.region_id or 'unknown'}", f"crop:{inputs.crop_type}"]
        if inputs.state:
            refs.append(f"state:{inputs.state}")
        if rag_result:
            for doc in rag_result.documents[:3]:
                refs.append(f"rag:{doc.document_id}")
        return refs

    def _build_summary(
        self,
        inputs: AgricultureInputs,
        crop: CropCondition,
        yield_risk: YieldRiskAssessment,
        irrigation: IrrigationRecommendation,
        decision: DecisionRequest,
    ) -> str:
        region = inputs.state or inputs.region_id or "region"
        return (
            f"Agricultural assessment for {inputs.crop_type} in {region} ({inputs.season}): "
            f"health {crop.health_status.value}, yield risk {yield_risk.risk_level.value} "
            f"({yield_risk.estimated_yield_pct:.0f}% of normal). "
            f"Irrigation: {irrigation.recommendation_type.value}. "
            f"{len(decision.possible_actions)} actions evaluated."
        )
