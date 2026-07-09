"""Disaster response analysis domain models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.agents.specialized.disaster_response.disaster_models import (
    EmergencyPriority,
    HazardType,
    ResponsePhase,
)
from backend.agents.state.climate_state import GeoLocation


class HazardAgentOutput(BaseModel):
    """Normalized output from a specialized hazard agent."""

    agent_id: str
    hazard_type: HazardType = HazardType.UNKNOWN
    severity: str = "unknown"
    risk_level: str = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    affected_regions: list[str] = Field(default_factory=list)
    affected_population: int = Field(default=0, ge=0)
    recommendations: list[str] = Field(default_factory=list)
    structured_output: dict[str, Any] = Field(default_factory=dict)
    consulted_live: bool = False


class PriorityRanking(BaseModel):
    """Ranked hazard priority for response planning."""

    rank: int = Field(default=1, ge=1)
    hazard_type: HazardType = HazardType.UNKNOWN
    agent_id: str = ""
    priority_score: float = Field(default=0.0, ge=0.0, le=1.0)
    emergency_priority: EmergencyPriority = EmergencyPriority.ROUTINE
    rationale: str = ""


class ResourceRequirement(BaseModel):
    """Emergency resource need estimate."""

    resource_type: str
    quantity: int = Field(default=0, ge=0)
    unit: str = "units"
    urgency: EmergencyPriority = EmergencyPriority.ELEVATED
    notes: str = ""


class EvacuationStrategy(BaseModel):
    """Evacuation plan summary."""

    required: bool = False
    zones: list[str] = Field(default_factory=list)
    estimated_population: int = Field(default=0, ge=0)
    priority_corridors: list[str] = Field(default_factory=list)
    shelter_assignments: list[str] = Field(default_factory=list)
    timeline_hours: float = Field(default=24.0, ge=0.0)


class MedicalSupportPlan(BaseModel):
    """Medical emergency support plan."""

    hospitals_activated: int = Field(default=0, ge=0)
    ambulances_required: int = Field(default=0, ge=0)
    field_hospitals: int = Field(default=0, ge=0)
    trauma_capacity_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    notes: list[str] = Field(default_factory=list)


class RecoveryPriority(BaseModel):
    """Post-disaster recovery priority item."""

    priority: int = Field(default=1, ge=1)
    domain: str
    description: str
    horizon_days: int = Field(default=30, ge=1)


class KnowledgeGraphInsights(BaseModel):
    """Pre-queried CKG insights for disaster coordination."""

    affected_infrastructure: list[str] = Field(default_factory=list)
    population_dependencies: list[str] = Field(default_factory=list)
    cascade_impacts: list[list[str]] = Field(default_factory=list)
    historical_responses: list[str] = Field(default_factory=list)
    query_count: int = Field(default=0, ge=0)


class DisasterAnalysisSignals(BaseModel):
    """Intermediate signals from disaster response reasoning."""

    active_hazard_count: int = Field(default=0, ge=0)
    compound_disaster: bool = False
    high_population_impact: bool = False
    infrastructure_critical: bool = False
    resource_gap: bool = False
    evacuation_required: bool = False
    medical_surge_required: bool = False
    composite_priority_score: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: float = Field(default=0.5, ge=0.0, le=1.0)


class DisasterInputs(BaseModel):
    """Aggregated disaster response inputs from request context."""

    location: GeoLocation | None = None
    region_id: str | None = None
    districts: list[str] = Field(default_factory=list)
    response_phase: ResponsePhase = ResponsePhase.RESPONSE
    hazard_agent_outputs: dict[str, HazardAgentOutput] = Field(default_factory=dict)
    consult_agents: list[str] = Field(default_factory=list)
    twin_id: str | None = None
    forecast_available: bool = False
    climate_state_available: bool = False
    digital_twin_available: bool = False

    @classmethod
    def from_request_context(cls, context: dict[str, Any]) -> DisasterInputs:
        location = None
        if "latitude" in context and "longitude" in context:
            location = GeoLocation(
                latitude=float(context["latitude"]),
                longitude=float(context["longitude"]),
                region_id=context.get("region_id"),
            )
        elif context.get("location") and isinstance(context["location"], dict):
            location = GeoLocation.model_validate(context["location"])

        phase_raw = context.get("response_phase", ResponsePhase.RESPONSE.value)
        try:
            phase = ResponsePhase(phase_raw)
        except ValueError:
            phase = ResponsePhase.RESPONSE

        hazard_outputs: dict[str, HazardAgentOutput] = {}
        raw_hazards = context.get("hazard_agent_outputs", {})
        if isinstance(raw_hazards, dict):
            for agent_id, payload in raw_hazards.items():
                if isinstance(payload, HazardAgentOutput):
                    hazard_outputs[agent_id] = payload
                elif isinstance(payload, dict):
                    hazard_outputs[agent_id] = HazardAgentOutput.model_validate({
                        "agent_id": agent_id,
                        **payload,
                    })

        return cls(
            location=location,
            region_id=context.get("region_id") or (location.region_id if location else None),
            districts=list(context.get("districts", [])),
            response_phase=phase,
            hazard_agent_outputs=hazard_outputs,
            consult_agents=list(context.get("consult_agents", [])),
            twin_id=context.get("twin_id"),
            forecast_available=bool(context.get("forecast_available")),
            climate_state_available=bool(context.get("climate_state_available")),
            digital_twin_available=bool(context.get("digital_twin_available")),
        )
