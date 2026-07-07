"""Water resource decision engine — determines downstream agent and system needs."""

from __future__ import annotations

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.specialized.agent_reflection import ReflectionResult
from backend.agents.specialized.water_resource.water_context import DecisionRequest, WaterInputs
from backend.agents.specialized.water_resource.water_models import (
    AGENT_AGRICULTURE,
    AGENT_DISASTER,
    AGENT_FLOOD,
    AGENT_URBAN_PLANNING,
    WaterStressLevel,
)
from backend.config.logger import get_logger

logger = get_logger(__name__)


class WaterDecisionEngine:
    """
    Rule-based decision layer (not RL) that determines whether to invoke
    other agents, simulations, forecast updates, or RL policy requests.
    """

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id

    async def evaluate(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        reflection: ReflectionResult,
    ) -> DecisionRequest:
        inputs = self._resolve_inputs(context)
        signals = reasoning.metadata.get("water_signals", {})
        stress = WaterStressLevel(reasoning.metadata.get("stress_level", WaterStressLevel.NONE.value))
        availability_score = float(signals.get("availability_score", 0.5))
        stress_score = float(signals.get("stress_score", 0.0))
        uncertainty = float(signals.get("uncertainty", 0.5))

        rationale: list[str] = []
        suggested: list[str] = []

        need_rl = (
            stress in (WaterStressLevel.SEVERE, WaterStressLevel.CRITICAL)
            and stress_score >= 0.6
            and uncertainty < 0.5
            and availability_score < 0.5
        )
        if need_rl:
            rationale.append("Complex multi-basin allocation warrants RL optimization")

        need_flood = bool(signals.get("overflow_risk")) or (
            inputs.reservoir.level_pct is not None and inputs.reservoir.level_pct >= 95.0
        )
        if need_flood:
            rationale.append("Reservoir overflow risk requires flood agent coordination")
            suggested.append(AGENT_FLOOD)

        need_agriculture = bool(signals.get("agricultural_demand_high")) or (
            inputs.demand.crop_area_ha is not None and inputs.demand.crop_area_ha > 1000
        )
        if need_agriculture:
            rationale.append("Agricultural water demand requires crop-specific analysis")
            suggested.append(AGENT_AGRICULTURE)

        need_urban = bool(signals.get("urban_demand_high")) or (
            inputs.demand.population is not None and inputs.demand.population > 1_000_000
        )
        if need_urban:
            rationale.append("Urban water supply requires planning coordination")
            suggested.append(AGENT_URBAN_PLANNING)

        need_disaster = stress in (WaterStressLevel.SEVERE, WaterStressLevel.CRITICAL)
        if need_disaster:
            rationale.append("Severe water stress may require disaster response")
            suggested.append(AGENT_DISASTER)

        need_simulation = (
            reflection.needs_simulation
            or stress in (WaterStressLevel.HIGH, WaterStressLevel.SEVERE, WaterStressLevel.CRITICAL)
            or bool(inputs.dependent_basins)
            or bool(signals.get("overflow_risk"))
        )
        if need_simulation:
            rationale.append("Basin-scale water simulation needed for allocation planning")

        need_forecast_update = (
            not inputs.forecast_available
            or bool(signals.get("rainfall_deficit"))
            or stress_score >= 0.4
        )
        if need_forecast_update:
            rationale.append("Updated rainfall forecast required for water planning")

        priority = "normal"
        if stress == WaterStressLevel.CRITICAL or bool(signals.get("overflow_risk")):
            priority = "critical"
        elif stress in (WaterStressLevel.SEVERE, WaterStressLevel.HIGH):
            priority = "high"

        unique_agents = list(dict.fromkeys(suggested))

        decision = DecisionRequest(
            need_rl=need_rl,
            need_flood_agent=need_flood,
            need_agriculture_agent=need_agriculture,
            need_urban_planning_agent=need_urban,
            need_disaster_agent=need_disaster,
            need_simulation=need_simulation,
            need_forecast_update=need_forecast_update,
            suggested_agents=unique_agents,
            rationale=rationale,
            priority=priority,
            metadata={
                "stress_level": stress.value,
                "stress_score": stress_score,
                "availability_score": availability_score,
            },
        )

        logger.debug(
            "water_decision_evaluated",
            agent_id=self._agent_id,
            suggested_agents=unique_agents,
            need_rl=need_rl,
            need_simulation=need_simulation,
        )
        return decision

    def _resolve_inputs(self, context: AgentContext) -> WaterInputs:
        stored = context.metadata.get("water_inputs")
        if isinstance(stored, WaterInputs):
            return stored
        return WaterInputs.from_request_context(context.request.context)
