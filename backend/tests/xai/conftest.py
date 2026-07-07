"""Shared fixtures for XAI framework tests."""

from __future__ import annotations

import pytest

from backend.agents.schemas.response import ToolOutputRecord
from backend.agents.specialized.agent_reasoning import ReasoningPhase, ReasoningResult, ReasoningStep
from backend.agents.specialized.agent_reflection import ReflectionFinding, ReflectionResult, ReflectionSignal
from backend.agents.specialized.agent_validator import ValidationIssue, ValidationCategory, ValidationResult
from backend.agents.tools.abstract_tool import ToolResult
from backend.decision import DecisionAction, DecisionManager, DecisionType, RiskLevel
from backend.tests.decision.conftest import build_climate_state, build_flood_decision_request, sample_constraints, sample_objectives
from backend.xai import ExplanationEngine, ExplanationInput, ExplanationType


def build_reasoning_result() -> ReasoningResult:
    return ReasoningResult(
        steps=[
            ReasoningStep(
                phase=ReasoningPhase.OBSERVE,
                content="Observing flood context for region=chennai",
                confidence=0.7,
                duration_ms=2.0,
                metadata={"stage": "observe"},
            ),
            ReasoningStep(
                phase=ReasoningPhase.THINK,
                content="Rainfall elevated=True, river overflow=True",
                confidence=0.85,
                duration_ms=5.0,
                metadata={"stage": "rainfall_impact"},
            ),
            ReasoningStep(
                phase=ReasoningPhase.VERIFY,
                content="Flood severity=high (composite=0.72)",
                confidence=0.9,
                duration_ms=3.0,
                metadata={"stage": "estimate_severity"},
            ),
        ],
        overall_confidence=0.82,
        metadata={
            "severity": "high",
            "flood_signals": {
                "historical_analog": True,
                "historical_score": 0.8,
                "composite_score": 0.72,
                "uncertainty": 0.25,
            },
        },
    )


def build_tool_results() -> list[ToolResult]:
    return [
        ToolResult(
            tool_name="rainfall_tool",
            success=True,
            output={"rainfall_score": 0.75, "heavy_rainfall": True, "current_mm": 120.0},
            duration_ms=1.2,
        ),
        ToolResult(
            tool_name="river_tool",
            success=True,
            output={"river_score": 0.7, "overflow": True, "river_level_m": 8.5},
            duration_ms=0.9,
        ),
        ToolResult(
            tool_name="historical_flood_tool",
            success=True,
            output={
                "historical_analog": True,
                "historical_score": 0.85,
                "events": [{"event_id": "flood-2015", "peak_depth_m": 1.8}],
            },
            duration_ms=1.0,
        ),
        ToolResult(
            tool_name="digital_twin_tool",
            success=True,
            output={"twin_id": "twin-chennai-01", "digital_twin_available": True, "lst_c": None},
            duration_ms=0.5,
        ),
    ]


def build_reflection_result() -> ReflectionResult:
    return ReflectionResult(
        findings=[
            ReflectionFinding(
                signal=ReflectionSignal.NEED_SIMULATION,
                message="Urban flood simulation recommended",
                severity=0.55,
            ),
        ],
        confidence=0.8,
        needs_simulation=True,
        notes=["Urban flood simulation recommended"],
    )


def build_validation_result() -> ValidationResult:
    return ValidationResult(
        valid=True,
        issues=[
            ValidationIssue(
                category=ValidationCategory.FORECAST_CONSISTENCY,
                message="Forecast horizon exceeds 72h",
                severity=0.3,
            ),
        ],
    )


def build_decision_response() -> tuple:
    from backend.decision.decision_actions import ActionRanking, RejectedAction
    from backend.decision.decision_response import DecisionResponse

    request = build_flood_decision_request()
    chosen = request.possible_actions[1]
    rejected = request.possible_actions[2]
    response = DecisionResponse(
        decision_id=request.decision_id,
        chosen_action=chosen,
        reward=45.0,
        confidence=0.78,
        reason="Balanced flood risk reduction and cost",
        ranking=[
            ActionRanking(
                action_id=chosen.action_id,
                rank=1,
                score=0.82,
                expected_reward=45.0,
                confidence=0.78,
                rationale="Best net value within safety constraints",
            ),
            ActionRanking(
                action_id=request.possible_actions[0].action_id,
                rank=2,
                score=0.65,
                expected_reward=25.0,
                confidence=0.7,
                rationale="Lower cost but reduced benefit",
            ),
        ],
        rejected_actions=[
            RejectedAction(
                action_id=rejected.action_id,
                reason="Exceeds safety risk threshold",
                constraint_violated="safety",
                score=0.4,
            ),
        ],
    )
    return request, response


def build_xai_input(*, full: bool = True) -> ExplanationInput:
    decision_request, decision_response = build_decision_response()
    return ExplanationInput(
        request_id="xai-test-001",
        agent_id="flood_agent",
        explanation_type=ExplanationType.FULL_PIPELINE,
        query="Assess flood risk in Chennai",
        reasoning=build_reasoning_result() if full else None,
        tool_results=build_tool_results() if full else [],
        reflection=build_reflection_result() if full else None,
        validation=build_validation_result() if full else None,
        decision_request=decision_request,
        decision_response=decision_response if full else None,
        memory_references=["memory:working:flood_report:abc"],
        recommendations=["Issue flood warning", "Monitor reservoir levels"],
        metadata={"region_id": "chennai"},
    )


@pytest.fixture
async def explanation_engine() -> ExplanationEngine:
    return await ExplanationEngine.create()
