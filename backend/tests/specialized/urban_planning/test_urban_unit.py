"""Unit tests for urban planning agent components."""

from __future__ import annotations

import pytest

from backend.agents.schemas.request import AgentRequest
from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.urban_planning.urban_context import UrbanInputs
from backend.agents.specialized.urban_planning.urban_models import (
    URBAN_PLANNING_AGENT_ID,
    UrbanResilienceLevel,
)
from backend.agents.specialized.urban_planning.urban_reasoning import (
    UrbanDecisionEngine,
    UrbanReasoningEngine,
)
from backend.agents.specialized.urban_planning.urban_tools import ALL_URBAN_TOOL_NAMES, create_urban_tools
from backend.agents.tools.abstract_tool import ToolInput
from backend.decision.decision_types import DecisionType
from backend.tests.specialized.urban_planning.conftest import (
    build_chennai_flooding_context,
    build_delhi_uhi_context,
)


@pytest.mark.asyncio
async def test_urban_tools_registered() -> None:
    tools = create_urban_tools()
    names = {t.name for t in tools}
    assert len(names) == 11
    assert names == set(ALL_URBAN_TOOL_NAMES)


@pytest.mark.asyncio
async def test_drainage_tool_chennai() -> None:
    tools = {t.name: t for t in create_urban_tools()}
    ctx = build_chennai_flooding_context()
    result = await tools["drainage_tool"].run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["drainage_deficit"] is True
    assert result.output["stormwater_upgrade_required"] is True


@pytest.mark.asyncio
async def test_building_tool_delhi_uhi() -> None:
    tools = {t.name: t for t in create_urban_tools()}
    ctx = build_delhi_uhi_context()
    result = await tools["building_tool"].run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["cool_roof_candidate"] is True
    assert result.output["heat_exposure_score"] >= 0.55


@pytest.mark.asyncio
async def test_urban_inputs_from_context() -> None:
    ctx = build_chennai_flooding_context()
    inputs = UrbanInputs.from_request_context(ctx)
    assert inputs.city_name == "Chennai"
    assert inputs.drainage.capacity_score < 0.35
    assert len(inputs.peer_agent_outputs) == 2


@pytest.mark.asyncio
async def test_urban_reasoning_chennai_flood() -> None:
    ctx_dict = build_chennai_flooding_context()
    request = AgentRequest(query="Plan Chennai flood adaptation", context=ctx_dict)
    context = AgentContext(agent_id=URBAN_PLANNING_AGENT_ID, request=request)
    context.metadata["urban_inputs"] = UrbanInputs.from_request_context(ctx_dict)

    engine = UrbanReasoningEngine(agent_id=URBAN_PLANNING_AGENT_ID)
    reasoning, signals = await engine.run(context, tool_results=[])

    assert signals.flood_vulnerability is True
    assert signals.drainage_deficit is True
    assert reasoning.metadata.get("resilience_score", 1.0) < 0.65
    assert len(reasoning.metadata.get("mitigation_options", [])) >= 1


@pytest.mark.asyncio
async def test_urban_decision_engine_delhi() -> None:
    ctx_dict = build_delhi_uhi_context()
    request = AgentRequest(query="Delhi UHI mitigation plan", context=ctx_dict)
    context = AgentContext(agent_id=URBAN_PLANNING_AGENT_ID, request=request)
    context.metadata["urban_inputs"] = UrbanInputs.from_request_context(ctx_dict)

    reasoning_engine = UrbanReasoningEngine(agent_id=URBAN_PLANNING_AGENT_ID)
    reasoning, _ = await reasoning_engine.run(context, tool_results=[])

    decision_engine = UrbanDecisionEngine(agent_id=URBAN_PLANNING_AGENT_ID)
    decision = await decision_engine.evaluate(context, reasoning)

    assert decision.decision_type == DecisionType.URBAN
    assert len(decision.possible_actions) >= 2
    assert float(decision.metadata.get("resilience_score", 1.0)) < 0.8
    assert decision.need_rl is True


@pytest.mark.asyncio
async def test_green_cover_tool() -> None:
    tools = {t.name: t for t in create_urban_tools()}
    ctx = build_delhi_uhi_context()
    result = await tools["green_cover_tool"].run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["low_green_cover"] is True
    assert result.output["canopy_gap_pct"] > 0
