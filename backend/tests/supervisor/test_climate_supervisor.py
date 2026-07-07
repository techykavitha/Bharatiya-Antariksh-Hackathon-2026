"""Integration tests for Climate Supervisor."""

import pytest

from backend.agents.schemas.request import AgentRequest
from backend.agents.supervisor.climate_supervisor import ClimateSupervisor
from backend.agents.supervisor.execution_context import SupervisorIntent
from backend.agents.supervisor.graph_builder import build_graph, compile_graph
from backend.utils.enums import AgentStatus


@pytest.mark.asyncio
async def test_supervisor_initialize(supervisor: ClimateSupervisor) -> None:
    assert supervisor.is_initialized


@pytest.mark.asyncio
async def test_classify_intent(supervisor: ClimateSupervisor) -> None:
    result = await supervisor.classify_intent("What is the forecast for Delhi tomorrow?")
    assert result.intent == SupervisorIntent.FORECAST


@pytest.mark.asyncio
async def test_process_request_what_if(supervisor: ClimateSupervisor) -> None:
    request = AgentRequest(query="What happens if rainfall decreases 20% in Karnataka?")
    response = await supervisor.process_request(request, session_id="test-session")
    assert response.intent == SupervisorIntent.WHAT_IF
    assert response.content
    assert response.execution_result.step_results


@pytest.mark.asyncio
async def test_process_request_general_qa(supervisor: ClimateSupervisor) -> None:
    request = AgentRequest(query="Hello, what can you help me with?")
    response = await supervisor.process_request(request)
    assert response.status in (AgentStatus.COMPLETED, AgentStatus.FAILED)


@pytest.mark.asyncio
async def test_graph_build_and_compile(supervisor: ClimateSupervisor) -> None:
    graph = build_graph(supervisor)
    compiled = compile_graph(graph)
    assert compiled is not None


@pytest.mark.asyncio
async def test_metrics_exposed(supervisor: ClimateSupervisor) -> None:
    request = AgentRequest(query="Generate a climate report for Tamil Nadu")
    response = await supervisor.process_request(request)
    assert "execution_duration_ms" in response.metrics
    assert "supervisor_count" in response.metrics


@pytest.mark.asyncio
async def test_merge_results(supervisor: ClimateSupervisor) -> None:
    from backend.agents.supervisor.execution_context import ExecutionResult, StepExecutionResult, StepStatus
    from backend.agents.schemas.response import AgentResponse

    step_result = StepExecutionResult(
        step_id="s1",
        supervisor_id="test",
        status=StepStatus.COMPLETED,
        response=AgentResponse(request_id="r1", agent_id="test", content="Test output"),
    )
    execution = ExecutionResult(plan_id="p1", step_results=[step_result])
    merged = await supervisor.merge_results(execution)
    assert "Test output" in merged.content
