"""Integration tests for UrbanPlanningAgent."""

from __future__ import annotations

import pytest

from backend.agents.domain import InfrastructureSupervisor
from backend.agents.schemas.request import AgentRequest
from backend.agents.specialized.urban_planning import URBAN_PLANNING_AGENT_ID, UrbanPlanningAgent
from backend.agents.state.workflow_state import create_initial_workflow_state
from backend.decision.decision_types import DecisionType
from backend.tests.specialized.urban_planning.conftest import (
    build_bengaluru_green_cover_context,
    build_chennai_flooding_context,
    build_climate_state,
    build_consult_agents_context,
    build_delhi_uhi_context,
    build_hyderabad_drainage_context,
)


@pytest.mark.asyncio
async def test_urban_agent_chennai_flooding(urban_agent: UrbanPlanningAgent) -> None:
    context = build_chennai_flooding_context()
    request = AgentRequest(
        query="Develop long-term flood adaptation plan for Chennai",
        climate_state=build_climate_state("chennai_urban"),
        context=context,
    )
    response = await urban_agent.invoke(request)
    report = urban_agent.last_urban_report

    assert response.agent_id == URBAN_PLANNING_AGENT_ID
    assert response.is_success
    assert report is not None
    assert report.urban_resilience_score < 0.6
    assert len(report.flood_mitigation_opportunities) >= 1
    assert report.decision_request is not None
    assert report.decision_request.decision_type == DecisionType.URBAN
    assert len(report.adaptation_strategy) >= 1


@pytest.mark.asyncio
async def test_urban_agent_delhi_uhi(urban_agent: UrbanPlanningAgent) -> None:
    context = build_delhi_uhi_context()
    request = AgentRequest(
        query="Mitigate Delhi urban heat island effect",
        climate_state=build_climate_state("delhi_uhi"),
        context=context,
    )
    response = await urban_agent.invoke(request)
    report = urban_agent.last_urban_report

    assert response.is_success
    assert report is not None
    assert len(report.heat_mitigation_opportunities) >= 1
    assert report.confidence > 0
    assert report.green_cover_analysis.current_cover_pct < 15.0
    assert report.green_cover_analysis.canopy_gap_pct > 0


@pytest.mark.asyncio
async def test_urban_agent_bengaluru_green_cover(urban_agent: UrbanPlanningAgent) -> None:
    context = build_bengaluru_green_cover_context()
    request = AgentRequest(
        query="Expand green cover and urban forest in Bengaluru",
        climate_state=build_climate_state("bengaluru_green"),
        context=context,
    )
    response = await urban_agent.invoke(request)
    report = urban_agent.last_urban_report

    assert response.is_success
    assert report is not None
    assert report.green_cover_analysis.current_cover_pct >= 20.0
    assert len(report.investment_priorities) >= 1
    assert len(report.recommendations) >= 1


@pytest.mark.asyncio
async def test_urban_agent_hyderabad_drainage(urban_agent: UrbanPlanningAgent) -> None:
    context = build_hyderabad_drainage_context()
    request = AgentRequest(
        query="Upgrade Hyderabad stormwater and drainage infrastructure",
        climate_state=build_climate_state("hyderabad_drainage"),
        context=context,
    )
    response = await urban_agent.invoke(request)
    report = urban_agent.last_urban_report

    assert response.is_success
    assert report is not None
    assert len(report.flood_mitigation_opportunities) >= 1
    assert report.urban_resilience_score > 0
    assert len(report.evidence) >= 2


@pytest.mark.asyncio
async def test_urban_agent_with_rl_xai_ckg(urban_agent_full: UrbanPlanningAgent) -> None:
    context = build_chennai_flooding_context()
    request = AgentRequest(
        query="Full pipeline urban adaptation with RL optimization",
        climate_state=build_climate_state("chennai_urban"),
        context=context,
    )
    response = await urban_agent_full.invoke(request)
    report = urban_agent_full.last_urban_report
    metrics = report.metrics

    assert response.is_success
    assert report is not None
    assert report.explainability_report is not None
    assert metrics is not None
    assert metrics.explainability_calls >= 1
    if report.decision_request and report.decision_request.need_rl:
        assert report.rl_response is not None
        assert metrics.rl_calls >= 1


@pytest.mark.asyncio
async def test_urban_agent_live_peer_consultation(urban_agent_full: UrbanPlanningAgent) -> None:
    context = build_consult_agents_context()
    request = AgentRequest(
        query="Consult hazard agents and build urban adaptation plan",
        climate_state=build_climate_state("live_peer_consultation"),
        context=context,
    )
    response = await urban_agent_full.invoke(request)
    report = urban_agent_full.last_urban_report
    metrics = report.metrics if report else None

    assert response.is_success
    assert report is not None
    assert metrics is not None
    assert metrics.peer_agents_consulted >= 3


@pytest.mark.asyncio
async def test_urban_as_graph_node(urban_agent: UrbanPlanningAgent) -> None:
    context = build_delhi_uhi_context()
    request = AgentRequest(
        query="Graph node urban test",
        climate_state=build_climate_state("delhi_uhi"),
        context=context,
    )
    await urban_agent.invoke(request)
    state = create_initial_workflow_state(
        climate_state=build_climate_state("delhi_uhi"),
        metadata={"query": "Graph node urban test", "session_id": "sess-urban"},
    )
    update = await urban_agent.as_graph_node(state)
    assert URBAN_PLANNING_AGENT_ID in update.get("called_agents", [])
    assert "metadata" in update
    assert "resilience_level" in update["metadata"]


@pytest.mark.asyncio
async def test_urban_infrastructure_supervisor_slot(memory_manager) -> None:
    supervisor = InfrastructureSupervisor(memory=memory_manager)
    await supervisor.initialize()
    slot_ids = [s.agent_id for s in supervisor.agent_slots]
    assert "urban_planning_agent" in slot_ids


@pytest.mark.asyncio
async def test_urban_report_sections(urban_agent: UrbanPlanningAgent) -> None:
    context = build_hyderabad_drainage_context()
    request = AgentRequest(
        query="Verify urban report completeness",
        climate_state=build_climate_state("hyderabad_drainage"),
        context=context,
    )
    await urban_agent.invoke(request)
    report = urban_agent.last_urban_report
    assert report is not None
    assert report.executive_summary
    assert report.adaptation_strategy
    assert report.investment_priorities
    assert report.infrastructure_risk
    assert report.confidence > 0
    assert report.evidence
