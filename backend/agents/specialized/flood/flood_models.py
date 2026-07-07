"""Flood domain type definitions and enumerations."""

from __future__ import annotations

from enum import StrEnum


class FloodType(StrEnum):
    """Classification of flood event type."""

    FLASH = "flash"
    RIVER = "river"
    URBAN = "urban"
    COASTAL = "coastal"
    RESERVOIR_OVERFLOW = "reservoir_overflow"
    UNKNOWN = "unknown"


class FloodRiskLevel(StrEnum):
    """Ordinal flood risk classification."""

    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"
    EXTREME = "extreme"


class FloodSeverity(StrEnum):
    """Flood severity based on impact potential."""

    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CATASTROPHIC = "catastrophic"


class FloodProbabilityBand(StrEnum):
    """Qualitative probability band."""

    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


# Agent identifiers for inter-agent delegation
AGENT_WATER_RESOURCE = "water_resource_agent"
AGENT_CYCLONE = "cyclone_agent"
AGENT_DISASTER = "disaster_response_agent"
AGENT_AIR_QUALITY = "air_quality_agent"
AGENT_URBAN_PLANNING = "urban_planning_agent"

FLOOD_AGENT_ID = "flood_agent"
