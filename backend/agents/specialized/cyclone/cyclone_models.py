"""Cyclone domain type definitions and enumerations."""

from __future__ import annotations

from enum import StrEnum


class CycloneBasin(StrEnum):
    """Tropical cyclone ocean basin."""

    BAY_OF_BENGAL = "bay_of_bengal"
    ARABIAN_SEA = "arabian_sea"
    UNKNOWN = "unknown"


class CycloneCategory(StrEnum):
    """IMD-aligned tropical cyclone intensity classification."""

    DISTURBANCE = "disturbance"
    DEPRESSION = "depression"
    DEEP_DEPRESSION = "deep_depression"
    CYCLONIC_STORM = "cyclonic_storm"
    SEVERE_CYCLONIC_STORM = "severe_cyclonic_storm"
    VERY_SEVERE_CYCLONIC_STORM = "very_severe_cyclonic_storm"
    EXTREMELY_SEVERE_CYCLONIC_STORM = "extremely_severe_cyclonic_storm"
    SUPER_CYCLONIC_STORM = "super_cyclonic_storm"


class CycloneSeverity(StrEnum):
    """Operational cyclone hazard severity."""

    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"
    EXTREME = "extreme"


class CycloneRiskLevel(StrEnum):
    """Ordinal cyclone risk classification."""

    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"
    CRITICAL = "critical"


class RapidIntensificationStatus(StrEnum):
    """Rapid intensification detection status."""

    NONE = "none"
    POSSIBLE = "possible"
    LIKELY = "likely"
    CONFIRMED = "confirmed"


class CycloneActionType(StrEnum):
    """Standardized cyclone response actions for the decision framework."""

    EVACUATION = "evacuation"
    RESERVOIR_PREPARATION = "reservoir_preparation"
    DISASTER_READINESS = "disaster_readiness"
    SCHOOL_CLOSURE = "school_closure"
    TRANSPORT_SUSPENSION = "transport_suspension"
    POWER_GRID_PROTECTION = "power_grid_protection"
    EMERGENCY_RESOURCE_ALLOCATION = "emergency_resource_allocation"
    COASTAL_WARNING = "coastal_warning"


# Inter-agent delegation identifiers
AGENT_FLOOD = "flood_agent"
AGENT_WATER_RESOURCE = "water_resource_agent"
AGENT_DISASTER = "disaster_response_agent"
AGENT_URBAN_PLANNING = "urban_planning_agent"
AGENT_AIR_QUALITY = "air_quality_agent"

CYCLONE_AGENT_ID = "cyclone_agent"

# Sustained wind thresholds (kt) for IMD categories — approximate
CATEGORY_WIND_KT: dict[CycloneCategory, tuple[float, float]] = {
    CycloneCategory.DISTURBANCE: (0, 22),
    CycloneCategory.DEPRESSION: (22, 27),
    CycloneCategory.DEEP_DEPRESSION: (27, 31),
    CycloneCategory.CYCLONIC_STORM: (31, 48),
    CycloneCategory.SEVERE_CYCLONIC_STORM: (48, 63),
    CycloneCategory.VERY_SEVERE_CYCLONIC_STORM: (63, 90),
    CycloneCategory.EXTREMELY_SEVERE_CYCLONIC_STORM: (90, 120),
    CycloneCategory.SUPER_CYCLONIC_STORM: (120, 250),
}
