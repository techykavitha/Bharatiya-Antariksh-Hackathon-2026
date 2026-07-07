"""Tests for domain registry."""

import pytest

from backend.agents.domain import (
    DomainRegistry,
    DomainType,
    EmergencySupervisor,
    EnvironmentalSupervisor,
    InfrastructureSupervisor,
)
from backend.agents.memory.memory_manager import MemoryManager
from backend.utils.errors import DependencyNotFoundError, DependencyRegistrationError


@pytest.mark.asyncio
async def test_register_and_resolve(memory_manager: MemoryManager) -> None:
    registry = DomainRegistry()
    supervisor = EnvironmentalSupervisor(memory=memory_manager)
    await registry.register_supervisor(supervisor)
    resolved = await registry.resolve("environmental_supervisor")
    assert resolved.supervisor_id == "environmental_supervisor"


@pytest.mark.asyncio
async def test_register_all_defaults(memory_manager: MemoryManager) -> None:
    registry = DomainRegistry()
    await registry.register_all_defaults(memory_manager)
    ids = await registry.list_ids()
    assert sorted(ids) == [
        "emergency_supervisor",
        "environmental_supervisor",
        "infrastructure_supervisor",
    ]


@pytest.mark.asyncio
async def test_resolve_by_domain(memory_manager: MemoryManager) -> None:
    registry = DomainRegistry()
    await registry.register_supervisor(InfrastructureSupervisor(memory=memory_manager))
    supervisor = await registry.resolve_by_domain(DomainType.INFRASTRUCTURE)
    assert supervisor.supervisor_id == "infrastructure_supervisor"


@pytest.mark.asyncio
async def test_duplicate_domain_raises(memory_manager: MemoryManager) -> None:
    registry = DomainRegistry()
    await registry.register_supervisor(EnvironmentalSupervisor(memory=memory_manager))
    with pytest.raises(DependencyRegistrationError):
        await registry.register_supervisor(EnvironmentalSupervisor(memory=memory_manager))


@pytest.mark.asyncio
async def test_unregister(memory_manager: MemoryManager) -> None:
    registry = DomainRegistry()
    await registry.register_supervisor(EmergencySupervisor(memory=memory_manager))
    assert await registry.unregister_supervisor("emergency_supervisor") is True
    with pytest.raises(DependencyNotFoundError):
        await registry.resolve("emergency_supervisor")


@pytest.mark.asyncio
async def test_health(memory_manager: MemoryManager) -> None:
    registry = DomainRegistry()
    await registry.register_all_defaults(memory_manager)
    health = await registry.health()
    assert all(health.values())
