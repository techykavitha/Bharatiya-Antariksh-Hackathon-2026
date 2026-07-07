"""Dedicated tools for water resource management analysis."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.agents.specialized.water_resource.water_context import WaterInputs
from backend.agents.specialized.water_resource.water_models import (
    GroundwaterTrend,
    ReleaseStrategy,
    ReservoirStatus,
)
from backend.agents.tools.abstract_tool import AbstractTool, ToolInput
from backend.utils.enums import ToolCategory
from backend.utils.errors import ToolValidationError


def _extract_inputs(tool_input: ToolInput) -> WaterInputs:
    ctx = {**tool_input.context, **tool_input.parameters}
    return WaterInputs.from_request_context(ctx)


def _region(tool_input: ToolInput) -> str:
    inputs = _extract_inputs(tool_input)
    return inputs.region_id or "unknown_region"


class ReservoirTool(AbstractTool):
    """Monitors reservoir storage levels and overflow risk."""

    @property
    def name(self) -> str:
        return "reservoir_tool"

    @property
    def description(self) -> str:
        return "Assess reservoir storage, inflow/outflow balance, and spillway status"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "reservoir_level_pct": {"type": "number"},
                "reservoir_capacity_mcm": {"type": "number"},
                "spillway_active": {"type": "boolean"},
            },
        }

    def validate_input(self, tool_input: ToolInput) -> None:
        super().validate_input(tool_input)
        inputs = _extract_inputs(tool_input)
        if inputs.reservoir.level_pct is None and inputs.reservoir.live_storage_mcm is None:
            raise ToolValidationError(
                "Reservoir tool requires reservoir_level_pct or live_storage_mcm",
                details={"tool": self.name},
            )

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        r = inputs.reservoir
        level = r.level_pct or 0.0
        capacity = r.capacity_mcm or 1000.0
        live = r.live_storage_mcm or (capacity * level / 100.0)
        inflow = r.inflow_m3s or 0.0
        outflow = r.outflow_m3s or 0.0
        net_flow = inflow - outflow

        if level <= r.dead_storage_pct + 5:
            status = ReservoirStatus.CRITICAL_LOW
            release = ReleaseStrategy.CONSERVATION
        elif level >= 95.0 or r.spillway_active:
            status = ReservoirStatus.OVERFLOW_RISK
            release = ReleaseStrategy.EMERGENCY_SPILL
        elif level >= 85.0:
            status = ReservoirStatus.STRESSED
            release = ReleaseStrategy.CONTROLLED_RELEASE
        elif level >= 70.0:
            status = ReservoirStatus.ELEVATED
            release = ReleaseStrategy.GRADUAL_RELEASE
        else:
            status = ReservoirStatus.NORMAL
            release = ReleaseStrategy.HOLD

        stressed = level >= 85.0 or r.spillway_active
        overflow_risk = level >= 95.0 or r.spillway_active
        storage_score = level / 100.0

        return {
            "region": _region(tool_input),
            "reservoir_name": r.name or "primary_reservoir",
            "level_pct": level,
            "capacity_mcm": capacity,
            "live_storage_mcm": round(live, 2),
            "inflow_m3s": inflow,
            "outflow_m3s": outflow,
            "net_flow_m3s": round(net_flow, 2),
            "spillway_active": r.spillway_active,
            "status": status.value,
            "recommended_release": release.value,
            "stressed": stressed,
            "overflow_risk": overflow_risk,
            "storage_score": round(storage_score, 3),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


class RiverTool(AbstractTool):
    """Analyzes river basin conditions and flow balance."""

    @property
    def name(self) -> str:
        return "river_tool"

    @property
    def description(self) -> str:
        return "Assess river stage, discharge, and basin flow balance"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "river_level_m": {"type": "number"},
                "river_discharge_m3s": {"type": "number"},
                "basin_id": {"type": "string"},
            },
        }

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        river = inputs.river
        level = river.river_level_m or 0.0
        banks = river.river_banks_m or level + 3.0
        discharge = river.discharge_m3s or 0.0
        upstream = river.upstream_inflow_m3s or discharge
        downstream = river.downstream_demand_m3s or discharge * 0.7
        margin = banks - level
        overflow = level >= banks
        flow_balance = upstream - downstream
        healthy = not overflow and flow_balance >= 0

        return {
            "region": _region(tool_input),
            "basin_id": river.basin_id or inputs.basin_id or "unknown_basin",
            "river_level_m": level,
            "river_banks_m": banks,
            "discharge_m3s": discharge,
            "upstream_inflow_m3s": upstream,
            "downstream_demand_m3s": downstream,
            "flow_balance_m3s": round(flow_balance, 2),
            "bank_margin_m": round(margin, 2),
            "overflow": overflow,
            "river_healthy": healthy,
            "river_score": round(min(discharge / max(downstream, 1.0), 1.0), 3),
        }


class GroundwaterTool(AbstractTool):
    """Assesses groundwater levels and extraction trends."""

    @property
    def name(self) -> str:
        return "groundwater_tool"

    @property
    def description(self) -> str:
        return "Evaluate groundwater depth, recharge, and extraction balance"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "groundwater_depth_m": {"type": "number"},
                "groundwater_extraction_m3d": {"type": "number"},
            },
        }

    def validate_input(self, tool_input: ToolInput) -> None:
        super().validate_input(tool_input)
        inputs = _extract_inputs(tool_input)
        if (
            inputs.groundwater.depth_to_water_m is None
            and inputs.groundwater.level_m is None
        ):
            raise ToolValidationError(
                "Groundwater tool requires groundwater_depth_m or groundwater_level_m",
                details={"tool": self.name},
            )

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        gw = inputs.groundwater
        depth = gw.depth_to_water_m or (50.0 - (gw.level_m or 25.0))
        recharge = gw.recharge_rate_mm or 5.0
        extraction = gw.extraction_rate_m3d or 0.0
        trend = gw.trend

        declining = trend in (GroundwaterTrend.DECLINING, GroundwaterTrend.CRITICAL_DECLINE)
        critical = depth >= 40.0 or trend == GroundwaterTrend.CRITICAL_DECLINE
        sustainable = recharge * 1000 >= extraction * 0.001 and not declining
        score = max(0.0, min(1.0 - depth / 60.0, 1.0))

        return {
            "region": _region(tool_input),
            "aquifer_id": gw.aquifer_id or "primary_aquifer",
            "depth_to_water_m": round(depth, 2),
            "recharge_rate_mm": recharge,
            "extraction_rate_m3d": extraction,
            "trend": trend.value,
            "declining": declining,
            "critical": critical,
            "sustainable": sustainable,
            "groundwater_score": round(score, 3),
        }


class RainfallTool(AbstractTool):
    """Analyzes rainfall and monsoon conditions for water availability."""

    @property
    def name(self) -> str:
        return "rainfall_tool"

    @property
    def description(self) -> str:
        return "Assess current rainfall, forecast accumulation, and monsoon deficit"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FORECAST

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "rainfall_mm": {"type": "number"},
                "rainfall_forecast_24h_mm": {"type": "number"},
                "monsoon_normal_pct": {"type": "number"},
            },
        }

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        r = inputs.rainfall
        current = r.current_mm or 0.0
        f24 = r.forecast_24h_mm or 0.0
        f72 = r.forecast_72h_mm or 0.0
        monsoon = r.monsoon_cumulative_mm or 0.0
        normal_pct = r.monsoon_normal_pct or 100.0

        deficit = normal_pct < 80.0
        favorable = normal_pct >= 100.0 or f72 >= 50.0
        score = min((current / 50.0 + f24 / 80.0 + normal_pct / 120.0) / 3.0, 1.0)

        return {
            "region": _region(tool_input),
            "current_mm": current,
            "forecast_24h_mm": f24,
            "forecast_72h_mm": f72,
            "monsoon_cumulative_mm": monsoon,
            "monsoon_normal_pct": normal_pct,
            "rainfall_deficit": deficit,
            "favorable_rainfall": favorable,
            "rainfall_score": round(score, 3),
        }


class SoilMoistureTool(AbstractTool):
    """Evaluates soil moisture for irrigation demand."""

    @property
    def name(self) -> str:
        return "soil_moisture_tool"

    @property
    def description(self) -> str:
        return "Analyze soil moisture levels and irrigation deficit"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "soil_moisture": {"type": "number"},
                "root_zone_moisture": {"type": "number"},
            },
        }

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        sm = inputs.soil_moisture
        surface = sm.surface_moisture if sm.surface_moisture is not None else 0.4
        root = sm.root_zone_moisture if sm.root_zone_moisture is not None else surface
        deficit = sm.deficit_index if sm.deficit_index is not None else max(0.0, 0.6 - root)
        irrigation_needed = deficit > 0.3 or root < 0.35

        return {
            "region": _region(tool_input),
            "surface_moisture": surface,
            "root_zone_moisture": root,
            "deficit_index": round(deficit, 3),
            "irrigation_needed": irrigation_needed,
            "soil_moisture_score": round(root, 3),
        }


class PopulationTool(AbstractTool):
    """Estimates population for urban water demand."""

    @property
    def name(self) -> str:
        return "population_tool"

    @property
    def description(self) -> str:
        return "Estimate population and per-capita water demand"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "population": {"type": "integer"},
                "districts": {"type": "array", "items": {"type": "string"}},
            },
        }

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        districts = inputs.districts or ["default_district"]
        population = inputs.demand.population or len(districts) * 500_000
        per_capita_lpcd = 135.0
        daily_demand_m3 = (population * per_capita_lpcd) / 1000.0

        return {
            "region": _region(tool_input),
            "districts": districts,
            "population": population,
            "per_capita_lpcd": per_capita_lpcd,
            "estimated_urban_demand_m3d": round(daily_demand_m3, 2),
        }


class DemandTool(AbstractTool):
    """Estimates total water demand across sectors."""

    @property
    def name(self) -> str:
        return "demand_tool"

    @property
    def description(self) -> str:
        return "Compute urban, agricultural, and industrial water demand"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "urban_demand_m3d": {"type": "number"},
                "agricultural_demand_m3d": {"type": "number"},
                "crop_area_ha": {"type": "number"},
            },
        }

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        d = inputs.demand
        urban = d.urban_demand_m3d or 0.0
        agri = d.agricultural_demand_m3d or 0.0
        industrial = d.industrial_demand_m3d or 0.0

        if agri == 0.0 and d.crop_area_ha:
            efficiency = d.irrigation_efficiency or 0.45
            agri = d.crop_area_ha * 50.0 / efficiency

        if urban == 0.0 and d.population:
            urban = (d.population * 135.0) / 1000.0

        total = urban + agri + industrial
        urban_high = urban > total * 0.4 if total > 0 else False
        agri_high = agri > total * 0.5 if total > 0 else False

        return {
            "region": _region(tool_input),
            "urban_demand_m3d": round(urban, 2),
            "agricultural_demand_m3d": round(agri, 2),
            "industrial_demand_m3d": round(industrial, 2),
            "total_demand_m3d": round(total, 2),
            "crop_area_ha": d.crop_area_ha,
            "crop_type": d.crop_type,
            "urban_demand_high": urban_high,
            "agricultural_demand_high": agri_high,
            "demand_score": round(min(total / 1_000_000.0, 1.0), 3),
        }


class ForecastTool(AbstractTool):
    """Integrates meteorological forecast for water planning."""

    @property
    def name(self) -> str:
        return "forecast_tool"

    @property
    def description(self) -> str:
        return "Retrieve precipitation forecast for water availability planning"

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
        improving = f72 > f24 * 1.2

        return {
            "region": _region(tool_input),
            "forecast_24h_mm": f24,
            "forecast_72h_mm": f72,
            "forecast_available": inputs.forecast_available or f24 > 0 or f72 > 0,
            "improving_trend": improving,
            "forecast_score": round(min((f24 + f72) / 150.0, 1.0), 3),
        }


class DigitalTwinTool(AbstractTool):
    """Reads water-relevant layers from the digital twin."""

    @property
    def name(self) -> str:
        return "digital_twin_tool"

    @property
    def description(self) -> str:
        return "Access digital twin water resource layers and scenario state"

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
        water_layer = layers.get("water", {}) if isinstance(layers, dict) else {}

        return {
            "twin_id": tool_input.context.get("twin_id") or tool_input.parameters.get("twin_id"),
            "digital_twin_available": bool(twin_state) or tool_input.context.get("digital_twin_available"),
            "water_layers": water_layer,
            "reservoir_level_pct": water_layer.get("reservoir_level_pct"),
            "basin_flow_m3s": water_layer.get("basin_flow_m3s"),
            "active_scenario": twin_state.get("scenario_id"),
        }


class HistoricalWaterTool(AbstractTool):
    """Compares current conditions against historical water records."""

    @property
    def name(self) -> str:
        return "historical_water_tool"

    @property
    def description(self) -> str:
        return "Retrieve and compare historical water level records"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.RETRIEVAL

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"region_id": {"type": "string"}}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        records = inputs.historical_records
        current_level = inputs.reservoir.level_pct or 0.0
        analog = False
        drought_analog = False
        comparable: list[dict[str, Any]] = []

        for record in records:
            comparable.append(record.model_dump())
            if record.reservoir_level_pct and current_level <= record.reservoir_level_pct * 1.1:
                if record.stress_level.value in ("high", "severe", "critical"):
                    drought_analog = True
            if record.rainfall_mm and inputs.rainfall.current_mm:
                if inputs.rainfall.current_mm >= record.rainfall_mm * 0.9:
                    analog = True

        return {
            "region": _region(tool_input),
            "record_count": len(records),
            "historical_analog": analog,
            "drought_analog": drought_analog,
            "records": comparable,
            "historical_score": round(min(len(records) / 5.0, 1.0) if records else 0.2, 3),
        }


def create_water_tools() -> list[AbstractTool]:
    """Factory returning all water resource analysis tools."""
    return [
        ReservoirTool(),
        RiverTool(),
        GroundwaterTool(),
        RainfallTool(),
        SoilMoistureTool(),
        PopulationTool(),
        DemandTool(),
        ForecastTool(),
        DigitalTwinTool(),
        HistoricalWaterTool(),
    ]


ALL_WATER_TOOL_NAMES: list[str] = [t().name for t in (
    ReservoirTool, RiverTool, GroundwaterTool, RainfallTool, SoilMoistureTool,
    PopulationTool, DemandTool, ForecastTool, DigitalTwinTool, HistoricalWaterTool,
)]
