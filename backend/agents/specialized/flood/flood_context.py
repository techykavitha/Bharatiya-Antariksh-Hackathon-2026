"""Flood analysis domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.agents.specialized.flood.flood_models import (
    FloodProbabilityBand,
    FloodRiskLevel,
    FloodSeverity,
    FloodType,
)
from backend.agents.state.climate_state import GeoLocation


class RainfallInput(BaseModel):
    """Rainfall observations and forecast inputs."""

    current_mm: float | None = Field(default=None, ge=0.0)
    forecast_24h_mm: float | None = Field(default=None, ge=0.0)
    forecast_72h_mm: float | None = Field(default=None, ge=0.0)
    intensity_mm_per_hr: float | None = Field(default=None, ge=0.0)
    antecedent_7d_mm: float | None = Field(default=None, ge=0.0)


class HydrologyInput(BaseModel):
    """River and reservoir level inputs."""

    river_level_m: float | None = Field(default=None)
    river_banks_m: float | None = Field(default=None)
    river_discharge_m3s: float | None = Field(default=None, ge=0.0)
    reservoir_level_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    reservoir_capacity_mcm: float | None = Field(default=None, ge=0.0)
    spillway_active: bool = False


class TerrainInput(BaseModel):
    """Terrain and hydrological routing inputs."""

    dem_resolution_m: float | None = Field(default=None, ge=0.0)
    mean_elevation_m: float | None = Field(default=None)
    slope_deg: float | None = Field(default=None, ge=0.0, le=90.0)
    drainage_capacity: float | None = Field(default=None, ge=0.0, le=1.0)
    soil_moisture: float | None = Field(default=None, ge=0.0, le=1.0)
    land_cover: str | None = None
    urban_density: float | None = Field(default=None, ge=0.0, le=1.0)
    impervious_fraction: float | None = Field(default=None, ge=0.0, le=1.0)


class HistoricalFloodEvent(BaseModel):
    """Record of a historical flood event for comparison."""

    event_id: str
    year: int
    flood_type: FloodType
    peak_depth_m: float = Field(ge=0.0)
    affected_population: int = Field(default=0, ge=0)
    districts: list[str] = Field(default_factory=list)
    rainfall_mm: float | None = None
    notes: str = ""


class FloodAnalysisSignals(BaseModel):
    """Intermediate signals computed during flood reasoning."""

    heavy_rainfall: bool = False
    river_overflow: bool = False
    terrain_vulnerable: bool = False
    reservoir_stressed: bool = False
    historical_analog: bool = False
    coastal_surge_risk: bool = False
    urban_pluvial_risk: bool = False
    rainfall_score: float = Field(default=0.0, ge=0.0, le=1.0)
    hydrology_score: float = Field(default=0.0, ge=0.0, le=1.0)
    terrain_score: float = Field(default=0.0, ge=0.0, le=1.0)
    historical_score: float = Field(default=0.0, ge=0.0, le=1.0)
    composite_score: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: float = Field(default=0.5, ge=0.0, le=1.0)


class AffectedDistrict(BaseModel):
    """District-level flood impact estimate."""

    district_id: str
    name: str
    expected_depth_m: float = Field(default=0.0, ge=0.0)
    population_at_risk: int = Field(default=0, ge=0)
    risk_level: FloodRiskLevel = FloodRiskLevel.MINIMAL
    probability: FloodProbabilityBand = FloodProbabilityBand.VERY_LOW


class FloodProbabilityEstimate(BaseModel):
    """Quantified flood probability output."""

    band: FloodProbabilityBand = FloodProbabilityBand.LOW
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    horizon_hours: int = Field(default=72, ge=1)
    drivers: list[str] = Field(default_factory=list)


class DecisionRequest(BaseModel):
    """Structured decision output from the flood decision engine."""

    request_id: str = Field(default_factory=lambda: str(uuid4()))
    need_rl: bool = False
    need_water_resource_agent: bool = False
    need_disaster_agent: bool = False
    need_cyclone_agent: bool = False
    need_air_quality_agent: bool = False
    need_urban_planning_agent: bool = False
    need_simulation: bool = False
    need_forecast_update: bool = False
    need_reservoir_optimization: bool = False
    suggested_agents: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
    priority: str = "normal"
    metadata: dict[str, Any] = Field(default_factory=dict)


class FloodInputs(BaseModel):
    """Aggregated flood analysis inputs extracted from request context."""

    location: GeoLocation | None = None
    region_id: str | None = None
    districts: list[str] = Field(default_factory=list)
    rainfall: RainfallInput = Field(default_factory=RainfallInput)
    hydrology: HydrologyInput = Field(default_factory=HydrologyInput)
    terrain: TerrainInput = Field(default_factory=TerrainInput)
    historical_events: list[HistoricalFloodEvent] = Field(default_factory=list)
    twin_id: str | None = None
    forecast_available: bool = False
    climate_state_available: bool = False
    digital_twin_available: bool = False
    dem_available: bool = False

    @classmethod
    def from_request_context(cls, context: dict[str, Any]) -> FloodInputs:
        """Parse flood inputs from an agent request context dictionary."""
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

        rainfall = RainfallInput(
            current_mm=context.get("rainfall_mm"),
            forecast_24h_mm=context.get("rainfall_forecast_24h_mm"),
            forecast_72h_mm=context.get("rainfall_forecast_72h_mm"),
            intensity_mm_per_hr=context.get("rainfall_intensity_mm_per_hr"),
            antecedent_7d_mm=context.get("antecedent_rainfall_7d_mm"),
        )
        hydrology = HydrologyInput(
            river_level_m=context.get("river_level_m"),
            river_banks_m=context.get("river_banks_m"),
            river_discharge_m3s=context.get("river_discharge_m3s"),
            reservoir_level_pct=context.get("reservoir_level_pct"),
            reservoir_capacity_mcm=context.get("reservoir_capacity_mcm"),
            spillway_active=bool(context.get("spillway_active", False)),
        )
        terrain = TerrainInput(
            dem_resolution_m=context.get("dem_resolution_m"),
            mean_elevation_m=context.get("mean_elevation_m"),
            slope_deg=context.get("slope_deg"),
            drainage_capacity=context.get("drainage_capacity"),
            soil_moisture=context.get("soil_moisture"),
            land_cover=context.get("land_cover"),
            urban_density=context.get("urban_density"),
            impervious_fraction=context.get("impervious_fraction"),
        )

        historical: list[HistoricalFloodEvent] = []
        for raw in context.get("historical_floods", []):
            if isinstance(raw, HistoricalFloodEvent):
                historical.append(raw)
            elif isinstance(raw, dict):
                historical.append(HistoricalFloodEvent.model_validate(raw))

        return cls(
            location=location,
            region_id=context.get("region_id") or (location.region_id if location else None),
            districts=list(context.get("districts", [])),
            rainfall=rainfall,
            hydrology=hydrology,
            terrain=terrain,
            historical_events=historical,
            twin_id=context.get("twin_id"),
            forecast_available=bool(context.get("forecast_available")),
            climate_state_available=bool(context.get("climate_state_available")),
            digital_twin_available=bool(context.get("digital_twin_available")),
            dem_available=bool(context.get("dem_available") or context.get("dem_resolution_m")),
        )
