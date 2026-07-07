"""Unit tests for water resource agent components."""

from __future__ import annotations

import pytest

from backend.agents.schemas.request import AgentRequest
from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.water_resource.water_context import WaterInputs
from backend.agents.specialized.water_resource.water_decision_engine import WaterDecisionEngine
from backend.agents.specialized.water_resource.water_models import WaterStressLevel
from backend.agents.specialized.water_resource.water_reasoning import WaterReasoningEngine
from backend.agents.specialized.water_resource.water_reflection import WaterReflectionEngine
from backend.agents.specialized.water_resource.water_tools import (
    DemandTool,
    GroundwaterTool,
    RainfallTool,
    ReservoirTool,
    RiverTool,
    SoilMoistureTool,
)
from backend.agents.specialized.water_resource.water_validator import WaterValidator
from backend.agents.tools.abstract_tool import ToolInput
from backend.tests.specialized.water_resource.conftest import (
    build_drought_context,
    build_overflow_context,
    build_water_context,
)


@pytest.mark.asyncio
async def test_reservoir_tool_normal() -> None:
    tool = ReservoirTool()
    ctx = build_water_context(reservoir_level_pct=65.0)
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["status"] == "normal"
    assert result.output["stressed"] is False


@pytest.mark.asyncio
async def test_reservoir_tool_overflow() -> None:
    tool = ReservoirTool()
    ctx = build_overflow_context()
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["overflow_risk"] is True
    assert result.output["status"] == "overflow_risk"


@pytest.mark.asyncio
async def test_river_tool_healthy() -> None:
    tool = RiverTool()
    ctx = build_water_context()
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["river_healthy"] is True


@pytest.mark.asyncio
async def test_groundwater_tool_declining() -> None:
    tool = GroundwaterTool()
    ctx = build_drought_context()
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["declining"] is True
    assert result.output["critical"] is True


@pytest.mark.asyncio
async def test_rainfall_tool_deficit() -> None:
    tool = RainfallTool()
    ctx = build_drought_context()
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["rainfall_deficit"] is True


@pytest.mark.asyncio
async def test_demand_tool_sectors() -> None:
    tool = DemandTool()
    ctx = build_water_context()
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["total_demand_m3d"] > 0
    assert result.output["urban_demand_m3d"] > 0
    assert result.output["agricultural_demand_m3d"] > 0


@pytest.mark.asyncio
async def test_soil_moisture_irrigation_needed() -> None:
    tool = SoilMoistureTool()
    ctx = build_drought_context()
    result = await tool.run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["irrigation_needed"] is True


@pytest.mark.asyncio
async def test_water_inputs_from_context() -> None:
    ctx = build_water_context()
    inputs = WaterInputs.from_request_context(ctx)
    assert inputs.region_id == "krishna_basin"
    assert inputs.reservoir.level_pct == 72.0
    assert len(inputs.historical_records) == 1
    assert inputs.reservoir_available is True


@pytest.mark.asyncio
async def test_water_reasoning_pipeline() -> None:
    engine = WaterReasoningEngine(agent_id="water_resource_agent")
    ctx_dict = build_water_context()
    context = AgentContext(
        agent_id="water_resource_agent",
        request=AgentRequest(query="Assess Krishna basin water resources", context=ctx_dict),
        metadata={"water_inputs": WaterInputs.from_request_context(ctx_dict)},
    )
    tools = [
        await ReservoirTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await RainfallTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await RiverTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await GroundwaterTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await DemandTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
    ]
    reasoning, signals = await engine.run(context, tools)
    assert len(reasoning.steps) >= 9
    assert signals.availability_score > 0.2
    assert reasoning.metadata.get("stress_level") in {s.value for s in WaterStressLevel}


@pytest.mark.asyncio
async def test_water_validator() -> None:
    validator = WaterValidator(agent_id="water_resource_agent")
    ctx_dict = build_water_context()
    context = AgentContext(
        agent_id="water_resource_agent",
        request=AgentRequest(query="Water check", context=ctx_dict, climate_state=None),
        metadata={"water_inputs": WaterInputs.from_request_context(ctx_dict)},
    )
    result = await validator.validate(context, [], strict=False)
    assert isinstance(result.valid, bool)


@pytest.mark.asyncio
async def test_decision_engine_overflow() -> None:
    engine = WaterDecisionEngine(agent_id="water_resource_agent")
    ctx_dict = build_overflow_context()
    context = AgentContext(
        agent_id="water_resource_agent",
        request=AgentRequest(
            query="Reservoir overflow risk in Krishna basin",
            context=ctx_dict,
        ),
        metadata={"water_inputs": WaterInputs.from_request_context(ctx_dict)},
    )
    reasoning_engine = WaterReasoningEngine(agent_id="water_resource_agent")
    tools = [
        await ReservoirTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await RainfallTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await RiverTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
        await DemandTool().run(ToolInput(parameters=ctx_dict, context=ctx_dict)),
    ]
    reasoning, _ = await reasoning_engine.run(context, tools)
    reflection = await WaterReflectionEngine(agent_id="water_resource_agent").evaluate(
        context, reasoning, tools,
    )
    decision = await engine.evaluate(context, reasoning, reflection)
    assert decision.need_flood_agent is True
    assert "flood_agent" in decision.suggested_agents


@pytest.mark.asyncio
async def test_reservoir_tool_validation_error() -> None:
    tool = ReservoirTool()
    with pytest.raises(Exception):
        await tool.run(ToolInput(parameters={}, context={}))


@pytest.mark.asyncio
async def test_groundwater_tool_validation_error() -> None:
    tool = GroundwaterTool()
    with pytest.raises(Exception):
        await tool.run(ToolInput(parameters={"region_id": "x"}, context={}))
