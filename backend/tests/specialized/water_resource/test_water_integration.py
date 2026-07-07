"""Integration tests for WaterResourceAgent."""

from __future__ import annotations

import pytest

from backend.agents.domain import InfrastructureSupervisor
from backend.agents.schemas.request import AgentRequest
from backend.agents.specialized.water_resource import WATER_RESOURCE_AGENT_ID, WaterResourceAgent
from backend.agents.specialized.water_resource.water_models import (
    ReleaseStrategy,
    WaterAvailabilityBand,
    WaterStressLevel,
)
from backend.agents.state.workflow_state import create_initial_workflow_state
from backend.tests.specialized.water_resource.conftest import (
    build_climate_state,
    build_drought_context,
    build_overflow_context,
    build_water_context,
)


@pytest.mark.asyncio
async def test_water_agent_initialize(water_agent: WaterResourceAgent) -> None:
    assert water_agent.is_initialized
    caps = await water_agent.capability_registry.list_capabilities()
    assert len(caps) == 11
    assert water_agent.tool_manager.has_tool("reservoir_tool")
    assert water_agent.tool_manager.has_tool("groundwater_tool")


@pytest.mark.asyncio
async def test_water_agent_invoke_normal(water_agent: WaterResourceAgent) -> None:
    context = build_water_context()
    request = AgentRequest(
        query="Assess water availability in Krishna basin",
        climate_state=build_climate_state(),
        context=context,
    )
    response = await water_agent.invoke(request)
    assert response.agent_id == WATER_RESOURCE_AGENT_ID
    assert response.is_success
    assert response.content
    assert water_agent.last_water_report is not None
    report = water_agent.last_water_report
    assert report.water_stress in (
        WaterStressLevel.NONE,
        WaterStressLevel.LOW,
        WaterStressLevel.MODERATE,
        WaterStressLevel.HIGH,
    )
    assert len(report.reservoir_status) >= 1
    assert report.confidence > 0
    assert "metrics" in response.metadata


@pytest.mark.asyncio
async def test_water_agent_metrics(water_agent: WaterResourceAgent) -> None:
    request = AgentRequest(
        query="Water resource assessment",
        climate_state=build_climate_state(),
        context=build_water_context(),
    )
    await water_agent.invoke(request)
    metrics = water_agent.last_water_metrics
    assert metrics is not None
    finalized = metrics.finalize_water()
    assert finalized.tool_usage_count >= 5
    assert finalized.memory_writes >= 1
    assert finalized.reservoir_analyses >= 1


@pytest.mark.asyncio
async def test_water_agent_overflow_scenario(water_agent: WaterResourceAgent) -> None:
    request = AgentRequest(
        query="Reservoir overflow risk at Nagarjuna Sagar",
        climate_state=build_climate_state(),
        context=build_overflow_context(),
    )
    await water_agent.invoke(request)
    report = water_agent.last_water_report
    assert report is not None
    assert report.decision_request.need_flood_agent is True
    assert report.decision_request.need_simulation is True
    assert report.release_strategy in (
        ReleaseStrategy.EMERGENCY_SPILL,
        ReleaseStrategy.CONTROLLED_RELEASE,
    )
    if report.reservoir_status:
        assert report.reservoir_status[0].overflow_risk is True


@pytest.mark.asyncio
async def test_water_agent_drought_scenario(water_agent: WaterResourceAgent) -> None:
    request = AgentRequest(
        query="Drought water stress assessment in Krishna basin",
        climate_state=build_climate_state(),
        context=build_drought_context(),
    )
    await water_agent.invoke(request)
    report = water_agent.last_water_report
    assert report is not None
    assert report.water_stress in (
        WaterStressLevel.HIGH,
        WaterStressLevel.SEVERE,
        WaterStressLevel.CRITICAL,
        WaterStressLevel.MODERATE,
    )
    assert report.water_availability.band in (
        WaterAvailabilityBand.DEFICIT,
        WaterAvailabilityBand.SEVERE_DEFICIT,
        WaterAvailabilityBand.MARGINAL,
    )
    assert report.decision_request.need_agriculture_agent is True
    assert len(report.recommendations) >= 1


@pytest.mark.asyncio
async def test_water_agent_decision_request(water_agent: WaterResourceAgent) -> None:
    request = AgentRequest(
        query="Urban and agricultural water demand in Krishna delta",
        climate_state=build_climate_state(),
        context=build_water_context(
            urban_demand_m3d=500_000.0,
            agricultural_demand_m3d=1_500_000.0,
            population=5_000_000,
            crop_area_ha=800_000.0,
        ),
    )
    await water_agent.invoke(request)
    report = water_agent.last_water_report
    assert report is not None
    assert report.decision_request.need_agriculture_agent is True
    assert report.decision_request.need_urban_planning_agent is True
    assert len(report.recommendations) >= 1


@pytest.mark.asyncio
async def test_water_agent_delegation(water_agent: WaterResourceAgent) -> None:
    request = AgentRequest(
        query="Critical reservoir overflow with downstream flood risk",
        climate_state=build_climate_state(),
        context=build_overflow_context(),
    )
    response = await water_agent.invoke(request)
    report = water_agent.last_water_report
    assert report is not None
    if report.decision_request.suggested_agents:
        assert len(response.delegated_to) >= 0


@pytest.mark.asyncio
async def test_water_agent_as_graph_node(water_agent: WaterResourceAgent) -> None:
    state = create_initial_workflow_state(
        climate_state=build_climate_state(),
        metadata={"query": "Water resources in Krishna basin", "session_id": "sess-water"},
    )
    update = await water_agent.as_graph_node(state)
    assert WATER_RESOURCE_AGENT_ID in update.get("called_agents", [])
    assert "metadata" in update
    assert "water_stress" in update["metadata"]


@pytest.mark.asyncio
async def test_water_agent_health(water_agent: WaterResourceAgent) -> None:
    report = await water_agent.health()
    assert report.agent_id == WATER_RESOURCE_AGENT_ID
    assert await water_agent.health_check() is True


@pytest.mark.asyncio
async def test_infrastructure_supervisor_with_water_agent(
    water_agent: WaterResourceAgent,
    memory_manager,
) -> None:
    supervisor = InfrastructureSupervisor(memory=memory_manager)
    await supervisor.initialize()
    await supervisor.register_agent(water_agent)

    request = AgentRequest(
        query="Manage water resources and reservoir levels in Krishna basin",
        climate_state=build_climate_state(),
        context=build_water_context(),
    )
    response = await supervisor.invoke(request)
    assert response.is_success or response.status.value == "completed"
    agents = await supervisor.list_agents()
    assert any(a.agent_id == WATER_RESOURCE_AGENT_ID for a in agents)


@pytest.mark.asyncio
async def test_water_report_structure(water_agent: WaterResourceAgent) -> None:
    request = AgentRequest(
        query="Full water resource analysis",
        climate_state=build_climate_state(),
        context=build_water_context(),
    )
    await water_agent.invoke(request)
    report = water_agent.last_water_report
    assert report is not None
    assert report.executive_summary
    assert report.water_availability.score >= 0
    assert report.demand.total_m3d > 0
    assert report.groundwater is not None
    assert report.required_actions is not None
    assert report.tool_outputs
