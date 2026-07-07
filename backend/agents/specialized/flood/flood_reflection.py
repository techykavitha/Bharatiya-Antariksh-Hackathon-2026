"""Flood-specific self-evaluation and reflection."""

from __future__ import annotations

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.specialized.agent_reflection import ReflectionFinding, ReflectionResult, ReflectionSignal
from backend.agents.specialized.flood.flood_context import FloodInputs
from backend.agents.specialized.flood.flood_models import (
    AGENT_CYCLONE,
    AGENT_DISASTER,
    AGENT_URBAN_PLANNING,
    AGENT_WATER_RESOURCE,
    FloodSeverity,
)
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


class FloodReflectionEngine:
    """Self-evaluates flood analysis completeness and delegation needs."""

    def __init__(self, *, agent_id: str, confidence_threshold: float = 0.5) -> None:
        self._agent_id = agent_id
        self._confidence_threshold = confidence_threshold

    async def evaluate(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        tool_results: list[ToolResult],
    ) -> ReflectionResult:
        findings: list[ReflectionFinding] = []
        notes: list[str] = []
        suggested: list[str] = []
        inputs = self._resolve_inputs(context)
        signals = reasoning.metadata.get("flood_signals", {})
        severity = reasoning.metadata.get("severity", FloodSeverity.NONE.value)

        if not self._has_sufficient_data(inputs, tool_results):
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.MISSING_CONTEXT,
                message="Insufficient hydrological data for high-confidence assessment",
                severity=0.8,
            ))

        if reasoning.overall_confidence < self._confidence_threshold:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.LOW_CONFIDENCE,
                message=f"Confidence {reasoning.overall_confidence:.2f} below threshold",
                severity=0.7,
            ))

        missing_tools = self._missing_tools(tool_results)
        if missing_tools:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.MISSING_CONTEXT,
                message=f"Missing tool outputs: {', '.join(missing_tools)}",
                severity=0.5,
                metadata={"missing_tools": ",".join(missing_tools)},
            ))

        needs_rl = severity in (
            FloodSeverity.MAJOR.value,
            FloodSeverity.CATASTROPHIC.value,
        ) and float(signals.get("composite_score", 0)) >= 0.7
        if needs_rl:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_RL,
                message="High-severity flood scenario warrants RL policy optimization",
                severity=0.6,
            ))

        needs_simulation = (
            severity in (FloodSeverity.MODERATE.value, FloodSeverity.MAJOR.value, FloodSeverity.CATASTROPHIC.value)
            or signals.get("terrain_vulnerable")
        )
        if needs_simulation:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_SIMULATION,
                message="Hydrological simulation recommended for inundation mapping",
                severity=0.55,
            ))

        if signals.get("reservoir_stressed"):
            suggested.append(AGENT_WATER_RESOURCE)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message="Reservoir stress requires water resource agent",
                severity=0.5,
                suggested_agent=AGENT_WATER_RESOURCE,
            ))

        if severity in (FloodSeverity.MAJOR.value, FloodSeverity.CATASTROPHIC.value):
            suggested.append(AGENT_DISASTER)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message="Major flood severity requires disaster response agent",
                severity=0.7,
                suggested_agent=AGENT_DISASTER,
            ))

        if context.query.lower().find("cyclone") >= 0 or context.query.lower().find("storm surge") >= 0:
            suggested.append(AGENT_CYCLONE)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message="Coastal/cyclone keywords detected",
                severity=0.4,
                suggested_agent=AGENT_CYCLONE,
            ))

        if signals.get("urban_pluvial_risk") or (inputs.terrain.urban_density or 0) > 0.6:
            suggested.append(AGENT_URBAN_PLANNING)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message="Urban pluvial risk requires urban planning agent",
                severity=0.45,
                suggested_agent=AGENT_URBAN_PLANNING,
            ))

        if not findings:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.SUFFICIENT,
                message="Flood analysis data is sufficient",
                severity=0.0,
            ))

        for f in findings:
            notes.append(f.message)
            context.add_reflection(f.message)

        unique_agents = list(dict.fromkeys(suggested))
        result = ReflectionResult(
            findings=findings,
            confidence=reasoning.overall_confidence,
            should_retry_reasoning=any(
                f.signal == ReflectionSignal.LOW_CONFIDENCE for f in findings
            ),
            needs_another_agent=bool(unique_agents),
            needs_rl=needs_rl,
            needs_simulation=needs_simulation,
            suggested_agents=unique_agents,
            notes=notes,
        )
        logger.debug(
            "flood_reflection_completed",
            agent_id=self._agent_id,
            needs_rl=needs_rl,
            suggested_agents=unique_agents,
        )
        return result

    def _resolve_inputs(self, context: AgentContext) -> FloodInputs:
        stored = context.metadata.get("flood_inputs")
        if isinstance(stored, FloodInputs):
            return stored
        return FloodInputs.from_request_context(context.request.context)

    def _has_sufficient_data(
        self,
        inputs: FloodInputs,
        tool_results: list[ToolResult],
    ) -> bool:
        successful = sum(1 for r in tool_results if r.success)
        has_rainfall = inputs.rainfall.current_mm is not None or any(
            r.tool_name == "rainfall_tool" and r.success for r in tool_results
        )
        return successful >= 3 and has_rainfall

    def _missing_tools(self, tool_results: list[ToolResult]) -> list[str]:
        executed = {r.tool_name for r in tool_results if r.success}
        expected = {"rainfall_tool", "terrain_tool", "dem_tool"}
        return [t for t in expected if t not in executed]
