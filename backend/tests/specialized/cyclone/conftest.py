"""Shared fixtures for cyclone agent tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import AgentResponse
from backend.agents.specialized.agent_execution import AgentCommunicationInterface
from backend.agents.specialized.cyclone import CycloneAgent
from backend.agents.specialized.cyclone.cyclone_context import HistoricalCycloneEvent, TrackPoint
from backend.agents.specialized.cyclone.cyclone_models import CycloneBasin
from backend.agents.state.climate_state import ClimateMeasurement, ClimateState, GeoLocation
from backend.decision.decision_actions import DecisionAction
from backend.decision.decision_response import DecisionResponse
from backend.decision.decision_types import RiskLevel
from backend.knowledge_graph.graph_engine import GraphEngine
from backend.utils.enums import AgentStatus, ClimateVariable
from backend.xai import ExplanationEngine


def _base_ocean_context(**overrides: object) -> dict:
    base = {
        "region_id": "odisha_coast",
        "latitude": 19.8135,
        "longitude": 85.8312,
        "basin": CycloneBasin.BAY_OF_BENGAL.value,
        "sst_c": 29.5,
        "sea_level_pressure_hpa": 985.0,
        "wind_speed_kt": 75.0,
        "wind_direction_deg": 220.0,
        "humidity_pct": 88.0,
        "ocean_heat_content_kj_cm2": 95.0,
        "cloud_top_temp_c": -58.0,
        "vertical_wind_shear_kt": 8.0,
        "landfall_probability": 0.72,
        "landfall_hours": 18.0,
        "max_wind_kt_forecast": 80.0,
        "forecast_rainfall_24h_mm": 180.0,
        "forecast_rainfall_72h_mm": 420.0,
        "rainfall_mm_24h": 180.0,
        "rainfall_mm_72h": 420.0,
        "districts": ["Puri", "Khordha", "Ganjam"],
        "coastal_states": ["Odisha"],
        "population_density": 8000.0,
        "forecast_available": True,
        "climate_state_available": True,
        "digital_twin_available": True,
        "insat_available": True,
        "twin_id": "twin-odisha-01",
        "digital_twin_state": {
            "twin_id": "twin-odisha-01",
            "scenario_id": "cyclone-landfall",
            "layers": {"cyclone": {"coastal_defense_status": "moderate"}},
        },
        "session_id": "cyclone-test-session",
    }
    base.update(overrides)
    return base


def build_fani_context() -> dict:
    """Cyclone Fani (2019) — Bay of Bengal, Odisha landfall analog."""
    return _base_ocean_context(
        region_id="fani_2019",
        cyclone_name="Fani",
        latitude=18.5,
        longitude=86.0,
        wind_speed_kt=115.0,
        sea_level_pressure_hpa=932.0,
        max_wind_kt_forecast=125.0,
        landfall_probability=0.88,
        landfall_hours=12.0,
        coastal_states=["Odisha", "West Bengal"],
        historical_cyclones=[
            HistoricalCycloneEvent(
                event_id="fani-2019",
                name="Fani",
                year=2019,
                basin=CycloneBasin.BAY_OF_BENGAL,
                peak_wind_kt=125.0,
                min_pressure_hpa=932.0,
                landfall_state="Odisha",
                fatalities=89,
                affected_population=16_000_000,
                storm_surge_m=4.5,
                notes="Extremely Severe Cyclonic Storm",
            ).model_dump(),
        ],
        track_points=[
            TrackPoint(latitude=18.5, longitude=86.0, wind_speed_kt=115.0).model_dump(),
            TrackPoint(latitude=19.5, longitude=85.5, wind_speed_kt=120.0).model_dump(),
            TrackPoint(latitude=20.2, longitude=85.8, wind_speed_kt=125.0).model_dump(),
        ],
    )


def build_amphan_context() -> dict:
    """Cyclone Amphan (2020) — BoB, West Bengal."""
    return _base_ocean_context(
        region_id="amphan_2020",
        cyclone_name="Amphan",
        latitude=16.8,
        longitude=87.5,
        wind_speed_kt=130.0,
        sea_level_pressure_hpa=925.0,
        max_wind_kt_forecast=135.0,
        sst_c=30.2,
        ocean_heat_content_kj_cm2=110.0,
        coastal_states=["West Bengal", "Odisha"],
        districts=["South 24 Parganas", "Kolkata", "East Midnapore"],
        historical_cyclones=[
            HistoricalCycloneEvent(
                event_id="amphan-2020",
                name="Amphan",
                year=2020,
                basin=CycloneBasin.BAY_OF_BENGAL,
                peak_wind_kt=135.0,
                min_pressure_hpa=925.0,
                landfall_state="West Bengal",
                fatalities=128,
                affected_population=18_000_000,
                storm_surge_m=5.0,
            ).model_dump(),
        ],
    )


def build_biparjoy_context() -> dict:
    """Cyclone Biparjoy (2023) — Arabian Sea."""
    return _base_ocean_context(
        region_id="biparjoy_2023",
        cyclone_name="Biparjoy",
        basin=CycloneBasin.ARABIAN_SEA.value,
        latitude=20.5,
        longitude=67.0,
        wind_speed_kt=95.0,
        sea_level_pressure_hpa=968.0,
        max_wind_kt_forecast=100.0,
        coastal_states=["Gujarat", "Pakistan"],
        districts=["Kutch", "Jamnagar"],
        historical_cyclones=[
            HistoricalCycloneEvent(
                event_id="biparjoy-2023",
                name="Biparjoy",
                year=2023,
                basin=CycloneBasin.ARABIAN_SEA,
                peak_wind_kt=100.0,
                min_pressure_hpa=968.0,
                landfall_state="Gujarat",
                affected_population=180_000,
                storm_surge_m=3.2,
            ).model_dump(),
        ],
    )


def build_michaung_context() -> dict:
    """Cyclone Michaung (2023) — BoB, Tamil Nadu."""
    return _base_ocean_context(
        region_id="michaung_2023",
        cyclone_name="Michaung",
        latitude=12.5,
        longitude=82.0,
        wind_speed_kt=70.0,
        sea_level_pressure_hpa=990.0,
        max_wind_kt_forecast=75.0,
        forecast_rainfall_24h_mm=250.0,
        forecast_rainfall_72h_mm=550.0,
        rainfall_mm_24h=250.0,
        rainfall_mm_72h=550.0,
        coastal_states=["Tamil Nadu", "Andhra Pradesh"],
        districts=["Chennai", "Tiruvallur", "Nellore"],
        historical_cyclones=[
            HistoricalCycloneEvent(
                event_id="michaung-2023",
                name="Michaung",
                year=2023,
                basin=CycloneBasin.BAY_OF_BENGAL,
                peak_wind_kt=75.0,
                min_pressure_hpa=990.0,
                landfall_state="Tamil Nadu",
                affected_population=2_500_000,
                storm_surge_m=1.8,
            ).model_dump(),
        ],
    )


def build_genesis_context() -> dict:
    """Pre-cyclone genesis scenario — warm SST, low pressure developing."""
    return _base_ocean_context(
        region_id="bob_genesis",
        cyclone_name=None,
        wind_speed_kt=25.0,
        sea_level_pressure_hpa=1004.0,
        sst_c=30.0,
        ocean_heat_content_kj_cm2=85.0,
        landfall_probability=0.15,
        max_wind_kt_forecast=45.0,
        forecast_rainfall_24h_mm=40.0,
        rainfall_mm_24h=40.0,
        historical_cyclones=[],
        track_points=[],
    )


def build_rapid_intensification_context() -> dict:
    """Rapid intensification scenario."""
    ctx = build_fani_context()
    ctx.update({
        "wind_speed_kt": 65.0,
        "max_wind_kt_forecast": 110.0,
        "ocean_heat_content_kj_cm2": 115.0,
        "sst_c": 30.5,
        "cyclone_name": "RI-Test",
    })
    return ctx


def build_climate_state(region_id: str = "odisha_coast") -> ClimateState:
    now = datetime.now(timezone.utc)
    return ClimateState(
        location=GeoLocation(latitude=19.8135, longitude=85.8312, region_id=region_id),
        measurements=[
            ClimateMeasurement(variable=ClimateVariable.TEMPERATURE, value=28.0, unit="C", timestamp=now),
            ClimateMeasurement(variable=ClimateVariable.HUMIDITY, value=88.0, unit="percent", timestamp=now),
            ClimateMeasurement(variable=ClimateVariable.WIND_SPEED, value=38.0, unit="m/s", timestamp=now),
        ],
        scenario_id="cyclone-scenario-01",
    )


class MockCycloneComm(AgentCommunicationInterface):
    async def call_agent(
        self, agent_id: str, request: AgentRequest, *, timeout_seconds: float | None = None,
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
        return AgentResponse(request_id=correlation_id, agent_id="async", content="async")


class MockRLOptimizationService:
    async def optimize(self, request, *, algorithm=None, validate: bool = True) -> DecisionResponse:
        action = request.possible_actions[0] if request.possible_actions else DecisionAction(
            description="Execute coastal evacuation",
            cost=80.0,
            expected_benefit=95.0,
            risk=RiskLevel.MODERATE,
        )
        return DecisionResponse(
            decision_id=request.decision_id,
            agent_id=request.agent_id,
            chosen_action=action,
            confidence=0.85,
            expected_reward=action.expected_benefit - action.cost,
        )


@pytest.fixture
async def memory_manager() -> MemoryManager:
    return await MemoryManager.create_in_memory()


@pytest.fixture
async def graph_engine() -> GraphEngine:
    return await GraphEngine.create(seed_india=True)


@pytest.fixture
async def explanation_engine() -> ExplanationEngine:
    return await ExplanationEngine.create()


@pytest.fixture
async def cyclone_agent(memory_manager: MemoryManager) -> CycloneAgent:
    return await CycloneAgent.create(
        memory_manager,
        agent_communication=MockCycloneComm(),
    )


@pytest.fixture
async def cyclone_agent_full(
    memory_manager: MemoryManager,
    graph_engine: GraphEngine,
    explanation_engine: ExplanationEngine,
) -> CycloneAgent:
    return await CycloneAgent.create(
        memory_manager,
        rl_service=MockRLOptimizationService(),  # type: ignore[arg-type]
        explanation_engine=explanation_engine,
        graph_engine=graph_engine,
        agent_communication=MockCycloneComm(),
    )
