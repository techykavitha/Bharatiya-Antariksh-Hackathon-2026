"""Shared fixtures for domain supervisor tests."""

from __future__ import annotations

import pytest

from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import AgentResponse
from backend.agents.domain.domain_execution import DomainAgentHandler
from backend.utils.enums import AgentStatus


class MockSpecializedAgent:
    """Mock specialized agent for domain supervisor tests."""

    def __init__(self, agent_id: str, *, content: str | None = None) -> None:
        self._id = agent_id
        self._content = content or f"Output from {agent_id}"

    @property
    def agent_id(self) -> str:
        return self._id

    async def invoke(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(
            request_id=request.request_id,
            agent_id=self._id,
            content=self._content,
            status=AgentStatus.COMPLETED,
            structured_output={"agent": self._id},
        )

    async def health_check(self) -> bool:
        return True


@pytest.fixture
async def memory_manager() -> MemoryManager:
    return await MemoryManager.create_in_memory()
