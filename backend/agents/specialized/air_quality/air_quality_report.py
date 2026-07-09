"""Air quality report generation."""

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
from backend.agents.specialized.air_quality.air_quality_context import (
    AQIAssessment,
    AirQualityInputs,
    HealthRiskAssessment,
    MitigationStrategy,
    PopulationExposure,
)
from backend.agents.specialized.air_quality.air_quality_metrics import AirQualityExecutionMetrics
from backend.agents.specialized.air_quality.air_quality_models import AQICategory, PollutantType
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger
from backend.decision.decision_priority import DecisionPriority
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.xai.explanation_report import ExplainabilityReport

logger = get_logger(__name__)


class RequiredAction(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    priority: str = "normal"
    category: str = "mitigation"
    target_agent: str | None = None


class AirQualityReport(BaseModel):
    """Professional air quality assessment report."""

    report_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    request_id: str
    executive_summary: str = ""
    aqi_assessment: AQIAssessment = Field(default_factory=AQIAssessment)
    dominant_pollutants: list[str] = Field(default_factory=list)
    forecast: dict[str, Any] = Field(default_factory=dict)
    population_exposure: PopulationExposure = Field(default_factory=PopulationExposure)
    health_risk: HealthRiskAssessment = Field(default_factory=HealthRiskAssessment)
    climate_risk: dict[str, Any] = Field(default_factory=dict)
    mitigation_strategies: list[MitigationStrategy] = Field(default_factory=list)
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
    alternative_mitigations: list[str] = Field(default_factory=list)
    counterfactuals: list[str] = Field(default_factory=list)
    metrics: AirQualityExecutionMetrics | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AirQualityReportBuilder:
    """Assembles an AirQualityReport from analysis artifacts."""

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
    ) -> AirQualityReport:
        inputs = self._resolve_inputs(context)
        signals = reasoning.metadata.get("air_quality_signals", {})
        outputs = self._index_outputs(tool_results)

        aqi = AQIAssessment.model_validate(reasoning.metadata.get("aqi_assessment", {}))
        exposure = PopulationExposure.model_validate(reasoning.metadata.get("population_exposure", {}))
        health = HealthRiskAssessment.model_validate(reasoning.metadata.get("health_risk", {}))
        mitigations = [
            MitigationStrategy.model_validate(m)
            for m in reasoning.metadata.get("mitigation_strategies", [])
            if isinstance(m, dict)
        ]

        dominant = self._dominant_pollutants(aqi, outputs)
        forecast = self._build_forecast(outputs)
        climate_risk = self._build_climate_risk(signals, inputs)
        recommendations = self._extract_recommendations(reasoning)
        evidence = self._build_evidence(tool_results, reasoning, inputs)
        alternatives, counterfactuals = self._extract_xai(explainability)
        summary = self._build_summary(inputs, aqi, health, mitigations, decision)

        chosen = None
        if rl_response and rl_response.chosen_action:
            chosen = rl_response.chosen_action.description

        confidence = reasoning.overall_confidence
        if not validation.valid:
            confidence = min(confidence, 0.55)

        return AirQualityReport(
            agent_id=self._agent_id,
            request_id=context.request_id,
            executive_summary=summary,
            aqi_assessment=aqi,
            dominant_pollutants=dominant,
            forecast=forecast,
            population_exposure=exposure,
            health_risk=health,
            climate_risk=climate_risk,
            mitigation_strategies=mitigations,
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
            alternative_mitigations=alternatives,
            counterfactuals=counterfactuals,
            metadata={
                "validation_valid": validation.valid,
                "air_quality_signals": signals,
                "reflection_confidence": reflection.confidence if reflection else None,
                "city_name": inputs.city_name,
                "state": inputs.state,
            },
        )

    def _resolve_inputs(self, context: AgentContext) -> AirQualityInputs:
        stored = context.metadata.get("air_quality_inputs")
        if isinstance(stored, AirQualityInputs):
            return stored
        return AirQualityInputs.from_request_context(context.request.context)

    def _index_outputs(self, tool_results: list[ToolResult]) -> dict[str, Any]:
        return {r.tool_name: r.output for r in tool_results if r.success and r.output}

    def _dominant_pollutants(self, aqi: AQIAssessment, outputs: dict[str, Any]) -> list[str]:
        pollutants: list[str] = [aqi.dominant_pollutant.value]
        pm = outputs.get("pm_tool", {})
        gas = outputs.get("gas_concentration_tool", {})
        if pm.get("pm25_exceedance"):
            pollutants.append(PollutantType.PM25.value)
        if pm.get("pm10_exceedance"):
            pollutants.append(PollutantType.PM10.value)
        if gas.get("ozone_formation_likely"):
            pollutants.append(PollutantType.O3.value)
        if gas.get("industrial_gas_signature"):
            pollutants.append(PollutantType.NO2.value)
        return list(dict.fromkeys(pollutants))

    def _build_forecast(self, outputs: dict[str, Any]) -> dict[str, Any]:
        forecast = outputs.get("forecast_tool", {})
        return {
            "forecast_aqi_24h": forecast.get("forecast_aqi_24h"),
            "forecast_aqi_72h": forecast.get("forecast_aqi_72h"),
            "deteriorating_trend": forecast.get("deteriorating_trend", False),
            "improving_trend": forecast.get("improving_trend", False),
            "persistence_likely": forecast.get("persistence_likely", False),
        }

    def _build_climate_risk(self, signals: dict[str, Any], inputs: AirQualityInputs) -> dict[str, Any]:
        return {
            "severe_aqi": signals.get("severe_aqi", False),
            "biomass_burning": signals.get("biomass_burning", False),
            "dust_storm": signals.get("dust_storm", False),
            "wildfire_smoke": signals.get("wildfire_smoke", False),
            "compound_hazard": signals.get("compound_hazard", False),
            "dominant_source": signals.get("dominant_source", "unknown"),
            "dispersion_score": signals.get("dispersion_score", 0.5),
            "transport_score": signals.get("transport_score", 0.0),
        }

    def _extract_recommendations(self, reasoning: ReasoningResult) -> list[str]:
        recs: list[str] = []
        for step in reasoning.steps:
            if step.metadata.get("recommendations"):
                recs.extend(step.metadata["recommendations"])
        if not recs:
            recs = [s.content for s in reasoning.steps if s.phase.value == "act"]
        return recs

    def _build_evidence(
        self, tool_results: list[ToolResult], reasoning: ReasoningResult, inputs: AirQualityInputs,
    ) -> list[str]:
        evidence: list[str] = []
        for r in tool_results:
            if r.success and r.output:
                key_fields = ("aqi", "pm2_5_ug_m3", "health_risk_score", "dominant_source", "wind_speed_ms")
                for field in key_fields:
                    if field in r.output:
                        evidence.append(f"{r.tool_name}: {field}={r.output[field]}")
                        break
        for peer_id, peer in inputs.peer_agent_outputs.items():
            evidence.append(f"Peer {peer_id}: {peer.summary[:80]}")
        return evidence[:15]

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

    def _build_summary(
        self,
        inputs: AirQualityInputs,
        aqi: AQIAssessment,
        health: HealthRiskAssessment,
        mitigations: list[MitigationStrategy],
        decision: DecisionRequest,
    ) -> str:
        city = inputs.city_name or inputs.region_id or "the study area"
        top_action = mitigations[0].title if mitigations else "monitoring"
        return (
            f"Air quality assessment for {city}: AQI {aqi.aqi} ({aqi.category.value}), "
            f"dominant pollutant {aqi.dominant_pollutant.value}. "
            f"Health risk {health.risk_level.value} affecting ~{health.hospital_admission_risk_pct:.0f}% "
            f"hospital admission risk. Priority action: {top_action}. "
            f"Decision priority: {decision.priority.name.lower()}."
        )

    def _build_required_actions(self, decision: DecisionRequest) -> list[RequiredAction]:
        actions: list[RequiredAction] = []
        for act in decision.possible_actions[:5]:
            action_type = act.metadata.get("action_type", "mitigation")
            actions.append(RequiredAction(
                description=act.description,
                priority=decision.priority.name.lower(),
                category=str(action_type),
            ))
        return actions

    def _build_references(self, inputs: AirQualityInputs) -> list[str]:
        refs: list[str] = []
        if inputs.twin_id:
            refs.append(f"digital_twin:{inputs.twin_id}")
        if inputs.region_id:
            refs.append(f"region:{inputs.region_id}")
        refs.append("cpcb_aqi_standards")
        refs.append("imd_air_quality_forecast")
        return refs
