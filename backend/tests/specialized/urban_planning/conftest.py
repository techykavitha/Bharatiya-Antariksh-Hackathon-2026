"""Shared fixtures for urban planning agent tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import AgentResponse
from backend.agents.specialized.agent_execution import AgentCommunicationInterface
from backend.agents.specialized.urban_planning import UrbanPlanningAgent
from backend.agents.specialized.urban_planning.urban_models import (
    AGENT_FLOOD,
    AGENT_HEATWAVE,
    AGENT_WATER_RESOURCE,
    LandUseCategory,
)
from backend.agents.state.climate_state import ClimateMeasurement, ClimateState, GeoLocation
from backend.decision.decision_actions import DecisionAction
from backend.decision.decision_response import DecisionResponse
from backend.decision.decision_types import RiskLevel
from backend.knowledge_graph.graph_engine import GraphEngine
from backend.utils.enums import AgentStatus, ClimateVariable
from backend.xai import ExplanationEngine


def _base_urban_context(**overrides: object) -> dict:
    base = {
        "forecast_available": True,
        "climate_state_available": True,
        "digital_twin_available": True,
        "planning_horizon_years": 10,
        "adaptation_budget_crores": 150.0,
        "session_id": "urban-test-session",
        "digital_twin_state": {
            "twin_id": "twin-urban-01",
            "scenario_id": "urban-adaptation",
            "layers": {
                "urban": {"planning_mode": "adaptation", "scenario_ready": True},
            },
        },
    }
    base.update(overrides)
    return base


def _flood_peer(**overrides: object) -> dict:
    data = {
        "domain": "flood",
        "severity": "severe",
        "risk_level": "high",
        "confidence": 0.86,
        "summary": "Urban flooding risk in low-lying zones",
        "recommendations": ["Upgrade stormwater systems", "Deploy flood barriers"],
    }
    data.update(overrides)
    return data


def _heatwave_peer(**overrides: object) -> dict:
    data = {
        "domain": "heatwave",
        "severity": "high",
        "risk_level": "high",
        "confidence": 0.84,
        "summary": "Elevated urban heat stress",
        "recommendations": ["Expand cooling infrastructure", "Increase green cover"],
    }
    data.update(overrides)
    return data


def _water_peer(**overrides: object) -> dict:
    data = {
        "domain": "water_stress",
        "severity": "moderate",
        "risk_level": "moderate",
        "confidence": 0.8,
        "summary": "Seasonal water stress affecting supply",
        "recommendations": ["Rainwater harvesting", "Reduce non-essential irrigation"],
    }
    data.update(overrides)
    return data


def build_chennai_flooding_context() -> dict:
    """Chennai urban flooding — high impervious surface, drainage deficit."""
    return _base_urban_context(
        region_id="chennai_urban",
        city_name="Chennai",
        latitude=13.0827,
        longitude=80.2707,
        districts=["Chennai", "Tambaram", "Avadi"],
        ndvi=0.18,
        green_cover_pct=12.0,
        building_density=0.72,
        impervious_surface_pct=78.0,
        population_density=14_000.0,
        land_use={
            "residential_pct": 45.0,
            "commercial_pct": 20.0,
            "industrial_pct": 10.0,
            "green_pct": 12.0,
            "impervious_pct": 78.0,
            "dominant_category": LandUseCategory.MIXED.value,
        },
        drainage={
            "capacity_score": 0.28,
            "detention_volume_m3": 50_000,
            "conveyance_adequacy": "inadequate",
            "flood_prone_zones": ["South Chennai", "Velachery", "Tambaram"],
        },
        peer_agent_outputs={
            AGENT_FLOOD: _flood_peer(severity="extreme"),
            AGENT_WATER_RESOURCE: _water_peer(severity="high"),
        },
        twin_id="twin_chennai_01",
    )


def build_delhi_uhi_context() -> dict:
    """Delhi UHI — extreme heat island, low vegetation."""
    return _base_urban_context(
        region_id="delhi_uhi",
        city_name="Delhi",
        latitude=28.6139,
        longitude=77.2090,
        districts=["Central Delhi", "South Delhi", "East Delhi"],
        ndvi=0.12,
        green_cover_pct=8.0,
        building_density=0.85,
        impervious_surface_pct=82.0,
        population_density=18_000.0,
        lst_c=46.0,
        uhi_intensity_c=6.5,
        land_use={
            "residential_pct": 40.0,
            "commercial_pct": 30.0,
            "industrial_pct": 15.0,
            "green_pct": 8.0,
            "impervious_pct": 82.0,
            "dominant_category": LandUseCategory.MIXED.value,
        },
        drainage={
            "capacity_score": 0.42,
            "conveyance_adequacy": "moderate",
            "flood_prone_zones": ["Yamuna floodplain"],
        },
        peer_agent_outputs={
            AGENT_HEATWAVE: _heatwave_peer(severity="extreme"),
        },
        twin_id="twin_delhi_01",
    )


def build_bengaluru_green_cover_context() -> dict:
    """Bengaluru green cover — moderate vegetation with expansion opportunity."""
    return _base_urban_context(
        region_id="bengaluru_green",
        city_name="Bengaluru",
        latitude=12.9716,
        longitude=77.5946,
        districts=["Bengaluru Urban", "Whitefield", "Electronic City"],
        ndvi=0.35,
        green_cover_pct=22.0,
        building_density=0.58,
        impervious_surface_pct=62.0,
        population_density=11_000.0,
        land_use={
            "residential_pct": 50.0,
            "commercial_pct": 25.0,
            "industrial_pct": 8.0,
            "green_pct": 22.0,
            "impervious_pct": 62.0,
            "dominant_category": LandUseCategory.MIXED.value,
        },
        drainage={
            "capacity_score": 0.55,
            "conveyance_adequacy": "adequate",
            "flood_prone_zones": ["Bellandur", "Outer Ring Road"],
        },
        green_cover_target_pct=33.0,
        peer_agent_outputs={
            AGENT_HEATWAVE: _heatwave_peer(severity="moderate"),
            AGENT_WATER_RESOURCE: _water_peer(),
        },
        twin_id="twin_bengaluru_01",
    )


def build_hyderabad_drainage_context() -> dict:
    """Hyderabad drainage — stormwater capacity deficit."""
    return _base_urban_context(
        region_id="hyderabad_drainage",
        city_name="Hyderabad",
        latitude=17.3850,
        longitude=78.4867,
        districts=["Hyderabad", "Secunderabad", "Cyberabad"],
        ndvi=0.22,
        green_cover_pct=15.0,
        building_density=0.65,
        impervious_surface_pct=70.0,
        population_density=12_500.0,
        land_use={
            "residential_pct": 48.0,
            "commercial_pct": 22.0,
            "industrial_pct": 12.0,
            "green_pct": 15.0,
            "impervious_pct": 70.0,
            "dominant_category": LandUseCategory.MIXED.value,
        },
        drainage={
            "capacity_score": 0.32,
            "detention_volume_m3": 35_000,
            "conveyance_adequacy": "inadequate",
            "flood_prone_zones": ["Hitec City", "Musi River corridor"],
        },
        peer_agent_outputs={
            AGENT_FLOOD: _flood_peer(severity="high"),
            AGENT_WATER_RESOURCE: _water_peer(severity="high"),
        },
        twin_id="twin_hyderabad_01",
    )


def build_consult_agents_context() -> dict:
    return _base_urban_context(
        region_id="live_peer_consultation",
        city_name="Pune",
        latitude=18.5204,
        longitude=73.8567,
        districts=["Pune City"],
        ndvi=0.25,
        green_cover_pct=18.0,
        building_density=0.6,
        consult_agents=[AGENT_HEATWAVE, AGENT_FLOOD, AGENT_WATER_RESOURCE],
        peer_agent_outputs={},
    )


def build_climate_state(region_id: str = "chennai_urban") -> ClimateState:
    now = datetime.now(timezone.utc)
    return ClimateState(
        location=GeoLocation(latitude=13.0827, longitude=80.2707, region_id=region_id),
        measurements=[
            ClimateMeasurement(variable=ClimateVariable.TEMPERATURE, value=34.0, unit="C", timestamp=now),
            ClimateMeasurement(variable=ClimateVariable.HUMIDITY, value=72.0, unit="percent", timestamp=now),
            ClimateMeasurement(variable=ClimateVariable.PRECIPITATION, value=85.0, unit="mm", timestamp=now),
        ],
        scenario_id="urban-planning-scenario-01",
    )


class MockUrbanComm(AgentCommunicationInterface):
    _RESPONSES: dict[str, dict] = {
        AGENT_FLOOD: _flood_peer(),
        AGENT_HEATWAVE: _heatwave_peer(),
        AGENT_WATER_RESOURCE: _water_peer(),
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
            description="Expand urban tree canopy",
            cost=35.0,
            expected_benefit=72.0,
            risk=RiskLevel.LOW,
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
async def urban_agent(memory_manager: MemoryManager) -> UrbanPlanningAgent:
    return await UrbanPlanningAgent.create(
        memory_manager,
        agent_communication=MockUrbanComm(),
    )


@pytest.fixture
async def urban_agent_full(
    memory_manager: MemoryManager,
    graph_engine: GraphEngine,
    explanation_engine: ExplanationEngine,
) -> UrbanPlanningAgent:
    return await UrbanPlanningAgent.create(
        memory_manager,
        rl_service=MockRLOptimizationService(),  # type: ignore[arg-type]
        explanation_engine=explanation_engine,
        graph_engine=graph_engine,
        agent_communication=MockUrbanComm(),
    )
