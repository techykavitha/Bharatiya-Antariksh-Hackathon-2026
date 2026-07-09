"""Disaster response reasoning and decision pipeline."""

from __future__ import annotations

import time
from typing import Any

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningPhase, ReasoningResult, ReasoningStep
from backend.agents.specialized.agent_reflection import ReflectionResult
from backend.agents.specialized.disaster_response.disaster_context import (
    DisasterAnalysisSignals,
    DisasterInputs,
    EvacuationStrategy,
    HazardAgentOutput,
    MedicalSupportPlan,
    PriorityRanking,
    RecoveryPriority,
    ResourceRequirement,
)
from backend.agents.specialized.disaster_response.disaster_models import (
    ACTION_CATALOG,
    DISASTER_RESPONSE_AGENT_ID,
    DisasterActionType,
    EmergencyPriority,
    HazardType,
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

SEVERITY_SCORES: dict[str, float] = {
    "none": 0.05, "low": 0.25, "moderate": 0.45, "high": 0.65,
    "severe": 0.8, "extreme": 0.9, "critical": 0.95, "catastrophic": 1.0,
}


class DisasterReasoningEngine:
    """Multi-hazard disaster response reasoning pipeline."""

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id

    async def run(
        self,
        context: AgentContext,
        tool_results: list[ToolResult] | None = None,
    ) -> tuple[ReasoningResult, DisasterAnalysisSignals]:
        start = time.perf_counter()
        steps: list[ReasoningStep] = []
        signals = DisasterAnalysisSignals()
        inputs = self._resolve_inputs(context)
        outputs = self._index_tool_outputs(tool_results or [])

        steps.append(self._observe(context, inputs))
        collect_step, hazards, signals = self._collect_hazard_outputs(inputs, signals)
        steps.append(collect_step)
        priority_step, rankings, signals = self._prioritize_hazards(hazards, signals)
        steps.append(priority_step)
        pop_step, signals = self._estimate_population(outputs, signals)
        steps.append(pop_step)
        infra_step, signals = self._assess_infrastructure(outputs, signals)
        steps.append(infra_step)
        resource_step, resources, signals = self._estimate_resources(outputs, signals)
        steps.append(resource_step)
        strategy_step, evacuation, medical, signals = self._generate_response_strategy(outputs, signals)
        steps.append(strategy_step)
        recovery_step, recovery, signals = self._generate_recovery_priorities(rankings, signals)
        steps.append(recovery_step)

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
                "disaster_signals": signals.model_dump(),
                "priority_rankings": [r.model_dump() for r in rankings],
                "resource_requirements": [r.model_dump() for r in resources],
                "evacuation_strategy": evacuation.model_dump(),
                "medical_support": medical.model_dump(),
                "recovery_priorities": [r.model_dump() for r in recovery],
                "hazard_count": len(hazards),
                "duration_ms": elapsed,
            },
        )
        return result, signals

    def _resolve_inputs(self, context: AgentContext) -> DisasterInputs:
        stored = context.metadata.get("disaster_inputs")
        if isinstance(stored, DisasterInputs):
            return stored
        return DisasterInputs.from_request_context(context.request.context)

    def _index_tool_outputs(self, results: list[ToolResult]) -> dict[str, Any]:
        return {r.tool_name: r.output for r in results if r.success and r.output}

    def _observe(self, context: AgentContext, inputs: DisasterInputs) -> ReasoningStep:
        return ReasoningStep(
            phase=ReasoningPhase.OBSERVE,
            content=f"Observing multi-hazard emergency in {inputs.region_id or 'region'}",
            confidence=0.9,
        )

    def _collect_hazard_outputs(
        self, inputs: DisasterInputs, signals: DisasterAnalysisSignals,
    ) -> tuple[ReasoningStep, list[HazardAgentOutput], DisasterAnalysisSignals]:
        hazards = list(inputs.hazard_agent_outputs.values())
        signals.active_hazard_count = len(hazards)
        signals.compound_disaster = len(hazards) >= 2
        agents = ", ".join(h.agent_id for h in hazards) or "none"
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Collected outputs from {len(hazards)} hazard agent(s): {agents}",
            confidence=0.85 if hazards else 0.4,
        ), hazards, signals

    def _prioritize_hazards(
        self, hazards: list[HazardAgentOutput], signals: DisasterAnalysisSignals,
    ) -> tuple[ReasoningStep, list[PriorityRanking], DisasterAnalysisSignals]:
        rankings: list[PriorityRanking] = []
        for idx, h in enumerate(
            sorted(hazards, key=lambda x: SEVERITY_SCORES.get(x.severity.lower(), 0.3), reverse=True),
            start=1,
        ):
            score = SEVERITY_SCORES.get(h.severity.lower(), 0.3) * h.confidence
            ep = self._score_to_priority(score)
            rankings.append(PriorityRanking(
                rank=idx,
                hazard_type=h.hazard_type,
                agent_id=h.agent_id,
                priority_score=round(score, 3),
                emergency_priority=ep,
                rationale=f"{h.hazard_type.value} severity {h.severity}",
            ))
        top_score = rankings[0].priority_score if rankings else 0.0
        signals.composite_priority_score = round(top_score, 3)
        content = (
            f"Top priority: {rankings[0].hazard_type.value} ({rankings[0].emergency_priority.value})"
            if rankings else "No active hazards — preparedness mode"
        )
        return ReasoningStep(phase=ReasoningPhase.THINK, content=content, confidence=0.8), rankings, signals

    def _estimate_population(
        self, outputs: dict[str, Any], signals: DisasterAnalysisSignals,
    ) -> tuple[ReasoningStep, DisasterAnalysisSignals]:
        pop_out = outputs.get("population_tool", {})
        total = int(pop_out.get("total_affected_population", 0))
        signals.high_population_impact = bool(pop_out.get("high_impact", total >= 500_000))
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Affected population estimate: {total:,}",
            confidence=0.75,
        ), signals

    def _assess_infrastructure(
        self, outputs: dict[str, Any], signals: DisasterAnalysisSignals,
    ) -> tuple[ReasoningStep, DisasterAnalysisSignals]:
        infra_out = outputs.get("critical_infrastructure_tool", {})
        signals.infrastructure_critical = bool(infra_out.get("protection_required", False))
        count = infra_out.get("critical_count", 0)
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Critical infrastructure assets flagged: {count}",
            confidence=0.73,
        ), signals

    def _estimate_resources(
        self, outputs: dict[str, Any], signals: DisasterAnalysisSignals,
    ) -> tuple[ReasoningStep, list[ResourceRequirement], DisasterAnalysisSignals]:
        res_out = outputs.get("emergency_resource_tool", {})
        relief_out = outputs.get("relief_inventory_tool", {})
        signals.resource_gap = bool(res_out.get("resource_gap") or relief_out.get("inventory_shortfall"))
        resources = [
            ResourceRequirement(resource_type="food_packets", quantity=int(res_out.get("food_packets", 0)), unit="packets"),
            ResourceRequirement(resource_type="water", quantity=int(res_out.get("water_litres", 0)), unit="litres"),
            ResourceRequirement(resource_type="shelter_tents", quantity=int(res_out.get("shelter_tents", 0)), unit="tents"),
        ]
        return ReasoningStep(
            phase=ReasoningPhase.ACT,
            content=f"Resource requirements estimated; gap={signals.resource_gap}",
            confidence=0.78,
        ), resources, signals

    def _generate_response_strategy(
        self, outputs: dict[str, Any], signals: DisasterAnalysisSignals,
    ) -> tuple[ReasoningStep, EvacuationStrategy, MedicalSupportPlan, DisasterAnalysisSignals]:
        shelter_out = outputs.get("shelter_tool", {})
        road_out = outputs.get("road_network_tool", {})
        hosp_out = outputs.get("hospital_tool", {})
        pop_out = outputs.get("population_tool", {})

        evacuation = EvacuationStrategy(
            required=bool(shelter_out.get("activation_required") or road_out.get("road_closure_required")),
            zones=pop_out.get("districts", []),
            estimated_population=int(pop_out.get("total_affected_population", 0)),
            priority_corridors=road_out.get("evacuation_corridors", []),
            shelter_assignments=[s.get("shelter_id", "") for s in shelter_out.get("shelters", []) if isinstance(s, dict)],
            timeline_hours=24.0 if signals.compound_disaster else 48.0,
        )
        medical = MedicalSupportPlan(
            hospitals_activated=len(hosp_out.get("hospitals", [])),
            ambulances_required=int(hosp_out.get("ambulances_required", 0)),
            trauma_capacity_pct=float(hosp_out.get("trauma_capacity_pct", 0.0)),
            notes=["Activate trauma protocols"] if hosp_out.get("medical_surge_required") else [],
        )
        signals.evacuation_required = evacuation.required
        signals.medical_surge_required = bool(hosp_out.get("medical_surge_required"))

        recs: list[str] = []
        if evacuation.required:
            recs.append("Execute phased evacuation via priority corridors")
        if signals.resource_gap:
            recs.append("Deploy emergency relief inventory and request additional supplies")
        if signals.medical_surge_required:
            recs.append("Activate medical surge capacity and field hospitals")
        if not recs:
            recs.append("Maintain readiness and monitor hazard agent updates")

        return ReasoningStep(
            phase=ReasoningPhase.ACT,
            content="; ".join(recs),
            confidence=0.82,
            metadata={"recommendations": recs},
        ), evacuation, medical, signals

    def _generate_recovery_priorities(
        self, rankings: list[PriorityRanking], signals: DisasterAnalysisSignals,
    ) -> tuple[ReasoningStep, list[RecoveryPriority], DisasterAnalysisSignals]:
        recovery: list[RecoveryPriority] = [
            RecoveryPriority(priority=1, domain="lifelines", description="Restore power and water supply", horizon_days=7),
            RecoveryPriority(priority=2, domain="transport", description="Clear blocked roads and restore connectivity", horizon_days=14),
        ]
        if rankings and rankings[0].hazard_type == HazardType.FLOOD:
            recovery.append(RecoveryPriority(priority=3, domain="housing", description="Assess flood damage and temporary housing", horizon_days=30))
        elif rankings and rankings[0].hazard_type == HazardType.CYCLONE:
            recovery.append(RecoveryPriority(priority=3, domain="coastal", description="Coastal infrastructure rehabilitation", horizon_days=60))
        else:
            recovery.append(RecoveryPriority(priority=3, domain="community", description="Community recovery and livelihood support", horizon_days=45))
        return ReasoningStep(
            phase=ReasoningPhase.VERIFY,
            content=f"Recovery plan: {len(recovery)} priority domains identified",
            confidence=0.7,
        ), recovery, signals

    def _score_to_priority(self, score: float) -> EmergencyPriority:
        if score >= 0.85:
            return EmergencyPriority.CATASTROPHIC
        if score >= 0.7:
            return EmergencyPriority.SEVERE
        if score >= 0.5:
            return EmergencyPriority.HIGH
        if score >= 0.3:
            return EmergencyPriority.ELEVATED
        return EmergencyPriority.ROUTINE


class DisasterDecisionEngine:
    """Builds standardized DecisionRequest for disaster response."""

    def __init__(self, *, agent_id: str = DISASTER_RESPONSE_AGENT_ID) -> None:
        self._agent_id = agent_id
        self._decision_manager = DecisionManager()

    async def evaluate(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        reflection: ReflectionResult | None = None,
    ) -> DecisionRequest:
        inputs = self._resolve_inputs(context)
        signals = reasoning.metadata.get("disaster_signals", {})
        composite = float(signals.get("composite_priority_score", 0.0))
        emergency = self._composite_to_emergency(composite, signals)

        need_rl = (
            signals.get("compound_disaster", False)
            or signals.get("resource_gap", False)
            or emergency in (EmergencyPriority.SEVERE, EmergencyPriority.CATASTROPHIC)
        )
        need_human = emergency == EmergencyPriority.CATASTROPHIC
        suggested = list(reflection.suggested_agents) if reflection else []

        decision = self._decision_manager.create(
            agent_id=self._agent_id,
            decision_type=DecisionType.DISASTER,
            objectives=self._build_objectives(emergency),
            possible_actions=self._build_actions(signals, emergency),
            constraints=self._build_constraints(inputs, emergency),
            context=DecisionContext(
                scenario=ScenarioContext(
                    scenario_id=inputs.region_id or context.request_id,
                    name=f"disaster_response_{inputs.region_id or 'coordination'}",
                    region_id=inputs.region_id,
                    horizon_hours=72,
                ),
                climate_state=context.climate_state,
            ),
            risk=RiskAssessment(
                level=self._map_risk_level(emergency),
                score=composite,
                factors=[f"emergency_{emergency.value}", f"hazards_{signals.get('active_hazard_count', 0)}"],
                affected_regions=inputs.districts,
                affected_population=self._estimate_population(inputs),
                horizon_hours=72,
            ),
            priority=self._map_decision_priority(emergency),
            confidence=reasoning.overall_confidence,
            need_simulation=signals.get("compound_disaster", False),
            need_other_agents=suggested,
            need_human=need_human,
            need_rl=need_rl,
            rationale=self._build_rationale(signals, emergency),
            metadata={"emergency_priority": emergency.value, "composite_score": composite},
            validate=True,
        )
        logger.debug("disaster_decision_evaluated", decision_id=decision.decision_id, need_rl=need_rl)
        return decision

    def _resolve_inputs(self, context: AgentContext) -> DisasterInputs:
        stored = context.metadata.get("disaster_inputs")
        if isinstance(stored, DisasterInputs):
            return stored
        return DisasterInputs.from_request_context(context.request.context)

    def _composite_to_emergency(self, composite: float, signals: dict[str, Any]) -> EmergencyPriority:
        if signals.get("compound_disaster") and composite >= 0.6:
            return EmergencyPriority.CATASTROPHIC
        if composite >= 0.8:
            return EmergencyPriority.SEVERE
        if composite >= 0.6:
            return EmergencyPriority.HIGH
        if composite >= 0.4:
            return EmergencyPriority.ELEVATED
        return EmergencyPriority.ROUTINE

    def _map_risk_level(self, emergency: EmergencyPriority) -> RiskLevel:
        mapping = {
            EmergencyPriority.CATASTROPHIC: RiskLevel.CRITICAL,
            EmergencyPriority.SEVERE: RiskLevel.SEVERE,
            EmergencyPriority.HIGH: RiskLevel.HIGH,
            EmergencyPriority.ELEVATED: RiskLevel.MODERATE,
            EmergencyPriority.ROUTINE: RiskLevel.LOW,
        }
        return mapping.get(emergency, RiskLevel.MODERATE)

    def _map_decision_priority(self, emergency: EmergencyPriority) -> DecisionPriority:
        mapping = {
            EmergencyPriority.CATASTROPHIC: DecisionPriority.CRITICAL,
            EmergencyPriority.SEVERE: DecisionPriority.URGENT,
            EmergencyPriority.HIGH: DecisionPriority.HIGH,
            EmergencyPriority.ELEVATED: DecisionPriority.NORMAL,
            EmergencyPriority.ROUTINE: DecisionPriority.LOW,
        }
        return mapping.get(emergency, DecisionPriority.NORMAL)

    def _build_actions(self, signals: dict[str, Any], emergency: EmergencyPriority) -> list[DecisionAction]:
        action_types: list[DisasterActionType] = [DisasterActionType.EMERGENCY_COMMUNICATION]
        if emergency in (EmergencyPriority.ELEVATED, EmergencyPriority.HIGH, EmergencyPriority.SEVERE, EmergencyPriority.CATASTROPHIC):
            action_types.append(DisasterActionType.EMERGENCY_RESOURCE_DEPLOYMENT)
        if signals.get("evacuation_required"):
            action_types.append(DisasterActionType.EVACUATION)
        if signals.get("medical_surge_required"):
            action_types.append(DisasterActionType.MEDICAL_RESPONSE)
        if emergency in (EmergencyPriority.HIGH, EmergencyPriority.SEVERE, EmergencyPriority.CATASTROPHIC):
            action_types.extend([
                DisasterActionType.SHELTER_ACTIVATION,
                DisasterActionType.INFRASTRUCTURE_PROTECTION,
            ])
        if signals.get("infrastructure_critical"):
            action_types.append(DisasterActionType.ROAD_CLOSURE)
        if emergency in (EmergencyPriority.SEVERE, EmergencyPriority.CATASTROPHIC):
            action_types.append(DisasterActionType.SEARCH_AND_RESCUE)

        risk_map = {
            "negligible": RiskLevel.NEGLIGIBLE, "low": RiskLevel.LOW,
            "moderate": RiskLevel.MODERATE, "high": RiskLevel.HIGH,
        }
        seen: set[DisasterActionType] = set()
        actions: list[DecisionAction] = []
        for at in action_types:
            if at in seen:
                continue
            seen.add(at)
            desc, cost, benefit, risk_str = ACTION_CATALOG[at]
            risk = risk_map.get(risk_str, RiskLevel.MODERATE)
            actions.append(DecisionAction(
                description=desc, cost=cost, expected_benefit=benefit, risk=risk,
                risk_score={"negligible": 0.1, "low": 0.25, "moderate": 0.5, "high": 0.75}.get(risk_str, 0.4),
                category=at.value,
            ))
        return actions

    def _build_objectives(self, emergency: EmergencyPriority) -> list[Objective]:
        return [
            Objective(objective_id="save_lives", description="Minimize loss of life", weight=0.40),
            Objective(objective_id="protect_vulnerable", description="Protect vulnerable populations", weight=0.25),
            Objective(objective_id="maintain_lifelines", description="Maintain critical lifelines", weight=0.20),
            Objective(
                objective_id="optimize_resources", description="Optimize resource allocation",
                weight=0.15, maximize=emergency != EmergencyPriority.CATASTROPHIC,
            ),
        ]

    def _build_constraints(self, inputs: DisasterInputs, emergency: EmergencyPriority) -> DecisionConstraints:
        max_cost = 500.0 if emergency == EmergencyPriority.CATASTROPHIC else 200.0
        return DecisionConstraints(
            budget=BudgetConstraint(max_cost=max_cost),
            time=TimeConstraint(max_hours=72.0),
            population=PopulationConstraint(max_affected_population=5_000_000),
            safety=SafetyConstraint(max_risk_score=0.9),
        )

    def _build_rationale(self, signals: dict[str, Any], emergency: EmergencyPriority) -> list[str]:
        rationale = [f"Emergency priority: {emergency.value}"]
        if signals.get("compound_disaster"):
            rationale.append("Compound multi-hazard disaster requires coordinated response")
        if signals.get("resource_gap"):
            rationale.append("Relief inventory shortfall — RL optimization recommended")
        if signals.get("evacuation_required"):
            rationale.append("Evacuation strategy activated")
        return rationale

    def _estimate_population(self, inputs: DisasterInputs) -> int:
        return sum(h.affected_population for h in inputs.hazard_agent_outputs.values()) or 100_000
