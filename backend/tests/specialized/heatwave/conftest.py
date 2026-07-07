"""Shared fixtures for heatwave agent tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import AgentResponse
from backend.agents.specialized.agent_execution import AgentCommunicationInterface
from backend.agents.specialized.heatwave import HeatwaveAgent
from backend.agents.specialized.heatwave.heatwave_context import HistoricalHeatwaveEvent
from backend.agents.state.climate_state import (
    ClimateMeasurement,
    ClimateState,
    GeoLocation,
)
from backend.decision.decision_actions import DecisionAction
from backend.decision.decision_response import DecisionResponse
from backend.decision.decision_types import RiskLevel
from backend.utils.enums import AgentStatus, ClimateVariable


def build_delhi_heatwave_context(
    *,
    region_id: str = "delhi",
    air_temp_c: float = 46.0,
    humidity_pct: float = 35.0,
    lst_c: float = 52.0,
    ndvi: float = 0.18,
    urban_density: float = 0.88,
    population_density: float = 11_000.0,
    building_density: float = 0.75,
    aqi: float | None = None,
    districts: list[str] | None = None,
    strict: bool = False,
) -> dict:
    """Build Delhi 2024-style extreme heatwave scenario."""
    return {
        "region_id": region_id,
        "latitude": 28.6139,
        "longitude": 77.2090,
        "air_temp_c": air_temp_c,
        "max_temp_c": air_temp_c,
        "surface_temp_c": air_temp_c + 3.0,
        "forecast_max_24h_c": air_temp_c + 1.0,
        "forecast_max_72h_c": air_temp_c + 2.0,
        "temp_trend_c_per_day": 1.2,
        "humidity_pct": humidity_pct,
        "relative_humidity_pct": humidity_pct,
        "wind_speed_ms": 2.5,
        "solar_radiation_wm2": 950.0,
        "lst_c": lst_c,
        "land_surface_temp_c": lst_c,
        "ndvi": ndvi,
        "land_cover": "urban",
        "urban_density": urban_density,
        "population_density": population_density,
        "building_density": building_density,
        "impervious_fraction": 0.72,
        "aqi": aqi,
        "districts": districts or ["Central Delhi", "East Delhi", "North Delhi", "South Delhi"],
        "forecast_available": True,
        "climate_state_available": True,
        "digital_twin_available": True,
        "twin_id": "twin-delhi-01",
        "digital_twin_state": {
            "twin_id": "twin-delhi-01",
            "layers": {"thermal": {"lst_c": lst_c, "uhi_intensity_c": lst_c - air_temp_c}},
        },
        "historical_heatwaves": [
            HistoricalHeatwaveEvent(
                event_id="heat-2022-delhi",
                year=2022,
                peak_temp_c=49.2,
                duration_days=9,
                affected_population=19_000_000,
                districts=["Central Delhi"],
                fatalities=25,
                notes="May 2022 heatwave",
            ).model_dump(),
            HistoricalHeatwaveEvent(
                event_id="heat-2015-delhi",
                year=2015,
                peak_temp_c=47.8,
                duration_days=7,
                affected_population=16_000_000,
                districts=["East Delhi"],
                fatalities=18,
            ).model_dump(),
        ],
        "session_id": "heatwave-test-session",
        "strict_validation": strict,
    }


def build_ahmedabad_uhi_context() -> dict:
    """Build Ahmedabad urban heat island scenario."""
    return build_delhi_heatwave_context(
        region_id="ahmedabad",
        air_temp_c=42.0,
        humidity_pct=55.0,
        lst_c=49.0,
        ndvi=0.12,
        urban_density=0.92,
        population_density=12_500.0,
        building_density=0.82,
        districts=["Ahmedabad East", "Ahmedabad West", "Sabarmati"],
    ) | {
        "latitude": 23.0225,
        "longitude": 72.5714,
        "twin_id": "twin-ahmedabad-01",
        "digital_twin_state": {
            "twin_id": "twin-ahmedabad-01",
            "layers": {"thermal": {"lst_c": 49.0, "uhi_intensity_c": 7.0}},
        },
        "historical_heatwaves": [
            HistoricalHeatwaveEvent(
                event_id="heat-2010-ahmedabad",
                year=2010,
                peak_temp_c=46.8,
                duration_days=5,
                affected_population=5_500_000,
                districts=["Ahmedabad East"],
            ).model_dump(),
        ],
    }


def build_compound_heat_aqi_context() -> dict:
    """Build compound heat + poor air quality scenario."""
    return build_delhi_heatwave_context(
        air_temp_c=44.0,
        humidity_pct=48.0,
        lst_c=50.0,
        aqi=380.0,
        districts=["Central Delhi", "Noida", "Gurgaon"],
    )


def build_mild_heat_context() -> dict:
    """Build low-risk thermal monitoring scenario."""
    return build_delhi_heatwave_context(
        air_temp_c=34.0,
        humidity_pct=45.0,
        lst_c=36.0,
        ndvi=0.55,
        urban_density=0.35,
        population_density=4_000.0,
        building_density=0.30,
    ) | {
        "forecast_max_24h_c": 35.0,
        "forecast_max_72h_c": 36.0,
        "temp_trend_c_per_day": 0.1,
        "historical_heatwaves": [],
    }


def build_climate_state(region_id: str = "delhi") -> ClimateState:
    now = datetime.now(timezone.utc)
    return ClimateState(
        location=GeoLocation(latitude=28.6139, longitude=77.2090, region_id=region_id),
        measurements=[
            ClimateMeasurement(
                variable=ClimateVariable.TEMPERATURE,
                value=46.0,
                unit="C",
                timestamp=now,
            ),
            ClimateMeasurement(
                variable=ClimateVariable.HUMIDITY,
                value=35.0,
                unit="percent",
                timestamp=now,
            ),
        ],
        scenario_id="heatwave-scenario-01",
    )


class MockHeatwaveComm(AgentCommunicationInterface):
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
async def heatwave_agent(memory_manager: MemoryManager) -> HeatwaveAgent:
    return await HeatwaveAgent.create(
        memory_manager,
        agent_communication=MockHeatwaveComm(),
    )


class MockRLOptimizationService:
    """Mock RL service for heatwave integration tests."""

    async def optimize(self, request, *, algorithm=None, validate: bool = True) -> DecisionResponse:
        action = request.possible_actions[0] if request.possible_actions else DecisionAction(
            description="Open public cooling centers",
            cost=15.0,
            expected_benefit=80.0,
            risk=RiskLevel.LOW,
        )
        return DecisionResponse(
            decision_id=request.decision_id,
            agent_id=request.agent_id,
            chosen_action=action,
            confidence=0.82,
            expected_reward=action.expected_benefit - action.cost,
        )


@pytest.fixture
async def heatwave_agent_with_rl(memory_manager: MemoryManager) -> HeatwaveAgent:
    return await HeatwaveAgent.create(
        memory_manager,
        rl_service=MockRLOptimizationService(),  # type: ignore[arg-type]
        agent_communication=MockHeatwaveComm(),
    )
