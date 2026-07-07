"""Reasoning trace enrichment for explainability."""

from __future__ import annotations

from backend.agents.specialized.agent_reasoning import ReasoningResult, ReasoningStep
from backend.agents.tools.abstract_tool import ToolResult
from backend.xai.explanation_report import ReasoningTraceReport, TraceStep


class ReasoningTraceBuilder:
    """Builds enriched reasoning traces from agent reasoning artifacts."""

    async def build(
        self,
        reasoning: ReasoningResult | None,
        *,
        tool_results: list[ToolResult] | None = None,
    ) -> ReasoningTraceReport:
        if reasoning is None or not reasoning.steps:
            return ReasoningTraceReport(
                narrative=["No structured reasoning trace available"],
                overall_confidence=0.0,
            )

        tool_names = {r.tool_name for r in (tool_results or []) if r.success}
        steps: list[TraceStep] = []
        stages: list[str] = []

        for index, step in enumerate(reasoning.steps):
            stage = self._extract_stage(step)
            if stage:
                stages.append(stage)
            supporting = self._supporting_tools(step, tool_names)
            steps.append(TraceStep(
                step_index=index,
                phase=step.phase.value,
                content=step.content,
                confidence=step.confidence,
                duration_ms=step.duration_ms,
                stage=stage,
                supporting_tools=supporting,
                metadata=dict(step.metadata),
            ))

        narrative = self._build_narrative(steps)
        total_ms = sum(s.duration_ms for s in steps)

        return ReasoningTraceReport(
            steps=steps,
            narrative=narrative,
            stage_sequence=list(dict.fromkeys(stages)),
            overall_confidence=reasoning.overall_confidence,
            total_duration_ms=round(total_ms, 2),
            metadata={
                "recommended_tools": reasoning.recommended_tools,
                "requires_reflection": reasoning.requires_reflection,
                "reasoning_metadata": reasoning.metadata,
            },
        )

    def _extract_stage(self, step: ReasoningStep) -> str | None:
        stage = step.metadata.get("stage")
        if isinstance(stage, str) and stage:
            return stage
        return None

    def _supporting_tools(self, step: ReasoningStep, tool_names: set[str]) -> list[str]:
        recommended = step.metadata.get("recommended_tools")
        if isinstance(recommended, list):
            return [str(t) for t in recommended if str(t) in tool_names]
        stage = step.metadata.get("stage", "")
        stage_tool_map = {
            "temperature_trend": "temperature_tool",
            "humidity": "humidity_tool",
            "heat_index": "humidity_tool",
            "urban_heat_island": "lst_tool",
            "population_exposure": "population_tool",
            "historical_comparison": "historical_heatwave_tool",
        }
        mapped = stage_tool_map.get(str(stage))
        if mapped and mapped in tool_names:
            return [mapped]
        return []

    def _build_narrative(self, steps: list[TraceStep]) -> list[str]:
        narrative: list[str] = []
        for step in steps:
            prefix = f"Step {step.step_index + 1}"
            if step.stage:
                prefix += f" ({step.stage})"
            narrative.append(f"{prefix}: {step.content}")
        return narrative
