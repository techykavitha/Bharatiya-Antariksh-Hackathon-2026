"""Flood report generation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.agents.schemas.response import ToolOutputRecord
from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.specialized.agent_reflection import ReflectionResult
from backend.agents.specialized.flood.flood_context import (
    AffectedDistrict,
    DecisionRequest,
    FloodInputs,
    FloodProbabilityEstimate,
)
from backend.agents.specialized.flood.flood_metrics import FloodExecutionMetrics
from backend.agents.specialized.flood.flood_models import (
    FloodRiskLevel,
    FloodSeverity,
    FloodType,
)
from backend.agents.specialized.flood.flood_validator import ValidationResult
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


class RequiredAction(BaseModel):
    """Action required from downstream systems or agents."""

    action_id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    priority: str = "normal"
    target_agent: str | None = None
    category: str = "operational"


class FloodReport(BaseModel):
    """Professional flood analysis report."""

    report_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    request_id: str
    executive_summary: str = ""
    flood_type: FloodType = FloodType.UNKNOWN
    risk_level: FloodRiskLevel = FloodRiskLevel.MINIMAL
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    severity: FloodSeverity = FloodSeverity.NONE
    reasoning: list[str] = Field(default_factory=list)
    affected_districts: list[AffectedDistrict] = Field(default_factory=list)
    expected_water_depth_m: float = Field(default=0.0, ge=0.0)
    probability: FloodProbabilityEstimate = Field(default_factory=FloodProbabilityEstimate)
    recommendations: list[str] = Field(default_factory=list)
    required_actions: list[RequiredAction] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    tool_outputs: list[ToolOutputRecord] = Field(default_factory=list)
    decision_request: DecisionRequest = Field(default_factory=DecisionRequest)
    need_rl: bool = False
    need_simulation: bool = False
    need_other_agents: list[str] = Field(default_factory=list)
    metrics: FloodExecutionMetrics | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_executive_text(self) -> str:
        return self.executive_summary


class FloodReportBuilder:
    """Assembles a ``FloodReport`` from analysis artifacts."""

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
        metrics: FloodExecutionMetrics | None = None,
    ) -> FloodReport:
        inputs = self._resolve_inputs(context)
        signals = reasoning.metadata.get("flood_signals", {})
        outputs = self._index_outputs(tool_results)

        flood_type = self._classify_flood_type(signals, outputs)
        severity = FloodSeverity(reasoning.metadata.get("severity", FloodSeverity.NONE.value))
        probability = self._resolve_probability(reasoning)
        risk_level = self._risk_from_score(signals.get("composite_score", 0.0), severity)
        depth = self._estimate_depth(outputs, signals)
        districts = self._build_affected_districts(inputs, outputs, risk_level, depth)
        recommendations = self._extract_recommendations(reasoning)
        required_actions = self._build_required_actions(decision, reflection)
        confidence = reasoning.overall_confidence
        if not validation.valid:
            confidence = min(confidence, 0.5)

        summary = self._executive_summary(
            flood_type, risk_level, severity, districts, depth, probability,
        )

        tool_records = [
            ToolOutputRecord(
                tool_name=r.tool_name,
                output=r.output,
                success=r.success,
                error=r.error,
                duration_ms=r.duration_ms,
            )
            for r in tool_results
        ]

        report = FloodReport(
            agent_id=self._agent_id,
            request_id=context.request_id,
            executive_summary=summary,
            flood_type=flood_type,
            risk_level=risk_level,
            confidence=confidence,
            severity=severity,
            reasoning=reasoning.trace,
            affected_districts=districts,
            expected_water_depth_m=depth,
            probability=probability,
            recommendations=recommendations,
            required_actions=required_actions,
            references=list(context.memory.references),
            tool_outputs=tool_records,
            decision_request=decision,
            need_rl=decision.need_rl,
            need_simulation=decision.need_simulation,
            need_other_agents=decision.suggested_agents,
            metrics=metrics,
            metadata={
                "validation_valid": validation.valid,
                "region_id": inputs.region_id,
                "signals": signals,
            },
        )
        logger.info(
            "flood_report_generated",
            agent_id=self._agent_id,
            risk_level=risk_level.value,
            severity=severity.value,
        )
        return report

    def _resolve_inputs(self, context: AgentContext) -> FloodInputs:
        stored = context.metadata.get("flood_inputs")
        if isinstance(stored, FloodInputs):
            return stored
        return FloodInputs.from_request_context(context.request.context)

    def _index_outputs(self, results: list[ToolResult]) -> dict[str, Any]:
        return {
            r.tool_name: r.output
            for r in results
            if r.success and isinstance(r.output, dict)
        }

    def _classify_flood_type(self, signals: dict[str, Any], outputs: dict[str, Any]) -> FloodType:
        if signals.get("urban_pluvial_risk"):
            return FloodType.URBAN
        if signals.get("river_overflow"):
            return FloodType.RIVER
        if signals.get("reservoir_stressed"):
            return FloodType.RESERVOIR_OVERFLOW
        if signals.get("heavy_rainfall") and signals.get("terrain_vulnerable"):
            return FloodType.FLASH
        river = outputs.get("river_tool", {})
        if river.get("flood_type_hint"):
            return FloodType(river["flood_type_hint"])
        reservoir = outputs.get("reservoir_tool", {})
        if reservoir.get("flood_type_hint"):
            return FloodType(reservoir["flood_type_hint"])
        return FloodType.UNKNOWN

    def _resolve_probability(self, reasoning: ReasoningResult) -> FloodProbabilityEstimate:
        raw = reasoning.metadata.get("probability")
        if isinstance(raw, dict):
            return FloodProbabilityEstimate.model_validate(raw)
        if isinstance(raw, FloodProbabilityEstimate):
            return raw
        return FloodProbabilityEstimate()

    def _risk_from_score(self, score: float, severity: FloodSeverity) -> FloodRiskLevel:
        if severity == FloodSeverity.CATASTROPHIC or score >= 0.85:
            return FloodRiskLevel.EXTREME
        if severity == FloodSeverity.MAJOR or score >= 0.7:
            return FloodRiskLevel.SEVERE
        if severity == FloodSeverity.MODERATE or score >= 0.55:
            return FloodRiskLevel.HIGH
        if score >= 0.35:
            return FloodRiskLevel.MODERATE
        if score >= 0.15:
            return FloodRiskLevel.LOW
        return FloodRiskLevel.MINIMAL

    def _estimate_depth(self, outputs: dict[str, Any], signals: dict[str, Any]) -> float:
        dem = outputs.get("dem_tool", {})
        depth = float(dem.get("estimated_depth_potential_m", 0.0))
        twin = outputs.get("digital_twin_tool", {})
        depth = max(depth, float(twin.get("inundation_depth_m", 0.0)))
        if signals.get("river_overflow"):
            depth = max(depth, 1.0)
        composite = float(signals.get("composite_score", 0.0))
        return round(max(depth, composite * 2.5), 2)

    def _build_affected_districts(
        self,
        inputs: FloodInputs,
        outputs: dict[str, Any],
        risk: FloodRiskLevel,
        depth: float,
    ) -> list[AffectedDistrict]:
        pop = outputs.get("population_tool", {})
        districts = inputs.districts or pop.get("districts", ["affected_area"])
        pop_per = int(pop.get("population_per_district", 10_000))
        prob = outputs.get("rainfall_tool", {})
        band = FloodProbabilityEstimate().band

        return [
            AffectedDistrict(
                district_id=f"district_{i}",
                name=str(name),
                expected_depth_m=round(depth * (0.8 + 0.1 * i), 2),
                population_at_risk=pop_per,
                risk_level=risk,
                probability=band,
            )
            for i, name in enumerate(districts)
        ]

    def _extract_recommendations(self, reasoning: ReasoningResult) -> list[str]:
        for step in reasoning.steps:
            recs = step.metadata.get("recommendations")
            if isinstance(recs, list) and recs:
                return [str(r) for r in recs]
        return ["Monitor conditions and update assessment as new data arrives"]

    def _build_required_actions(
        self,
        decision: DecisionRequest,
        reflection: ReflectionResult,
    ) -> list[RequiredAction]:
        actions: list[RequiredAction] = []
        if decision.need_disaster_agent:
            actions.append(RequiredAction(
                description="Activate disaster response coordination",
                priority="high",
                target_agent="disaster_response_agent",
                category="emergency",
            ))
        if decision.need_water_resource_agent:
            actions.append(RequiredAction(
                description="Request reservoir release optimization",
                priority="high",
                target_agent="water_resource_agent",
                category="infrastructure",
            ))
        if decision.need_simulation:
            actions.append(RequiredAction(
                description="Run hydrological inundation simulation",
                priority="normal",
                category="simulation",
            ))
        if decision.need_forecast_update:
            actions.append(RequiredAction(
                description="Refresh precipitation forecast for planning horizon",
                priority="normal",
                category="forecast",
            ))
        if decision.need_rl:
            actions.append(RequiredAction(
                description="Request RL policy for evacuation and resource allocation",
                priority="high",
                category="rl",
            ))
        return actions

    def _executive_summary(
        self,
        flood_type: FloodType,
        risk: FloodRiskLevel,
        severity: FloodSeverity,
        districts: list[AffectedDistrict],
        depth: float,
        probability: FloodProbabilityEstimate,
    ) -> str:
        district_names = ", ".join(d.name for d in districts[:3]) or "target area"
        return (
            f"Flood assessment for {district_names}: {flood_type.value} flood risk "
            f"rated {risk.value} with {severity.value} severity. "
            f"Probability band: {probability.band.value} ({probability.score:.0%}). "
            f"Expected water depth up to {depth:.1f}m. "
            f"{len(districts)} district(s) potentially affected."
        )
