"""Shared fixtures for air quality agent tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import AgentResponse
from backend.agents.specialized.agent_execution import AgentCommunicationInterface
from backend.agents.specialized.air_quality import AirQualityAgent
from backend.agents.specialized.air_quality.air_quality_models import (
    AGENT_AGRICULTURE,
    AGENT_CYCLONE,
    AGENT_DISASTER,
    AGENT_HEATWAVE,
    AGENT_URBAN_PLANNING,
)
from backend.agents.state.climate_state import ClimateMeasurement, ClimateState, GeoLocation
from backend.decision.decision_actions import DecisionAction
from backend.decision.decision_response import DecisionResponse
from backend.decision.decision_types import RiskLevel
from backend.knowledge_graph.graph_engine import GraphEngine
from backend.utils.enums import AgentStatus, ClimateVariable
from backend.xai import ExplanationEngine


def _base_aq_context(**overrides: object) -> dict:
    base = {
        "forecast_available": True,
        "climate_state_available": True,
        "digital_twin_available": True,
        "session_id": "air-quality-test-session",
        "digital_twin_state": {
            "twin_id": "twin-aq-01",
            "scenario_id": "pollution-episode",
            "layers": {
                "air_quality": {
                    "status": "active",
                    "hotspots": ["industrial_zone_a"],
                    "emission_sources": ["traffic_corridor_1"],
                },
            },
        },
    }
    base.update(overrides)
    return base


def _heatwave_peer(**overrides: object) -> dict:
    data = {
        "domain": "heatwave",
        "severity": "severe",
        "risk_level": "high",
        "confidence": 0.88,
        "summary": "Heatwave amplifying ozone formation and stagnation",
        "recommendations": ["Avoid outdoor activity during peak heat"],
    }
    data.update(overrides)
    return data


def _urban_peer(**overrides: object) -> dict:
    data = {
        "domain": "urban",
        "severity": "high",
        "risk_level": "high",
        "confidence": 0.82,
        "summary": "Dense urban traffic corridors contributing to NO2 hotspots",
        "recommendations": ["Expand green cover along arterial roads"],
    }
    data.update(overrides)
    return data


def _agriculture_peer(**overrides: object) -> dict:
    data = {
        "domain": "agriculture",
        "severity": "severe",
        "risk_level": "high",
        "confidence": 0.9,
        "summary": "Active stubble burning in upwind agricultural districts",
        "recommendations": ["Deploy biomass management teams"],
    }
    data.update(overrides)
    return data


def _cyclone_peer(**overrides: object) -> dict:
    data = {
        "domain": "cyclone",
        "severity": "moderate",
        "risk_level": "moderate",
        "confidence": 0.75,
        "summary": "Coastal circulation affecting pollutant dispersion",
        "recommendations": ["Monitor post-landfall air quality degradation"],
    }
    data.update(overrides)
    return data


def _disaster_peer(**overrides: object) -> dict:
    data = {
        "domain": "disaster",
        "severity": "high",
        "risk_level": "high",
        "confidence": 0.85,
        "summary": "Public health emergency coordination required",
        "recommendations": ["Activate emergency response protocols"],
    }
    data.update(overrides)
    return data


def build_delhi_severe_pollution_context() -> dict:
    """Delhi winter severe pollution — inversion, high PM, low wind."""
    return _base_aq_context(
        region_id="delhi_severe",
        city_name="Delhi",
        state="Delhi",
        latitude=28.6139,
        longitude=77.2090,
        districts=["Central Delhi", "East Delhi", "Noida"],
        pollutants={"pm2_5": 285.0, "pm10": 420.0, "no2": 95.0, "so2": 28.0, "o3": 45.0, "co": 120.0},
        temperature_c=12.0,
        humidity_pct=78.0,
        wind_speed_ms=0.8,
        wind_direction_deg=270.0,
        mixing_height_m=350.0,
        inversion_present=True,
        forecast_aqi_24h=310,
        forecast_aqi_72h=280,
        forecast_wind_speed_ms=1.2,
        population_total=20_000_000,
        population_density=18000.0,
        sensitive_population_pct=22.0,
        emission_inventory={
            "traffic_share_pct": 38.0,
            "industrial_share_pct": 22.0,
            "biomass_burning_share_pct": 18.0,
            "dust_share_pct": 12.0,
            "construction_share_pct": 10.0,
            "dominant_source": "traffic",
        },
        satellite_aerosol={"aod_550": 0.85, "fire_hotspot_count": 3, "biomass_burning_index": 0.4},
        historical_aqi=[180, 220, 260, 285, 310],
        peer_agent_outputs={AGENT_HEATWAVE: _heatwave_peer()},
        twin_id="twin_delhi_01",
    )


def build_punjab_stubble_burning_context() -> dict:
    """Punjab stubble burning — biomass smoke transport."""
    return _base_aq_context(
        region_id="punjab_stubble",
        city_name="Ludhiana",
        state="Punjab",
        latitude=30.9010,
        longitude=75.8573,
        districts=["Ludhiana", "Amritsar", "Patiala"],
        pollutants={"pm2_5": 195.0, "pm10": 280.0, "no2": 55.0, "so2": 18.0, "o3": 35.0, "co": 80.0},
        temperature_c=22.0,
        humidity_pct=55.0,
        wind_speed_ms=3.5,
        wind_direction_deg=315.0,
        mixing_height_m=800.0,
        inversion_present=False,
        forecast_aqi_24h=210,
        forecast_aqi_72h=175,
        population_total=3_500_000,
        population_density=8500.0,
        emission_inventory={
            "traffic_share_pct": 15.0,
            "industrial_share_pct": 12.0,
            "biomass_burning_share_pct": 55.0,
            "dust_share_pct": 10.0,
            "construction_share_pct": 8.0,
            "dominant_source": "biomass_burning",
        },
        satellite_aerosol={
            "aod_550": 1.1,
            "fire_hotspot_count": 42,
            "smoke_plume_detected": True,
            "biomass_burning_index": 0.82,
        },
        historical_aqi=[120, 150, 180, 195],
        peer_agent_outputs={AGENT_AGRICULTURE: _agriculture_peer()},
        twin_id="twin_punjab_stubble",
    )


def build_rajasthan_dust_storm_context() -> dict:
    """Rajasthan dust storm — coarse PM dominance, high wind transport."""
    return _base_aq_context(
        region_id="rajasthan_dust",
        city_name="Jodhpur",
        state="Rajasthan",
        latitude=26.2389,
        longitude=73.0243,
        districts=["Jodhpur", "Bikaner", "Jaisalmer"],
        pollutants={"pm2_5": 85.0, "pm10": 380.0, "no2": 30.0, "so2": 15.0, "o3": 55.0, "co": 45.0},
        temperature_c=38.0,
        humidity_pct=25.0,
        wind_speed_ms=8.5,
        wind_direction_deg=240.0,
        mixing_height_m=1500.0,
        inversion_present=False,
        forecast_aqi_24h=320,
        forecast_aqi_72h=180,
        population_total=1_200_000,
        population_density=5200.0,
        emission_inventory={
            "traffic_share_pct": 12.0,
            "industrial_share_pct": 8.0,
            "biomass_burning_share_pct": 5.0,
            "dust_share_pct": 65.0,
            "construction_share_pct": 10.0,
            "dominant_source": "dust",
        },
        satellite_aerosol={
            "aod_550": 1.4,
            "fire_hotspot_count": 0,
            "dust_plume_detected": True,
            "biomass_burning_index": 0.1,
        },
        historical_aqi=[90, 110, 150, 280, 380],
        twin_id="twin_rajasthan_dust",
    )


def build_mumbai_coastal_pollution_context() -> dict:
    """Mumbai coastal pollution — industrial + traffic, moderate-high AQI."""
    return _base_aq_context(
        region_id="mumbai_coastal",
        city_name="Mumbai",
        state="Maharashtra",
        latitude=19.0760,
        longitude=72.8777,
        districts=["Mumbai", "Navi Mumbai", "Thane"],
        pollutants={"pm2_5": 145.0, "pm10": 210.0, "no2": 72.0, "so2": 35.0, "o3": 68.0, "co": 95.0},
        temperature_c=32.0,
        humidity_pct=82.0,
        wind_speed_ms=4.2,
        wind_direction_deg=180.0,
        mixing_height_m=900.0,
        inversion_present=False,
        forecast_aqi_24h=160,
        forecast_aqi_72h=140,
        population_total=18_000_000,
        population_density=21000.0,
        emission_inventory={
            "traffic_share_pct": 42.0,
            "industrial_share_pct": 35.0,
            "biomass_burning_share_pct": 3.0,
            "dust_share_pct": 8.0,
            "construction_share_pct": 12.0,
            "dominant_source": "industrial",
        },
        satellite_aerosol={"aod_550": 0.55, "fire_hotspot_count": 1, "biomass_burning_index": 0.15},
        historical_aqi=[110, 125, 140, 145],
        peer_agent_outputs={
            AGENT_URBAN_PLANNING: _urban_peer(),
            AGENT_CYCLONE: _cyclone_peer(),
        },
        twin_id="twin_mumbai_coastal",
    )


def build_consult_agents_context() -> dict:
    return _base_aq_context(
        region_id="live_aq_consultation",
        city_name="Ahmedabad",
        state="Gujarat",
        pollutants={"pm2_5": 180.0, "pm10": 250.0, "no2": 60.0},
        population_total=7_000_000,
        consult_agents=[AGENT_HEATWAVE, AGENT_URBAN_PLANNING, AGENT_AGRICULTURE, AGENT_DISASTER],
        peer_agent_outputs={},
    )


def build_climate_state(region_id: str = "delhi_severe") -> ClimateState:
    now = datetime.now(timezone.utc)
    return ClimateState(
        location=GeoLocation(latitude=28.6139, longitude=77.2090, region_id=region_id),
        measurements=[
            ClimateMeasurement(variable=ClimateVariable.TEMPERATURE, value=12.0, unit="C", timestamp=now),
            ClimateMeasurement(variable=ClimateVariable.HUMIDITY, value=78.0, unit="percent", timestamp=now),
            ClimateMeasurement(variable=ClimateVariable.WIND_SPEED, value=0.8, unit="m/s", timestamp=now),
        ],
        scenario_id="air-quality-scenario-01",
    )


class MockAirQualityComm(AgentCommunicationInterface):
    _RESPONSES: dict[str, dict] = {
        AGENT_HEATWAVE: _heatwave_peer(),
        AGENT_URBAN_PLANNING: _urban_peer(),
        AGENT_AGRICULTURE: _agriculture_peer(),
        AGENT_CYCLONE: _cyclone_peer(),
        AGENT_DISASTER: _disaster_peer(),
    }

    async def call_agent(
        self, agent_id: str, request: AgentRequest, *, timeout_seconds: float | None = None,
    ) -> AgentResponse:
        payload = self._RESPONSES.get(agent_id, {"severity": "moderate", "confidence": 0.65})
        return AgentResponse(
            request_id=request.request_id,
            agent_id=agent_id,
            content=f"Assessment from {agent_id}",
            status=AgentStatus.COMPLETED,
            structured_output={**payload, "executive_summary": payload.get("summary", "")},
        )

    async def broadcast(self, agent_ids: list[str], request: AgentRequest) -> list[AgentResponse]:
        return [await self.call_agent(aid, request) for aid in agent_ids]

    async def wait_for_response(self, correlation_id: str, *, timeout_seconds: float = 120) -> AgentResponse:
        return AgentResponse(request_id=correlation_id, agent_id="async", content="async")


class MockRLOptimizationService:
    async def optimize(self, request, *, algorithm=None, validate: bool = True) -> DecisionResponse:
        action = request.possible_actions[0] if request.possible_actions else DecisionAction(
            description="Issue public health advisory",
            cost=2.0,
            expected_benefit=65.0,
            risk=RiskLevel.NEGLIGIBLE,
        )
        return DecisionResponse(
            decision_id=request.decision_id,
            agent_id=request.agent_id,
            chosen_action=action,
            confidence=0.86,
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
async def air_quality_agent(memory_manager: MemoryManager) -> AirQualityAgent:
    return await AirQualityAgent.create(
        memory_manager,
        agent_communication=MockAirQualityComm(),
    )


@pytest.fixture
async def air_quality_agent_full(
    memory_manager: MemoryManager,
    graph_engine: GraphEngine,
    explanation_engine: ExplanationEngine,
) -> AirQualityAgent:
    return await AirQualityAgent.create(
        memory_manager,
        rl_service=MockRLOptimizationService(),  # type: ignore[arg-type]
        explanation_engine=explanation_engine,
        graph_engine=graph_engine,
        agent_communication=MockAirQualityComm(),
    )
