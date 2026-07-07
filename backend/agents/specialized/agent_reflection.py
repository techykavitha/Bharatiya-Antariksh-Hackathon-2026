"""Self-evaluation and reflection for specialized agents."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


class ReflectionSignal(StrEnum):
    """Signals raised during agent self-evaluation."""

    MISSING_CONTEXT = "missing_context"
    LOW_CONFIDENCE = "low_confidence"
    NEED_ANOTHER_AGENT = "need_another_agent"
    NEED_RL = "need_rl"
    NEED_SIMULATION = "need_simulation"
    NEED_FORECAST = "need_forecast"
    VALIDATION_FAILED = "validation_failed"
    SUFFICIENT = "sufficient"


class ReflectionFinding(BaseModel):
    """Individual reflection finding."""

    signal: ReflectionSignal
    message: str
    severity: float = Field(default=0.5, ge=0.0, le=1.0)
    suggested_agent: str | None = None
    metadata: dict[str, str | float | bool] = Field(default_factory=dict)


class ReflectionResult(BaseModel):
    """Aggregated self-evaluation output."""

    findings: list[ReflectionFinding] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    should_retry_reasoning: bool = False
    needs_another_agent: bool = False
    needs_rl: bool = False
    needs_simulation: bool = False
    suggested_agents: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @property
    def is_sufficient(self) -> bool:
        blocking = {
            ReflectionSignal.MISSING_CONTEXT,
            ReflectionSignal.LOW_CONFIDENCE,
            ReflectionSignal.VALIDATION_FAILED,
        }
        return not any(f.signal in blocking for f in self.findings)


class ReflectionEngine:
    """
    Evaluates whether a specialized agent has sufficient context and confidence.

    Checks for missing context, low confidence, delegation needs, RL needs,
    and simulation requirements.
    """

    def __init__(
        self,
        *,
        agent_id: str,
        confidence_threshold: float = 0.4,
    ) -> None:
        self._agent_id = agent_id
        self._confidence_threshold = confidence_threshold

    async def evaluate(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
    ) -> ReflectionResult:
        findings: list[ReflectionFinding] = []
        notes: list[str] = []
        suggested_agents: list[str] = []

        if not context.query.strip():
            findings.append(
                ReflectionFinding(
                    signal=ReflectionSignal.MISSING_CONTEXT,
                    message="Query is empty",
                    severity=1.0,
                ),
            )

        if not context.request.has_climate_context and self._requires_climate(context):
            findings.append(
                ReflectionFinding(
                    signal=ReflectionSignal.MISSING_CONTEXT,
                    message="Climate state not attached to request",
                    severity=0.7,
                ),
            )

        if reasoning.overall_confidence < self._confidence_threshold:
            findings.append(
                ReflectionFinding(
                    signal=ReflectionSignal.LOW_CONFIDENCE,
                    message=(
                        f"Reasoning confidence {reasoning.overall_confidence:.2f} "
                        f"below threshold {self._confidence_threshold}"
                    ),
                    severity=1.0 - reasoning.overall_confidence,
                ),
            )

        if context.validation_errors:
            findings.append(
                ReflectionFinding(
                    signal=ReflectionSignal.VALIDATION_FAILED,
                    message="; ".join(context.validation_errors),
                    severity=0.9,
                ),
            )

        needs_simulation = self._check_simulation_need(context, reasoning)
        if needs_simulation:
            findings.append(
                ReflectionFinding(
                    signal=ReflectionSignal.NEED_SIMULATION,
                    message="Simulation context required but not available",
                    severity=0.8,
                ),
            )

        needs_forecast = self._check_forecast_need(context, reasoning)
        if needs_forecast:
            findings.append(
                ReflectionFinding(
                    signal=ReflectionSignal.NEED_FORECAST,
                    message="Forecast context required but not available",
                    severity=0.7,
                ),
            )

        needs_rl = self._check_rl_need(context, reasoning)
        if needs_rl:
            findings.append(
                ReflectionFinding(
                    signal=ReflectionSignal.NEED_RL,
                    message="RL policy evaluation recommended",
                    severity=0.6,
                ),
            )

        delegate_agent = self._suggest_delegate_agent(context, reasoning)
        if delegate_agent:
            findings.append(
                ReflectionFinding(
                    signal=ReflectionSignal.NEED_ANOTHER_AGENT,
                    message=f"Delegation to '{delegate_agent}' recommended",
                    severity=0.5,
                    suggested_agent=delegate_agent,
                ),
            )
            suggested_agents.append(delegate_agent)

        if not findings:
            findings.append(
                ReflectionFinding(
                    signal=ReflectionSignal.SUFFICIENT,
                    message="Context and confidence are sufficient",
                    severity=0.0,
                ),
            )

        for finding in findings:
            notes.append(finding.message)
            context.add_reflection(finding.message)

        result = ReflectionResult(
            findings=findings,
            confidence=reasoning.overall_confidence,
            should_retry_reasoning=any(
                f.signal == ReflectionSignal.LOW_CONFIDENCE for f in findings
            ),
            needs_another_agent=bool(suggested_agents),
            needs_rl=needs_rl,
            needs_simulation=needs_simulation,
            suggested_agents=suggested_agents,
            notes=notes,
        )

        logger.debug(
            "reflection_completed",
            agent_id=self._agent_id,
            findings=len(findings),
            needs_rl=result.needs_rl,
            needs_agent=result.needs_another_agent,
        )
        return result

    def _requires_climate(self, context: AgentContext) -> bool:
        return bool(context.metadata.get("requires_climate_state"))

    def _check_simulation_need(self, context: AgentContext, reasoning: ReasoningResult) -> bool:
        if context.simulation.simulation_id or context.simulation.outputs:
            return False
        return bool(
            context.metadata.get("requires_simulation")
            or reasoning.metadata.get("requires_simulation")
        )

    def _check_forecast_need(self, context: AgentContext, reasoning: ReasoningResult) -> bool:
        if context.forecast.references or context.forecast.payload:
            return False
        return bool(
            context.metadata.get("requires_forecast")
            or reasoning.metadata.get("requires_forecast")
        )

    def _check_rl_need(self, context: AgentContext, reasoning: ReasoningResult) -> bool:
        if context.rl_outputs.policy or context.rl_outputs.ranked_actions:
            return False
        return bool(
            context.metadata.get("requires_rl")
            or reasoning.metadata.get("requires_rl")
        )

    def _suggest_delegate_agent(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
    ) -> str | None:
        explicit = context.metadata.get("delegate_to")
        if isinstance(explicit, str) and explicit:
            return explicit
        suggested = reasoning.metadata.get("delegate_to")
        if isinstance(suggested, str) and suggested:
            return suggested
        if reasoning.overall_confidence < 0.2:
            fallback = context.request.target_agent
            if fallback and fallback != context.agent_id:
                return fallback
        return None
