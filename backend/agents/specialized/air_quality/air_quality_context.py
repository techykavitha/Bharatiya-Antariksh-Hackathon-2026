"""Air quality analysis domain models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.agents.specialized.air_quality.air_quality_models import (
    AQICategory,
    HealthRiskLevel,
    PollutantType,
    PollutionSourceType,
)
from backend.agents.state.climate_state import GeoLocation


class PeerAgentOutput(BaseModel):
    """Normalized output from a peer specialized agent."""

    agent_id: str
    domain: str = "unknown"
    severity: str = "unknown"
    risk_level: str = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    affected_regions: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    structured_output: dict[str, Any] = Field(default_factory=dict)
    consulted_live: bool = False


class PollutantReading(BaseModel):
    """Concentration reading for a single pollutant."""

    pollutant: PollutantType
    concentration_ug_m3: float = Field(default=0.0, ge=0.0)
    sub_index: int = Field(default=0, ge=0)
    dominant: bool = False


class MeteorologyProfile(BaseModel):
    """Atmospheric conditions affecting dispersion and chemistry."""

    temperature_c: float | None = None
    humidity_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    wind_speed_ms: float = Field(default=0.0, ge=0.0)
    wind_direction_deg: float = Field(default=0.0, ge=0.0, le=360.0)
    mixing_height_m: float = Field(default=1000.0, ge=0.0)
    inversion_present: bool = False
    forecast_temp_c: float | None = None
    forecast_wind_speed_ms: float | None = None


class EmissionInventory(BaseModel):
    """Regional emission source inventory."""

    traffic_share_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    industrial_share_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    biomass_burning_share_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    dust_share_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    construction_share_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    dominant_source: PollutionSourceType = PollutionSourceType.UNKNOWN


class SatelliteAerosolProfile(BaseModel):
    """Satellite-derived aerosol optical depth products."""

    aod_550: float = Field(default=0.0, ge=0.0, le=5.0)
    fire_hotspot_count: int = Field(default=0, ge=0)
    smoke_plume_detected: bool = False
    dust_plume_detected: bool = False
    biomass_burning_index: float = Field(default=0.0, ge=0.0, le=1.0)


class PopulationExposure(BaseModel):
    """Population-weighted exposure assessment."""

    total_population: int = Field(default=0, ge=0)
    sensitive_population: int = Field(default=0, ge=0)
    exposed_population: int = Field(default=0, ge=0)
    exposure_score: float = Field(default=0.0, ge=0.0, le=1.0)
    high_risk_zones: list[str] = Field(default_factory=list)


class HealthRiskAssessment(BaseModel):
    """Environmental health risk quantification."""

    risk_level: HealthRiskLevel = HealthRiskLevel.MODERATE
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    respiratory_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    cardiovascular_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    vulnerable_groups: list[str] = Field(default_factory=list)
    hospital_admission_risk_pct: float = Field(default=0.0, ge=0.0)


class MitigationStrategy(BaseModel):
    """Candidate air quality mitigation intervention."""

    action_type: str
    title: str
    description: str
    estimated_aqi_reduction: int = Field(default=0, ge=0)
    urgency: str = "normal"
    priority_rank: int = Field(default=1, ge=1)


class AQIAssessment(BaseModel):
    """Composite air quality index assessment."""

    aqi: int = Field(default=0, ge=0)
    category: AQICategory = AQICategory.GOOD
    dominant_pollutant: PollutantType = PollutantType.PM25
    pollutants: list[PollutantReading] = Field(default_factory=list)
    forecast_aqi_24h: int | None = None
    forecast_aqi_72h: int | None = None


class KnowledgeGraphInsights(BaseModel):
    """Pre-queried CKG insights for air quality analysis."""

    emission_sources: list[str] = Field(default_factory=list)
    historical_pollution: list[str] = Field(default_factory=list)
    population_nodes: list[str] = Field(default_factory=list)
    infrastructure_nodes: list[str] = Field(default_factory=list)
    compound_hazards: list[str] = Field(default_factory=list)
    query_count: int = Field(default=0, ge=0)


class AirQualityAnalysisSignals(BaseModel):
    """Intermediate signals from air quality reasoning."""

    aqi_score: float = Field(default=0.0, ge=0.0, le=1.0)
    pm25_score: float = Field(default=0.0, ge=0.0, le=1.0)
    pm10_score: float = Field(default=0.0, ge=0.0, le=1.0)
    transport_score: float = Field(default=0.0, ge=0.0, le=1.0)
    dispersion_score: float = Field(default=0.5, ge=0.0, le=1.0)
    health_risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    exposure_score: float = Field(default=0.0, ge=0.0, le=1.0)
    biomass_burning: bool = False
    dust_storm: bool = False
    wildfire_smoke: bool = False
    compound_hazard: bool = False
    severe_aqi: bool = False
    dominant_source: PollutionSourceType = PollutionSourceType.UNKNOWN
    uncertainty: float = Field(default=0.35, ge=0.0, le=1.0)


class AirQualityInputs(BaseModel):
    """Aggregated air quality inputs from request context."""

    location: GeoLocation | None = None
    region_id: str | None = None
    city_name: str | None = None
    state: str | None = None
    districts: list[str] = Field(default_factory=list)
    pollutants: dict[str, float] = Field(default_factory=dict)
    meteorology: MeteorologyProfile = Field(default_factory=MeteorologyProfile)
    emissions: EmissionInventory = Field(default_factory=EmissionInventory)
    satellite: SatelliteAerosolProfile = Field(default_factory=SatelliteAerosolProfile)
    population_total: int = Field(default=0, ge=0)
    population_density: float = Field(default=0.0, ge=0.0)
    sensitive_population_pct: float = Field(default=15.0, ge=0.0, le=100.0)
    historical_aqi: list[int] = Field(default_factory=list)
    peer_agent_outputs: dict[str, PeerAgentOutput] = Field(default_factory=dict)
    consult_agents: list[str] = Field(default_factory=list)
    twin_id: str | None = None
    forecast_available: bool = False
    climate_state_available: bool = False
    digital_twin_available: bool = False

    @classmethod
    def from_request_context(cls, context: dict[str, Any]) -> AirQualityInputs:
        location = None
        if "latitude" in context and "longitude" in context:
            location = GeoLocation(
                latitude=float(context["latitude"]),
                longitude=float(context["longitude"]),
                region_id=context.get("region_id"),
            )
        elif context.get("location") and isinstance(context["location"], dict):
            location = GeoLocation.model_validate(context["location"])

        pollutants: dict[str, float] = {}
        raw_pollutants = context.get("pollutants", {})
        if isinstance(raw_pollutants, dict):
            for key, val in raw_pollutants.items():
                pollutants[str(key)] = float(val)
        for key in ("pm2_5", "pm10", "no2", "so2", "o3", "co"):
            if key in context and key not in pollutants:
                pollutants[key] = float(context[key])

        met = MeteorologyProfile(
            temperature_c=context.get("temperature_c"),
            humidity_pct=context.get("humidity_pct"),
            wind_speed_ms=float(context.get("wind_speed_ms", 0.0)),
            wind_direction_deg=float(context.get("wind_direction_deg", 0.0)),
            mixing_height_m=float(context.get("mixing_height_m", 1000.0)),
            inversion_present=bool(context.get("inversion_present", False)),
            forecast_temp_c=context.get("forecast_temp_c"),
            forecast_wind_speed_ms=context.get("forecast_wind_speed_ms"),
        )

        emissions_raw = context.get("emission_inventory", context.get("emissions", {}))
        emissions = EmissionInventory()
        if isinstance(emissions_raw, dict):
            emissions = EmissionInventory.model_validate(emissions_raw)

        sat_raw = context.get("satellite_aerosol", context.get("satellite", {}))
        satellite = SatelliteAerosolProfile()
        if isinstance(sat_raw, dict):
            satellite = SatelliteAerosolProfile.model_validate(sat_raw)

        peer_outputs: dict[str, PeerAgentOutput] = {}
        for key in ("peer_agent_outputs", "hazard_agent_outputs"):
            raw = context.get(key, {})
            if isinstance(raw, dict):
                for agent_id, payload in raw.items():
                    if isinstance(payload, PeerAgentOutput):
                        peer_outputs[agent_id] = payload
                    elif isinstance(payload, dict):
                        peer_outputs[agent_id] = PeerAgentOutput.model_validate({
                            "agent_id": agent_id,
                            **payload,
                        })

        hist = context.get("historical_aqi", [])
        historical_aqi = [int(v) for v in hist] if isinstance(hist, list) else []

        return cls(
            location=location,
            region_id=context.get("region_id") or (location.region_id if location else None),
            city_name=context.get("city_name"),
            state=context.get("state"),
            districts=list(context.get("districts", [])),
            pollutants=pollutants,
            meteorology=met,
            emissions=emissions,
            satellite=satellite,
            population_total=int(context.get("population_total", 0)),
            population_density=float(context.get("population_density", 0.0)),
            sensitive_population_pct=float(context.get("sensitive_population_pct", 15.0)),
            historical_aqi=historical_aqi,
            peer_agent_outputs=peer_outputs,
            consult_agents=list(context.get("consult_agents", [])),
            twin_id=context.get("twin_id"),
            forecast_available=bool(context.get("forecast_available")),
            climate_state_available=bool(context.get("climate_state_available")),
            digital_twin_available=bool(context.get("digital_twin_available")),
        )
