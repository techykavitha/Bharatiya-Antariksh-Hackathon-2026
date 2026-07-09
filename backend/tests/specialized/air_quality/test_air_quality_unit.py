"""Unit tests for air quality agent components."""

from __future__ import annotations

import pytest

from backend.agents.schemas.request import AgentRequest
from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.air_quality.air_quality_context import AirQualityInputs
from backend.agents.specialized.air_quality.air_quality_models import AIR_QUALITY_AGENT_ID
from backend.agents.specialized.air_quality.air_quality_reasoning import (
    AirQualityDecisionEngine,
    AirQualityReasoningEngine,
)
from backend.agents.specialized.air_quality.air_quality_tools import ALL_AIR_QUALITY_TOOL_NAMES, create_air_quality_tools
from backend.agents.tools.abstract_tool import ToolInput
from backend.decision.decision_types import DecisionType
from backend.tests.specialized.air_quality.conftest import (
    build_delhi_severe_pollution_context,
    build_punjab_stubble_burning_context,
    build_rajasthan_dust_storm_context,
)


@pytest.mark.asyncio
async def test_air_quality_tools_registered() -> None:
    tools = create_air_quality_tools()
    names = {t.name for t in tools}
    assert len(names) == 12
    assert names == set(ALL_AIR_QUALITY_TOOL_NAMES)


@pytest.mark.asyncio
async def test_aqi_tool_delhi_severe() -> None:
    tools = {t.name: t for t in create_air_quality_tools()}
    ctx = build_delhi_severe_pollution_context()
    result = await tools["aqi_tool"].run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["aqi"] >= 301
    assert result.output["severe_aqi"] is True
    assert result.output["dominant_pollutant"] in ("pm2_5", "pm10")


@pytest.mark.asyncio
async def test_pm_tool_punjab_stubble() -> None:
    tools = {t.name: t for t in create_air_quality_tools()}
    ctx = build_punjab_stubble_burning_context()
    result = await tools["pm_tool"].run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["biomass_burning_indicator"] is True
    assert result.output["pm2_5_ug_m3"] > 150.0


@pytest.mark.asyncio
async def test_satellite_aerosol_tool_rajasthan_dust() -> None:
    tools = {t.name: t for t in create_air_quality_tools()}
    ctx = build_rajasthan_dust_storm_context()
    result = await tools["satellite_aerosol_tool"].run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["dust_plume_detected"] is True
    assert result.output["high_aod"] is True


@pytest.mark.asyncio
async def test_air_quality_inputs_from_context() -> None:
    ctx = build_delhi_severe_pollution_context()
    inputs = AirQualityInputs.from_request_context(ctx)
    assert inputs.city_name == "Delhi"
    assert inputs.pollutants["pm2_5"] == 285.0
    assert inputs.meteorology.inversion_present is True
    assert len(inputs.peer_agent_outputs) == 1


@pytest.mark.asyncio
async def test_air_quality_reasoning_delhi_severe() -> None:
    ctx_dict = build_delhi_severe_pollution_context()
    request = AgentRequest(query="Assess Delhi severe air pollution", context=ctx_dict)
    context = AgentContext(agent_id=AIR_QUALITY_AGENT_ID, request=request)
    context.metadata["air_quality_inputs"] = AirQualityInputs.from_request_context(ctx_dict)

    engine = AirQualityReasoningEngine(agent_id=AIR_QUALITY_AGENT_ID)
    reasoning, signals = await engine.run(context, tool_results=[])

    assert signals.severe_aqi is True
    assert signals.health_risk_score >= 0.5
    assert int(reasoning.metadata.get("aqi_assessment", {}).get("aqi", 0)) >= 301


@pytest.mark.asyncio
async def test_air_quality_reasoning_rajasthan_dust() -> None:
    ctx_dict = build_rajasthan_dust_storm_context()
    request = AgentRequest(query="Assess Rajasthan dust storm air quality", context=ctx_dict)
    context = AgentContext(agent_id=AIR_QUALITY_AGENT_ID, request=request)
    context.metadata["air_quality_inputs"] = AirQualityInputs.from_request_context(ctx_dict)

    engine = AirQualityReasoningEngine(agent_id=AIR_QUALITY_AGENT_ID)
    reasoning, signals = await engine.run(context, tool_results=[])

    assert signals.dust_storm is True
    assert signals.transport_score >= 0.5


@pytest.mark.asyncio
async def test_air_quality_decision_engine() -> None:
    ctx_dict = build_delhi_severe_pollution_context()
    request = AgentRequest(query="Delhi AQI emergency decision", context=ctx_dict)
    context = AgentContext(agent_id=AIR_QUALITY_AGENT_ID, request=request)
    context.metadata["air_quality_inputs"] = AirQualityInputs.from_request_context(ctx_dict)

    reasoning_engine = AirQualityReasoningEngine(agent_id=AIR_QUALITY_AGENT_ID)
    reasoning, _ = await reasoning_engine.run(context, tool_results=[])

    decision_engine = AirQualityDecisionEngine(agent_id=AIR_QUALITY_AGENT_ID)
    decision = await decision_engine.evaluate(context, reasoning)

    assert decision.decision_type == DecisionType.AQI
    assert len(decision.possible_actions) >= 2
    assert decision.need_rl is True
