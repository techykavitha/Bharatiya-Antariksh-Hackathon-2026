"""Tests for BaseDomainSupervisor and concrete domain supervisors."""

import pytest

from backend.agents.domain import (
    DomainType,
    EmergencySupervisor,
    EnvironmentalSupervisor,
    InfrastructureSupervisor,
)
from backend.agents.schemas.request import AgentRequest
from backend.agents.state.workflow_state import create_initial_workflow_state
from backend.tests.domain.conftest import MockSpecializedAgent
from backend.utils.enums import AgentStatus


@pytest.mark.asyncio
async def test_environmental_initialize(memory_manager) -> None:
    supervisor = EnvironmentalSupervisor(memory=memory_manager)
    await supervisor.initialize()
    assert supervisor.is_initialized
    agents = await supervisor.list_agents()
    assert len(agents) == 3


@pytest.mark.asyncio
async def test_select_agents_flood_query(memory_manager) -> None:
    supervisor = EnvironmentalSupervisor(memory=memory_manager)
    await supervisor.initialize()
    request = AgentRequest(query="Assess flood weather risk in Chennai")
    selection = await supervisor.select_agents(request)
    assert selection.domain == DomainType.ENVIRONMENTAL
    assert "flood_agent" in selection.selected_agents


@pytest.mark.asyncio
async def test_execute_with_registered_agents(memory_manager) -> None:
    supervisor = EnvironmentalSupervisor(memory=memory_manager)
    await supervisor.initialize()
    await supervisor.register_agent(MockSpecializedAgent("flood_agent"))
    await supervisor.register_agent(MockSpecializedAgent("heatwave_agent"))

    request = AgentRequest(query="Weather risk from heavy rainfall")
    result = await supervisor.execute(request)
    assert len(result.agent_results) >= 1
    assert result.completed_agents


@pytest.mark.asyncio
async def test_merge_results(memory_manager) -> None:
    supervisor = InfrastructureSupervisor(memory=memory_manager)
    await supervisor.initialize()
    await supervisor.register_agent(MockSpecializedAgent("agriculture_agent"))
    request = AgentRequest(query="Analyze crop yield for Karnataka farms")
    execution = await supervisor.execute(request)
    merged = await supervisor.merge_results(execution)
    assert merged.domain == DomainType.INFRASTRUCTURE


@pytest.mark.asyncio
async def test_invoke_entry_point(memory_manager) -> None:
    supervisor = EmergencySupervisor(memory=memory_manager)
    await supervisor.initialize()
    await supervisor.register_agent(MockSpecializedAgent("cyclone_agent"))
    request = AgentRequest(query="Monitor cyclone track in Bay of Bengal")
    response = await supervisor.invoke(request)
    assert response.agent_id == "emergency_supervisor"
    assert response.status in (AgentStatus.COMPLETED, AgentStatus.FAILED)


@pytest.mark.asyncio
async def test_as_graph_node(memory_manager) -> None:
    supervisor = EnvironmentalSupervisor(memory=memory_manager)
    await supervisor.initialize()
    await supervisor.register_agent(MockSpecializedAgent("air_quality_agent"))
    state = create_initial_workflow_state(metadata={"query": "Monitor air quality in Delhi"})
    update = await supervisor.as_graph_node(state)
    assert "metadata" in update
    assert update["metadata"]["active_domain"] == "environmental_supervisor"


@pytest.mark.asyncio
async def test_update_memory(memory_manager) -> None:
    supervisor = EnvironmentalSupervisor(memory=memory_manager)
    await supervisor.initialize()
    await supervisor.register_agent(MockSpecializedAgent("flood_agent"))
    request = AgentRequest(query="Flood risk assessment")
    execution = await supervisor.execute(request)
    merged = await supervisor.merge_results(execution)
    refs = await supervisor.update_memory(request, merged, session_id="sess-1")
    assert len(refs) >= 1


@pytest.mark.asyncio
async def test_health_report(memory_manager) -> None:
    supervisor = InfrastructureSupervisor(memory=memory_manager)
    await supervisor.initialize()
    report = await supervisor.health()
    assert report.supervisor_id == "infrastructure_supervisor"
    assert report.healthy is True


@pytest.mark.asyncio
async def test_unregister_agent(memory_manager) -> None:
    supervisor = EmergencySupervisor(memory=memory_manager)
    await supervisor.initialize()
    await supervisor.register_agent(MockSpecializedAgent("disaster_response_agent"))
    assert await supervisor.unregister_agent("disaster_response_agent") is True
