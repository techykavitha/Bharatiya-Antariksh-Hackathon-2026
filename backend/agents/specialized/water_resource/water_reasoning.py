"""Water resource-specific reasoning pipeline."""

from __future__ import annotations

import time
from typing import Any

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningPhase, ReasoningResult, ReasoningStep
from backend.agents.specialized.water_resource.water_context import (
    WaterAnalysisSignals,
    WaterAvailabilityEstimate,
    WaterInputs,
)
from backend.agents.specialized.water_resource.water_models import (
    ReleaseStrategy,
    ReservoirStatus,
    WaterAvailabilityBand,
    WaterStressLevel,
)
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)

WATER_REASONING_STAGES: list[str] = [
    "observe",
    "current_storage",
    "forecast_rainfall",
    "river_conditions",
    "groundwater",
    "urban_demand",
    "agricultural_demand",
    "estimate_water_availability",
    "estimate_water_stress",
    "determine_reservoir_strategy",
    "generate_recommendations",
]


class WaterReasoningEngine:
    """
    Hydrological reasoning pipeline for water resource management.

    Stages: Observe → storage → rainfall → river → groundwater →
    urban demand → agricultural demand → availability → stress →
    reservoir strategy → recommendations.
    """

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id

    async def run(
        self,
        context: AgentContext,
        tool_results: list[ToolResult] | None = None,
    ) -> tuple[ReasoningResult, WaterAnalysisSignals]:
        start = time.perf_counter()
        steps: list[ReasoningStep] = []
        signals = WaterAnalysisSignals()
        inputs = self._resolve_inputs(context)
        outputs = self._index_tool_outputs(tool_results or [])

        steps.append(await self._observe(context, inputs))

        storage_step, signals = self._analyze_storage(outputs, signals)
        steps.append(storage_step)

        rainfall_step, signals = self._analyze_rainfall(outputs, signals)
        steps.append(rainfall_step)

        river_step, signals = self._analyze_river(outputs, signals)
        steps.append(river_step)

        gw_step, signals = self._analyze_groundwater(outputs, signals)
        steps.append(gw_step)

        urban_step, signals = self._analyze_urban_demand(outputs, signals)
        steps.append(urban_step)

        agri_step, signals = self._analyze_agricultural_demand(outputs, signals)
        steps.append(agri_step)

        avail_step, signals, availability = self._estimate_availability(outputs, signals)
        steps.append(avail_step)

        stress_step, signals, stress = self._estimate_stress(signals, availability)
        steps.append(stress_step)

        strategy_step, signals, strategy = self._determine_reservoir_strategy(outputs, signals)
        steps.append(strategy_step)

        rec_step = self._generate_recommendations(signals, stress, strategy, availability)
        steps.append(rec_step)

        for step in steps:
            context.add_reasoning(f"[{step.phase.value}] {step.content}")

        confidences = [s.confidence for s in steps if s.confidence > 0]
        overall = sum(confidences) / len(confidences) if confidences else 0.5
        elapsed = (time.perf_counter() - start) * 1000

        logger.debug(
            "water_reasoning_completed",
            agent_id=self._agent_id,
            stress_score=signals.stress_score,
            availability_score=signals.availability_score,
        )

        result = ReasoningResult(
            steps=steps,
            overall_confidence=overall,
            recommended_tools=[],
            metadata={
                "water_signals": signals.model_dump(),
                "stress_level": stress.value,
                "availability": availability.model_dump(),
                "release_strategy": strategy.value,
                "duration_ms": elapsed,
                "stages": WATER_REASONING_STAGES,
            },
        )
        return result, signals

    def _resolve_inputs(self, context: AgentContext) -> WaterInputs:
        stored = context.metadata.get("water_inputs")
        if isinstance(stored, WaterInputs):
            return stored
        return WaterInputs.from_request_context(context.request.context)

    def _index_tool_outputs(self, results: list[ToolResult]) -> dict[str, Any]:
        indexed: dict[str, Any] = {}
        for r in results:
            if r.success and isinstance(r.output, dict):
                indexed[r.tool_name] = r.output
        return indexed

    async def _observe(self, context: AgentContext, inputs: WaterInputs) -> ReasoningStep:
        basin = inputs.basin_id or inputs.region_id or "unspecified"
        return ReasoningStep(
            phase=ReasoningPhase.OBSERVE,
            content=(
                f"Observing water resource context for basin={basin}, "
                f"region={inputs.region_id}, climate={inputs.climate_state_available}"
            ),
            confidence=0.7,
            metadata={"basin_id": basin, "region_id": inputs.region_id},
        )

    def _analyze_storage(
        self,
        outputs: dict[str, Any],
        signals: WaterAnalysisSignals,
    ) -> tuple[ReasoningStep, WaterAnalysisSignals]:
        reservoir = outputs.get("reservoir_tool", {})
        level = float(reservoir.get("level_pct", 0.0))
        stressed = bool(reservoir.get("stressed"))
        overflow = bool(reservoir.get("overflow_risk"))
        score = float(reservoir.get("storage_score", level / 100.0))

        signals.storage_stressed = stressed
        signals.overflow_risk = overflow
        signals.storage_adequate = 30.0 <= level <= 80.0 and not stressed
        signals.storage_score = score

        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Storage level={level:.1f}%, stressed={stressed}, overflow_risk={overflow}",
            confidence=0.8 if reservoir else 0.35,
            metadata={"stage": "current_storage"},
        ), signals

    def _analyze_rainfall(
        self,
        outputs: dict[str, Any],
        signals: WaterAnalysisSignals,
    ) -> tuple[ReasoningStep, WaterAnalysisSignals]:
        rain = outputs.get("rainfall_tool", {})
        forecast = outputs.get("forecast_tool", {})
        deficit = bool(rain.get("rainfall_deficit"))
        score = float(rain.get("rainfall_score", 0.0))
        if forecast:
            score = max(score, float(forecast.get("forecast_score", 0.0)))

        signals.rainfall_deficit = deficit
        signals.rainfall_score = score

        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Rainfall deficit={deficit}, rainfall_score={score:.2f}",
            confidence=0.75 if rain else 0.4,
            metadata={"stage": "forecast_rainfall"},
        ), signals

    def _analyze_river(
        self,
        outputs: dict[str, Any],
        signals: WaterAnalysisSignals,
    ) -> tuple[ReasoningStep, WaterAnalysisSignals]:
        river = outputs.get("river_tool", {})
        healthy = bool(river.get("river_healthy", True))
        overflow = bool(river.get("overflow", False))
        score = float(river.get("river_score", 0.5))

        signals.river_healthy = healthy and not overflow
        signals.river_score = score

        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"River healthy={healthy}, overflow={overflow}, score={score:.2f}",
            confidence=0.75 if river else 0.35,
            metadata={"stage": "river_conditions"},
        ), signals

    def _analyze_groundwater(
        self,
        outputs: dict[str, Any],
        signals: WaterAnalysisSignals,
    ) -> tuple[ReasoningStep, WaterAnalysisSignals]:
        gw = outputs.get("groundwater_tool", {})
        declining = bool(gw.get("declining"))
        score = float(gw.get("groundwater_score", 0.5))

        signals.groundwater_declining = declining
        signals.groundwater_score = score

        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Groundwater declining={declining}, score={score:.2f}",
            confidence=0.75 if gw else 0.3,
            metadata={"stage": "groundwater"},
        ), signals

    def _analyze_urban_demand(
        self,
        outputs: dict[str, Any],
        signals: WaterAnalysisSignals,
    ) -> tuple[ReasoningStep, WaterAnalysisSignals]:
        demand = outputs.get("demand_tool", {})
        population = outputs.get("population_tool", {})
        urban_high = bool(demand.get("urban_demand_high"))
        urban_m3d = float(demand.get("urban_demand_m3d", 0.0))

        signals.urban_demand_high = urban_high or urban_m3d > 100_000

        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Urban demand={urban_m3d:.0f} m3/d, high={signals.urban_demand_high}",
            confidence=0.7 if demand or population else 0.35,
            metadata={"stage": "urban_demand"},
        ), signals

    def _analyze_agricultural_demand(
        self,
        outputs: dict[str, Any],
        signals: WaterAnalysisSignals,
    ) -> tuple[ReasoningStep, WaterAnalysisSignals]:
        demand = outputs.get("demand_tool", {})
        soil = outputs.get("soil_moisture_tool", {})
        agri_high = bool(demand.get("agricultural_demand_high"))
        irrigation = bool(soil.get("irrigation_needed"))
        agri_m3d = float(demand.get("agricultural_demand_m3d", 0.0))
        demand_score = float(demand.get("demand_score", 0.0))

        signals.agricultural_demand_high = agri_high or irrigation
        signals.demand_score = demand_score

        return ReasoningStep(
            phase=ReasoningPhase.THINK,
            content=f"Agricultural demand={agri_m3d:.0f} m3/d, irrigation_needed={irrigation}",
            confidence=0.75 if demand else 0.35,
            metadata={"stage": "agricultural_demand"},
        ), signals

    def _estimate_availability(
        self,
        outputs: dict[str, Any],
        signals: WaterAnalysisSignals,
    ) -> tuple[ReasoningStep, WaterAnalysisSignals, WaterAvailabilityEstimate]:
        reservoir = outputs.get("reservoir_tool", {})
        river = outputs.get("river_tool", {})
        demand = outputs.get("demand_tool", {})

        live_storage = float(reservoir.get("live_storage_mcm", 0.0))
        discharge = float(river.get("discharge_m3s", 0.0))
        supply_m3d = live_storage * 1000.0 / 30.0 + discharge * 86400.0 * 0.1
        demand_m3d = float(demand.get("total_demand_m3d", 0.0))
        surplus = supply_m3d - demand_m3d

        availability_score = (
            signals.storage_score * 0.30
            + signals.rainfall_score * 0.25
            + signals.river_score * 0.20
            + signals.groundwater_score * 0.25
        )
        signals.availability_score = round(availability_score, 3)

        if availability_score >= 0.75:
            band = WaterAvailabilityBand.ABUNDANT
        elif availability_score >= 0.55:
            band = WaterAvailabilityBand.ADEQUATE
        elif availability_score >= 0.40:
            band = WaterAvailabilityBand.MARGINAL
        elif availability_score >= 0.25:
            band = WaterAvailabilityBand.DEFICIT
        else:
            band = WaterAvailabilityBand.SEVERE_DEFICIT

        drivers: list[str] = []
        if signals.storage_stressed:
            drivers.append("reservoir_stress")
        if signals.rainfall_deficit:
            drivers.append("rainfall_deficit")
        if signals.groundwater_declining:
            drivers.append("groundwater_decline")

        estimate = WaterAvailabilityEstimate(
            band=band,
            score=availability_score,
            supply_m3d=round(supply_m3d, 2),
            demand_m3d=round(demand_m3d, 2),
            surplus_deficit_m3d=round(surplus, 2),
            drivers=drivers,
        )

        return ReasoningStep(
            phase=ReasoningPhase.VERIFY,
            content=f"Water availability={band.value} ({availability_score:.2f}), surplus={surplus:.0f} m3/d",
            confidence=0.85,
            metadata={"stage": "estimate_water_availability"},
        ), signals, estimate

    def _estimate_stress(
        self,
        signals: WaterAnalysisSignals,
        availability: WaterAvailabilityEstimate,
    ) -> tuple[ReasoningStep, WaterAnalysisSignals, WaterStressLevel]:
        stress_score = (
            signals.demand_score * 0.30
            + (1.0 - signals.availability_score) * 0.40
            + (0.3 if signals.groundwater_declining else 0.0)
            + (0.2 if signals.rainfall_deficit else 0.0)
            + (0.25 if signals.overflow_risk else 0.0)
        )
        stress_score = min(max(stress_score, 0.0), 1.0)
        signals.stress_score = round(stress_score, 3)
        signals.composite_score = round(
            (signals.availability_score + (1.0 - stress_score)) / 2.0, 3,
        )

        if stress_score >= 0.8:
            stress = WaterStressLevel.CRITICAL
        elif stress_score >= 0.65:
            stress = WaterStressLevel.SEVERE
        elif stress_score >= 0.50:
            stress = WaterStressLevel.HIGH
        elif stress_score >= 0.35:
            stress = WaterStressLevel.MODERATE
        elif stress_score >= 0.15:
            stress = WaterStressLevel.LOW
        else:
            stress = WaterStressLevel.NONE

        return ReasoningStep(
            phase=ReasoningPhase.VERIFY,
            content=f"Water stress={stress.value} (score={stress_score:.2f})",
            confidence=0.8,
            metadata={"stage": "estimate_water_stress"},
        ), signals, stress

    def _determine_reservoir_strategy(
        self,
        outputs: dict[str, Any],
        signals: WaterAnalysisSignals,
    ) -> tuple[ReasoningStep, WaterAnalysisSignals, ReleaseStrategy]:
        reservoir = outputs.get("reservoir_tool", {})
        raw_strategy = reservoir.get("recommended_release", ReleaseStrategy.HOLD.value)
        try:
            strategy = ReleaseStrategy(raw_strategy)
        except ValueError:
            strategy = ReleaseStrategy.HOLD

        if signals.rainfall_deficit and not signals.overflow_risk:
            strategy = ReleaseStrategy.CONSERVATION
        elif signals.overflow_risk:
            strategy = ReleaseStrategy.EMERGENCY_SPILL

        return ReasoningStep(
            phase=ReasoningPhase.ACT,
            content=f"Reservoir strategy={strategy.value}",
            confidence=0.85,
            metadata={"stage": "determine_reservoir_strategy"},
        ), signals, strategy

    def _generate_recommendations(
        self,
        signals: WaterAnalysisSignals,
        stress: WaterStressLevel,
        strategy: ReleaseStrategy,
        availability: WaterAvailabilityEstimate,
    ) -> ReasoningStep:
        recs: list[str] = []
        if signals.overflow_risk:
            recs.append("Initiate controlled reservoir releases to prevent downstream flooding")
        if strategy == ReleaseStrategy.CONSERVATION:
            recs.append("Implement water conservation measures and restrict non-essential usage")
        if signals.rainfall_deficit:
            recs.append("Monitor monsoon progression and prepare drought contingency plans")
        if signals.groundwater_declining:
            recs.append("Reduce groundwater extraction and promote recharge structures")
        if signals.agricultural_demand_high:
            recs.append("Optimize irrigation scheduling based on crop water requirements")
        if signals.urban_demand_high:
            recs.append("Review urban water supply allocation and demand management")
        if stress in (WaterStressLevel.SEVERE, WaterStressLevel.CRITICAL):
            recs.append("Activate inter-basin water transfer protocols if available")
        if availability.band == WaterAvailabilityBand.ABUNDANT:
            recs.append("Maintain current operations; storage levels are healthy")
        if not recs:
            recs.append("Continue routine monitoring; water resources within normal parameters")

        return ReasoningStep(
            phase=ReasoningPhase.ACT,
            content=f"Generated {len(recs)} recommendations",
            confidence=0.85,
            metadata={"stage": "generate_recommendations", "recommendations": recs},
        )
