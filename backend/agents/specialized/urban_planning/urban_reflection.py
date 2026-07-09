"""Urban planning self-evaluation and reflection."""

from __future__ import annotations

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.specialized.agent_reflection import ReflectionFinding, ReflectionResult, ReflectionSignal
from backend.agents.specialized.urban_planning.urban_context import UrbanInputs
from backend.agents.specialized.urban_planning.urban_models import (
    AGENT_AIR_QUALITY,
    AGENT_AGRICULTURE,
    AGENT_FLOOD,
    AGENT_HEATWAVE,
    AGENT_WATER_RESOURCE,
    ALL_PEER_AGENTS,
    UrbanResilienceLevel,
)
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


class UrbanReflectionEngine:
    """Evaluates urban planning analysis completeness."""

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
        signals = reasoning.metadata.get("urban_signals", {})
        resilience = float(signals.get("resilience_score", 0.5))

        if not inputs.environment.ndvi and not inputs.environment.green_cover_pct:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.MISSING_CONTEXT,
                message="Vegetation and green cover data limited for planning confidence",
                severity=0.55,
            ))

        if reasoning.overall_confidence < self._confidence_threshold:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.LOW_CONFIDENCE,
                message=f"Planning confidence {reasoning.overall_confidence:.2f} below threshold",
                severity=0.65,
            ))

        missing_peers = self._missing_peer_agents(inputs)
        for agent_id in missing_peers:
            suggested.append(agent_id)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message=f"Consult {agent_id} for domain-specific hazard context",
                severity=0.45,
                suggested_agent=agent_id,
            ))

        needs_rl = (
            resilience < 0.55
            or len(reasoning.metadata.get("mitigation_options", [])) >= 3
            or signals.get("flood_vulnerability", False)
        )
        if needs_rl:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_RL,
                message="Multi-objective adaptation portfolio warrants RL budget optimization",
                severity=0.55,
            ))

        needs_simulation = (
            signals.get("urban_heat_island", False)
            and signals.get("flood_vulnerability", False)
        )
        if needs_simulation:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_SIMULATION,
                message="Compound heat-flood scenario simulation recommended for what-if analysis",
                severity=0.5,
            ))

        if signals.get("urban_heat_island") and AGENT_HEATWAVE not in suggested:
            if AGENT_HEATWAVE not in inputs.peer_agent_outputs:
                suggested.append(AGENT_HEATWAVE)
        if signals.get("flood_vulnerability") and AGENT_FLOOD not in suggested:
            if AGENT_FLOOD not in inputs.peer_agent_outputs:
                suggested.append(AGENT_FLOOD)
        if signals.get("water_scarcity") and AGENT_WATER_RESOURCE not in suggested:
            if AGENT_WATER_RESOURCE not in inputs.peer_agent_outputs:
                suggested.append(AGENT_WATER_RESOURCE)
        if float(signals.get("heat_risk_score", 0)) >= 0.6 and AGENT_AIR_QUALITY not in suggested:
            suggested.append(AGENT_AIR_QUALITY)

        if resilience < 0.35:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.VALIDATION_FAILED,
                message=f"Critical resilience level: {signals.get('resilience_level', UrbanResilienceLevel.CRITICAL.value)}",
                severity=0.7,
            ))

        if not findings:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.SUFFICIENT,
                message="Urban planning data is sufficient for adaptation strategy",
                severity=0.0,
            ))

        for f in findings:
            notes.append(f.message)
            context.add_reflection(f.message)

        unique = list(dict.fromkeys(suggested))
        return ReflectionResult(
            findings=findings,
            confidence=reasoning.overall_confidence,
            should_retry_reasoning=any(f.signal == ReflectionSignal.LOW_CONFIDENCE for f in findings),
            needs_another_agent=bool(unique),
            needs_rl=needs_rl,
            needs_simulation=needs_simulation,
            suggested_agents=unique,
            notes=notes,
        )

    def _resolve_inputs(self, context: AgentContext) -> UrbanInputs:
        stored = context.metadata.get("urban_inputs")
        if isinstance(stored, UrbanInputs):
            return stored
        return UrbanInputs.from_request_context(context.request.context)

    def _missing_peer_agents(self, inputs: UrbanInputs) -> list[str]:
        present = set(inputs.peer_agent_outputs.keys())
        consult = set(inputs.consult_agents) if inputs.consult_agents else set(ALL_PEER_AGENTS[:3])
        return [a for a in consult if a not in present]
