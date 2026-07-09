"""Cyclone-specific self-evaluation and reflection."""

from __future__ import annotations

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.specialized.agent_reflection import ReflectionFinding, ReflectionResult, ReflectionSignal
from backend.agents.specialized.cyclone.cyclone_context import CycloneInputs
from backend.agents.specialized.cyclone.cyclone_models import (
    AGENT_AIR_QUALITY,
    AGENT_DISASTER,
    AGENT_FLOOD,
    AGENT_URBAN_PLANNING,
    AGENT_WATER_RESOURCE,
    CycloneSeverity,
    RapidIntensificationStatus,
)
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


class CycloneReflectionEngine:
    """Self-evaluates cyclone analysis completeness and delegation needs."""

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
        signals = reasoning.metadata.get("cyclone_signals", {})
        severity = CycloneSeverity(reasoning.metadata.get("severity", CycloneSeverity.NONE.value))

        if not self._has_sufficient_data(inputs, tool_results):
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.MISSING_CONTEXT,
                message="Insufficient ocean-atmosphere data for high-confidence cyclone assessment",
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

        needs_rl = severity in (CycloneSeverity.SEVERE, CycloneSeverity.EXTREME) and float(
            signals.get("composite_score", 0),
        ) >= 0.65
        if needs_rl:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_RL,
                message="Severe cyclone warrants RL-optimized evacuation and resource allocation",
                severity=0.65,
            ))

        needs_simulation = (
            severity in (CycloneSeverity.HIGH, CycloneSeverity.SEVERE, CycloneSeverity.EXTREME)
            or signals.get("high_storm_surge")
        )
        if needs_simulation:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_SIMULATION,
                message="Storm surge and track simulation recommended",
                severity=0.55,
            ))

        if signals.get("heavy_rainfall") or severity in (CycloneSeverity.HIGH, CycloneSeverity.SEVERE, CycloneSeverity.EXTREME):
            suggested.append(AGENT_FLOOD)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message="Cyclone rainfall requires flood agent coordination",
                severity=0.6,
                suggested_agent=AGENT_FLOOD,
            ))

        if signals.get("heavy_rainfall") or severity in (
            CycloneSeverity.MODERATE,
            CycloneSeverity.HIGH,
            CycloneSeverity.SEVERE,
            CycloneSeverity.EXTREME,
        ):
            suggested.append(AGENT_WATER_RESOURCE)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message="Reservoir management coordination required",
                severity=0.5,
                suggested_agent=AGENT_WATER_RESOURCE,
            ))

        if severity in (CycloneSeverity.SEVERE, CycloneSeverity.EXTREME):
            suggested.append(AGENT_DISASTER)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message="Severe cyclone requires disaster response agent",
                severity=0.75,
                suggested_agent=AGENT_DISASTER,
            ))

        if signals.get("infrastructure_at_risk"):
            suggested.append(AGENT_URBAN_PLANNING)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message="Infrastructure risk requires urban planning coordination",
                severity=0.45,
                suggested_agent=AGENT_URBAN_PLANNING,
            ))

        ri = signals.get("rapid_intensification", RapidIntensificationStatus.NONE.value)
        if ri in (RapidIntensificationStatus.LIKELY.value, RapidIntensificationStatus.CONFIRMED.value):
            suggested.append(AGENT_AIR_QUALITY)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message="Post-landfall air quality impacts may require AQI agent",
                severity=0.35,
                suggested_agent=AGENT_AIR_QUALITY,
            ))

        if not findings:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.SUFFICIENT,
                message="Cyclone analysis data is sufficient",
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

    def _resolve_inputs(self, context: AgentContext) -> CycloneInputs:
        stored = context.metadata.get("cyclone_inputs")
        if isinstance(stored, CycloneInputs):
            return stored
        return CycloneInputs.from_request_context(context.request.context)

    def _has_sufficient_data(self, inputs: CycloneInputs, tool_results: list[ToolResult]) -> bool:
        successful = sum(1 for r in tool_results if r.success)
        has_ocean = inputs.ocean.sst_c is not None or any(
            r.tool_name in ("sst_tool", "pressure_tool", "wind_tool") and r.success for r in tool_results
        )
        return successful >= 5 and has_ocean

    def _missing_tools(self, tool_results: list[ToolResult]) -> list[str]:
        executed = {r.tool_name for r in tool_results if r.success}
        expected = {"sst_tool", "pressure_tool", "wind_tool", "forecast_tool"}
        return [t for t in expected if t not in executed]
