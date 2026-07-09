"""Shared fixtures for agriculture agent tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import AgentResponse
from backend.agents.specialized.agent_execution import AgentCommunicationInterface
from backend.agents.specialized.agriculture import AgricultureAgent
from backend.agents.specialized.agriculture.agriculture_models import (
    AGENT_FLOOD,
    AGENT_HEATWAVE,
    AGENT_WATER_RESOURCE,
    CROP_COTTON,
    CROP_PADDY,
    CROP_WHEAT,
)
from backend.agents.specialized.agriculture.agriculture_rag import InMemoryAgricultureRAG, AgricultureRagService
from backend.agents.state.climate_state import ClimateMeasurement, ClimateState, GeoLocation
from backend.decision.decision_actions import DecisionAction
from backend.decision.decision_response import DecisionResponse
from backend.decision.decision_types import RiskLevel
from backend.knowledge_graph.graph_engine import GraphEngine
from backend.utils.enums import AgentStatus, ClimateVariable
from backend.xai import ExplanationEngine


def _base_farm_context(**overrides: object) -> dict:
    base = {
        "forecast_available": True,
        "climate_state_available": True,
        "digital_twin_available": True,
        "land_use": "agricultural",
        "area_hectares": 5000.0,
        "field_capacity_pct": 50.0,
        "session_id": "agriculture-test-session",
        "digital_twin_state": {
            "twin_id": "twin-farm-01",
            "scenario_id": "crop-season",
            "layers": {"agriculture": {"field_status": "active", "irrigation_mode": "canal"}},
        },
    }
    base.update(overrides)
    return base


def _water_peer(**overrides: object) -> dict:
    data = {
        "domain": "water_stress",
        "severity": "moderate",
        "risk_level": "moderate",
        "confidence": 0.82,
        "summary": "Adequate reservoir supply for irrigation",
        "recommendations": ["Monitor reservoir levels"],
    }
    data.update(overrides)
    return data


def _heatwave_peer(**overrides: object) -> dict:
    data = {
        "domain": "heatwave",
        "severity": "high",
        "risk_level": "high",
        "confidence": 0.85,
        "summary": "Heat stress during grain filling",
        "recommendations": ["Irrigate during early morning"],
    }
    data.update(overrides)
    return data


def _flood_peer(**overrides: object) -> dict:
    data = {
        "domain": "flood",
        "severity": "severe",
        "risk_level": "high",
        "confidence": 0.88,
        "summary": "Standing water in low-lying paddy fields",
        "recommendations": ["Drain fields within 48 hours"],
    }
    data.update(overrides)
    return data


def build_punjab_wheat_context() -> dict:
    """Punjab wheat — rabi season, moderate NDVI, heat stress risk."""
    return _base_farm_context(
        region_id="punjab_wheat",
        state="Punjab",
        latitude=30.9010,
        longitude=75.8573,
        districts=["Ludhiana", "Amritsar", "Jalandhar"],
        crop_type=CROP_WHEAT,
        season="rabi",
        ndvi=0.62,
        evi=0.48,
        ndvi_trend=-0.03,
        soil_moisture_pct=38.0,
        groundwater_level_m=12.0,
        temperature_c=28.0,
        max_temp_c=41.0,
        rainfall_mm_7d=5.0,
        rainfall_mm_30d=25.0,
        humidity_pct=45.0,
        forecast_rainfall_7d_mm=8.0,
        day_of_year=90,
        crop_calendar=[
            {"stage": "tillering", "start_day": 60, "end_day": 100, "critical": True},
            {"stage": "flowering", "start_day": 100, "end_day": 130, "critical": True},
            {"stage": "grain_filling", "start_day": 130, "end_day": 160, "critical": True},
        ],
        peer_agent_outputs={AGENT_HEATWAVE: _heatwave_peer(severity="high")},
        twin_id="twin_punjab_wheat",
    )


def build_tamil_nadu_paddy_context() -> dict:
    """Tamil Nadu paddy — kharif, flood risk in delta."""
    return _base_farm_context(
        region_id="tamil_nadu_paddy",
        state="Tamil Nadu",
        latitude=10.7905,
        longitude=78.7047,
        districts=["Thanjavur", "Tiruvarur", "Nagapattinam"],
        crop_type=CROP_PADDY,
        season="kharif",
        ndvi=0.55,
        evi=0.42,
        soil_moisture_pct=72.0,
        temperature_c=32.0,
        max_temp_c=36.0,
        rainfall_mm_7d=180.0,
        rainfall_mm_30d=420.0,
        humidity_pct=88.0,
        forecast_rainfall_7d_mm=120.0,
        day_of_year=280,
        crop_calendar=[
            {"stage": "transplanting", "start_day": 200, "end_day": 230},
            {"stage": "tillering", "start_day": 230, "end_day": 270},
            {"stage": "flowering", "start_day": 270, "end_day": 310, "critical": True},
        ],
        peer_agent_outputs={
            AGENT_FLOOD: _flood_peer(severity="severe"),
            AGENT_WATER_RESOURCE: _water_peer(severity="high"),
        },
        twin_id="twin_tn_paddy",
    )


def build_maharashtra_cotton_context() -> dict:
    """Maharashtra cotton — kharif, water stress during flowering."""
    return _base_farm_context(
        region_id="maharashtra_cotton",
        state="Maharashtra",
        latitude=20.5937,
        longitude=78.9629,
        districts=["Vidarbha", "Yavatmal", "Wardha"],
        crop_type=CROP_COTTON,
        season="kharif",
        ndvi=0.45,
        evi=0.35,
        ndvi_trend=-0.08,
        soil_moisture_pct=28.0,
        groundwater_level_m=25.0,
        temperature_c=34.0,
        max_temp_c=39.0,
        rainfall_mm_7d=15.0,
        rainfall_mm_30d=80.0,
        humidity_pct=70.0,
        forecast_rainfall_7d_mm=10.0,
        day_of_year=250,
        crop_calendar=[
            {"stage": "square_formation", "start_day": 220, "end_day": 260, "critical": True},
            {"stage": "flowering", "start_day": 260, "end_day": 300, "critical": True},
            {"stage": "boll_development", "start_day": 300, "end_day": 340},
        ],
        peer_agent_outputs={
            AGENT_WATER_RESOURCE: _water_peer(severity="severe"),
            AGENT_HEATWAVE: _heatwave_peer(severity="moderate"),
        },
        twin_id="twin_maharashtra_cotton",
    )


def build_karnataka_drought_context() -> dict:
    """Karnataka drought — low soil moisture, millet promotion."""
    return _base_farm_context(
        region_id="karnataka_drought",
        state="Karnataka",
        latitude=12.9716,
        longitude=77.5946,
        districts=["Raichur", "Koppal", "Bellary"],
        crop_type="millet",
        season="kharif",
        ndvi=0.22,
        evi=0.18,
        ndvi_trend=-0.12,
        soil_moisture_pct=18.0,
        groundwater_level_m=35.0,
        temperature_c=36.0,
        max_temp_c=42.0,
        rainfall_mm_7d=2.0,
        rainfall_mm_30d=12.0,
        humidity_pct=40.0,
        forecast_rainfall_7d_mm=3.0,
        day_of_year=200,
        crop_calendar=[
            {"stage": "sowing", "start_day": 170, "end_day": 200},
            {"stage": "vegetative", "start_day": 200, "end_day": 240, "critical": True},
        ],
        peer_agent_outputs={
            AGENT_WATER_RESOURCE: _water_peer(severity="extreme"),
            AGENT_HEATWAVE: _heatwave_peer(severity="severe"),
        },
        twin_id="twin_karnataka_drought",
    )


def build_consult_agents_context() -> dict:
    return _base_farm_context(
        region_id="live_ag_consultation",
        state="Gujarat",
        crop_type=CROP_COTTON,
        season="kharif",
        ndvi=0.4,
        consult_agents=[AGENT_WATER_RESOURCE, AGENT_HEATWAVE, AGENT_FLOOD],
        peer_agent_outputs={},
    )


def build_climate_state(region_id: str = "punjab_wheat") -> ClimateState:
    now = datetime.now(timezone.utc)
    return ClimateState(
        location=GeoLocation(latitude=30.9010, longitude=75.8573, region_id=region_id),
        measurements=[
            ClimateMeasurement(variable=ClimateVariable.TEMPERATURE, value=32.0, unit="C", timestamp=now),
            ClimateMeasurement(variable=ClimateVariable.HUMIDITY, value=55.0, unit="percent", timestamp=now),
            ClimateMeasurement(variable=ClimateVariable.PRECIPITATION, value=5.0, unit="mm", timestamp=now),
        ],
        scenario_id="agriculture-scenario-01",
    )


class MockAgricultureComm(AgentCommunicationInterface):
    _RESPONSES: dict[str, dict] = {
        AGENT_WATER_RESOURCE: _water_peer(),
        AGENT_HEATWAVE: _heatwave_peer(),
        AGENT_FLOOD: _flood_peer(),
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
            description="Increase irrigation frequency",
            cost=20.0,
            expected_benefit=75.0,
            risk=RiskLevel.LOW,
        )
        return DecisionResponse(
            decision_id=request.decision_id,
            agent_id=request.agent_id,
            chosen_action=action,
            confidence=0.87,
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
def rag_service() -> AgricultureRagService:
    return AgricultureRagService(retriever=InMemoryAgricultureRAG())


@pytest.fixture
async def agriculture_agent(memory_manager: MemoryManager, rag_service: AgricultureRagService) -> AgricultureAgent:
    return await AgricultureAgent.create(
        memory_manager,
        rag_service=rag_service,
        agent_communication=MockAgricultureComm(),
    )


@pytest.fixture
async def agriculture_agent_full(
    memory_manager: MemoryManager,
    graph_engine: GraphEngine,
    explanation_engine: ExplanationEngine,
    rag_service: AgricultureRagService,
) -> AgricultureAgent:
    return await AgricultureAgent.create(
        memory_manager,
        rl_service=MockRLOptimizationService(),  # type: ignore[arg-type]
        explanation_engine=explanation_engine,
        graph_engine=graph_engine,
        rag_service=rag_service,
        agent_communication=MockAgricultureComm(),
    )
