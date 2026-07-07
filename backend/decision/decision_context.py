"""Context models for decision requests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.agents.state.climate_state import (
    ActiveSimulation,
    ClimateState,
    ForecastReference,
)


class ScenarioContext(BaseModel):
    """Scenario metadata for decision evaluation."""

    scenario_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "default"
    description: str = ""
    region_id: str | None = None
    horizon_hours: int = Field(default=72, ge=1)
    tags: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SimulationReference(BaseModel):
    """Pointer to a simulation artifact relevant to the decision."""

    simulation_id: str
    name: str | None = None
    status: str | None = None
    storage_uri: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_active_simulation(cls, sim: ActiveSimulation) -> SimulationReference:
        return cls(
            simulation_id=sim.simulation_id,
            name=sim.name,
            status=sim.status.value if hasattr(sim.status, "value") else str(sim.status),
            parameters=dict(sim.parameters),
        )


class DecisionContext(BaseModel):
    """Environmental and operational context for a decision request."""

    scenario: ScenarioContext = Field(default_factory=ScenarioContext)
    climate_state: ClimateState | None = None
    forecast_reference: ForecastReference | None = None
    simulation_reference: SimulationReference | None = None
    session_id: str | None = None
    request_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_climate_state(
        cls,
        climate_state: ClimateState,
        *,
        scenario_name: str = "climate_decision",
        region_id: str | None = None,
    ) -> DecisionContext:
        scenario = ScenarioContext(
            scenario_id=climate_state.scenario_id or str(uuid4()),
            name=scenario_name,
            region_id=region_id or (
                climate_state.location.region_id if climate_state.location else None
            ),
        )
        forecast_ref = climate_state.forecast_references[0] if climate_state.forecast_references else None
        sim_ref = (
            SimulationReference.from_active_simulation(climate_state.active_simulation)
            if climate_state.active_simulation
            else None
        )
        return cls(
            scenario=scenario,
            climate_state=climate_state,
            forecast_reference=forecast_ref,
            simulation_reference=sim_ref,
        )
