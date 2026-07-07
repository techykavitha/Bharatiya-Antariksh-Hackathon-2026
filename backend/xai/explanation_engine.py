"""Central explainability engine orchestrating all XAI components."""

from __future__ import annotations

import time
from typing import Any

from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.config.logger import get_logger
from backend.xai.alternative_actions import AlternativeActionsEngine
from backend.xai.confidence_engine import ConfidenceEngine
from backend.xai.counterfactual_engine import CounterfactualEngine
from backend.xai.evidence_engine import EvidenceEngine
from backend.xai.explanation_models import ExplanationType
from backend.xai.explanation_report import ExplainabilityReport, ExplanationInput
from backend.xai.reasoning_trace import ReasoningTraceBuilder
from backend.xai.uncertainty_engine import UncertaintyEngine

logger = get_logger(__name__)


class ExplanationEngine:
    """
    Centralized Explainability Framework for Hyperion Climate Twin.

    Produces standardized ``ExplainabilityReport`` objects for specialized
    agents and the RL optimization service.
    """

    def __init__(self) -> None:
        self._trace_builder = ReasoningTraceBuilder()
        self._evidence_engine = EvidenceEngine()
        self._confidence_engine = ConfidenceEngine()
        self._uncertainty_engine = UncertaintyEngine()
        self._alternatives_engine = AlternativeActionsEngine()
        self._counterfactual_engine = CounterfactualEngine()
        self._last_report: ExplainabilityReport | None = None

    @property
    def last_report(self) -> ExplainabilityReport | None:
        return self._last_report

    @classmethod
    async def create(cls) -> ExplanationEngine:
        return cls()

    async def explain(self, explanation_input: ExplanationInput) -> ExplainabilityReport:
        """Generate a full explainability report from pipeline artifacts."""
        start = time.perf_counter()
        explanation_type = explanation_input.explanation_type

        reasoning_trace = await self._maybe_trace(explanation_type, explanation_input)
        evidence = await self._maybe_evidence(explanation_type, explanation_input)
        confidence = await self._maybe_confidence(explanation_type, explanation_input)
        uncertainty = await self._maybe_uncertainty(explanation_type, explanation_input)
        alternatives = await self._maybe_alternatives(explanation_type, explanation_input)
        counterfactuals = await self._maybe_counterfactuals(explanation_type, explanation_input)

        executive_summary = self._build_executive_summary(
            explanation_input,
            confidence,
            uncertainty,
            alternatives,
        )
        chosen_summary = self._chosen_action_summary(alternatives)
        caveats = self._build_caveats(explanation_input, uncertainty)
        elapsed = (time.perf_counter() - start) * 1000

        report = ExplainabilityReport(
            request_id=explanation_input.request_id,
            agent_id=explanation_input.agent_id,
            explanation_type=explanation_type,
            executive_summary=executive_summary,
            reasoning_trace=reasoning_trace,
            evidence=evidence,
            confidence=confidence,
            uncertainty=uncertainty,
            alternatives=alternatives,
            counterfactuals=counterfactuals,
            chosen_action_summary=chosen_summary,
            recommendations=list(explanation_input.recommendations),
            caveats=caveats,
            processing_time_ms=round(elapsed, 2),
            metadata=dict(explanation_input.metadata),
        )

        self._last_report = report
        logger.debug(
            "explanation_generated",
            request_id=explanation_input.request_id,
            agent_id=explanation_input.agent_id,
            confidence=confidence.overall,
            uncertainty=uncertainty.overall,
            processing_ms=report.processing_time_ms,
        )
        return report

    async def explain_decision(
        self,
        decision_request: DecisionRequest,
        *,
        decision_response: DecisionResponse | None = None,
        request_id: str | None = None,
        recommendations: list[str] | None = None,
    ) -> ExplainabilityReport:
        """Convenience API for decision + RL explainability."""
        return await self.explain(ExplanationInput(
            request_id=request_id or decision_request.context.request_id or decision_request.decision_id,
            agent_id=decision_request.agent_id,
            explanation_type=ExplanationType.RL if decision_response else ExplanationType.DECISION,
            decision_request=decision_request,
            decision_response=decision_response,
            recommendations=recommendations or [],
            metadata={"decision_type": decision_request.decision_type.value},
        ))

    async def explain_pipeline(self, explanation_input: ExplanationInput) -> ExplainabilityReport:
        """Full pipeline explanation with all components."""
        enriched = explanation_input.model_copy(
            update={"explanation_type": ExplanationType.FULL_PIPELINE},
        )
        return await self.explain(enriched)

    async def _maybe_trace(
        self,
        explanation_type: ExplanationType,
        explanation_input: ExplanationInput,
    ) -> Any:
        if explanation_type in (
            ExplanationType.REASONING,
            ExplanationType.FULL_PIPELINE,
        ):
            return await self._trace_builder.build(
                explanation_input.reasoning,
                tool_results=explanation_input.tool_results,
            )
        return await self._trace_builder.build(None)

    async def _maybe_evidence(
        self,
        explanation_type: ExplanationType,
        explanation_input: ExplanationInput,
    ) -> Any:
        if explanation_type in (
            ExplanationType.REASONING,
            ExplanationType.DECISION,
            ExplanationType.RL,
            ExplanationType.FULL_PIPELINE,
        ):
            return await self._evidence_engine.collect(explanation_input)
        return await self._evidence_engine.collect(ExplanationInput(
            request_id=explanation_input.request_id,
            agent_id=explanation_input.agent_id,
        ))

    async def _maybe_confidence(
        self,
        explanation_type: ExplanationType,
        explanation_input: ExplanationInput,
    ) -> Any:
        if explanation_type in (
            ExplanationType.DECISION,
            ExplanationType.RL,
            ExplanationType.FULL_PIPELINE,
        ):
            return await self._confidence_engine.estimate(explanation_input)
        return await self._confidence_engine.estimate(explanation_input)

    async def _maybe_uncertainty(
        self,
        explanation_type: ExplanationType,
        explanation_input: ExplanationInput,
    ) -> Any:
        if explanation_type in (
            ExplanationType.DECISION,
            ExplanationType.RL,
            ExplanationType.FULL_PIPELINE,
        ):
            return await self._uncertainty_engine.estimate(explanation_input)
        return await self._uncertainty_engine.estimate(explanation_input)

    async def _maybe_alternatives(
        self,
        explanation_type: ExplanationType,
        explanation_input: ExplanationInput,
    ) -> Any:
        if explanation_type in (
            ExplanationType.DECISION,
            ExplanationType.RL,
            ExplanationType.FULL_PIPELINE,
        ):
            return await self._alternatives_engine.analyze(explanation_input)
        return await self._alternatives_engine.analyze(explanation_input)

    async def _maybe_counterfactuals(
        self,
        explanation_type: ExplanationType,
        explanation_input: ExplanationInput,
    ) -> Any:
        if explanation_type in (
            ExplanationType.DECISION,
            ExplanationType.RL,
            ExplanationType.FULL_PIPELINE,
        ):
            return await self._counterfactual_engine.analyze(explanation_input)
        return await self._counterfactual_engine.analyze(explanation_input)

    def _build_executive_summary(
        self,
        explanation_input: ExplanationInput,
        confidence: Any,
        uncertainty: Any,
        alternatives: Any,
    ) -> str:
        query = explanation_input.query or "climate decision"
        chosen = alternatives.chosen_action.description if alternatives.chosen_action else "no action selected"
        return (
            f"Explanation for {explanation_input.agent_id} regarding '{query}'. "
            f"Recommendation: {chosen}. "
            f"Confidence {confidence.overall:.0%}, uncertainty {uncertainty.overall:.0%}. "
            f"{evidence_summary(explanation_input)}"
        )

    def _chosen_action_summary(self, alternatives: Any) -> str:
        if not alternatives.chosen_action:
            return ""
        action = alternatives.chosen_action
        return (
            f"Selected action '{action.description}' "
            f"(cost={action.cost:.1f}, benefit={action.expected_benefit:.1f}, risk={action.risk.value}). "
            f"{alternatives.summary}"
        )

    def _build_caveats(self, explanation_input: ExplanationInput, uncertainty: Any) -> list[str]:
        caveats: list[str] = []
        if explanation_input.validation and not explanation_input.validation.valid:
            caveats.extend(explanation_input.validation.error_messages[:3])
        if explanation_input.reflection:
            caveats.extend(explanation_input.reflection.notes[:3])
        for component in uncertainty.components:
            if component.score >= 0.55:
                caveats.append(f"Elevated {component.dimension.value} uncertainty: {component.description}")
        return list(dict.fromkeys(caveats))


def evidence_summary(explanation_input: ExplanationInput) -> str:
    """Short evidence summary helper for executive text."""
    tool_count = len(explanation_input.tool_results) or len(explanation_input.tool_output_records)
    if tool_count:
        return f"Supported by {tool_count} tool outputs."
    return "Limited tool evidence available."
