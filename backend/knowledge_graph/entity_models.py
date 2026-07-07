"""Climate Knowledge Graph entity type definitions and models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EntityType(StrEnum):
    """Canonical CKG entity types."""

    WEATHER_EVENT = "weather_event"
    FLOOD = "flood"
    CYCLONE = "cyclone"
    HEATWAVE = "heatwave"
    DROUGHT = "drought"
    RAINFALL = "rainfall"
    RESERVOIR = "reservoir"
    RIVER = "river"
    DISTRICT = "district"
    STATE = "state"
    POPULATION = "population"
    HOSPITAL = "hospital"
    ROAD = "road"
    POWER_GRID = "power_grid"
    AGRICULTURE = "agriculture"
    FOREST = "forest"
    URBAN_AREA = "urban_area"
    POLICY = "policy"
    FORECAST = "forecast"
    SIMULATION = "simulation"
    DIGITAL_TWIN = "digital_twin"
    SPECIALIZED_AGENT = "specialized_agent"


class ClimateEntity(BaseModel):
    """Base entity stored in the Climate Knowledge Graph."""

    entity_id: str = Field(default_factory=lambda: str(uuid4()))
    entity_type: EntityType
    name: str
    description: str = ""
    region_id: str | None = None
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    attributes: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)


class WeatherEventEntity(ClimateEntity):
    """Generic weather event node."""

    entity_type: EntityType = EntityType.WEATHER_EVENT
    severity: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class FloodEntity(ClimateEntity):
    entity_type: EntityType = EntityType.FLOOD
    peak_depth_m: float | None = Field(default=None, ge=0.0)
    affected_population: int | None = Field(default=None, ge=0)
    year: int | None = None


class CycloneEntity(ClimateEntity):
    entity_type: EntityType = EntityType.CYCLONE
    max_wind_speed_kmh: float | None = Field(default=None, ge=0.0)
    category: str | None = None
    landfall_district: str | None = None


class HeatwaveEntity(ClimateEntity):
    entity_type: EntityType = EntityType.HEATWAVE
    peak_temp_c: float | None = Field(default=None)
    duration_days: int | None = Field(default=None, ge=1)
    heat_index_c: float | None = None


class DroughtEntity(ClimateEntity):
    entity_type: EntityType = EntityType.DROUGHT
    severity: str | None = None
    rainfall_deficit_pct: float | None = Field(default=None, ge=0.0, le=100.0)


class RainfallEntity(ClimateEntity):
    entity_type: EntityType = EntityType.RAINFALL
    amount_mm: float | None = Field(default=None, ge=0.0)
    duration_hours: float | None = Field(default=None, ge=0.0)
    intensity_mm_per_hr: float | None = Field(default=None, ge=0.0)


class ReservoirEntity(ClimateEntity):
    entity_type: EntityType = EntityType.RESERVOIR
    capacity_mcm: float | None = Field(default=None, ge=0.0)
    current_level_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    spillway_active: bool = False


class RiverEntity(ClimateEntity):
    entity_type: EntityType = EntityType.RIVER
    length_km: float | None = Field(default=None, ge=0.0)
    discharge_m3s: float | None = Field(default=None, ge=0.0)
    bank_level_m: float | None = None


class DistrictEntity(ClimateEntity):
    entity_type: EntityType = EntityType.DISTRICT
    state_code: str | None = None
    population: int | None = Field(default=None, ge=0)


class StateEntity(ClimateEntity):
    entity_type: EntityType = EntityType.STATE
    country_code: str = "IN"
    population: int | None = Field(default=None, ge=0)


class PopulationEntity(ClimateEntity):
    entity_type: EntityType = EntityType.POPULATION
    total: int = Field(default=0, ge=0)
    vulnerable_fraction: float = Field(default=0.0, ge=0.0, le=1.0)


class HospitalEntity(ClimateEntity):
    entity_type: EntityType = EntityType.HOSPITAL
    bed_capacity: int | None = Field(default=None, ge=0)
    critical_care_beds: int | None = Field(default=None, ge=0)


class RoadEntity(ClimateEntity):
    entity_type: EntityType = EntityType.ROAD
    road_class: str | None = None
    length_km: float | None = Field(default=None, ge=0.0)


class PowerGridEntity(ClimateEntity):
    entity_type: EntityType = EntityType.POWER_GRID
    capacity_mw: float | None = Field(default=None, ge=0.0)
    load_pct: float | None = Field(default=None, ge=0.0, le=100.0)


class AgricultureEntity(ClimateEntity):
    entity_type: EntityType = EntityType.AGRICULTURE
    crop_area_ha: float | None = Field(default=None, ge=0.0)
    primary_crop: str | None = None
    irrigation_source: str | None = None


class ForestEntity(ClimateEntity):
    entity_type: EntityType = EntityType.FOREST
    area_sq_km: float | None = Field(default=None, ge=0.0)
    canopy_cover_pct: float | None = Field(default=None, ge=0.0, le=100.0)


class UrbanAreaEntity(ClimateEntity):
    entity_type: EntityType = EntityType.URBAN_AREA
    urban_density: float | None = Field(default=None, ge=0.0, le=1.0)
    impervious_fraction: float | None = Field(default=None, ge=0.0, le=1.0)


class PolicyEntity(ClimateEntity):
    entity_type: EntityType = EntityType.POLICY
    policy_type: str | None = None
    authority: str | None = None
    effective_date: str | None = None


class ForecastEntity(ClimateEntity):
    entity_type: EntityType = EntityType.FORECAST
    model_name: str | None = None
    horizon_hours: int | None = Field(default=None, ge=1)
    generated_at: str | None = None


class SimulationEntity(ClimateEntity):
    entity_type: EntityType = EntityType.SIMULATION
    scenario_name: str | None = None
    status: str | None = None
    horizon_hours: int | None = Field(default=None, ge=1)


class DigitalTwinEntity(ClimateEntity):
    entity_type: EntityType = EntityType.DIGITAL_TWIN
    twin_id: str | None = None
    version: str | None = None
    layers: list[str] = Field(default_factory=list)


class SpecializedAgentEntity(ClimateEntity):
    entity_type: EntityType = EntityType.SPECIALIZED_AGENT
    agent_id: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    domain: str | None = None


ENTITY_MODEL_REGISTRY: dict[EntityType, type[ClimateEntity]] = {
    EntityType.WEATHER_EVENT: WeatherEventEntity,
    EntityType.FLOOD: FloodEntity,
    EntityType.CYCLONE: CycloneEntity,
    EntityType.HEATWAVE: HeatwaveEntity,
    EntityType.DROUGHT: DroughtEntity,
    EntityType.RAINFALL: RainfallEntity,
    EntityType.RESERVOIR: ReservoirEntity,
    EntityType.RIVER: RiverEntity,
    EntityType.DISTRICT: DistrictEntity,
    EntityType.STATE: StateEntity,
    EntityType.POPULATION: PopulationEntity,
    EntityType.HOSPITAL: HospitalEntity,
    EntityType.ROAD: RoadEntity,
    EntityType.POWER_GRID: PowerGridEntity,
    EntityType.AGRICULTURE: AgricultureEntity,
    EntityType.FOREST: ForestEntity,
    EntityType.URBAN_AREA: UrbanAreaEntity,
    EntityType.POLICY: PolicyEntity,
    EntityType.FORECAST: ForecastEntity,
    EntityType.SIMULATION: SimulationEntity,
    EntityType.DIGITAL_TWIN: DigitalTwinEntity,
    EntityType.SPECIALIZED_AGENT: SpecializedAgentEntity,
}


def create_entity(entity_type: EntityType, **kwargs: Any) -> ClimateEntity:
    """Factory for typed entity creation."""
    model_cls = ENTITY_MODEL_REGISTRY.get(entity_type, ClimateEntity)
    return model_cls(entity_type=entity_type, **kwargs)
