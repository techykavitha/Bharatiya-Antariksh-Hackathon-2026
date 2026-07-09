"""Air quality domain type definitions and enumerations."""

from __future__ import annotations

from enum import StrEnum


class AQICategory(StrEnum):
    """Indian CPCB AQI category bands."""

    GOOD = "good"
    SATISFACTORY = "satisfactory"
    MODERATE = "moderate"
    POOR = "poor"
    VERY_POOR = "very_poor"
    SEVERE = "severe"
    HAZARDOUS = "hazardous"


class PollutantType(StrEnum):
    """Primary atmospheric pollutants tracked by the agent."""

    PM25 = "pm2_5"
    PM10 = "pm10"
    NO2 = "no2"
    SO2 = "so2"
    O3 = "o3"
    CO = "co"


class HealthRiskLevel(StrEnum):
    """Population health risk classification."""

    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"
    CRITICAL = "critical"


class PollutionSourceType(StrEnum):
    """Dominant pollution source families."""

    TRAFFIC = "traffic"
    INDUSTRIAL = "industrial"
    BIOMASS_BURNING = "biomass_burning"
    DUST = "dust"
    CONSTRUCTION = "construction"
    WILDFIRE_SMOKE = "wildfire_smoke"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class AirQualityActionType(StrEnum):
    """Standardized air quality mitigation actions for the decision framework."""

    TRAFFIC_RESTRICTIONS = "traffic_restrictions"
    INDUSTRIAL_EMISSION_REDUCTION = "industrial_emission_reduction"
    PUBLIC_HEALTH_ADVISORY = "public_health_advisory"
    SCHOOL_CLOSURE = "school_closure"
    MASK_ADVISORY = "mask_advisory"
    VEHICLE_RESTRICTIONS = "vehicle_restrictions"
    EMERGENCY_AIR_QUALITY_ALERT = "emergency_air_quality_alert"


# Peer agent identifiers
AGENT_HEATWAVE = "heatwave_agent"
AGENT_URBAN_PLANNING = "urban_planning_agent"
AGENT_DISASTER = "disaster_response_agent"
AGENT_AGRICULTURE = "agriculture_agent"
AGENT_CYCLONE = "cyclone_agent"

AIR_QUALITY_AGENT_ID = "air_quality_agent"

ALL_PEER_AGENTS: list[str] = [
    AGENT_HEATWAVE,
    AGENT_URBAN_PLANNING,
    AGENT_DISASTER,
    AGENT_AGRICULTURE,
    AGENT_CYCLONE,
]

ACTION_CATALOG: dict[AirQualityActionType, tuple[str, float, float, str]] = {
    AirQualityActionType.TRAFFIC_RESTRICTIONS: (
        "Implement odd-even traffic restrictions in high-exposure corridors", 15.0, 72.0, "low",
    ),
    AirQualityActionType.INDUSTRIAL_EMISSION_REDUCTION: (
        "Mandate temporary industrial emission curtailment in hotspot zones", 35.0, 80.0, "moderate",
    ),
    AirQualityActionType.PUBLIC_HEALTH_ADVISORY: (
        "Issue public health advisory for sensitive groups", 2.0, 65.0, "negligible",
    ),
    AirQualityActionType.SCHOOL_CLOSURE: (
        "Close schools and outdoor activity centres during severe AQI episodes", 8.0, 78.0, "low",
    ),
    AirQualityActionType.MASK_ADVISORY: (
        "Distribute N95 masks and issue mandatory outdoor mask advisory", 12.0, 70.0, "negligible",
    ),
    AirQualityActionType.VEHICLE_RESTRICTIONS: (
        "Restrict diesel commercial vehicles and construction equipment", 25.0, 75.0, "moderate",
    ),
    AirQualityActionType.EMERGENCY_AIR_QUALITY_ALERT: (
        "Activate emergency air quality alert and GRAP Stage III/IV measures", 40.0, 88.0, "moderate",
    ),
}

# CPCB 24-hour breakpoints (µg/m³) for sub-index calculation — simplified
PM25_BREAKPOINTS: list[tuple[float, float, int, int]] = [
    (0, 30, 0, 50),
    (31, 60, 51, 100),
    (61, 90, 101, 200),
    (91, 120, 201, 300),
    (121, 250, 301, 400),
    (251, 500, 401, 500),
]

PM10_BREAKPOINTS: list[tuple[float, float, int, int]] = [
    (0, 50, 0, 50),
    (51, 100, 51, 100),
    (101, 250, 101, 200),
    (251, 350, 201, 300),
    (351, 430, 301, 400),
    (431, 600, 401, 500),
]
