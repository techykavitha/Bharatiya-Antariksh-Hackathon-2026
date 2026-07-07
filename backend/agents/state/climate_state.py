"""Climate domain state models for Hyperion Climate Twin."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.utils.enums import ClimateVariable, SimulationStatus


class GeoLocation(BaseModel):
    """Geographic coordinate with optional elevation."""

    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    elevation_m: float | None = Field(default=None)
    region_id: str | None = Field(default=None, description="Administrative region identifier")


class ClimateMeasurement(BaseModel):
    """A single climate variable observation or model output."""

    variable: ClimateVariable
    value: float
    unit: str
    timestamp: datetime
    location: GeoLocation | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source: str | None = Field(default=None, description="Data source or model identifier")


class ActiveSimulation(BaseModel):
    """Metadata for a currently running or paused climate simulation."""

    simulation_id: str
    name: str
    status: SimulationStatus = SimulationStatus.PENDING
    started_at: datetime | None = None
    updated_at: datetime | None = None
    current_step: int = Field(default=0, ge=0)
    total_steps: int | None = Field(default=None, ge=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)


class ForecastReference(BaseModel):
    """Pointer to a stored forecast artifact."""

    forecast_id: str
    model_name: str
    horizon_hours: int = Field(..., ge=1)
    generated_at: datetime
    location: GeoLocation | None = None
    variables: list[ClimateVariable] = Field(default_factory=list)
    storage_uri: str | None = Field(default=None, description="URI to forecast data store")


class DigitalTwinSnapshot(BaseModel):
    """Point-in-time snapshot of the digital twin state."""

    twin_id: str
    version: str
    captured_at: datetime
    location: GeoLocation | None = None
    layers: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClimateState(BaseModel):
    """
    Canonical representation of the current climate context.

    Aggregates measurements, active simulations, forecast references,
    and digital twin snapshots for agent reasoning and tool execution.
    """

    location: GeoLocation | None = None
    measurements: list[ClimateMeasurement] = Field(default_factory=list)
    active_simulation: ActiveSimulation | None = None
    forecast_references: list[ForecastReference] = Field(default_factory=list)
    digital_twin: DigitalTwinSnapshot | None = None
    scenario_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def latest_measurement(self, variable: ClimateVariable) -> ClimateMeasurement | None:
        """Return the most recent measurement for a given climate variable."""
        matches = [m for m in self.measurements if m.variable == variable]
        if not matches:
            return None
        return max(matches, key=lambda m: m.timestamp)
