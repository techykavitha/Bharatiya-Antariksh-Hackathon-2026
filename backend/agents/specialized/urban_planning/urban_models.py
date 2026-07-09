"""Urban planning domain type definitions and enumerations."""

from __future__ import annotations

from enum import StrEnum


class UrbanResilienceLevel(StrEnum):
    """Ordinal urban climate resilience classification."""

    CRITICAL = "critical"
    LOW = "low"
    MODERATE = "moderate"
    GOOD = "good"
    EXCELLENT = "excellent"


class LandUseCategory(StrEnum):
    """Primary land-use classification."""

    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    MIXED = "mixed"
    GREEN = "green"
    WATER = "water"
    TRANSPORT = "transport"
    UNKNOWN = "unknown"


class MitigationStrategyType(StrEnum):
    """Long-term climate adaptation strategy families."""

    HEAT_MITIGATION = "heat_mitigation"
    FLOOD_MITIGATION = "flood_mitigation"
    WATER_SECURITY = "water_security"
    GREEN_INFRASTRUCTURE = "green_infrastructure"
    DRAINAGE_UPGRADE = "drainage_upgrade"
    LAND_USE_REFORM = "land_use_reform"


class UrbanActionType(StrEnum):
    """Standardized urban adaptation actions for the decision framework."""

    PLANT_TREES = "plant_trees"
    GREEN_ROOFS = "green_roofs"
    COOL_ROOFS = "cool_roofs"
    RAIN_GARDENS = "rain_gardens"
    PERMEABLE_PAVEMENT = "permeable_pavement"
    STORMWATER_UPGRADES = "stormwater_upgrades"
    URBAN_FOREST_EXPANSION = "urban_forest_expansion"
    BUILDING_RETROFITS = "building_retrofits"
    LAND_USE_CHANGES = "land_use_changes"


# Peer agent identifiers
AGENT_HEATWAVE = "heatwave_agent"
AGENT_FLOOD = "flood_agent"
AGENT_WATER_RESOURCE = "water_resource_agent"
AGENT_AIR_QUALITY = "air_quality_agent"
AGENT_AGRICULTURE = "agriculture_agent"
AGENT_DISASTER = "disaster_response_agent"

URBAN_PLANNING_AGENT_ID = "urban_planning_agent"

ALL_PEER_AGENTS: list[str] = [
    AGENT_HEATWAVE,
    AGENT_FLOOD,
    AGENT_WATER_RESOURCE,
    AGENT_AIR_QUALITY,
    AGENT_AGRICULTURE,
]

ACTION_CATALOG: dict[UrbanActionType, tuple[str, float, float, str]] = {
    UrbanActionType.PLANT_TREES: (
        "Expand urban tree canopy along heat corridors", 35.0, 72.0, "low",
    ),
    UrbanActionType.GREEN_ROOFS: (
        "Install green roofs on public and commercial buildings", 55.0, 68.0, "low",
    ),
    UrbanActionType.COOL_ROOFS: (
        "Deploy cool-roof coatings on high-exposure buildings", 40.0, 65.0, "low",
    ),
    UrbanActionType.RAIN_GARDENS: (
        "Construct rain gardens in flood-prone micro-catchments", 30.0, 70.0, "low",
    ),
    UrbanActionType.PERMEABLE_PAVEMENT: (
        "Replace impervious surfaces with permeable pavement", 45.0, 68.0, "low",
    ),
    UrbanActionType.STORMWATER_UPGRADES: (
        "Upgrade stormwater detention and conveyance systems", 80.0, 78.0, "moderate",
    ),
    UrbanActionType.URBAN_FOREST_EXPANSION: (
        "Expand urban forest blocks and green belts", 60.0, 75.0, "low",
    ),
    UrbanActionType.BUILDING_RETROFITS: (
        "Retrofit buildings for thermal and flood resilience", 90.0, 80.0, "moderate",
    ),
    UrbanActionType.LAND_USE_CHANGES: (
        "Rezone and repurpose land for climate-resilient use", 70.0, 72.0, "moderate",
    ),
}
