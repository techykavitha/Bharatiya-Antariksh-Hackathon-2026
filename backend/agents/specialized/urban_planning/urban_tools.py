"""Dedicated tools for urban climate planning and adaptation analysis."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.agents.specialized.urban_planning.urban_context import UrbanInputs
from backend.agents.tools.abstract_tool import AbstractTool, ToolInput
from backend.utils.enums import ToolCategory


def _extract_inputs(tool_input: ToolInput) -> UrbanInputs:
    ctx = {**tool_input.context, **tool_input.parameters}
    return UrbanInputs.from_request_context(ctx)


def _region(tool_input: ToolInput) -> str:
    return _extract_inputs(tool_input).region_id or "unknown_region"


def _schema(*properties: str) -> dict[str, Any]:
    return {"type": "object", "properties": {name: {"type": "number"} for name in properties}}


class LandUseTool(AbstractTool):
    @property
    def name(self) -> str:
        return "land_use_tool"

    @property
    def description(self) -> str:
        return "Analyze land-use composition and climate exposure"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GEOSPATIAL

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        lu = inputs.land_use
        climate_exposure = min(
            (lu.impervious_pct / 100.0) * 0.5 + (lu.industrial_pct / 100.0) * 0.3 + 0.2,
            1.0,
        )
        return {
            "region": _region(tool_input),
            "residential_pct": lu.residential_pct,
            "commercial_pct": lu.commercial_pct,
            "industrial_pct": lu.industrial_pct,
            "green_pct": lu.green_pct,
            "impervious_pct": lu.impervious_pct,
            "dominant_category": lu.dominant_category.value,
            "climate_exposure_score": round(climate_exposure, 3),
            "rezoning_opportunity": lu.impervious_pct > 55 and lu.green_pct < 15,
        }


class NDVITool(AbstractTool):
    @property
    def name(self) -> str:
        return "ndvi_tool"

    @property
    def description(self) -> str:
        return "Assess vegetation index and urban cooling potential"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GEOSPATIAL

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("ndvi")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        ndvi = inputs.environment.ndvi
        low_vegetation = ndvi < 0.25
        cooling_potential = max(0.0, min((0.6 - ndvi) / 0.6, 1.0))
        return {
            "region": _region(tool_input),
            "ndvi": round(ndvi, 3),
            "low_vegetation": low_vegetation,
            "cooling_potential_score": round(cooling_potential, 3),
            "tree_planting_priority": low_vegetation,
        }


class BuildingTool(AbstractTool):
    @property
    def name(self) -> str:
        return "building_tool"

    @property
    def description(self) -> str:
        return "Assess building density and heat exposure"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("building_density")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        density = inputs.environment.building_density
        lst = inputs.environment.lst_c or 35.0
        heat_exposure = min(density * 0.6 + min(lst / 50.0, 1.0) * 0.4, 1.0)
        return {
            "region": _region(tool_input),
            "building_density": round(density, 3),
            "heat_exposure_score": round(heat_exposure, 3),
            "cool_roof_candidate": heat_exposure >= 0.55,
            "green_roof_candidate": density >= 0.45 and inputs.environment.green_cover_pct < 25,
            "retrofit_priority": heat_exposure >= 0.65,
        }


class RoadTool(AbstractTool):
    @property
    def name(self) -> str:
        return "road_tool"

    @property
    def description(self) -> str:
        return "Assess road network climate risk and permeability opportunities"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        roads = tool_input.context.get("road_network", {
            "arterial_km": 120.0,
            "local_km": 450.0,
            "impervious_road_pct": 88.0,
        })
        impervious = float(roads.get("impervious_road_pct", inputs.land_use.impervious_pct))
        climate_risk = min(impervious / 100.0 * 0.7 + inputs.environment.uhi_intensity_c / 10.0 * 0.3, 1.0)
        return {
            "region": _region(tool_input),
            "arterial_km": roads.get("arterial_km", 0),
            "local_km": roads.get("local_km", 0),
            "impervious_road_pct": impervious,
            "climate_risk_score": round(climate_risk, 3),
            "permeable_pavement_opportunity": impervious > 75,
        }


class DrainageTool(AbstractTool):
    @property
    def name(self) -> str:
        return "drainage_tool"

    @property
    def description(self) -> str:
        return "Assess drainage capacity and stormwater management needs"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("drainage_capacity_score")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        d = inputs.drainage
        deficit = d.capacity_score < 0.45
        stormwater_need = deficit or inputs.land_use.impervious_pct > 60
        return {
            "region": _region(tool_input),
            "capacity_score": round(d.capacity_score, 3),
            "detention_volume_m3": d.detention_volume_m3,
            "conveyance_adequacy": d.conveyance_adequacy,
            "flood_prone_zones": d.flood_prone_zones,
            "drainage_deficit": deficit,
            "stormwater_upgrade_required": stormwater_need,
            "rain_garden_opportunity": stormwater_need and inputs.environment.green_cover_pct < 20,
        }


class GreenCoverTool(AbstractTool):
    @property
    def name(self) -> str:
        return "green_cover_tool"

    @property
    def description(self) -> str:
        return "Assess urban green cover and forest expansion potential"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GEOSPATIAL

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("green_cover_pct")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        current = inputs.environment.green_cover_pct or inputs.land_use.green_pct
        target = float(tool_input.context.get("green_cover_target_pct", 33.0))
        gap = max(target - current, 0.0)
        return {
            "region": _region(tool_input),
            "current_cover_pct": round(current, 2),
            "target_cover_pct": target,
            "canopy_gap_pct": round(gap, 2),
            "low_green_cover": current < 20.0,
            "urban_forest_opportunity": gap >= 8.0,
            "cooling_potential_score": round(min(gap / 20.0, 1.0), 3),
        }


class PopulationTool(AbstractTool):
    @property
    def name(self) -> str:
        return "population_tool"

    @property
    def description(self) -> str:
        return "Estimate urban population exposure to climate risks"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("population_density")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        density = inputs.environment.population_density or 8000.0
        districts = max(len(inputs.districts), 1)
        total = int(density * 25 * districts)
        vulnerable = int(total * 0.28)
        return {
            "region": _region(tool_input),
            "population_density": density,
            "estimated_population": total,
            "vulnerable_population": vulnerable,
            "high_density_exposure": density > 12_000,
            "districts": inputs.districts,
        }


class ForecastTool(AbstractTool):
    @property
    def name(self) -> str:
        return "forecast_tool"

    @property
    def description(self) -> str:
        return "Assess climate forecast horizon for long-term planning"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FORECAST

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"horizon_years": {"type": "number"}}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        horizon = int(tool_input.context.get("planning_horizon_years", inputs.planning_horizon_years))
        warming_trend = float(tool_input.context.get("warming_trend_c_per_decade", 0.35))
        return {
            "region": _region(tool_input),
            "planning_horizon_years": horizon,
            "forecast_available": inputs.forecast_available,
            "warming_trend_c_per_decade": warming_trend,
            "escalating_heat_risk": warming_trend >= 0.3,
            "escalating_flood_risk": inputs.drainage.capacity_score < 0.5,
        }


class DigitalTwinTool(AbstractTool):
    @property
    def name(self) -> str:
        return "digital_twin_tool"

    @property
    def description(self) -> str:
        return "Access urban digital twin layers for scenario planning"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SIMULATION

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"twin_id": {"type": "string"}}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        twin = tool_input.context.get("digital_twin_state") or {}
        layers = twin.get("layers", {}) if isinstance(twin, dict) else {}
        urban = layers.get("urban", layers.get("planning", {}))
        return {
            "twin_id": tool_input.context.get("twin_id"),
            "digital_twin_available": bool(twin),
            "urban_layers": urban if isinstance(urban, dict) else {},
            "scenario_ready": bool(urban),
        }


class KnowledgeGraphTool(AbstractTool):
    @property
    def name(self) -> str:
        return "knowledge_graph_tool"

    @property
    def description(self) -> str:
        return "Surface Climate Knowledge Graph urban planning insights"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        from backend.agents.specialized.urban_planning.urban_context import KnowledgeGraphInsights
        raw = tool_input.context.get("ckg_insights") or tool_input.parameters.get("ckg_insights")
        if isinstance(raw, KnowledgeGraphInsights):
            insights = raw
        elif isinstance(raw, dict):
            insights = KnowledgeGraphInsights.model_validate(raw)
        else:
            insights = KnowledgeGraphInsights()
        return {
            "region": _region(tool_input),
            "urban_dependencies": insights.urban_dependencies,
            "infrastructure_nodes": insights.infrastructure_nodes,
            "population_nodes": insights.population_nodes,
            "historical_mitigation_projects": insights.historical_mitigation_projects,
            "query_count": insights.query_count,
            "ckg_available": insights.query_count > 0,
        }


class InfrastructureTool(AbstractTool):
    @property
    def name(self) -> str:
        return "infrastructure_tool"

    @property
    def description(self) -> str:
        return "Assess critical urban infrastructure climate exposure"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        infra = tool_input.context.get("critical_infrastructure", [
            {"id": "power-grid", "name": "City Power Grid", "category": "power"},
            {"id": "water-treatment", "name": "Water Treatment Plant", "category": "water"},
            {"id": "metro-network", "name": "Metro Network", "category": "transport"},
        ])
        inputs = _extract_inputs(tool_input)
        exposure = min(
            inputs.environment.building_density * 0.3
            + (1.0 - inputs.drainage.capacity_score) * 0.35
            + inputs.environment.uhi_intensity_c / 12.0 * 0.35,
            1.0,
        )
        return {
            "region": _region(tool_input),
            "infrastructure_assets": [i for i in infra if isinstance(i, dict)],
            "exposure_score": round(exposure, 3),
            "protection_required": exposure >= 0.55,
            "asset_count": len(infra),
        }


def create_urban_tools() -> list[AbstractTool]:
    return [
        LandUseTool(),
        NDVITool(),
        BuildingTool(),
        RoadTool(),
        DrainageTool(),
        GreenCoverTool(),
        PopulationTool(),
        ForecastTool(),
        DigitalTwinTool(),
        KnowledgeGraphTool(),
        InfrastructureTool(),
    ]


ALL_URBAN_TOOL_NAMES: list[str] = [t().name for t in (
    LandUseTool, NDVITool, BuildingTool, RoadTool, DrainageTool,
    GreenCoverTool, PopulationTool, ForecastTool, DigitalTwinTool,
    KnowledgeGraphTool, InfrastructureTool,
)]
