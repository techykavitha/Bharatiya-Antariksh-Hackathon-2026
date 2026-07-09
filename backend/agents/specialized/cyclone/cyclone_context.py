"""Cyclone analysis domain models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.agents.specialized.cyclone.cyclone_models import (
    CycloneBasin,
    CycloneCategory,
    CycloneRiskLevel,
    CycloneSeverity,
    RapidIntensificationStatus,
)
from backend.agents.state.climate_state import GeoLocation


class OceanAtmosphereInput(BaseModel):
    """Sea surface and atmospheric state inputs."""

    sst_c: float | None = Field(default=None)
    sea_level_pressure_hpa: float | None = Field(default=None)
    wind_speed_kt: float | None = Field(default=None, ge=0.0)
    wind_direction_deg: float | None = Field(default=None, ge=0.0, le=360.0)
    humidity_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    ocean_heat_content_kj_cm2: float | None = Field(default=None, ge=0.0)
    cloud_top_temp_c: float | None = Field(default=None)
    vertical_wind_shear_kt: float | None = Field(default=None, ge=0.0)


class TrackPoint(BaseModel):
    """Cyclone position on forecast or observed track."""

    latitude: float
    longitude: float
    timestamp_iso: str | None = None
    wind_speed_kt: float | None = Field(default=None, ge=0.0)
    pressure_hpa: float | None = Field(default=None)


class ForecastInput(BaseModel):
    """Track and intensity forecast inputs."""

    track_points: list[TrackPoint] = Field(default_factory=list)
    landfall_latitude: float | None = None
    landfall_longitude: float | None = None
    landfall_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    landfall_hours: float | None = Field(default=None, ge=0.0)
    max_wind_kt_forecast: float | None = Field(default=None, ge=0.0)
    rainfall_mm_24h: float | None = Field(default=None, ge=0.0)
    rainfall_mm_72h: float | None = Field(default=None, ge=0.0)


class HistoricalCycloneEvent(BaseModel):
    """Record of a historical cyclone for analog comparison."""

    event_id: str
    name: str
    year: int
    basin: CycloneBasin = CycloneBasin.BAY_OF_BENGAL
    peak_wind_kt: float = Field(ge=0.0)
    min_pressure_hpa: float = Field(default=1000.0)
    landfall_state: str = ""
    fatalities: int = Field(default=0, ge=0)
    affected_population: int = Field(default=0, ge=0)
    storm_surge_m: float = Field(default=0.0, ge=0.0)
    notes: str = ""


class StormSurgeEstimate(BaseModel):
    """Storm surge height and coastal inundation estimate."""

    surge_height_m: float = Field(default=0.0, ge=0.0)
    inundation_depth_m: float = Field(default=0.0, ge=0.0)
    coastal_exposure_km: float = Field(default=0.0, ge=0.0)
    risk_level: CycloneRiskLevel = CycloneRiskLevel.MINIMAL


class WindHazardEstimate(BaseModel):
    """Wind hazard envelope."""

    max_sustained_wind_kt: float = Field(default=0.0, ge=0.0)
    gust_wind_kt: float = Field(default=0.0, ge=0.0)
    destructive_radius_km: float = Field(default=0.0, ge=0.0)
    category: CycloneCategory = CycloneCategory.DISTURBANCE


class RainfallImpactEstimate(BaseModel):
    """Rainfall impact from cyclone outer bands and landfall."""

    rainfall_24h_mm: float = Field(default=0.0, ge=0.0)
    rainfall_72h_mm: float = Field(default=0.0, ge=0.0)
    flash_flood_risk: bool = False
    landslide_risk: bool = False


class CycloneAnalysisSignals(BaseModel):
    """Intermediate signals computed during cyclone reasoning."""

    cyclone_detected: bool = False
    genesis_likely: bool = False
    rapid_intensification: RapidIntensificationStatus = RapidIntensificationStatus.NONE
    landfall_threat: bool = False
    high_storm_surge: bool = False
    heavy_rainfall: bool = False
    high_population_exposure: bool = False
    infrastructure_at_risk: bool = False
    historical_analog: bool = False
    warm_sst: bool = False
    low_pressure: bool = False
    favorable_genesis: bool = False
    sst_score: float = Field(default=0.0, ge=0.0, le=1.0)
    pressure_score: float = Field(default=0.0, ge=0.0, le=1.0)
    wind_score: float = Field(default=0.0, ge=0.0, le=1.0)
    track_score: float = Field(default=0.0, ge=0.0, le=1.0)
    surge_score: float = Field(default=0.0, ge=0.0, le=1.0)
    rainfall_score: float = Field(default=0.0, ge=0.0, le=1.0)
    vulnerability_score: float = Field(default=0.0, ge=0.0, le=1.0)
    composite_score: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: float = Field(default=0.5, ge=0.0, le=1.0)


class PopulationExposure(BaseModel):
    """Coastal population exposure estimate."""

    district_id: str
    name: str
    population: int = Field(default=0, ge=0)
    coastal_population: int = Field(default=0, ge=0)
    evacuation_zones: list[str] = Field(default_factory=list)
    risk_level: CycloneRiskLevel = CycloneRiskLevel.MINIMAL


class InfrastructureExposure(BaseModel):
    """Critical infrastructure cyclone exposure."""

    infrastructure_id: str
    name: str
    category: str
    risk_level: CycloneRiskLevel = CycloneRiskLevel.MINIMAL
    notes: str = ""


class KnowledgeGraphInsights(BaseModel):
    """Pre-queried CKG insights attached to cyclone context."""

    affected_regions: list[str] = Field(default_factory=list)
    affected_infrastructure: list[str] = Field(default_factory=list)
    dependent_agents: list[str] = Field(default_factory=list)
    historical_analogs: list[str] = Field(default_factory=list)
    cascade_chains: list[list[str]] = Field(default_factory=list)
    query_count: int = Field(default=0, ge=0)


class CycloneInputs(BaseModel):
    """Aggregated cyclone inputs extracted from request context."""

    location: GeoLocation | None = None
    region_id: str | None = None
    basin: CycloneBasin = CycloneBasin.UNKNOWN
    districts: list[str] = Field(default_factory=list)
    coastal_states: list[str] = Field(default_factory=list)
    ocean: OceanAtmosphereInput = Field(default_factory=OceanAtmosphereInput)
    forecast: ForecastInput = Field(default_factory=ForecastInput)
    historical_events: list[HistoricalCycloneEvent] = Field(default_factory=list)
    cyclone_name: str | None = None
    twin_id: str | None = None
    forecast_available: bool = False
    climate_state_available: bool = False
    digital_twin_available: bool = False
    insat_available: bool = False

    @classmethod
    def from_request_context(cls, context: dict[str, Any]) -> CycloneInputs:
        """Parse cyclone inputs from an agent request context dictionary."""
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

        basin_raw = context.get("basin", "unknown")
        try:
            basin = CycloneBasin(basin_raw)
        except ValueError:
            basin = CycloneBasin.UNKNOWN

        track_points: list[TrackPoint] = []
        for raw in context.get("track_points", []):
            if isinstance(raw, TrackPoint):
                track_points.append(raw)
            elif isinstance(raw, dict):
                track_points.append(TrackPoint.model_validate(raw))

        ocean = OceanAtmosphereInput(
            sst_c=context.get("sst_c") or context.get("sea_surface_temp_c"),
            sea_level_pressure_hpa=context.get("sea_level_pressure_hpa") or context.get("mslp_hpa"),
            wind_speed_kt=context.get("wind_speed_kt") or context.get("max_wind_kt"),
            wind_direction_deg=context.get("wind_direction_deg"),
            humidity_pct=context.get("humidity_pct") or context.get("relative_humidity_pct"),
            ocean_heat_content_kj_cm2=context.get("ocean_heat_content_kj_cm2") or context.get("ohc"),
            cloud_top_temp_c=context.get("cloud_top_temp_c"),
            vertical_wind_shear_kt=context.get("vertical_wind_shear_kt"),
        )
        forecast = ForecastInput(
            track_points=track_points,
            landfall_latitude=context.get("landfall_latitude"),
            landfall_longitude=context.get("landfall_longitude"),
            landfall_probability=context.get("landfall_probability"),
            landfall_hours=context.get("landfall_hours"),
            max_wind_kt_forecast=context.get("max_wind_kt_forecast") or context.get("forecast_max_wind_kt"),
            rainfall_mm_24h=context.get("rainfall_mm_24h") or context.get("forecast_rainfall_24h_mm"),
            rainfall_mm_72h=context.get("rainfall_mm_72h") or context.get("forecast_rainfall_72h_mm"),
        )

        historical: list[HistoricalCycloneEvent] = []
        for raw in context.get("historical_cyclones", []):
            if isinstance(raw, HistoricalCycloneEvent):
                historical.append(raw)
            elif isinstance(raw, dict):
                historical.append(HistoricalCycloneEvent.model_validate(raw))

        return cls(
            location=location,
            region_id=context.get("region_id") or (location.region_id if location else None),
            basin=basin,
            districts=list(context.get("districts", [])),
            coastal_states=list(context.get("coastal_states", [])),
            ocean=ocean,
            forecast=forecast,
            historical_events=historical,
            cyclone_name=context.get("cyclone_name"),
            twin_id=context.get("twin_id"),
            forecast_available=bool(context.get("forecast_available")),
            climate_state_available=bool(context.get("climate_state_available")),
            digital_twin_available=bool(context.get("digital_twin_available")),
            insat_available=bool(context.get("insat_available")),
        )
