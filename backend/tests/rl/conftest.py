"""Shared fixtures for RL service tests."""

from __future__ import annotations

import pytest

from backend.agents.memory.memory_manager import MemoryManager
from backend.decision import DecisionManager, DecisionType, RiskLevel
from backend.rl import PolicyManager, RLOptimizationService, RLAlgorithm
from backend.tests.decision.conftest import (
    build_flood_decision_request,
    build_water_decision_request,
    sample_action,
    sample_constraints,
    sample_objectives,
)


@pytest.fixture
async def memory_manager() -> MemoryManager:
    return await MemoryManager.create_in_memory()


@pytest.fixture
def policy_manager() -> PolicyManager:
    return PolicyManager()


@pytest.fixture
async def rl_service(memory_manager: MemoryManager) -> RLOptimizationService:
    return await RLOptimizationService.create(memory=memory_manager)


@pytest.fixture
def flood_decision_request():
    return build_flood_decision_request()


@pytest.fixture
def water_decision_request():
    return build_water_decision_request()


def build_budget_violation_request():
    manager = DecisionManager()
    return manager.create(
        agent_id="flood_agent",
        decision_type=DecisionType.FLOOD,
        objectives=sample_objectives(),
        possible_actions=[
            sample_action("Expensive evacuation", cost=500.0, benefit=90.0, risk=RiskLevel.HIGH),
        ],
        constraints=sample_constraints(),
        need_rl=True,
    )
