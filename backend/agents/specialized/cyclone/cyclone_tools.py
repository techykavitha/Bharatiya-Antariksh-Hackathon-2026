"""Dedicated tools for tropical cyclone monitoring and forecasting."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from backend.agents.specialized.cyclone.cyclone_context import CycloneInputs, KnowledgeGraphInsights
from backend.agents.specialized.cyclone.cyclone_models import (
    CATEGORY_WIND_KT,
    CycloneBasin,
    CycloneCategory,
)
from backend.agents.tools.abstract_tool import AbstractTool, ToolInput
from backend.utils.enums import ToolCategory
from backend.utils.errors import ToolValidationError


def _extract_inputs(tool_input: ToolInput) -> CycloneInputs:
    ctx = {**tool_input.context, **tool_input.parameters}
    return CycloneInputs.from_request_context(ctx)


def _region(tool_input: ToolInput) -> str:
    return _extract_inputs(tool_input).region_id or "unknown_region"


def _schema(*properties: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {name: {"type": "number"} for name in properties},
    }


def _classify_wind(wind_kt: float) -> CycloneCategory:
    for category, (lo, hi) in CATEGORY_WIND_KT.items():
        if lo <= wind_kt < hi:
            return category
    if wind_kt >= 120:
        return CycloneCategory.SUPER_CYCLONIC_STORM
    return CycloneCategory.DISTURBANCE


class SSTTool(AbstractTool):
    """Analyzes sea surface temperature for cyclogenesis potential."""

    @property
    def name(self) -> str:
        return "sst_tool"

    @property
    def description(self) -> str:
        return "Assess SST, warm pool extent, and cyclogenesis favorability"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("sst_c", "sea_surface_temp_c")

    def validate_input(self, tool_input: ToolInput) -> None:
        super().validate_input(tool_input)
        inputs = _extract_inputs(tool_input)
        if inputs.ocean.sst_c is None:
            raise ToolValidationError("SST tool requires sst_c", details={"tool": self.name})

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        sst = inputs.ocean.sst_c or 28.0
        warm = sst >= 26.5
        very_warm = sst >= 29.0
        genesis_favorable = warm and (inputs.basin != CycloneBasin.UNKNOWN)
        score = min(max((sst - 24.0) / 6.0, 0.0), 1.0)
        return {
            "region": _region(tool_input),
            "basin": inputs.basin.value,
            "sst_c": sst,
            "warm_sst": warm,
            "very_warm_sst": very_warm,
            "genesis_favorable": genesis_favorable,
            "sst_score": round(score, 3),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


class PressureTool(AbstractTool):
    """Analyzes sea level pressure for cyclone detection."""

    @property
    def name(self) -> str:
        return "pressure_tool"

    @property
    def description(self) -> str:
        return "Assess MSLP, pressure gradient, and cyclone center detection"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("sea_level_pressure_hpa", "mslp_hpa")

    def validate_input(self, tool_input: ToolInput) -> None:
        super().validate_input(tool_input)
        inputs = _extract_inputs(tool_input)
        if inputs.ocean.sea_level_pressure_hpa is None:
            raise ToolValidationError("Pressure tool requires sea_level_pressure_hpa", details={"tool": self.name})

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        mslp = inputs.ocean.sea_level_pressure_hpa or 1008.0
        low_pressure = mslp < 1000.0
        deep_low = mslp < 980.0
        cyclone_center_likely = mslp < 995.0
        score = min(max((1013.0 - mslp) / 35.0, 0.0), 1.0)
        return {
            "region": _region(tool_input),
            "sea_level_pressure_hpa": mslp,
            "low_pressure": low_pressure,
            "deep_low_pressure": deep_low,
            "cyclone_center_likely": cyclone_center_likely,
            "pressure_score": round(score, 3),
        }


class WindTool(AbstractTool):
    """Analyzes sustained wind and cyclone intensity."""

    @property
    def name(self) -> str:
        return "wind_tool"

    @property
    def description(self) -> str:
        return "Assess sustained wind, gusts, and IMD intensity classification"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("wind_speed_kt", "max_wind_kt", "wind_direction_deg")

    def validate_input(self, tool_input: ToolInput) -> None:
        super().validate_input(tool_input)
        inputs = _extract_inputs(tool_input)
        wind = inputs.ocean.wind_speed_kt or inputs.forecast.max_wind_kt_forecast
        if wind is None:
            raise ToolValidationError("Wind tool requires wind_speed_kt", details={"tool": self.name})

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        wind = inputs.ocean.wind_speed_kt or inputs.forecast.max_wind_kt_forecast or 0.0
        direction = inputs.ocean.wind_direction_deg or 0.0
        category = _classify_wind(wind)
        gust = wind * 1.25
        destructive = wind >= 48
        score = min(wind / 120.0, 1.0)
        return {
            "region": _region(tool_input),
            "wind_speed_kt": wind,
            "wind_direction_deg": direction,
            "gust_wind_kt": round(gust, 1),
            "category": category.value,
            "destructive_winds": destructive,
            "wind_score": round(score, 3),
        }


class OceanHeatTool(AbstractTool):
    """Analyzes ocean heat content for rapid intensification potential."""

    @property
    def name(self) -> str:
        return "ocean_heat_tool"

    @property
    def description(self) -> str:
        return "Assess OHC and upper-ocean thermal energy for RI potential"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("ocean_heat_content_kj_cm2", "ohc", "sst_c")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        ohc = inputs.ocean.ocean_heat_content_kj_cm2
        sst = inputs.ocean.sst_c or 28.0
        if ohc is None:
            ohc = max(40.0, (sst - 26.0) * 25.0)
        ri_favorable = ohc >= 80.0 and sst >= 28.5
        ri_likely = ohc >= 100.0 and sst >= 29.0
        score = min(ohc / 120.0, 1.0)
        return {
            "region": _region(tool_input),
            "ocean_heat_content_kj_cm2": round(ohc, 1),
            "ri_favorable": ri_favorable,
            "ri_likely": ri_likely,
            "ocean_heat_score": round(score, 3),
        }


class INSATTool(AbstractTool):
    """Processes INSAT satellite observations for cyclone structure."""

    @property
    def name(self) -> str:
        return "insat_tool"

    @property
    def description(self) -> str:
        return "Analyze INSAT IR imagery, cloud top temperature, and eye detection"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("cloud_top_temp_c")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        ctt = inputs.ocean.cloud_top_temp_c
        if ctt is None:
            wind = inputs.ocean.wind_speed_kt or 0.0
            ctt = -20.0 - min(wind / 5.0, 40.0)
        organized = ctt < -40.0
        eye_detected = ctt < -55.0 and (inputs.ocean.wind_speed_kt or 0) >= 65
        return {
            "region": _region(tool_input),
            "cloud_top_temp_c": round(ctt, 1),
            "insat_available": inputs.insat_available or ctt is not None,
            "organized_convection": organized,
            "eye_detected": eye_detected,
            "satellite_score": round(min(abs(ctt) / 70.0, 1.0), 3),
        }


class ForecastTool(AbstractTool):
    """Analyzes track and intensity forecast."""

    @property
    def name(self) -> str:
        return "forecast_tool"

    @property
    def description(self) -> str:
        return "Assess track forecast, landfall timing, and intensity evolution"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FORECAST

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"landfall_probability": {"type": "number"}}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        fc = inputs.forecast
        landfall_prob = fc.landfall_probability or 0.0
        if landfall_prob == 0.0 and fc.landfall_latitude is not None:
            landfall_prob = 0.65
        landfall_hours = fc.landfall_hours or 48.0
        max_wind = fc.max_wind_kt_forecast or inputs.ocean.wind_speed_kt or 0.0
        track_points = len(fc.track_points)
        landfall_threat = landfall_prob >= 0.4
        rain_24 = fc.rainfall_mm_24h or 0.0
        rain_72 = fc.rainfall_mm_72h or 0.0
        return {
            "region": _region(tool_input),
            "landfall_probability": round(landfall_prob, 3),
            "landfall_hours": landfall_hours,
            "max_wind_kt_forecast": max_wind,
            "track_point_count": track_points,
            "landfall_threat": landfall_threat,
            "forecast_category": _classify_wind(max_wind).value,
            "track_score": round(min(landfall_prob + track_points * 0.05, 1.0), 3),
            "rainfall_mm_24h": rain_24,
            "rainfall_mm_72h": rain_72,
        }


class HistoricalCycloneTool(AbstractTool):
    """Compares current conditions to historical cyclone analogs."""

    @property
    def name(self) -> str:
        return "historical_cyclone_tool"

    @property
    def description(self) -> str:
        return "Match historical cyclone analogs for India basins"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        wind = inputs.ocean.wind_speed_kt or inputs.forecast.max_wind_kt_forecast or 0.0
        analogs: list[dict[str, Any]] = []
        for event in inputs.historical_events:
            similarity = 1.0 - min(abs(wind - event.peak_wind_kt) / 80.0, 1.0)
            if similarity >= 0.4:
                analogs.append({
                    "event_id": event.event_id,
                    "name": event.name,
                    "year": event.year,
                    "similarity": round(similarity, 3),
                    "peak_wind_kt": event.peak_wind_kt,
                    "landfall_state": event.landfall_state,
                })
        analogs.sort(key=lambda a: a["similarity"], reverse=True)
        return {
            "region": _region(tool_input),
            "historical_analog_count": len(analogs),
            "top_analogs": analogs[:3],
            "historical_analog": len(analogs) > 0,
            "historical_score": round(analogs[0]["similarity"], 3) if analogs else 0.0,
        }


class StormSurgeTool(AbstractTool):
    """Estimates storm surge and coastal inundation."""

    @property
    def name(self) -> str:
        return "storm_surge_tool"

    @property
    def description(self) -> str:
        return "Estimate storm surge height and coastal inundation risk"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("wind_speed_kt", "max_wind_kt")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        wind = inputs.ocean.wind_speed_kt or inputs.forecast.max_wind_kt_forecast or 0.0
        pressure = inputs.ocean.sea_level_pressure_hpa or 1005.0
        # Simplified surge model: wind-driven + inverse pressure
        surge_m = max(0.0, (wind / 100.0) ** 2 * 4.5 + (1013.0 - pressure) * 0.02)
        inundation = surge_m * 0.85
        high_surge = surge_m >= 2.0
        extreme_surge = surge_m >= 4.0
        return {
            "region": _region(tool_input),
            "surge_height_m": round(surge_m, 2),
            "inundation_depth_m": round(inundation, 2),
            "coastal_exposure_km": round(min(wind / 2.0, 200.0), 1),
            "high_storm_surge": high_surge,
            "extreme_storm_surge": extreme_surge,
            "surge_score": round(min(surge_m / 5.0, 1.0), 3),
        }


class DigitalTwinTool(AbstractTool):
    """Reads cyclone-relevant digital twin layers."""

    @property
    def name(self) -> str:
        return "digital_twin_tool"

    @property
    def description(self) -> str:
        return "Access coastal digital twin state for cyclone scenario"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SIMULATION

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"twin_id": {"type": "string"}}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        twin_state = tool_input.context.get("digital_twin_state") or tool_input.parameters.get("digital_twin_state")
        cyclone_layer: dict[str, Any] = {}
        if isinstance(twin_state, dict):
            layers = twin_state.get("layers", {})
            cyclone_layer = layers.get("cyclone", layers.get("coastal", {}))
            if not isinstance(cyclone_layer, dict):
                cyclone_layer = {}
        return {
            "twin_id": tool_input.context.get("twin_id"),
            "digital_twin_available": bool(twin_state),
            "cyclone_layers": cyclone_layer,
            "coastal_defense_status": cyclone_layer.get("coastal_defense_status", "unknown"),
            "active_scenario": twin_state.get("scenario_id") if isinstance(twin_state, dict) else None,
        }


class KnowledgeGraphTool(AbstractTool):
    """Surfaces pre-queried Climate Knowledge Graph insights."""

    @property
    def name(self) -> str:
        return "knowledge_graph_tool"

    @property
    def description(self) -> str:
        return "Query affected regions, infrastructure, agents, and cascade chains from CKG"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        raw = tool_input.context.get("ckg_insights") or tool_input.parameters.get("ckg_insights")
        if isinstance(raw, KnowledgeGraphInsights):
            insights = raw
        elif isinstance(raw, dict):
            insights = KnowledgeGraphInsights.model_validate(raw)
        else:
            insights = KnowledgeGraphInsights()
        return {
            "region": _region(tool_input),
            "affected_regions": insights.affected_regions,
            "affected_infrastructure": insights.affected_infrastructure,
            "dependent_agents": insights.dependent_agents,
            "historical_analogs": insights.historical_analogs,
            "cascade_chains": insights.cascade_chains,
            "query_count": insights.query_count,
            "ckg_available": insights.query_count > 0,
        }


class PopulationTool(AbstractTool):
    """Estimates coastal population exposure."""

    @property
    def name(self) -> str:
        return "population_tool"

    @property
    def description(self) -> str:
        return "Assess coastal population exposure and evacuation zones"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"population_density": {"type": "number"}}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        density = float(tool_input.context.get("population_density", 5000.0))
        districts = inputs.districts or ["coastal_district"]
        coastal_fraction = 0.35 if inputs.basin != CycloneBasin.UNKNOWN else 0.2
        exposures: list[dict[str, Any]] = []
        for district in districts:
            pop = int(density * 50)
            coastal_pop = int(pop * coastal_fraction)
            exposures.append({
                "district_id": district.lower().replace(" ", "_"),
                "name": district,
                "population": pop,
                "coastal_population": coastal_pop,
            })
        total_coastal = sum(e["coastal_population"] for e in exposures)
        high_exposure = total_coastal >= 500_000
        return {
            "region": _region(tool_input),
            "population_exposures": exposures,
            "total_coastal_population": total_coastal,
            "high_population_exposure": high_exposure,
            "vulnerability_score": round(min(total_coastal / 2_000_000, 1.0), 3),
        }


class InfrastructureTool(AbstractTool):
    """Assesses critical infrastructure cyclone risk."""

    @property
    def name(self) -> str:
        return "infrastructure_tool"

    @property
    def description(self) -> str:
        return "Assess ports, power plants, hospitals, and transport infrastructure risk"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("wind_speed_kt", "surge_height_m")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        wind = inputs.ocean.wind_speed_kt or 0.0
        infra_list = tool_input.context.get("critical_infrastructure", [
            {"infrastructure_id": "port-01", "name": "Major Port", "category": "port"},
            {"infrastructure_id": "power-01", "name": "Coastal Power Plant", "category": "power"},
            {"infrastructure_id": "hospital-01", "name": "District Hospital", "category": "healthcare"},
        ])
        at_risk: list[dict[str, Any]] = []
        for item in infra_list:
            if not isinstance(item, dict):
                continue
            category = item.get("category", "general")
            risk = "low"
            if wind >= 90 or category == "port":
                risk = "severe" if wind >= 65 else "high"
            elif wind >= 48:
                risk = "moderate"
            at_risk.append({**item, "risk_level": risk})
        return {
            "region": _region(tool_input),
            "infrastructure_risks": at_risk,
            "infrastructure_at_risk": any(i["risk_level"] in ("high", "severe") for i in at_risk),
            "infrastructure_count": len(at_risk),
        }


def create_cyclone_tools() -> list[AbstractTool]:
    return [
        SSTTool(),
        PressureTool(),
        WindTool(),
        OceanHeatTool(),
        INSATTool(),
        ForecastTool(),
        HistoricalCycloneTool(),
        StormSurgeTool(),
        DigitalTwinTool(),
        KnowledgeGraphTool(),
        PopulationTool(),
        InfrastructureTool(),
    ]


ALL_CYCLONE_TOOL_NAMES: list[str] = [t().name for t in (
    SSTTool, PressureTool, WindTool, OceanHeatTool, INSATTool,
    ForecastTool, HistoricalCycloneTool, StormSurgeTool,
    DigitalTwinTool, KnowledgeGraphTool, PopulationTool, InfrastructureTool,
)]
