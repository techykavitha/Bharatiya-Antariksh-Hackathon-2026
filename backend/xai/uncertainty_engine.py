"""Uncertainty estimation engine for explainability."""

from __future__ import annotations

from backend.agents.specialized.agent_reflection import ReflectionResult, ReflectionSignal
from backend.agents.specialized.agent_validator import ValidationResult as AgentValidationResult
from backend.agents.tools.abstract_tool import ToolResult
from backend.decision.decision_request import DecisionRequest
from backend.xai.explanation_models import UncertaintyDimension
from backend.xai.explanation_report import ExplanationInput, UncertaintyComponent, UncertaintyEstimate


_DEFAULT_WEIGHTS: dict[UncertaintyDimension, float] = {
    UncertaintyDimension.FORECAST: 0.25,
    UncertaintyDimension.MISSING_DATA: 0.30,
    UncertaintyDimension.MODEL: 0.25,
    UncertaintyDimension.SIMULATION: 0.20,
}


class UncertaintyEngine:
    """Estimates multi-dimensional uncertainty for recommendations."""

    async def estimate(self, explanation_input: ExplanationInput) -> UncertaintyEstimate:
        forecast = self._forecast_uncertainty(explanation_input)
        missing = self._missing_data_uncertainty(explanation_input)
        model = self._model_uncertainty(explanation_input)
        simulation = self._simulation_uncertainty(explanation_input)

        components = [
            UncertaintyComponent(
                dimension=UncertaintyDimension.FORECAST,
                score=forecast,
                weight=_DEFAULT_WEIGHTS[UncertaintyDimension.FORECAST],
                description="Uncertainty in forecast inputs and horizon reliability",
                mitigations=self._forecast_mitigations(forecast),
            ),
            UncertaintyComponent(
                dimension=UncertaintyDimension.MISSING_DATA,
                score=missing,
                weight=_DEFAULT_WEIGHTS[UncertaintyDimension.MISSING_DATA],
                description="Gaps in required observations, tools, or context",
                mitigations=self._missing_data_mitigations(missing),
            ),
            UncertaintyComponent(
                dimension=UncertaintyDimension.MODEL,
                score=model,
                weight=_DEFAULT_WEIGHTS[UncertaintyDimension.MODEL],
                description="Model and reasoning confidence limitations",
                mitigations=self._model_mitigations(model),
            ),
            UncertaintyComponent(
                dimension=UncertaintyDimension.SIMULATION,
                score=simulation,
                weight=_DEFAULT_WEIGHTS[UncertaintyDimension.SIMULATION],
                description="Dependence on simulation not yet executed",
                mitigations=self._simulation_mitigations(simulation),
            ),
        ]

        overall = sum(c.score * c.weight for c in components)
        summary = self._build_summary(overall, components)

        return UncertaintyEstimate(
            overall=round(overall, 3),
            components=components,
            forecast_uncertainty=round(forecast, 3),
            missing_data=round(missing, 3),
            model_uncertainty=round(model, 3),
            simulation_uncertainty=round(simulation, 3),
            summary=summary,
        )

    def _forecast_uncertainty(self, explanation_input: ExplanationInput) -> float:
        decision = explanation_input.decision_request
        if not decision:
            return 0.5

        if decision.context.forecast_reference:
            return 0.25

        climate = decision.context.climate_state
        if climate and climate.forecast_references:
            return 0.3

        reflection = explanation_input.reflection
        if reflection and any(f.signal == ReflectionSignal.NEED_FORECAST for f in reflection.findings):
            return 0.85

        return 0.65

    def _missing_data_uncertainty(self, explanation_input: ExplanationInput) -> float:
        score = 0.2
        reflection = explanation_input.reflection
        if reflection:
            if any(f.signal == ReflectionSignal.MISSING_CONTEXT for f in reflection.findings):
                score += 0.35
            if reflection.needs_another_agent:
                score += 0.1

        validation = explanation_input.validation
        if validation and not validation.valid:
            score += min(len(validation.issues) * 0.08, 0.35)

        tool_results = explanation_input.tool_results
        if tool_results:
            failed = sum(1 for r in tool_results if not r.success)
            score += (failed / len(tool_results)) * 0.3
        elif not explanation_input.tool_output_records:
            score += 0.25

        return min(score, 1.0)

    def _model_uncertainty(self, explanation_input: ExplanationInput) -> float:
        reasoning = explanation_input.reasoning
        if not reasoning:
            return 0.55

        uncertainty_signal = 0.0
        signals = reasoning.metadata.get("heat_signals") or reasoning.metadata.get("flood_signals") or {}
        if isinstance(signals, dict):
            raw = signals.get("uncertainty")
            if isinstance(raw, (int, float)):
                uncertainty_signal = float(raw)

        confidence_gap = 1.0 - reasoning.overall_confidence
        reflection = explanation_input.reflection
        if reflection and any(f.signal == ReflectionSignal.LOW_CONFIDENCE for f in reflection.findings):
            confidence_gap = max(confidence_gap, 0.4)

        return min(max((confidence_gap + uncertainty_signal) / 2.0, 0.1), 1.0)

    def _simulation_uncertainty(self, explanation_input: ExplanationInput) -> float:
        decision = explanation_input.decision_request
        reflection = explanation_input.reflection

        if decision and decision.need_simulation:
            if decision.context.simulation_reference:
                return 0.35
            return 0.75

        if reflection and reflection.needs_simulation:
            return 0.7

        if decision and decision.context.simulation_reference:
            return 0.2

        return 0.15

    def _forecast_mitigations(self, score: float) -> list[str]:
        if score < 0.4:
            return []
        return ["Acquire updated forecast", "Reduce decision horizon", "Use ensemble forecast"]

    def _missing_data_mitigations(self, score: float) -> list[str]:
        if score < 0.4:
            return []
        return ["Execute missing tools", "Request additional observations", "Delegate to complementary agent"]

    def _model_mitigations(self, score: float) -> list[str]:
        if score < 0.4:
            return []
        return ["Re-run reasoning with additional context", "Escalate to human review"]

    def _simulation_mitigations(self, score: float) -> list[str]:
        if score < 0.4:
            return []
        return ["Run scenario simulation", "Use digital twin projection", "Apply conservative action bounds"]

    def _build_summary(self, overall: float, components: list[UncertaintyComponent]) -> str:
        dominant = max(components, key=lambda c: c.score * c.weight)
        if overall >= 0.65:
            level = "high"
        elif overall >= 0.4:
            level = "moderate"
        else:
            level = "low"
        return (
            f"Overall uncertainty is {level} ({overall:.0%}). "
            f"Dominant factor: {dominant.dimension.value}."
        )
