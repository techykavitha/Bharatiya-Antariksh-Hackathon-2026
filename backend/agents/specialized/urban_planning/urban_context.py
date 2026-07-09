"""Urban planning analysis domain models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.agents.specialized.urban_planning.urban_models import (
    LandUseCategory,
    MitigationStrategyType,
    UrbanResilienceLevel,
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


class LandUseProfile(BaseModel):
    """Land-use composition for the urban study area."""

    residential_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    commercial_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    industrial_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    green_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    impervious_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    dominant_category: LandUseCategory = LandUseCategory.UNKNOWN


class UrbanEnvironmentProfile(BaseModel):
    """Built-environment and geospatial characteristics."""

    ndvi: float = Field(default=0.0, ge=-1.0, le=1.0)
    green_cover_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    building_density: float = Field(default=0.0, ge=0.0, le=1.0)
    impervious_surface_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    population_density: float = Field(default=0.0, ge=0.0)
    lst_c: float | None = None
    uhi_intensity_c: float = Field(default=0.0, ge=0.0)


class DrainageProfile(BaseModel):
    """Stormwater and drainage system profile."""

    capacity_score: float = Field(default=0.5, ge=0.0, le=1.0)
    detention_volume_m3: float = Field(default=0.0, ge=0.0)
    conveyance_adequacy: str = "unknown"
    flood_prone_zones: list[str] = Field(default_factory=list)
    upgrade_required: bool = False


class MitigationOption(BaseModel):
    """Candidate long-term adaptation intervention."""

    strategy_type: MitigationStrategyType
    title: str
    description: str
    estimated_cost_crores: float = Field(default=0.0, ge=0.0)
    long_term_benefit_score: float = Field(default=0.0, ge=0.0, le=1.0)
    payback_years: float = Field(default=10.0, ge=0.0)
    priority_rank: int = Field(default=1, ge=1)


class InvestmentPriority(BaseModel):
    """Ranked investment priority for adaptation portfolio."""

    rank: int = Field(default=1, ge=1)
    project: str
    domain: str
    estimated_cost_crores: float = Field(default=0.0, ge=0.0)
    benefit_score: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = ""


class GreenCoverAnalysis(BaseModel):
    """Green cover and cooling potential assessment."""

    current_cover_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    target_cover_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    canopy_gap_pct: float = Field(default=0.0, ge=0.0)
    cooling_potential_score: float = Field(default=0.0, ge=0.0, le=1.0)
    recommended_interventions: list[str] = Field(default_factory=list)


class KnowledgeGraphInsights(BaseModel):
    """Pre-queried CKG insights for urban planning."""

    urban_dependencies: list[str] = Field(default_factory=list)
    infrastructure_nodes: list[str] = Field(default_factory=list)
    population_nodes: list[str] = Field(default_factory=list)
    historical_mitigation_projects: list[str] = Field(default_factory=list)
    query_count: int = Field(default=0, ge=0)


class UrbanAnalysisSignals(BaseModel):
    """Intermediate signals from urban planning reasoning."""

    heat_risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    flood_risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    water_stress_score: float = Field(default=0.0, ge=0.0, le=1.0)
    green_cover_score: float = Field(default=0.0, ge=0.0, le=1.0)
    drainage_score: float = Field(default=0.0, ge=0.0, le=1.0)
    infrastructure_exposure_score: float = Field(default=0.0, ge=0.0, le=1.0)
    urban_heat_island: bool = False
    flood_vulnerability: bool = False
    water_scarcity: bool = False
    low_green_cover: bool = False
    drainage_deficit: bool = False
    resilience_score: float = Field(default=0.5, ge=0.0, le=1.0)
    resilience_level: UrbanResilienceLevel = UrbanResilienceLevel.MODERATE
    uncertainty: float = Field(default=0.4, ge=0.0, le=1.0)


class UrbanInputs(BaseModel):
    """Aggregated urban planning inputs from request context."""

    location: GeoLocation | None = None
    region_id: str | None = None
    city_name: str | None = None
    districts: list[str] = Field(default_factory=list)
    land_use: LandUseProfile = Field(default_factory=LandUseProfile)
    environment: UrbanEnvironmentProfile = Field(default_factory=UrbanEnvironmentProfile)
    drainage: DrainageProfile = Field(default_factory=DrainageProfile)
    peer_agent_outputs: dict[str, PeerAgentOutput] = Field(default_factory=dict)
    consult_agents: list[str] = Field(default_factory=list)
    planning_horizon_years: int = Field(default=10, ge=1)
    adaptation_budget_crores: float = Field(default=100.0, ge=0.0)
    twin_id: str | None = None
    forecast_available: bool = False
    climate_state_available: bool = False
    digital_twin_available: bool = False

    @classmethod
    def from_request_context(cls, context: dict[str, Any]) -> UrbanInputs:
        location = None
        if "latitude" in context and "longitude" in context:
            location = GeoLocation(
                latitude=float(context["latitude"]),
                longitude=float(context["longitude"]),
                region_id=context.get("region_id"),
            )
        elif context.get("location") and isinstance(context["location"], dict):
            location = GeoLocation.model_validate(context["location"])

        land_use_raw = context.get("land_use", {})
        land_use = LandUseProfile.model_validate(land_use_raw) if isinstance(land_use_raw, dict) else LandUseProfile()

        env_raw = context.get("urban_environment", context)
        environment = UrbanEnvironmentProfile(
            ndvi=float(env_raw.get("ndvi", context.get("ndvi", 0.0))),
            green_cover_pct=float(env_raw.get("green_cover_pct", context.get("green_cover_pct", 0.0))),
            building_density=float(env_raw.get("building_density", context.get("building_density", 0.0))),
            impervious_surface_pct=float(
                env_raw.get("impervious_surface_pct", context.get("impervious_surface_pct", 0.0)),
            ),
            population_density=float(
                env_raw.get("population_density", context.get("population_density", 0.0)),
            ),
            lst_c=env_raw.get("lst_c", context.get("lst_c")),
            uhi_intensity_c=float(env_raw.get("uhi_intensity_c", context.get("uhi_intensity_c", 0.0))),
        )

        drainage_raw = context.get("drainage", {})
        drainage = DrainageProfile.model_validate(drainage_raw) if isinstance(drainage_raw, dict) else DrainageProfile(
            capacity_score=float(context.get("drainage_capacity_score", 0.5)),
            detention_volume_m3=float(context.get("detention_volume_m3", 0.0)),
            conveyance_adequacy=str(context.get("conveyance_adequacy", "unknown")),
            flood_prone_zones=list(context.get("flood_prone_zones", [])),
        )

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

        if land_use.impervious_pct <= 0 and environment.impervious_surface_pct > 0:
            land_use.impervious_pct = environment.impervious_surface_pct

        return cls(
            location=location,
            region_id=context.get("region_id") or (location.region_id if location else None),
            city_name=context.get("city_name"),
            districts=list(context.get("districts", [])),
            land_use=land_use,
            environment=environment,
            drainage=drainage,
            peer_agent_outputs=peer_outputs,
            consult_agents=list(context.get("consult_agents", [])),
            planning_horizon_years=int(context.get("planning_horizon_years", 10)),
            adaptation_budget_crores=float(context.get("adaptation_budget_crores", 100.0)),
            twin_id=context.get("twin_id"),
            forecast_available=bool(context.get("forecast_available")),
            climate_state_available=bool(context.get("climate_state_available")),
            digital_twin_available=bool(context.get("digital_twin_available")),
        )
