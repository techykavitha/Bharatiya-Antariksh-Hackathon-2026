"""Unit tests for decision framework models and utilities."""

from __future__ import annotations

import pytest

from backend.decision import (
    BudgetConstraint,
    DecisionAction,
    DecisionConstraints,
    DecisionPriority,
    DecisionType,
    DecisionValidationError,
    Objective,
    RiskAssessment,
    RiskLevel,
    SafetyConstraint,
    compare_priority,
    escalate_priority,
    priority_from_label,
)
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_validator import ValidationSeverity
from backend.tests.decision.conftest import sample_action, sample_constraints, sample_objectives


def test_decision_type_values() -> None:
    assert DecisionType.FLOOD.value == "flood"
    assert DecisionType.WATER.value == "water"
    assert DecisionType.GENERAL.value == "general"
    assert len(DecisionType) == 9


def test_priority_ordering() -> None:
    assert compare_priority(DecisionPriority.CRITICAL, DecisionPriority.LOW) > 0
    assert compare_priority(DecisionPriority.NORMAL, DecisionPriority.NORMAL) == 0
    assert escalate_priority(DecisionPriority.NORMAL) == DecisionPriority.HIGH
    assert escalate_priority(DecisionPriority.CRITICAL) == DecisionPriority.CRITICAL


def test_priority_from_label() -> None:
    assert priority_from_label("critical") == DecisionPriority.CRITICAL
    assert priority_from_label("NORMAL") == DecisionPriority.NORMAL
    assert priority_from_label("unknown") == DecisionPriority.NORMAL


def test_decision_action_net_value() -> None:
    action = sample_action(cost=20.0, benefit=80.0)
    assert action.net_value == 60.0


def test_decision_request_rl_payload_strips_agent() -> None:
    request = DecisionRequest(
        agent_id="flood_agent",
        decision_type=DecisionType.FLOOD,
        objectives=sample_objectives(),
        possible_actions=[sample_action()],
    )
    payload = request.to_rl_payload()
    assert "agent_id" not in payload
    assert "decision_type" in payload
    assert "possible_actions" in payload


def test_decision_request_agent_id_required() -> None:
    with pytest.raises(ValueError):
        DecisionRequest(
            agent_id="  ",
            decision_type=DecisionType.FLOOD,
            objectives=sample_objectives(),
            possible_actions=[sample_action()],
        )


def test_constraints_active_categories() -> None:
    constraints = sample_constraints()
    cats = constraints.active_categories()
    assert "budget" in [c.value for c in cats]
    assert "safety" in [c.value for c in cats]


def test_risk_assessment_exceeds() -> None:
    risk = RiskAssessment(level=RiskLevel.SEVERE, score=0.8)
    assert risk.exceeds(RiskLevel.MODERATE)
    assert not risk.exceeds(RiskLevel.CRITICAL)


def test_validator_valid_request(decision_validator, flood_request) -> None:
    result = decision_validator.validate_request(flood_request)
    assert result.valid is True
    assert len(result.blocking_issues) == 0


def test_validator_rejects_no_actions(decision_validator) -> None:
    request = DecisionRequest(
        agent_id="flood_agent",
        decision_type=DecisionType.FLOOD,
        objectives=sample_objectives(),
        possible_actions=[],
        need_rl=True,
    )
    result = decision_validator.validate_request(request)
    assert result.valid is False
    assert any(i.code == "insufficient_actions" for i in result.issues)


def test_validator_budget_violation(decision_validator) -> None:
    request = DecisionRequest(
        agent_id="water_resource_agent",
        decision_type=DecisionType.WATER,
        objectives=sample_objectives(),
        possible_actions=[
            DecisionAction(description="Expensive action", cost=500.0, expected_benefit=100.0),
        ],
        constraints=DecisionConstraints(budget=BudgetConstraint(max_cost=50.0)),
    )
    result = decision_validator.validate_request(request)
    assert result.valid is False
    assert any(i.code == "budget_exceeded" for i in result.issues)


def test_validator_safety_violation(decision_validator) -> None:
    request = DecisionRequest(
        agent_id="flood_agent",
        decision_type=DecisionType.FLOOD,
        objectives=sample_objectives(),
        possible_actions=[
            DecisionAction(
                description="Risky action",
                cost=10.0,
                risk_score=0.95,
                expected_benefit=50.0,
            ),
        ],
        constraints=DecisionConstraints(safety=SafetyConstraint(max_risk_score=0.7)),
    )
    result = decision_validator.validate_request(request)
    assert result.valid is False
    assert any(i.code == "safety_violation" for i in result.issues)


def test_validator_strict_raises(decision_validator) -> None:
    request = DecisionRequest(
        agent_id="flood_agent",
        decision_type=DecisionType.FLOOD,
        objectives=sample_objectives(),
        possible_actions=[],
    )
    with pytest.raises(DecisionValidationError):
        decision_validator.validate_request(request, strict=True)


def test_validator_duplicate_objectives(decision_validator) -> None:
    objs = [
        Objective(objective_id="same", description="A", weight=0.5),
        Objective(objective_id="same", description="B", weight=0.5),
    ]
    request = DecisionRequest(
        agent_id="flood_agent",
        decision_type=DecisionType.FLOOD,
        objectives=objs,
        possible_actions=[sample_action()],
    )
    result = decision_validator.validate_request(request)
    assert any(i.code == "duplicate_objectives" for i in result.issues)


def test_validator_no_go_region(decision_validator) -> None:
    request = DecisionRequest(
        agent_id="flood_agent",
        decision_type=DecisionType.FLOOD,
        objectives=sample_objectives(),
        possible_actions=[
            DecisionAction(
                description="Release to protected area",
                cost=5.0,
                expected_benefit=20.0,
                affected_regions=["protected_wetland"],
            ),
        ],
        constraints=DecisionConstraints(
            safety=SafetyConstraint(no_go_regions=["protected_wetland"]),
        ),
    )
    result = decision_validator.validate_request(request)
    assert any(i.code == "no_go_region" for i in result.issues)
    assert any(i.severity == ValidationSeverity.CRITICAL for i in result.issues)
