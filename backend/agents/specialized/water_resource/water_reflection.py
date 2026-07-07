"""Water resource-specific self-evaluation and reflection."""

from __future__ import annotations

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.specialized.agent_reflection import ReflectionFinding, ReflectionResult, ReflectionSignal
from backend.agents.specialized.water_resource.water_context import WaterInputs
from backend.agents.specialized.water_resource.water_models import (
    AGENT_AGRICULTURE,
    AGENT_DISASTER,
    AGENT_FLOOD,
    AGENT_URBAN_PLANNING,
    WaterStressLevel,
)
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


class WaterReflectionEngine:
    """Self-evaluates water resource analysis completeness and delegation needs."""

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
        signals = reasoning.metadata.get("water_signals", {})
        stress = reasoning.metadata.get("stress_level", WaterStressLevel.NONE.value)

        if not self._has_sufficient_data(inputs, tool_results):
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.MISSING_CONTEXT,
                message="Insufficient hydrological data for high-confidence water assessment",
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

        needs_rl = (
            stress in (WaterStressLevel.SEVERE.value, WaterStressLevel.CRITICAL.value)
            and float(signals.get("composite_score", 0)) >= 0.5
            and float(signals.get("uncertainty", 0.5)) < 0.5
        )
        if needs_rl:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_RL,
                message="Complex water allocation scenario warrants RL optimization",
                severity=0.6,
            ))

        needs_simulation = (
            bool(signals.get("overflow_risk"))
            or stress in (
                WaterStressLevel.HIGH.value,
                WaterStressLevel.SEVERE.value,
                WaterStressLevel.CRITICAL.value,
            )
            or bool(inputs.dependent_basins)
        )
        if needs_simulation:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_SIMULATION,
                message="Basin-scale water simulation recommended for allocation planning",
                severity=0.55,
            ))

        if signals.get("overflow_risk"):
            suggested.append(AGENT_FLOOD)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message="Reservoir overflow risk requires flood agent coordination",
                severity=0.7,
                suggested_agent=AGENT_FLOOD,
            ))

        if signals.get("agricultural_demand_high"):
            suggested.append(AGENT_AGRICULTURE)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message="High agricultural demand requires agriculture agent",
                severity=0.5,
                suggested_agent=AGENT_AGRICULTURE,
            ))

        if signals.get("urban_demand_high"):
            suggested.append(AGENT_URBAN_PLANNING)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message="High urban demand requires urban planning agent",
                severity=0.5,
                suggested_agent=AGENT_URBAN_PLANNING,
            ))

        if stress in (WaterStressLevel.SEVERE.value, WaterStressLevel.CRITICAL.value):
            suggested.append(AGENT_DISASTER)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message="Severe water stress may require disaster response coordination",
                severity=0.6,
                suggested_agent=AGENT_DISASTER,
            ))

        if not findings:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.SUFFICIENT,
                message="Water resource analysis data is sufficient",
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
            "water_reflection_completed",
            agent_id=self._agent_id,
            needs_rl=needs_rl,
            suggested_agents=unique_agents,
        )
        return result

    def _resolve_inputs(self, context: AgentContext) -> WaterInputs:
        stored = context.metadata.get("water_inputs")
        if isinstance(stored, WaterInputs):
            return stored
        return WaterInputs.from_request_context(context.request.context)

    def _has_sufficient_data(
        self,
        inputs: WaterInputs,
        tool_results: list[ToolResult],
    ) -> bool:
        successful = sum(1 for r in tool_results if r.success)
        has_reservoir = inputs.reservoir.level_pct is not None or any(
            r.tool_name == "reservoir_tool" and r.success for r in tool_results
        )
        return successful >= 4 and has_reservoir

    def _missing_tools(self, tool_results: list[ToolResult]) -> list[str]:
        executed = {r.tool_name for r in tool_results if r.success}
        expected = {"reservoir_tool", "rainfall_tool", "demand_tool"}
        return [t for t in expected if t not in executed]
