"""Integration tests for HeatwaveAgent."""

from __future__ import annotations

import pytest

from backend.agents.domain import EnvironmentalSupervisor
from backend.agents.schemas.request import AgentRequest
from backend.agents.specialized.heatwave import HEATWAVE_AGENT_ID, HeatwaveAgent
from backend.agents.specialized.heatwave.heatwave_models import HeatRiskLevel, HeatwaveSeverity
from backend.agents.state.workflow_state import create_initial_workflow_state
from backend.decision.decision_types import DecisionType
from backend.tests.specialized.heatwave.conftest import (
    build_ahmedabad_uhi_context,
    build_climate_state,
    build_compound_heat_aqi_context,
    build_delhi_heatwave_context,
    build_mild_heat_context,
)


@pytest.mark.asyncio
async def test_heatwave_agent_initialize(heatwave_agent: HeatwaveAgent) -> None:
    assert heatwave_agent.is_initialized
    caps = await heatwave_agent.capability_registry.list_capabilities()
    assert len(caps) == 10
    assert heatwave_agent.tool_manager.has_tool("temperature_tool")
    assert heatwave_agent.tool_manager.has_tool("humidity_tool")
    assert heatwave_agent.tool_manager.has_tool("health_risk_tool")


@pytest.mark.asyncio
async def test_heatwave_agent_invoke_delhi_extreme(heatwave_agent: HeatwaveAgent) -> None:
    context = build_delhi_heatwave_context()
    request = AgentRequest(
        query="Assess extreme heatwave risk in Delhi during May 2024",
        climate_state=build_climate_state(),
        context=context,
    )
    response = await heatwave_agent.invoke(request)
    assert response.agent_id == HEATWAVE_AGENT_ID
    assert response.is_success
    assert response.content
    assert heatwave_agent.last_heatwave_report is not None
    report = heatwave_agent.last_heatwave_report
    assert report.severity in (
        HeatwaveSeverity.HIGH,
        HeatwaveSeverity.SEVERE,
        HeatwaveSeverity.EXTREME,
        HeatwaveSeverity.MODERATE,
    )
    assert report.heat_index.heat_index_c > 35.0
    assert report.uhi_score > 0
    assert len(report.population_at_risk) >= 1
    assert report.confidence > 0
    assert "metrics" in response.metadata


@pytest.mark.asyncio
async def test_heatwave_agent_ahmedabad_uhi(heatwave_agent: HeatwaveAgent) -> None:
    context = build_ahmedabad_uhi_context()
    request = AgentRequest(
        query="Urban heat island analysis in Ahmedabad",
        climate_state=build_climate_state(region_id="ahmedabad"),
        context=context,
    )
    response = await heatwave_agent.invoke(request)
    report = heatwave_agent.last_heatwave_report
    assert response.is_success
    assert report is not None
    assert report.uhi_score > 0.2
    assert report.decision_request is not None
    assert report.decision_request.decision_type == DecisionType.HEATWAVE


@pytest.mark.asyncio
async def test_heatwave_agent_compound_aqi(heatwave_agent: HeatwaveAgent) -> None:
    context = build_compound_heat_aqi_context()
    request = AgentRequest(
        query="Compound heatwave and air quality emergency in Delhi NCR",
        climate_state=build_climate_state(),
        context=context,
    )
    response = await heatwave_agent.invoke(request)
    report = heatwave_agent.last_heatwave_report
    assert response.is_success
    assert report is not None
    signals = report.metadata.get("signals", {})
    assert signals.get("compound_aqi_risk") is True or report.classification.value == "compound"


@pytest.mark.asyncio
async def test_heatwave_agent_metrics(heatwave_agent: HeatwaveAgent) -> None:
    request = AgentRequest(
        query="Heatwave assessment",
        climate_state=build_climate_state(),
        context=build_delhi_heatwave_context(),
    )
    await heatwave_agent.invoke(request)
    metrics = heatwave_agent.last_heatwave_metrics
    assert metrics is not None
    finalized = metrics.finalize_heatwave()
    assert finalized.tool_usage_count >= 5
    assert finalized.memory_writes >= 1
    assert finalized.decision_requests >= 1


@pytest.mark.asyncio
async def test_heatwave_agent_decision_request(heatwave_agent: HeatwaveAgent) -> None:
    request = AgentRequest(
        query="Severe heatwave with urban heat island in Delhi",
        climate_state=build_climate_state(),
        context=build_delhi_heatwave_context(),
    )
    await heatwave_agent.invoke(request)
    report = heatwave_agent.last_heatwave_report
    assert report is not None
    assert report.decision_request is not None
    assert report.decision_request.decision_type == DecisionType.HEATWAVE
    assert len(report.decision_request.possible_actions) >= 1
    assert len(report.recommendations) >= 1


@pytest.mark.asyncio
async def test_heatwave_agent_rl_integration(heatwave_agent_with_rl: HeatwaveAgent) -> None:
    request = AgentRequest(
        query="Extreme heatwave requiring RL-optimized mitigation in Delhi",
        climate_state=build_climate_state(),
        context=build_delhi_heatwave_context(),
    )
    response = await heatwave_agent_with_rl.invoke(request)
    report = heatwave_agent_with_rl.last_heatwave_report
    assert response.is_success
    assert report is not None
    if report.need_rl:
        assert report.rl_response is not None
        assert report.chosen_mitigation_action is not None
        metrics = heatwave_agent_with_rl.last_heatwave_metrics
        assert metrics is not None
        finalized = metrics.finalize_heatwave()
        assert finalized.rl_calls >= 1


@pytest.mark.asyncio
async def test_heatwave_agent_mild_scenario(heatwave_agent: HeatwaveAgent) -> None:
    request = AgentRequest(
        query="Routine thermal monitoring",
        climate_state=build_climate_state(),
        context=build_mild_heat_context(),
    )
    response = await heatwave_agent.invoke(request)
    report = heatwave_agent.last_heatwave_report
    assert response.is_success
    assert report is not None
    assert report.risk_level in (
        HeatRiskLevel.MINIMAL,
        HeatRiskLevel.LOW,
        HeatRiskLevel.MODERATE,
        HeatRiskLevel.HIGH,
    )


@pytest.mark.asyncio
async def test_heatwave_agent_as_graph_node(heatwave_agent: HeatwaveAgent) -> None:
    state = create_initial_workflow_state(
        climate_state=build_climate_state(),
        metadata={"query": "Heatwave risk in Delhi", "session_id": "sess-heat"},
    )
    update = await heatwave_agent.as_graph_node(state)
    assert HEATWAVE_AGENT_ID in update.get("called_agents", [])
    assert "metadata" in update
    assert "heatwave_risk_level" in update["metadata"]


@pytest.mark.asyncio
async def test_heatwave_agent_health(heatwave_agent: HeatwaveAgent) -> None:
    report = await heatwave_agent.health()
    assert report.agent_id == HEATWAVE_AGENT_ID
    assert await heatwave_agent.health_check() is True


@pytest.mark.asyncio
async def test_environmental_supervisor_with_heatwave_agent(
    heatwave_agent: HeatwaveAgent,
    memory_manager,
) -> None:
    supervisor = EnvironmentalSupervisor(memory=memory_manager)
    await supervisor.initialize()
    await supervisor.register_agent(heatwave_agent)

    request = AgentRequest(
        query="Evaluate heatwave weather risk in Delhi during extreme summer",
        climate_state=build_climate_state(),
        context=build_delhi_heatwave_context(),
    )
    response = await supervisor.invoke(request)
    assert response.is_success or response.status.value == "completed"
    agents = await supervisor.list_agents()
    assert any(a.agent_id == HEATWAVE_AGENT_ID for a in agents)


@pytest.mark.asyncio
async def test_heatwave_report_structure(heatwave_agent: HeatwaveAgent) -> None:
    request = AgentRequest(
        query="Full heatwave analysis",
        climate_state=build_climate_state(),
        context=build_delhi_heatwave_context(),
    )
    await heatwave_agent.invoke(request)
    report = heatwave_agent.last_heatwave_report
    assert report is not None
    assert report.executive_summary
    assert report.heat_index.heat_index_c > 0
    assert report.wet_bulb_c >= 0
    assert report.decision_request is not None
    assert report.references is not None
