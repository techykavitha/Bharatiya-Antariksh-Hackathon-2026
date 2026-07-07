"""Integration tests for DecisionManager."""

from __future__ import annotations

import pytest

from backend.decision import (
    DecisionPriority,
    DecisionResponse,
    DecisionType,
    DecisionValidationError,
    PriorityContext,
    RiskLevel,
)
from backend.decision.decision_actions import ActionRanking, RejectedAction
from backend.decision.decision_context import DecisionContext
from backend.decision.decision_types import DecisionStatus
from backend.tests.decision.conftest import (
    build_climate_state,
    build_flood_decision_request,
    build_water_decision_request,
    sample_action,
    sample_objectives,
)


@pytest.mark.asyncio
async def test_manager_create(decision_manager) -> None:
    request = decision_manager.create(
        agent_id="flood_agent",
        decision_type=DecisionType.FLOOD,
        objectives=sample_objectives(),
        possible_actions=[sample_action(), sample_action("Evacuate", 50.0, 80.0)],
    )
    assert request.decision_id
    assert request.status == DecisionStatus.PENDING
    assert decision_manager.get_request(request.decision_id) is request


@pytest.mark.asyncio
async def test_manager_create_from_builder(decision_manager) -> None:
    request = decision_manager.create_from_builder(
        agent_id="water_resource_agent",
        decision_type=DecisionType.WATER,
        scenario_name="krishna_basin",
        region_id="krishna",
        objectives=["Balance supply", "Prevent overflow"],
        actions=[("Gradual release", 10.0, 40.0), ("Hold", 1.0, 15.0)],
        priority_label="high",
        need_rl=True,
        need_simulation=True,
    )
    assert request.agent_id == "water_resource_agent"
    assert request.decision_type == DecisionType.WATER
    assert len(request.possible_actions) == 2
    assert request.priority == DecisionPriority.HIGH


@pytest.mark.asyncio
async def test_manager_queue_and_dequeue(decision_manager, flood_request, water_request) -> None:
    low = decision_manager.create(
        agent_id="agriculture_agent",
        decision_type=DecisionType.AGRICULTURE,
        objectives=sample_objectives(),
        possible_actions=[sample_action("Irrigate", 5.0, 20.0)],
        priority=DecisionPriority.LOW,
        confidence=0.5,
    )
    await decision_manager.queue(low)
    await decision_manager.queue(water_request)
    await decision_manager.queue(flood_request)

    assert await decision_manager.queue_size() == 3

    first = await decision_manager.dequeue()
    assert first is not None
    assert first.decision_id == flood_request.decision_id
    assert first.status == DecisionStatus.PROCESSING

    second = await decision_manager.dequeue()
    assert second is not None
    assert second.priority >= DecisionPriority.NORMAL


@pytest.mark.asyncio
async def test_manager_compare(decision_manager, flood_request, water_request) -> None:
    comparison = decision_manager.compare(flood_request, water_request)
    assert comparison.decision_id_a == flood_request.decision_id
    assert comparison.priority_delta > 0
    assert comparison.same_type is False
    assert comparison.same_agent is False
    assert comparison.higher_priority == flood_request.decision_id


@pytest.mark.asyncio
async def test_manager_merge(decision_manager) -> None:
    flood = build_flood_decision_request()
    water = build_water_decision_request()
    merged = decision_manager.merge([flood, water], decision_type=DecisionType.GENERAL)

    assert merged.decision_type == DecisionType.GENERAL
    assert len(merged.possible_actions) == len(flood.possible_actions) + len(water.possible_actions)
    assert merged.priority == DecisionPriority.HIGH
    assert merged.need_rl is True
    assert merged.need_simulation is True
    assert "merged_from" in merged.metadata


@pytest.mark.asyncio
async def test_manager_merge_empty_raises(decision_manager) -> None:
    with pytest.raises(ValueError):
        decision_manager.merge([])


@pytest.mark.asyncio
async def test_manager_prioritize(decision_manager, water_request) -> None:
    water_request.priority = DecisionPriority.NORMAL
    resolved = decision_manager.prioritize(
        water_request,
        PriorityContext(base_priority=DecisionPriority.NORMAL, risk_escalation=True),
    )
    assert resolved == DecisionPriority.HIGH
    assert water_request.priority == DecisionPriority.HIGH


@pytest.mark.asyncio
async def test_manager_serialize_round_trip(decision_manager, flood_request) -> None:
    json_str = decision_manager.serialize_json(flood_request)
    restored = decision_manager.deserialize_request_json(json_str)
    assert restored.decision_id == flood_request.decision_id
    assert restored.agent_id == flood_request.agent_id


@pytest.mark.asyncio
async def test_manager_db_record_round_trip(decision_manager, flood_request) -> None:
    record = decision_manager.to_db_record(flood_request)
    restored = decision_manager.from_db_record(record)
    assert restored.decision_id == flood_request.decision_id


@pytest.mark.asyncio
async def test_manager_store_response(decision_manager) -> None:
    request = decision_manager.create(
        agent_id="flood_agent",
        decision_type=DecisionType.FLOOD,
        objectives=sample_objectives(),
        possible_actions=[sample_action(), sample_action("Evacuate", 50.0, 80.0)],
    )
    action = request.possible_actions[0]
    response = DecisionResponse(
        decision_id=request.decision_id,
        chosen_action=action,
        ranking=[ActionRanking(action_id=action.action_id, rank=1, score=0.85)],
        reward=42.0,
        confidence=0.9,
        reason="Selected",
    )
    decision_manager.store_response(response)
    stored = decision_manager.get_response(response.response_id)
    assert stored is not None
    assert stored.is_successful()

    updated_request = decision_manager.get_request(request.decision_id)
    assert updated_request is not None
    assert updated_request.status == DecisionStatus.COMPLETED


@pytest.mark.asyncio
async def test_manager_validate_response(decision_manager, flood_request) -> None:
    action = flood_request.possible_actions[0]
    response = DecisionResponse(
        decision_id=flood_request.decision_id,
        chosen_action=action,
        confidence=0.85,
        reason="OK",
    )
    result = decision_manager.validate_response(response, flood_request)
    assert result.valid is True


@pytest.mark.asyncio
async def test_manager_validate_response_id_mismatch(decision_manager, flood_request) -> None:
    response = DecisionResponse(
        decision_id="wrong-id",
        chosen_action=flood_request.possible_actions[0],
        confidence=0.85,
    )
    result = decision_manager.validate_response(response, flood_request)
    assert result.valid is False


@pytest.mark.asyncio
async def test_manager_list_requests(decision_manager) -> None:
    decision_manager.create(
        agent_id="flood_agent",
        decision_type=DecisionType.FLOOD,
        objectives=sample_objectives(),
        possible_actions=[sample_action()],
    )
    decision_manager.create(
        agent_id="water_resource_agent",
        decision_type=DecisionType.WATER,
        objectives=sample_objectives(),
        possible_actions=[sample_action()],
    )
    flood_only = decision_manager.list_requests(decision_type=DecisionType.FLOOD)
    assert len(flood_only) >= 1
    assert all(r.decision_type == DecisionType.FLOOD for r in flood_only)


@pytest.mark.asyncio
async def test_uniform_schema_across_agents(decision_manager) -> None:
    """RL must receive identical schema from flood and water agents."""
    flood = decision_manager.create_from_builder(
        agent_id="flood_agent",
        decision_type=DecisionType.FLOOD,
        scenario_name="flood",
        objectives=["Minimize inundation"],
        actions=[("Warn", 5.0, 30.0)],
        need_rl=True,
    )
    water = decision_manager.create_from_builder(
        agent_id="water_resource_agent",
        decision_type=DecisionType.WATER,
        scenario_name="water",
        objectives=["Balance supply"],
        actions=[("Release", 10.0, 40.0)],
        need_rl=True,
    )

    flood_keys = set(flood.to_rl_payload().keys())
    water_keys = set(water.to_rl_payload().keys())
    assert flood_keys == water_keys
    assert "agent_id" not in flood_keys
    assert "agent_id" not in water_keys


@pytest.mark.asyncio
async def test_context_from_climate_state() -> None:
    climate = build_climate_state()
    context = DecisionContext.from_climate_state(climate, scenario_name="chennai")
    assert context.climate_state is not None
    assert context.forecast_reference is not None
    assert context.forecast_reference.forecast_id == "fcst-001"


@pytest.mark.asyncio
async def test_manager_create_strict_validation(decision_manager) -> None:
    with pytest.raises(DecisionValidationError):
        decision_manager.create(
            agent_id="flood_agent",
            decision_type=DecisionType.FLOOD,
            objectives=sample_objectives(),
            possible_actions=[],
            need_rl=True,
            validate=True,
            strict=True,
        )


@pytest.mark.asyncio
async def test_clear_queue(decision_manager, flood_request) -> None:
    await decision_manager.queue(flood_request)
    cleared = await decision_manager.clear_queue()
    assert cleared == 1
    assert await decision_manager.queue_size() == 0
