"""Dedicated tools for precision agriculture and crop analysis."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.agents.specialized.agriculture.agriculture_context import AgricultureInputs
from backend.agents.specialized.agriculture.agriculture_models import CropHealthStatus
from backend.agents.tools.abstract_tool import AbstractTool, ToolInput
from backend.utils.enums import ToolCategory


def _extract_inputs(tool_input: ToolInput) -> AgricultureInputs:
    ctx = {**tool_input.context, **tool_input.parameters}
    return AgricultureInputs.from_request_context(ctx)


def _region(tool_input: ToolInput) -> str:
    return _extract_inputs(tool_input).region_id or "unknown_region"


def _schema(*properties: str) -> dict[str, Any]:
    return {"type": "object", "properties": {name: {"type": "number"} for name in properties}}


class NDVITool(AbstractTool):
    @property
    def name(self) -> str:
        return "ndvi_tool"

    @property
    def description(self) -> str:
        return "Assess crop health via Normalized Difference Vegetation Index"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GEOSPATIAL

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("ndvi")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        ndvi = inputs.remote_sensing.ndvi
        trend = inputs.remote_sensing.ndvi_trend
        if ndvi >= 0.65:
            health = CropHealthStatus.EXCELLENT
        elif ndvi >= 0.5:
            health = CropHealthStatus.GOOD
        elif ndvi >= 0.35:
            health = CropHealthStatus.MODERATE
        elif ndvi >= 0.2:
            health = CropHealthStatus.STRESSED
        else:
            health = CropHealthStatus.CRITICAL
        declining = trend < -0.05
        return {
            "region": _region(tool_input),
            "crop_type": inputs.crop_type,
            "ndvi": round(ndvi, 3),
            "ndvi_trend": round(trend, 3),
            "health_status": health.value,
            "declining_vigor": declining,
            "crop_health_score": round(min(ndvi / 0.8, 1.0), 3),
        }


class EVITool(AbstractTool):
    @property
    def name(self) -> str:
        return "evi_tool"

    @property
    def description(self) -> str:
        return "Assess enhanced vegetation index for crop canopy density"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GEOSPATIAL

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("evi")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        evi = inputs.remote_sensing.evi
        return {
            "region": _region(tool_input),
            "evi": round(evi, 3),
            "evi_trend": round(inputs.remote_sensing.evi_trend, 3),
            "canopy_density": "high" if evi >= 0.5 else "moderate" if evi >= 0.3 else "low",
            "evi_score": round(min(evi / 0.7, 1.0), 3),
        }


class SoilMoistureTool(AbstractTool):
    @property
    def name(self) -> str:
        return "soil_moisture_tool"

    @property
    def description(self) -> str:
        return "Assess soil moisture and irrigation need"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("soil_moisture_pct")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        moisture = inputs.soil.soil_moisture_pct or 40.0
        fc = inputs.soil.field_capacity_pct
        deficit = max(fc - moisture, 0.0)
        irrigation_needed = moisture < fc * 0.6
        return {
            "region": _region(tool_input),
            "soil_moisture_pct": round(moisture, 2),
            "field_capacity_pct": fc,
            "moisture_deficit_pct": round(deficit, 2),
            "irrigation_needed": irrigation_needed,
            "soil_moisture_score": round(moisture / fc, 3),
            "groundwater_level_m": inputs.soil.groundwater_level_m,
        }


class CropCalendarTool(AbstractTool):
    @property
    def name(self) -> str:
        return "crop_calendar_tool"

    @property
    def description(self) -> str:
        return "Determine current crop phenology stage from calendar"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        day_of_year = int(tool_input.context.get("day_of_year", 180))
        stage = "vegetative"
        critical = False
        for entry in inputs.crop_calendar:
            if entry.start_day <= day_of_year <= entry.end_day:
                stage = entry.stage
                critical = entry.critical
                break
        return {
            "region": _region(tool_input),
            "crop_type": inputs.crop_type,
            "season": inputs.season,
            "phenology_stage": stage,
            "critical_stage": critical,
            "calendar_entries": len(inputs.crop_calendar),
        }


class LandUseTool(AbstractTool):
    @property
    def name(self) -> str:
        return "land_use_tool"

    @property
    def description(self) -> str:
        return "Assess agricultural land use and crop suitability"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GEOSPATIAL

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        return {
            "region": _region(tool_input),
            "land_use": inputs.land_use,
            "area_hectares": inputs.area_hectares,
            "crop_type": inputs.crop_type,
            "suitable_for_crop": inputs.land_use in ("agricultural", "irrigated", "cropland"),
        }


class WeatherTool(AbstractTool):
    @property
    def name(self) -> str:
        return "weather_tool"

    @property
    def description(self) -> str:
        return "Analyze temperature, rainfall, and humidity for crop stress"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("temperature_c", "rainfall_mm_7d")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        w = inputs.weather
        max_temp = w.max_temp_c or w.temperature_c or 30.0
        heat_stress = max_temp >= 38.0
        excess_rain = w.rainfall_mm_7d > 100.0
        drought_indicator = w.rainfall_mm_30d < 20.0 and w.rainfall_mm_7d < 5.0
        humidity = w.humidity_pct or 60.0
        pest_favorable = humidity >= 75.0 and 25.0 <= max_temp <= 35.0
        return {
            "region": _region(tool_input),
            "max_temp_c": max_temp,
            "rainfall_mm_7d": w.rainfall_mm_7d,
            "rainfall_mm_30d": w.rainfall_mm_30d,
            "humidity_pct": humidity,
            "heat_stress": heat_stress,
            "excess_rainfall": excess_rain,
            "drought_indicator": drought_indicator,
            "pest_favorability": pest_favorable,
        }


class ForecastTool(AbstractTool):
    @property
    def name(self) -> str:
        return "forecast_tool"

    @property
    def description(self) -> str:
        return "Assess agricultural weather forecast horizon"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FORECAST

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"forecast_rainfall_7d_mm": {"type": "number"}}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        rain_7d = inputs.weather.forecast_rainfall_7d_mm
        return {
            "region": _region(tool_input),
            "forecast_rainfall_7d_mm": rain_7d,
            "forecast_available": inputs.forecast_available,
            "favorable_for_irrigation_deferral": rain_7d >= 30.0,
            "drought_persistence_likely": rain_7d < 5.0,
        }


class YieldEstimationTool(AbstractTool):
    @property
    def name(self) -> str:
        return "yield_estimation_tool"

    @property
    def description(self) -> str:
        return "Estimate crop yield potential and risk"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("ndvi", "soil_moisture_pct")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        ndvi = inputs.remote_sensing.ndvi
        moisture = inputs.soil.soil_moisture_pct or 40.0
        base_yield = min(ndvi / 0.7, 1.0) * 100.0
        moisture_factor = min(moisture / inputs.soil.field_capacity_pct, 1.0)
        estimated = base_yield * (0.6 + 0.4 * moisture_factor)
        risk = max(0.0, 1.0 - estimated / 100.0)
        return {
            "region": _region(tool_input),
            "crop_type": inputs.crop_type,
            "estimated_yield_pct": round(estimated, 1),
            "yield_risk_score": round(risk, 3),
            "area_hectares": inputs.area_hectares,
        }


class IrrigationTool(AbstractTool):
    @property
    def name(self) -> str:
        return "irrigation_tool"

    @property
    def description(self) -> str:
        return "Generate irrigation scheduling recommendation"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.PLANNING

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("soil_moisture_pct")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        moisture = inputs.soil.soil_moisture_pct or 40.0
        fc = inputs.soil.field_capacity_pct
        deficit = max(fc - moisture, 0.0)
        if moisture < fc * 0.35:
            rec = "emergency"
            volume = 60.0
        elif moisture < fc * 0.6:
            rec = "increase"
            volume = 40.0
        elif moisture > fc * 0.95:
            rec = "reduce"
            volume = 0.0
        else:
            rec = "maintain"
            volume = 25.0
        return {
            "region": _region(tool_input),
            "recommendation_type": rec,
            "irrigation_volume_mm": volume,
            "frequency_days": 5 if rec in ("increase", "emergency") else 7,
            "method": tool_input.context.get("irrigation_method", "canal"),
            "moisture_deficit_mm": round(deficit * 0.5, 1),
        }


class KnowledgeGraphTool(AbstractTool):
    @property
    def name(self) -> str:
        return "knowledge_graph_tool"

    @property
    def description(self) -> str:
        return "Surface Climate Knowledge Graph agricultural insights"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        from backend.agents.specialized.agriculture.agriculture_context import KnowledgeGraphInsights
        raw = tool_input.context.get("ckg_insights") or tool_input.parameters.get("ckg_insights")
        if isinstance(raw, KnowledgeGraphInsights):
            insights = raw
        elif isinstance(raw, dict):
            insights = KnowledgeGraphInsights.model_validate(raw)
        else:
            insights = KnowledgeGraphInsights()
        return {
            "region": _region(tool_input),
            "crop_dependencies": insights.crop_dependencies,
            "water_dependencies": insights.water_dependencies,
            "historical_impacts": insights.historical_impacts,
            "regional_suitability": insights.regional_suitability,
            "query_count": insights.query_count,
            "ckg_available": insights.query_count > 0,
        }


class DigitalTwinTool(AbstractTool):
    @property
    def name(self) -> str:
        return "digital_twin_tool"

    @property
    def description(self) -> str:
        return "Access agricultural digital twin field state"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SIMULATION

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"twin_id": {"type": "string"}}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        twin = tool_input.context.get("digital_twin_state") or {}
        layers = twin.get("layers", {}) if isinstance(twin, dict) else {}
        ag = layers.get("agriculture", layers.get("farm", {}))
        return {
            "twin_id": tool_input.context.get("twin_id"),
            "digital_twin_available": bool(twin),
            "agriculture_layers": ag if isinstance(ag, dict) else {},
            "field_scenario": twin.get("scenario_id") if isinstance(twin, dict) else None,
        }


class GovernmentAdvisoryTool(AbstractTool):
    @property
    def name(self) -> str:
        return "government_advisory_tool"

    @property
    def description(self) -> str:
        return "Surface government agricultural advisories from RAG retrieval"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        from backend.agents.specialized.agriculture.agriculture_context import RagRetrievalResult
        raw = tool_input.context.get("rag_result") or tool_input.parameters.get("rag_result")
        if isinstance(raw, RagRetrievalResult):
            rag = raw
        elif isinstance(raw, dict):
            rag = RagRetrievalResult.model_validate(raw)
        else:
            rag = RagRetrievalResult()
        advisories = [
            {"title": a.title, "content": a.content, "source": a.source, "relevance": a.relevance_score}
            for a in rag.advisories
        ]
        return {
            "region": _region(tool_input),
            "advisories": advisories,
            "advisory_count": len(advisories),
            "rag_documents": len(rag.documents),
            "has_government_advisory": len(advisories) > 0,
        }


def create_agriculture_tools() -> list[AbstractTool]:
    return [
        NDVITool(),
        EVITool(),
        SoilMoistureTool(),
        CropCalendarTool(),
        LandUseTool(),
        WeatherTool(),
        ForecastTool(),
        YieldEstimationTool(),
        IrrigationTool(),
        KnowledgeGraphTool(),
        DigitalTwinTool(),
        GovernmentAdvisoryTool(),
    ]


ALL_AGRICULTURE_TOOL_NAMES: list[str] = [t().name for t in (
    NDVITool, EVITool, SoilMoistureTool, CropCalendarTool, LandUseTool,
    WeatherTool, ForecastTool, YieldEstimationTool, IrrigationTool,
    KnowledgeGraphTool, DigitalTwinTool, GovernmentAdvisoryTool,
)]
