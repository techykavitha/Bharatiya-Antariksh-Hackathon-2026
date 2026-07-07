"""Water resource domain type definitions and enumerations."""

from __future__ import annotations

from enum import StrEnum


class WaterStressLevel(StrEnum):
    """Ordinal water stress classification."""

    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"
    CRITICAL = "critical"


class ReservoirStatus(StrEnum):
    """Reservoir operational status."""

    NORMAL = "normal"
    ELEVATED = "elevated"
    STRESSED = "stressed"
    OVERFLOW_RISK = "overflow_risk"
    CRITICAL_LOW = "critical_low"
    UNKNOWN = "unknown"


class WaterAvailabilityBand(StrEnum):
    """Qualitative water availability band."""

    ABUNDANT = "abundant"
    ADEQUATE = "adequate"
    MARGINAL = "marginal"
    DEFICIT = "deficit"
    SEVERE_DEFICIT = "severe_deficit"


class ReleaseStrategy(StrEnum):
    """Recommended reservoir release strategy."""

    HOLD = "hold"
    GRADUAL_RELEASE = "gradual_release"
    CONTROLLED_RELEASE = "controlled_release"
    EMERGENCY_SPILL = "emergency_spill"
    CONSERVATION = "conservation"
    SUPPLEMENTAL_RELEASE = "supplemental_release"


class GroundwaterTrend(StrEnum):
    """Groundwater level trend."""

    RISING = "rising"
    STABLE = "stable"
    DECLINING = "declining"
    CRITICAL_DECLINE = "critical_decline"
    UNKNOWN = "unknown"


# Agent identifiers for inter-agent delegation
AGENT_FLOOD = "flood_agent"
AGENT_AGRICULTURE = "agriculture_agent"
AGENT_URBAN_PLANNING = "urban_planning_agent"
AGENT_DISASTER = "disaster_response_agent"

WATER_RESOURCE_AGENT_ID = "water_resource_agent"
