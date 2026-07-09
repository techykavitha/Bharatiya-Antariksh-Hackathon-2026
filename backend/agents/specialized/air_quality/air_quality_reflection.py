"""Air quality self-evaluation and reflection."""

from __future__ import annotations

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.specialized.agent_reflection import ReflectionFinding, ReflectionResult, ReflectionSignal
from backend.agents.specialized.air_quality.air_quality_context import AirQualityInputs
from backend.agents.specialized.air_quality.air_quality_models import (
    AGENT_AGRICULTURE,
    AGENT_CYCLONE,
    AGENT_DISASTER,
    AGENT_HEATWAVE,
    AGENT_URBAN_PLANNING,
    ALL_PEER_AGENTS,
)
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


class AirQualityReflectionEngine:
    """Evaluates air quality analysis completeness."""

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
        signals = reasoning.metadata.get("air_quality_signals", {})
        aqi = int(reasoning.metadata.get("aqi_assessment", {}).get("aqi", 0))

        if not inputs.pollutants:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.MISSING_CONTEXT,
                message="Pollutant concentration data limited for AQI confidence",
                severity=0.55,
            ))

        if reasoning.overall_confidence < self._confidence_threshold:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.LOW_CONFIDENCE,
                message=f"Air quality confidence {reasoning.overall_confidence:.2f} below threshold",
                severity=0.65,
            ))

        missing_peers = self._missing_peer_agents(inputs)
        for agent_id in missing_peers:
            suggested.append(agent_id)
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                message=f"Consult {agent_id} for compound hazard context",
                severity=0.45,
                suggested_agent=agent_id,
            ))

        needs_rl = (
            aqi >= 201
            or len(reasoning.metadata.get("mitigation_strategies", [])) >= 3
            or signals.get("severe_aqi", False)
        )
        if needs_rl:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_RL,
                message="Multi-action mitigation portfolio warrants RL optimization",
                severity=0.55,
            ))

        needs_simulation = bool(signals.get("compound_hazard"))
        if needs_simulation:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.NEED_SIMULATION,
                message="Compound climate-pollution hazard simulation recommended",
                severity=0.5,
            ))

        if signals.get("biomass_burning") and AGENT_AGRICULTURE not in suggested:
            if AGENT_AGRICULTURE not in inputs.peer_agent_outputs:
                suggested.append(AGENT_AGRICULTURE)
        if float(signals.get("health_risk_score", 0)) >= 0.6 and AGENT_DISASTER not in suggested:
            if AGENT_DISASTER not in inputs.peer_agent_outputs:
                suggested.append(AGENT_DISASTER)
        if signals.get("compound_hazard") and AGENT_HEATWAVE not in suggested:
            if AGENT_HEATWAVE not in inputs.peer_agent_outputs:
                suggested.append(AGENT_HEATWAVE)
        if aqi >= 201 and AGENT_URBAN_PLANNING not in suggested:
            if AGENT_URBAN_PLANNING not in inputs.peer_agent_outputs:
                suggested.append(AGENT_URBAN_PLANNING)
        cyclone_peer = inputs.peer_agent_outputs.get(AGENT_CYCLONE)
        if not cyclone_peer and inputs.city_name and "mumbai" in (inputs.city_name or "").lower():
            suggested.append(AGENT_CYCLONE)

        if aqi >= 400:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.VALIDATION_FAILED,
                message=f"Hazardous AQI level detected: {aqi}",
                severity=0.75,
            ))

        if not findings:
            findings.append(ReflectionFinding(
                signal=ReflectionSignal.SUFFICIENT,
                message="Air quality data is sufficient for mitigation advisory",
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

    def _resolve_inputs(self, context: AgentContext) -> AirQualityInputs:
        stored = context.metadata.get("air_quality_inputs")
        if isinstance(stored, AirQualityInputs):
            return stored
        return AirQualityInputs.from_request_context(context.request.context)

    def _missing_peer_agents(self, inputs: AirQualityInputs) -> list[str]:
        present = set(inputs.peer_agent_outputs.keys())
        consult = set(inputs.consult_agents) if inputs.consult_agents else set(ALL_PEER_AGENTS[:2])
        return [a for a in consult if a not in present]
