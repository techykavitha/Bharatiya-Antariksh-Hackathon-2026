"""Cyclone-specific reasoning and decision pipeline."""

from __future__ import annotations

import time
from typing import Any

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningPhase, ReasoningResult, ReasoningStep
from backend.agents.specialized.agent_reflection import ReflectionResult
from backend.agents.specialized.cyclone.cyclone_context import (
    CycloneAnalysisSignals,
    CycloneInputs,
    RainfallImpactEstimate,
    StormSurgeEstimate,
    TrackPoint,
    WindHazardEstimate,
)
from backend.agents.specialized.cyclone.cyclone_models import (
    CATEGORY_WIND_KT,
    CYCLONE_AGENT_ID,
    CycloneActionType,
    CycloneBasin,
    CycloneCategory,
    CycloneSeverity,
    RapidIntensificationStatus,
)
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger
from backend.decision import DecisionManager
from backend.decision.decision_actions import DecisionAction
from backend.decision.decision_constraints import (
    BudgetConstraint,
    DecisionConstraints,
    PopulationConstraint,
    SafetyConstraint,
    TimeConstraint,
)
from backend.decision.decision_context import DecisionContext, ScenarioContext
from backend.decision.decision_priority import DecisionPriority
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_types import DecisionType, Objective, RiskAssessment, RiskLevel

logger = get_logger(__name__)

CYCLONE_REASONING_STAGES: list[str] = [
    "observe",
    "detect_cyclone",
    "estimate_genesis",
    "estimate_track",
    "estimate_intensity",
    "estimate_landfall",
    "estimate_storm_surge",
    "estimate_rainfall",
    "estimate_population_exposure",
    "estimate_infrastructure_risk",
    "generate_recommendations",
]

ACTION_CATALOG: dict[CycloneActionType, tuple[str, float, float, RiskLevel]] = {
    CycloneActionType.EVACUATION: ("Execute coastal evacuation", 80.0, 95.0, RiskLevel.MODERATE),
    CycloneActionType.RESERVOIR_PREPARATION: ("Prepare reservoirs for cyclone inflow", 25.0, 70.0, RiskLevel.LOW),
    CycloneActionType.DISASTER_READINESS: ("Activate disaster readiness protocol", 50.0, 85.0, RiskLevel.LOW),
    CycloneActionType.SCHOOL_CLOSURE: ("Close schools in landfall corridor", 5.0, 65.0, RiskLevel.LOW),
    CycloneActionType.TRANSPORT_SUSPENSION: ("Suspend coastal rail and ferry services", 15.0, 75.0, RiskLevel.LOW),
    CycloneActionType.POWER_GRID_PROTECTION: ("Protect coastal power grid infrastructure", 40.0, 80.0, RiskLevel.LOW),
    CycloneActionType.EMERGENCY_RESOURCE_ALLOCATION: ("Deploy emergency relief resources", 60.0, 90.0, RiskLevel.MODERATE),
    CycloneActionType.COASTAL_WARNING: ("Issue coastal cyclone warning", 3.0, 55.0, RiskLevel.NEGLIGIBLE),
}


def _classify_wind(wind_kt: float) -> CycloneCategory:
    for category, (lo, hi) in CATEGORY_WIND_KT.items():
        if lo <= wind_kt < hi:
            return category
    if wind_kt >= 120:
        return CycloneCategory.SUPER_CYCLONIC_STORM
    return CycloneCategory.DISTURBANCE


class CycloneReasoningEngine:
    """Tropical cyclone reasoning pipeline for India basins."""

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id

    async def run(
        self,
        context: AgentContext,
        tool_results: list[ToolResult] | None = None,
    ) -> tuple[ReasoningResult, CycloneAnalysisSignals]:
        start = time.perf_counter()
        steps: list[ReasoningStep] = []
        signals = CycloneAnalysisSignals()
        inputs = self._resolve_inputs(context)
        outputs = self._index_tool_outputs(tool_results or [])

        steps.append(self._observe(context, inputs))
        detect_step, signals = self._detect_cyclone(outputs, inputs, signals)
        steps.append(detect_step)
        genesis_step, signals = self._estimate_genesis(outputs, inputs, signals)
        steps.append(genesis_step)
        track_step, signals, track = self._estimate_track(outputs, inputs, signals)
        steps.append(track_step)
        intensity_step, signals, wind_hazard = self._estimate_intensity(outputs, inputs, signals)
        steps.append(intensity_step)
        landfall_step, signals = self._estimate_landfall(outputs, inputs, signals)
        steps.append(landfall_step)
        surge_step, signals, surge = self._estimate_storm_surge(outputs, signals)
        steps.append(surge_step)
        rain_step, signals, rainfall = self._estimate_rainfall(outputs, signals)
        steps.append(rain_step)
        pop_step, signals = self._estimate_population_exposure(outputs, signals)
        steps.append(pop_step)
        infra_step, signals = self._estimate_infrastructure_risk(outputs, signals)
        steps.append(infra_step)

        severity, signals = self._resolve_severity(signals, wind_hazard)
        rec_step = self._generate_recommendations(signals, severity, surge, rainfall)
        steps.append(rec_step)

        for step in steps:
            context.add_reasoning(f"[{step.phase.value}] {step.content}")

        confidences = [s.confidence for s in steps if s.confidence > 0]
        overall = sum(confidences) / len(confidences) if confidences else 0.5
        elapsed = (time.perf_counter() - start) * 1000

        result = ReasoningResult(
            steps=steps,
            overall_confidence=overall,
            recommended_tools=[],
            metadata={
                "cyclone_signals": signals.model_dump(),
                "severity": severity.value,
                "category": wind_hazard.category.value,
                "wind_hazard": wind_hazard.model_dump(),
                "storm_surge": surge.model_dump(),
                "rainfall_impact": rainfall.model_dump(),
                "track": track,
                "duration_ms": elapsed,
                "stages": CYCLONE_REASONING_STAGES,
            },
        )
        return result, signals

    def _resolve_inputs(self, context: AgentContext) -> CycloneInputs:
        stored = context.metadata.get("cyclone_inputs")
        if isinstance(stored, CycloneInputs):
            return stored
        return CycloneInputs.from_request_context(context.request.context)

    def _index_tool_outputs(self, results: list[ToolResult]) -> dict[str, Any]:
        return {r.tool_name: r.output for r in results if r.success and r.output}

    def _observe(self, context: AgentContext, inputs: CycloneInputs) -> ReasoningStep:
        basin = inputs.basin.value if inputs.basin != CycloneBasin.UNKNOWN else "unspecified"
        return ReasoningStep(
            phase=ReasoningPhase.OBSERVE,
            content=f"Observing cyclone conditions in {inputs.region_id or 'region'} ({basin})",
            confidence=0.9,
        )

    def _detect_cyclone(
        self, outputs: dict[str, Any], inputs: CycloneInputs, signals: CycloneAnalysisSignals,
    ) -> tuple[ReasoningStep, CycloneAnalysisSignals]:
        wind_out = outputs.get("wind_tool", {})
        pressure_out = outputs.get("pressure_tool", {})
        wind = inputs.ocean.wind_speed_kt or wind_out.get("wind_speed_kt", 0.0)
        mslp = inputs.ocean.sea_level_pressure_hpa or pressure_out.get("sea_level_pressure_hpa", 1013.0)
        detected = (
            wind >= 27
            or pressure_out.get("cyclone_center_likely", False)
            or inputs.cyclone_name is not None
        )
        signals.cyclone_detected = detected
        signals.wind_score = float(wind_out.get("wind_score", min(wind / 120.0, 1.0)))
        signals.pressure_score = float(pressure_out.get("pressure_score", 0.0))
        signals.low_pressure = mslp < 1000.0
        conf = 0.85 if detected else 0.5
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Cyclone {'detected' if detected else 'not confirmed'} (wind {wind:.0f} kt, MSLP {mslp:.0f} hPa)",
            confidence=conf,
        ), signals

    def _estimate_genesis(
        self, outputs: dict[str, Any], inputs: CycloneInputs, signals: CycloneAnalysisSignals,
    ) -> tuple[ReasoningStep, CycloneAnalysisSignals]:
        sst_out = outputs.get("sst_tool", {})
        ohc_out = outputs.get("ocean_heat_tool", {})
        signals.warm_sst = bool(sst_out.get("warm_sst", False))
        signals.favorable_genesis = bool(sst_out.get("genesis_favorable", False))
        signals.sst_score = float(sst_out.get("sst_score", 0.0))
        signals.genesis_likely = signals.favorable_genesis and not signals.cyclone_detected
        if ohc_out.get("ri_likely"):
            signals.rapid_intensification = RapidIntensificationStatus.LIKELY
        elif ohc_out.get("ri_favorable"):
            signals.rapid_intensification = RapidIntensificationStatus.POSSIBLE
        content = (
            f"Genesis {'favorable' if signals.favorable_genesis else 'unfavorable'}; "
            f"RI status: {signals.rapid_intensification.value}"
        )
        return ReasoningStep(phase=ReasoningPhase.THINK, content=content, confidence=0.75), signals

    def _estimate_track(
        self, outputs: dict[str, Any], inputs: CycloneInputs, signals: CycloneAnalysisSignals,
    ) -> tuple[ReasoningStep, CycloneAnalysisSignals, list[dict[str, Any]]]:
        fc_out = outputs.get("forecast_tool", {})
        track_pts = [
            {"latitude": p.latitude, "longitude": p.longitude, "wind_speed_kt": p.wind_speed_kt}
            for p in inputs.forecast.track_points
        ]
        signals.track_score = float(fc_out.get("track_score", 0.0))
        landfall_prob = fc_out.get("landfall_probability", inputs.forecast.landfall_probability or 0.0)
        content = f"Track forecast: {len(track_pts)} points, landfall probability {landfall_prob:.0%}"
        return ReasoningStep(phase=ReasoningPhase.ACT, content=content, confidence=0.7), signals, track_pts

    def _estimate_intensity(
        self, outputs: dict[str, Any], inputs: CycloneInputs, signals: CycloneAnalysisSignals,
    ) -> tuple[ReasoningStep, CycloneAnalysisSignals, WindHazardEstimate]:
        wind_out = outputs.get("wind_tool", {})
        wind = float(wind_out.get("wind_speed_kt", inputs.ocean.wind_speed_kt or 0.0))
        category = CycloneCategory(wind_out.get("category", _classify_wind(wind).value))
        hazard = WindHazardEstimate(
            max_sustained_wind_kt=wind,
            gust_wind_kt=float(wind_out.get("gust_wind_kt", wind * 1.25)),
            destructive_radius_km=min(wind * 1.5, 300.0),
            category=category,
        )
        signals.wind_score = float(wind_out.get("wind_score", 0.0))
        if signals.rapid_intensification == RapidIntensificationStatus.LIKELY and wind >= 65:
            signals.rapid_intensification = RapidIntensificationStatus.CONFIRMED
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Intensity: {category.value} ({wind:.0f} kt sustained)",
            confidence=0.8,
        ), signals, hazard

    def _estimate_landfall(
        self, outputs: dict[str, Any], inputs: CycloneInputs, signals: CycloneAnalysisSignals,
    ) -> tuple[ReasoningStep, CycloneAnalysisSignals]:
        fc_out = outputs.get("forecast_tool", {})
        prob = float(fc_out.get("landfall_probability", inputs.forecast.landfall_probability or 0.0))
        hours = fc_out.get("landfall_hours", inputs.forecast.landfall_hours)
        signals.landfall_threat = prob >= 0.4 or bool(fc_out.get("landfall_threat"))
        states = ", ".join(inputs.coastal_states) if inputs.coastal_states else "coastal corridor"
        content = f"Landfall threat: {signals.landfall_threat} (p={prob:.0%}, ETA {hours}h) toward {states}"
        return ReasoningStep(phase=ReasoningPhase.ACT, content=content, confidence=0.72), signals

    def _estimate_storm_surge(
        self, outputs: dict[str, Any], signals: CycloneAnalysisSignals,
    ) -> tuple[ReasoningStep, CycloneAnalysisSignals, StormSurgeEstimate]:
        surge_out = outputs.get("storm_surge_tool", {})
        surge_m = float(surge_out.get("surge_height_m", 0.0))
        signals.high_storm_surge = bool(surge_out.get("high_storm_surge", surge_m >= 2.0))
        signals.surge_score = float(surge_out.get("surge_score", 0.0))
        from backend.agents.specialized.cyclone.cyclone_models import CycloneRiskLevel
        risk = CycloneRiskLevel.SEVERE if surge_m >= 4.0 else (
            CycloneRiskLevel.HIGH if surge_m >= 2.0 else CycloneRiskLevel.MODERATE
        )
        estimate = StormSurgeEstimate(
            surge_height_m=surge_m,
            inundation_depth_m=float(surge_out.get("inundation_depth_m", surge_m * 0.85)),
            coastal_exposure_km=float(surge_out.get("coastal_exposure_km", 0.0)),
            risk_level=risk,
        )
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Storm surge estimate: {surge_m:.1f} m",
            confidence=0.7,
        ), signals, estimate

    def _estimate_rainfall(
        self, outputs: dict[str, Any], signals: CycloneAnalysisSignals,
    ) -> tuple[ReasoningStep, CycloneAnalysisSignals, RainfallImpactEstimate]:
        fc_out = outputs.get("forecast_tool", {})
        rain_24 = float(fc_out.get("rainfall_mm_24h", 0.0))
        rain_72 = float(fc_out.get("rainfall_mm_72h", 0.0))
        signals.heavy_rainfall = rain_24 >= 100.0 or rain_72 >= 250.0
        signals.rainfall_score = min(rain_72 / 500.0, 1.0) if rain_72 else min(rain_24 / 200.0, 1.0)
        estimate = RainfallImpactEstimate(
            rainfall_24h_mm=rain_24,
            rainfall_72h_mm=rain_72,
            flash_flood_risk=rain_24 >= 150.0,
            landslide_risk=rain_72 >= 400.0,
        )
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Rainfall impact: {rain_24:.0f} mm/24h, {rain_72:.0f} mm/72h",
            confidence=0.68,
        ), signals, estimate

    def _estimate_population_exposure(
        self, outputs: dict[str, Any], signals: CycloneAnalysisSignals,
    ) -> tuple[ReasoningStep, CycloneAnalysisSignals]:
        pop_out = outputs.get("population_tool", {})
        signals.high_population_exposure = bool(pop_out.get("high_population_exposure", False))
        signals.vulnerability_score = float(pop_out.get("vulnerability_score", 0.0))
        total = pop_out.get("total_coastal_population", 0)
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Coastal population exposure: {total:,}",
            confidence=0.75,
        ), signals

    def _estimate_infrastructure_risk(
        self, outputs: dict[str, Any], signals: CycloneAnalysisSignals,
    ) -> tuple[ReasoningStep, CycloneAnalysisSignals]:
        infra_out = outputs.get("infrastructure_tool", {})
        signals.infrastructure_at_risk = bool(infra_out.get("infrastructure_at_risk", False))
        count = infra_out.get("infrastructure_count", 0)
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Infrastructure at risk: {count} assets flagged",
            confidence=0.73,
        ), signals

    def _resolve_severity(
        self, signals: CycloneAnalysisSignals, wind: WindHazardEstimate,
    ) -> tuple[CycloneSeverity, CycloneAnalysisSignals]:
        score = (
            signals.wind_score * 0.35
            + signals.surge_score * 0.25
            + signals.rainfall_score * 0.15
            + signals.vulnerability_score * 0.15
            + signals.track_score * 0.10
        )
        signals.composite_score = round(score, 3)
        if wind.max_sustained_wind_kt >= 90 or score >= 0.85:
            severity = CycloneSeverity.EXTREME
        elif wind.max_sustained_wind_kt >= 65 or score >= 0.7:
            severity = CycloneSeverity.SEVERE
        elif wind.max_sustained_wind_kt >= 48 or score >= 0.55:
            severity = CycloneSeverity.HIGH
        elif wind.max_sustained_wind_kt >= 34 or score >= 0.35:
            severity = CycloneSeverity.MODERATE
        elif signals.cyclone_detected or signals.genesis_likely:
            severity = CycloneSeverity.LOW
        else:
            severity = CycloneSeverity.NONE
        return severity, signals

    def _generate_recommendations(
        self,
        signals: CycloneAnalysisSignals,
        severity: CycloneSeverity,
        surge: StormSurgeEstimate,
        rainfall: RainfallImpactEstimate,
    ) -> ReasoningStep:
        recs: list[str] = []
        if severity in (CycloneSeverity.SEVERE, CycloneSeverity.EXTREME):
            recs.append("Execute phased coastal evacuation")
        if signals.high_storm_surge:
            recs.append(f"Prepare for {surge.surge_height_m:.1f}m storm surge inundation")
        if rainfall.flash_flood_risk:
            recs.append("Coordinate with flood agent for inland rainfall impacts")
        if signals.rapid_intensification in (
            RapidIntensificationStatus.LIKELY,
            RapidIntensificationStatus.CONFIRMED,
        ):
            recs.append("Monitor for rapid intensification — update warnings every 3 hours")
        if not recs:
            recs.append("Continue cyclone monitoring and issue coastal advisories")
        return ReasoningStep(
            phase=ReasoningPhase.ACT,
            content="; ".join(recs),
            confidence=0.8,
            metadata={"recommendations": recs},
        )


class CycloneDecisionEngine:
    """Builds standardized DecisionRequest objects for cyclone response."""

    def __init__(self, *, agent_id: str = CYCLONE_AGENT_ID) -> None:
        self._agent_id = agent_id
        self._decision_manager = DecisionManager()

    async def evaluate(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        reflection: ReflectionResult,
    ) -> DecisionRequest:
        inputs = self._resolve_inputs(context)
        signals_raw = reasoning.metadata.get("cyclone_signals", {})
        severity = CycloneSeverity(reasoning.metadata.get("severity", CycloneSeverity.NONE.value))
        composite = float(signals_raw.get("composite_score", 0.0))

        need_rl = reflection.needs_rl or (
            severity in (CycloneSeverity.SEVERE, CycloneSeverity.EXTREME) and composite >= 0.65
        )
        need_human = severity == CycloneSeverity.EXTREME
        suggested_agents = list(reflection.suggested_agents)
        priority = self._resolve_priority(severity)
        risk_level = self._map_risk_level(severity, composite)
        actions = self._build_actions(severity, signals_raw)

        decision = self._decision_manager.create(
            agent_id=self._agent_id,
            decision_type=DecisionType.CYCLONE,
            objectives=self._build_objectives(severity),
            possible_actions=actions,
            constraints=self._build_constraints(inputs, severity),
            context=DecisionContext(
                scenario=ScenarioContext(
                    scenario_id=inputs.region_id or context.request_id,
                    name=f"cyclone_{inputs.cyclone_name or inputs.region_id or 'analysis'}",
                    region_id=inputs.region_id,
                    horizon_hours=int(inputs.forecast.landfall_hours or 72),
                ),
                climate_state=context.climate_state,
            ),
            risk=RiskAssessment(
                level=risk_level,
                score=composite,
                factors=[f"severity_{severity.value}", f"basin_{inputs.basin.value}"],
                affected_regions=inputs.districts + inputs.coastal_states,
                affected_population=self._estimate_population(inputs),
                horizon_hours=int(inputs.forecast.landfall_hours or 72),
            ),
            priority=priority,
            confidence=reasoning.overall_confidence,
            need_simulation=reflection.needs_simulation,
            need_other_agents=suggested_agents,
            need_human=need_human,
            need_rl=need_rl,
            rationale=self._build_rationale(signals_raw, severity, reflection),
            metadata={
                "severity": severity.value,
                "category": reasoning.metadata.get("category"),
                "cyclone_name": inputs.cyclone_name,
                "basin": inputs.basin.value,
                "composite_score": composite,
            },
            validate=True,
        )
        logger.debug("cyclone_decision_evaluated", decision_id=decision.decision_id, need_rl=need_rl)
        return decision

    def _resolve_inputs(self, context: AgentContext) -> CycloneInputs:
        stored = context.metadata.get("cyclone_inputs")
        if isinstance(stored, CycloneInputs):
            return stored
        return CycloneInputs.from_request_context(context.request.context)

    def _resolve_priority(self, severity: CycloneSeverity) -> DecisionPriority:
        if severity == CycloneSeverity.EXTREME:
            return DecisionPriority.CRITICAL
        if severity == CycloneSeverity.SEVERE:
            return DecisionPriority.URGENT
        if severity == CycloneSeverity.HIGH:
            return DecisionPriority.HIGH
        if severity == CycloneSeverity.MODERATE:
            return DecisionPriority.NORMAL
        return DecisionPriority.LOW

    def _map_risk_level(self, severity: CycloneSeverity, composite: float) -> RiskLevel:
        if severity == CycloneSeverity.EXTREME or composite >= 0.85:
            return RiskLevel.CRITICAL
        if severity == CycloneSeverity.SEVERE or composite >= 0.7:
            return RiskLevel.SEVERE
        if severity == CycloneSeverity.HIGH or composite >= 0.55:
            return RiskLevel.HIGH
        if composite >= 0.35:
            return RiskLevel.MODERATE
        return RiskLevel.LOW

    def _build_actions(self, severity: CycloneSeverity, signals: dict[str, Any]) -> list[DecisionAction]:
        action_types: list[CycloneActionType] = [CycloneActionType.COASTAL_WARNING]
        if severity in (CycloneSeverity.MODERATE, CycloneSeverity.HIGH, CycloneSeverity.SEVERE, CycloneSeverity.EXTREME):
            action_types.extend([
                CycloneActionType.DISASTER_READINESS,
                CycloneActionType.SCHOOL_CLOSURE,
            ])
        if severity in (CycloneSeverity.HIGH, CycloneSeverity.SEVERE, CycloneSeverity.EXTREME):
            action_types.extend([
                CycloneActionType.TRANSPORT_SUSPENSION,
                CycloneActionType.POWER_GRID_PROTECTION,
                CycloneActionType.EMERGENCY_RESOURCE_ALLOCATION,
            ])
        if signals.get("high_storm_surge"):
            action_types.append(CycloneActionType.EVACUATION)
        if signals.get("heavy_rainfall"):
            action_types.append(CycloneActionType.RESERVOIR_PREPARATION)
        if severity in (CycloneSeverity.SEVERE, CycloneSeverity.EXTREME):
            action_types.append(CycloneActionType.EVACUATION)

        seen: set[CycloneActionType] = set()
        actions: list[DecisionAction] = []
        risk_map = {"negligible": 0.1, "low": 0.25, "moderate": 0.5, "high": 0.75, "severe": 0.9, "critical": 1.0}
        for at in action_types:
            if at in seen:
                continue
            seen.add(at)
            desc, cost, benefit, risk = ACTION_CATALOG[at]
            actions.append(DecisionAction(
                description=desc,
                cost=cost,
                expected_benefit=benefit,
                risk=risk,
                risk_score=risk_map.get(risk.value, 0.4),
                category=at.value,
            ))
        return actions

    def _build_objectives(self, severity: CycloneSeverity) -> list[Objective]:
        objs = [
            Objective(objective_id="minimize_casualties", description="Minimize cyclone-related casualties", weight=0.40),
            Objective(objective_id="protect_coastal_population", description="Protect coastal population", weight=0.30),
            Objective(objective_id="maintain_critical_infra", description="Maintain critical infrastructure", weight=0.20),
        ]
        if severity in (CycloneSeverity.SEVERE, CycloneSeverity.EXTREME):
            objs.append(Objective(objective_id="optimize_evacuation", description="Optimize evacuation timing", weight=0.10))
        else:
            objs.append(Objective(objective_id="minimize_cost", description="Minimize response cost", weight=0.10, maximize=False))
        return objs

    def _build_constraints(self, inputs: CycloneInputs, severity: CycloneSeverity) -> DecisionConstraints:
        max_cost = 300.0 if severity in (CycloneSeverity.SEVERE, CycloneSeverity.EXTREME) else 100.0
        return DecisionConstraints(
            budget=BudgetConstraint(max_cost=max_cost),
            time=TimeConstraint(max_hours=float(inputs.forecast.landfall_hours or 72)),
            population=PopulationConstraint(max_affected_population=2_000_000),
            safety=SafetyConstraint(max_risk_score=0.9),
        )

    def _build_rationale(
        self, signals: dict[str, Any], severity: CycloneSeverity, reflection: ReflectionResult,
    ) -> list[str]:
        rationale = [f"Cyclone severity: {severity.value}"]
        if signals.get("landfall_threat"):
            rationale.append("Landfall threat identified on forecast track")
        if signals.get("high_storm_surge"):
            rationale.append("High storm surge risk along exposed coastline")
        if reflection.needs_rl:
            rationale.append("RL optimization recommended for evacuation resource allocation")
        rationale.extend(reflection.notes[:3])
        return rationale

    def _estimate_population(self, inputs: CycloneInputs) -> int:
        return 500_000 * max(len(inputs.districts), 1)
