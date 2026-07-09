"""Agriculture self-evaluation and reflection."""

from __future__ import annotations

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.specialized.agent_reflection import ReflectionFinding, ReflectionResult, ReflectionSignal
from backend.agents.specialized.agriculture.agriculture_context import AgricultureInputs
from backend.agents.specialized.agriculture.agriculture_models import (
    AGENT_FLOOD,
    AGENT_HEATWAVE,
    AGENT_URBAN_PLANNING,
    AGENT_WATER_RESOURCE,
    ALL_PEER_AGENTS,
)
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


class AgricultureReflectionEngine:
    """Evaluates agriculture analysis completeness."""

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
        signals = reasoning.metadata.get("agriculture_signals", {})

        if not inputs.remote_sensing.ndvi and not tool_results:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.MISSING_CONTEXT,
                message="Remote sensing data limited for crop health assessment",
                severity=0.55,
            ))

        if reasoning.overall_confidence < self._confidence_threshold:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.LOW_CONFIDENCE,
                message=f"Agriculture confidence {reasoning.overall_confidence:.2f} below threshold",
                severity=0.65,
            ))

        rag_count = reasoning.metadata.get("rag_document_count", 0)
        if rag_count == 0:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.MISSING_CONTEXT,
                message="No RAG documents retrieved for advisory context",
                severity=0.45,
            ))

        for agent_id in self._missing_peer_agents(inputs):
            suggested.append(agent_id)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message=f"Consult {agent_id} for integrated hazard-water context",
                severity=0.45,
                suggested_agent=agent_id,
            ))

        needs_rl = (
            signals.get("drought_risk", False)
            or signals.get("water_stress", False)
            or float(signals.get("yield_risk_score", 0)) >= 0.5
        )
        if needs_rl:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_RL,
                message="Irrigation and crop scheduling warrant RL optimization",
                severity=0.55,
            ))

        if signals.get("drought_risk") and AGENT_WATER_RESOURCE not in suggested:
            if AGENT_WATER_RESOURCE not in inputs.peer_agent_outputs:
                suggested.append(AGENT_WATER_RESOURCE)
        if signals.get("heat_stress") and AGENT_HEATWAVE not in suggested:
            if AGENT_HEATWAVE not in inputs.peer_agent_outputs:
                suggested.append(AGENT_HEATWAVE)
        if signals.get("flood_impact") and AGENT_FLOOD not in suggested:
            if AGENT_FLOOD not in inputs.peer_agent_outputs:
                suggested.append(AGENT_FLOOD)

        if not findings:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.SUFFICIENT,
                message="Agricultural analysis data is sufficient",
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
            needs_simulation=False,
            suggested_agents=unique,
            notes=notes,
        )

    def _resolve_inputs(self, context: AgentContext) -> AgricultureInputs:
        stored = context.metadata.get("agriculture_inputs")
        if isinstance(stored, AgricultureInputs):
            return stored
        return AgricultureInputs.from_request_context(context.request.context)

    def _missing_peer_agents(self, inputs: AgricultureInputs) -> list[str]:
        present = set(inputs.peer_agent_outputs.keys())
        consult = set(inputs.consult_agents) if inputs.consult_agents else set(ALL_PEER_AGENTS[:3])
        return [a for a in consult if a not in present]
