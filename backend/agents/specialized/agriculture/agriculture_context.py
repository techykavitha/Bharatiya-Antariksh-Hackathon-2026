"""Agriculture analysis domain models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.agents.specialized.agriculture.agriculture_models import (
    CropHealthStatus,
    CropStressType,
    IrrigationRecommendationType,
    YieldRiskLevel,
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


class CropCalendarEntry(BaseModel):
    """Crop phenology calendar entry."""

    stage: str
    start_day: int = Field(default=1, ge=1)
    end_day: int = Field(default=30, ge=1)
    critical: bool = False
    irrigation_mm: float = Field(default=0.0, ge=0.0)


class RemoteSensingInput(BaseModel):
    """Satellite vegetation indices."""

    ndvi: float = Field(default=0.0, ge=-1.0, le=1.0)
    evi: float = Field(default=0.0, ge=-1.0, le=1.0)
    ndvi_trend: float = Field(default=0.0)
    evi_trend: float = Field(default=0.0)


class SoilMoistureInput(BaseModel):
    """Soil moisture and groundwater inputs."""

    soil_moisture_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    soil_moisture_depth_cm: float = Field(default=30.0, ge=0.0)
    groundwater_level_m: float | None = None
    field_capacity_pct: float = Field(default=50.0, ge=0.0, le=100.0)


class WeatherInput(BaseModel):
    """Agricultural weather inputs."""

    temperature_c: float | None = None
    max_temp_c: float | None = None
    rainfall_mm_7d: float = Field(default=0.0, ge=0.0)
    rainfall_mm_30d: float = Field(default=0.0, ge=0.0)
    humidity_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    forecast_rainfall_7d_mm: float = Field(default=0.0, ge=0.0)


class CropCondition(BaseModel):
    """Assessed crop health and phenology status."""

    crop_type: str = "unknown"
    health_status: CropHealthStatus = CropHealthStatus.MODERATE
    phenology_stage: str = "unknown"
    ndvi: float = Field(default=0.0, ge=-1.0, le=1.0)
    evi: float = Field(default=0.0, ge=-1.0, le=1.0)
    stress_type: CropStressType = CropStressType.NONE
    area_hectares: float = Field(default=0.0, ge=0.0)


class SoilMoistureAssessment(BaseModel):
    """Soil moisture condition assessment."""

    soil_moisture_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    deficit_pct: float = Field(default=0.0, ge=0.0)
    status: str = "adequate"
    irrigation_needed: bool = False


class IrrigationRecommendation(BaseModel):
    """Irrigation strategy recommendation."""

    recommendation_type: IrrigationRecommendationType = IrrigationRecommendationType.MAINTAIN
    volume_mm: float = Field(default=0.0, ge=0.0)
    frequency_days: int = Field(default=7, ge=1)
    method: str = "canal"
    rationale: str = ""
    urgency: str = "normal"


class YieldRiskAssessment(BaseModel):
    """Yield risk quantification."""

    risk_level: YieldRiskLevel = YieldRiskLevel.MODERATE
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    estimated_yield_pct: float = Field(default=100.0, ge=0.0, le=150.0)
    drivers: list[str] = Field(default_factory=list)


class GovernmentAdvisory(BaseModel):
    """Government agricultural advisory snippet."""

    source: str = "ICAR"
    title: str = ""
    content: str = ""
    issued_date: str = ""
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)


class RagDocument(BaseModel):
    """Retrieved knowledge document from RAG."""

    document_id: str
    category: str
    title: str
    content: str
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagRetrievalResult(BaseModel):
    """Aggregated RAG retrieval output."""

    query: str = ""
    documents: list[RagDocument] = Field(default_factory=list)
    advisories: list[GovernmentAdvisory] = Field(default_factory=list)
    retrieval_count: int = Field(default=0, ge=0)


class KnowledgeGraphInsights(BaseModel):
    """Pre-queried CKG insights for agriculture."""

    crop_dependencies: list[str] = Field(default_factory=list)
    water_dependencies: list[str] = Field(default_factory=list)
    historical_impacts: list[str] = Field(default_factory=list)
    regional_suitability: list[str] = Field(default_factory=list)
    query_count: int = Field(default=0, ge=0)


class AgricultureAnalysisSignals(BaseModel):
    """Intermediate signals from agriculture reasoning."""

    crop_health_score: float = Field(default=0.5, ge=0.0, le=1.0)
    soil_moisture_score: float = Field(default=0.5, ge=0.0, le=1.0)
    heat_stress_score: float = Field(default=0.0, ge=0.0, le=1.0)
    flood_risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    yield_risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    pest_favorability_score: float = Field(default=0.0, ge=0.0, le=1.0)
    drought_risk: bool = False
    heat_stress: bool = False
    flood_impact: bool = False
    water_stress: bool = False
    resilience_score: float = Field(default=0.5, ge=0.0, le=1.0)
    uncertainty: float = Field(default=0.4, ge=0.0, le=1.0)


class AgricultureInputs(BaseModel):
    """Aggregated agriculture inputs from request context."""

    location: GeoLocation | None = None
    region_id: str | None = None
    state: str | None = None
    districts: list[str] = Field(default_factory=list)
    crop_type: str = "unknown"
    season: str = "kharif"
    remote_sensing: RemoteSensingInput = Field(default_factory=RemoteSensingInput)
    soil: SoilMoistureInput = Field(default_factory=SoilMoistureInput)
    weather: WeatherInput = Field(default_factory=WeatherInput)
    crop_calendar: list[CropCalendarEntry] = Field(default_factory=list)
    land_use: str = "agricultural"
    area_hectares: float = Field(default=0.0, ge=0.0)
    peer_agent_outputs: dict[str, PeerAgentOutput] = Field(default_factory=dict)
    consult_agents: list[str] = Field(default_factory=list)
    twin_id: str | None = None
    forecast_available: bool = False
    climate_state_available: bool = False
    digital_twin_available: bool = False

    @classmethod
    def from_request_context(cls, context: dict[str, Any]) -> AgricultureInputs:
        location = None
        if "latitude" in context and "longitude" in context:
            location = GeoLocation(
                latitude=float(context["latitude"]),
                longitude=float(context["longitude"]),
                region_id=context.get("region_id"),
            )
        elif context.get("location") and isinstance(context["location"], dict):
            location = GeoLocation.model_validate(context["location"])

        rs = RemoteSensingInput(
            ndvi=float(context.get("ndvi", 0.0)),
            evi=float(context.get("evi", 0.0)),
            ndvi_trend=float(context.get("ndvi_trend", 0.0)),
            evi_trend=float(context.get("evi_trend", 0.0)),
        )
        soil = SoilMoistureInput(
            soil_moisture_pct=context.get("soil_moisture_pct"),
            soil_moisture_depth_cm=float(context.get("soil_moisture_depth_cm", 30.0)),
            groundwater_level_m=context.get("groundwater_level_m"),
            field_capacity_pct=float(context.get("field_capacity_pct", 50.0)),
        )
        weather = WeatherInput(
            temperature_c=context.get("temperature_c"),
            max_temp_c=context.get("max_temp_c"),
            rainfall_mm_7d=float(context.get("rainfall_mm_7d", 0.0)),
            rainfall_mm_30d=float(context.get("rainfall_mm_30d", 0.0)),
            humidity_pct=context.get("humidity_pct"),
            forecast_rainfall_7d_mm=float(context.get("forecast_rainfall_7d_mm", 0.0)),
        )

        calendar: list[CropCalendarEntry] = []
        for raw in context.get("crop_calendar", []):
            if isinstance(raw, dict):
                calendar.append(CropCalendarEntry.model_validate(raw))

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

        return cls(
            location=location,
            region_id=context.get("region_id") or (location.region_id if location else None),
            state=context.get("state"),
            districts=list(context.get("districts", [])),
            crop_type=str(context.get("crop_type", "unknown")),
            season=str(context.get("season", "kharif")),
            remote_sensing=rs,
            soil=soil,
            weather=weather,
            crop_calendar=calendar,
            land_use=str(context.get("land_use", "agricultural")),
            area_hectares=float(context.get("area_hectares", 0.0)),
            peer_agent_outputs=peer_outputs,
            consult_agents=list(context.get("consult_agents", [])),
            twin_id=context.get("twin_id"),
            forecast_available=bool(context.get("forecast_available")),
            climate_state_available=bool(context.get("climate_state_available")),
            digital_twin_available=bool(context.get("digital_twin_available")),
        )
