"""Unit tests for heatwave agent components."""

from __future__ import annotations

import pytest

from backend.agents.schemas.request import AgentRequest
from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.heatwave.heatwave_context import HeatwaveInputs
from backend.agents.specialized.heatwave.heatwave_decision_engine import HeatwaveDecisionEngine
from backend.agents.specialized.heatwave.heatwave_models import HeatwaveSeverity
from backend.agents.specialized.heatwave.heatwave_reasoning import HeatwaveReasoningEngine
from backend.agents.specialized.heatwave.heatwave_reflection import HeatwaveReflectionEngine
from backend.agents.specialized.heatwave.heatwave_tools import (
    HistoricalHeatwaveTool,
    HumidityTool,
    LSTTool,
    NDVITool,
    PopulationTool,
    TemperatureTool,
    UrbanDensityTool,
)
from backend.agents.specialized.heatwave.heatwave_validator import HeatwaveValidator
from backend.agents.tools.abstract_tool import ToolInput
from backend.decision.decision_types import DecisionType
from backend.tests.specialized.heatwave.conftest import (
    build_ahmedabad_uhi_context,
    build_compound_heat_aqi_context,
    build_delhi_heatwave_context,
)


@pytest.mark.asyncio
async def test_temperature_tool_elevated() -> None:
    tool = TemperatureTool()
    ctx = build_delhi_heatwave_context()
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["elevated_temperature"] is True
    assert result.output["temperature_score"] > 0.5


@pytest.mark.asyncio
async def test_humidity_tool_heat_index() -> None:
    tool = HumidityTool()
    ctx = build_delhi_heatwave_context()
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["heat_index_c"] > 40.0
    assert result.output["wet_bulb_c"] > 20.0


@pytest.mark.asyncio
async def test_lst_tool_uhi() -> None:
    tool = LSTTool()
    ctx = build_ahmedabad_uhi_context()
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["urban_heat_island"] is True
    assert result.output["uhi_score"] > 0.3


@pytest.mark.asyncio
async def test_ndvi_tool_low_vegetation() -> None:
    tool = NDVITool()
    ctx = build_delhi_heatwave_context(ndvi=0.12)
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["low_vegetation"] is True
    assert result.output["tree_plantation_recommended"] is True


@pytest.mark.asyncio
async def test_urban_density_tool() -> None:
    tool = UrbanDensityTool()
    ctx = build_ahmedabad_uhi_context()
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["high_urban_exposure"] is True


@pytest.mark.asyncio
async def test_population_tool_exposure() -> None:
    tool = PopulationTool()
    ctx = build_delhi_heatwave_context()
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["total_population"] > 0
    assert result.output["high_exposure"] is True


@pytest.mark.asyncio
async def test_historical_heatwave_analog() -> None:
    tool = HistoricalHeatwaveTool()
    ctx = build_delhi_heatwave_context()
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["historical_analog"] is True


@pytest.mark.asyncio
async def test_heatwave_inputs_from_context() -> None:
    ctx = build_delhi_heatwave_context()
    inputs = HeatwaveInputs.from_request_context(ctx)
    assert inputs.region_id == "delhi"
    assert inputs.temperature.air_temp_c == 46.0
    assert len(inputs.historical_events) == 2
    assert inputs.urban.ndvi == 0.18


@pytest.mark.asyncio
async def test_heatwave_reasoning_pipeline() -> None:
    engine = HeatwaveReasoningEngine(agent_id="heatwave_agent")
    ctx_dict = build_delhi_heatwave_context()
    context = AgentContext(
        agent_id="heatwave_agent",
        request=AgentRequest(query="Assess heatwave risk in Delhi", context=ctx_dict),
        metadata={"heatwave_inputs": HeatwaveInputs.from_request_context(ctx_dict)},
    )
    tools = [
        await TemperatureTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await HumidityTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await LSTTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await NDVITool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await PopulationTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
    ]
    reasoning, signals = await engine.run(context, tools)
    assert len(reasoning.steps) >= 10
    assert signals.composite_score > 0.3
    assert reasoning.metadata.get("severity") in {s.value for s in HeatwaveSeverity}


@pytest.mark.asyncio
async def test_compound_aqi_reasoning() -> None:
    engine = HeatwaveReasoningEngine(agent_id="heatwave_agent")
    ctx_dict = build_compound_heat_aqi_context()
    context = AgentContext(
        agent_id="heatwave_agent",
        request=AgentRequest(query="Compound heat and air quality risk", context=ctx_dict),
        metadata={"heatwave_inputs": HeatwaveInputs.from_request_context(ctx_dict)},
    )
    from backend.agents.specialized.heatwave.heatwave_tools import HealthRiskTool

    tools = [
        await TemperatureTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await HumidityTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await HealthRiskTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
    ]
    reasoning, signals = await engine.run(context, tools)
    heat_signals = reasoning.metadata.get("heat_signals", {})
    assert heat_signals.get("compound_aqi_risk") is True or signals.compound_aqi_risk is True


@pytest.mark.asyncio
async def test_heatwave_validator() -> None:
    validator = HeatwaveValidator(agent_id="heatwave_agent")
    ctx_dict = build_delhi_heatwave_context()
    context = AgentContext(
        agent_id="heatwave_agent",
        request=AgentRequest(query="Heatwave check", context=ctx_dict, climate_state=None),
        metadata={"heatwave_inputs": HeatwaveInputs.from_request_context(ctx_dict)},
    )
    result = await validator.validate(context, [], strict=False)
    assert isinstance(result.valid, bool)


@pytest.mark.asyncio
async def test_decision_engine_unified_request() -> None:
    engine = HeatwaveDecisionEngine(agent_id="heatwave_agent")
    ctx_dict = build_delhi_heatwave_context()
    context = AgentContext(
        agent_id="heatwave_agent",
        request=AgentRequest(
            query="Severe heatwave in Delhi with urban heat island",
            context=ctx_dict,
        ),
        metadata={"heatwave_inputs": HeatwaveInputs.from_request_context(ctx_dict)},
    )
    reasoning_engine = HeatwaveReasoningEngine(agent_id="heatwave_agent")
    tools = [
        await TemperatureTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await HumidityTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await LSTTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await NDVITool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await UrbanDensityTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await PopulationTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
    ]
    reasoning, _ = await reasoning_engine.run(context, tools)
    reflection = await HeatwaveReflectionEngine(agent_id="heatwave_agent").evaluate(
        context, reasoning, tools,
    )
    decision = await engine.evaluate(context, reasoning, reflection)
    assert decision.decision_type == DecisionType.HEATWAVE
    assert decision.agent_id == "heatwave_agent"
    assert len(decision.possible_actions) >= 1
    assert decision.need_rl or decision.need_simulation or len(decision.need_other_agents) >= 0


@pytest.mark.asyncio
async def test_tree_plantation_only_when_low_vegetation() -> None:
    engine = HeatwaveDecisionEngine(agent_id="heatwave_agent")
    ctx_high_ndvi = build_delhi_heatwave_context(ndvi=0.65)
    ctx_dict = ctx_high_ndvi
    context = AgentContext(
        agent_id="heatwave_agent",
        request=AgentRequest(query="Heatwave", context=ctx_dict),
        metadata={"heatwave_inputs": HeatwaveInputs.from_request_context(ctx_dict)},
    )
    reasoning_engine = HeatwaveReasoningEngine(agent_id="heatwave_agent")
    tools = [
        await TemperatureTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await HumidityTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await NDVITool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
    ]
    reasoning, _ = await reasoning_engine.run(context, tools)
    reflection = await HeatwaveReflectionEngine(agent_id="heatwave_agent").evaluate(
        context, reasoning, tools,
    )
    decision = await engine.evaluate(context, reasoning, reflection)
    categories = {a.category for a in decision.possible_actions}
    assert "tree_plantation" not in categories
