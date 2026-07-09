"""Disaster response domain type definitions and enumerations."""

from __future__ import annotations

from enum import StrEnum


class EmergencyPriority(StrEnum):
    """Operational emergency priority level."""

    ROUTINE = "routine"
    ELEVATED = "elevated"
    HIGH = "high"
    SEVERE = "severe"
    CATASTROPHIC = "catastrophic"


class HazardType(StrEnum):
    """Multi-hazard classification."""

    FLOOD = "flood"
    CYCLONE = "cyclone"
    HEATWAVE = "heatwave"
    WATER_STRESS = "water_stress"
    DROUGHT = "drought"
    AIR_QUALITY = "air_quality"
    AGRICULTURE = "agriculture"
    COMPOUND = "compound"
    UNKNOWN = "unknown"


class ResponsePhase(StrEnum):
    """Disaster response lifecycle phase."""

    PREPAREDNESS = "preparedness"
    RESPONSE = "response"
    RECOVERY = "recovery"
    MITIGATION = "mitigation"


class DisasterActionType(StrEnum):
    """Standardized disaster response actions for the decision framework."""

    EVACUATION = "evacuation"
    EMERGENCY_RESOURCE_DEPLOYMENT = "emergency_resource_deployment"
    SHELTER_ACTIVATION = "shelter_activation"
    MEDICAL_RESPONSE = "medical_response"
    ROAD_CLOSURE = "road_closure"
    INFRASTRUCTURE_PROTECTION = "infrastructure_protection"
    EMERGENCY_COMMUNICATION = "emergency_communication"
    SEARCH_AND_RESCUE = "search_and_rescue"


# Hazard agent identifiers
AGENT_FLOOD = "flood_agent"
AGENT_CYCLONE = "cyclone_agent"
AGENT_HEATWAVE = "heatwave_agent"
AGENT_WATER_RESOURCE = "water_resource_agent"
AGENT_URBAN_PLANNING = "urban_planning_agent"
AGENT_AGRICULTURE = "agriculture_agent"
AGENT_AIR_QUALITY = "air_quality_agent"

DISASTER_RESPONSE_AGENT_ID = "disaster_response_agent"

ALL_HAZARD_AGENTS: list[str] = [
    AGENT_FLOOD,
    AGENT_CYCLONE,
    AGENT_HEATWAVE,
    AGENT_WATER_RESOURCE,
    AGENT_AIR_QUALITY,
    AGENT_AGRICULTURE,
]

ACTION_CATALOG: dict[DisasterActionType, tuple[str, float, float, str]] = {
    DisasterActionType.EVACUATION: ("Execute phased population evacuation", 120.0, 95.0, "moderate"),
    DisasterActionType.EMERGENCY_RESOURCE_DEPLOYMENT: (
        "Deploy emergency relief resources", 80.0, 90.0, "low",
    ),
    DisasterActionType.SHELTER_ACTIVATION: ("Activate emergency shelters", 40.0, 85.0, "low"),
    DisasterActionType.MEDICAL_RESPONSE: ("Deploy medical emergency teams", 60.0, 92.0, "low"),
    DisasterActionType.ROAD_CLOSURE: ("Close vulnerable transport corridors", 10.0, 70.0, "low"),
    DisasterActionType.INFRASTRUCTURE_PROTECTION: (
        "Protect critical infrastructure assets", 55.0, 80.0, "low",
    ),
    DisasterActionType.EMERGENCY_COMMUNICATION: (
        "Issue multi-channel emergency alerts", 5.0, 65.0, "negligible",
    ),
    DisasterActionType.SEARCH_AND_RESCUE: ("Launch search and rescue operations", 90.0, 93.0, "moderate"),
}
