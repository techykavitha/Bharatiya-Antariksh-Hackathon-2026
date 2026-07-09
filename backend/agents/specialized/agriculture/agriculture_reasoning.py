"""Agriculture reasoning and decision pipeline."""

from __future__ import annotations

import time
from typing import Any

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningPhase, ReasoningResult, ReasoningStep
from backend.agents.specialized.agent_reflection import ReflectionResult
from backend.agents.specialized.agriculture.agriculture_context import (
    AgricultureAnalysisSignals,
    AgricultureInputs,
    CropCondition,
    IrrigationRecommendation,
    RagRetrievalResult,
    SoilMoistureAssessment,
    YieldRiskAssessment,
)
from backend.agents.specialized.agriculture.agriculture_models import (
    ACTION_CATALOG,
    AGRICULTURE_AGENT_ID,
    AgricultureActionType,
    CropHealthStatus,
    CropStressType,
    IrrigationRecommendationType,
    YieldRiskLevel,
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


class AgricultureReasoningEngine:
    """Precision agriculture reasoning pipeline with RAG-informed recommendations."""

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id

    async def run(
        self,
        context: AgentContext,
        tool_results: list[ToolResult] | None = None,
        rag_result: RagRetrievalResult | None = None,
    ) -> tuple[ReasoningResult, AgricultureAnalysisSignals]:
        start = time.perf_counter()
        steps: list[ReasoningStep] = []
        signals = AgricultureAnalysisSignals()
        inputs = self._resolve_inputs(context)
        outputs = self._index_tool_outputs(tool_results or [])

        steps.append(self._observe(context, inputs))
        crop_step, crop, signals = self._analyze_crop_condition(outputs, inputs, signals)
        steps.append(crop_step)
        soil_step, soil, signals = self._analyze_soil_moisture(outputs, inputs, signals)
        steps.append(soil_step)
        weather_step, signals = self._analyze_weather_forecast(outputs, inputs, signals)
        steps.append(weather_step)
        heat_step, signals = self._analyze_heat_stress(outputs, inputs, signals)
        steps.append(heat_step)
        flood_step, signals = self._analyze_flood_risk(outputs, inputs, signals)
        steps.append(flood_step)
        yield_step, yield_risk, signals = self._analyze_yield_risk(outputs, signals)
        steps.append(yield_step)
        rag_step = self._retrieve_advisory(rag_result, inputs)
        steps.append(rag_step)
        irr_step, irrigation, signals = self._generate_irrigation_strategy(outputs, soil, signals)
        steps.append(irr_step)
        adapt_step, signals = self._generate_adaptation_recommendations(signals, rag_result, crop)
        steps.append(adapt_step)

        signals.resilience_score = self._compute_resilience(signals)

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
                "agriculture_signals": signals.model_dump(),
                "crop_condition": crop.model_dump(),
                "soil_moisture": soil.model_dump(),
                "yield_risk": yield_risk.model_dump(),
                "irrigation": irrigation.model_dump(),
                "rag_document_count": rag_result.retrieval_count if rag_result else 0,
                "resilience_score": signals.resilience_score,
                "duration_ms": elapsed,
            },
        )
        return result, signals

    def _resolve_inputs(self, context: AgentContext) -> AgricultureInputs:
        stored = context.metadata.get("agriculture_inputs")
        if isinstance(stored, AgricultureInputs):
            return stored
        return AgricultureInputs.from_request_context(context.request.context)

    def _index_tool_outputs(self, results: list[ToolResult]) -> dict[str, Any]:
        return {r.tool_name: r.output for r in results if r.success and r.output}

    def _observe(self, context: AgentContext, inputs: AgricultureInputs) -> ReasoningStep:
        region = inputs.state or inputs.region_id or "farm region"
        return ReasoningStep(
            phase=ReasoningPhase.OBSERVE,
            content=f"Observing {inputs.crop_type} crop in {region} ({inputs.season} season)",
            confidence=0.9,
        )

    def _analyze_crop_condition(
        self, outputs: dict[str, Any], inputs: AgricultureInputs, signals: AgricultureAnalysisSignals,
    ) -> tuple[ReasoningStep, CropCondition, AgricultureAnalysisSignals]:
        ndvi_out = outputs.get("ndvi_tool", {})
        evi_out = outputs.get("evi_tool", {})
        cal_out = outputs.get("crop_calendar_tool", {})
        ndvi = float(ndvi_out.get("ndvi", inputs.remote_sensing.ndvi))
        evi = float(evi_out.get("evi", inputs.remote_sensing.evi))
        health_str = ndvi_out.get("health_status", CropHealthStatus.MODERATE.value)
        try:
            health = CropHealthStatus(health_str)
        except ValueError:
            health = CropHealthStatus.MODERATE
        crop = CropCondition(
            crop_type=inputs.crop_type,
            health_status=health,
            phenology_stage=str(cal_out.get("phenology_stage", "vegetative")),
            ndvi=ndvi,
            evi=evi,
            area_hectares=inputs.area_hectares,
        )
        signals.crop_health_score = float(ndvi_out.get("crop_health_score", min(ndvi / 0.8, 1.0)))
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Crop health: {health.value}, NDVI={ndvi:.2f}, stage={crop.phenology_stage}",
            confidence=0.85,
        ), crop, signals

    def _analyze_soil_moisture(
        self, outputs: dict[str, Any], inputs: AgricultureInputs, signals: AgricultureAnalysisSignals,
    ) -> tuple[ReasoningStep, SoilMoistureAssessment, AgricultureAnalysisSignals]:
        sm_out = outputs.get("soil_moisture_tool", {})
        moisture = float(sm_out.get("soil_moisture_pct", inputs.soil.soil_moisture_pct or 40.0))
        deficit = float(sm_out.get("moisture_deficit_pct", max(inputs.soil.field_capacity_pct - moisture, 0)))
        status = "adequate"
        if moisture < inputs.soil.field_capacity_pct * 0.4:
            status = "critical_deficit"
            signals.drought_risk = True
            signals.water_stress = True
        elif moisture < inputs.soil.field_capacity_pct * 0.6:
            status = "deficit"
            signals.water_stress = True
        soil = SoilMoistureAssessment(
            soil_moisture_pct=moisture,
            deficit_pct=deficit,
            status=status,
            irrigation_needed=bool(sm_out.get("irrigation_needed", moisture < inputs.soil.field_capacity_pct * 0.6)),
        )
        signals.soil_moisture_score = float(sm_out.get("soil_moisture_score", moisture / inputs.soil.field_capacity_pct))
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Soil moisture {moisture:.1f}% ({status})",
            confidence=0.82,
        ), soil, signals

    def _analyze_weather_forecast(
        self, outputs: dict[str, Any], inputs: AgricultureInputs, signals: AgricultureAnalysisSignals,
    ) -> tuple[ReasoningStep, AgricultureAnalysisSignals]:
        forecast = outputs.get("forecast_tool", {})
        rain_7d = float(forecast.get("forecast_rainfall_7d_mm", inputs.weather.forecast_rainfall_7d_mm))
        content = f"7-day forecast rainfall: {rain_7d:.0f}mm"
        if forecast.get("drought_persistence_likely"):
            signals.drought_risk = True
            content += " — drought persistence likely"
        return ReasoningStep(phase=ReasoningPhase.THINK, content=content, confidence=0.75), signals

    def _analyze_heat_stress(
        self, outputs: dict[str, Any], inputs: AgricultureInputs, signals: AgricultureAnalysisSignals,
    ) -> tuple[ReasoningStep, AgricultureAnalysisSignals]:
        weather = outputs.get("weather_tool", {})
        heatwave = inputs.peer_agent_outputs.get("heatwave_agent")
        score = 0.3
        if weather.get("heat_stress"):
            score = 0.75
        if heatwave and heatwave.severity in ("severe", "extreme", "high"):
            score = max(score, 0.8)
        max_temp = float(weather.get("max_temp_c", inputs.weather.max_temp_c or 30.0))
        if max_temp >= 40.0:
            score = max(score, 0.85)
        signals.heat_stress_score = round(score, 3)
        signals.heat_stress = score >= 0.6
        pest = bool(weather.get("pest_favorability"))
        signals.pest_favorability_score = 0.7 if pest else 0.2
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Heat stress score={score:.2f}, pest favorability={'high' if pest else 'low'}",
            confidence=0.8,
        ), signals

    def _analyze_flood_risk(
        self, outputs: dict[str, Any], inputs: AgricultureInputs, signals: AgricultureAnalysisSignals,
    ) -> tuple[ReasoningStep, AgricultureAnalysisSignals]:
        weather = outputs.get("weather_tool", {})
        flood = inputs.peer_agent_outputs.get("flood_agent")
        score = 0.2
        if weather.get("excess_rainfall"):
            score = 0.65
        if flood and flood.severity in ("severe", "extreme", "high"):
            score = max(score, 0.8)
        signals.flood_risk_score = round(score, 3)
        signals.flood_impact = score >= 0.55
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Flood impact risk score={score:.2f}",
            confidence=0.78,
        ), signals

    def _analyze_yield_risk(
        self, outputs: dict[str, Any], signals: AgricultureAnalysisSignals,
    ) -> tuple[ReasoningStep, YieldRiskAssessment, AgricultureAnalysisSignals]:
        yield_out = outputs.get("yield_estimation_tool", {})
        score = float(yield_out.get("yield_risk_score", 0.3))
        estimated = float(yield_out.get("estimated_yield_pct", 100.0))
        if score >= 0.7:
            level = YieldRiskLevel.CRITICAL
        elif score >= 0.55:
            level = YieldRiskLevel.SEVERE
        elif score >= 0.4:
            level = YieldRiskLevel.HIGH
        elif score >= 0.25:
            level = YieldRiskLevel.MODERATE
        else:
            level = YieldRiskLevel.LOW
        drivers: list[str] = []
        if signals.drought_risk:
            drivers.append("drought")
        if signals.heat_stress:
            drivers.append("heat_stress")
        if signals.flood_impact:
            drivers.append("flood")
        yield_risk = YieldRiskAssessment(
            risk_level=level,
            risk_score=round(score, 3),
            estimated_yield_pct=estimated,
            drivers=drivers,
        )
        signals.yield_risk_score = round(score, 3)
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Yield risk: {level.value} ({estimated:.0f}% of normal)",
            confidence=0.8,
        ), yield_risk, signals

    def _retrieve_advisory(
        self, rag_result: RagRetrievalResult | None, inputs: AgricultureInputs,
    ) -> ReasoningStep:
        count = rag_result.retrieval_count if rag_result else 0
        titles = [d.title for d in rag_result.documents[:2]] if rag_result else []
        content = f"RAG retrieved {count} document(s)"
        if titles:
            content += f": {', '.join(titles)}"
        return ReasoningStep(phase=ReasoningPhase.THINK, content=content, confidence=0.8 if count else 0.4)

    def _generate_irrigation_strategy(
        self,
        outputs: dict[str, Any],
        soil: SoilMoistureAssessment,
        signals: AgricultureAnalysisSignals,
    ) -> tuple[ReasoningStep, IrrigationRecommendation, AgricultureAnalysisSignals]:
        irr_out = outputs.get("irrigation_tool", {})
        rec_type = irr_out.get("recommendation_type", "maintain")
        try:
            rec_enum = IrrigationRecommendationType(rec_type)
        except ValueError:
            rec_enum = IrrigationRecommendationType.MAINTAIN
        irrigation = IrrigationRecommendation(
            recommendation_type=rec_enum,
            volume_mm=float(irr_out.get("irrigation_volume_mm", 25.0)),
            frequency_days=int(irr_out.get("frequency_days", 7)),
            method=str(irr_out.get("method", "canal")),
            rationale=f"Soil moisture {soil.status}; deficit {soil.deficit_pct:.1f}%",
            urgency="high" if rec_enum == IrrigationRecommendationType.EMERGENCY else "normal",
        )
        return ReasoningStep(
            phase=ReasoningPhase.ACT,
            content=f"Irrigation: {rec_enum.value}, {irrigation.volume_mm:.0f}mm every {irrigation.frequency_days}d",
            confidence=0.83,
        ), irrigation, signals

    def _generate_adaptation_recommendations(
        self,
        signals: AgricultureAnalysisSignals,
        rag_result: RagRetrievalResult | None,
        crop: CropCondition,
    ) -> tuple[ReasoningStep, AgricultureAnalysisSignals]:
        recs: list[str] = []
        if signals.drought_risk:
            recs.append("Implement water conservation and micro-irrigation")
            crop.stress_type = CropStressType.DROUGHT
        if signals.heat_stress:
            recs.append("Schedule irrigation at critical growth stages during heatwave")
            crop.stress_type = CropStressType.HEAT if crop.stress_type == CropStressType.NONE else CropStressType.COMPOUND
        if signals.flood_impact:
            recs.append("Improve field drainage and delay sowing in flood-prone plots")
            crop.stress_type = CropStressType.FLOOD if crop.stress_type == CropStressType.NONE else CropStressType.COMPOUND
        if signals.pest_favorability_score >= 0.6:
            recs.append("Monitor pest populations and apply IPM protocols")
        if rag_result and rag_result.advisories:
            recs.append(f"Follow advisory: {rag_result.advisories[0].title}")
        if not recs:
            recs.append("Continue standard crop management practices")
        return ReasoningStep(
            phase=ReasoningPhase.VERIFY,
            content="; ".join(recs),
            confidence=0.85,
            metadata={"recommendations": recs},
        ), signals

    def _compute_resilience(self, signals: AgricultureAnalysisSignals) -> float:
        risk_avg = (
            signals.yield_risk_score
            + signals.heat_stress_score
            + signals.flood_risk_score
        ) / 3.0
        return round(max(0.0, min(signals.crop_health_score * 0.4 + signals.soil_moisture_score * 0.3 + (1.0 - risk_avg) * 0.3, 1.0)), 3)


class AgricultureDecisionEngine:
    """Builds standardized DecisionRequest for agricultural actions."""

    def __init__(self, *, agent_id: str = AGRICULTURE_AGENT_ID) -> None:
        self._agent_id = agent_id
        self._decision_manager = DecisionManager()

    async def evaluate(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        reflection: ReflectionResult | None = None,
    ) -> DecisionRequest:
        inputs = self._resolve_inputs(context)
        signals = reasoning.metadata.get("agriculture_signals", {})
        resilience = float(signals.get("resilience_score", 0.5))

        need_rl = (
            (reflection.needs_rl if reflection else False)
            or signals.get("drought_risk", False)
            or signals.get("water_stress", False)
            or float(signals.get("yield_risk_score", 0)) >= 0.5
        )
        need_human = float(signals.get("yield_risk_score", 0)) >= 0.75
        suggested = list(reflection.suggested_agents) if reflection else []

        decision = self._decision_manager.create(
            agent_id=self._agent_id,
            decision_type=DecisionType.AGRICULTURE,
            objectives=self._build_objectives(),
            possible_actions=self._build_actions(signals, reasoning),
            constraints=self._build_constraints(inputs),
            context=DecisionContext(
                scenario=ScenarioContext(
                    scenario_id=inputs.region_id or context.request_id,
                    name=f"agriculture_{inputs.crop_type}_{inputs.region_id or 'analysis'}",
                    region_id=inputs.region_id,
                    horizon_hours=720,
                ),
                climate_state=context.climate_state,
            ),
            risk=RiskAssessment(
                level=self._map_risk_level(signals),
                score=float(signals.get("yield_risk_score", 0.3)),
                factors=[f"crop_{inputs.crop_type}", f"season_{inputs.season}"],
                affected_regions=inputs.districts,
                affected_population=int(inputs.area_hectares * 5),
                horizon_hours=720,
            ),
            priority=self._map_priority(signals),
            confidence=reasoning.overall_confidence,
            need_simulation=signals.get("flood_impact") and signals.get("drought_risk"),
            need_other_agents=suggested,
            need_human=need_human,
            need_rl=need_rl,
            rationale=self._build_rationale(signals, inputs),
            metadata={"resilience_score": resilience, "crop_type": inputs.crop_type},
            validate=True,
        )
        logger.debug("agriculture_decision_evaluated", decision_id=decision.decision_id, need_rl=need_rl)
        return decision

    def _resolve_inputs(self, context: AgentContext) -> AgricultureInputs:
        stored = context.metadata.get("agriculture_inputs")
        if isinstance(stored, AgricultureInputs):
            return stored
        return AgricultureInputs.from_request_context(context.request.context)

    def _map_risk_level(self, signals: dict[str, Any]) -> RiskLevel:
        score = float(signals.get("yield_risk_score", 0.3))
        if score >= 0.75:
            return RiskLevel.CRITICAL
        if score >= 0.55:
            return RiskLevel.SEVERE
        if score >= 0.4:
            return RiskLevel.HIGH
        if score >= 0.25:
            return RiskLevel.MODERATE
        return RiskLevel.LOW

    def _map_priority(self, signals: dict[str, Any]) -> DecisionPriority:
        score = float(signals.get("yield_risk_score", 0.3))
        if score >= 0.75:
            return DecisionPriority.CRITICAL
        if score >= 0.55:
            return DecisionPriority.URGENT
        if score >= 0.4:
            return DecisionPriority.HIGH
        return DecisionPriority.NORMAL

    def _build_actions(self, signals: dict[str, Any], reasoning: ReasoningResult) -> list[DecisionAction]:
        irrigation = reasoning.metadata.get("irrigation", {})
        rec_type = irrigation.get("recommendation_type", "maintain")
        action_types: list[AgricultureActionType] = []

        if rec_type == "emergency":
            action_types.append(AgricultureActionType.EMERGENCY_IRRIGATION)
        elif rec_type == "increase":
            action_types.append(AgricultureActionType.INCREASE_IRRIGATION)
        elif rec_type == "reduce":
            action_types.append(AgricultureActionType.REDUCE_IRRIGATION)

        if signals.get("drought_risk") or signals.get("water_stress"):
            action_types.extend([
                AgricultureActionType.WATER_CONSERVATION,
                AgricultureActionType.ALTERNATIVE_CROP,
            ])
        if signals.get("heat_stress"):
            action_types.append(AgricultureActionType.CHANGE_CROP_SCHEDULE)
        if float(signals.get("pest_favorability_score", 0)) >= 0.6:
            action_types.append(AgricultureActionType.CROP_PROTECTION)
        if float(signals.get("yield_risk_score", 0)) >= 0.55:
            action_types.append(AgricultureActionType.GOVERNMENT_ASSISTANCE)

        if not action_types:
            action_types.append(AgricultureActionType.INCREASE_IRRIGATION)

        risk_map = {
            "negligible": RiskLevel.NEGLIGIBLE, "low": RiskLevel.LOW,
            "moderate": RiskLevel.MODERATE, "high": RiskLevel.HIGH,
        }
        seen: set[AgricultureActionType] = set()
        actions: list[DecisionAction] = []
        for at in action_types:
            if at in seen:
                continue
            seen.add(at)
            desc, cost, benefit, risk_str = ACTION_CATALOG[at]
            risk = risk_map.get(risk_str, RiskLevel.MODERATE)
            actions.append(DecisionAction(
                description=desc, cost=cost, expected_benefit=benefit, risk=risk,
                risk_score={"negligible": 0.1, "low": 0.2, "moderate": 0.4, "high": 0.6}.get(risk_str, 0.35),
                category=at.value,
            ))
        return actions

    def _build_objectives(self) -> list[Objective]:
        return [
            Objective(objective_id="maximize_yield", description="Maximize crop yield potential", weight=0.35),
            Objective(objective_id="minimize_water_use", description="Optimize water use efficiency", weight=0.25),
            Objective(objective_id="protect_crop_health", description="Protect crop health and reduce stress", weight=0.25),
            Objective(objective_id="farmer_livelihood", description="Support farmer livelihood security", weight=0.15),
        ]

    def _build_constraints(self, inputs: AgricultureInputs) -> DecisionConstraints:
        return DecisionConstraints(
            budget=BudgetConstraint(max_cost=100.0),
            time=TimeConstraint(max_hours=720.0),
            population=PopulationConstraint(max_affected_population=1_000_000),
            safety=SafetyConstraint(max_risk_score=0.85),
        )

    def _build_rationale(self, signals: dict[str, Any], inputs: AgricultureInputs) -> list[str]:
        rationale = [f"Crop: {inputs.crop_type} ({inputs.season} season)"]
        if signals.get("drought_risk"):
            rationale.append("Drought risk requires irrigation optimization")
        if signals.get("heat_stress"):
            rationale.append("Heat stress threatens critical growth stages")
        if signals.get("flood_impact"):
            rationale.append("Flood risk may damage standing crop")
        return rationale
