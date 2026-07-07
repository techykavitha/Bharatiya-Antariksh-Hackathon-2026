"""Heatwave-specific self-evaluation and reflection."""

from __future__ import annotations

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.specialized.agent_reflection import ReflectionFinding, ReflectionResult, ReflectionSignal
from backend.agents.specialized.heatwave.heatwave_context import HeatwaveInputs
from backend.agents.specialized.heatwave.heatwave_models import (
    AGENT_AIR_QUALITY,
    AGENT_DISASTER,
    AGENT_FLOOD,
    AGENT_URBAN_PLANNING,
    AGENT_WATER_RESOURCE,
    HeatwaveSeverity,
)
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


class HeatwaveReflectionEngine:
    """Self-evaluates heatwave analysis completeness and delegation needs."""

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
        signals = reasoning.metadata.get("heat_signals", {})
        severity = reasoning.metadata.get("severity", HeatwaveSeverity.NONE.value)

        if not self._has_sufficient_data(inputs, tool_results):
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.MISSING_CONTEXT,
                message="Insufficient thermal data for high-confidence assessment",
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
            HeatwaveSeverity.SEVERE.value,
            HeatwaveSeverity.EXTREME.value,
        ) and float(signals.get("composite_score", 0)) >= 0.65
        if needs_rl:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_RL,
                message="Severe heatwave warrants RL-optimized mitigation planning",
                severity=0.6,
            ))

        needs_simulation = severity in (
            HeatwaveSeverity.HIGH.value,
            HeatwaveSeverity.SEVERE.value,
            HeatwaveSeverity.EXTREME.value,
        ) or signals.get("urban_heat_island")
        if needs_simulation:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_SIMULATION,
                message="Urban thermal simulation recommended for cooling strategy",
                severity=0.55,
            ))

        if signals.get("urban_heat_island") or (inputs.urban.urban_density or 0) > 0.6:
            suggested.append(AGENT_URBAN_PLANNING)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message="Urban heat island requires urban planning agent",
                severity=0.5,
                suggested_agent=AGENT_URBAN_PLANNING,
            ))

        if severity in (HeatwaveSeverity.HIGH.value, HeatwaveSeverity.SEVERE.value, HeatwaveSeverity.EXTREME.value):
            suggested.append(AGENT_WATER_RESOURCE)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message="Heat stress requires water distribution coordination",
                severity=0.5,
                suggested_agent=AGENT_WATER_RESOURCE,
            ))

        if signals.get("compound_aqi_risk"):
            suggested.append(AGENT_AIR_QUALITY)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message="Compound heat-AQI event requires air quality agent",
                severity=0.6,
                suggested_agent=AGENT_AIR_QUALITY,
            ))

        if severity in (HeatwaveSeverity.SEVERE.value, HeatwaveSeverity.EXTREME.value):
            suggested.append(AGENT_DISASTER)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message="Severe heatwave requires disaster response coordination",
                severity=0.7,
                suggested_agent=AGENT_DISASTER,
            ))

        if "monsoon" in context.query.lower() or signals.get("compound_aqi_risk"):
            if severity in (HeatwaveSeverity.SEVERE.value, HeatwaveSeverity.EXTREME.value):
                suggested.append(AGENT_FLOOD)
                findings.append(ReflectionFinding(
                    signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                    message="Compound heat-flood risk may require flood agent",
                    severity=0.4,
                    suggested_agent=AGENT_FLOOD,
                ))

        if not findings:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.SUFFICIENT,
                message="Heatwave analysis data is sufficient",
                severity=0.0,
            ))

        for f in findings:
            notes.append(f.message)
            context.add_reflection(f.message)

        unique_agents = list(dict.fromkeys(suggested))
        return ReflectionResult(
            findings=findings,
            confidence=reasoning.overall_confidence,
            should_retry_reasoning=any(f.signal == ReflectionSignal.LOW_CONFIDENCE for f in findings),
            needs_another_agent=bool(unique_agents),
            needs_rl=needs_rl,
            needs_simulation=needs_simulation,
            suggested_agents=unique_agents,
            notes=notes,
        )

    def _resolve_inputs(self, context: AgentContext) -> HeatwaveInputs:
        stored = context.metadata.get("heatwave_inputs")
        if isinstance(stored, HeatwaveInputs):
            return stored
        return HeatwaveInputs.from_request_context(context.request.context)

    def _has_sufficient_data(
        self, inputs: HeatwaveInputs, tool_results: list[ToolResult],
    ) -> bool:
        successful = sum(1 for r in tool_results if r.success)
        has_temp = inputs.temperature.air_temp_c is not None or any(
            r.tool_name == "temperature_tool" and r.success for r in tool_results
        )
        return successful >= 4 and has_temp

    def _missing_tools(self, tool_results: list[ToolResult]) -> list[str]:
        executed = {r.tool_name for r in tool_results if r.success}
        expected = {"temperature_tool", "humidity_tool", "population_tool"}
        return [t for t in expected if t not in executed]
