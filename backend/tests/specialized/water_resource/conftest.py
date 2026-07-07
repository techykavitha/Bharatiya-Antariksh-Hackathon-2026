"""Shared fixtures for water resource agent tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import AgentResponse
from backend.agents.specialized.agent_execution import AgentCommunicationInterface
from backend.agents.specialized.water_resource import WaterResourceAgent
from backend.agents.specialized.water_resource.water_context import HistoricalWaterRecord
from backend.agents.specialized.water_resource.water_models import WaterStressLevel
from backend.agents.state.climate_state import (
    ClimateMeasurement,
    ClimateState,
    GeoLocation,
)
from backend.utils.enums import AgentStatus, ClimateVariable


def build_water_context(
    *,
    region_id: str = "krishna_basin",
    basin_id: str = "krishna",
    reservoir_level_pct: float = 72.0,
    reservoir_capacity_mcm: float = 8100.0,
    spillway_active: bool = False,
    river_level_m: float = 18.5,
    river_banks_m: float = 22.0,
    river_discharge_m3s: float = 1200.0,
    groundwater_depth_m: float = 22.0,
    groundwater_trend: str = "stable",
    rainfall_mm: float = 45.0,
    monsoon_normal_pct: float = 92.0,
    urban_demand_m3d: float = 250_000.0,
    agricultural_demand_m3d: float = 800_000.0,
    population: int = 2_500_000,
    crop_area_ha: float = 500_000.0,
    soil_moisture: float = 0.55,
    districts: list[str] | None = None,
    strict: bool = False,
) -> dict:
    """Build a realistic Krishna basin water management scenario."""
    return {
        "region_id": region_id,
        "basin_id": basin_id,
        "latitude": 16.5062,
        "longitude": 80.6480,
        "reservoir_name": "Nagarjuna Sagar",
        "reservoir_level_pct": reservoir_level_pct,
        "reservoir_capacity_mcm": reservoir_capacity_mcm,
        "live_storage_mcm": reservoir_capacity_mcm * reservoir_level_pct / 100.0,
        "reservoir_inflow_m3s": 850.0,
        "reservoir_outflow_m3s": 600.0,
        "spillway_active": spillway_active,
        "reservoir_available": True,
        "river_level_m": river_level_m,
        "river_banks_m": river_banks_m,
        "river_discharge_m3s": river_discharge_m3s,
        "upstream_inflow_m3s": 950.0,
        "downstream_demand_m3s": 700.0,
        "groundwater_depth_m": groundwater_depth_m,
        "groundwater_level_m": 50.0 - groundwater_depth_m / 2,
        "groundwater_recharge_mm": 8.0,
        "groundwater_extraction_m3d": 120_000.0,
        "groundwater_trend": groundwater_trend,
        "groundwater_available": True,
        "aquifer_id": "krishna_delta_aquifer",
        "rainfall_mm": rainfall_mm,
        "rainfall_forecast_24h_mm": 35.0,
        "rainfall_forecast_72h_mm": 80.0,
        "monsoon_cumulative_mm": 650.0,
        "monsoon_normal_pct": monsoon_normal_pct,
        "urban_demand_m3d": urban_demand_m3d,
        "agricultural_demand_m3d": agricultural_demand_m3d,
        "industrial_demand_m3d": 50_000.0,
        "population": population,
        "crop_area_ha": crop_area_ha,
        "crop_type": "paddy",
        "irrigation_efficiency": 0.42,
        "soil_moisture": soil_moisture,
        "root_zone_moisture": soil_moisture,
        "districts": districts or ["Guntur", "Krishna", "Nalgonda"],
        "dependent_basins": ["godavari_link"],
        "forecast_available": True,
        "climate_state_available": True,
        "digital_twin_available": True,
        "twin_id": "twin-krishna-01",
        "digital_twin_state": {
            "twin_id": "twin-krishna-01",
            "layers": {"water": {"reservoir_level_pct": reservoir_level_pct, "basin_flow_m3s": 1200.0}},
        },
        "historical_water_levels": [
            HistoricalWaterRecord(
                record_id="drought-2016",
                year=2016,
                month=6,
                reservoir_level_pct=28.0,
                groundwater_depth_m=38.0,
                rainfall_mm=320.0,
                stress_level=WaterStressLevel.SEVERE,
            ).model_dump(),
        ],
        "session_id": "water-test-session",
        "strict_validation": strict,
    }


def build_overflow_context() -> dict:
    """Reservoir near spillway — overflow scenario."""
    ctx = build_water_context(
        reservoir_level_pct=97.0,
        spillway_active=True,
        rainfall_mm=120.0,
        monsoon_normal_pct=130.0,
        river_level_m=21.5,
        river_banks_m=20.0,
    )
    ctx["rainfall_forecast_24h_mm"] = 90.0
    ctx["rainfall_forecast_72h_mm"] = 200.0
    return ctx


def build_drought_context() -> dict:
    """Severe water stress / drought scenario."""
    ctx = build_water_context(
        reservoir_level_pct=18.0,
        groundwater_depth_m=42.0,
        groundwater_trend="critical_decline",
        rainfall_mm=5.0,
        monsoon_normal_pct=45.0,
        soil_moisture=0.22,
        agricultural_demand_m3d=1_200_000.0,
    )
    ctx["rainfall_forecast_24h_mm"] = 2.0
    ctx["rainfall_forecast_72h_mm"] = 8.0
    return ctx


def build_climate_state() -> ClimateState:
    now = datetime.now(timezone.utc)
    return ClimateState(
        location=GeoLocation(latitude=16.5062, longitude=80.6480, region_id="krishna_basin"),
        measurements=[
            ClimateMeasurement(
                variable=ClimateVariable.PRECIPITATION,
                value=45.0,
                unit="mm",
                timestamp=now,
            ),
            ClimateMeasurement(
                variable=ClimateVariable.SOIL_MOISTURE,
                value=0.55,
                unit="fraction",
                timestamp=now,
            ),
        ],
        scenario_id="water-scenario-01",
    )


class MockWaterComm(AgentCommunicationInterface):
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
async def water_agent(memory_manager: MemoryManager) -> WaterResourceAgent:
    return await WaterResourceAgent.create(
        memory_manager,
        agent_communication=MockWaterComm(),
    )
