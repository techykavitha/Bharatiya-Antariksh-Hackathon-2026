"""Unit tests for Cyclone Agent components."""

from __future__ import annotations

import pytest

from backend.agents.schemas.request import AgentRequest
from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.cyclone.cyclone_context import CycloneInputs
from backend.agents.specialized.cyclone import (
    CYCLONE_AGENT_ID,
    CycloneAgent,
    CycloneBasin,
    CycloneCategory,
    CycloneDecisionEngine,
    CycloneReasoningEngine,
    CycloneReflectionEngine,
    CycloneSeverity,
    CycloneValidator,
    create_cyclone_tools,
)
from backend.agents.tools.abstract_tool import ToolInput
from backend.decision.decision_types import DecisionType
from backend.tests.specialized.cyclone.conftest import (
    build_amphan_context,
    build_fani_context,
    build_genesis_context,
    build_rapid_intensification_context,
)


@pytest.mark.asyncio
async def test_cyclone_tools_count() -> None:
    tools = create_cyclone_tools()
    assert len(tools) == 12
    names = {t.name for t in tools}
    assert "sst_tool" in names
    assert "storm_surge_tool" in names
    assert "knowledge_graph_tool" in names


@pytest.mark.asyncio
async def test_sst_tool_execution() -> None:
    tools = {t.name: t for t in create_cyclone_tools()}
    result = await tools["sst_tool"].run(ToolInput(parameters=build_genesis_context()))
    assert result.success
    assert result.output["warm_sst"] is True
    assert result.output["genesis_favorable"] is True


@pytest.mark.asyncio
async def test_wind_tool_classifies_category() -> None:
    tools = {t.name: t for t in create_cyclone_tools()}
    ctx = build_fani_context()
    result = await tools["wind_tool"].run(ToolInput(parameters=ctx))
    assert result.success
    assert result.output["wind_speed_kt"] >= 100
    assert result.output["category"] in (
        CycloneCategory.EXTREMELY_SEVERE_CYCLONIC_STORM.value,
        CycloneCategory.SUPER_CYCLONIC_STORM.value,
        CycloneCategory.VERY_SEVERE_CYCLONIC_STORM.value,
    )


@pytest.mark.asyncio
async def test_storm_surge_tool_high_surge_for_major_cyclone() -> None:
    tools = {t.name: t for t in create_cyclone_tools()}
    result = await tools["storm_surge_tool"].run(ToolInput(parameters=build_amphan_context()))
    assert result.success
    assert result.output["surge_height_m"] >= 2.0


@pytest.mark.asyncio
async def test_historical_cyclone_tool_finds_analog() -> None:
    tools = {t.name: t for t in create_cyclone_tools()}
    result = await tools["historical_cyclone_tool"].run(ToolInput(parameters=build_fani_context()))
    assert result.success
    assert result.output["historical_analog"] is True
    assert result.output["historical_analog_count"] >= 1


@pytest.mark.asyncio
async def test_cyclone_inputs_from_context() -> None:
    inputs = CycloneInputs.from_request_context(build_fani_context())
    assert inputs.cyclone_name == "Fani"
    assert inputs.basin == CycloneBasin.BAY_OF_BENGAL
    assert inputs.ocean.wind_speed_kt == 115.0
    assert len(inputs.historical_events) == 1


@pytest.mark.asyncio
async def test_cyclone_reasoning_severe_for_fani(memory_manager) -> None:
    engine = CycloneReasoningEngine(agent_id=CYCLONE_AGENT_ID)
    ctx_dict = build_fani_context()
    request = AgentRequest(query="Assess Fani", context=ctx_dict)
    context = AgentContext(
        agent_id=CYCLONE_AGENT_ID,
        request=request,
        metadata={"cyclone_inputs": CycloneInputs.from_request_context(ctx_dict)},
    )

    tools = {t.name: t for t in create_cyclone_tools()}
    tool_results = []
    for tool in tools.values():
        tool_results.append(await tool.run(ToolInput(parameters=ctx_dict, context=ctx_dict)))

    reasoning, signals = await engine.run(context, tool_results)
    assert reasoning.overall_confidence > 0
    assert signals.cyclone_detected is True
    severity = CycloneSeverity(reasoning.metadata["severity"])
    assert severity in (CycloneSeverity.HIGH, CycloneSeverity.SEVERE, CycloneSeverity.EXTREME)


@pytest.mark.asyncio
async def test_cyclone_reasoning_genesis_scenario(memory_manager) -> None:
    engine = CycloneReasoningEngine(agent_id=CYCLONE_AGENT_ID)
    ctx_dict = build_genesis_context()
    request = AgentRequest(query="Monitor genesis", context=ctx_dict)
    context = AgentContext(
        agent_id=CYCLONE_AGENT_ID,
        request=request,
        metadata={"cyclone_inputs": CycloneInputs.from_request_context(ctx_dict)},
    )

    tools = {t.name: t for t in create_cyclone_tools()}
    tool_results = []
    for tool in tools.values():
        try:
            tool_results.append(await tool.run(ToolInput(parameters=ctx_dict, context=ctx_dict)))
        except Exception:
            pass

    reasoning, signals = await engine.run(context, tool_results)
    assert signals.favorable_genesis or signals.genesis_likely or signals.warm_sst


@pytest.mark.asyncio
async def test_cyclone_reflection_suggests_flood_agent(memory_manager) -> None:
    reflection_engine = CycloneReflectionEngine(agent_id=CYCLONE_AGENT_ID)
    reasoning_engine = CycloneReasoningEngine(agent_id=CYCLONE_AGENT_ID)
    ctx_dict = build_fani_context()
    request = AgentRequest(query="Fani landfall", context=ctx_dict)
    context = AgentContext(
        agent_id=CYCLONE_AGENT_ID,
        request=request,
        metadata={"cyclone_inputs": CycloneInputs.from_request_context(ctx_dict)},
    )

    tools = {t.name: t for t in create_cyclone_tools()}
    tool_results = [
        await t.run(ToolInput(parameters=ctx_dict, context=ctx_dict)) for t in tools.values()
    ]
    reasoning, _ = await reasoning_engine.run(context, tool_results)
    reflection = await reflection_engine.evaluate(context, reasoning, tool_results)
    assert "flood_agent" in reflection.suggested_agents or reflection.needs_another_agent


@pytest.mark.asyncio
async def test_cyclone_decision_engine_unified_request(memory_manager) -> None:
    decision_engine = CycloneDecisionEngine()
    reasoning_engine = CycloneReasoningEngine(agent_id=CYCLONE_AGENT_ID)
    reflection_engine = CycloneReflectionEngine(agent_id=CYCLONE_AGENT_ID)
    ctx_dict = build_fani_context()
    request = AgentRequest(query="Fani evacuation", context=ctx_dict)
    context = AgentContext(
        agent_id=CYCLONE_AGENT_ID,
        request=request,
        metadata={"cyclone_inputs": CycloneInputs.from_request_context(ctx_dict)},
    )

    tools = {t.name: t for t in create_cyclone_tools()}
    tool_results = [
        await t.run(ToolInput(parameters=ctx_dict, context=ctx_dict)) for t in tools.values()
    ]
    reasoning, _ = await reasoning_engine.run(context, tool_results)
    reflection = await reflection_engine.evaluate(context, reasoning, tool_results)
    decision = await decision_engine.evaluate(context, reasoning, reflection)

    assert decision.agent_id == CYCLONE_AGENT_ID
    assert decision.decision_type == DecisionType.CYCLONE
    assert len(decision.possible_actions) >= 1
    assert any(a.category == "coastal_warning" for a in decision.possible_actions)


@pytest.mark.asyncio
async def test_cyclone_validator_passes_fani(memory_manager) -> None:
    validator = CycloneValidator(agent_id=CYCLONE_AGENT_ID)
    ctx_dict = build_fani_context()
    request = AgentRequest(query="Validate Fani", context=ctx_dict)
    context = AgentContext(
        agent_id=CYCLONE_AGENT_ID,
        request=request,
        metadata={"cyclone_inputs": CycloneInputs.from_request_context(ctx_dict)},
    )

    tools = {t.name: t for t in create_cyclone_tools()}
    tool_results = [
        await t.run(ToolInput(parameters=ctx_dict, context=ctx_dict)) for t in tools.values()
    ]
    result = await validator.validate(context, tool_results)
    assert result.valid is True


@pytest.mark.asyncio
async def test_rapid_intensification_detection(memory_manager) -> None:
    engine = CycloneReasoningEngine(agent_id=CYCLONE_AGENT_ID)
    ctx_dict = build_rapid_intensification_context()
    request = AgentRequest(query="RI monitoring", context=ctx_dict)
    context = AgentContext(
        agent_id=CYCLONE_AGENT_ID,
        request=request,
        metadata={"cyclone_inputs": CycloneInputs.from_request_context(ctx_dict)},
    )

    tools = {t.name: t for t in create_cyclone_tools()}
    tool_results = [
        await t.run(ToolInput(parameters=ctx_dict, context=ctx_dict)) for t in tools.values()
    ]
    reasoning, signals = await engine.run(context, tool_results)
    ri = signals.rapid_intensification.value
    assert ri in ("possible", "likely", "confirmed")


@pytest.mark.asyncio
async def test_cyclone_agent_initialize(cyclone_agent: CycloneAgent) -> None:
    assert cyclone_agent.is_initialized
    caps = await cyclone_agent.capability_registry.list_capabilities()
    assert len(caps) == 12
    assert cyclone_agent.tool_manager.has_tool("sst_tool")
    assert cyclone_agent.tool_manager.has_tool("insat_tool")
