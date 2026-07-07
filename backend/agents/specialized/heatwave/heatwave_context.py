"""Heatwave analysis domain models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.agents.specialized.heatwave.heatwave_models import (
    HeatProbabilityBand,
    HeatRiskLevel,
    HeatwaveClassification,
    HeatwaveSeverity,
)
from backend.agents.state.climate_state import GeoLocation


class TemperatureInput(BaseModel):
    """Air and surface temperature inputs."""

    air_temp_c: float | None = Field(default=None)
    surface_temp_c: float | None = Field(default=None)
    max_temp_c: float | None = Field(default=None)
    min_temp_c: float | None = Field(default=None)
    forecast_max_24h_c: float | None = Field(default=None)
    forecast_max_72h_c: float | None = Field(default=None)
    trend_c_per_day: float | None = Field(default=None)


class HumidityInput(BaseModel):
    """Humidity and moisture inputs."""

    relative_humidity_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    dew_point_c: float | None = Field(default=None)
    wet_bulb_c: float | None = Field(default=None)


class WindSolarInput(BaseModel):
    """Wind and solar radiation inputs."""

    wind_speed_ms: float | None = Field(default=None, ge=0.0)
    solar_radiation_wm2: float | None = Field(default=None, ge=0.0)


class UrbanThermalInput(BaseModel):
    """Urban heat island and built environment inputs."""

    lst_c: float | None = Field(default=None)
    ndvi: float | None = Field(default=None, ge=-1.0, le=1.0)
    land_cover: str | None = None
    urban_density: float | None = Field(default=None, ge=0.0, le=1.0)
    population_density: float | None = Field(default=None, ge=0.0)
    building_density: float | None = Field(default=None, ge=0.0, le=1.0)
    impervious_fraction: float | None = Field(default=None, ge=0.0, le=1.0)


class HistoricalHeatwaveEvent(BaseModel):
    """Record of a historical heatwave for comparison."""

    event_id: str
    year: int
    peak_temp_c: float = Field(ge=0.0)
    duration_days: int = Field(default=1, ge=1)
    affected_population: int = Field(default=0, ge=0)
    districts: list[str] = Field(default_factory=list)
    fatalities: int = Field(default=0, ge=0)
    notes: str = ""


class HeatAnalysisSignals(BaseModel):
    """Intermediate signals computed during heatwave reasoning."""

    elevated_temperature: bool = False
    rising_trend: bool = False
    high_humidity_stress: bool = False
    urban_heat_island: bool = False
    high_population_exposure: bool = False
    historical_analog: bool = False
    compound_aqi_risk: bool = False
    low_vegetation: bool = False
    infrastructure_at_risk: bool = False
    temperature_score: float = Field(default=0.0, ge=0.0, le=1.0)
    humidity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    heat_index_score: float = Field(default=0.0, ge=0.0, le=1.0)
    uhi_score: float = Field(default=0.0, ge=0.0, le=1.0)
    vulnerability_score: float = Field(default=0.0, ge=0.0, le=1.0)
    historical_score: float = Field(default=0.0, ge=0.0, le=1.0)
    composite_score: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: float = Field(default=0.5, ge=0.0, le=1.0)


class HeatIndexEstimate(BaseModel):
    """Computed heat index and thermal comfort metrics."""

    heat_index_c: float = Field(default=0.0, ge=0.0)
    wet_bulb_c: float = Field(default=0.0, ge=0.0)
    discomfort_level: str = "comfortable"
    dangerous: bool = False


class HeatProbabilityEstimate(BaseModel):
    """Quantified heatwave probability output."""

    band: HeatProbabilityBand = HeatProbabilityBand.LOW
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    horizon_hours: int = Field(default=72, ge=1)
    drivers: list[str] = Field(default_factory=list)


class PopulationAtRisk(BaseModel):
    """Population exposure estimate."""

    district_id: str
    name: str
    population: int = Field(default=0, ge=0)
    vulnerable_population: int = Field(default=0, ge=0)
    risk_level: HeatRiskLevel = HeatRiskLevel.MINIMAL


class InfrastructureRisk(BaseModel):
    """Critical infrastructure heat risk."""

    infrastructure_id: str
    name: str
    category: str
    risk_level: HeatRiskLevel = HeatRiskLevel.MINIMAL
    notes: str = ""


class HeatwaveInputs(BaseModel):
    """Aggregated heatwave inputs extracted from request context."""

    location: GeoLocation | None = None
    region_id: str | None = None
    districts: list[str] = Field(default_factory=list)
    temperature: TemperatureInput = Field(default_factory=TemperatureInput)
    humidity: HumidityInput = Field(default_factory=HumidityInput)
    wind_solar: WindSolarInput = Field(default_factory=WindSolarInput)
    urban: UrbanThermalInput = Field(default_factory=UrbanThermalInput)
    historical_events: list[HistoricalHeatwaveEvent] = Field(default_factory=list)
    aqi: float | None = Field(default=None, ge=0.0)
    twin_id: str | None = None
    forecast_available: bool = False
    climate_state_available: bool = False
    digital_twin_available: bool = False

    @classmethod
    def from_request_context(cls, context: dict[str, Any]) -> HeatwaveInputs:
        """Parse heatwave inputs from an agent request context dictionary."""
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

        temperature = TemperatureInput(
            air_temp_c=context.get("air_temp_c") or context.get("temperature_c"),
            surface_temp_c=context.get("surface_temp_c"),
            max_temp_c=context.get("max_temp_c"),
            min_temp_c=context.get("min_temp_c"),
            forecast_max_24h_c=context.get("forecast_max_24h_c"),
            forecast_max_72h_c=context.get("forecast_max_72h_c"),
            trend_c_per_day=context.get("temp_trend_c_per_day"),
        )
        humidity = HumidityInput(
            relative_humidity_pct=context.get("humidity_pct") or context.get("relative_humidity_pct"),
            dew_point_c=context.get("dew_point_c"),
            wet_bulb_c=context.get("wet_bulb_c"),
        )
        wind_solar = WindSolarInput(
            wind_speed_ms=context.get("wind_speed_ms"),
            solar_radiation_wm2=context.get("solar_radiation_wm2"),
        )
        urban = UrbanThermalInput(
            lst_c=context.get("lst_c") or context.get("land_surface_temp_c"),
            ndvi=context.get("ndvi"),
            land_cover=context.get("land_cover"),
            urban_density=context.get("urban_density"),
            population_density=context.get("population_density"),
            building_density=context.get("building_density"),
            impervious_fraction=context.get("impervious_fraction"),
        )

        historical: list[HistoricalHeatwaveEvent] = []
        for raw in context.get("historical_heatwaves", []):
            if isinstance(raw, HistoricalHeatwaveEvent):
                historical.append(raw)
            elif isinstance(raw, dict):
                historical.append(HistoricalHeatwaveEvent.model_validate(raw))

        return cls(
            location=location,
            region_id=context.get("region_id") or (location.region_id if location else None),
            districts=list(context.get("districts", [])),
            temperature=temperature,
            humidity=humidity,
            wind_solar=wind_solar,
            urban=urban,
            historical_events=historical,
            aqi=context.get("aqi"),
            twin_id=context.get("twin_id"),
            forecast_available=bool(context.get("forecast_available")),
            climate_state_available=bool(context.get("climate_state_available")),
            digital_twin_available=bool(context.get("digital_twin_available")),
        )
