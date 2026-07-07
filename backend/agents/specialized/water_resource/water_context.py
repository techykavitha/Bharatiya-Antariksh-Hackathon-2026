"""Water resource analysis domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.agents.specialized.water_resource.water_models import (
    GroundwaterTrend,
    ReleaseStrategy,
    ReservoirStatus,
    WaterAvailabilityBand,
    WaterStressLevel,
)
from backend.agents.state.climate_state import GeoLocation


class ReservoirInput(BaseModel):
    """Reservoir storage and operational inputs."""

    level_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    capacity_mcm: float | None = Field(default=None, ge=0.0)
    live_storage_mcm: float | None = Field(default=None, ge=0.0)
    inflow_m3s: float | None = Field(default=None, ge=0.0)
    outflow_m3s: float | None = Field(default=None, ge=0.0)
    spillway_active: bool = False
    dead_storage_pct: float = Field(default=10.0, ge=0.0, le=50.0)
    name: str | None = None


class RiverBasinInput(BaseModel):
    """River basin hydrology inputs."""

    river_level_m: float | None = Field(default=None)
    river_banks_m: float | None = Field(default=None)
    discharge_m3s: float | None = Field(default=None, ge=0.0)
    basin_id: str | None = None
    upstream_inflow_m3s: float | None = Field(default=None, ge=0.0)
    downstream_demand_m3s: float | None = Field(default=None, ge=0.0)


class GroundwaterInput(BaseModel):
    """Groundwater aquifer inputs."""

    level_m: float | None = Field(default=None)
    depth_to_water_m: float | None = Field(default=None, ge=0.0)
    recharge_rate_mm: float | None = Field(default=None, ge=0.0)
    extraction_rate_m3d: float | None = Field(default=None, ge=0.0)
    trend: GroundwaterTrend = GroundwaterTrend.UNKNOWN
    aquifer_id: str | None = None


class RainfallForecastInput(BaseModel):
    """Rainfall forecast inputs for water availability."""

    current_mm: float | None = Field(default=None, ge=0.0)
    forecast_24h_mm: float | None = Field(default=None, ge=0.0)
    forecast_72h_mm: float | None = Field(default=None, ge=0.0)
    monsoon_cumulative_mm: float | None = Field(default=None, ge=0.0)
    monsoon_normal_pct: float | None = Field(default=None, ge=0.0)


class DemandInput(BaseModel):
    """Water demand from urban and agricultural sectors."""

    urban_demand_m3d: float | None = Field(default=None, ge=0.0)
    agricultural_demand_m3d: float | None = Field(default=None, ge=0.0)
    industrial_demand_m3d: float | None = Field(default=None, ge=0.0)
    crop_area_ha: float | None = Field(default=None, ge=0.0)
    crop_type: str | None = None
    irrigation_efficiency: float | None = Field(default=None, ge=0.0, le=1.0)
    population: int | None = Field(default=None, ge=0)


class SoilMoistureInput(BaseModel):
    """Soil moisture for agricultural water demand estimation."""

    surface_moisture: float | None = Field(default=None, ge=0.0, le=1.0)
    root_zone_moisture: float | None = Field(default=None, ge=0.0, le=1.0)
    deficit_index: float | None = Field(default=None, ge=0.0, le=1.0)


class HistoricalWaterRecord(BaseModel):
    """Historical water level record for trend comparison."""

    record_id: str
    year: int
    month: int | None = None
    reservoir_level_pct: float | None = None
    groundwater_depth_m: float | None = None
    rainfall_mm: float | None = None
    stress_level: WaterStressLevel = WaterStressLevel.NONE
    notes: str = ""


class WaterAnalysisSignals(BaseModel):
    """Intermediate signals computed during water resource reasoning."""

    storage_adequate: bool = False
    storage_stressed: bool = False
    overflow_risk: bool = False
    river_healthy: bool = True
    groundwater_declining: bool = False
    rainfall_deficit: bool = False
    urban_demand_high: bool = False
    agricultural_demand_high: bool = False
    inter_basin_dependency: bool = False
    storage_score: float = Field(default=0.0, ge=0.0, le=1.0)
    rainfall_score: float = Field(default=0.0, ge=0.0, le=1.0)
    river_score: float = Field(default=0.0, ge=0.0, le=1.0)
    groundwater_score: float = Field(default=0.0, ge=0.0, le=1.0)
    demand_score: float = Field(default=0.0, ge=0.0, le=1.0)
    availability_score: float = Field(default=0.0, ge=0.0, le=1.0)
    stress_score: float = Field(default=0.0, ge=0.0, le=1.0)
    composite_score: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: float = Field(default=0.5, ge=0.0, le=1.0)


class ReservoirStatusReport(BaseModel):
    """Per-reservoir status summary."""

    reservoir_id: str
    name: str
    level_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    status: ReservoirStatus = ReservoirStatus.UNKNOWN
    live_storage_mcm: float = Field(default=0.0, ge=0.0)
    recommended_release: ReleaseStrategy = ReleaseStrategy.HOLD
    overflow_risk: bool = False


class WaterAvailabilityEstimate(BaseModel):
    """Quantified water availability output."""

    band: WaterAvailabilityBand = WaterAvailabilityBand.ADEQUATE
    score: float = Field(default=0.5, ge=0.0, le=1.0)
    supply_m3d: float = Field(default=0.0, ge=0.0)
    demand_m3d: float = Field(default=0.0, ge=0.0)
    surplus_deficit_m3d: float = 0.0
    horizon_days: int = Field(default=30, ge=1)
    drivers: list[str] = Field(default_factory=list)


class DecisionRequest(BaseModel):
    """Structured decision output from the water decision engine."""

    request_id: str = Field(default_factory=lambda: str(uuid4()))
    need_rl: bool = False
    need_flood_agent: bool = False
    need_agriculture_agent: bool = False
    need_urban_planning_agent: bool = False
    need_disaster_agent: bool = False
    need_simulation: bool = False
    need_forecast_update: bool = False
    suggested_agents: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
    priority: str = "normal"
    metadata: dict[str, Any] = Field(default_factory=dict)


class WaterInputs(BaseModel):
    """Aggregated water resource inputs extracted from request context."""

    location: GeoLocation | None = None
    region_id: str | None = None
    basin_id: str | None = None
    districts: list[str] = Field(default_factory=list)
    reservoir: ReservoirInput = Field(default_factory=ReservoirInput)
    river: RiverBasinInput = Field(default_factory=RiverBasinInput)
    groundwater: GroundwaterInput = Field(default_factory=GroundwaterInput)
    rainfall: RainfallForecastInput = Field(default_factory=RainfallForecastInput)
    demand: DemandInput = Field(default_factory=DemandInput)
    soil_moisture: SoilMoistureInput = Field(default_factory=SoilMoistureInput)
    historical_records: list[HistoricalWaterRecord] = Field(default_factory=list)
    dependent_basins: list[str] = Field(default_factory=list)
    twin_id: str | None = None
    forecast_available: bool = False
    climate_state_available: bool = False
    digital_twin_available: bool = False
    reservoir_available: bool = False
    groundwater_available: bool = False

    @classmethod
    def from_request_context(cls, context: dict[str, Any]) -> WaterInputs:
        """Parse water inputs from an agent request context dictionary."""
        location = None
        if "latitude" in context and "longitude" in context:
            location = GeoLocation(
                latitude=float(context["latitude"]),
                longitude=float(context["longitude"]),
                elevation_m=context.get("elevation_m"),
                region_id=context.get("region_id"),
            )
        elif context.get("location"):
            loc = context["location"]
            if isinstance(loc, dict):
                location = GeoLocation.model_validate(loc)
            elif isinstance(loc, GeoLocation):
                location = loc

        reservoir = ReservoirInput(
            level_pct=context.get("reservoir_level_pct"),
            capacity_mcm=context.get("reservoir_capacity_mcm"),
            live_storage_mcm=context.get("live_storage_mcm"),
            inflow_m3s=context.get("reservoir_inflow_m3s"),
            outflow_m3s=context.get("reservoir_outflow_m3s"),
            spillway_active=bool(context.get("spillway_active", False)),
            dead_storage_pct=float(context.get("dead_storage_pct", 10.0)),
            name=context.get("reservoir_name"),
        )
        river = RiverBasinInput(
            river_level_m=context.get("river_level_m"),
            river_banks_m=context.get("river_banks_m"),
            discharge_m3s=context.get("river_discharge_m3s"),
            basin_id=context.get("basin_id"),
            upstream_inflow_m3s=context.get("upstream_inflow_m3s"),
            downstream_demand_m3s=context.get("downstream_demand_m3s"),
        )
        gw_trend = str(context.get("groundwater_trend", "unknown"))
        try:
            gw_trend_enum = GroundwaterTrend(gw_trend)
        except ValueError:
            gw_trend_enum = GroundwaterTrend.UNKNOWN
        groundwater = GroundwaterInput(
            level_m=context.get("groundwater_level_m"),
            depth_to_water_m=context.get("groundwater_depth_m"),
            recharge_rate_mm=context.get("groundwater_recharge_mm"),
            extraction_rate_m3d=context.get("groundwater_extraction_m3d"),
            trend=gw_trend_enum,
            aquifer_id=context.get("aquifer_id"),
        )
        rainfall = RainfallForecastInput(
            current_mm=context.get("rainfall_mm"),
            forecast_24h_mm=context.get("rainfall_forecast_24h_mm"),
            forecast_72h_mm=context.get("rainfall_forecast_72h_mm"),
            monsoon_cumulative_mm=context.get("monsoon_cumulative_mm"),
            monsoon_normal_pct=context.get("monsoon_normal_pct"),
        )
        demand = DemandInput(
            urban_demand_m3d=context.get("urban_demand_m3d"),
            agricultural_demand_m3d=context.get("agricultural_demand_m3d"),
            industrial_demand_m3d=context.get("industrial_demand_m3d"),
            crop_area_ha=context.get("crop_area_ha"),
            crop_type=context.get("crop_type"),
            irrigation_efficiency=context.get("irrigation_efficiency"),
            population=context.get("population"),
        )
        soil_moisture = SoilMoistureInput(
            surface_moisture=context.get("soil_moisture") or context.get("surface_moisture"),
            root_zone_moisture=context.get("root_zone_moisture"),
            deficit_index=context.get("soil_moisture_deficit"),
        )

        historical: list[HistoricalWaterRecord] = []
        for raw in context.get("historical_water_levels", []):
            if isinstance(raw, HistoricalWaterRecord):
                historical.append(raw)
            elif isinstance(raw, dict):
                historical.append(HistoricalWaterRecord.model_validate(raw))

        return cls(
            location=location,
            region_id=context.get("region_id") or (location.region_id if location else None),
            basin_id=context.get("basin_id"),
            districts=list(context.get("districts", [])),
            reservoir=reservoir,
            river=river,
            groundwater=groundwater,
            rainfall=rainfall,
            demand=demand,
            soil_moisture=soil_moisture,
            historical_records=historical,
            dependent_basins=list(context.get("dependent_basins", [])),
            twin_id=context.get("twin_id"),
            forecast_available=bool(context.get("forecast_available")),
            climate_state_available=bool(context.get("climate_state_available")),
            digital_twin_available=bool(context.get("digital_twin_available")),
            reservoir_available=bool(
                context.get("reservoir_available")
                or context.get("reservoir_level_pct") is not None
            ),
            groundwater_available=bool(
                context.get("groundwater_available")
                or context.get("groundwater_level_m") is not None
                or context.get("groundwater_depth_m") is not None
            ),
        )
