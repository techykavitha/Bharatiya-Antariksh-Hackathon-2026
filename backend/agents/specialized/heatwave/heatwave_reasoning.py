"""Heatwave-specific reasoning pipeline."""

from __future__ import annotations

import time
from typing import Any

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningPhase, ReasoningResult, ReasoningStep
from backend.agents.specialized.heatwave.heatwave_context import (
    HeatAnalysisSignals,
    HeatIndexEstimate,
    HeatProbabilityEstimate,
    HeatwaveInputs,
)
from backend.agents.specialized.heatwave.heatwave_models import HeatProbabilityBand, HeatwaveSeverity
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)

HEATWAVE_REASONING_STAGES: list[str] = [
    "observe",
    "temperature_trend",
    "humidity",
    "heat_index",
    "urban_heat_island",
    "population_exposure",
    "historical_comparison",
    "estimate_severity",
    "estimate_duration",
    "estimate_vulnerability",
    "generate_recommendations",
]


class HeatwaveReasoningEngine:
    """Thermal stress reasoning pipeline for heatwave analysis."""

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id

    async def run(
        self,
        context: AgentContext,
        tool_results: list[ToolResult] | None = None,
    ) -> tuple[ReasoningResult, HeatAnalysisSignals]:
        start = time.perf_counter()
        steps: list[ReasoningStep] = []
        signals = HeatAnalysisSignals()
        inputs = self._resolve_inputs(context)
        outputs = self._index_tool_outputs(tool_results or [])

        steps.append(await self._observe(context, inputs))

        temp_step, signals = self._analyze_temperature(outputs, signals)
        steps.append(temp_step)

        humidity_step, signals, heat_index = self._analyze_humidity(outputs, signals)
        steps.append(humidity_step)

        hi_step, signals = self._analyze_heat_index(heat_index, signals)
        steps.append(hi_step)

        uhi_step, signals = self._analyze_uhi(outputs, signals)
        steps.append(uhi_step)

        pop_step, signals = self._analyze_population(outputs, signals)
        steps.append(pop_step)

        hist_step, signals = self._analyze_historical(outputs, signals)
        steps.append(hist_step)

        severity_step, signals, severity = self._estimate_severity(signals, heat_index)
        steps.append(severity_step)

        duration_step, signals, duration_days = self._estimate_duration(outputs, signals)
        steps.append(duration_step)

        vuln_step, signals = self._estimate_vulnerability(outputs, signals)
        steps.append(vuln_step)

        prob_step, signals, probability = self._estimate_probability(signals)
        steps.append(prob_step)

        rec_step = self._generate_recommendations(signals, severity, duration_days)
        steps.append(rec_step)

        for step in steps:
            context.add_reasoning(f"[{step.phase.value}] {step.content}")

        confidences = [s.confidence for s in steps if s.confidence > 0]
        overall = sum(confidences) / len(confidences) if confidences else 0.5
        elapsed = (time.perf_counter() - start) * 1000

        result = ReasoningResult(
            steps=steps,
            overall_confidence=overall,
            recommended_tools=[],
            metadata={
                "heat_signals": signals.model_dump(),
                "severity": severity.value,
                "duration_days": duration_days,
                "heat_index": heat_index.model_dump(),
                "probability": probability.model_dump(),
                "duration_ms": elapsed,
                "stages": HEATWAVE_REASONING_STAGES,
            },
        )
        return result, signals

    def _resolve_inputs(self, context: AgentContext) -> HeatwaveInputs:
        stored = context.metadata.get("heatwave_inputs")
        if isinstance(stored, HeatwaveInputs):
            return stored
        return HeatwaveInputs.from_request_context(context.request.context)

    def _index_tool_outputs(self, results: list[ToolResult]) -> dict[str, Any]:
        return {
            r.tool_name: r.output
            for r in results
            if r.success and isinstance(r.output, dict)
        }

    async def _observe(self, context: AgentContext, inputs: HeatwaveInputs) -> ReasoningStep:
        return ReasoningStep(
            phase=ReasoningPhase.OBSERVE,
            content=(
                f"Observing heatwave context for region={inputs.region_id}, "
                f"districts={inputs.districts or ['unspecified']}"
            ),
            confidence=0.7,
            metadata={"region_id": inputs.region_id},
        )

    def _analyze_temperature(
        self, outputs: dict[str, Any], signals: HeatAnalysisSignals,
    ) -> tuple[ReasoningStep, HeatAnalysisSignals]:
        temp = outputs.get("temperature_tool", {})
        elevated = bool(temp.get("elevated_temperature"))
        rising = bool(temp.get("rising_trend"))
        score = float(temp.get("temperature_score", 0.0))
        signals.elevated_temperature = elevated
        signals.rising_trend = rising
        signals.temperature_score = score
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Temperature elevated={elevated}, rising={rising}, score={score:.2f}",
            confidence=0.8 if temp else 0.35,
            metadata={"stage": "temperature_trend"},
        ), signals

    def _analyze_humidity(
        self, outputs: dict[str, Any], signals: HeatAnalysisSignals,
    ) -> tuple[ReasoningStep, HeatAnalysisSignals, HeatIndexEstimate]:
        humid = outputs.get("humidity_tool", {})
        hi_c = float(humid.get("heat_index_c", 0.0))
        wb_c = float(humid.get("wet_bulb_c", 0.0))
        high_stress = bool(humid.get("high_humidity_stress"))
        dangerous = bool(humid.get("dangerous_heat"))
        score = float(humid.get("humidity_score", 0.0))
        signals.high_humidity_stress = high_stress
        signals.humidity_score = score

        discomfort = "comfortable"
        if dangerous:
            discomfort = "dangerous"
        elif hi_c >= 41.0:
            discomfort = "extreme_caution"
        elif hi_c >= 32.0:
            discomfort = "caution"

        estimate = HeatIndexEstimate(
            heat_index_c=hi_c,
            wet_bulb_c=wb_c,
            discomfort_level=discomfort,
            dangerous=dangerous,
        )
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Heat index={hi_c:.1f}C, wet bulb={wb_c:.1f}C, stress={high_stress}",
            confidence=0.75 if humid else 0.3,
            metadata={"stage": "humidity"},
        ), signals, estimate

    def _analyze_heat_index(
        self, heat_index: HeatIndexEstimate, signals: HeatAnalysisSignals,
    ) -> tuple[ReasoningStep, HeatAnalysisSignals]:
        score = min(heat_index.heat_index_c / 55.0, 1.0)
        signals.heat_index_score = score
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Heat index analysis: {heat_index.discomfort_level}",
            confidence=0.8,
            metadata={"stage": "heat_index"},
        ), signals

    def _analyze_uhi(
        self, outputs: dict[str, Any], signals: HeatAnalysisSignals,
    ) -> tuple[ReasoningStep, HeatAnalysisSignals]:
        lst = outputs.get("lst_tool", {})
        urban = outputs.get("urban_density_tool", {})
        ndvi = outputs.get("ndvi_tool", {})
        uhi = bool(lst.get("urban_heat_island"))
        score = max(float(lst.get("uhi_score", 0.0)), float(urban.get("urban_score", 0.0)))
        signals.urban_heat_island = uhi
        signals.uhi_score = score
        signals.low_vegetation = bool(ndvi.get("low_vegetation"))
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Urban heat island={uhi}, uhi_score={score:.2f}",
            confidence=0.75 if lst or urban else 0.35,
            metadata={"stage": "urban_heat_island"},
        ), signals

    def _analyze_population(
        self, outputs: dict[str, Any], signals: HeatAnalysisSignals,
    ) -> tuple[ReasoningStep, HeatAnalysisSignals]:
        pop = outputs.get("population_tool", {})
        high = bool(pop.get("high_exposure"))
        signals.high_population_exposure = high
        signals.vulnerability_score = float(
            outputs.get("health_risk_tool", {}).get("vulnerability_score", 0.3)
        )
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Population exposure high={high}, vulnerable={pop.get('vulnerable_population', 0)}",
            confidence=0.7 if pop else 0.35,
            metadata={"stage": "population_exposure"},
        ), signals

    def _analyze_historical(
        self, outputs: dict[str, Any], signals: HeatAnalysisSignals,
    ) -> tuple[ReasoningStep, HeatAnalysisSignals]:
        hist = outputs.get("historical_heatwave_tool", {})
        analog = bool(hist.get("historical_analog"))
        score = float(hist.get("historical_score", 0.0))
        signals.historical_analog = analog
        signals.historical_score = score
        health = outputs.get("health_risk_tool", {})
        signals.compound_aqi_risk = bool(health.get("compound_aqi_heat_risk"))
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Historical analog={analog}, compound_aqi={signals.compound_aqi_risk}",
            confidence=0.7 if hist else 0.25,
            metadata={"stage": "historical_comparison"},
        ), signals

    def _estimate_severity(
        self, signals: HeatAnalysisSignals, heat_index: HeatIndexEstimate,
    ) -> tuple[ReasoningStep, HeatAnalysisSignals, HeatwaveSeverity]:
        composite = (
            signals.temperature_score * 0.30
            + signals.heat_index_score * 0.30
            + signals.uhi_score * 0.20
            + signals.vulnerability_score * 0.20
        )
        signals.composite_score = round(composite, 3)

        if composite >= 0.85 or heat_index.dangerous:
            severity = HeatwaveSeverity.EXTREME
        elif composite >= 0.70 or heat_index.heat_index_c >= 45.0:
            severity = HeatwaveSeverity.SEVERE
        elif composite >= 0.55 or heat_index.heat_index_c >= 41.0:
            severity = HeatwaveSeverity.HIGH
        elif composite >= 0.35:
            severity = HeatwaveSeverity.MODERATE
        elif composite >= 0.15:
            severity = HeatwaveSeverity.LOW
        else:
            severity = HeatwaveSeverity.NONE

        return ReasoningStep(
            phase=ReasoningPhase.VERIFY,
            content=f"Heatwave severity={severity.value} (composite={composite:.2f})",
            confidence=0.85,
            metadata={"stage": "estimate_severity"},
        ), signals, severity

    def _estimate_duration(
        self, outputs: dict[str, Any], signals: HeatAnalysisSignals,
    ) -> tuple[ReasoningStep, HeatAnalysisSignals, int]:
        forecast = outputs.get("forecast_tool", {})
        temp = outputs.get("temperature_tool", {})
        duration = 3
        if bool(forecast.get("worsening_trend")) and bool(temp.get("rising_trend")):
            duration = 7
        elif signals.elevated_temperature:
            duration = 5
        return ReasoningStep(
            phase=ReasoningPhase.VERIFY,
            content=f"Estimated duration={duration} days",
            confidence=0.7,
            metadata={"stage": "estimate_duration", "duration_days": duration},
        ), signals, duration

    def _estimate_vulnerability(
        self, outputs: dict[str, Any], signals: HeatAnalysisSignals,
    ) -> tuple[ReasoningStep, HeatAnalysisSignals]:
        health = outputs.get("health_risk_tool", {})
        infra_risk = signals.urban_heat_island and signals.high_population_exposure
        signals.infrastructure_at_risk = infra_risk
        vuln = float(health.get("vulnerability_score", signals.vulnerability_score))
        signals.vulnerability_score = vuln
        return ReasoningStep(
            phase=ReasoningPhase.VERIFY,
            content=f"Vulnerability score={vuln:.2f}, infrastructure_at_risk={infra_risk}",
            confidence=0.75,
            metadata={"stage": "estimate_vulnerability"},
        ), signals

    def _estimate_probability(
        self, signals: HeatAnalysisSignals,
    ) -> tuple[ReasoningStep, HeatAnalysisSignals, HeatProbabilityEstimate]:
        composite = signals.composite_score
        if composite >= 0.75:
            band = HeatProbabilityBand.VERY_HIGH
        elif composite >= 0.55:
            band = HeatProbabilityBand.HIGH
        elif composite >= 0.35:
            band = HeatProbabilityBand.MEDIUM
        elif composite >= 0.15:
            band = HeatProbabilityBand.LOW
        else:
            band = HeatProbabilityBand.VERY_LOW

        drivers = []
        if signals.elevated_temperature:
            drivers.append("elevated_temperature")
        if signals.rising_trend:
            drivers.append("rising_trend")
        if signals.urban_heat_island:
            drivers.append("urban_heat_island")
        if signals.high_humidity_stress:
            drivers.append("humidity_stress")

        estimate = HeatProbabilityEstimate(band=band, score=composite, drivers=drivers)
        return ReasoningStep(
            phase=ReasoningPhase.VERIFY,
            content=f"Heatwave probability={band.value} ({composite:.2f})",
            confidence=0.8,
            metadata={"stage": "estimate_probability"},
        ), signals, estimate

    def _generate_recommendations(
        self,
        signals: HeatAnalysisSignals,
        severity: HeatwaveSeverity,
        duration_days: int,
    ) -> ReasoningStep:
        recs: list[str] = []
        if severity in (HeatwaveSeverity.HIGH, HeatwaveSeverity.SEVERE, HeatwaveSeverity.EXTREME):
            recs.append("Activate public heat alerts and cooling center operations")
        if signals.urban_heat_island:
            recs.append("Deploy urban cooling measures including reflective roofs and misting")
        if signals.high_population_exposure:
            recs.append("Prioritize vulnerable populations for outreach and hydration")
        if duration_days >= 5:
            recs.append("Modify school and work hours during peak afternoon heat")
        if signals.compound_aqi_risk:
            recs.append("Issue compound heat-AQI health advisories")
        if not recs:
            recs.append("Continue routine thermal monitoring; conditions within seasonal norms")

        return ReasoningStep(
            phase=ReasoningPhase.ACT,
            content=f"Generated {len(recs)} recommendations",
            confidence=0.85,
            metadata={"stage": "generate_recommendations", "recommendations": recs},
        )
