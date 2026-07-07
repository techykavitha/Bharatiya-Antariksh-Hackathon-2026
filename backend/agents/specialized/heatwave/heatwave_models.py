"""Heatwave domain type definitions and enumerations."""

from __future__ import annotations

from enum import StrEnum


class HeatwaveClassification(StrEnum):
    """Classification of heatwave event type."""

    NONE = "none"
    MODERATE = "moderate"
    SEVERE = "severe"
    EXTREME = "extreme"
    PROLONGED = "prolonged"
    COMPOUND = "compound"


class HeatwaveSeverity(StrEnum):
    """Heatwave severity based on thermal stress impact."""

    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"
    EXTREME = "extreme"


class HeatRiskLevel(StrEnum):
    """Ordinal heat risk classification."""

    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"
    CRITICAL = "critical"


class HeatProbabilityBand(StrEnum):
    """Qualitative heatwave probability band."""

    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class HeatActionType(StrEnum):
    """Standardized heatwave mitigation actions for the decision framework."""

    URBAN_COOLING = "urban_cooling"
    COOLING_CENTERS = "cooling_centers"
    WATER_DISTRIBUTION = "water_distribution"
    TREE_PLANTATION = "tree_plantation"
    SCHOOL_CLOSURE = "school_closure"
    WORK_HOUR_MODIFICATION = "work_hour_modification"
    PUBLIC_ALERTS = "public_alerts"
    EMERGENCY_RESPONSE = "emergency_response"


# Agent identifiers for inter-agent delegation
AGENT_URBAN_PLANNING = "urban_planning_agent"
AGENT_WATER_RESOURCE = "water_resource_agent"
AGENT_AIR_QUALITY = "air_quality_agent"
AGENT_DISASTER = "disaster_response_agent"
AGENT_FLOOD = "flood_agent"

HEATWAVE_AGENT_ID = "heatwave_agent"
