"""Cyclone report generation."""

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
from backend.agents.specialized.cyclone.cyclone_context import (
    CycloneInputs,
    InfrastructureExposure,
    PopulationExposure,
    RainfallImpactEstimate,
    StormSurgeEstimate,
    WindHazardEstimate,
)
from backend.agents.specialized.cyclone.cyclone_metrics import CycloneExecutionMetrics
from backend.agents.specialized.cyclone.cyclone_models import (
    CycloneBasin,
    CycloneCategory,
    CycloneRiskLevel,
    CycloneSeverity,
)
from backend.agents.tools.abstract_tool import ToolResult
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.config.logger import get_logger
from backend.xai.explanation_report import ExplainabilityReport

logger = get_logger(__name__)


class RequiredAction(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    priority: str = "normal"
    target_agent: str | None = None
    category: str = "operational"


class CycloneReport(BaseModel):
    """Professional tropical cyclone analysis report."""

    report_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    request_id: str
    executive_summary: str = ""
    cyclone_name: str | None = None
    basin: CycloneBasin = CycloneBasin.UNKNOWN
    category: CycloneCategory = CycloneCategory.DISTURBANCE
    severity: CycloneSeverity = CycloneSeverity.NONE
    risk_level: CycloneRiskLevel = CycloneRiskLevel.MINIMAL
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    current_position: dict[str, float] = Field(default_factory=dict)
    forecast_track: list[dict[str, Any]] = Field(default_factory=list)
    landfall_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    estimated_intensity_kt: float = Field(default=0.0, ge=0.0)
    wind_hazard: WindHazardEstimate = Field(default_factory=WindHazardEstimate)
    storm_surge: StormSurgeEstimate = Field(default_factory=StormSurgeEstimate)
    rainfall_impact: RainfallImpactEstimate = Field(default_factory=RainfallImpactEstimate)
    affected_population: list[PopulationExposure] = Field(default_factory=list)
    critical_infrastructure: list[InfrastructureExposure] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    required_actions: list[RequiredAction] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    tool_outputs: list[ToolOutputRecord] = Field(default_factory=list)
    decision_request: DecisionRequest | None = None
    rl_response: DecisionResponse | None = None
    explainability_report: ExplainabilityReport | None = None
    chosen_action: str | None = None
    need_rl: bool = False
    need_simulation: bool = False
    need_other_agents: list[str] = Field(default_factory=list)
    metrics: CycloneExecutionMetrics | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CycloneReportBuilder:
    """Assembles a CycloneReport from analysis artifacts."""

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
        explainability: ExplainabilityReport | None = None,
    ) -> CycloneReport:
        inputs = self._resolve_inputs(context)
        signals = reasoning.metadata.get("cyclone_signals", {})
        outputs = self._index_outputs(tool_results)
        severity = CycloneSeverity(reasoning.metadata.get("severity", CycloneSeverity.NONE.value))
        wind_hazard = WindHazardEstimate.model_validate(
            reasoning.metadata.get("wind_hazard", {}),
        )
        storm_surge = StormSurgeEstimate.model_validate(
            reasoning.metadata.get("storm_surge", {}),
        )
        rainfall = RainfallImpactEstimate.model_validate(
            reasoning.metadata.get("rainfall_impact", {}),
        )
        risk_level = self._map_risk_level(severity, float(signals.get("composite_score", 0.0)))
        population = self._build_population(outputs, risk_level)
        infrastructure = self._build_infrastructure(outputs, risk_level)
        recommendations = self._extract_recommendations(reasoning)
        evidence = self._build_evidence(tool_results, reasoning)
        summary = self._build_summary(inputs, severity, wind_hazard, storm_surge, decision)

        chosen = None
        if rl_response and rl_response.chosen_action:
            chosen = rl_response.chosen_action.description

        return CycloneReport(
            agent_id=self._agent_id,
            request_id=context.request_id,
            executive_summary=summary,
            cyclone_name=inputs.cyclone_name,
            basin=inputs.basin,
            category=wind_hazard.category,
            severity=severity,
            risk_level=risk_level,
            confidence=reasoning.overall_confidence,
            current_position=self._current_position(inputs),
            forecast_track=reasoning.metadata.get("track", []),
            landfall_probability=float(outputs.get("forecast_tool", {}).get(
                "landfall_probability", inputs.forecast.landfall_probability or 0.0,
            )),
            estimated_intensity_kt=wind_hazard.max_sustained_wind_kt,
            wind_hazard=wind_hazard,
            storm_surge=storm_surge,
            rainfall_impact=rainfall,
            affected_population=population,
            critical_infrastructure=infrastructure,
            reasoning=[s.content for s in reasoning.steps],
            recommendations=recommendations,
            evidence=evidence,
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
            metadata={
                "validation_valid": validation.valid,
                "reflection_confidence": reflection.confidence,
                "cyclone_signals": signals,
            },
        )

    def _resolve_inputs(self, context: AgentContext) -> CycloneInputs:
        stored = context.metadata.get("cyclone_inputs")
        if isinstance(stored, CycloneInputs):
            return stored
        return CycloneInputs.from_request_context(context.request.context)

    def _index_outputs(self, tool_results: list[ToolResult]) -> dict[str, Any]:
        return {r.tool_name: r.output for r in tool_results if r.success and r.output}

    def _current_position(self, inputs: CycloneInputs) -> dict[str, float]:
        if inputs.location:
            return {
                "latitude": inputs.location.latitude,
                "longitude": inputs.location.longitude,
            }
        if inputs.forecast.track_points:
            pt = inputs.forecast.track_points[0]
            return {"latitude": pt.latitude, "longitude": pt.longitude}
        return {}

    def _map_risk_level(self, severity: CycloneSeverity, composite: float) -> CycloneRiskLevel:
        if severity == CycloneSeverity.EXTREME or composite >= 0.85:
            return CycloneRiskLevel.CRITICAL
        if severity == CycloneSeverity.SEVERE or composite >= 0.7:
            return CycloneRiskLevel.SEVERE
        if severity == CycloneSeverity.HIGH or composite >= 0.55:
            return CycloneRiskLevel.HIGH
        if composite >= 0.35:
            return CycloneRiskLevel.MODERATE
        if composite >= 0.15:
            return CycloneRiskLevel.LOW
        return CycloneRiskLevel.MINIMAL

    def _build_population(
        self, outputs: dict[str, Any], risk: CycloneRiskLevel,
    ) -> list[PopulationExposure]:
        exposures: list[PopulationExposure] = []
        for raw in outputs.get("population_tool", {}).get("population_exposures", []):
            if isinstance(raw, dict):
                exposures.append(PopulationExposure(
                    district_id=raw.get("district_id", "unknown"),
                    name=raw.get("name", "Unknown"),
                    population=raw.get("population", 0),
                    coastal_population=raw.get("coastal_population", 0),
                    risk_level=risk,
                ))
        return exposures

    def _build_infrastructure(
        self, outputs: dict[str, Any], risk: CycloneRiskLevel,
    ) -> list[InfrastructureExposure]:
        items: list[InfrastructureExposure] = []
        for raw in outputs.get("infrastructure_tool", {}).get("infrastructure_risks", []):
            if isinstance(raw, dict):
                rl = CycloneRiskLevel.HIGH if raw.get("risk_level") in ("high", "severe") else risk
                items.append(InfrastructureExposure(
                    infrastructure_id=raw.get("infrastructure_id", "unknown"),
                    name=raw.get("name", "Unknown"),
                    category=raw.get("category", "general"),
                    risk_level=rl,
                ))
        return items

    def _extract_recommendations(self, reasoning: ReasoningResult) -> list[str]:
        for step in reversed(reasoning.steps):
            if step.metadata.get("recommendations"):
                return list(step.metadata["recommendations"])
        return [step.content for step in reasoning.steps if step.metadata.get("recommendations")]

    def _build_evidence(self, tool_results: list[ToolResult], reasoning: ReasoningResult) -> list[str]:
        evidence: list[str] = []
        for r in tool_results:
            if r.success and r.output:
                evidence.append(f"{r.tool_name}: {list(r.output.keys())[:4]}")
        evidence.append(f"reasoning_confidence={reasoning.overall_confidence:.2f}")
        return evidence

    def _build_references(self, inputs: CycloneInputs) -> list[str]:
        refs = [f"basin:{inputs.basin.value}"]
        for event in inputs.historical_events[:3]:
            refs.append(f"historical:{event.name}-{event.year}")
        return refs

    def _build_summary(
        self,
        inputs: CycloneInputs,
        severity: CycloneSeverity,
        wind: WindHazardEstimate,
        surge: StormSurgeEstimate,
        decision: DecisionRequest,
    ) -> str:
        name = inputs.cyclone_name or "Unnamed system"
        basin = inputs.basin.value.replace("_", " ").title()
        return (
            f"{name} in {basin}: {wind.category.value.replace('_', ' ')} "
            f"({wind.max_sustained_wind_kt:.0f} kt), severity {severity.value}. "
            f"Storm surge {surge.surge_height_m:.1f}m. "
            f"{len(decision.possible_actions)} response actions evaluated."
        )
