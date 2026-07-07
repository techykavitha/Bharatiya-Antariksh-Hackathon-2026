"""Flood decision engine — determines downstream agent and system needs."""

from __future__ import annotations

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.specialized.agent_reflection import ReflectionResult
from backend.agents.specialized.flood.flood_context import DecisionRequest, FloodInputs
from backend.agents.specialized.flood.flood_models import (
    AGENT_AIR_QUALITY,
    AGENT_CYCLONE,
    AGENT_DISASTER,
    AGENT_URBAN_PLANNING,
    AGENT_WATER_RESOURCE,
    FloodRiskLevel,
    FloodSeverity,
)
from backend.config.logger import get_logger

logger = get_logger(__name__)


class FloodDecisionEngine:
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
        signals = reasoning.metadata.get("flood_signals", {})
        severity = FloodSeverity(reasoning.metadata.get("severity", FloodSeverity.NONE.value))
        composite = float(signals.get("composite_score", 0.0))
        uncertainty = float(signals.get("uncertainty", 0.5))

        rationale: list[str] = []
        suggested: list[str] = []

        need_rl = (
            severity in (FloodSeverity.MAJOR, FloodSeverity.CATASTROPHIC)
            and composite >= 0.65
            and uncertainty < 0.5
        )
        if need_rl:
            rationale.append("High-severity flood with sufficient data confidence for RL policy")

        need_water = bool(signals.get("reservoir_stressed")) or (
            inputs.hydrology.reservoir_level_pct is not None
            and inputs.hydrology.reservoir_level_pct >= 80.0
        )
        if need_water:
            rationale.append("Reservoir levels require water resource management")
            suggested.append(AGENT_WATER_RESOURCE)

        need_disaster = severity in (FloodSeverity.MAJOR, FloodSeverity.CATASTROPHIC)
        if need_disaster:
            rationale.append("Major/catastrophic severity requires disaster response")
            suggested.append(AGENT_DISASTER)

        need_cyclone = (
            "cyclone" in context.query.lower()
            or "storm surge" in context.query.lower()
            or "coastal" in context.query.lower()
        )
        if need_cyclone:
            rationale.append("Coastal/cyclone context detected")
            suggested.append(AGENT_CYCLONE)

        need_air_quality = composite >= 0.5 and "pollution" in context.query.lower()
        if need_air_quality:
            rationale.append("Post-flood air quality assessment may be needed")
            suggested.append(AGENT_AIR_QUALITY)

        need_urban = (
            bool(signals.get("urban_pluvial_risk"))
            or (inputs.terrain.urban_density or 0) > 0.5
        )
        if need_urban:
            rationale.append("Urban pluvial flooding requires planning coordination")
            suggested.append(AGENT_URBAN_PLANNING)

        need_simulation = (
            reflection.needs_simulation
            or severity in (FloodSeverity.MODERATE, FloodSeverity.MAJOR, FloodSeverity.CATASTROPHIC)
            or composite >= 0.45
        )
        if need_simulation:
            rationale.append("Inundation simulation needed for spatial impact mapping")

        need_forecast_update = (
            not inputs.forecast_available
            or float(signals.get("rainfall_score", 0)) >= 0.5
        )
        if need_forecast_update and composite >= 0.3:
            rationale.append("Updated forecast required for evolving conditions")

        need_reservoir_optimization = need_water and composite >= 0.4
        if need_reservoir_optimization:
            rationale.append("Reservoir optimization recommended")

        priority = "normal"
        risk = self._risk_level(composite, severity)
        if risk in (FloodRiskLevel.SEVERE, FloodRiskLevel.EXTREME):
            priority = "critical"
        elif risk == FloodRiskLevel.HIGH:
            priority = "high"

        unique_agents = list(dict.fromkeys(suggested))

        decision = DecisionRequest(
            need_rl=need_rl,
            need_water_resource_agent=need_water,
            need_disaster_agent=need_disaster,
            need_cyclone_agent=need_cyclone,
            need_air_quality_agent=need_air_quality,
            need_urban_planning_agent=need_urban,
            need_simulation=need_simulation,
            need_forecast_update=need_forecast_update,
            need_reservoir_optimization=need_reservoir_optimization,
            suggested_agents=unique_agents,
            rationale=rationale,
            priority=priority,
            metadata={
                "composite_score": composite,
                "severity": severity.value,
                "risk_level": risk.value,
            },
        )

        logger.debug(
            "flood_decision_evaluated",
            agent_id=self._agent_id,
            suggested_agents=unique_agents,
            need_rl=need_rl,
            need_simulation=need_simulation,
        )
        return decision

    def _resolve_inputs(self, context: AgentContext) -> FloodInputs:
        stored = context.metadata.get("flood_inputs")
        if isinstance(stored, FloodInputs):
            return stored
        return FloodInputs.from_request_context(context.request.context)

    def _risk_level(self, composite: float, severity: FloodSeverity) -> FloodRiskLevel:
        if severity == FloodSeverity.CATASTROPHIC or composite >= 0.85:
            return FloodRiskLevel.EXTREME
        if severity == FloodSeverity.MAJOR or composite >= 0.7:
            return FloodRiskLevel.SEVERE
        if severity == FloodSeverity.MODERATE or composite >= 0.55:
            return FloodRiskLevel.HIGH
        if composite >= 0.35:
            return FloodRiskLevel.MODERATE
        if composite >= 0.15:
            return FloodRiskLevel.LOW
        return FloodRiskLevel.MINIMAL
