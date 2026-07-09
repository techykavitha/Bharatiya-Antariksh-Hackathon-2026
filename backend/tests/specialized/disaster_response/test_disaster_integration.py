"""Integration tests for DisasterResponseAgent."""

from __future__ import annotations

import pytest

from backend.agents.domain import EmergencySupervisor
from backend.agents.schemas.request import AgentRequest
from backend.agents.specialized.disaster_response import (
    DISASTER_RESPONSE_AGENT_ID,
    DisasterResponseAgent,
    EmergencyPriority,
)
from backend.agents.state.workflow_state import create_initial_workflow_state
from backend.decision.decision_types import DecisionType
from backend.tests.specialized.disaster_response.conftest import (
    build_climate_state,
    build_consult_agents_context,
    build_cyclone_flood_context,
    build_heatwave_water_stress_context,
    build_multi_hazard_context,
    build_single_flood_context,
)


@pytest.mark.asyncio
async def test_disaster_agent_cyclone_flood_compound(disaster_agent: DisasterResponseAgent) -> None:
    context = build_cyclone_flood_context()
    request = AgentRequest(
        query="Coordinate cyclone and flood emergency response for Odisha coast",
        climate_state=build_climate_state("fani_flood_compound"),
        context=context,
    )
    response = await disaster_agent.invoke(request)
    report = disaster_agent.last_disaster_report

    assert response.agent_id == DISASTER_RESPONSE_AGENT_ID
    assert response.is_success
    assert report is not None
    assert len(report.hazard_overview) == 2
    assert report.metadata.get("compound_disaster") is True
    assert report.emergency_priority in (
        EmergencyPriority.HIGH,
        EmergencyPriority.SEVERE,
        EmergencyPriority.CATASTROPHIC,
    )
    assert report.decision_request is not None
    assert report.decision_request.decision_type == DecisionType.DISASTER
    assert report.affected_population > 0
    assert report.evacuation_strategy.required or len(report.recommendations) > 0


@pytest.mark.asyncio
async def test_disaster_agent_heatwave_water_stress(disaster_agent: DisasterResponseAgent) -> None:
    context = build_heatwave_water_stress_context()
    request = AgentRequest(
        query="Plan response for concurrent heatwave and water stress",
        climate_state=build_climate_state("heatwave_water_stress"),
        context=context,
    )
    response = await disaster_agent.invoke(request)
    report = disaster_agent.last_disaster_report

    assert response.is_success
    assert report is not None
    assert len(report.priority_ranking) == 2
    hazard_types = {h["hazard_type"] for h in report.hazard_overview}
    assert "heatwave" in hazard_types
    assert "water_stress" in hazard_types
    assert report.confidence > 0


@pytest.mark.asyncio
async def test_disaster_agent_multi_hazard_emergency(disaster_agent: DisasterResponseAgent) -> None:
    context = build_multi_hazard_context()
    request = AgentRequest(
        query="Generate multi-hazard emergency response plan",
        climate_state=build_climate_state("multi_hazard_emergency"),
        context=context,
    )
    response = await disaster_agent.invoke(request)
    report = disaster_agent.last_disaster_report

    assert response.is_success
    assert report is not None
    assert len(report.hazard_overview) == 3
    assert report.metadata.get("compound_disaster") is True
    assert len(report.emergency_resources) >= 1
    assert len(report.recovery_priorities) >= 2
    assert len(report.evidence) >= 2


@pytest.mark.asyncio
async def test_disaster_agent_with_rl_xai_ckg(disaster_agent_full: DisasterResponseAgent) -> None:
    context = build_multi_hazard_context()
    request = AgentRequest(
        query="Full pipeline disaster response with RL and explainability",
        climate_state=build_climate_state("multi_hazard_emergency"),
        context=context,
    )
    response = await disaster_agent_full.invoke(request)
    report = disaster_agent_full.last_disaster_report
    metrics = report.metrics

    assert response.is_success
    assert report is not None
    assert report.decision_request is not None
    assert report.explainability_report is not None
    assert metrics is not None
    assert metrics.explainability_calls >= 1
    assert metrics.knowledge_graph_queries >= 0
    if report.decision_request.need_rl:
        assert report.rl_response is not None
        assert metrics.rl_calls >= 1


@pytest.mark.asyncio
async def test_disaster_agent_live_hazard_consultation(disaster_agent_full: DisasterResponseAgent) -> None:
    context = build_consult_agents_context()
    request = AgentRequest(
        query="Consult hazard agents and build response plan",
        climate_state=build_climate_state("live_consultation"),
        context=context,
    )
    response = await disaster_agent_full.invoke(request)
    report = disaster_agent_full.last_disaster_report
    metrics = report.metrics if report else None

    assert response.is_success
    assert report is not None
    assert len(report.hazard_overview) >= 2
    assert metrics is not None
    assert metrics.hazard_agents_consulted >= 2


@pytest.mark.asyncio
async def test_disaster_agent_single_hazard(disaster_agent: DisasterResponseAgent) -> None:
    context = build_single_flood_context()
    request = AgentRequest(
        query="Flood-only emergency response plan",
        climate_state=build_climate_state("chennai_flood"),
        context=context,
    )
    response = await disaster_agent.invoke(request)
    report = disaster_agent.last_disaster_report

    assert response.is_success
    assert report is not None
    assert len(report.hazard_overview) == 1
    assert report.hazard_overview[0]["hazard_type"] == "flood"


@pytest.mark.asyncio
async def test_disaster_as_graph_node(disaster_agent: DisasterResponseAgent) -> None:
    context = build_cyclone_flood_context()
    request = AgentRequest(
        query="Graph node disaster test",
        climate_state=build_climate_state(),
        context=context,
    )
    await disaster_agent.invoke(request)
    state = create_initial_workflow_state(
        climate_state=build_climate_state(),
        metadata={"query": "Graph node disaster test", "session_id": "sess-disaster"},
    )
    update = await disaster_agent.as_graph_node(state)
    assert DISASTER_RESPONSE_AGENT_ID in update.get("called_agents", [])
    assert "metadata" in update
    assert "emergency_priority" in update["metadata"]


@pytest.mark.asyncio
async def test_disaster_emergency_supervisor_slot(memory_manager) -> None:
    supervisor = EmergencySupervisor(memory=memory_manager)
    await supervisor.initialize()
    slot_ids = [s.agent_id for s in supervisor.agent_slots]
    assert "disaster_response_agent" in slot_ids


@pytest.mark.asyncio
async def test_disaster_report_sections(disaster_agent: DisasterResponseAgent) -> None:
    context = build_cyclone_flood_context()
    request = AgentRequest(
        query="Verify disaster report completeness",
        climate_state=build_climate_state("fani_flood_compound"),
        context=context,
    )
    await disaster_agent.invoke(request)
    report = disaster_agent.last_disaster_report
    assert report is not None
    assert report.executive_summary
    assert report.priority_ranking
    assert report.medical_support is not None
    assert report.recovery_priorities
    assert report.recommendations
    assert report.confidence > 0
    assert report.evidence
