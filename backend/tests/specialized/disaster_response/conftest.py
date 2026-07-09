"""Shared fixtures for disaster response agent tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import AgentResponse
from backend.agents.specialized.agent_execution import AgentCommunicationInterface
from backend.agents.specialized.disaster_response import DisasterResponseAgent
from backend.agents.specialized.disaster_response.disaster_models import (
    AGENT_CYCLONE,
    AGENT_FLOOD,
    AGENT_HEATWAVE,
    AGENT_WATER_RESOURCE,
    HazardType,
)
from backend.agents.state.climate_state import ClimateMeasurement, ClimateState, GeoLocation
from backend.decision.decision_actions import DecisionAction
from backend.decision.decision_response import DecisionResponse
from backend.decision.decision_types import RiskLevel
from backend.knowledge_graph.graph_engine import GraphEngine
from backend.utils.enums import AgentStatus, ClimateVariable
from backend.xai import ExplanationEngine


def _base_disaster_context(**overrides: object) -> dict:
    base = {
        "region_id": "odisha_coast",
        "latitude": 19.8135,
        "longitude": 85.8312,
        "districts": ["Puri", "Khordha", "Ganjam"],
        "forecast_available": True,
        "climate_state_available": True,
        "digital_twin_available": True,
        "twin_id": "twin-odisha-emergency-01",
        "digital_twin_state": {
            "twin_id": "twin-odisha-emergency-01",
            "scenario_id": "compound-disaster",
            "layers": {
                "emergency": {"response_status": "activated"},
                "disaster": {"coordination_level": "state"},
            },
        },
        "session_id": "disaster-test-session",
        "population_density": 8000.0,
        "relief_inventory": {
            "food_packets": 50_000,
            "water_litres": 200_000,
            "medical_kits": 2000,
            "generators": 150,
            "vehicles": 80,
        },
        "evacuation_corridors": ["NH-16", "SH-42", "Coastal Highway"],
    }
    base.update(overrides)
    return base


def _flood_hazard(**overrides: object) -> dict:
    data = {
        "hazard_type": HazardType.FLOOD.value,
        "severity": "severe",
        "risk_level": "high",
        "confidence": 0.88,
        "summary": "Severe riverine flooding across coastal districts",
        "affected_regions": ["Puri", "Khordha"],
        "affected_population": 500_000,
        "recommendations": ["Deploy rescue boats", "Evacuate low-lying areas"],
    }
    data.update(overrides)
    return data


def _cyclone_hazard(**overrides: object) -> dict:
    data = {
        "hazard_type": HazardType.CYCLONE.value,
        "severity": "extreme",
        "risk_level": "critical",
        "confidence": 0.92,
        "summary": "Extremely severe cyclonic storm approaching landfall",
        "affected_regions": ["Puri", "Ganjam"],
        "affected_population": 1_200_000,
        "recommendations": ["Coastal evacuation", "Storm surge protection"],
    }
    data.update(overrides)
    return data


def _heatwave_hazard(**overrides: object) -> dict:
    data = {
        "hazard_type": HazardType.HEATWAVE.value,
        "severity": "high",
        "risk_level": "high",
        "confidence": 0.85,
        "summary": "Prolonged heatwave with heat index above 45C",
        "affected_regions": ["Khordha", "Cuttack"],
        "affected_population": 800_000,
        "recommendations": ["Open cooling shelters", "Issue heat advisories"],
    }
    data.update(overrides)
    return data


def _water_stress_hazard(**overrides: object) -> dict:
    data = {
        "hazard_type": HazardType.WATER_STRESS.value,
        "severity": "severe",
        "risk_level": "high",
        "confidence": 0.82,
        "summary": "Reservoir levels critically low; water rationing required",
        "affected_regions": ["Khordha", "Cuttack"],
        "affected_population": 600_000,
        "recommendations": ["Tanker deployment", "Restrict agricultural irrigation"],
    }
    data.update(overrides)
    return data


def build_cyclone_flood_context() -> dict:
    """Compound disaster: Cyclone + Flood."""
    return _base_disaster_context(
        region_id="fani_flood_compound",
        hazard_agent_outputs={
            AGENT_FLOOD: _flood_hazard(),
            AGENT_CYCLONE: _cyclone_hazard(),
        },
    )


def build_heatwave_water_stress_context() -> dict:
    """Compound disaster: Heatwave + Water Stress."""
    return _base_disaster_context(
        region_id="heatwave_water_stress",
        districts=["Khordha", "Cuttack", "Puri"],
        hazard_agent_outputs={
            AGENT_HEATWAVE: _heatwave_hazard(),
            AGENT_WATER_RESOURCE: _water_stress_hazard(),
        },
    )


def build_multi_hazard_context() -> dict:
    """Multi-hazard emergency: Flood + Cyclone + Heatwave."""
    return _base_disaster_context(
        region_id="multi_hazard_emergency",
        hazard_agent_outputs={
            AGENT_FLOOD: _flood_hazard(severity="extreme", affected_population=750_000),
            AGENT_CYCLONE: _cyclone_hazard(severity="extreme"),
            AGENT_HEATWAVE: _heatwave_hazard(severity="moderate", affected_population=300_000),
        },
        relief_inventory={
            "food_packets": 10_000,
            "water_litres": 50_000,
            "medical_kits": 500,
            "generators": 30,
            "vehicles": 20,
        },
    )


def build_single_flood_context() -> dict:
    return _base_disaster_context(
        region_id="chennai_flood",
        hazard_agent_outputs={AGENT_FLOOD: _flood_hazard(affected_population=200_000)},
    )


def build_consult_agents_context() -> dict:
    """Context requiring live hazard agent consultation."""
    return _base_disaster_context(
        region_id="live_consultation",
        consult_agents=[AGENT_FLOOD, AGENT_CYCLONE],
        hazard_agent_outputs={},
    )


def build_climate_state(region_id: str = "odisha_coast") -> ClimateState:
    now = datetime.now(timezone.utc)
    return ClimateState(
        location=GeoLocation(latitude=19.8135, longitude=85.8312, region_id=region_id),
        measurements=[
            ClimateMeasurement(variable=ClimateVariable.TEMPERATURE, value=32.0, unit="C", timestamp=now),
            ClimateMeasurement(variable=ClimateVariable.HUMIDITY, value=85.0, unit="percent", timestamp=now),
            ClimateMeasurement(variable=ClimateVariable.PRECIPITATION, value=120.0, unit="mm", timestamp=now),
        ],
        scenario_id="disaster-scenario-01",
    )


class MockDisasterComm(AgentCommunicationInterface):
    """Mock hazard agent responses for inter-agent communication tests."""

    _RESPONSES: dict[str, dict] = {
        AGENT_FLOOD: _flood_hazard(),
        AGENT_CYCLONE: _cyclone_hazard(),
        AGENT_HEATWAVE: _heatwave_hazard(),
        AGENT_WATER_RESOURCE: _water_stress_hazard(),
    }

    async def call_agent(
        self, agent_id: str, request: AgentRequest, *, timeout_seconds: float | None = None,
    ) -> AgentResponse:
        payload = self._RESPONSES.get(agent_id, {"severity": "moderate", "confidence": 0.6})
        return AgentResponse(
            request_id=request.request_id,
            agent_id=agent_id,
            content=f"Hazard assessment from {agent_id}",
            status=AgentStatus.COMPLETED,
            structured_output={
                **payload,
                "executive_summary": payload.get("summary", ""),
            },
        )

    async def broadcast(self, agent_ids: list[str], request: AgentRequest) -> list[AgentResponse]:
        return [
            await self.call_agent(aid, request) for aid in agent_ids
        ]

    async def wait_for_response(self, correlation_id: str, *, timeout_seconds: float = 120) -> AgentResponse:
        return AgentResponse(request_id=correlation_id, agent_id="async", content="async")


class MockRLOptimizationService:
    async def optimize(self, request, *, algorithm=None, validate: bool = True) -> DecisionResponse:
        action = request.possible_actions[0] if request.possible_actions else DecisionAction(
            description="Deploy emergency relief resources",
            cost=80.0,
            expected_benefit=90.0,
            risk=RiskLevel.MODERATE,
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
async def disaster_agent(memory_manager: MemoryManager) -> DisasterResponseAgent:
    return await DisasterResponseAgent.create(
        memory_manager,
        agent_communication=MockDisasterComm(),
    )


@pytest.fixture
async def disaster_agent_full(
    memory_manager: MemoryManager,
    graph_engine: GraphEngine,
    explanation_engine: ExplanationEngine,
) -> DisasterResponseAgent:
    return await DisasterResponseAgent.create(
        memory_manager,
        rl_service=MockRLOptimizationService(),  # type: ignore[arg-type]
        explanation_engine=explanation_engine,
        graph_engine=graph_engine,
        agent_communication=MockDisasterComm(),
    )
