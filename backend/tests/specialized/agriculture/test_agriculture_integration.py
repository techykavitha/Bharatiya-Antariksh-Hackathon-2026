"""Integration tests for AgricultureAgent."""

from __future__ import annotations

import pytest

from backend.agents.domain import InfrastructureSupervisor
from backend.agents.schemas.request import AgentRequest
from backend.agents.specialized.agriculture import AGRICULTURE_AGENT_ID, AgricultureAgent
from backend.agents.state.workflow_state import create_initial_workflow_state
from backend.decision.decision_types import DecisionType
from backend.tests.specialized.agriculture.conftest import (
    build_climate_state,
    build_consult_agents_context,
    build_karnataka_drought_context,
    build_maharashtra_cotton_context,
    build_punjab_wheat_context,
    build_tamil_nadu_paddy_context,
)


@pytest.mark.asyncio
async def test_agriculture_agent_punjab_wheat(agriculture_agent: AgricultureAgent) -> None:
    context = build_punjab_wheat_context()
    request = AgentRequest(
        query="Assess Punjab wheat crop health and irrigation needs",
        climate_state=build_climate_state("punjab_wheat"),
        context=context,
    )
    response = await agriculture_agent.invoke(request)
    report = agriculture_agent.last_agriculture_report

    assert response.agent_id == AGRICULTURE_AGENT_ID
    assert response.is_success
    assert report is not None
    assert report.crop_health.crop_type == "wheat"
    assert report.decision_request is not None
    assert report.decision_request.decision_type == DecisionType.AGRICULTURE
    assert len(report.rag_documents) >= 1
    assert report.confidence > 0


@pytest.mark.asyncio
async def test_agriculture_agent_tamil_nadu_paddy(agriculture_agent: AgricultureAgent) -> None:
    context = build_tamil_nadu_paddy_context()
    request = AgentRequest(
        query="Tamil Nadu paddy flood impact and drainage advisory",
        climate_state=build_climate_state("tamil_nadu_paddy"),
        context=context,
    )
    response = await agriculture_agent.invoke(request)
    report = agriculture_agent.last_agriculture_report

    assert response.is_success
    assert report is not None
    assert report.crop_health.crop_type == "paddy"
    assert report.climate_risk.get("flood_impact") or report.climate_risk.get("flood_risk_score", 0) > 0.3
    assert len(report.recommendations) >= 1


@pytest.mark.asyncio
async def test_agriculture_agent_maharashtra_cotton(agriculture_agent: AgricultureAgent) -> None:
    context = build_maharashtra_cotton_context()
    request = AgentRequest(
        query="Maharashtra cotton water stress and irrigation optimization",
        climate_state=build_climate_state("maharashtra_cotton"),
        context=context,
    )
    response = await agriculture_agent.invoke(request)
    report = agriculture_agent.last_agriculture_report

    assert response.is_success
    assert report is not None
    assert report.crop_health.crop_type == "cotton"
    assert report.soil_moisture.irrigation_needed or report.irrigation_recommendation.volume_mm > 0
    assert len(report.evidence) >= 3


@pytest.mark.asyncio
async def test_agriculture_agent_karnataka_drought(agriculture_agent: AgricultureAgent) -> None:
    context = build_karnataka_drought_context()
    request = AgentRequest(
        query="Karnataka drought emergency advisory for millet farmers",
        climate_state=build_climate_state("karnataka_drought"),
        context=context,
    )
    response = await agriculture_agent.invoke(request)
    report = agriculture_agent.last_agriculture_report

    assert response.is_success
    assert report is not None
    assert report.yield_risk.risk_score >= 0.3
    assert report.climate_risk.get("drought_risk") is True
    assert len(report.government_advisory) >= 0 or len(report.rag_documents) >= 1


@pytest.mark.asyncio
async def test_agriculture_agent_with_rl_xai_ckg_rag(agriculture_agent_full: AgricultureAgent) -> None:
    context = build_karnataka_drought_context()
    request = AgentRequest(
        query="Full pipeline agriculture assessment with RL and RAG",
        climate_state=build_climate_state("karnataka_drought"),
        context=context,
    )
    response = await agriculture_agent_full.invoke(request)
    report = agriculture_agent_full.last_agriculture_report
    metrics = report.metrics

    assert response.is_success
    assert report is not None
    assert report.explainability_report is not None
    assert metrics is not None
    assert metrics.rag_retrievals >= 1
    assert metrics.explainability_calls >= 1
    if report.decision_request and report.decision_request.need_rl:
        assert report.rl_response is not None
        assert metrics.rl_calls >= 1


@pytest.mark.asyncio
async def test_agriculture_agent_live_peer_consultation(agriculture_agent_full: AgricultureAgent) -> None:
    context = build_consult_agents_context()
    request = AgentRequest(
        query="Consult water and hazard agents for crop advisory",
        climate_state=build_climate_state("live_ag_consultation"),
        context=context,
    )
    response = await agriculture_agent_full.invoke(request)
    report = agriculture_agent_full.last_agriculture_report
    metrics = report.metrics if report else None

    assert response.is_success
    assert report is not None
    assert metrics is not None
    assert metrics.peer_agents_consulted >= 3


@pytest.mark.asyncio
async def test_agriculture_as_graph_node(agriculture_agent: AgricultureAgent) -> None:
    context = build_punjab_wheat_context()
    request = AgentRequest(
        query="Graph node agriculture test",
        climate_state=build_climate_state("punjab_wheat"),
        context=context,
    )
    await agriculture_agent.invoke(request)
    state = create_initial_workflow_state(
        climate_state=build_climate_state("punjab_wheat"),
        metadata={"query": "Graph node agriculture test", "session_id": "sess-ag"},
    )
    update = await agriculture_agent.as_graph_node(state)
    assert AGRICULTURE_AGENT_ID in update.get("called_agents", [])
    assert "metadata" in update
    assert "crop_type" in update["metadata"]


@pytest.mark.asyncio
async def test_agriculture_infrastructure_supervisor_slot(memory_manager) -> None:
    supervisor = InfrastructureSupervisor(memory=memory_manager)
    await supervisor.initialize()
    slot_ids = [s.agent_id for s in supervisor.agent_slots]
    assert "agriculture_agent" in slot_ids


@pytest.mark.asyncio
async def test_agriculture_report_sections(agriculture_agent: AgricultureAgent) -> None:
    context = build_maharashtra_cotton_context()
    request = AgentRequest(
        query="Verify agriculture report completeness",
        climate_state=build_climate_state("maharashtra_cotton"),
        context=context,
    )
    await agriculture_agent.invoke(request)
    report = agriculture_agent.last_agriculture_report
    assert report is not None
    assert report.executive_summary
    assert report.crop_health
    assert report.soil_moisture
    assert report.yield_risk
    assert report.irrigation_recommendation
    assert report.recommendations
    assert report.confidence > 0
    assert report.evidence
