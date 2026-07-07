"""Tests for agent registry."""

import pytest

from backend.agents.supervisor.agent_registry import AgentRegistry
from backend.tests.supervisor.conftest import MockDomainSupervisor
from backend.utils.errors import DependencyNotFoundError, DependencyRegistrationError


@pytest.mark.asyncio
async def test_register_and_resolve() -> None:
    registry = AgentRegistry()
    handler = MockDomainSupervisor("test_supervisor")
    await registry.register(handler, description="Test supervisor")
    resolved = await registry.resolve("test_supervisor")
    assert resolved.supervisor_id == "test_supervisor"


@pytest.mark.asyncio
async def test_duplicate_registration_raises() -> None:
    registry = AgentRegistry()
    await registry.register(MockDomainSupervisor("dup"))
    with pytest.raises(DependencyRegistrationError):
        await registry.register(MockDomainSupervisor("dup"))


@pytest.mark.asyncio
async def test_unregister() -> None:
    registry = AgentRegistry()
    await registry.register(MockDomainSupervisor("rm"))
    assert await registry.unregister("rm") is True
    with pytest.raises(DependencyNotFoundError):
        await registry.resolve("rm")


@pytest.mark.asyncio
async def test_health_check() -> None:
    registry = AgentRegistry()
    await registry.register(MockDomainSupervisor("healthy"))
    health = await registry.health()
    assert health["healthy"] is True


@pytest.mark.asyncio
async def test_list_supervisors() -> None:
    registry = AgentRegistry()
    await registry.register(MockDomainSupervisor("a"))
    await registry.register(MockDomainSupervisor("b"))
    ids = await registry.list_ids()
    assert sorted(ids) == ["a", "b"]
