"""Reusable reasoning pipeline for specialized agents."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from backend.agents.specialized.agent_context import AgentContext
from backend.config.logger import get_logger
from backend.utils.constants import MAX_REASONING_ITERATIONS

logger = get_logger(__name__)


class ReasoningPhase(StrEnum):
    """Canonical phases of the specialized agent reasoning loop."""

    OBSERVE = "observe"
    THINK = "think"
    ACT = "act"
    REFLECT = "reflect"
    VERIFY = "verify"


class ReasoningStep(BaseModel):
    """A single step in the reasoning trace."""

    phase: ReasoningPhase
    content: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    duration_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReasoningResult(BaseModel):
    """Output of a full reasoning pipeline execution."""

    steps: list[ReasoningStep] = Field(default_factory=list)
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    recommended_tools: list[str] = Field(default_factory=list)
    requires_reflection: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def trace(self) -> list[str]:
        return [f"[{step.phase.value}] {step.content}" for step in self.steps]


class ReasoningEngine:
    """
    Reusable Observe → Think → Act → Reflect → Verify pipeline.

    Subclasses override phase hooks via ``BaseSpecializedAgent``; the engine
    coordinates sequencing, iteration limits, and confidence aggregation.
    """

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id

    async def run(
        self,
        context: AgentContext,
        *,
        observe: Any,
        think: Any,
        act: Any,
        reflect: Any,
        verify: Any,
        max_iterations: int = MAX_REASONING_ITERATIONS,
    ) -> ReasoningResult:
        steps: list[ReasoningStep] = []
        recommended_tools: list[str] = []
        iteration = 0
        overall_confidence = 0.0

        while iteration < max_iterations and not context.cancelled:
            iteration += 1

            observe_step = await self._run_phase(
                ReasoningPhase.OBSERVE,
                observe,
                context,
            )
            steps.append(observe_step)

            think_step = await self._run_phase(
                ReasoningPhase.THINK,
                think,
                context,
            )
            steps.append(think_step)

            act_step = await self._run_phase(
                ReasoningPhase.ACT,
                act,
                context,
            )
            steps.append(act_step)
            act_tools = act_step.metadata.get("recommended_tools", [])
            if isinstance(act_tools, list):
                recommended_tools.extend(str(t) for t in act_tools)

            reflect_step = await self._run_phase(
                ReasoningPhase.REFLECT,
                reflect,
                context,
            )
            steps.append(reflect_step)

            verify_step = await self._run_phase(
                ReasoningPhase.VERIFY,
                verify,
                context,
            )
            steps.append(verify_step)

            confidences = [s.confidence for s in steps if s.confidence > 0]
            overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            if verify_step.metadata.get("verified", False):
                break
            if reflect_step.metadata.get("stop_iteration", False):
                break

        requires_reflection = any(
            s.phase == ReasoningPhase.REFLECT and s.metadata.get("needs_followup")
            for s in steps
        )

        for step in steps:
            context.add_reasoning(f"[{step.phase.value}] {step.content}")

        logger.debug(
            "reasoning_completed",
            agent_id=self._agent_id,
            steps=len(steps),
            confidence=round(overall_confidence, 3),
        )

        return ReasoningResult(
            steps=steps,
            overall_confidence=overall_confidence,
            recommended_tools=list(dict.fromkeys(recommended_tools)),
            requires_reflection=requires_reflection,
            metadata={"iterations": iteration},
        )

    async def _run_phase(
        self,
        phase: ReasoningPhase,
        handler: Any,
        context: AgentContext,
    ) -> ReasoningStep:
        start = time.perf_counter()
        outcome = await handler(context, phase)
        elapsed = (time.perf_counter() - start) * 1000

        if isinstance(outcome, ReasoningStep):
            return outcome.model_copy(update={"duration_ms": elapsed})

        if isinstance(outcome, dict):
            return ReasoningStep(
                phase=phase,
                content=str(outcome.get("content", "")),
                confidence=float(outcome.get("confidence", 0.5)),
                duration_ms=elapsed,
                metadata=dict(outcome.get("metadata", {})),
            )

        return ReasoningStep(
            phase=phase,
            content=str(outcome),
            duration_ms=elapsed,
        )
