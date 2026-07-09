"""Air quality reasoning and decision pipeline."""

from __future__ import annotations

import time
from typing import Any

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningPhase, ReasoningResult, ReasoningStep
from backend.agents.specialized.agent_reflection import ReflectionResult
from backend.agents.specialized.air_quality.air_quality_context import (
    AQIAssessment,
    AirQualityAnalysisSignals,
    AirQualityInputs,
    HealthRiskAssessment,
    MitigationStrategy,
    PopulationExposure,
    PollutantReading,
)
from backend.agents.specialized.air_quality.air_quality_models import (
    ACTION_CATALOG,
    AIR_QUALITY_AGENT_ID,
    AQICategory,
    AirQualityActionType,
    HealthRiskLevel,
    PollutantType,
    PollutionSourceType,
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


class AirQualityReasoningEngine:
    """Atmospheric pollution analysis reasoning pipeline."""

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id

    async def run(
        self,
        context: AgentContext,
        tool_results: list[ToolResult] | None = None,
    ) -> tuple[ReasoningResult, AirQualityAnalysisSignals]:
        start = time.perf_counter()
        steps: list[ReasoningStep] = []
        signals = AirQualityAnalysisSignals()
        inputs = self._resolve_inputs(context)
        outputs = self._index_tool_outputs(tool_results or [])

        steps.append(self._observe(context, inputs))
        met_step, signals = self._analyze_meteorology(outputs, inputs, signals)
        steps.append(met_step)
        source_step, signals = self._analyze_pollution_sources(outputs, inputs, signals)
        steps.append(source_step)
        transport_step, signals = self._analyze_transport(outputs, inputs, signals)
        steps.append(transport_step)
        dispersion_step, signals = self._analyze_dispersion(outputs, inputs, signals)
        steps.append(dispersion_step)
        aqi_step, aqi_assessment, signals = self._analyze_aqi(outputs, inputs, signals)
        steps.append(aqi_step)
        exposure_step, exposure, signals = self._analyze_population_exposure(outputs, inputs, signals, aqi_assessment)
        steps.append(exposure_step)
        health_step, health, signals = self._analyze_health_risk(outputs, inputs, signals, aqi_assessment, exposure)
        steps.append(health_step)
        mit_step, mitigations, signals = self._generate_mitigation_strategy(outputs, signals, aqi_assessment, health)
        steps.append(mit_step)

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
                "air_quality_signals": signals.model_dump(),
                "aqi_assessment": aqi_assessment.model_dump(),
                "population_exposure": exposure.model_dump(),
                "health_risk": health.model_dump(),
                "mitigation_strategies": [m.model_dump() for m in mitigations],
                "duration_ms": elapsed,
            },
        )
        return result, signals

    def _resolve_inputs(self, context: AgentContext) -> AirQualityInputs:
        stored = context.metadata.get("air_quality_inputs")
        if isinstance(stored, AirQualityInputs):
            return stored
        return AirQualityInputs.from_request_context(context.request.context)

    def _index_tool_outputs(self, results: list[ToolResult]) -> dict[str, Any]:
        return {r.tool_name: r.output for r in results if r.success and r.output}

    def _observe(self, context: AgentContext, inputs: AirQualityInputs) -> ReasoningStep:
        city = inputs.city_name or inputs.region_id or "study area"
        return ReasoningStep(
            phase=ReasoningPhase.OBSERVE,
            content=f"Observing atmospheric pollution context for {city}",
            confidence=0.9,
        )

    def _analyze_meteorology(
        self, outputs: dict[str, Any], inputs: AirQualityInputs, signals: AirQualityAnalysisSignals,
    ) -> tuple[ReasoningStep, AirQualityAnalysisSignals]:
        wind = outputs.get("wind_tool", {})
        forecast = outputs.get("forecast_tool", {})
        met = inputs.meteorology
        speed = float(wind.get("wind_speed_ms", met.wind_speed_ms))
        inversion = bool(wind.get("stagnation")) or met.inversion_present
        temp = met.temperature_c or 30.0
        content = (
            f"Meteorology: T={temp:.0f}°C, wind={speed:.1f}m/s, "
            f"inversion={'yes' if inversion else 'no'}"
        )
        if forecast.get("persistence_likely"):
            content += ", pollution persistence likely"
        if inputs.peer_agent_outputs.get("heatwave_agent"):
            hw = inputs.peer_agent_outputs["heatwave_agent"]
            if hw.severity in ("severe", "extreme", "high"):
                content += f", heatwave compound ({hw.severity})"
                signals.compound_hazard = True
        return ReasoningStep(phase=ReasoningPhase.THINK, content=content, confidence=0.85), signals

    def _analyze_pollution_sources(
        self, outputs: dict[str, Any], inputs: AirQualityInputs, signals: AirQualityAnalysisSignals,
    ) -> tuple[ReasoningStep, AirQualityAnalysisSignals]:
        emission = outputs.get("emission_tool", {})
        pm = outputs.get("pm_tool", {})
        satellite = outputs.get("satellite_aerosol_tool", {})
        dominant = str(
            emission.get("dominant_source", inputs.emissions.dominant_source.value),
        )
        try:
            signals.dominant_source = PollutionSourceType(dominant)
        except ValueError:
            signals.dominant_source = PollutionSourceType.MIXED

        signals.biomass_burning = bool(
            emission.get("biomass_burning_significant")
            or pm.get("biomass_burning_indicator")
            or satellite.get("smoke_plume_detected")
            or inputs.emissions.biomass_burning_share_pct >= 25.0
            or inputs.satellite.biomass_burning_index > 0.5
            or inputs.satellite.smoke_plume_detected,
        )
        signals.dust_storm = bool(
            emission.get("dust_significant")
            or pm.get("dust_indicator")
            or satellite.get("dust_plume_detected")
            or inputs.emissions.dust_share_pct >= 30.0
            or inputs.satellite.dust_plume_detected
            or signals.dominant_source == PollutionSourceType.DUST,
        )
        signals.wildfire_smoke = bool(
            satellite.get("wildfire_smoke_risk")
            or (inputs.satellite.biomass_burning_index > 0.6 and inputs.satellite.fire_hotspot_count >= 10),
        )

        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Dominant source: {signals.dominant_source.value}, biomass={signals.biomass_burning}, dust={signals.dust_storm}",
            confidence=0.82,
        ), signals

    def _analyze_transport(
        self, outputs: dict[str, Any], inputs: AirQualityInputs, signals: AirQualityAnalysisSignals,
    ) -> tuple[ReasoningStep, AirQualityAnalysisSignals]:
        wind = outputs.get("wind_tool", {})
        satellite = outputs.get("satellite_aerosol_tool", {})
        transport = float(wind.get("transport_potential", 0.0))
        if not wind:
            speed = inputs.meteorology.wind_speed_ms
            transport = min(speed / 8.0, 1.0) if speed >= 1.5 else 0.1
        if satellite.get("smoke_plume_detected") and transport > 0.3:
            transport = max(transport, 0.6)
        signals.transport_score = round(transport, 3)
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Pollution transport potential={transport:.2f}",
            confidence=0.8,
        ), signals

    def _analyze_dispersion(
        self, outputs: dict[str, Any], inputs: AirQualityInputs, signals: AirQualityAnalysisSignals,
    ) -> tuple[ReasoningStep, AirQualityAnalysisSignals]:
        wind = outputs.get("wind_tool", {})
        favorable = bool(wind.get("dispersion_favorable"))
        if not wind:
            favorable = (
                inputs.meteorology.wind_speed_ms >= 2.5
                and not inputs.meteorology.inversion_present
            )
        dispersion = 0.75 if favorable else 0.25
        if inputs.meteorology.inversion_present:
            dispersion = 0.15
        signals.dispersion_score = round(dispersion, 3)
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Dispersion conditions {'favorable' if favorable else 'unfavorable'} (score={dispersion:.2f})",
            confidence=0.81,
        ), signals

    def _analyze_aqi(
        self, outputs: dict[str, Any], inputs: AirQualityInputs, signals: AirQualityAnalysisSignals,
    ) -> tuple[ReasoningStep, AQIAssessment, AirQualityAnalysisSignals]:
        aqi_out = outputs.get("aqi_tool", {})
        pm = outputs.get("pm_tool", {})
        forecast = outputs.get("forecast_tool", {})

        if aqi_out:
            aqi = int(aqi_out.get("aqi", 0))
            category = AQICategory(aqi_out.get("category", AQICategory.MODERATE.value))
            dominant = PollutantType(aqi_out.get("dominant_pollutant", PollutantType.PM25.value))
        else:
            pm25 = float(inputs.pollutants.get("pm2_5", 0.0))
            pm10 = float(inputs.pollutants.get("pm10", 0.0))
            from backend.agents.specialized.air_quality.air_quality_tools import _aqi_category, _sub_index
            from backend.agents.specialized.air_quality.air_quality_models import PM10_BREAKPOINTS, PM25_BREAKPOINTS

            idx25 = _sub_index(pm25, PM25_BREAKPOINTS)
            idx10 = _sub_index(pm10, PM10_BREAKPOINTS)
            aqi = max(idx25, idx10)
            category = _aqi_category(aqi)
            dominant = PollutantType.PM25 if idx25 >= idx10 else PollutantType.PM10

        pollutants = [
            PollutantReading(
                pollutant=PollutantType.PM25,
                concentration_ug_m3=float(pm.get("pm2_5_ug_m3", inputs.pollutants.get("pm2_5", 0))),
                dominant=dominant == PollutantType.PM25,
            ),
            PollutantReading(
                pollutant=PollutantType.PM10,
                concentration_ug_m3=float(pm.get("pm10_ug_m3", inputs.pollutants.get("pm10", 0))),
                dominant=dominant == PollutantType.PM10,
            ),
        ]

        assessment = AQIAssessment(
            aqi=aqi,
            category=category,
            dominant_pollutant=dominant,
            pollutants=pollutants,
            forecast_aqi_24h=forecast.get("forecast_aqi_24h"),
            forecast_aqi_72h=forecast.get("forecast_aqi_72h"),
        )
        signals.aqi_score = round(min(aqi / 500.0, 1.0), 3)
        signals.pm25_score = float(pm.get("pm25_score", min(float(inputs.pollutants.get("pm2_5", 0)) / 250.0, 1.0)))
        signals.pm10_score = float(pm.get("pm10_score", min(float(inputs.pollutants.get("pm10", 0)) / 430.0, 1.0)))
        signals.severe_aqi = aqi >= 301

        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"AQI={aqi} ({category.value}), dominant={dominant.value}",
            confidence=0.88,
        ), assessment, signals

    def _analyze_population_exposure(
        self,
        outputs: dict[str, Any],
        inputs: AirQualityInputs,
        signals: AirQualityAnalysisSignals,
        aqi: AQIAssessment,
    ) -> tuple[ReasoningStep, PopulationExposure, AirQualityAnalysisSignals]:
        pop_out = outputs.get("population_tool", {})
        health_out = outputs.get("health_risk_tool", {})
        pop = int(pop_out.get("population_total", inputs.population_total))
        density = float(pop_out.get("population_density", inputs.population_density))
        exposure_score = float(pop_out.get("exposure_score", 0.0))
        if not pop_out:
            exposure_score = min(density / 20000.0, 1.0) if density else min(pop / 10_000_000, 1.0)

        exposed = int(health_out.get("exposed_population", pop * min(signals.aqi_score + 0.2, 1.0)))
        sensitive = int(health_out.get("sensitive_population", pop * inputs.sensitive_population_pct / 100.0))
        zones = list(pop_out.get("exposure_zones", inputs.districts[:3]))

        exposure = PopulationExposure(
            total_population=pop,
            sensitive_population=sensitive,
            exposed_population=exposed,
            exposure_score=exposure_score,
            high_risk_zones=zones,
        )
        signals.exposure_score = round(exposure_score, 3)

        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Population exposure: {exposed:,} exposed, score={exposure_score:.2f}",
            confidence=0.79,
        ), exposure, signals

    def _analyze_health_risk(
        self,
        outputs: dict[str, Any],
        inputs: AirQualityInputs,
        signals: AirQualityAnalysisSignals,
        aqi: AQIAssessment,
        exposure: PopulationExposure,
    ) -> tuple[ReasoningStep, HealthRiskAssessment, AirQualityAnalysisSignals]:
        health_out = outputs.get("health_risk_tool", {})
        risk_score = float(health_out.get("health_risk_score", signals.aqi_score))
        if not health_out:
            risk_score = min(aqi.aqi / 400.0, 1.0)

        level_str = str(health_out.get("health_risk_level", "moderate"))
        try:
            level = HealthRiskLevel(level_str)
        except ValueError:
            level = self._map_health_level(aqi.aqi)

        health = HealthRiskAssessment(
            risk_level=level,
            risk_score=risk_score,
            respiratory_risk=float(health_out.get("respiratory_risk", risk_score * 0.9)),
            cardiovascular_risk=float(health_out.get("cardiovascular_risk", risk_score * 0.75)),
            vulnerable_groups=list(health_out.get("vulnerable_groups", ["children", "elderly", "asthmatics"])),
            hospital_admission_risk_pct=float(health_out.get("hospital_admission_risk_pct", risk_score * 12)),
        )
        signals.health_risk_score = round(risk_score, 3)

        cyclone = inputs.peer_agent_outputs.get("cyclone_agent")
        if cyclone and cyclone.severity in ("severe", "extreme"):
            signals.compound_hazard = True

        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Health risk: {level.value} (score={risk_score:.2f})",
            confidence=0.84,
        ), health, signals

    def _map_health_level(self, aqi: int) -> HealthRiskLevel:
        if aqi >= 400:
            return HealthRiskLevel.CRITICAL
        if aqi >= 301:
            return HealthRiskLevel.SEVERE
        if aqi >= 201:
            return HealthRiskLevel.HIGH
        if aqi >= 101:
            return HealthRiskLevel.MODERATE
        if aqi >= 51:
            return HealthRiskLevel.LOW
        return HealthRiskLevel.MINIMAL

    def _generate_mitigation_strategy(
        self,
        outputs: dict[str, Any],
        signals: AirQualityAnalysisSignals,
        aqi: AQIAssessment,
        health: HealthRiskAssessment,
    ) -> tuple[ReasoningStep, list[MitigationStrategy], AirQualityAnalysisSignals]:
        strategies: list[MitigationStrategy] = []
        rank = 1

        if signals.severe_aqi or aqi.aqi >= 301:
            strategies.append(MitigationStrategy(
                action_type=AirQualityActionType.EMERGENCY_AIR_QUALITY_ALERT.value,
                title="Emergency AQI alert",
                description="Activate GRAP Stage III/IV emergency measures",
                estimated_aqi_reduction=80,
                urgency="critical",
                priority_rank=rank,
            ))
            rank += 1
            strategies.append(MitigationStrategy(
                action_type=AirQualityActionType.SCHOOL_CLOSURE.value,
                title="School closure advisory",
                description="Close schools and suspend outdoor activities for children",
                estimated_aqi_reduction=20,
                urgency="high",
                priority_rank=rank,
            ))
            rank += 1

        if signals.dominant_source in (PollutionSourceType.TRAFFIC, PollutionSourceType.MIXED) or outputs.get("emission_tool", {}).get("traffic_hotspot"):
            strategies.append(MitigationStrategy(
                action_type=AirQualityActionType.VEHICLE_RESTRICTIONS.value,
                title="Vehicle restrictions",
                description="Restrict diesel commercial vehicles in pollution corridors",
                estimated_aqi_reduction=40,
                urgency="high" if signals.severe_aqi else "normal",
                priority_rank=rank,
            ))
            rank += 1
            strategies.append(MitigationStrategy(
                action_type=AirQualityActionType.TRAFFIC_RESTRICTIONS.value,
                title="Traffic restrictions",
                description="Implement odd-even traffic scheme in hotspot zones",
                estimated_aqi_reduction=35,
                priority_rank=rank,
            ))
            rank += 1

        if signals.biomass_burning or signals.dominant_source == PollutionSourceType.BIOMASS_BURNING:
            strategies.append(MitigationStrategy(
                action_type=AirQualityActionType.INDUSTRIAL_EMISSION_REDUCTION.value,
                title="Biomass burning suppression",
                description="Enforce stubble burning ban and deploy biomass management teams",
                estimated_aqi_reduction=60,
                urgency="high",
                priority_rank=rank,
            ))
            rank += 1

        if outputs.get("emission_tool", {}).get("industrial_hotspot") or signals.dominant_source == PollutionSourceType.INDUSTRIAL:
            strategies.append(MitigationStrategy(
                action_type=AirQualityActionType.INDUSTRIAL_EMISSION_REDUCTION.value,
                title="Industrial emission curtailment",
                description="Mandate temporary shutdown of non-essential industrial units",
                estimated_aqi_reduction=50,
                priority_rank=rank,
            ))
            rank += 1

        if health.risk_score >= 0.4 or signals.exposure_score >= 0.5:
            strategies.append(MitigationStrategy(
                action_type=AirQualityActionType.PUBLIC_HEALTH_ADVISORY.value,
                title="Public health advisory",
                description="Issue health advisory for sensitive groups and outdoor workers",
                estimated_aqi_reduction=5,
                urgency="high" if health.risk_level in (HealthRiskLevel.SEVERE, HealthRiskLevel.CRITICAL) else "normal",
                priority_rank=rank,
            ))
            rank += 1
            strategies.append(MitigationStrategy(
                action_type=AirQualityActionType.MASK_ADVISORY.value,
                title="Mask advisory",
                description="Distribute N95 masks and mandate outdoor mask usage",
                estimated_aqi_reduction=0,
                priority_rank=rank,
            ))
            rank += 1

        if not strategies:
            strategies.append(MitigationStrategy(
                action_type=AirQualityActionType.PUBLIC_HEALTH_ADVISORY.value,
                title="Routine air quality monitoring",
                description="Maintain monitoring and issue standard public advisories",
                estimated_aqi_reduction=0,
                priority_rank=1,
            ))

        recs = [s.title for s in strategies[:4]]
        return ReasoningStep(
            phase=ReasoningPhase.ACT,
            content=f"Generated {len(strategies)} mitigation strategies: {', '.join(recs)}",
            confidence=0.86,
            metadata={"recommendations": recs},
        ), strategies, signals


class AirQualityDecisionEngine:
    """Builds standardized DecisionRequest for air quality mitigation."""

    def __init__(self, *, agent_id: str = AIR_QUALITY_AGENT_ID) -> None:
        self._agent_id = agent_id
        self._decision_manager = DecisionManager()

    async def evaluate(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        reflection: ReflectionResult | None = None,
    ) -> DecisionRequest:
        inputs = self._resolve_inputs(context)
        signals = reasoning.metadata.get("air_quality_signals", {})
        aqi_data = reasoning.metadata.get("aqi_assessment", {})
        aqi = int(aqi_data.get("aqi", 0))
        health_score = float(signals.get("health_risk_score", 0.5))

        need_rl = (
            (reflection.needs_rl if reflection else False)
            or aqi >= 201
            or len(reasoning.metadata.get("mitigation_strategies", [])) >= 3
        )
        need_human = aqi >= 400 or health_score >= 0.85
        suggested = list(reflection.suggested_agents) if reflection else []

        decision = self._decision_manager.create(
            agent_id=self._agent_id,
            decision_type=DecisionType.AQI,
            objectives=self._build_objectives(),
            possible_actions=self._build_actions(signals, aqi),
            constraints=self._build_constraints(inputs),
            context=DecisionContext(
                scenario=ScenarioContext(
                    scenario_id=inputs.region_id or context.request_id,
                    name=f"air_quality_{inputs.region_id or 'assessment'}",
                    region_id=inputs.region_id,
                    horizon_hours=72,
                ),
                climate_state=context.climate_state,
            ),
            risk=RiskAssessment(
                level=self._map_risk_level(aqi),
                score=min(aqi / 500.0, 1.0),
                factors=[
                    f"aqi_{aqi}",
                    f"health_{health_score:.2f}",
                    f"source_{signals.get('dominant_source', 'unknown')}",
                ],
                affected_regions=inputs.districts,
                affected_population=inputs.population_total or int(inputs.population_density * 10),
                horizon_hours=72,
            ),
            priority=self._map_priority(aqi),
            confidence=reasoning.overall_confidence,
            need_simulation=bool(signals.get("compound_hazard")),
            need_other_agents=suggested,
            need_human=need_human,
            need_rl=need_rl,
            metadata={
                "aqi": aqi,
                "aqi_category": aqi_data.get("category"),
                "dominant_pollutant": aqi_data.get("dominant_pollutant"),
                "health_risk_score": health_score,
                "severe_aqi": signals.get("severe_aqi", False),
            },
        )
        return decision

    def _resolve_inputs(self, context: AgentContext) -> AirQualityInputs:
        stored = context.metadata.get("air_quality_inputs")
        if isinstance(stored, AirQualityInputs):
            return stored
        return AirQualityInputs.from_request_context(context.request.context)

    def _build_objectives(self) -> list[Objective]:
        return [
            Objective(objective_id="reduce_aqi", description="Reduce ambient air quality index", weight=0.35, maximize=False),
            Objective(objective_id="protect_public_health", description="Protect public health from pollution exposure", weight=0.35),
            Objective(objective_id="minimize_economic_disruption", description="Minimize economic disruption from controls", weight=0.15, maximize=False),
            Objective(objective_id="target_emission_sources", description="Target dominant emission sources effectively", weight=0.15),
        ]

    def _build_actions(self, signals: dict[str, Any], aqi: int) -> list[DecisionAction]:
        actions: list[DecisionAction] = []
        for action_type, (desc, cost, benefit, risk) in ACTION_CATALOG.items():
            include = False
            if action_type == AirQualityActionType.EMERGENCY_AIR_QUALITY_ALERT and aqi >= 301:
                include = True
            elif action_type == AirQualityActionType.SCHOOL_CLOSURE and aqi >= 301:
                include = True
            elif action_type == AirQualityActionType.TRAFFIC_RESTRICTIONS and aqi >= 201:
                include = True
            elif action_type == AirQualityActionType.VEHICLE_RESTRICTIONS and aqi >= 201:
                include = True
            elif action_type == AirQualityActionType.INDUSTRIAL_EMISSION_REDUCTION and (
                signals.get("dominant_source") in ("industrial", "biomass_burning")
                or signals.get("biomass_burning")
            ):
                include = True
            elif action_type in (
                AirQualityActionType.PUBLIC_HEALTH_ADVISORY,
                AirQualityActionType.MASK_ADVISORY,
            ) and aqi >= 101:
                include = True
            if include:
                try:
                    risk_level = RiskLevel(risk)
                except ValueError:
                    risk_level = RiskLevel.LOW
                actions.append(DecisionAction(
                    description=desc,
                    cost=cost,
                    expected_benefit=benefit,
                    risk=risk_level,
                    metadata={"action_type": action_type.value},
                ))
        if not actions:
            actions.append(DecisionAction(
                description=ACTION_CATALOG[AirQualityActionType.PUBLIC_HEALTH_ADVISORY][0],
                cost=2.0,
                expected_benefit=65.0,
                risk=RiskLevel.NEGLIGIBLE,
                metadata={"action_type": AirQualityActionType.PUBLIC_HEALTH_ADVISORY.value},
            ))
        return actions

    def _build_constraints(self, inputs: AirQualityInputs) -> DecisionConstraints:
        pop = inputs.population_total or int(inputs.population_density * 10) or 1_000_000
        return DecisionConstraints(
            budget=BudgetConstraint(max_cost=100.0),
            population=PopulationConstraint(max_affected_population=int(pop * 0.8)),
            safety=SafetyConstraint(max_risk_score=0.85),
            time=TimeConstraint(max_hours=72.0),
        )

    def _map_risk_level(self, aqi: int) -> RiskLevel:
        if aqi >= 400:
            return RiskLevel.CRITICAL
        if aqi >= 301:
            return RiskLevel.HIGH
        if aqi >= 201:
            return RiskLevel.MODERATE
        if aqi >= 101:
            return RiskLevel.LOW
        return RiskLevel.NEGLIGIBLE

    def _map_priority(self, aqi: int) -> DecisionPriority:
        if aqi >= 400:
            return DecisionPriority.CRITICAL
        if aqi >= 301:
            return DecisionPriority.URGENT
        if aqi >= 201:
            return DecisionPriority.HIGH
        return DecisionPriority.NORMAL
