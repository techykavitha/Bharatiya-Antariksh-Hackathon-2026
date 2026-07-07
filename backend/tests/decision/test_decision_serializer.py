"""Unit tests for decision serializer."""

from __future__ import annotations

import json

import pytest

from backend.decision import DecisionResponse, DecisionType
from backend.decision.decision_actions import ActionRanking, RejectedAction
from backend.decision.decision_response import DecisionStatus
from backend.decision.decision_serializer import DecisionSerializer
from backend.tests.decision.conftest import build_flood_decision_request, sample_action
from backend.utils.errors import SchemaValidationError


def test_json_round_trip(decision_serializer, flood_request) -> None:
    json_str = decision_serializer.to_json(flood_request)
    restored = decision_serializer.from_json(json_str, type(flood_request))
    assert restored.decision_id == flood_request.decision_id
    assert restored.agent_id == flood_request.agent_id
    assert restored.decision_type == DecisionType.FLOOD
    assert len(restored.possible_actions) == len(flood_request.possible_actions)


def test_pydantic_round_trip(decision_serializer, flood_request) -> None:
    copy = decision_serializer.to_pydantic(flood_request)
    assert copy.model_dump() == flood_request.model_dump()


def test_request_db_record_round_trip(decision_serializer, flood_request) -> None:
    record = decision_serializer.request_to_db_record(flood_request)
    assert record["table"] == "decision_requests"
    assert record["agent_id"] == "flood_agent"
    assert record["decision_type"] == "flood"
    assert record["schema_version"] == "1.0"
    assert "payload_json" in record

    restored = decision_serializer.request_from_db_record(record)
    assert restored.decision_id == flood_request.decision_id
    assert restored.confidence == flood_request.confidence


def test_response_db_record_round_trip(decision_serializer, flood_request) -> None:
    action = flood_request.possible_actions[0]
    response = DecisionResponse(
        decision_id=flood_request.decision_id,
        chosen_action=action,
        ranking=[ActionRanking(action_id=action.action_id, rank=1, score=0.9, expected_reward=45.0)],
        reward=45.0,
        confidence=0.88,
        reason="Optimal flood mitigation",
        rejected_actions=[
            RejectedAction(action_id="other", reason="Cost too high", constraint_violated="budget"),
        ],
    )
    record = decision_serializer.response_to_db_record(response)
    assert record["table"] == "decision_responses"
    restored = decision_serializer.response_from_db_record(record)
    assert restored.decision_id == flood_request.decision_id
    assert restored.chosen_action is not None
    assert restored.chosen_action.action_id == action.action_id


def test_invalid_json_raises(decision_serializer) -> None:
    with pytest.raises(SchemaValidationError):
        decision_serializer.from_json("{invalid", type(build_flood_decision_request()))


def test_rl_payload_json_serializable(flood_request) -> None:
    payload = flood_request.to_rl_payload()
    serialized = json.dumps(payload)
    data = json.loads(serialized)
    assert "agent_id" not in data
    assert data["decision_type"] == "flood"
