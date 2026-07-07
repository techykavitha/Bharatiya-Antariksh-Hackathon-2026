"""Unit tests for RL framework components."""

from __future__ import annotations

import pytest

from backend.decision import DecisionType, RiskLevel
from backend.decision.decision_actions import DecisionAction
from backend.rl import (
    ActionSpace,
    PPOPolicy,
    RLAlgorithm,
    RLConstraintEngine,
    RewardEngine,
    StateEncoder,
    create_policy,
)
from backend.rl.rl_engine import DQNPolicy, SACPolicy
from backend.rl.rl_multi_objective import MultiObjectiveOptimizer
from backend.rl.rl_policy_manager import PolicyManager
from backend.tests.decision.conftest import build_flood_decision_request, sample_objectives
from backend.tests.rl.conftest import build_budget_violation_request


@pytest.mark.asyncio
async def test_state_encoder_produces_vector() -> None:
    request = build_flood_decision_request()
    encoder = StateEncoder()
    state = await encoder.encode(request)
    assert state.dimension > 0
    assert len(state.vector) == state.dimension
    assert state.decision_id == request.decision_id
    assert "confidence" in state.features
    assert "risk_score" in state.features


@pytest.mark.asyncio
async def test_state_encoder_strips_agent_identity() -> None:
    request = build_flood_decision_request()
    payload = request.to_rl_payload()
    assert "agent_id" not in payload


def test_action_space_from_request() -> None:
    request = build_flood_decision_request()
    space = ActionSpace.from_request(request)
    assert space.discrete_size == len(request.possible_actions)
    encoded = space.encode(request.possible_actions[0])
    assert encoded.discrete_index == 0
    decoded = space.decode(encoded)
    assert decoded.action_id == request.possible_actions[0].action_id


@pytest.mark.asyncio
async def test_reward_engine_compute() -> None:
    request = build_flood_decision_request()
    encoder = StateEncoder()
    state = await encoder.encode(request)
    engine = RewardEngine()
    action = request.possible_actions[0]
    breakdown = engine.compute(action, request, state)
    assert breakdown.action_id == action.action_id
    assert breakdown.total != 0.0
    assert len(breakdown.components) > 0


@pytest.mark.asyncio
async def test_multi_objective_evaluate_all() -> None:
    request = build_flood_decision_request()
    encoder = StateEncoder()
    state = await encoder.encode(request)
    optimizer = MultiObjectiveOptimizer()
    results = optimizer.evaluate_all(request, state)
    assert len(results) == len(request.possible_actions)
    assert results[0].pareto_rank == 1
    assert results[0].total_score >= results[-1].total_score


def test_constraint_engine_budget_violation() -> None:
    request = build_budget_violation_request()
    engine = RLConstraintEngine()
    feasible, results = engine.filter_feasible(request)
    assert len(feasible) == 0
    assert results[0].feasible is False


def test_constraint_engine_feasible_actions() -> None:
    request = build_flood_decision_request()
    engine = RLConstraintEngine()
    feasible, _ = engine.filter_feasible(request)
    assert len(feasible) == len(request.possible_actions)


@pytest.mark.asyncio
async def test_ppo_policy_selection() -> None:
    manager = PolicyManager()
    artifact = manager.get_active_artifact()
    policy = PPOPolicy(artifact=artifact)
    request = build_flood_decision_request()
    space = ActionSpace.from_request(request)
    optimizer = MultiObjectiveOptimizer()
    state = await StateEncoder().encode(request)
    scores = optimizer.evaluate_all(request, state)
    output = policy.select(state, space, scores)
    assert 0 <= output.selected_index < len(scores)
    assert output.algorithm == RLAlgorithm.PPO.value
    assert len(output.probabilities) == len(scores)


@pytest.mark.asyncio
async def test_dqn_policy_epsilon_greedy() -> None:
    manager = PolicyManager()
    artifact = manager.get_artifact(f"default_{RLAlgorithm.DQN.value}_v1")
    policy = DQNPolicy(artifact=artifact)
    request = build_flood_decision_request()
    state = await StateEncoder().encode(request)
    scores = MultiObjectiveOptimizer().evaluate_all(request, state)
    output = policy.select(state, ActionSpace.from_request(request), scores)
    assert output.selected_index >= 0


@pytest.mark.asyncio
async def test_sac_policy_selection() -> None:
    manager = PolicyManager()
    artifact = manager.get_artifact(f"default_{RLAlgorithm.SAC.value}_v1")
    policy = SACPolicy(artifact=artifact)
    request = build_flood_decision_request()
    state = await StateEncoder().encode(request)
    scores = MultiObjectiveOptimizer().evaluate_all(request, state)
    output = policy.select(state, ActionSpace.from_request(request), scores)
    assert output.confidence > 0


def test_policy_factory_all_algorithms() -> None:
    manager = PolicyManager()
    for algorithm in RLAlgorithm:
        policies = manager.list_versions(algorithm=algorithm)
        assert len(policies) >= 1
        artifact = manager.get_artifact(policies[0].policy_id)
        assert artifact is not None
        policy = create_policy(artifact)
        assert policy.algorithm == algorithm
