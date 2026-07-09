"""Disaster response self-evaluation and reflection."""

from __future__ import annotations

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.specialized.agent_reflection import ReflectionFinding, ReflectionResult, ReflectionSignal
from backend.agents.specialized.disaster_response.disaster_context import DisasterInputs
from backend.agents.specialized.disaster_response.disaster_models import (
    AGENT_AIR_QUALITY,
    AGENT_AGRICULTURE,
    AGENT_FLOOD,
    AGENT_HEATWAVE,
    AGENT_URBAN_PLANNING,
    AGENT_WATER_RESOURCE,
    ALL_HAZARD_AGENTS,
    EmergencyPriority,
)
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


class DisasterReflectionEngine:
    """Evaluates disaster response plan completeness."""

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
        signals = reasoning.metadata.get("disaster_signals", {})
        rankings = reasoning.metadata.get("priority_rankings", [])

        if not inputs.hazard_agent_outputs:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.MISSING_CONTEXT,
                message="No hazard agent outputs available for coordination",
                severity=0.85,
            ))

        if reasoning.overall_confidence < self._confidence_threshold:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.LOW_CONFIDENCE,
                message=f"Coordination confidence {reasoning.overall_confidence:.2f} below threshold",
                severity=0.7,
            ))

        missing_hazards = self._missing_hazard_agents(inputs)
        for agent_id in missing_hazards:
            suggested.append(agent_id)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message=f"Consult {agent_id} for complete hazard picture",
                severity=0.5,
                suggested_agent=agent_id,
            ))

        composite = float(signals.get("composite_priority_score", 0.0))
        needs_rl = (
            signals.get("compound_disaster", False)
            or signals.get("resource_gap", False)
            or composite >= 0.65
        )
        if needs_rl:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_RL,
                message="Multi-hazard resource allocation warrants RL optimization",
                severity=0.6,
            ))

        needs_simulation = signals.get("compound_disaster", False)
        if needs_simulation:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_SIMULATION,
                message="Compound disaster scenario simulation recommended",
                severity=0.55,
            ))

        hazard_types = {r.get("hazard_type") for r in rankings if isinstance(r, dict)}
        if "flood" in hazard_types and AGENT_FLOOD not in suggested:
            suggested.append(AGENT_FLOOD)
        if "heatwave" in hazard_types and AGENT_HEATWAVE not in suggested:
            suggested.append(AGENT_HEATWAVE)
        if signals.get("infrastructure_critical") and AGENT_URBAN_PLANNING not in suggested:
            suggested.append(AGENT_URBAN_PLANNING)
        if signals.get("resource_gap") and AGENT_WATER_RESOURCE not in suggested:
            suggested.append(AGENT_WATER_RESOURCE)

        if not findings:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.SUFFICIENT,
                message="Disaster response coordination data is sufficient",
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

    def _resolve_inputs(self, context: AgentContext) -> DisasterInputs:
        stored = context.metadata.get("disaster_inputs")
        if isinstance(stored, DisasterInputs):
            return stored
        return DisasterInputs.from_request_context(context.request.context)

    def _missing_hazard_agents(self, inputs: DisasterInputs) -> list[str]:
        present = set(inputs.hazard_agent_outputs.keys())
        consult = set(inputs.consult_agents) if inputs.consult_agents else set(ALL_HAZARD_AGENTS[:4])
        return [a for a in consult if a not in present]
