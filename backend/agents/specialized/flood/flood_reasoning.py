"""Flood-specific reasoning pipeline."""

from __future__ import annotations

import time
from typing import Any

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningPhase, ReasoningResult, ReasoningStep
from backend.agents.specialized.flood.flood_context import (
    FloodAnalysisSignals,
    FloodInputs,
    FloodProbabilityEstimate,
)
from backend.agents.specialized.flood.flood_models import FloodProbabilityBand, FloodSeverity, FloodType
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)

FLOOD_REASONING_STAGES: list[str] = [
    "observe",
    "identify_heavy_rainfall",
    "identify_river_overflow",
    "check_terrain",
    "check_reservoirs",
    "compare_historical_events",
    "estimate_flood_probability",
    "estimate_severity",
    "estimate_uncertainty",
    "generate_recommendations",
]


class FloodReasoningEngine:
    """
    Hydrological reasoning pipeline for flood analysis.

    Stages: Observe → rainfall → river → terrain → reservoir →
    historical → probability → severity → uncertainty → recommendations.
    """

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id

    async def run(
        self,
        context: AgentContext,
        tool_results: list[ToolResult] | None = None,
    ) -> tuple[ReasoningResult, FloodAnalysisSignals]:
        start = time.perf_counter()
        steps: list[ReasoningStep] = []
        signals = FloodAnalysisSignals()
        inputs = self._resolve_inputs(context)
        outputs = self._index_tool_outputs(tool_results or [])

        steps.append(await self._observe(context, inputs))

        rainfall_step, signals = self._analyze_rainfall(outputs, signals)
        steps.append(rainfall_step)

        river_step, signals = self._analyze_river(outputs, signals)
        steps.append(river_step)

        terrain_step, signals = self._analyze_terrain(outputs, signals)
        steps.append(terrain_step)

        reservoir_step, signals = self._analyze_reservoir(outputs, signals)
        steps.append(reservoir_step)

        historical_step, signals = self._analyze_historical(outputs, signals)
        steps.append(historical_step)

        prob_step, signals, probability = self._estimate_probability(signals)
        steps.append(prob_step)

        severity_step, signals, severity = self._estimate_severity(signals, outputs)
        steps.append(severity_step)

        uncertainty_step, signals = self._estimate_uncertainty(signals, inputs)
        steps.append(uncertainty_step)

        rec_step = self._generate_recommendations(signals, severity, probability)
        steps.append(rec_step)

        for step in steps:
            context.add_reasoning(f"[{step.phase.value}] {step.content}")

        confidences = [s.confidence for s in steps if s.confidence > 0]
        overall = sum(confidences) / len(confidences) if confidences else 0.5
        elapsed = (time.perf_counter() - start) * 1000

        logger.debug(
            "flood_reasoning_completed",
            agent_id=self._agent_id,
            composite_score=signals.composite_score,
            severity=severity.value,
        )

        result = ReasoningResult(
            steps=steps,
            overall_confidence=overall,
            recommended_tools=[],
            metadata={
                "flood_signals": signals.model_dump(),
                "severity": severity.value,
                "probability": probability.model_dump(),
                "duration_ms": elapsed,
                "stages": FLOOD_REASONING_STAGES,
            },
        )
        return result, signals

    def _resolve_inputs(self, context: AgentContext) -> FloodInputs:
        stored = context.metadata.get("flood_inputs")
        if isinstance(stored, FloodInputs):
            return stored
        return FloodInputs.from_request_context(context.request.context)

    def _index_tool_outputs(self, results: list[ToolResult]) -> dict[str, Any]:
        indexed: dict[str, Any] = {}
        for r in results:
            if r.success and isinstance(r.output, dict):
                indexed[r.tool_name] = r.output
        return indexed

    async def _observe(self, context: AgentContext, inputs: FloodInputs) -> ReasoningStep:
        districts = inputs.districts or ["unspecified"]
        return ReasoningStep(
            phase=ReasoningPhase.OBSERVE,
            content=(
                f"Observing flood context for region={inputs.region_id}, "
                f"districts={districts}, climate={inputs.climate_state_available}"
            ),
            confidence=0.7,
            metadata={"region_id": inputs.region_id, "district_count": len(districts)},
        )

    def _analyze_rainfall(
        self,
        outputs: dict[str, Any],
        signals: FloodAnalysisSignals,
    ) -> tuple[ReasoningStep, FloodAnalysisSignals]:
        rain = outputs.get("rainfall_tool", {})
        forecast = outputs.get("forecast_tool", {})
        heavy = bool(rain.get("heavy_rainfall")) or bool(rain.get("flash_flood_risk"))
        score = float(rain.get("rainfall_score", 0.0))
        if forecast:
            score = max(score, float(forecast.get("forecast_score", 0.0)))
        signals.heavy_rainfall = heavy
        signals.rainfall_score = score
        signals.urban_pluvial_risk = bool(rain.get("flash_flood_risk"))
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Heavy rainfall identified={heavy}, score={score:.2f}",
            confidence=0.75 if rain else 0.4,
            metadata={"stage": "identify_heavy_rainfall"},
        ), signals

    def _analyze_river(
        self,
        outputs: dict[str, Any],
        signals: FloodAnalysisSignals,
    ) -> tuple[ReasoningStep, FloodAnalysisSignals]:
        river = outputs.get("river_tool", {})
        overflow = bool(river.get("overflow"))
        score = float(river.get("hydrology_score", 0.0))
        signals.river_overflow = overflow
        signals.hydrology_score = score
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"River overflow={overflow}, hydrology_score={score:.2f}",
            confidence=0.8 if river else 0.35,
            metadata={"stage": "identify_river_overflow"},
        ), signals

    def _analyze_terrain(
        self,
        outputs: dict[str, Any],
        signals: FloodAnalysisSignals,
    ) -> tuple[ReasoningStep, FloodAnalysisSignals]:
        terrain = outputs.get("terrain_tool", {})
        dem = outputs.get("dem_tool", {})
        vulnerable = bool(terrain.get("terrain_vulnerable")) or bool(dem.get("low_lying"))
        t_score = float(terrain.get("terrain_score", 0.0))
        d_score = float(dem.get("dem_score", 0.0))
        score = max(t_score, d_score)
        signals.terrain_vulnerable = vulnerable
        signals.terrain_score = score
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Terrain vulnerable={vulnerable}, terrain_score={score:.2f}",
            confidence=0.7 if terrain or dem else 0.3,
            metadata={"stage": "check_terrain"},
        ), signals

    def _analyze_reservoir(
        self,
        outputs: dict[str, Any],
        signals: FloodAnalysisSignals,
    ) -> tuple[ReasoningStep, FloodAnalysisSignals]:
        reservoir = outputs.get("reservoir_tool", {})
        stressed = bool(reservoir.get("stressed")) or bool(reservoir.get("overflow_risk"))
        score = float(reservoir.get("reservoir_score", 0.0))
        signals.reservoir_stressed = stressed
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Reservoir stressed={stressed}, level_score={score:.2f}",
            confidence=0.75 if reservoir else 0.3,
            metadata={"stage": "check_reservoirs"},
        ), signals

    def _analyze_historical(
        self,
        outputs: dict[str, Any],
        signals: FloodAnalysisSignals,
    ) -> tuple[ReasoningStep, FloodAnalysisSignals]:
        hist = outputs.get("historical_flood_tool", {})
        analog = bool(hist.get("historical_analog"))
        score = float(hist.get("historical_score", 0.0))
        signals.historical_analog = analog
        signals.historical_score = score
        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Historical analog={analog}, historical_score={score:.2f}",
            confidence=0.7 if hist else 0.25,
            metadata={"stage": "compare_historical_events"},
        ), signals

    def _estimate_probability(
        self,
        signals: FloodAnalysisSignals,
    ) -> tuple[ReasoningStep, FloodAnalysisSignals, FloodProbabilityEstimate]:
        composite = (
            signals.rainfall_score * 0.35
            + signals.hydrology_score * 0.30
            + signals.terrain_score * 0.20
            + signals.historical_score * 0.15
        )
        signals.composite_score = round(composite, 3)

        if composite >= 0.75:
            band = FloodProbabilityBand.VERY_HIGH
        elif composite >= 0.55:
            band = FloodProbabilityBand.HIGH
        elif composite >= 0.35:
            band = FloodProbabilityBand.MEDIUM
        elif composite >= 0.15:
            band = FloodProbabilityBand.LOW
        else:
            band = FloodProbabilityBand.VERY_LOW

        drivers = []
        if signals.heavy_rainfall:
            drivers.append("heavy_rainfall")
        if signals.river_overflow:
            drivers.append("river_overflow")
        if signals.terrain_vulnerable:
            drivers.append("terrain_vulnerability")
        if signals.reservoir_stressed:
            drivers.append("reservoir_stress")

        estimate = FloodProbabilityEstimate(
            band=band,
            score=composite,
            drivers=drivers,
        )
        return ReasoningStep(
            phase=ReasoningPhase.VERIFY,
            content=f"Flood probability={band.value} ({composite:.2f})",
            confidence=0.85,
            metadata={"stage": "estimate_flood_probability"},
        ), signals, estimate

    def _estimate_severity(
        self,
        signals: FloodAnalysisSignals,
        outputs: dict[str, Any],
    ) -> tuple[ReasoningStep, FloodAnalysisSignals, FloodSeverity]:
        depth = 0.0
        dem = outputs.get("dem_tool", {})
        if dem:
            depth = float(dem.get("estimated_depth_potential_m", 0.0))
        river = outputs.get("river_tool", {})
        if river.get("overflow"):
            depth = max(depth, 1.5)

        composite = signals.composite_score
        if composite >= 0.8 or depth >= 2.0:
            severity = FloodSeverity.CATASTROPHIC
        elif composite >= 0.65 or depth >= 1.0:
            severity = FloodSeverity.MAJOR
        elif composite >= 0.45 or depth >= 0.5:
            severity = FloodSeverity.MODERATE
        elif composite >= 0.2:
            severity = FloodSeverity.MINOR
        else:
            severity = FloodSeverity.NONE

        return ReasoningStep(
            phase=ReasoningPhase.VERIFY,
            content=f"Flood severity={severity.value}, depth_potential={depth:.2f}m",
            confidence=0.8,
            metadata={"stage": "estimate_severity", "depth_m": depth},
        ), signals, severity

    def _estimate_uncertainty(
        self,
        signals: FloodAnalysisSignals,
        inputs: FloodInputs,
    ) -> tuple[ReasoningStep, FloodAnalysisSignals]:
        missing = 0
        if not inputs.dem_available:
            missing += 1
        if not inputs.forecast_available:
            missing += 1
        if not inputs.historical_events:
            missing += 1
        if not inputs.climate_state_available:
            missing += 1
        uncertainty = min(0.2 + missing * 0.15, 0.9)
        signals.uncertainty = uncertainty
        return ReasoningStep(
            phase=ReasoningPhase.REFLECT,
            content=f"Uncertainty={uncertainty:.2f} (missing_inputs={missing})",
            confidence=1.0 - uncertainty,
            metadata={"stage": "estimate_uncertainty"},
        ), signals

    def _generate_recommendations(
        self,
        signals: FloodAnalysisSignals,
        severity: FloodSeverity,
        probability: Any,
    ) -> ReasoningStep:
        recs: list[str] = []
        if signals.heavy_rainfall:
            recs.append("Issue flash flood watch for vulnerable districts")
        if signals.river_overflow:
            recs.append("Activate river basin monitoring and downstream alerts")
        if signals.reservoir_stressed:
            recs.append("Coordinate with water resource management for controlled releases")
        if severity in (FloodSeverity.MAJOR, FloodSeverity.CATASTROPHIC):
            recs.append("Prepare emergency evacuation protocols")
        if not recs:
            recs.append("Continue routine monitoring; conditions within normal bounds")

        return ReasoningStep(
            phase=ReasoningPhase.ACT,
            content=f"Generated {len(recs)} recommendations",
            confidence=0.85,
            metadata={"stage": "generate_recommendations", "recommendations": recs},
        )
