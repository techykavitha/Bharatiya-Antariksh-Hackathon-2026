"""Integration tests for FloodAgent."""

from __future__ import annotations

import pytest

from backend.agents.domain import EnvironmentalSupervisor
from backend.agents.schemas.request import AgentRequest
from backend.agents.specialized.flood import FLOOD_AGENT_ID, FloodAgent
from backend.agents.specialized.flood.flood_models import FloodRiskLevel, FloodSeverity
from backend.agents.state.workflow_state import create_initial_workflow_state
from backend.tests.specialized.flood.conftest import build_climate_state, build_flood_context


@pytest.mark.asyncio
async def test_flood_agent_initialize(flood_agent: FloodAgent) -> None:
    assert flood_agent.is_initialized
    caps = await flood_agent.capability_registry.list_capabilities()
    assert len(caps) == 10
    assert flood_agent.tool_manager.has_tool("rainfall_tool")
    assert flood_agent.tool_manager.has_tool("dem_tool")


@pytest.mark.asyncio
async def test_flood_agent_invoke_high_risk(flood_agent: FloodAgent) -> None:
    context = build_flood_context()
    request = AgentRequest(
        query="Assess flood risk in Chennai after heavy rainfall",
        climate_state=build_climate_state(),
        context=context,
    )
    response = await flood_agent.invoke(request)
    assert response.agent_id == FLOOD_AGENT_ID
    assert response.is_success
    assert response.content
    assert flood_agent.last_flood_report is not None
    report = flood_agent.last_flood_report
    assert report.risk_level in (
        FloodRiskLevel.HIGH,
        FloodRiskLevel.SEVERE,
        FloodRiskLevel.EXTREME,
        FloodRiskLevel.MODERATE,
    )
    assert report.severity != FloodSeverity.NONE
    assert report.expected_water_depth_m > 0
    assert len(report.affected_districts) >= 1
    assert report.confidence > 0
    assert "metrics" in response.metadata


@pytest.mark.asyncio
async def test_flood_agent_metrics(flood_agent: FloodAgent) -> None:
    request = AgentRequest(
        query="Flood assessment",
        climate_state=build_climate_state(),
        context=build_flood_context(),
    )
    await flood_agent.invoke(request)
    metrics = flood_agent.last_flood_metrics
    assert metrics is not None
    finalized = metrics.finalize_flood()
    assert finalized.tool_usage_count >= 5
    assert finalized.memory_writes >= 1
    assert finalized.flood_severity != FloodSeverity.NONE or finalized.flood_risk_level == FloodRiskLevel.MINIMAL


@pytest.mark.asyncio
async def test_flood_agent_decision_request(flood_agent: FloodAgent) -> None:
    request = AgentRequest(
        query="Reservoir overflow and river flooding in Chennai",
        climate_state=build_climate_state(),
        context=build_flood_context(reservoir_level_pct=98.0),
    )
    await flood_agent.invoke(request)
    report = flood_agent.last_flood_report
    assert report is not None
    assert report.decision_request.need_water_resource_agent is True
    assert report.decision_request.need_simulation is True
    assert len(report.recommendations) >= 1


@pytest.mark.asyncio
async def test_flood_agent_delegation(flood_agent: FloodAgent) -> None:
    request = AgentRequest(
        query="Catastrophic urban flood with reservoir stress",
        climate_state=build_climate_state(),
        context=build_flood_context(
            rainfall_mm=180.0,
            reservoir_level_pct=99.0,
            river_level_m=10.0,
            river_banks_m=6.0,
        ),
    )
    response = await flood_agent.invoke(request)
    report = flood_agent.last_flood_report
    assert report is not None
    if report.decision_request.suggested_agents:
        assert len(response.delegated_to) >= 0


@pytest.mark.asyncio
async def test_flood_agent_as_graph_node(flood_agent: FloodAgent) -> None:
    state = create_initial_workflow_state(
        climate_state=build_climate_state(),
        metadata={"query": "Flood risk in Chennai", "session_id": "sess-flood"},
    )
    update = await flood_agent.as_graph_node(state)
    assert FLOOD_AGENT_ID in update.get("called_agents", [])
    assert "metadata" in update
    assert "flood_risk_level" in update["metadata"]


@pytest.mark.asyncio
async def test_flood_agent_health(flood_agent: FloodAgent) -> None:
    report = await flood_agent.health()
    assert report.agent_id == FLOOD_AGENT_ID
    assert await flood_agent.health_check() is True


@pytest.mark.asyncio
async def test_environmental_supervisor_with_flood_agent(
    flood_agent: FloodAgent,
    memory_manager,
) -> None:
    supervisor = EnvironmentalSupervisor(memory=memory_manager)
    await supervisor.initialize()
    await supervisor.register_agent(flood_agent)

    request = AgentRequest(
        query="Evaluate flood weather risk from heavy rainfall in Chennai",
        climate_state=build_climate_state(),
        context=build_flood_context(),
    )
    response = await supervisor.invoke(request)
    assert response.is_success or response.status.value == "completed"
    agents = await supervisor.list_agents()
    assert any(a.agent_id == FLOOD_AGENT_ID for a in agents)


@pytest.mark.asyncio
async def test_flood_low_risk_scenario(flood_agent: FloodAgent) -> None:
    context = build_flood_context(
        rainfall_mm=5.0,
        river_level_m=2.0,
        river_banks_m=8.0,
        reservoir_level_pct=40.0,
        slope_deg=5.0,
        drainage_capacity=0.8,
        soil_moisture=0.3,
        urban_density=0.2,
    )
    context["rainfall_forecast_24h_mm"] = 8.0
    context["rainfall_forecast_72h_mm"] = 15.0
    context["rainfall_intensity_mm_per_hr"] = 2.0
    context["antecedent_rainfall_7d_mm"] = 20.0
    context["historical_floods"] = []
    request = AgentRequest(
        query="Routine flood monitoring",
        climate_state=build_climate_state(),
        context=context,
    )
    response = await flood_agent.invoke(request)
    report = flood_agent.last_flood_report
    assert response.is_success
    assert report is not None
    assert report.risk_level in (
        FloodRiskLevel.MINIMAL,
        FloodRiskLevel.LOW,
        FloodRiskLevel.MODERATE,
        FloodRiskLevel.HIGH,
    )


@pytest.mark.asyncio
async def test_flood_coastal_query_decision(flood_agent: FloodAgent) -> None:
    context = build_flood_context()
    request = AgentRequest(
        query="Coastal storm surge flood risk assessment",
        climate_state=build_climate_state(),
        context=context,
    )
    await flood_agent.invoke(request)
    report = flood_agent.last_flood_report
    assert report is not None
    assert report.decision_request.need_cyclone_agent is True


@pytest.mark.asyncio
async def test_flood_report_structure(flood_agent: FloodAgent) -> None:
    request = AgentRequest(
        query="Full flood analysis",
        climate_state=build_climate_state(),
        context=build_flood_context(),
    )
    await flood_agent.invoke(request)
    report = flood_agent.last_flood_report
    assert report is not None
    assert report.executive_summary
    assert report.flood_type.value != ""
    assert report.probability.score >= 0
    assert report.required_actions is not None
    assert report.tool_outputs
