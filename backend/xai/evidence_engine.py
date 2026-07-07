"""Evidence collection engine for explainability."""

from __future__ import annotations

from typing import Any

from backend.agents.schemas.response import ToolOutputRecord
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.tools.abstract_tool import ToolResult
from backend.decision.decision_request import DecisionRequest
from backend.xai.explanation_models import EvidenceSource
from backend.xai.explanation_report import EvidenceBundle, EvidenceItem, ExplanationInput


class EvidenceEngine:
    """Collects and categorizes evidence supporting agent recommendations."""

    async def collect(self, explanation_input: ExplanationInput) -> EvidenceBundle:
        items: list[EvidenceItem] = []
        climate: list[EvidenceItem] = []
        forecast: list[EvidenceItem] = []
        historical: list[EvidenceItem] = []
        twin: list[EvidenceItem] = []
        tool_evidence: list[EvidenceItem] = []
        reasoning_evidence: list[EvidenceItem] = []

        if explanation_input.decision_request:
            climate = self._collect_climate(explanation_input.decision_request)
            forecast = self._collect_forecast(explanation_input.decision_request)
            items.extend(climate)
            items.extend(forecast)

        tool_evidence = self._collect_tool_evidence(
            explanation_input.tool_results,
            explanation_input.tool_output_records,
        )
        items.extend(tool_evidence)

        historical = self._collect_historical(tool_evidence)
        items.extend(historical)

        twin = self._collect_digital_twin(tool_evidence)
        items.extend(twin)

        if explanation_input.reasoning:
            reasoning_evidence = self._collect_reasoning(explanation_input.reasoning)
            items.extend(reasoning_evidence)

        if explanation_input.decision_request:
            items.extend(self._collect_decision_rationale(explanation_input.decision_request))

        memory_refs = list(explanation_input.memory_references)
        for ref in memory_refs:
            items.append(EvidenceItem(
                source=EvidenceSource.MEMORY,
                label="memory_reference",
                value=ref,
                provenance="shared_memory",
            ))

        summary = self._summarize(items, memory_refs)

        return EvidenceBundle(
            items=items,
            climate_variables=climate,
            forecast_outputs=forecast,
            historical_events=historical,
            digital_twin_state=twin,
            memory_references=memory_refs,
            tool_evidence=tool_evidence,
            reasoning_evidence=reasoning_evidence,
            summary=summary,
        )

    def _collect_climate(self, decision: DecisionRequest) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        climate = decision.context.climate_state
        if not climate:
            return evidence

        for measurement in climate.measurements:
            evidence.append(EvidenceItem(
                source=EvidenceSource.CLIMATE_VARIABLE,
                label=measurement.variable.value,
                value=measurement.value,
                unit=measurement.unit,
                confidence=measurement.confidence,
                provenance=measurement.source or "climate_state",
                metadata={
                    "timestamp": measurement.timestamp.isoformat(),
                    "region_id": (
                        measurement.location.region_id
                        if measurement.location
                        else climate.location.region_id if climate.location else None
                    ),
                },
            ))

        if climate.digital_twin:
            evidence.append(EvidenceItem(
                source=EvidenceSource.DIGITAL_TWIN,
                label="digital_twin_snapshot",
                value=climate.digital_twin.twin_id,
                provenance="climate_state",
            ))

        return evidence

    def _collect_forecast(self, decision: DecisionRequest) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        ref = decision.context.forecast_reference
        if ref:
            evidence.append(EvidenceItem(
                source=EvidenceSource.FORECAST,
                label="forecast_reference",
                value=ref.forecast_id,
                provenance=ref.model_name,
                metadata={
                    "horizon_hours": ref.horizon_hours,
                    "generated_at": ref.generated_at.isoformat(),
                    "variables": [v.value for v in ref.variables],
                },
            ))
        return evidence

    def _collect_tool_evidence(
        self,
        tool_results: list[ToolResult],
        tool_records: list[ToolOutputRecord],
    ) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []

        for result in tool_results:
            if not result.success:
                continue
            evidence.extend(self._evidence_from_tool_output(result.tool_name, result.output))

        if not evidence:
            for record in tool_records:
                if not record.success:
                    continue
                evidence.extend(self._evidence_from_tool_output(record.tool_name, record.output))

        return evidence

    def _evidence_from_tool_output(self, tool_name: str, output: Any) -> list[EvidenceItem]:
        if not isinstance(output, dict):
            return [EvidenceItem(
                source=EvidenceSource.TOOL_OUTPUT,
                label=tool_name,
                value=output,
                provenance=tool_name,
            )]

        items: list[EvidenceItem] = []
        for key, value in output.items():
            if key in ("retrieved_at", "events", "districts", "heat_layers"):
                continue
            if isinstance(value, (int, float, str, bool)):
                items.append(EvidenceItem(
                    source=EvidenceSource.TOOL_OUTPUT,
                    label=f"{tool_name}.{key}",
                    value=value,
                    provenance=tool_name,
                ))

        if tool_name == "historical_heatwave_tool" and output.get("events"):
            for event in output["events"]:
                if isinstance(event, dict):
                    items.append(EvidenceItem(
                        source=EvidenceSource.HISTORICAL_EVENT,
                        label=f"historical_{event.get('event_id', 'event')}",
                        value=event.get("peak_temp_c") or event.get("peak_depth_m"),
                        provenance="historical_heatwave_tool",
                        metadata=event,
                    ))

        if tool_name == "historical_flood_tool" and output.get("events"):
            for event in output["events"]:
                if isinstance(event, dict):
                    items.append(EvidenceItem(
                        source=EvidenceSource.HISTORICAL_EVENT,
                        label=f"historical_{event.get('event_id', 'event')}",
                        value=event.get("peak_depth_m") or event.get("rainfall_mm"),
                        provenance="historical_flood_tool",
                        metadata=event,
                    ))

        if tool_name == "digital_twin_tool":
            items.append(EvidenceItem(
                source=EvidenceSource.DIGITAL_TWIN,
                label="digital_twin",
                value=output.get("twin_id"),
                provenance="digital_twin_tool",
                metadata={
                    "available": output.get("digital_twin_available"),
                    "lst_c": output.get("lst_c"),
                    "uhi_intensity_c": output.get("uhi_intensity_c"),
                },
            ))

        return items

    def _collect_historical(self, tool_evidence: list[EvidenceItem]) -> list[EvidenceItem]:
        return [e for e in tool_evidence if e.source == EvidenceSource.HISTORICAL_EVENT]

    def _collect_digital_twin(self, tool_evidence: list[EvidenceItem]) -> list[EvidenceItem]:
        return [e for e in tool_evidence if e.source == EvidenceSource.DIGITAL_TWIN]

    def _collect_reasoning(self, reasoning: ReasoningResult) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for index, step in enumerate(reasoning.steps):
            evidence.append(EvidenceItem(
                source=EvidenceSource.REASONING,
                label=f"reasoning_step_{index}",
                value=step.content,
                confidence=step.confidence,
                provenance=step.phase.value,
                metadata={"stage": step.metadata.get("stage")},
            ))

        signals = reasoning.metadata.get("heat_signals") or reasoning.metadata.get("flood_signals")
        if isinstance(signals, dict):
            for key, value in signals.items():
                if isinstance(value, (int, float, str, bool)):
                    evidence.append(EvidenceItem(
                        source=EvidenceSource.REASONING,
                        label=f"signal.{key}",
                        value=value,
                        provenance="reasoning_metadata",
                    ))
        return evidence

    def _collect_decision_rationale(self, decision: DecisionRequest) -> list[EvidenceItem]:
        return [
            EvidenceItem(
                source=EvidenceSource.DECISION,
                label=f"rationale_{index}",
                value=line,
                provenance="decision_request",
            )
            for index, line in enumerate(decision.rationale)
        ]

    def _summarize(self, items: list[EvidenceItem], memory_refs: list[str]) -> str:
        sources = {item.source.value for item in items}
        parts = [f"{len(items)} evidence items from {len(sources)} source types"]
        if memory_refs:
            parts.append(f"{len(memory_refs)} memory references")
        return "; ".join(parts) + "."
