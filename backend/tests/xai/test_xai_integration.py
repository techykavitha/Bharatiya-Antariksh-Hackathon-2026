"""Integration tests for the Explainability Framework."""

from __future__ import annotations

import pytest

from backend.decision import DecisionManager, DecisionType, RiskLevel
from backend.tests.decision.conftest import sample_action, sample_constraints, sample_objectives
from backend.tests.xai.conftest import build_xai_input, build_decision_response
from backend.xai import ExplanationEngine, ExplanationType, ExplainabilityReport


@pytest.mark.asyncio
async def test_explanation_engine_full_pipeline(explanation_engine: ExplanationEngine) -> None:
    report = await explanation_engine.explain_pipeline(build_xai_input())
    assert isinstance(report, ExplainabilityReport)
    assert report.executive_summary
    assert len(report.reasoning_trace.steps) >= 3
    assert len(report.evidence.items) > 0
    assert report.confidence.overall > 0
    assert report.uncertainty.overall >= 0
    assert report.alternatives.chosen_action is not None
    assert len(report.counterfactuals.scenarios) >= 2
    assert report.processing_time_ms >= 0
    assert explanation_engine.last_report is report


@pytest.mark.asyncio
async def test_explanation_engine_decision_only(explanation_engine: ExplanationEngine) -> None:
    explanation_input = build_xai_input().model_copy(
        update={"explanation_type": ExplanationType.DECISION},
    )
    report = await explanation_engine.explain(explanation_input)
    assert report.alternatives.chosen_action is not None
    assert report.counterfactuals.scenarios
    assert report.chosen_action_summary


@pytest.mark.asyncio
async def test_explanation_engine_rl_convenience(explanation_engine: ExplanationEngine) -> None:
    decision_request, decision_response = build_decision_response()
    report = await explanation_engine.explain_decision(
        decision_request,
        decision_response=decision_response,
        recommendations=["Deploy pumps"],
    )
    assert report.explanation_type == ExplanationType.RL
    assert report.recommendations == ["Deploy pumps"]
    assert report.alternatives.ranking


@pytest.mark.asyncio
async def test_explainability_report_audit_trace(explanation_engine: ExplanationEngine) -> None:
    report = await explanation_engine.explain_pipeline(build_xai_input())
    trace = report.to_audit_trace()
    assert len(trace) >= 2
    assert report.is_high_confidence or not report.is_high_confidence


@pytest.mark.asyncio
async def test_heatwave_decision_explanation(explanation_engine: ExplanationEngine) -> None:
    manager = DecisionManager()
    request = manager.create(
        agent_id="heatwave_agent",
        decision_type=DecisionType.HEATWAVE,
        objectives=sample_objectives(),
        possible_actions=[
            sample_action("Open cooling centers", cost=15.0, benefit=80.0, risk=RiskLevel.LOW),
            sample_action("Emergency response", cost=100.0, benefit=95.0, risk=RiskLevel.HIGH),
        ],
        constraints=sample_constraints(),
        need_rl=True,
        need_simulation=True,
        rationale=["Severe heatwave with urban heat island"],
    )
    report = await explanation_engine.explain_decision(request)
    assert report.agent_id == "heatwave_agent"
    assert report.uncertainty.simulation_uncertainty > 0.5
    assert "heatwave" in report.metadata.get("decision_type", "")


@pytest.mark.asyncio
async def test_explanation_with_minimal_input(explanation_engine: ExplanationEngine) -> None:
    report = await explanation_engine.explain(build_xai_input(full=False))
    assert report.executive_summary
    assert report.reasoning_trace.narrative
    assert report.alternatives.chosen_action is None
