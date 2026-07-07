"""Confidence estimation engine for explainability."""

from __future__ import annotations

from backend.agents.specialized.agent_reflection import ReflectionResult
from backend.agents.specialized.agent_validator import ValidationResult as AgentValidationResult
from backend.agents.tools.abstract_tool import ToolResult
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.xai.explanation_models import ConfidenceDimension
from backend.xai.explanation_report import ConfidenceComponent, ConfidenceEstimate, ExplanationInput


_DEFAULT_WEIGHTS: dict[ConfidenceDimension, float] = {
    ConfidenceDimension.MODEL: 0.25,
    ConfidenceDimension.DATA_QUALITY: 0.25,
    ConfidenceDimension.FORECAST_RELIABILITY: 0.20,
    ConfidenceDimension.TOOL_CONSISTENCY: 0.15,
    ConfidenceDimension.HISTORICAL_SIMILARITY: 0.15,
}


class ConfidenceEngine:
    """Estimates multi-dimensional confidence for recommendations."""

    async def estimate(self, explanation_input: ExplanationInput) -> ConfidenceEstimate:
        model = self._model_confidence(explanation_input)
        data_quality = self._data_quality(explanation_input)
        forecast = self._forecast_reliability(explanation_input)
        tool_consistency = self._tool_consistency(explanation_input.tool_results)
        historical = self._historical_similarity(explanation_input)

        components = [
            ConfidenceComponent(
                dimension=ConfidenceDimension.MODEL,
                score=model,
                weight=_DEFAULT_WEIGHTS[ConfidenceDimension.MODEL],
                rationale="Aggregated reasoning and RL model confidence",
            ),
            ConfidenceComponent(
                dimension=ConfidenceDimension.DATA_QUALITY,
                score=data_quality,
                weight=_DEFAULT_WEIGHTS[ConfidenceDimension.DATA_QUALITY],
                rationale="Input validation and tool execution success",
            ),
            ConfidenceComponent(
                dimension=ConfidenceDimension.FORECAST_RELIABILITY,
                score=forecast,
                weight=_DEFAULT_WEIGHTS[ConfidenceDimension.FORECAST_RELIABILITY],
                rationale="Forecast availability and decision context references",
            ),
            ConfidenceComponent(
                dimension=ConfidenceDimension.TOOL_CONSISTENCY,
                score=tool_consistency,
                weight=_DEFAULT_WEIGHTS[ConfidenceDimension.TOOL_CONSISTENCY],
                rationale="Cross-tool output agreement and completeness",
            ),
            ConfidenceComponent(
                dimension=ConfidenceDimension.HISTORICAL_SIMILARITY,
                score=historical,
                weight=_DEFAULT_WEIGHTS[ConfidenceDimension.HISTORICAL_SIMILARITY],
                rationale="Historical analog strength from tool and reasoning signals",
            ),
        ]

        overall = sum(c.score * c.weight for c in components)
        summary = self._build_summary(overall, components)

        return ConfidenceEstimate(
            overall=round(overall, 3),
            components=components,
            model_confidence=round(model, 3),
            data_quality=round(data_quality, 3),
            forecast_reliability=round(forecast, 3),
            tool_consistency=round(tool_consistency, 3),
            historical_similarity=round(historical, 3),
            summary=summary,
        )

    def _model_confidence(self, explanation_input: ExplanationInput) -> float:
        scores: list[float] = []
        if explanation_input.reasoning:
            scores.append(explanation_input.reasoning.overall_confidence)
        if explanation_input.reflection:
            scores.append(explanation_input.reflection.confidence)
        if explanation_input.decision_request:
            scores.append(explanation_input.decision_request.confidence)
        response = explanation_input.decision_response
        if response and response.confidence > 0:
            scores.append(response.confidence)
        if not scores:
            return 0.5
        return sum(scores) / len(scores)

    def _data_quality(self, explanation_input: ExplanationInput) -> float:
        validation = explanation_input.validation
        if validation is None:
            tool_results = explanation_input.tool_results
            if not tool_results:
                return 0.5
            success_rate = sum(1 for r in tool_results if r.success) / len(tool_results)
            return min(max(success_rate, 0.2), 1.0)

        if validation.valid:
            base = 0.85
        else:
            base = 0.45

        penalty = min(len(validation.issues) * 0.05, 0.35)
        return max(base - penalty, 0.1)

    def _forecast_reliability(self, explanation_input: ExplanationInput) -> float:
        decision = explanation_input.decision_request
        if not decision:
            return 0.5

        score = 0.4
        if decision.context.forecast_reference:
            score += 0.35
        climate = decision.context.climate_state
        if climate and climate.forecast_references:
            score += 0.15
        if decision.metadata.get("forecast_available"):
            score += 0.1
        return min(score, 1.0)

    def _tool_consistency(self, tool_results: list[ToolResult]) -> float:
        if not tool_results:
            return 0.5

        success_rate = sum(1 for r in tool_results if r.success) / len(tool_results)
        if success_rate < 1.0:
            return round(success_rate * 0.8, 3)

        scores: list[float] = []
        outputs = {
            r.tool_name: r.output for r in tool_results
            if r.success and isinstance(r.output, dict)
        }

        temp_score = outputs.get("temperature_tool", {}).get("temperature_score")
        hi_score = outputs.get("humidity_tool", {}).get("humidity_score")
        if isinstance(temp_score, (int, float)) and isinstance(hi_score, (int, float)):
            delta = abs(float(temp_score) - float(hi_score))
            scores.append(max(1.0 - delta, 0.3))

        rainfall = outputs.get("rainfall_tool", {}).get("rainfall_score")
        river = outputs.get("river_tool", {}).get("river_score")
        if isinstance(rainfall, (int, float)) and isinstance(river, (int, float)):
            delta = abs(float(rainfall) - float(river))
            scores.append(max(1.0 - delta * 0.5, 0.3))

        if scores:
            return round((success_rate + sum(scores) / len(scores)) / 2.0, 3)
        return round(success_rate, 3)

    def _historical_similarity(self, explanation_input: ExplanationInput) -> float:
        reasoning = explanation_input.reasoning
        if reasoning:
            signals = (
                reasoning.metadata.get("heat_signals")
                or reasoning.metadata.get("flood_signals")
                or reasoning.metadata.get("water_signals")
                or {}
            )
            if isinstance(signals, dict):
                if signals.get("historical_analog"):
                    return 0.85
                hist_score = signals.get("historical_score")
                if isinstance(hist_score, (int, float)):
                    return min(max(float(hist_score), 0.2), 1.0)

        for result in explanation_input.tool_results:
            if not result.success or not isinstance(result.output, dict):
                continue
            if result.output.get("historical_analog"):
                return 0.8
            hist_score = result.output.get("historical_score")
            if isinstance(hist_score, (int, float)):
                return min(max(float(hist_score), 0.2), 1.0)

        return 0.35

    def _build_summary(self, overall: float, components: list[ConfidenceComponent]) -> str:
        weakest = min(components, key=lambda c: c.score)
        if overall >= 0.75:
            level = "high"
        elif overall >= 0.55:
            level = "moderate"
        else:
            level = "low"
        return (
            f"Overall confidence is {level} ({overall:.0%}). "
            f"Lowest dimension: {weakest.dimension.value} ({weakest.score:.0%})."
        )
