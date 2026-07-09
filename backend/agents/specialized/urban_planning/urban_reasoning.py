"""Urban planning reasoning and decision pipeline."""

from __future__ import annotations

import time
from typing import Any

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningPhase, ReasoningResult, ReasoningStep
from backend.agents.specialized.agent_reflection import ReflectionResult
from backend.agents.specialized.urban_planning.urban_context import (
    GreenCoverAnalysis,
    InvestmentPriority,
    MitigationOption,
    UrbanAnalysisSignals,
    UrbanInputs,
)
from backend.agents.specialized.urban_planning.urban_models import (
    ACTION_CATALOG,
    URBAN_PLANNING_AGENT_ID,
    MitigationStrategyType,
    UrbanActionType,
    UrbanResilienceLevel,
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


class UrbanReasoningEngine:
    """Long-term urban climate adaptation reasoning pipeline."""

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id

    async def run(
        self,
        context: AgentContext,
        tool_results: list[ToolResult] | None = None,
    ) -> tuple[ReasoningResult, UrbanAnalysisSignals]:
        start = time.perf_counter()
        steps: list[ReasoningStep] = []
        signals = UrbanAnalysisSignals()
        inputs = self._resolve_inputs(context)
        outputs = self._index_tool_outputs(tool_results or [])

        steps.append(self._observe(context, inputs))
        env_step, signals = self._analyze_urban_environment(outputs, inputs, signals)
        steps.append(env_step)
        heat_step, signals = self._analyze_heat_risk(outputs, inputs, signals)
        steps.append(heat_step)
        flood_step, signals = self._analyze_flood_risk(outputs, inputs, signals)
        steps.append(flood_step)
        water_step, signals = self._analyze_water_availability(outputs, inputs, signals)
        steps.append(water_step)
        green_step, green_analysis, signals = self._analyze_green_cover(outputs, inputs, signals)
        steps.append(green_step)
        drain_step, signals = self._analyze_drainage(outputs, inputs, signals)
        steps.append(drain_step)
        infra_step, signals = self._analyze_infrastructure(outputs, inputs, signals)
        steps.append(infra_step)
        mit_step, mitigations, signals = self._generate_mitigation_options(outputs, signals, green_analysis)
        steps.append(mit_step)
        benefit_step, investments, signals = self._estimate_long_term_benefit(mitigations, signals)
        steps.append(benefit_step)
        rec_step = self._generate_recommendations(signals, mitigations)
        steps.append(rec_step)

        signals.resilience_score, signals.resilience_level = self._compute_resilience(signals)

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
                "urban_signals": signals.model_dump(),
                "mitigation_options": [m.model_dump() for m in mitigations],
                "investment_priorities": [i.model_dump() for i in investments],
                "green_cover_analysis": green_analysis.model_dump(),
                "resilience_score": signals.resilience_score,
                "resilience_level": signals.resilience_level.value,
                "duration_ms": elapsed,
            },
        )
        return result, signals

    def _resolve_inputs(self, context: AgentContext) -> UrbanInputs:
        stored = context.metadata.get("urban_inputs")
        if isinstance(stored, UrbanInputs):
            return stored
        return UrbanInputs.from_request_context(context.request.context)

    def _index_tool_outputs(self, results: list[ToolResult]) -> dict[str, Any]:
        return {r.tool_name: r.output for r in results if r.success and r.output}

    def _observe(self, context: AgentContext, inputs: UrbanInputs) -> ReasoningStep:
        city = inputs.city_name or inputs.region_id or "urban area"
        return ReasoningStep(
            phase=ReasoningPhase.OBSERVE,
            content=f"Observing urban climate planning context for {city}",
            confidence=0.9,
        )

    def _analyze_urban_environment(
        self, outputs: dict[str, Any], inputs: UrbanInputs, signals: UrbanAnalysisSignals,
    ) -> tuple[ReasoningStep, UrbanAnalysisSignals]:
        land = outputs.get("land_use_tool", {})
        building = outputs.get("building_tool", {})
        impervious = float(land.get("impervious_pct", inputs.land_use.impervious_pct))
        density = float(building.get("building_density", inputs.environment.building_density))
        content = (
            f"Urban environment: impervious={impervious:.0f}%, "
            f"building_density={density:.2f}, dominant={land.get('dominant_category', 'unknown')}"
        )
        return ReasoningStep(phase=ReasoningPhase.THINK, content=content, confidence=0.82), signals

    def _analyze_heat_risk(
        self, outputs: dict[str, Any], inputs: UrbanInputs, signals: UrbanAnalysisSignals,
    ) -> tuple[ReasoningStep, UrbanAnalysisSignals]:
        building = outputs.get("building_tool", {})
        ndvi = outputs.get("ndvi_tool", {})
        heatwave = inputs.peer_agent_outputs.get("heatwave_agent")
        score = float(building.get("heat_exposure_score", 0.0))
        if not building:
            score = min(
                inputs.environment.building_density * 0.5
                + inputs.environment.uhi_intensity_c / 10.0 * 0.5,
                1.0,
            )
        if heatwave and heatwave.severity in ("severe", "extreme", "high"):
            score = max(score, 0.7)
        uhi = (
            inputs.environment.uhi_intensity_c >= 3.0
            or bool(ndvi.get("low_vegetation"))
            or (not ndvi and inputs.environment.ndvi < 0.25)
        )
        signals.heat_risk_score = round(score, 3)
        signals.urban_heat_island = uhi
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Heat risk score={score:.2f}, UHI={'detected' if uhi else 'moderate'}",
            confidence=0.8,
        ), signals

    def _analyze_flood_risk(
        self, outputs: dict[str, Any], inputs: UrbanInputs, signals: UrbanAnalysisSignals,
    ) -> tuple[ReasoningStep, UrbanAnalysisSignals]:
        drainage = outputs.get("drainage_tool", {})
        flood = inputs.peer_agent_outputs.get("flood_agent")
        capacity = float(
            drainage.get("capacity_score", inputs.drainage.capacity_score),
        )
        score = 1.0 - capacity
        if flood and flood.severity in ("severe", "extreme", "high"):
            score = max(score, 0.75)
        signals.flood_risk_score = round(min(score, 1.0), 3)
        signals.flood_vulnerability = (
            bool(drainage.get("drainage_deficit"))
            or capacity < 0.45
            or score >= 0.55
        )
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Flood risk score={signals.flood_risk_score:.2f}",
            confidence=0.78,
        ), signals

    def _analyze_water_availability(
        self, outputs: dict[str, Any], inputs: UrbanInputs, signals: UrbanAnalysisSignals,
    ) -> tuple[ReasoningStep, UrbanAnalysisSignals]:
        water = inputs.peer_agent_outputs.get("water_resource_agent")
        forecast = outputs.get("forecast_tool", {})
        score = 0.35
        if water and water.severity in ("severe", "high", "critical"):
            score = 0.75
        if forecast.get("escalating_flood_risk") and inputs.drainage.capacity_score < 0.4:
            score = max(score, 0.5)
        signals.water_stress_score = round(score, 3)
        signals.water_scarcity = score >= 0.6
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Water availability stress score={score:.2f}",
            confidence=0.72,
        ), signals

    def _analyze_green_cover(
        self, outputs: dict[str, Any], inputs: UrbanInputs, signals: UrbanAnalysisSignals,
    ) -> tuple[ReasoningStep, GreenCoverAnalysis, UrbanAnalysisSignals]:
        green = outputs.get("green_cover_tool", {})
        ndvi = outputs.get("ndvi_tool", {})
        current = float(green.get("current_cover_pct", inputs.environment.green_cover_pct))
        target = float(green.get("target_cover_pct", 33.0))
        gap = float(green.get("canopy_gap_pct", max(target - current, 0.0)))
        analysis = GreenCoverAnalysis(
            current_cover_pct=current,
            target_cover_pct=target,
            canopy_gap_pct=gap,
            cooling_potential_score=float(
                green.get("cooling_potential_score", min(gap / 20.0, 1.0)),
            ),
            recommended_interventions=[
                "urban_forest_expansion" if green.get("urban_forest_opportunity", gap >= 8.0) else "",
                "tree_planting" if ndvi.get("tree_planting_priority", inputs.environment.ndvi < 0.25) else "",
            ],
        )
        analysis.recommended_interventions = [r for r in analysis.recommended_interventions if r]
        signals.green_cover_score = round(current / 100.0, 3)
        signals.low_green_cover = bool(green.get("low_green_cover")) or current < 20.0
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Green cover {current:.1f}% vs target {target:.1f}%",
            confidence=0.8,
        ), analysis, signals

    def _analyze_drainage(
        self, outputs: dict[str, Any], inputs: UrbanInputs, signals: UrbanAnalysisSignals,
    ) -> tuple[ReasoningStep, UrbanAnalysisSignals]:
        drainage = outputs.get("drainage_tool", {})
        score = float(drainage.get("capacity_score", inputs.drainage.capacity_score))
        signals.drainage_score = round(score, 3)
        signals.drainage_deficit = bool(drainage.get("drainage_deficit")) or score < 0.45
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Drainage capacity score={score:.2f}, upgrade={'required' if signals.drainage_deficit else 'optional'}",
            confidence=0.77,
        ), signals

    def _analyze_infrastructure(
        self, outputs: dict[str, Any], inputs: UrbanInputs, signals: UrbanAnalysisSignals,
    ) -> tuple[ReasoningStep, UrbanAnalysisSignals]:
        infra = outputs.get("infrastructure_tool", {})
        score = float(infra.get("exposure_score", 0.0))
        if not infra:
            score = min(
                inputs.environment.building_density * 0.3
                + (1.0 - inputs.drainage.capacity_score) * 0.35
                + inputs.environment.uhi_intensity_c / 12.0 * 0.35,
                1.0,
            )
        signals.infrastructure_exposure_score = round(score, 3)
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Infrastructure exposure score={score:.2f}",
            confidence=0.76,
        ), signals

    def _generate_mitigation_options(
        self,
        outputs: dict[str, Any],
        signals: UrbanAnalysisSignals,
        green: GreenCoverAnalysis,
    ) -> tuple[ReasoningStep, list[MitigationOption], UrbanAnalysisSignals]:
        options: list[MitigationOption] = []
        rank = 1
        if signals.urban_heat_island or signals.heat_risk_score >= 0.55:
            options.extend([
                MitigationOption(
                    strategy_type=MitigationStrategyType.HEAT_MITIGATION,
                    title="Cool roof program",
                    description="Coat high-exposure rooftops with reflective cool-roof materials",
                    estimated_cost_crores=25.0,
                    long_term_benefit_score=0.72,
                    payback_years=8.0,
                    priority_rank=rank,
                ),
                MitigationOption(
                    strategy_type=MitigationStrategyType.GREEN_INFRASTRUCTURE,
                    title="Urban tree plantation",
                    description="Expand street and block-level tree canopy in heat corridors",
                    estimated_cost_crores=18.0,
                    long_term_benefit_score=0.78,
                    payback_years=6.0,
                    priority_rank=rank + 1,
                ),
            ])
            rank += 2
        if signals.flood_vulnerability:
            options.append(MitigationOption(
                strategy_type=MitigationStrategyType.FLOOD_MITIGATION,
                title="Stormwater system upgrade",
                description="Expand detention basins and upgrade conveyance in flood-prone zones",
                estimated_cost_crores=55.0,
                long_term_benefit_score=0.82,
                payback_years=12.0,
                priority_rank=rank,
            ))
            rank += 1
            if outputs.get("drainage_tool", {}).get("rain_garden_opportunity"):
                options.append(MitigationOption(
                    strategy_type=MitigationStrategyType.GREEN_INFRASTRUCTURE,
                    title="Rain garden network",
                    description="Deploy distributed rain gardens in micro-catchments",
                    estimated_cost_crores=15.0,
                    long_term_benefit_score=0.7,
                    payback_years=7.0,
                    priority_rank=rank,
                ))
                rank += 1
        if signals.low_green_cover or green.canopy_gap_pct >= 5:
            options.append(MitigationOption(
                strategy_type=MitigationStrategyType.GREEN_INFRASTRUCTURE,
                title="Urban forest expansion",
                description="Establish new urban forest blocks to close canopy gap",
                estimated_cost_crores=30.0,
                long_term_benefit_score=0.75,
                payback_years=9.0,
                priority_rank=rank,
            ))
        if outputs.get("road_tool", {}).get("permeable_pavement_opportunity"):
            options.append(MitigationOption(
                strategy_type=MitigationStrategyType.DRAINAGE_UPGRADE,
                title="Permeable pavement pilot",
                description="Replace impervious road segments with permeable surfaces",
                estimated_cost_crores=22.0,
                long_term_benefit_score=0.68,
                payback_years=10.0,
                priority_rank=rank + 1,
            ))
        if not options:
            options.append(MitigationOption(
                strategy_type=MitigationStrategyType.GREEN_INFRASTRUCTURE,
                title="Baseline green infrastructure",
                description="Maintain and incrementally expand urban green cover",
                estimated_cost_crores=10.0,
                long_term_benefit_score=0.55,
                payback_years=8.0,
                priority_rank=1,
            ))
        return ReasoningStep(
            phase=ReasoningPhase.ACT,
            content=f"Generated {len(options)} mitigation option(s)",
            confidence=0.83,
        ), options, signals

    def _estimate_long_term_benefit(
        self, mitigations: list[MitigationOption], signals: UrbanAnalysisSignals,
    ) -> tuple[ReasoningStep, list[InvestmentPriority], UrbanAnalysisSignals]:
        ranked = sorted(mitigations, key=lambda m: m.long_term_benefit_score, reverse=True)
        investments = [
            InvestmentPriority(
                rank=idx,
                project=m.title,
                domain=m.strategy_type.value,
                estimated_cost_crores=m.estimated_cost_crores,
                benefit_score=m.long_term_benefit_score,
                rationale=m.description,
            )
            for idx, m in enumerate(ranked, start=1)
        ]
        return ReasoningStep(
            phase=ReasoningPhase.ACT,
            content=f"Ranked {len(investments)} investment priorities by long-term benefit",
            confidence=0.8,
        ), investments, signals

    def _generate_recommendations(
        self, signals: UrbanAnalysisSignals, mitigations: list[MitigationOption],
    ) -> ReasoningStep:
        recs: list[str] = []
        if signals.urban_heat_island:
            recs.append("Prioritize cool roofs and urban tree canopy in UHI hotspots")
        if signals.flood_vulnerability:
            recs.append("Upgrade stormwater infrastructure and deploy rain gardens")
        if signals.low_green_cover:
            recs.append("Expand urban forest blocks to close green cover gap")
        if signals.drainage_deficit:
            recs.append("Address drainage capacity deficit before next monsoon cycle")
        if signals.water_scarcity:
            recs.append("Integrate water security measures with land-use planning")
        if not recs:
            recs.append("Maintain incremental climate adaptation investments across all domains")
        top = mitigations[0].title if mitigations else "baseline adaptation"
        recs.insert(0, f"Lead investment: {top}")
        return ReasoningStep(
            phase=ReasoningPhase.VERIFY,
            content="; ".join(recs),
            confidence=0.85,
            metadata={"recommendations": recs},
        )

    def _compute_resilience(self, signals: UrbanAnalysisSignals) -> tuple[float, UrbanResilienceLevel]:
        risk_avg = (
            signals.heat_risk_score
            + signals.flood_risk_score
            + signals.water_stress_score
            + signals.infrastructure_exposure_score
        ) / 4.0
        resilience = max(0.0, min(1.0 - risk_avg * 0.7 + signals.green_cover_score * 0.3, 1.0))
        if resilience >= 0.75:
            level = UrbanResilienceLevel.EXCELLENT
        elif resilience >= 0.6:
            level = UrbanResilienceLevel.GOOD
        elif resilience >= 0.45:
            level = UrbanResilienceLevel.MODERATE
        elif resilience >= 0.3:
            level = UrbanResilienceLevel.LOW
        else:
            level = UrbanResilienceLevel.CRITICAL
        return round(resilience, 3), level


class UrbanDecisionEngine:
    """Builds standardized DecisionRequest for urban climate adaptation."""

    def __init__(self, *, agent_id: str = URBAN_PLANNING_AGENT_ID) -> None:
        self._agent_id = agent_id
        self._decision_manager = DecisionManager()

    async def evaluate(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        reflection: ReflectionResult | None = None,
    ) -> DecisionRequest:
        inputs = self._resolve_inputs(context)
        signals = reasoning.metadata.get("urban_signals", {})
        resilience = float(signals.get("resilience_score", 0.5))

        need_rl = (
            (reflection.needs_rl if reflection else False)
            or resilience < 0.5
            or len(reasoning.metadata.get("mitigation_options", [])) >= 3
        )
        need_human = resilience < 0.3
        suggested = list(reflection.suggested_agents) if reflection else []

        decision = self._decision_manager.create(
            agent_id=self._agent_id,
            decision_type=DecisionType.URBAN,
            objectives=self._build_objectives(),
            possible_actions=self._build_actions(signals),
            constraints=self._build_constraints(inputs),
            context=DecisionContext(
                scenario=ScenarioContext(
                    scenario_id=inputs.region_id or context.request_id,
                    name=f"urban_planning_{inputs.region_id or 'adaptation'}",
                    region_id=inputs.region_id,
                    horizon_hours=inputs.planning_horizon_years * 365 * 24,
                ),
                climate_state=context.climate_state,
            ),
            risk=RiskAssessment(
                level=self._map_risk_level(resilience),
                score=1.0 - resilience,
                factors=[
                    f"heat_{signals.get('heat_risk_score', 0):.2f}",
                    f"flood_{signals.get('flood_risk_score', 0):.2f}",
                ],
                affected_regions=inputs.districts,
                affected_population=self._estimate_population(inputs),
                horizon_hours=inputs.planning_horizon_years * 365 * 24,
            ),
            priority=self._map_priority(resilience),
            confidence=reasoning.overall_confidence,
            need_simulation=bool(signals.get("flood_vulnerability") and signals.get("urban_heat_island")),
            need_other_agents=suggested,
            need_human=need_human,
            need_rl=need_rl,
            rationale=self._build_rationale(signals, resilience),
            metadata={
                "resilience_score": resilience,
                "resilience_level": signals.get("resilience_level", UrbanResilienceLevel.MODERATE.value),
            },
            validate=True,
        )
        logger.debug("urban_decision_evaluated", decision_id=decision.decision_id, need_rl=need_rl)
        return decision

    def _resolve_inputs(self, context: AgentContext) -> UrbanInputs:
        stored = context.metadata.get("urban_inputs")
        if isinstance(stored, UrbanInputs):
            return stored
        return UrbanInputs.from_request_context(context.request.context)

    def _map_risk_level(self, resilience: float) -> RiskLevel:
        if resilience < 0.3:
            return RiskLevel.CRITICAL
        if resilience < 0.45:
            return RiskLevel.SEVERE
        if resilience < 0.6:
            return RiskLevel.HIGH
        if resilience < 0.75:
            return RiskLevel.MODERATE
        return RiskLevel.LOW

    def _map_priority(self, resilience: float) -> DecisionPriority:
        if resilience < 0.3:
            return DecisionPriority.CRITICAL
        if resilience < 0.45:
            return DecisionPriority.URGENT
        if resilience < 0.6:
            return DecisionPriority.HIGH
        return DecisionPriority.NORMAL

    def _build_actions(self, signals: dict[str, Any]) -> list[DecisionAction]:
        action_types: list[UrbanActionType] = []
        if signals.get("low_green_cover") or signals.get("urban_heat_island"):
            action_types.extend([
                UrbanActionType.PLANT_TREES,
                UrbanActionType.URBAN_FOREST_EXPANSION,
            ])
        if signals.get("urban_heat_island") or float(signals.get("heat_risk_score", 0)) >= 0.55:
            action_types.extend([UrbanActionType.COOL_ROOFS, UrbanActionType.GREEN_ROOFS])
        if signals.get("flood_vulnerability"):
            action_types.extend([
                UrbanActionType.STORMWATER_UPGRADES,
                UrbanActionType.RAIN_GARDENS,
                UrbanActionType.PERMEABLE_PAVEMENT,
            ])
        if float(signals.get("infrastructure_exposure_score", 0)) >= 0.55:
            action_types.append(UrbanActionType.BUILDING_RETROFITS)
        if signals.get("water_scarcity") or float(signals.get("flood_risk_score", 0)) >= 0.5:
            action_types.append(UrbanActionType.LAND_USE_CHANGES)

        if not action_types:
            action_types.append(UrbanActionType.PLANT_TREES)

        risk_map = {
            "negligible": RiskLevel.NEGLIGIBLE, "low": RiskLevel.LOW,
            "moderate": RiskLevel.MODERATE, "high": RiskLevel.HIGH,
        }
        seen: set[UrbanActionType] = set()
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
            Objective(objective_id="maximize_resilience", description="Maximize long-term urban resilience", weight=0.35),
            Objective(objective_id="reduce_heat_exposure", description="Reduce urban heat island exposure", weight=0.25),
            Objective(objective_id="reduce_flood_risk", description="Reduce pluvial and fluvial flood risk", weight=0.20),
            Objective(objective_id="optimize_budget", description="Optimize adaptation budget allocation", weight=0.20),
        ]

    def _build_constraints(self, inputs: UrbanInputs) -> DecisionConstraints:
        return DecisionConstraints(
            budget=BudgetConstraint(max_cost=inputs.adaptation_budget_crores),
            time=TimeConstraint(max_hours=float(inputs.planning_horizon_years * 365 * 24)),
            population=PopulationConstraint(max_affected_population=10_000_000),
            safety=SafetyConstraint(max_risk_score=0.85),
        )

    def _build_rationale(self, signals: dict[str, Any], resilience: float) -> list[str]:
        rationale = [f"Urban resilience score: {resilience:.2f}"]
        if signals.get("urban_heat_island"):
            rationale.append("Urban heat island mitigation required")
        if signals.get("flood_vulnerability"):
            rationale.append("Flood vulnerability drives stormwater investments")
        if signals.get("low_green_cover"):
            rationale.append("Green cover gap warrants forest expansion")
        return rationale

    def _estimate_population(self, inputs: UrbanInputs) -> int:
        density = inputs.environment.population_density or 8000.0
        return int(density * 25 * max(len(inputs.districts), 1))
