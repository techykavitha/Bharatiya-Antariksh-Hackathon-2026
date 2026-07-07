"""Tests for BaseAgent and AbstractTool."""

from __future__ import annotations

from typing import Any

import pytest

from backend.agents.base import BaseAgent
from backend.agents.memory.interfaces import AgentMemory, MemoryEntry
from backend.agents.schemas import AgentRequest, AgentResponse
from backend.agents.tools import AbstractTool, ToolInput
from backend.utils.enums import AgentRole, AgentStatus, ToolCategory
from backend.utils.errors import ToolNotFoundError


class _StubMemory(AgentMemory):
    """In-memory stub for testing BaseAgent memory methods."""

    def __init__(self) -> None:
        self._store: dict[str, MemoryEntry] = {}

    @property
    def backend_name(self) -> str:
        return "stub"

    async def write(self, key: str, value: Any, *, metadata: dict[str, Any] | None = None) -> None:
        self._store[key] = MemoryEntry(key=key, value=value, metadata=metadata or {})

    async def read(self, key: str) -> MemoryEntry | None:
        return self._store.get(key)

    async def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

    async def search(self, query: str, *, limit: int = 10, filters: dict[str, Any] | None = None) -> list[MemoryEntry]:
        return list(self._store.values())[:limit]

    async def clear(self, namespace: str | None = None) -> int:
        count = len(self._store)
        self._store.clear()
        return count


class _EchoTool(AbstractTool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echoes input parameters"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.COMMUNICATION

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"message": {"type": "string"}}}

    async def _execute(self, tool_input: ToolInput) -> Any:
        return tool_input.parameters.get("message", "")


class _TestAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            agent_id="test-agent",
            role=AgentRole.DOMAIN,
            description="Test domain agent",
            tools=[_EchoTool()],
            memory_backends={"stub": _StubMemory()},
        )

    async def reason(self, request: AgentRequest) -> list[str]:
        return [f"Analyzing: {request.query}"]

    async def generate_response(
        self,
        request: AgentRequest,
        *,
        reasoning: list[str],
        tool_results: list,
        memory_references: list[str],
    ) -> AgentResponse:
        content = f"Answer to: {request.query}"
        if tool_results:
            content += f" | tool={tool_results[0].output}"
        return AgentResponse(
            request_id=request.request_id,
            agent_id=self.agent_id,
            content=content,
            status=AgentStatus.COMPLETED,
            reasoning_trace=reasoning,
            memory_references=memory_references,
        )


@pytest.fixture
def agent() -> _TestAgent:
    return _TestAgent()


@pytest.mark.asyncio
async def test_agent_initialize(agent: _TestAgent) -> None:
    await agent.initialize()
    assert agent.is_initialized
    assert agent.status == AgentStatus.IDLE


@pytest.mark.asyncio
async def test_agent_invoke(agent: _TestAgent) -> None:
    request = AgentRequest(query="What is the temperature?")
    response = await agent.invoke(request)
    assert response.is_success
    assert "temperature" in response.content.lower()
    assert len(response.reasoning_trace) == 1


@pytest.mark.asyncio
async def test_agent_use_tools(agent: _TestAgent) -> None:
    await agent.initialize()
    results = await agent.use_tools([("echo", {"message": "hello"})])
    assert len(results) == 1
    assert results[0].output == "hello"


@pytest.mark.asyncio
async def test_agent_tool_not_found(agent: _TestAgent) -> None:
    await agent.initialize()
    with pytest.raises(ToolNotFoundError):
        await agent.use_tools([("missing", {})])


@pytest.mark.asyncio
async def test_agent_memory_roundtrip(agent: _TestAgent) -> None:
    await agent.initialize()
    await agent.write_memory("key1", {"data": 42}, backend="stub")
    entry = await agent.read_memory("key1", backend="stub")
    assert entry is not None
    assert entry.value == {"data": 42}
