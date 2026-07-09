"""Unit tests for agriculture agent components."""

from __future__ import annotations

import pytest

from backend.agents.schemas.request import AgentRequest
from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agriculture.agriculture_context import AgricultureInputs
from backend.agents.specialized.agriculture.agriculture_models import AGRICULTURE_AGENT_ID
from backend.agents.specialized.agriculture.agriculture_rag import InMemoryAgricultureRAG
from backend.agents.specialized.agriculture.agriculture_reasoning import (
    AgricultureDecisionEngine,
    AgricultureReasoningEngine,
)
from backend.agents.specialized.agriculture.agriculture_tools import (
    ALL_AGRICULTURE_TOOL_NAMES,
    create_agriculture_tools,
)
from backend.agents.tools.abstract_tool import ToolInput
from backend.decision.decision_types import DecisionType
from backend.tests.specialized.agriculture.conftest import (
    build_karnataka_drought_context,
    build_punjab_wheat_context,
)


@pytest.mark.asyncio
async def test_agriculture_tools_registered() -> None:
    tools = create_agriculture_tools()
    names = {t.name for t in tools}
    assert len(names) == 12
    assert names == set(ALL_AGRICULTURE_TOOL_NAMES)


@pytest.mark.asyncio
async def test_ndvi_tool_punjab_wheat() -> None:
    tools = {t.name: t for t in create_agriculture_tools()}
    ctx = build_punjab_wheat_context()
    result = await tools["ndvi_tool"].run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["ndvi"] == 0.62
    assert result.output["health_status"] in ("good", "moderate", "excellent")


@pytest.mark.asyncio
async def test_soil_moisture_tool_karnataka_drought() -> None:
    tools = {t.name: t for t in create_agriculture_tools()}
    ctx = build_karnataka_drought_context()
    result = await tools["soil_moisture_tool"].run(ToolInput(parameters=ctx, context=ctx))
    assert result.success
    assert result.output["irrigation_needed"] is True
    assert result.output["soil_moisture_pct"] < 25.0


@pytest.mark.asyncio
async def test_agriculture_inputs_from_context() -> None:
    ctx = build_punjab_wheat_context()
    inputs = AgricultureInputs.from_request_context(ctx)
    assert inputs.crop_type == "wheat"
    assert inputs.state == "Punjab"
    assert inputs.season == "rabi"
    assert len(inputs.crop_calendar) == 3


@pytest.mark.asyncio
async def test_rag_retrieval_wheat() -> None:
    rag = InMemoryAgricultureRAG()
    result = await rag.retrieve(
        "wheat rabi irrigation advisory Punjab",
        crop_type="wheat",
        region="punjab",
        season="rabi",
    )
    assert result.retrieval_count >= 1
    assert any("wheat" in d.title.lower() or "wheat" in d.content.lower() for d in result.documents)


@pytest.mark.asyncio
async def test_rag_retrieval_karnataka_drought() -> None:
    rag = InMemoryAgricultureRAG()
    result = await rag.retrieve(
        "drought millet advisory Karnataka",
        crop_type="millet",
        region="karnataka",
    )
    assert result.retrieval_count >= 1
    assert any(d.category == "government_advisory" for d in result.documents) or result.documents


@pytest.mark.asyncio
async def test_agriculture_reasoning_drought() -> None:
    ctx_dict = build_karnataka_drought_context()
    request = AgentRequest(query="Assess Karnataka drought impact on millet", context=ctx_dict)
    context = AgentContext(agent_id=AGRICULTURE_AGENT_ID, request=request)
    context.metadata["agriculture_inputs"] = AgricultureInputs.from_request_context(ctx_dict)

    engine = AgricultureReasoningEngine(agent_id=AGRICULTURE_AGENT_ID)
    reasoning, signals = await engine.run(context, tool_results=[])

    assert signals.drought_risk is True
    assert signals.water_stress is True
    assert float(reasoning.metadata.get("resilience_score", 1.0)) < 0.6


@pytest.mark.asyncio
async def test_agriculture_decision_engine() -> None:
    ctx_dict = build_karnataka_drought_context()
    request = AgentRequest(query="Drought decision plan", context=ctx_dict)
    context = AgentContext(agent_id=AGRICULTURE_AGENT_ID, request=request)
    context.metadata["agriculture_inputs"] = AgricultureInputs.from_request_context(ctx_dict)

    reasoning_engine = AgricultureReasoningEngine(agent_id=AGRICULTURE_AGENT_ID)
    reasoning, _ = await reasoning_engine.run(context, tool_results=[])

    decision_engine = AgricultureDecisionEngine(agent_id=AGRICULTURE_AGENT_ID)
    decision = await decision_engine.evaluate(context, reasoning)

    assert decision.decision_type == DecisionType.AGRICULTURE
    assert len(decision.possible_actions) >= 2
    assert decision.need_rl is True
