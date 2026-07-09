"""Integration tests for AirQualityAgent."""

from __future__ import annotations

import pytest

from backend.agents.domain.environmental_supervisor import EnvironmentalSupervisor
from backend.agents.schemas.request import AgentRequest
from backend.agents.specialized.air_quality import AIR_QUALITY_AGENT_ID, AirQualityAgent
from backend.agents.state.workflow_state import create_initial_workflow_state
from backend.decision.decision_types import DecisionType
from backend.tests.specialized.air_quality.conftest import (
    build_climate_state,
    build_consult_agents_context,
    build_delhi_severe_pollution_context,
    build_mumbai_coastal_pollution_context,
    build_punjab_stubble_burning_context,
    build_rajasthan_dust_storm_context,
)


@pytest.mark.asyncio
async def test_air_quality_agent_delhi_severe(air_quality_agent: AirQualityAgent) -> None:
    context = build_delhi_severe_pollution_context()
    request = AgentRequest(
        query="Assess Delhi severe winter air pollution and health risk",
        climate_state=build_climate_state("delhi_severe"),
        context=context,
    )
    response = await air_quality_agent.invoke(request)
    report = air_quality_agent.last_air_quality_report

    assert response.agent_id == AIR_QUALITY_AGENT_ID
    assert response.is_success
    assert report is not None
    assert report.aqi_assessment.aqi >= 301
    assert report.decision_request is not None
    assert report.decision_request.decision_type == DecisionType.AQI
    assert report.confidence > 0


@pytest.mark.asyncio
async def test_air_quality_agent_punjab_stubble(air_quality_agent: AirQualityAgent) -> None:
    context = build_punjab_stubble_burning_context()
    request = AgentRequest(
        query="Punjab stubble burning smoke impact assessment",
        climate_state=build_climate_state("punjab_stubble"),
        context=context,
    )
    response = await air_quality_agent.invoke(request)
    report = air_quality_agent.last_air_quality_report

    assert response.is_success
    assert report is not None
    assert report.climate_risk.get("biomass_burning") is True
    assert len(report.mitigation_strategies) >= 1


@pytest.mark.asyncio
async def test_air_quality_agent_rajasthan_dust(air_quality_agent: AirQualityAgent) -> None:
    context = build_rajasthan_dust_storm_context()
    request = AgentRequest(
        query="Rajasthan dust storm air quality emergency",
        climate_state=build_climate_state("rajasthan_dust"),
        context=context,
    )
    response = await air_quality_agent.invoke(request)
    report = air_quality_agent.last_air_quality_report

    assert response.is_success
    assert report is not None
    assert report.climate_risk.get("dust_storm") is True
    assert report.aqi_assessment.dominant_pollutant.value in ("pm10", "pm2_5")


@pytest.mark.asyncio
async def test_air_quality_agent_mumbai_coastal(air_quality_agent: AirQualityAgent) -> None:
    context = build_mumbai_coastal_pollution_context()
    request = AgentRequest(
        query="Mumbai coastal industrial pollution assessment",
        climate_state=build_climate_state("mumbai_coastal"),
        context=context,
    )
    response = await air_quality_agent.invoke(request)
    report = air_quality_agent.last_air_quality_report

    assert response.is_success
    assert report is not None
    assert report.aqi_assessment.aqi >= 101
    assert report.health_risk.risk_score >= 0.3
    assert len(report.evidence) >= 0


@pytest.mark.asyncio
async def test_air_quality_agent_with_rl_xai_ckg(air_quality_agent_full: AirQualityAgent) -> None:
    context = build_delhi_severe_pollution_context()
    request = AgentRequest(
        query="Full pipeline Delhi air quality with RL optimization",
        climate_state=build_climate_state("delhi_severe"),
        context=context,
    )
    response = await air_quality_agent_full.invoke(request)
    report = air_quality_agent_full.last_air_quality_report
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
async def test_air_quality_agent_live_peer_consultation(air_quality_agent_full: AirQualityAgent) -> None:
    context = build_consult_agents_context()
    request = AgentRequest(
        query="Consult peer agents for compound air quality hazard",
        climate_state=build_climate_state("live_aq_consultation"),
        context=context,
    )
    response = await air_quality_agent_full.invoke(request)
    report = air_quality_agent_full.last_air_quality_report
    metrics = report.metrics

    assert response.is_success
    assert report is not None
    assert metrics is not None
    assert metrics.peer_agents_consulted >= 4


@pytest.mark.asyncio
async def test_air_quality_as_graph_node(air_quality_agent: AirQualityAgent) -> None:
    context = build_delhi_severe_pollution_context()
    request = AgentRequest(
        query="Graph node air quality test",
        climate_state=build_climate_state("delhi_severe"),
        context=context,
    )
    await air_quality_agent.invoke(request)
    state = create_initial_workflow_state(
        climate_state=build_climate_state("delhi_severe"),
        metadata={"query": "Graph node air quality test", "session_id": "sess-aq"},
    )
    update = await air_quality_agent.as_graph_node(state)
    assert AIR_QUALITY_AGENT_ID in update.get("called_agents", [])
    assert "metadata" in update
    assert "aqi" in update["metadata"]
    assert "aqi_category" in update["metadata"]


@pytest.mark.asyncio
async def test_air_quality_environmental_supervisor_slot(memory_manager) -> None:
    supervisor = EnvironmentalSupervisor(memory=memory_manager)
    await supervisor.initialize()
    slot_ids = [s.agent_id for s in supervisor.agent_slots]
    assert "air_quality_agent" in slot_ids


@pytest.mark.asyncio
async def test_air_quality_report_sections(air_quality_agent: AirQualityAgent) -> None:
    context = build_delhi_severe_pollution_context()
    request = AgentRequest(
        query="Verify air quality report completeness",
        climate_state=build_climate_state("delhi_severe"),
        context=context,
    )
    await air_quality_agent.invoke(request)
    report = air_quality_agent.last_air_quality_report
    assert report is not None
    assert report.executive_summary
    assert report.aqi_assessment.aqi >= 301
    assert report.dominant_pollutants
    assert report.forecast
    assert report.population_exposure.exposed_population > 0
    assert report.health_risk.risk_level
    assert report.mitigation_strategies
    assert report.recommendations
    assert report.evidence
