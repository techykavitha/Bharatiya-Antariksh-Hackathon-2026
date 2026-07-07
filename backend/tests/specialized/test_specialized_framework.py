"""Tests for the specialized agent framework."""

from __future__ import annotations

from typing import Any

import pytest

from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.schemas.request import AgentRequest
from backend.agents.specialized import (
    AgentCapability,
    AgentCommunicationInterface,
    AgentExecutionEngine,
    AgentExecutionMode,
    AgentExecutionPlan,
    AgentExecutionStep,
    BaseSpecializedAgent,
    CapabilityCategory,
    ExecutionTaskType,
    SpecializedAgentRegistry,
    SpecializedRLEngineInterface,
    ToolCallSpec,
    ToolManager,
)
from backend.agents.schemas.response import AgentResponse
from backend.agents.state.workflow_state import create_initial_workflow_state
from backend.agents.tools.abstract_tool import AbstractTool, ToolInput
from backend.utils.enums import AgentStatus, ToolCategory


class _EchoTool(AbstractTool):
    @property
    def name(self) -> str:
        return "echo_tool"

    @property
    def description(self) -> str:
        return "Echoes input parameters"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"message": {"type": "string"}}}

    async def _execute(self, tool_input: ToolInput) -> Any:
        return tool_input.parameters.get("message", "")


class _MockRL(SpecializedRLEngineInterface):
    async def request_policy(
        self,
        scenario_id: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {"scenario_id": scenario_id, "policy": "mock"}

    async def evaluate_action(
        self,
        action: dict[str, Any],
        *,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {"score": 0.8, "action": action}

    async def rank_actions(
        self,
        actions: list[dict[str, Any]],
        *,
        criteria: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return sorted(actions, key=lambda a: a.get("priority", 0), reverse=True)


class _MockComm(AgentCommunicationInterface):
    async def call_agent(
        self,
        agent_id: str,
        request: AgentRequest,
        *,
        timeout_seconds: float | None = None,
    ) -> AgentResponse:
        return AgentResponse(
            request_id=request.request_id,
            agent_id=agent_id,
            content=f"Delegated response from {agent_id}",
            status=AgentStatus.COMPLETED,
        )

    async def broadcast(
        self,
        agent_ids: list[str],
        request: AgentRequest,
    ) -> list[AgentResponse]:
        return [
            AgentResponse(
                request_id=request.request_id,
                agent_id=aid,
                content=f"Broadcast from {aid}",
            )
            for aid in agent_ids
        ]

    async def wait_for_response(
        self,
        correlation_id: str,
        *,
        timeout_seconds: float = 120,
    ) -> AgentResponse:
        return AgentResponse(
            request_id=correlation_id,
            agent_id="async_agent",
            content="Async response",
        )


class _FrameworkTestAgent(BaseSpecializedAgent):
    """Concrete agent for framework validation — not a climate agent."""

    async def declare_capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                capability_id="analysis",
                name="Generic Analysis",
                category=CapabilityCategory.ANALYSIS,
                keywords=["analyze", "assess", "evaluate"],
            ),
        ]

    async def _on_generate_recommendations(self, context, reasoning, reflection) -> list[str]:
        return ["Review results and validate with domain experts."]


@pytest.fixture
async def test_agent(memory_manager: MemoryManager) -> _FrameworkTestAgent:
    agent = _FrameworkTestAgent(
        agent_id="framework_test_agent",
        description="Framework validation agent",
        memory=memory_manager,
        tools=[_EchoTool()],
        rl_engine=_MockRL(),
        agent_communication=_MockComm(),
    )
    await agent.initialize()
    return agent


@pytest.mark.asyncio
async def test_agent_initialize(test_agent: _FrameworkTestAgent) -> None:
    assert test_agent.is_initialized
    caps = await test_agent.capability_registry.list_capabilities()
    assert len(caps) == 1
    assert test_agent.tool_manager.has_tool("echo_tool")


@pytest.mark.asyncio
async def test_invoke_pipeline(test_agent: _FrameworkTestAgent) -> None:
    request = AgentRequest(
        query="Analyze regional conditions",
        tool_names=["echo_tool"],
        context={"message": "test payload"},
    )
    response = await test_agent.invoke(request)
    assert response.agent_id == "framework_test_agent"
    assert response.is_success
    assert response.content
    assert test_agent.last_report is not None
    assert test_agent.last_metrics is not None


@pytest.mark.asyncio
async def test_tool_manager_parallel() -> None:
    manager = ToolManager(agent_id="tool_test")
    manager.register(_EchoTool())
    specs = [
        ToolCallSpec(tool_name="echo_tool", parameters={"message": "a"}),
        ToolCallSpec(tool_name="echo_tool", parameters={"message": "b"}),
    ]
    from backend.agents.specialized.agent_tools import ToolExecutionMode

    result = await manager.execute(specs, mode=ToolExecutionMode.PARALLEL)
    assert result.success_count == 2


@pytest.mark.asyncio
async def test_specialized_registry(test_agent: _FrameworkTestAgent) -> None:
    registry = SpecializedAgentRegistry()
    await registry.register(test_agent, name="Framework Test")
    resolved = await registry.resolve("framework_test_agent")
    assert resolved.agent_id == "framework_test_agent"
    health = await registry.health()
    assert health["framework_test_agent"] is True


@pytest.mark.asyncio
async def test_execution_engine_retry() -> None:
    engine = AgentExecutionEngine(agent_id="exec_test")
    calls: list[int] = []

    async def flaky_handler(context, step: AgentExecutionStep) -> str:
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError("transient")
        return "ok"

    plan = AgentExecutionPlan(
        agent_id="exec_test",
        steps=[
            AgentExecutionStep(
                task_type=ExecutionTaskType.REASONING,
                name="reason",
                max_retries=2,
            ),
        ],
    )
    from backend.agents.specialized.agent_context import AgentContext

    context = AgentContext(
        agent_id="exec_test",
        request=AgentRequest(query="test"),
    )
    outcome = await engine.execute(
        plan,
        context,
        {ExecutionTaskType.REASONING: flaky_handler},
    )
    assert outcome.step_outcomes[0].success
    assert outcome.step_outcomes[0].retry_attempts == 1


@pytest.mark.asyncio
async def test_as_graph_node(test_agent: _FrameworkTestAgent) -> None:
    state = create_initial_workflow_state(metadata={"query": "Analyze test scenario"})
    update = await test_agent.as_graph_node(state)
    assert "called_agents" in update
    assert "framework_test_agent" in update["called_agents"]


@pytest.mark.asyncio
async def test_health_check(test_agent: _FrameworkTestAgent) -> None:
    report = await test_agent.health()
    assert report.agent_id == "framework_test_agent"
    assert await test_agent.health_check() is True


@pytest.mark.asyncio
async def test_rl_interface(test_agent: _FrameworkTestAgent) -> None:
    from backend.agents.specialized.agent_context import AgentContext

    context = AgentContext(
        agent_id=test_agent.agent_id,
        request=AgentRequest(query="policy test", current_scenario="sc-1"),
    )
    policy = await test_agent.request_rl(context)
    assert policy.get("policy") == "mock"


@pytest.mark.asyncio
async def test_reflection_low_confidence() -> None:
    from backend.agents.specialized.agent_reflection import ReflectionEngine
    from backend.agents.specialized.agent_reasoning import ReasoningResult
    from backend.agents.specialized.agent_context import AgentContext

    engine = ReflectionEngine(agent_id="reflect_test", confidence_threshold=0.8)
    context = AgentContext(
        agent_id="reflect_test",
        request=AgentRequest(query="test"),
    )
    reasoning = ReasoningResult(overall_confidence=0.2)
    result = await engine.evaluate(context, reasoning)
    assert result.should_retry_reasoning
    assert any(f.signal.value == "low_confidence" for f in result.findings)
