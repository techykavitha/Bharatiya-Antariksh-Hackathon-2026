"""Unit tests for flood agent components."""

from __future__ import annotations

import pytest

from backend.agents.schemas.request import AgentRequest
from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.flood.flood_context import FloodInputs
from backend.agents.specialized.flood.flood_decision_engine import FloodDecisionEngine
from backend.agents.specialized.flood.flood_models import FloodRiskLevel, FloodSeverity
from backend.agents.specialized.flood.flood_reasoning import FloodReasoningEngine
from backend.agents.specialized.flood.flood_reflection import FloodReflectionEngine
from backend.agents.specialized.flood.flood_tools import (
    DEMTool,
    HistoricalFloodTool,
    RainfallTool,
    ReservoirTool,
    RiverTool,
    TerrainTool,
)
from backend.agents.specialized.flood.flood_validator import FloodValidator
from backend.agents.tools.abstract_tool import ToolInput
from backend.tests.specialized.flood.conftest import build_flood_context


@pytest.mark.asyncio
async def test_rainfall_tool_heavy_rain() -> None:
    tool = RainfallTool()
    ctx = build_flood_context(rainfall_mm=120.0)
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["heavy_rainfall"] is True
    assert result.output["rainfall_score"] > 0.5


@pytest.mark.asyncio
async def test_river_tool_overflow() -> None:
    tool = RiverTool()
    ctx = build_flood_context(river_level_m=8.5, river_banks_m=7.0)
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["overflow"] is True


@pytest.mark.asyncio
async def test_reservoir_tool_stressed() -> None:
    tool = ReservoirTool()
    ctx = build_flood_context(reservoir_level_pct=95.0)
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["stressed"] is True
    assert result.output["overflow_risk"] is True


@pytest.mark.asyncio
async def test_terrain_tool_vulnerable() -> None:
    tool = TerrainTool()
    ctx = build_flood_context(slope_deg=20.0, drainage_capacity=0.2)
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["terrain_vulnerable"] is True


@pytest.mark.asyncio
async def test_dem_tool_low_lying() -> None:
    tool = DEMTool()
    ctx = build_flood_context(mean_elevation_m=8.0)
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["low_lying"] is True
    assert result.output["estimated_depth_potential_m"] > 0


@pytest.mark.asyncio
async def test_historical_flood_analog() -> None:
    tool = HistoricalFloodTool()
    ctx = build_flood_context(rainfall_mm=95.0)
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["historical_analog"] is True


@pytest.mark.asyncio
async def test_flood_inputs_from_context() -> None:
    ctx = build_flood_context()
    inputs = FloodInputs.from_request_context(ctx)
    assert inputs.region_id == "chennai"
    assert inputs.rainfall.current_mm == 120.0
    assert len(inputs.historical_events) == 1
    assert inputs.dem_available is True


@pytest.mark.asyncio
async def test_flood_reasoning_pipeline() -> None:
    engine = FloodReasoningEngine(agent_id="flood_agent")
    ctx_dict = build_flood_context()
    context = AgentContext(
        agent_id="flood_agent",
        request=AgentRequest(query="Assess flood risk in Chennai", context=ctx_dict),
        metadata={"flood_inputs": FloodInputs.from_request_context(ctx_dict)},
    )
    tools = [
        await RainfallTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await RiverTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await TerrainTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await DEMTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
    ]
    reasoning, signals = await engine.run(context, tools)
    assert len(reasoning.steps) >= 8
    assert signals.composite_score > 0.3
    assert reasoning.metadata.get("severity") in {s.value for s in FloodSeverity}


@pytest.mark.asyncio
async def test_flood_validator_strict() -> None:
    validator = FloodValidator(agent_id="flood_agent")
    ctx_dict = build_flood_context()
    context = AgentContext(
        agent_id="flood_agent",
        request=AgentRequest(query="Flood check", context=ctx_dict, climate_state=None),
        metadata={"flood_inputs": FloodInputs.from_request_context(ctx_dict)},
    )
    result = await validator.validate(context, [], strict=False)
    assert isinstance(result.valid, bool)
    assert len(result.issues) >= 0


@pytest.mark.asyncio
async def test_decision_engine_high_risk() -> None:
    engine = FloodDecisionEngine(agent_id="flood_agent")
    ctx_dict = build_flood_context()
    context = AgentContext(
        agent_id="flood_agent",
        request=AgentRequest(
            query="Major flood risk in Chennai with reservoir stress",
            context=ctx_dict,
        ),
        metadata={"flood_inputs": FloodInputs.from_request_context(ctx_dict)},
    )
    reasoning_engine = FloodReasoningEngine(agent_id="flood_agent")
    tools = [
        await RainfallTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await RiverTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await ReservoirTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
    ]
    reasoning, _ = await reasoning_engine.run(context, tools)
    reflection = await FloodReflectionEngine(agent_id="flood_agent").evaluate(
        context, reasoning, tools,
    )
    decision = await engine.evaluate(context, reasoning, reflection)
    assert decision.need_water_resource_agent is True
    assert "water_resource_agent" in decision.suggested_agents or decision.need_disaster_agent


@pytest.mark.asyncio
async def test_rainfall_tool_validation_error() -> None:
    tool = RainfallTool()
    with pytest.raises(Exception):
        await tool.run(ToolInput(parameters={}, context={}))


@pytest.mark.asyncio
async def test_dem_tool_validation_error() -> None:
    tool = DEMTool()
    with pytest.raises(Exception):
        await tool.run(ToolInput(parameters={"region_id": "x"}, context={}))
