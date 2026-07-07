"""Dedicated tools for flood risk analysis."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.agents.specialized.flood.flood_context import FloodInputs
from backend.agents.specialized.flood.flood_models import FloodType
from backend.agents.tools.abstract_tool import AbstractTool, ToolInput
from backend.utils.enums import ToolCategory
from backend.utils.errors import ToolValidationError


def _extract_inputs(tool_input: ToolInput) -> FloodInputs:
    ctx = {**tool_input.context, **tool_input.parameters}
    return FloodInputs.from_request_context(ctx)


def _region(tool_input: ToolInput) -> str:
    inputs = _extract_inputs(tool_input)
    return inputs.region_id or "unknown_region"


class RainfallTool(AbstractTool):
    """Analyzes current and forecast rainfall for flood potential."""

    @property
    def name(self) -> str:
        return "rainfall_tool"

    @property
    def description(self) -> str:
        return "Retrieve and analyze rainfall observations and forecast accumulation"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FORECAST

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "rainfall_mm": {"type": "number"},
                "rainfall_forecast_24h_mm": {"type": "number"},
                "rainfall_forecast_72h_mm": {"type": "number"},
            },
        }

    def validate_input(self, tool_input: ToolInput) -> None:
        super().validate_input(tool_input)
        inputs = _extract_inputs(tool_input)
        if inputs.rainfall.current_mm is None and inputs.rainfall.forecast_24h_mm is None:
            raise ToolValidationError(
                "Rainfall tool requires rainfall_mm or rainfall_forecast_24h_mm",
                details={"tool": self.name},
            )

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        r = inputs.rainfall
        current = r.current_mm or 0.0
        f24 = r.forecast_24h_mm or 0.0
        f72 = r.forecast_72h_mm or 0.0
        antecedent = r.antecedent_7d_mm or 0.0
        intensity = r.intensity_mm_per_hr or 0.0

        heavy = current >= 50.0 or f24 >= 80.0 or intensity >= 15.0
        flash_risk = intensity >= 25.0 or (current >= 30.0 and antecedent >= 100.0)
        score = min((current / 100.0 + f24 / 150.0 + intensity / 30.0) / 3.0, 1.0)

        return {
            "region": _region(tool_input),
            "current_mm": current,
            "forecast_24h_mm": f24,
            "forecast_72h_mm": f72,
            "antecedent_7d_mm": antecedent,
            "intensity_mm_per_hr": intensity,
            "heavy_rainfall": heavy,
            "flash_flood_risk": flash_risk,
            "rainfall_score": round(score, 3),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


class RiverTool(AbstractTool):
    """Analyzes river levels and discharge for flood risk."""

    @property
    def name(self) -> str:
        return "river_tool"

    @property
    def description(self) -> str:
        return "Assess river stage, bank capacity, and overflow potential"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "river_level_m": {"type": "number"},
                "river_banks_m": {"type": "number"},
            },
        }

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        h = inputs.hydrology
        level = h.river_level_m or 0.0
        banks = h.river_banks_m or level + 2.0
        discharge = h.river_discharge_m3s or 0.0
        margin = banks - level
        overflow = level >= banks or margin < 0.5
        score = min(max(level / max(banks, 0.1), 0.0), 1.0)

        return {
            "region": _region(tool_input),
            "river_level_m": level,
            "river_banks_m": banks,
            "discharge_m3s": discharge,
            "bank_margin_m": round(margin, 2),
            "overflow": overflow,
            "flood_type_hint": FloodType.RIVER.value if overflow else None,
            "hydrology_score": round(score, 3),
        }


class ReservoirTool(AbstractTool):
    """Assesses reservoir levels and spillway status."""

    @property
    def name(self) -> str:
        return "reservoir_tool"

    @property
    def description(self) -> str:
        return "Evaluate reservoir storage, spillway activation, and overflow risk"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "reservoir_level_pct": {"type": "number"},
                "spillway_active": {"type": "boolean"},
            },
        }

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        h = inputs.hydrology
        level = h.reservoir_level_pct or 0.0
        stressed = level >= 85.0 or h.spillway_active
        overflow_risk = level >= 95.0 or h.spillway_active

        return {
            "region": _region(tool_input),
            "reservoir_level_pct": level,
            "capacity_mcm": h.reservoir_capacity_mcm,
            "spillway_active": h.spillway_active,
            "stressed": stressed,
            "overflow_risk": overflow_risk,
            "flood_type_hint": FloodType.RESERVOIR_OVERFLOW.value if overflow_risk else None,
            "reservoir_score": round(level / 100.0, 3),
        }


class TerrainTool(AbstractTool):
    """Evaluates terrain slope, drainage, and soil moisture."""

    @property
    def name(self) -> str:
        return "terrain_tool"

    @property
    def description(self) -> str:
        return "Analyze slope, drainage capacity, soil moisture, and runoff potential"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GEOSPATIAL

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "slope_deg": {"type": "number"},
                "drainage_capacity": {"type": "number"},
                "soil_moisture": {"type": "number"},
            },
        }

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        t = inputs.terrain
        slope = t.slope_deg or 0.0
        drainage = t.drainage_capacity if t.drainage_capacity is not None else 0.5
        moisture = t.soil_moisture if t.soil_moisture is not None else 0.3
        vulnerable = slope > 15.0 or drainage < 0.3 or moisture > 0.8
        runoff_index = min((slope / 45.0 + moisture) / 2.0, 1.0)

        return {
            "region": _region(tool_input),
            "slope_deg": slope,
            "drainage_capacity": drainage,
            "soil_moisture": moisture,
            "land_cover": t.land_cover,
            "terrain_vulnerable": vulnerable,
            "runoff_index": round(runoff_index, 3),
            "terrain_score": round(runoff_index * (1.0 - drainage * 0.5), 3),
        }


class DEMTool(AbstractTool):
    """Digital elevation model analysis for inundation routing."""

    @property
    def name(self) -> str:
        return "dem_tool"

    @property
    def description(self) -> str:
        return "Analyze DEM elevation and low-lying area exposure"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GEOSPATIAL

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "dem_resolution_m": {"type": "number"},
                "mean_elevation_m": {"type": "number"},
            },
        }

    def validate_input(self, tool_input: ToolInput) -> None:
        super().validate_input(tool_input)
        inputs = _extract_inputs(tool_input)
        if inputs.terrain.dem_resolution_m is None and inputs.terrain.mean_elevation_m is None:
            raise ToolValidationError(
                "DEM tool requires dem_resolution_m or mean_elevation_m",
                details={"tool": self.name},
            )

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        t = inputs.terrain
        resolution = t.dem_resolution_m or 30.0
        elevation = t.mean_elevation_m or 50.0
        low_lying = elevation < 20.0
        depth_potential = max(0.0, (20.0 - elevation) / 10.0) if low_lying else 0.0

        return {
            "region": _region(tool_input),
            "dem_resolution_m": resolution,
            "mean_elevation_m": elevation,
            "low_lying": low_lying,
            "estimated_depth_potential_m": round(depth_potential, 2),
            "dem_available": True,
            "dem_score": round(depth_potential, 3),
        }


class HistoricalFloodTool(AbstractTool):
    """Compares current conditions against historical flood events."""

    @property
    def name(self) -> str:
        return "historical_flood_tool"

    @property
    def description(self) -> str:
        return "Retrieve and compare historical flood events for the region"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.RETRIEVAL

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"region_id": {"type": "string"}}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        events = inputs.historical_events
        analog = False
        max_depth = 0.0
        comparable: list[dict[str, Any]] = []

        current_rain = inputs.rainfall.current_mm or 0.0
        for event in events:
            comparable.append(event.model_dump())
            max_depth = max(max_depth, event.peak_depth_m)
            if event.rainfall_mm and current_rain >= event.rainfall_mm * 0.8:
                analog = True

        return {
            "region": _region(tool_input),
            "event_count": len(events),
            "historical_analog": analog,
            "max_historical_depth_m": max_depth,
            "events": comparable,
            "historical_score": round(min(len(events) / 5.0, 1.0) if analog else 0.2, 3),
        }


class PopulationTool(AbstractTool):
    """Estimates population exposure in affected districts."""

    @property
    def name(self) -> str:
        return "population_tool"

    @property
    def description(self) -> str:
        return "Estimate affected population by district"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "districts": {"type": "array", "items": {"type": "string"}},
                "urban_density": {"type": "number"},
            },
        }

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        districts = inputs.districts or ["default_district"]
        density = inputs.terrain.urban_density or 0.3
        base_pop = int(50_000 * density + 10_000)
        total = base_pop * len(districts)

        return {
            "region": _region(tool_input),
            "districts": districts,
            "population_per_district": base_pop,
            "total_population_at_risk": total,
            "urban_density": density,
        }


class ForecastTool(AbstractTool):
    """Integrates meteorological forecast for flood horizon."""

    @property
    def name(self) -> str:
        return "forecast_tool"

    @property
    def description(self) -> str:
        return "Retrieve and interpret precipitation forecast for flood planning"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FORECAST

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "rainfall_forecast_24h_mm": {"type": "number"},
                "rainfall_forecast_72h_mm": {"type": "number"},
            },
        }

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        f24 = inputs.rainfall.forecast_24h_mm or 0.0
        f72 = inputs.rainfall.forecast_72h_mm or 0.0
        worsening = f72 > f24 * 1.5

        return {
            "region": _region(tool_input),
            "forecast_24h_mm": f24,
            "forecast_72h_mm": f72,
            "forecast_available": inputs.forecast_available or f24 > 0 or f72 > 0,
            "worsening_trend": worsening,
            "forecast_score": round(min((f24 + f72) / 200.0, 1.0), 3),
        }


class DigitalTwinTool(AbstractTool):
    """Reads flood-relevant layers from the digital twin."""

    @property
    def name(self) -> str:
        return "digital_twin_tool"

    @property
    def description(self) -> str:
        return "Access digital twin flood layers and scenario state"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SIMULATION

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "twin_id": {"type": "string"},
            },
        }

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        twin_state = tool_input.context.get("digital_twin_state", {})
        if not isinstance(twin_state, dict):
            twin_state = {}
        layers = twin_state.get("layers", twin_state)
        flood_layer = layers.get("flood", {}) if isinstance(layers, dict) else {}

        return {
            "twin_id": tool_input.context.get("twin_id") or tool_input.parameters.get("twin_id"),
            "digital_twin_available": bool(twin_state) or tool_input.context.get("digital_twin_available"),
            "flood_layers": flood_layer,
            "inundation_depth_m": flood_layer.get("inundation_depth_m", 0.0),
            "active_scenario": twin_state.get("scenario_id"),
        }


def create_flood_tools() -> list[AbstractTool]:
    """Factory returning all flood analysis tools."""
    return [
        RainfallTool(),
        RiverTool(),
        ReservoirTool(),
        TerrainTool(),
        DEMTool(),
        HistoricalFloodTool(),
        PopulationTool(),
        ForecastTool(),
        DigitalTwinTool(),
    ]


ALL_FLOOD_TOOL_NAMES: list[str] = [t().name for t in (
    RainfallTool, RiverTool, ReservoirTool, TerrainTool, DEMTool,
    HistoricalFloodTool, PopulationTool, ForecastTool, DigitalTwinTool,
)]
