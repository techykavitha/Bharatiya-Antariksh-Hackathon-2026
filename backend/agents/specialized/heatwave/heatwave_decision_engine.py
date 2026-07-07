"""Heatwave decision engine — produces unified DecisionRequest objects."""

from __future__ import annotations

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.specialized.agent_reflection import ReflectionResult
from backend.agents.specialized.heatwave.heatwave_context import HeatIndexEstimate, HeatwaveInputs
from backend.agents.specialized.heatwave.heatwave_models import (
    AGENT_AIR_QUALITY,
    AGENT_DISASTER,
    AGENT_FLOOD,
    AGENT_URBAN_PLANNING,
    AGENT_WATER_RESOURCE,
    HEATWAVE_AGENT_ID,
    HeatActionType,
    HeatwaveSeverity,
)
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
from backend.decision.decision_priority import DecisionPriority, priority_from_label
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_types import DecisionType, Objective, RiskAssessment, RiskLevel
from backend.config.logger import get_logger

logger = get_logger(__name__)

ACTION_CATALOG: dict[HeatActionType, tuple[str, float, float, RiskLevel]] = {
    HeatActionType.URBAN_COOLING: ("Deploy urban cooling infrastructure", 25.0, 70.0, RiskLevel.LOW),
    HeatActionType.COOLING_CENTERS: ("Open public cooling centers", 15.0, 80.0, RiskLevel.LOW),
    HeatActionType.WATER_DISTRIBUTION: ("Distribute drinking water to vulnerable areas", 20.0, 75.0, RiskLevel.LOW),
    HeatActionType.TREE_PLANTATION: ("Accelerate urban tree plantation program", 30.0, 55.0, RiskLevel.LOW),
    HeatActionType.SCHOOL_CLOSURE: ("Close schools during peak heat hours", 5.0, 60.0, RiskLevel.MODERATE),
    HeatActionType.WORK_HOUR_MODIFICATION: ("Modify outdoor work hours", 8.0, 65.0, RiskLevel.LOW),
    HeatActionType.PUBLIC_ALERTS: ("Issue public heat health alerts", 3.0, 50.0, RiskLevel.NEGLIGIBLE),
    HeatActionType.EMERGENCY_RESPONSE: ("Activate emergency heat response protocol", 100.0, 95.0, RiskLevel.HIGH),
}


class HeatwaveDecisionEngine:
    """
    Builds standardized ``DecisionRequest`` objects via the Decision Framework.

    Does NOT use a custom decision schema.
    """

    def __init__(self, *, agent_id: str = HEATWAVE_AGENT_ID) -> None:
        self._agent_id = agent_id
        self._decision_manager = DecisionManager()

    @property
    def decision_manager(self) -> DecisionManager:
        return self._decision_manager

    async def evaluate(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        reflection: ReflectionResult,
    ) -> DecisionRequest:
        inputs = self._resolve_inputs(context)
        signals = reasoning.metadata.get("heat_signals", {})
        severity = HeatwaveSeverity(reasoning.metadata.get("severity", HeatwaveSeverity.NONE.value))
        composite = float(signals.get("composite_score", 0.0))
        heat_index = self._resolve_heat_index(reasoning)

        need_rl = reflection.needs_rl or (
            severity in (HeatwaveSeverity.SEVERE, HeatwaveSeverity.EXTREME)
            and composite >= 0.65
        )
        need_simulation = reflection.needs_simulation
        need_human = severity == HeatwaveSeverity.EXTREME or heat_index.dangerous

        suggested_agents = list(reflection.suggested_agents)
        rationale = self._build_rationale(signals, severity, reflection)

        priority = self._resolve_priority(severity, heat_index)
        risk_level = self._map_risk_level(severity, composite)
        actions = self._build_actions(severity, signals)
        objectives = self._build_objectives(severity)
        constraints = self._build_constraints(inputs, severity)

        decision_context = DecisionContext(
            scenario=ScenarioContext(
                scenario_id=inputs.region_id or context.request_id,
                name=f"heatwave_{inputs.region_id or 'analysis'}",
                region_id=inputs.region_id,
                horizon_hours=int(reasoning.metadata.get("duration_days", 3)) * 24,
            ),
            climate_state=context.climate_state,
            forecast_reference=(
                context.climate_state.forecast_references[0]
                if context.climate_state and context.climate_state.forecast_references
                else None
            ),
        )

        decision = self._decision_manager.create(
            agent_id=self._agent_id,
            decision_type=DecisionType.HEATWAVE,
            objectives=objectives,
            possible_actions=actions,
            constraints=constraints,
            context=decision_context,
            risk=RiskAssessment(
                level=risk_level,
                score=composite,
                factors=[f"severity_{severity.value}"],
                affected_regions=inputs.districts,
                affected_population=self._estimate_population(inputs),
                horizon_hours=int(reasoning.metadata.get("duration_days", 3)) * 24,
            ),
            priority=priority,
            confidence=reasoning.overall_confidence,
            need_simulation=need_simulation,
            need_other_agents=suggested_agents,
            need_human=need_human,
            need_rl=need_rl,
            rationale=rationale,
            metadata={
                "severity": severity.value,
                "composite_score": composite,
                "heat_index_c": heat_index.heat_index_c,
                "wet_bulb_c": heat_index.wet_bulb_c,
                "uhi_score": signals.get("uhi_score", 0.0),
            },
            validate=True,
        )

        logger.debug(
            "heatwave_decision_evaluated",
            agent_id=self._agent_id,
            decision_id=decision.decision_id,
            need_rl=need_rl,
            action_count=len(actions),
        )
        return decision

    def _resolve_inputs(self, context: AgentContext) -> HeatwaveInputs:
        stored = context.metadata.get("heatwave_inputs")
        if isinstance(stored, HeatwaveInputs):
            return stored
        return HeatwaveInputs.from_request_context(context.request.context)

    def _resolve_heat_index(self, reasoning: ReasoningResult) -> HeatIndexEstimate:
        raw = reasoning.metadata.get("heat_index")
        if isinstance(raw, dict):
            return HeatIndexEstimate.model_validate(raw)
        return HeatIndexEstimate()

    def _build_rationale(self, signals: dict, severity: HeatwaveSeverity, reflection: ReflectionResult) -> list[str]:
        rationale: list[str] = [f"Heatwave severity: {severity.value}"]
        if signals.get("urban_heat_island"):
            rationale.append("Urban heat island detected")
        if signals.get("compound_aqi_risk"):
            rationale.append("Compound heat-AQI risk identified")
        if reflection.needs_rl:
            rationale.append("RL optimization recommended for mitigation portfolio")
        rationale.extend(reflection.notes[:3])
        return rationale

    def _resolve_priority(self, severity: HeatwaveSeverity, heat_index: HeatIndexEstimate) -> DecisionPriority:
        if severity == HeatwaveSeverity.EXTREME or heat_index.dangerous:
            return DecisionPriority.CRITICAL
        if severity == HeatwaveSeverity.SEVERE:
            return DecisionPriority.URGENT
        if severity == HeatwaveSeverity.HIGH:
            return DecisionPriority.HIGH
        if severity == HeatwaveSeverity.MODERATE:
            return DecisionPriority.NORMAL
        return DecisionPriority.LOW

    def _map_risk_level(self, severity: HeatwaveSeverity, composite: float) -> RiskLevel:
        if severity == HeatwaveSeverity.EXTREME or composite >= 0.85:
            return RiskLevel.CRITICAL
        if severity == HeatwaveSeverity.SEVERE or composite >= 0.7:
            return RiskLevel.SEVERE
        if severity == HeatwaveSeverity.HIGH or composite >= 0.55:
            return RiskLevel.HIGH
        if composite >= 0.35:
            return RiskLevel.MODERATE
        if composite >= 0.15:
            return RiskLevel.LOW
        return RiskLevel.NEGLIGIBLE

    def _build_actions(self, severity: HeatwaveSeverity, signals: dict) -> list[DecisionAction]:
        actions: list[DecisionAction] = []
        always = [HeatActionType.PUBLIC_ALERTS]
        if severity in (HeatwaveSeverity.MODERATE, HeatwaveSeverity.HIGH, HeatwaveSeverity.SEVERE, HeatwaveSeverity.EXTREME):
            always.extend([HeatActionType.COOLING_CENTERS, HeatActionType.WATER_DISTRIBUTION])
        if severity in (HeatwaveSeverity.HIGH, HeatwaveSeverity.SEVERE, HeatwaveSeverity.EXTREME):
            always.extend([HeatActionType.WORK_HOUR_MODIFICATION, HeatActionType.SCHOOL_CLOSURE])
        if signals.get("urban_heat_island"):
            always.append(HeatActionType.URBAN_COOLING)
        if signals.get("low_vegetation"):
            always.append(HeatActionType.TREE_PLANTATION)
        if severity in (HeatwaveSeverity.SEVERE, HeatwaveSeverity.EXTREME):
            always.append(HeatActionType.EMERGENCY_RESPONSE)

        seen: set[HeatActionType] = set()
        for action_type in always:
            if action_type in seen:
                continue
            seen.add(action_type)
            desc, cost, benefit, risk = ACTION_CATALOG[action_type]
            actions.append(DecisionAction(
                description=desc,
                cost=cost,
                expected_benefit=benefit,
                risk=risk,
                risk_score={"negligible": 0.1, "low": 0.25, "moderate": 0.5, "high": 0.75, "severe": 0.9, "critical": 1.0}.get(risk.value, 0.4),
                category=action_type.value,
                affected_regions=[],
            ))
        return actions

    def _build_objectives(self, severity: HeatwaveSeverity) -> list[Objective]:
        objs = [
            Objective(objective_id="minimize_heat_mortality", description="Minimize heat-related mortality", weight=0.35),
            Objective(objective_id="protect_vulnerable", description="Protect vulnerable populations", weight=0.30),
            Objective(objective_id="reduce_thermal_stress", description="Reduce urban thermal stress", weight=0.20),
        ]
        if severity in (HeatwaveSeverity.SEVERE, HeatwaveSeverity.EXTREME):
            objs.append(Objective(objective_id="maintain_critical_infra", description="Maintain critical infrastructure", weight=0.15))
        else:
            objs.append(Objective(objective_id="minimize_cost", description="Minimize response cost", weight=0.15, maximize=False))
        return objs

    def _build_constraints(self, inputs: HeatwaveInputs, severity: HeatwaveSeverity) -> DecisionConstraints:
        max_cost = 200.0 if severity in (HeatwaveSeverity.SEVERE, HeatwaveSeverity.EXTREME) else 80.0
        return DecisionConstraints(
            budget=BudgetConstraint(max_cost=max_cost),
            time=TimeConstraint(max_hours=72.0 if severity == HeatwaveSeverity.EXTREME else 48.0),
            population=PopulationConstraint(max_affected_population=500_000),
            safety=SafetyConstraint(max_risk_score=0.85),
        )

    def _estimate_population(self, inputs: HeatwaveInputs) -> int:
        density = inputs.urban.population_density or 5000.0
        return int(density * 10 * max(len(inputs.districts), 1))
