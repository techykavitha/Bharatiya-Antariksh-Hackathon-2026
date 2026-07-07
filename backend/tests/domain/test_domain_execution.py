"""Tests for domain execution engine."""

import pytest

from backend.agents.domain.domain_context import (
    DomainExecutionMode,
    DomainExecutionPlan,
    DomainExecutionStep,
    DomainType,
)
from backend.agents.domain.domain_execution import DomainExecutionPolicy, DomainExecutor
from backend.agents.schemas.request import AgentRequest
from backend.tests.domain.conftest import MockSpecializedAgent


@pytest.mark.asyncio
async def test_sequential_execution() -> None:
    agents = {
        "agent_a": MockSpecializedAgent("agent_a"),
        "agent_b": MockSpecializedAgent("agent_b"),
    }

    async def resolve(agent_id: str):
        return agents[agent_id]

    executor = DomainExecutor(resolve_agent=resolve)
    step_a = DomainExecutionStep(step_id="s1", agent_id="agent_a")
    step_b = DomainExecutionStep(step_id="s2", agent_id="agent_b", dependencies=["s1"])
    plan = DomainExecutionPlan(
        domain=DomainType.ENVIRONMENTAL,
        query="test",
        steps=[step_a, step_b],
        execution_mode=DomainExecutionMode.SEQUENTIAL,
    )
    request = AgentRequest(query="test")
    result = await executor.execute(plan, request)
    assert len(result.agent_results) == 2
    assert all(r.success for r in result.agent_results)


@pytest.mark.asyncio
async def test_parallel_execution() -> None:
    agents = {
        "agent_a": MockSpecializedAgent("agent_a"),
        "agent_b": MockSpecializedAgent("agent_b"),
    }

    async def resolve(agent_id: str):
        return agents[agent_id]

    executor = DomainExecutor(resolve_agent=resolve)
    plan = DomainExecutionPlan(
        domain=DomainType.EMERGENCY,
        query="test",
        steps=[
            DomainExecutionStep(agent_id="agent_a", parallel_group="g1"),
            DomainExecutionStep(agent_id="agent_b", parallel_group="g1"),
        ],
        execution_mode=DomainExecutionMode.PARALLEL,
    )
    result = await executor.execute(plan, AgentRequest(query="test"))
    assert len(result.agent_results) == 2


@pytest.mark.asyncio
async def test_retry_on_failure() -> None:
    call_count = {"n": 0}

    class FlakyAgent:
        @property
        def agent_id(self) -> str:
            return "flaky"

        async def invoke(self, request):
            call_count["n"] += 1
            if call_count["n"] < 2:
                raise RuntimeError("transient")
            from backend.agents.schemas.response import AgentResponse
            from backend.utils.enums import AgentStatus
            return AgentResponse(request_id=request.request_id, agent_id="flaky", content="ok", status=AgentStatus.COMPLETED)

        async def health_check(self) -> bool:
            return True

    async def resolve(_: str):
        return FlakyAgent()

    executor = DomainExecutor(resolve_agent=resolve, policy=DomainExecutionPolicy(retry_delay_seconds=0.01))
    plan = DomainExecutionPlan(
        domain=DomainType.INFRASTRUCTURE,
        query="test",
        steps=[DomainExecutionStep(agent_id="flaky", max_retries=2)],
    )
    result = await executor.execute(plan, AgentRequest(query="test"))
    assert result.agent_results[0].success
    assert result.agent_results[0].retry_attempts >= 1
