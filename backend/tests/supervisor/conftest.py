"""Shared fixtures for supervisor tests."""

from __future__ import annotations

import pytest

from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import AgentResponse
from backend.agents.supervisor.agent_registry import AgentRegistry
from backend.agents.supervisor.climate_supervisor import ClimateSupervisor
from backend.utils.enums import AgentStatus


class MockDomainSupervisor:
    """Mock domain supervisor for integration tests."""

    def __init__(self, supervisor_id: str, *, content: str | None = None) -> None:
        self._id = supervisor_id
        self._content = content or f"Response from {supervisor_id}"

    @property
    def supervisor_id(self) -> str:
        return self._id

    async def invoke(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(
            request_id=request.request_id,
            agent_id=self._id,
            content=self._content,
            status=AgentStatus.COMPLETED,
            structured_output={"supervisor": self._id},
        )

    async def health_check(self) -> bool:
        return True


@pytest.fixture
async def memory_manager() -> MemoryManager:
    return await MemoryManager.create_in_memory()


@pytest.fixture
async def registry() -> AgentRegistry:
    reg = AgentRegistry()
    for sid in (
        "simulation_supervisor",
        "agriculture_supervisor",
        "water_resources_supervisor",
        "general_qa_supervisor",
        "forecast_supervisor",
    ):
        await reg.register(MockDomainSupervisor(sid))
    return reg


@pytest.fixture
async def supervisor(memory_manager: MemoryManager, registry: AgentRegistry) -> ClimateSupervisor:
    sup = ClimateSupervisor(memory=memory_manager, registry=registry)
    await sup.initialize()
    return sup
