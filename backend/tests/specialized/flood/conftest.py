"""Shared fixtures for flood agent tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import AgentResponse
from backend.agents.specialized.agent_execution import AgentCommunicationInterface
from backend.agents.specialized.flood import FloodAgent
from backend.agents.specialized.flood.flood_context import HistoricalFloodEvent
from backend.agents.specialized.flood.flood_models import FloodType
from backend.agents.state.climate_state import (
    ClimateMeasurement,
    ClimateState,
    GeoLocation,
)
from backend.utils.enums import AgentStatus, ClimateVariable


def build_flood_context(
    *,
    region_id: str = "chennai",
    rainfall_mm: float = 120.0,
    river_level_m: float = 8.5,
    river_banks_m: float = 7.0,
    reservoir_level_pct: float = 92.0,
    dem_resolution_m: float = 10.0,
    mean_elevation_m: float = 12.0,
    slope_deg: float = 18.0,
    drainage_capacity: float = 0.25,
    soil_moisture: float = 0.85,
    urban_density: float = 0.7,
    districts: list[str] | None = None,
    strict: bool = False,
) -> dict:
    """Build a realistic flood scenario request context."""
    return {
        "region_id": region_id,
        "latitude": 13.0827,
        "longitude": 80.2707,
        "rainfall_mm": rainfall_mm,
        "rainfall_forecast_24h_mm": 80.0,
        "rainfall_forecast_72h_mm": 150.0,
        "rainfall_intensity_mm_per_hr": 22.0,
        "antecedent_rainfall_7d_mm": 180.0,
        "river_level_m": river_level_m,
        "river_banks_m": river_banks_m,
        "river_discharge_m3s": 2500.0,
        "reservoir_level_pct": reservoir_level_pct,
        "reservoir_capacity_mcm": 3500.0,
        "spillway_active": reservoir_level_pct >= 90.0,
        "dem_resolution_m": dem_resolution_m,
        "mean_elevation_m": mean_elevation_m,
        "dem_available": True,
        "slope_deg": slope_deg,
        "drainage_capacity": drainage_capacity,
        "soil_moisture": soil_moisture,
        "land_cover": "urban",
        "urban_density": urban_density,
        "impervious_fraction": 0.65,
        "districts": districts or ["Chennai Central", "Adyar", "Tambaram"],
        "forecast_available": True,
        "climate_state_available": True,
        "digital_twin_available": True,
        "twin_id": "twin-chennai-01",
        "digital_twin_state": {
            "twin_id": "twin-chennai-01",
            "layers": {"flood": {"inundation_depth_m": 1.2}},
        },
        "historical_floods": [
            HistoricalFloodEvent(
                event_id="flood-2015",
                year=2015,
                flood_type=FloodType.URBAN,
                peak_depth_m=1.8,
                affected_population=50_000,
                districts=["Chennai Central"],
                rainfall_mm=100.0,
            ).model_dump(),
        ],
        "session_id": "flood-test-session",
        "strict_validation": strict,
    }


def build_climate_state() -> ClimateState:
    now = datetime.now(timezone.utc)
    return ClimateState(
        location=GeoLocation(latitude=13.0827, longitude=80.2707, region_id="chennai"),
        measurements=[
            ClimateMeasurement(
                variable=ClimateVariable.PRECIPITATION,
                value=120.0,
                unit="mm",
                timestamp=now,
            ),
            ClimateMeasurement(
                variable=ClimateVariable.SOIL_MOISTURE,
                value=0.85,
                unit="fraction",
                timestamp=now,
            ),
        ],
        scenario_id="flood-scenario-01",
    )


class MockFloodComm(AgentCommunicationInterface):
    async def call_agent(
        self,
        agent_id: str,
        request: AgentRequest,
        *,
        timeout_seconds: float | None = None,
    ) -> AgentResponse:
        return AgentResponse(
            request_id=request.request_id,
            agent_id=agent_id,
            content=f"Support from {agent_id}",
            status=AgentStatus.COMPLETED,
        )

    async def broadcast(self, agent_ids: list[str], request: AgentRequest) -> list[AgentResponse]:
        return [
            AgentResponse(request_id=request.request_id, agent_id=aid, content="ok")
            for aid in agent_ids
        ]

    async def wait_for_response(self, correlation_id: str, *, timeout_seconds: float = 120) -> AgentResponse:
        return AgentResponse(
            request_id=correlation_id,
            agent_id="async",
            content="async",
        )


@pytest.fixture
async def memory_manager() -> MemoryManager:
    return await MemoryManager.create_in_memory()


@pytest.fixture
async def flood_agent(memory_manager: MemoryManager) -> FloodAgent:
    return await FloodAgent.create(
        memory_manager,
        agent_communication=MockFloodComm(),
    )
