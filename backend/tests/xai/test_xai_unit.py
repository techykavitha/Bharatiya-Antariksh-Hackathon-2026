"""Unit tests for XAI framework components."""

from __future__ import annotations

import pytest

from backend.xai import (
    AlternativeActionsEngine,
    ConfidenceEngine,
    CounterfactualEngine,
    EvidenceEngine,
    ExplanationType,
    ReasoningTraceBuilder,
    UncertaintyEngine,
)
from backend.tests.xai.conftest import build_xai_input


@pytest.mark.asyncio
async def test_reasoning_trace_builder() -> None:
    builder = ReasoningTraceBuilder()
    explanation_input = build_xai_input()
    trace = await builder.build(
        explanation_input.reasoning,
        tool_results=explanation_input.tool_results,
    )
    assert len(trace.steps) == 3
    assert len(trace.narrative) == 3
    assert trace.overall_confidence > 0.7
    assert trace.total_duration_ms > 0


@pytest.mark.asyncio
async def test_evidence_engine_collects_sources() -> None:
    engine = EvidenceEngine()
    bundle = await engine.collect(build_xai_input())
    assert len(bundle.items) > 0
    assert len(bundle.tool_evidence) > 0
    assert len(bundle.historical_events) >= 1
    assert len(bundle.memory_references) == 1
    assert bundle.summary


@pytest.mark.asyncio
async def test_confidence_engine_dimensions() -> None:
    engine = ConfidenceEngine()
    estimate = await engine.estimate(build_xai_input())
    assert 0.0 <= estimate.overall <= 1.0
    assert estimate.model_confidence > 0
    assert estimate.data_quality > 0
    assert estimate.historical_similarity >= 0.8
    assert len(estimate.components) == 5
    assert estimate.summary


@pytest.mark.asyncio
async def test_uncertainty_engine_dimensions() -> None:
    engine = UncertaintyEngine()
    estimate = await engine.estimate(build_xai_input())
    assert 0.0 <= estimate.overall <= 1.0
    assert estimate.simulation_uncertainty > 0.5
    assert len(estimate.components) == 4
    assert estimate.summary


@pytest.mark.asyncio
async def test_alternative_actions_engine() -> None:
    engine = AlternativeActionsEngine()
    analysis = await engine.analyze(build_xai_input())
    assert analysis.chosen_action is not None
    assert len(analysis.alternatives) >= 1
    assert len(analysis.rejected) >= 1
    assert analysis.summary


@pytest.mark.asyncio
async def test_counterfactual_engine() -> None:
    engine = CounterfactualEngine()
    analysis = await engine.analyze(build_xai_input())
    assert analysis.question.startswith("What if")
    assert len(analysis.scenarios) >= 2
    assert any("What if" in s.title for s in analysis.scenarios)
    assert analysis.summary


@pytest.mark.asyncio
async def test_explanation_input_validation() -> None:
    explanation_input = build_xai_input()
    assert explanation_input.agent_id == "flood_agent"
    assert explanation_input.explanation_type == ExplanationType.FULL_PIPELINE
    assert explanation_input.decision_request is not None
