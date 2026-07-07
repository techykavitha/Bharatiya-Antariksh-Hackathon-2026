"""Dedicated tools for heatwave and thermal stress analysis."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from backend.agents.specialized.heatwave.heatwave_context import HeatwaveInputs
from backend.agents.tools.abstract_tool import AbstractTool, ToolInput
from backend.utils.enums import ToolCategory
from backend.utils.errors import ToolValidationError


def _extract_inputs(tool_input: ToolInput) -> HeatwaveInputs:
    ctx = {**tool_input.context, **tool_input.parameters}
    return HeatwaveInputs.from_request_context(ctx)


def _region(tool_input: ToolInput) -> str:
    return _extract_inputs(tool_input).region_id or "unknown_region"


def _heat_index_c(temp_c: float, rh_pct: float) -> float:
    """Approximate heat index in Celsius (converted from NOAA formula)."""
    if temp_c < 27.0:
        return temp_c
    t_f = temp_c * 9.0 / 5.0 + 32.0
    hi_f = (
        -42.379 + 2.04901523 * t_f + 10.14333127 * rh_pct
        - 0.22475541 * t_f * rh_pct - 6.83783e-3 * t_f ** 2
        - 5.481717e-2 * rh_pct ** 2 + 1.22874e-3 * t_f ** 2 * rh_pct
        + 8.5282e-4 * t_f * rh_pct ** 2 - 1.99e-6 * t_f ** 2 * rh_pct ** 2
    )
    return (hi_f - 32.0) * 5.0 / 9.0


def _wet_bulb_estimate(temp_c: float, rh_pct: float) -> float:
    """Simplified wet-bulb temperature estimate (Stull formula)."""
    rh = max(min(rh_pct, 100.0), 0.1)
    return (
        temp_c * math.atan(0.151977 * math.sqrt(rh + 8.313659))
        + math.atan(temp_c + rh)
        - math.atan(rh - 1.676331)
        + 0.00391838 * rh ** 1.5 * math.atan(0.023101 * rh)
        - 4.686035
    )


def _schema(*properties: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {name: {"type": "number"} for name in properties},
    }


class TemperatureTool(AbstractTool):
    """Analyzes air and surface temperature trends."""

    @property
    def name(self) -> str:
        return "temperature_tool"

    @property
    def description(self) -> str:
        return "Assess air/surface temperature, trends, and forecast maxima"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("air_temp_c", "max_temp_c", "forecast_max_24h_c", "forecast_max_72h_c")

    def validate_input(self, tool_input: ToolInput) -> None:
        super().validate_input(tool_input)
        inputs = _extract_inputs(tool_input)
        if inputs.temperature.air_temp_c is None and inputs.temperature.max_temp_c is None:
            raise ToolValidationError(
                "Temperature tool requires air_temp_c or max_temp_c",
                details={"tool": self.name},
            )

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        t = inputs.temperature
        air = t.air_temp_c or t.max_temp_c or 0.0
        surface = t.surface_temp_c or air + 2.0
        f24 = t.forecast_max_24h_c or air
        f72 = t.forecast_max_72h_c or f24
        trend = t.trend_c_per_day or 0.0
        elevated = air >= 38.0 or f24 >= 40.0
        rising = trend > 0.5 or f72 > f24 * 1.05
        score = min(max((air - 30.0) / 20.0, 0.0), 1.0)

        return {
            "region": _region(tool_input),
            "air_temp_c": air,
            "surface_temp_c": surface,
            "forecast_max_24h_c": f24,
            "forecast_max_72h_c": f72,
            "trend_c_per_day": trend,
            "elevated_temperature": elevated,
            "rising_trend": rising,
            "temperature_score": round(score, 3),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


class HumidityTool(AbstractTool):
    """Analyzes humidity and computes heat index / wet bulb."""

    @property
    def name(self) -> str:
        return "humidity_tool"

    @property
    def description(self) -> str:
        return "Assess humidity, heat index, and wet-bulb temperature"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("humidity_pct", "relative_humidity_pct", "air_temp_c")

    def validate_input(self, tool_input: ToolInput) -> None:
        super().validate_input(tool_input)
        inputs = _extract_inputs(tool_input)
        if inputs.humidity.relative_humidity_pct is None:
            raise ToolValidationError(
                "Humidity tool requires humidity_pct or relative_humidity_pct",
                details={"tool": self.name},
            )

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        h = inputs.humidity
        rh = h.relative_humidity_pct or 50.0
        air = inputs.temperature.air_temp_c or inputs.temperature.max_temp_c or 35.0
        heat_index = _heat_index_c(air, rh)
        wet_bulb = h.wet_bulb_c or _wet_bulb_estimate(air, rh)
        high_stress = heat_index >= 41.0 or wet_bulb >= 28.0
        dangerous = wet_bulb >= 31.0 or heat_index >= 54.0

        return {
            "region": _region(tool_input),
            "relative_humidity_pct": rh,
            "heat_index_c": round(heat_index, 2),
            "wet_bulb_c": round(wet_bulb, 2),
            "high_humidity_stress": high_stress,
            "dangerous_heat": dangerous,
            "humidity_score": round(min(rh / 100.0 + (heat_index - 30.0) / 30.0, 1.0), 3),
        }


class LSTTool(AbstractTool):
    """Land surface temperature analysis for urban heat island."""

    @property
    def name(self) -> str:
        return "lst_tool"

    @property
    def description(self) -> str:
        return "Analyze land surface temperature and urban heat island intensity"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GEOSPATIAL

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("lst_c", "air_temp_c")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        air = inputs.temperature.air_temp_c or 35.0
        lst = inputs.urban.lst_c or air + 4.0
        uhi_intensity = lst - air
        uhi = uhi_intensity >= 3.0
        score = min(uhi_intensity / 10.0, 1.0)

        return {
            "region": _region(tool_input),
            "lst_c": round(lst, 2),
            "air_temp_c": air,
            "uhi_intensity_c": round(uhi_intensity, 2),
            "urban_heat_island": uhi,
            "uhi_score": round(score, 3),
        }


class NDVITool(AbstractTool):
    """Vegetation index for urban cooling potential."""

    @property
    def name(self) -> str:
        return "ndvi_tool"

    @property
    def description(self) -> str:
        return "Assess NDVI and vegetation cover for cooling potential"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GEOSPATIAL

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("ndvi")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        ndvi = inputs.urban.ndvi if inputs.urban.ndvi is not None else 0.3
        low_vegetation = ndvi < 0.25
        cooling_potential = max(ndvi, 0.0)

        return {
            "region": _region(tool_input),
            "ndvi": ndvi,
            "low_vegetation": low_vegetation,
            "cooling_potential": round(cooling_potential, 3),
            "tree_plantation_recommended": low_vegetation,
        }


class UrbanDensityTool(AbstractTool):
    """Urban and building density for heat exposure."""

    @property
    def name(self) -> str:
        return "urban_density_tool"

    @property
    def description(self) -> str:
        return "Analyze urban density, building density, and impervious surface"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GEOSPATIAL

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("urban_density", "building_density", "impervious_fraction")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        u = inputs.urban
        urban = u.urban_density if u.urban_density is not None else 0.5
        building = u.building_density if u.building_density is not None else 0.4
        impervious = u.impervious_fraction if u.impervious_fraction is not None else 0.5
        high_urban = urban > 0.6 or building > 0.65

        return {
            "region": _region(tool_input),
            "urban_density": urban,
            "building_density": building,
            "impervious_fraction": impervious,
            "land_cover": u.land_cover,
            "high_urban_exposure": high_urban,
            "urban_score": round((urban + building + impervious) / 3.0, 3),
        }


class PopulationTool(AbstractTool):
    """Population density and vulnerability exposure."""

    @property
    def name(self) -> str:
        return "population_tool"

    @property
    def description(self) -> str:
        return "Estimate population at risk from heat exposure"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("population_density")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        districts = inputs.districts or ["default_district"]
        pop_density = inputs.urban.population_density or 8000.0
        population = int(pop_density * 10 * len(districts))
        vulnerable = int(population * 0.25)

        return {
            "region": _region(tool_input),
            "districts": districts,
            "population_density": pop_density,
            "total_population": population,
            "vulnerable_population": vulnerable,
            "high_exposure": pop_density > 10000,
        }


class ForecastTool(AbstractTool):
    """Temperature forecast for heatwave evolution."""

    @property
    def name(self) -> str:
        return "forecast_tool"

    @property
    def description(self) -> str:
        return "Retrieve temperature forecast for heatwave planning"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FORECAST

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("forecast_max_24h_c", "forecast_max_72h_c")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        f24 = inputs.temperature.forecast_max_24h_c or 0.0
        f72 = inputs.temperature.forecast_max_72h_c or 0.0
        worsening = f72 > f24 + 1.0

        return {
            "region": _region(tool_input),
            "forecast_max_24h_c": f24,
            "forecast_max_72h_c": f72,
            "forecast_available": inputs.forecast_available or f24 > 0,
            "worsening_trend": worsening,
            "forecast_score": round(min(f72 / 50.0, 1.0), 3),
        }


class HistoricalHeatwaveTool(AbstractTool):
    """Compares current conditions against historical heatwaves."""

    @property
    def name(self) -> str:
        return "historical_heatwave_tool"

    @property
    def description(self) -> str:
        return "Retrieve and compare historical heatwave events"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.RETRIEVAL

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"historical_heatwaves": {"type": "array"}}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        events = inputs.historical_events
        current = inputs.temperature.max_temp_c or inputs.temperature.air_temp_c or 0.0
        analog = False
        max_peak = 0.0
        comparable: list[dict[str, Any]] = []

        for event in events:
            comparable.append(event.model_dump())
            max_peak = max(max_peak, event.peak_temp_c)
            if current >= event.peak_temp_c * 0.9:
                analog = True

        return {
            "region": _region(tool_input),
            "event_count": len(events),
            "historical_analog": analog,
            "max_historical_peak_c": max_peak,
            "events": comparable,
            "historical_score": round(min(len(events) / 5.0, 1.0) if analog else 0.2, 3),
        }


class DigitalTwinTool(AbstractTool):
    """Reads heat-relevant layers from the digital twin."""

    @property
    def name(self) -> str:
        return "digital_twin_tool"

    @property
    def description(self) -> str:
        return "Access digital twin thermal layers and scenario state"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SIMULATION

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"twin_id": {"type": "string"}}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        twin_state = tool_input.context.get("digital_twin_state", {})
        if not isinstance(twin_state, dict):
            twin_state = {}
        layers = twin_state.get("layers", twin_state)
        heat_layer: dict[str, Any] = {}
        if isinstance(layers, dict):
            heat_layer = layers.get("heat", layers.get("thermal", {}))
            if not isinstance(heat_layer, dict):
                heat_layer = {}

        return {
            "twin_id": tool_input.context.get("twin_id"),
            "digital_twin_available": bool(twin_state) or tool_input.context.get("digital_twin_available"),
            "heat_layers": heat_layer,
            "lst_c": heat_layer.get("lst_c"),
            "uhi_intensity_c": heat_layer.get("uhi_intensity_c"),
            "active_scenario": twin_state.get("scenario_id"),
        }


class HealthRiskTool(AbstractTool):
    """Public health risk from thermal stress."""

    @property
    def name(self) -> str:
        return "health_risk_tool"

    @property
    def description(self) -> str:
        return "Assess human health risk from heat and compound AQI exposure"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("air_temp_c", "humidity_pct", "aqi")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        air = inputs.temperature.air_temp_c or 35.0
        rh = inputs.humidity.relative_humidity_pct or 50.0
        aqi = inputs.aqi
        heat_index = _heat_index_c(air, rh)
        compound = aqi is not None and aqi > 150 and heat_index >= 38.0
        health_risk = "low"
        if heat_index >= 54.0:
            health_risk = "extreme"
        elif heat_index >= 41.0:
            health_risk = "high"
        elif heat_index >= 32.0:
            health_risk = "moderate"

        return {
            "region": _region(tool_input),
            "heat_index_c": round(heat_index, 2),
            "aqi": aqi,
            "compound_aqi_heat_risk": compound,
            "health_risk_level": health_risk,
            "vulnerability_score": round(min(heat_index / 55.0, 1.0), 3),
        }


def create_heatwave_tools() -> list[AbstractTool]:
    return [
        TemperatureTool(),
        HumidityTool(),
        LSTTool(),
        NDVITool(),
        UrbanDensityTool(),
        PopulationTool(),
        ForecastTool(),
        HistoricalHeatwaveTool(),
        DigitalTwinTool(),
        HealthRiskTool(),
    ]


ALL_HEATWAVE_TOOL_NAMES: list[str] = [t().name for t in (
    TemperatureTool, HumidityTool, LSTTool, NDVITool, UrbanDensityTool,
    PopulationTool, ForecastTool, HistoricalHeatwaveTool, DigitalTwinTool, HealthRiskTool,
)]
