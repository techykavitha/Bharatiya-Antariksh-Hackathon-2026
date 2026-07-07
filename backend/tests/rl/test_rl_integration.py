"""Integration tests for RLOptimizationService."""

from __future__ import annotations

import pytest

from backend.decision import DecisionManager, DecisionType
from backend.rl import RLAlgorithm, RLOptimizationService
from backend.tests.decision.conftest import sample_action, sample_constraints, sample_objectives
from backend.tests.rl.conftest import build_budget_violation_request


@pytest.mark.asyncio
async def test_rl_service_optimize_flood(rl_service, flood_decision_request) -> None:
    response = await rl_service.optimize(flood_decision_request)
    assert response.is_successful()
    assert response.chosen_action is not None
    assert response.decision_id == flood_decision_request.decision_id
    assert response.reward is not None
    assert response.confidence > 0
    assert len(response.ranking) >= 1
    assert response.engine_id.startswith("rl_")


@pytest.mark.asyncio
async def test_rl_service_optimize_water(rl_service, water_decision_request) -> None:
    response = await rl_service.optimize(water_decision_request)
    assert response.is_successful()
    assert response.chosen_action is not None


@pytest.mark.asyncio
async def test_rl_service_agent_agnostic(rl_service, flood_decision_request, water_decision_request) -> None:
    """RL produces same response schema regardless of originating agent."""
    flood_resp = await rl_service.optimize(flood_decision_request)
    water_resp = await rl_service.optimize(water_decision_request)
    assert set(flood_resp.model_dump().keys()) == set(water_resp.model_dump().keys())
    assert "flood" not in flood_resp.engine_id
    assert "water" not in water_resp.engine_id


@pytest.mark.asyncio
async def test_rl_service_rank_actions(rl_service, flood_decision_request) -> None:
    rankings = await rl_service.rank_actions(flood_decision_request)
    assert len(rankings) >= 1
    assert rankings[0].rank == 1
    ranks = [r.rank for r in rankings]
    assert ranks == sorted(ranks)


@pytest.mark.asyncio
async def test_rl_service_evaluate_action(rl_service, flood_decision_request) -> None:
    action_id = flood_decision_request.possible_actions[0].action_id
    result = await rl_service.evaluate(flood_decision_request, action_id)
    assert result.action_id == action_id
    assert result.total_score != 0.0


@pytest.mark.asyncio
async def test_rl_service_simulate_reward(rl_service, flood_decision_request) -> None:
    action_id = flood_decision_request.possible_actions[0].action_id
    breakdown = await rl_service.simulate_reward(flood_decision_request, action_id)
    assert breakdown.action_id == action_id
    assert len(breakdown.components) > 0


@pytest.mark.asyncio
async def test_rl_service_metrics(rl_service, flood_decision_request) -> None:
    await rl_service.optimize(flood_decision_request)
    metrics = rl_service.last_metrics
    assert metrics is not None
    assert metrics.inference_latency_ms > 0
    assert metrics.actions_evaluated >= 1
    assert metrics.optimization_confidence > 0
    assert metrics.algorithm == RLAlgorithm.PPO.value


@pytest.mark.asyncio
async def test_rl_service_ppo_algorithm(rl_service, flood_decision_request) -> None:
    response = await rl_service.optimize(flood_decision_request, algorithm=RLAlgorithm.PPO)
    assert response.metadata.get("algorithm") == "ppo"


@pytest.mark.asyncio
async def test_rl_service_sac_algorithm(rl_service, flood_decision_request) -> None:
    response = await rl_service.optimize(flood_decision_request, algorithm=RLAlgorithm.SAC)
    assert response.metadata.get("algorithm") == "sac"


@pytest.mark.asyncio
async def test_rl_service_dqn_algorithm(rl_service, flood_decision_request) -> None:
    response = await rl_service.optimize(flood_decision_request, algorithm=RLAlgorithm.DQN)
    assert response.metadata.get("algorithm") == "dqn"


@pytest.mark.asyncio
async def test_rl_service_constraint_failure(rl_service) -> None:
    request = build_budget_violation_request()
    response = await rl_service.optimize(request, validate=False)
    assert not response.is_successful()
    assert response.status.value == "failed"


@pytest.mark.asyncio
async def test_rl_service_records_episode(rl_service, flood_decision_request) -> None:
    await rl_service.optimize(flood_decision_request)
    episodes = await rl_service.get_training_episodes()
    assert len(episodes) >= 1
    assert episodes[-1].decision_id == flood_decision_request.decision_id


@pytest.mark.asyncio
async def test_rl_service_switch_policy(rl_service) -> None:
    policies = await rl_service.list_policies()
    sac_policy = next(p for p in policies if p["algorithm"] == "sac")
    active_id = await rl_service.switch_policy(sac_policy["policy_id"])
    assert active_id == sac_policy["policy_id"]


@pytest.mark.asyncio
async def test_rl_service_uniform_decision_types(rl_service) -> None:
    """Verify all decision types produce valid responses."""
    manager = DecisionManager()
    for dt in DecisionType:
        request = manager.create(
            agent_id="test_agent",
            decision_type=dt,
            objectives=sample_objectives(),
            possible_actions=[
                sample_action(f"Action for {dt.value}", 10.0, 40.0),
                sample_action(f"Alternative for {dt.value}", 5.0, 25.0),
            ],
            constraints=sample_constraints(),
        )
        response = await rl_service.optimize(request, validate=False)
        assert response.decision_id == request.decision_id
        if response.is_successful():
            assert response.chosen_action is not None


@pytest.mark.asyncio
async def test_rl_service_invalid_action_id(rl_service, flood_decision_request) -> None:
    from backend.rl import RLOptimizationError

    with pytest.raises(RLOptimizationError):
        await rl_service.evaluate(flood_decision_request, "nonexistent-action-id")
