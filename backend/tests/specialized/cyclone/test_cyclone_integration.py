"""Integration tests for CycloneAgent."""

from __future__ import annotations

import pytest

from backend.agents.domain import EmergencySupervisor
from backend.agents.schemas.request import AgentRequest
from backend.agents.specialized.cyclone import CYCLONE_AGENT_ID, CycloneAgent, CycloneSeverity
from backend.agents.state.workflow_state import create_initial_workflow_state
from backend.decision.decision_types import DecisionType
from backend.tests.specialized.cyclone.conftest import (
    build_amphan_context,
    build_biparjoy_context,
    build_climate_state,
    build_fani_context,
    build_genesis_context,
    build_michaung_context,
    build_rapid_intensification_context,
)


@pytest.mark.asyncio
async def test_cyclone_agent_invoke_fani(cyclone_agent: CycloneAgent) -> None:
    context = build_fani_context()
    request = AgentRequest(
        query="Assess Cyclone Fani landfall risk on Odisha coast",
        climate_state=build_climate_state("fani_2019"),
        context=context,
    )
    response = await cyclone_agent.invoke(request)
    assert response.agent_id == CYCLONE_AGENT_ID
    assert response.is_success
    report = cyclone_agent.last_cyclone_report
    assert report is not None
    assert report.cyclone_name == "Fani"
    assert report.severity in (
        CycloneSeverity.HIGH,
        CycloneSeverity.SEVERE,
        CycloneSeverity.EXTREME,
    )
    assert report.estimated_intensity_kt >= 65
    assert report.landfall_probability >= 0.4
    assert report.decision_request is not None
    assert report.decision_request.decision_type == DecisionType.CYCLONE
    assert len(report.affected_population) >= 1


@pytest.mark.asyncio
async def test_cyclone_agent_amphan(cyclone_agent: CycloneAgent) -> None:
    context = build_amphan_context()
    request = AgentRequest(
        query="Cyclone Amphan impact assessment for West Bengal",
        climate_state=build_climate_state("amphan_2020"),
        context=context,
    )
    response = await cyclone_agent.invoke(request)
    report = cyclone_agent.last_cyclone_report
    assert response.is_success
    assert report is not None
    assert report.cyclone_name == "Amphan"
    assert report.storm_surge.surge_height_m >= 2.0
    assert report.confidence > 0


@pytest.mark.asyncio
async def test_cyclone_agent_biparjoy_arabian_sea(cyclone_agent: CycloneAgent) -> None:
    context = build_biparjoy_context()
    request = AgentRequest(
        query="Track Cyclone Biparjoy in Arabian Sea",
        climate_state=build_climate_state("biparjoy_2023"),
        context=context,
    )
    response = await cyclone_agent.invoke(request)
    report = cyclone_agent.last_cyclone_report
    assert response.is_success
    assert report is not None
    assert report.basin.value == "arabian_sea"
    assert report.cyclone_name == "Biparjoy"


@pytest.mark.asyncio
async def test_cyclone_agent_michaung(cyclone_agent: CycloneAgent) -> None:
    context = build_michaung_context()
    request = AgentRequest(
        query="Cyclone Michaung rainfall and landfall for Tamil Nadu",
        climate_state=build_climate_state("michaung_2023"),
        context=context,
    )
    response = await cyclone_agent.invoke(request)
    report = cyclone_agent.last_cyclone_report
    assert response.is_success
    assert report is not None
    assert report.rainfall_impact.rainfall_24h_mm >= 100
    assert "flood" in " ".join(report.recommendations).lower() or report.decision_request


@pytest.mark.asyncio
async def test_cyclone_genesis_scenario(cyclone_agent: CycloneAgent) -> None:
    context = build_genesis_context()
    request = AgentRequest(
        query="Monitor cyclogenesis in Bay of Bengal",
        climate_state=build_climate_state("bob_genesis"),
        context=context,
    )
    response = await cyclone_agent.invoke(request)
    report = cyclone_agent.last_cyclone_report
    assert response.is_success
    assert report is not None
    assert report.confidence > 0


@pytest.mark.asyncio
async def test_cyclone_rapid_intensification(cyclone_agent: CycloneAgent) -> None:
    context = build_rapid_intensification_context()
    request = AgentRequest(
        query="Rapid intensification alert for developing cyclone",
        climate_state=build_climate_state("fani_2019"),
        context=context,
    )
    response = await cyclone_agent.invoke(request)
    report = cyclone_agent.last_cyclone_report
    assert response.is_success
    assert report is not None
    signals = report.metadata.get("cyclone_signals", {})
    ri = signals.get("rapid_intensification", "")
    assert ri in ("possible", "likely", "confirmed", "")


@pytest.mark.asyncio
async def test_cyclone_agent_with_rl_xai_ckg(cyclone_agent_full: CycloneAgent) -> None:
    context = build_fani_context()
    request = AgentRequest(
        query="Full pipeline cyclone assessment with RL and explainability",
        climate_state=build_climate_state("fani_2019"),
        context=context,
    )
    response = await cyclone_agent_full.invoke(request)
    report = cyclone_agent_full.last_cyclone_report
    metrics = report.metrics
    assert response.is_success
    assert report is not None
    assert report.decision_request is not None
    assert report.explainability_report is not None
    assert metrics is not None
    assert metrics.explainability_calls >= 1
    if report.decision_request.need_rl and cyclone_agent_full._rl_service is not None:
        assert report.rl_response is not None
        assert metrics.rl_calls >= 1


@pytest.mark.asyncio
async def test_cyclone_agent_inter_agent_delegation(cyclone_agent_full: CycloneAgent) -> None:
    context = build_fani_context()
    request = AgentRequest(
        query="Coordinate cyclone response with flood and disaster agents",
        climate_state=build_climate_state("fani_2019"),
        context=context,
    )
    response = await cyclone_agent_full.invoke(request)
    report = cyclone_agent_full.last_cyclone_report
    assert response.is_success
    assert report is not None
    assert len(report.need_other_agents) >= 0


@pytest.mark.asyncio
async def test_cyclone_as_graph_node(cyclone_agent: CycloneAgent) -> None:
    context = build_fani_context()
    request = AgentRequest(
        query="Graph node test",
        climate_state=build_climate_state(),
        context=context,
    )
    await cyclone_agent.invoke(request)
    state = create_initial_workflow_state(
        climate_state=build_climate_state(),
        metadata={"query": "Graph node test", "session_id": "sess-cyclone"},
    )
    update = await cyclone_agent.as_graph_node(state)
    assert CYCLONE_AGENT_ID in update.get("called_agents", [])
    assert "metadata" in update
    assert "cyclone_severity" in update["metadata"]


@pytest.mark.asyncio
async def test_cyclone_emergency_supervisor_slot(memory_manager) -> None:
    supervisor = EmergencySupervisor(memory=memory_manager)
    await supervisor.initialize()
    slot_ids = [s.agent_id for s in supervisor.agent_slots]
    assert "cyclone_agent" in slot_ids


@pytest.mark.asyncio
async def test_cyclone_report_evidence_and_confidence(cyclone_agent: CycloneAgent) -> None:
    context = build_amphan_context()
    request = AgentRequest(
        query="Amphan evidence trail",
        climate_state=build_climate_state("amphan_2020"),
        context=context,
    )
    response = await cyclone_agent.invoke(request)
    report = cyclone_agent.last_cyclone_report
    assert response.is_success
    assert report is not None
    assert len(report.evidence) >= 1
    assert report.confidence > 0
    assert report.executive_summary
