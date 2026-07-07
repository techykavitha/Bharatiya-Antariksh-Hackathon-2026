"""Heatwave report generation."""

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
from backend.agents.specialized.heatwave.heatwave_context import (
    HeatIndexEstimate,
    HeatProbabilityEstimate,
    HeatwaveInputs,
    InfrastructureRisk,
    PopulationAtRisk,
)
from backend.agents.specialized.heatwave.heatwave_metrics import HeatwaveExecutionMetrics
from backend.agents.specialized.heatwave.heatwave_models import (
    HeatRiskLevel,
    HeatwaveClassification,
    HeatwaveSeverity,
)
from backend.agents.tools.abstract_tool import ToolResult
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.config.logger import get_logger

logger = get_logger(__name__)


class RequiredAction(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    priority: str = "normal"
    target_agent: str | None = None
    category: str = "operational"


class HeatwaveReport(BaseModel):
    """Professional heatwave analysis report."""

    report_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    request_id: str
    executive_summary: str = ""
    classification: HeatwaveClassification = HeatwaveClassification.NONE
    severity: HeatwaveSeverity = HeatwaveSeverity.NONE
    risk_level: HeatRiskLevel = HeatRiskLevel.MINIMAL
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    heat_index: HeatIndexEstimate = Field(default_factory=HeatIndexEstimate)
    wet_bulb_c: float = Field(default=0.0, ge=0.0)
    uhi_score: float = Field(default=0.0, ge=0.0, le=1.0)
    duration_days: int = Field(default=0, ge=0)
    population_at_risk: list[PopulationAtRisk] = Field(default_factory=list)
    critical_infrastructure: list[InfrastructureRisk] = Field(default_factory=list)
    probability: HeatProbabilityEstimate = Field(default_factory=HeatProbabilityEstimate)
    reasoning: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    required_actions: list[RequiredAction] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    tool_outputs: list[ToolOutputRecord] = Field(default_factory=list)
    decision_request: DecisionRequest | None = None
    rl_response: DecisionResponse | None = None
    chosen_mitigation_action: str | None = None
    need_rl: bool = False
    need_simulation: bool = False
    need_other_agents: list[str] = Field(default_factory=list)
    metrics: HeatwaveExecutionMetrics | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HeatwaveReportBuilder:
    """Assembles a ``HeatwaveReport`` from analysis artifacts."""

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id

    def build(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        tool_results: list[ToolResult],
        reflection: ReflectionResult,
        validation: ValidationResult,
        decision: DecisionRequest,
        rl_response: DecisionResponse | None = None,
    ) -> HeatwaveReport:
        inputs = self._resolve_inputs(context)
        signals = reasoning.metadata.get("heat_signals", {})
        outputs = self._index_outputs(tool_results)
        severity = HeatwaveSeverity(reasoning.metadata.get("severity", HeatwaveSeverity.NONE.value))
        heat_index = self._resolve_heat_index(reasoning)
        probability = self._resolve_probability(reasoning)
        classification = self._classify(signals, severity)
        risk_level = self._risk_from_score(float(signals.get("composite_score", 0.0)), severity)
        population = self._build_population_at_risk(inputs, outputs, risk_level)
        infrastructure = self._build_infrastructure_risks(signals, severity)
        recommendations = self._extract_recommendations(reasoning)
        required_actions = self._build_required_actions(decision, rl_response)
        confidence = reasoning.overall_confidence
        if not validation.valid:
            confidence = min(confidence, 0.5)

        chosen = None
        if rl_response and rl_response.chosen_action:
            chosen = rl_response.chosen_action.description

        summary = self._executive_summary(
            classification, severity, heat_index, population, duration_days=int(
                reasoning.metadata.get("duration_days", 0),
            ),
        )

        tool_records = [
            ToolOutputRecord(
                tool_name=r.tool_name, output=r.output, success=r.success,
                error=r.error, duration_ms=r.duration_ms,
            )
            for r in tool_results
        ]

        return HeatwaveReport(
            agent_id=self._agent_id,
            request_id=context.request_id,
            executive_summary=summary,
            classification=classification,
            severity=severity,
            risk_level=risk_level,
            confidence=confidence,
            heat_index=heat_index,
            wet_bulb_c=heat_index.wet_bulb_c,
            uhi_score=float(signals.get("uhi_score", 0.0)),
            duration_days=int(reasoning.metadata.get("duration_days", 0)),
            population_at_risk=population,
            critical_infrastructure=infrastructure,
            probability=probability,
            reasoning=reasoning.trace,
            recommendations=recommendations,
            required_actions=required_actions,
            references=list(context.memory.references),
            tool_outputs=tool_records,
            decision_request=decision,
            rl_response=rl_response,
            chosen_mitigation_action=chosen,
            need_rl=decision.need_rl,
            need_simulation=decision.need_simulation,
            need_other_agents=decision.need_other_agents,
            metadata={
                "validation_valid": validation.valid,
                "region_id": inputs.region_id,
                "signals": signals,
            },
        )

    def _resolve_inputs(self, context: AgentContext) -> HeatwaveInputs:
        stored = context.metadata.get("heatwave_inputs")
        if isinstance(stored, HeatwaveInputs):
            return stored
        return HeatwaveInputs.from_request_context(context.request.context)

    def _index_outputs(self, results: list[ToolResult]) -> dict[str, Any]:
        return {r.tool_name: r.output for r in results if r.success and isinstance(r.output, dict)}

    def _resolve_heat_index(self, reasoning: ReasoningResult) -> HeatIndexEstimate:
        raw = reasoning.metadata.get("heat_index")
        if isinstance(raw, dict):
            return HeatIndexEstimate.model_validate(raw)
        return HeatIndexEstimate()

    def _resolve_probability(self, reasoning: ReasoningResult) -> HeatProbabilityEstimate:
        raw = reasoning.metadata.get("probability")
        if isinstance(raw, dict):
            return HeatProbabilityEstimate.model_validate(raw)
        return HeatProbabilityEstimate()

    def _classify(self, signals: dict[str, Any], severity: HeatwaveSeverity) -> HeatwaveClassification:
        if signals.get("compound_aqi_risk"):
            return HeatwaveClassification.COMPOUND
        if severity == HeatwaveSeverity.EXTREME:
            return HeatwaveClassification.EXTREME
        if signals.get("rising_trend") and severity in (HeatwaveSeverity.HIGH, HeatwaveSeverity.SEVERE):
            return HeatwaveClassification.PROLONGED
        if severity in (HeatwaveSeverity.HIGH, HeatwaveSeverity.SEVERE):
            return HeatwaveClassification.SEVERE
        if severity == HeatwaveSeverity.MODERATE:
            return HeatwaveClassification.MODERATE
        return HeatwaveClassification.NONE

    def _risk_from_score(self, score: float, severity: HeatwaveSeverity) -> HeatRiskLevel:
        if severity == HeatwaveSeverity.EXTREME or score >= 0.85:
            return HeatRiskLevel.CRITICAL
        if severity == HeatwaveSeverity.SEVERE or score >= 0.7:
            return HeatRiskLevel.SEVERE
        if severity == HeatwaveSeverity.HIGH or score >= 0.55:
            return HeatRiskLevel.HIGH
        if score >= 0.35:
            return HeatRiskLevel.MODERATE
        if score >= 0.15:
            return HeatRiskLevel.LOW
        return HeatRiskLevel.MINIMAL

    def _build_population_at_risk(
        self, inputs: HeatwaveInputs, outputs: dict[str, Any], risk: HeatRiskLevel,
    ) -> list[PopulationAtRisk]:
        pop = outputs.get("population_tool", {})
        districts = inputs.districts or pop.get("districts", ["affected_area"])
        per_district = int(pop.get("total_population", 50000) / max(len(districts), 1))
        vulnerable = int(pop.get("vulnerable_population", per_district * 0.25) / max(len(districts), 1))
        return [
            PopulationAtRisk(
                district_id=f"district_{i}",
                name=str(name),
                population=per_district,
                vulnerable_population=vulnerable,
                risk_level=risk,
            )
            for i, name in enumerate(districts)
        ]

    def _build_infrastructure_risks(
        self, signals: dict[str, Any], severity: HeatwaveSeverity,
    ) -> list[InfrastructureRisk]:
        if not signals.get("infrastructure_at_risk"):
            return []
        risk = HeatRiskLevel.HIGH if severity in (HeatwaveSeverity.HIGH, HeatwaveSeverity.SEVERE) else HeatRiskLevel.MODERATE
        return [
            InfrastructureRisk(infrastructure_id="power_grid", name="Power Grid", category="energy", risk_level=risk),
            InfrastructureRisk(infrastructure_id="hospitals", name="Healthcare Facilities", category="health", risk_level=risk),
            InfrastructureRisk(infrastructure_id="transport", name="Public Transport", category="transport", risk_level=risk),
        ]

    def _extract_recommendations(self, reasoning: ReasoningResult) -> list[str]:
        for step in reasoning.steps:
            recs = step.metadata.get("recommendations")
            if isinstance(recs, list) and recs:
                return [str(r) for r in recs]
        return ["Monitor thermal conditions and update assessment as new data arrives"]

    def _build_required_actions(
        self, decision: DecisionRequest, rl_response: DecisionResponse | None,
    ) -> list[RequiredAction]:
        actions: list[RequiredAction] = []
        if rl_response and rl_response.chosen_action:
            actions.append(RequiredAction(
                description=rl_response.chosen_action.description,
                priority="high",
                category="rl_optimized",
            ))
        for agent in decision.need_other_agents:
            actions.append(RequiredAction(
                description=f"Coordinate with {agent}",
                priority="normal",
                target_agent=agent,
                category="coordination",
            ))
        if decision.need_simulation:
            actions.append(RequiredAction(description="Run urban thermal simulation", category="simulation"))
        return actions

    def _executive_summary(
        self,
        classification: HeatwaveClassification,
        severity: HeatwaveSeverity,
        heat_index: HeatIndexEstimate,
        population: list[PopulationAtRisk],
        duration_days: int,
    ) -> str:
        total_pop = sum(p.population for p in population)
        return (
            f"Heatwave assessment: {classification.value} event rated {severity.value}. "
            f"Heat index {heat_index.heat_index_c:.1f}C, wet bulb {heat_index.wet_bulb_c:.1f}C. "
            f"Estimated duration {duration_days} days. "
            f"Approximately {total_pop:,} people in affected districts."
        )
