"""Agriculture domain type definitions and enumerations."""

from __future__ import annotations

from enum import StrEnum


class CropHealthStatus(StrEnum):
    """Remote-sensing derived crop health classification."""

    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    STRESSED = "stressed"
    CRITICAL = "critical"


class YieldRiskLevel(StrEnum):
    """Ordinal yield risk classification."""

    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"
    CRITICAL = "critical"


class CropStressType(StrEnum):
    """Primary crop stress drivers."""

    NONE = "none"
    DROUGHT = "drought"
    HEAT = "heat"
    FLOOD = "flood"
    WATERLOGGING = "waterlogging"
    PEST = "pest"
    NUTRIENT = "nutrient"
    COMPOUND = "compound"


class IrrigationRecommendationType(StrEnum):
    """Irrigation action classification."""

    MAINTAIN = "maintain"
    INCREASE = "increase"
    REDUCE = "reduce"
    EMERGENCY = "emergency"
    DEFER = "defer"


class AgricultureActionType(StrEnum):
    """Standardized agricultural actions for the decision framework."""

    INCREASE_IRRIGATION = "increase_irrigation"
    REDUCE_IRRIGATION = "reduce_irrigation"
    CHANGE_CROP_SCHEDULE = "change_crop_schedule"
    ALTERNATIVE_CROP = "alternative_crop"
    EMERGENCY_IRRIGATION = "emergency_irrigation"
    WATER_CONSERVATION = "water_conservation"
    CROP_PROTECTION = "crop_protection"
    GOVERNMENT_ASSISTANCE = "government_assistance"


# Peer agent identifiers
AGENT_WATER_RESOURCE = "water_resource_agent"
AGENT_HEATWAVE = "heatwave_agent"
AGENT_FLOOD = "flood_agent"
AGENT_URBAN_PLANNING = "urban_planning_agent"
AGENT_DISASTER = "disaster_response_agent"

AGRICULTURE_AGENT_ID = "agriculture_agent"

ALL_PEER_AGENTS: list[str] = [
    AGENT_WATER_RESOURCE,
    AGENT_HEATWAVE,
    AGENT_FLOOD,
    AGENT_URBAN_PLANNING,
]

ACTION_CATALOG: dict[AgricultureActionType, tuple[str, float, float, str]] = {
    AgricultureActionType.INCREASE_IRRIGATION: (
        "Increase irrigation frequency and duration", 20.0, 75.0, "low",
    ),
    AgricultureActionType.REDUCE_IRRIGATION: (
        "Reduce irrigation to prevent waterlogging", 5.0, 60.0, "low",
    ),
    AgricultureActionType.CHANGE_CROP_SCHEDULE: (
        "Adjust sowing/harvest schedule based on phenology", 8.0, 70.0, "low",
    ),
    AgricultureActionType.ALTERNATIVE_CROP: (
        "Recommend drought-resilient alternative crop variety", 15.0, 72.0, "moderate",
    ),
    AgricultureActionType.EMERGENCY_IRRIGATION: (
        "Deploy emergency irrigation for critical growth stage", 45.0, 88.0, "moderate",
    ),
    AgricultureActionType.WATER_CONSERVATION: (
        "Implement micro-irrigation and water conservation measures", 25.0, 68.0, "low",
    ),
    AgricultureActionType.CROP_PROTECTION: (
        "Apply crop protection for pest/disease risk", 18.0, 70.0, "low",
    ),
    AgricultureActionType.GOVERNMENT_ASSISTANCE: (
        "Activate government agricultural assistance programs", 10.0, 65.0, "negligible",
    ),
}

# Common Indian crop types
CROP_WHEAT = "wheat"
CROP_PADDY = "paddy"
CROP_COTTON = "cotton"
CROP_MAIZE = "maize"
CROP_SUGARCANE = "sugarcane"
CROP_MILLET = "millet"
