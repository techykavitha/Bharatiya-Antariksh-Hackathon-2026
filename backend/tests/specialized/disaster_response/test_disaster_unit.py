"""Unit tests for disaster response agent components."""

from __future__ import annotations

import pytest

from backend.agents.schemas.request import AgentRequest
from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.disaster_response.disaster_context import DisasterInputs
from backend.agents.specialized.disaster_response.disaster_models import (
    DISASTER_RESPONSE_AGENT_ID,
    EmergencyPriority,
    HazardType,
)
from backend.agents.specialized.disaster_response.disaster_reasoning import (
    DisasterDecisionEngine,
    DisasterReasoningEngine,
)
from backend.agents.specialized.disaster_response.disaster_tools import (
    ALL_DISASTER_TOOL_NAMES,
    create_disaster_tools,
)
from backend.agents.tools.abstract_tool import ToolInput
from backend.decision.decision_types import DecisionType
from backend.tests.specialized.disaster_response.conftest import (
    build_cyclone_flood_context,
    build_multi_hazard_context,
)


@pytest.mark.asyncio
async def test_disaster_tools_registered() -> None:
    tools = create_disaster_tools()
    names = {t.name for t in tools}
    assert len(names) == 11
    assert names == set(ALL_DISASTER_TOOL_NAMES)


@pytest.mark.asyncio
async def test_emergency_resource_tool() -> None:
    tools = {t.name: t for t in create_disaster_tools()}
    ctx = build_cyclone_flood_context()
    result = await tools["emergency_resource_tool"].run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["food_packets"] > 0
    assert result.output["resource_gap"] is True


@pytest.mark.asyncio
async def test_population_tool_compound() -> None:
    tools = {t.name: t for t in create_disaster_tools()}
    ctx = build_multi_hazard_context()
    result = await tools["population_tool"].run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["total_affected_population"] >= 750_000


@pytest.mark.asyncio
async def test_disaster_inputs_from_context() -> None:
    ctx = build_cyclone_flood_context()
    inputs = DisasterInputs.from_request_context(ctx)
    assert inputs.region_id == "fani_flood_compound"
    assert len(inputs.hazard_agent_outputs) == 2
    assert inputs.hazard_agent_outputs["flood_agent"].hazard_type == HazardType.FLOOD


@pytest.mark.asyncio
async def test_disaster_reasoning_prioritizes_cyclone() -> None:
    ctx_dict = build_cyclone_flood_context()
    request = AgentRequest(query="Coordinate cyclone and flood response", context=ctx_dict)
    context = AgentContext(agent_id=DISASTER_RESPONSE_AGENT_ID, request=request)
    context.metadata["disaster_inputs"] = DisasterInputs.from_request_context(ctx_dict)

    engine = DisasterReasoningEngine(agent_id=DISASTER_RESPONSE_AGENT_ID)
    reasoning, signals = await engine.run(context, tool_results=[])

    rankings = reasoning.metadata.get("priority_rankings", [])
    assert len(rankings) == 2
    assert rankings[0]["hazard_type"] == HazardType.CYCLONE.value
    assert signals.compound_disaster is True
    assert reasoning.overall_confidence > 0


@pytest.mark.asyncio
async def test_disaster_decision_engine_compound() -> None:
    ctx_dict = build_multi_hazard_context()
    request = AgentRequest(query="Multi-hazard emergency plan", context=ctx_dict)
    context = AgentContext(agent_id=DISASTER_RESPONSE_AGENT_ID, request=request)
    context.metadata["disaster_inputs"] = DisasterInputs.from_request_context(ctx_dict)

    reasoning_engine = DisasterReasoningEngine(agent_id=DISASTER_RESPONSE_AGENT_ID)
    reasoning, _ = await reasoning_engine.run(context, tool_results=[])

    decision_engine = DisasterDecisionEngine(agent_id=DISASTER_RESPONSE_AGENT_ID)
    decision = await decision_engine.evaluate(context, reasoning)

    assert decision.decision_type == DecisionType.DISASTER
    assert decision.need_rl is True
    assert len(decision.possible_actions) >= 3
    assert decision.metadata.get("emergency_priority") in (
        EmergencyPriority.HIGH.value,
        EmergencyPriority.SEVERE.value,
        EmergencyPriority.CATASTROPHIC.value,
    )


@pytest.mark.asyncio
async def test_shelter_tool_activation() -> None:
    tools = {t.name: t for t in create_disaster_tools()}
    ctx = build_cyclone_flood_context()
    result = await tools["shelter_tool"].run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["activation_required"] is True
    assert len(result.output["shelters"]) >= 1
