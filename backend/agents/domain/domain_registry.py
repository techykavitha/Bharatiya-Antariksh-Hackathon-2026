"""Registry for domain-level supervisors in the Hyperion hierarchy."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.agents.domain.base_domain_supervisor import BaseDomainSupervisor
from backend.agents.domain.domain_context import DomainType
from backend.config.logger import get_logger
from backend.utils.errors import DependencyNotFoundError, DependencyRegistrationError

logger = get_logger(__name__)


@dataclass
class DomainSupervisorRegistration:
    """Registered domain supervisor metadata."""

    supervisor_id: str
    domain_type: DomainType
    supervisor: BaseDomainSupervisor
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    healthy: bool = True
    last_health_check: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class DomainRegistry:
    """
    Central registry for domain supervisors.

    Bridges the Climate Supervisor layer with Environmental, Infrastructure,
    and Emergency domain supervisors.
    """

    def __init__(self) -> None:
        self._registrations: dict[str, DomainSupervisorRegistration] = {}
        self._by_domain: dict[DomainType, str] = {}
        self._lock = asyncio.Lock()

    async def register_supervisor(
        self,
        supervisor: BaseDomainSupervisor,
        *,
        description: str = "",
        capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Register a domain supervisor instance."""
        supervisor_id = supervisor.supervisor_id
        domain_type = supervisor.domain_type

        async with self._lock:
            if supervisor_id in self._registrations:
                raise DependencyRegistrationError(
                    f"Domain supervisor '{supervisor_id}' is already registered",
                    details={"supervisor_id": supervisor_id},
                )
            if domain_type in self._by_domain:
                raise DependencyRegistrationError(
                    f"Domain type '{domain_type.value}' already has a registered supervisor",
                    details={"domain_type": domain_type.value},
                )

            if not supervisor.is_initialized:
                await supervisor.initialize()

            self._registrations[supervisor_id] = DomainSupervisorRegistration(
                supervisor_id=supervisor_id,
                domain_type=domain_type,
                supervisor=supervisor,
                description=description,
                capabilities=capabilities or [t.name for t in supervisor.supported_tasks],
                metadata=metadata or {},
            )
            self._by_domain[domain_type] = supervisor_id

        logger.info("domain_supervisor_registered", supervisor_id=supervisor_id, domain=domain_type.value)

    async def unregister_supervisor(self, supervisor_id: str) -> bool:
        async with self._lock:
            registration = self._registrations.pop(supervisor_id, None)
            if registration is None:
                return False
            self._by_domain.pop(registration.domain_type, None)
        logger.info("domain_supervisor_unregistered", supervisor_id=supervisor_id)
        return True

    async def resolve(self, supervisor_id: str) -> BaseDomainSupervisor:
        async with self._lock:
            registration = self._registrations.get(supervisor_id)
            if registration is None:
                raise DependencyNotFoundError(
                    f"Domain supervisor '{supervisor_id}' is not registered",
                    details={"supervisor_id": supervisor_id},
                )
            return registration.supervisor

    async def resolve_by_domain(self, domain_type: DomainType) -> BaseDomainSupervisor:
        async with self._lock:
            supervisor_id = self._by_domain.get(domain_type)
            if supervisor_id is None:
                raise DependencyNotFoundError(
                    f"No supervisor registered for domain '{domain_type.value}'",
                    details={"domain_type": domain_type.value},
                )
            return self._registrations[supervisor_id].supervisor

    async def list(self) -> list[DomainSupervisorRegistration]:
        async with self._lock:
            return list(self._registrations.values())

    async def list_ids(self) -> list[str]:
        async with self._lock:
            return sorted(self._registrations.keys())

    async def health(self, supervisor_id: str | None = None) -> dict[str, bool]:
        results: dict[str, bool] = {}
        async with self._lock:
            targets = (
                {supervisor_id: self._registrations[supervisor_id]}
                if supervisor_id
                else dict(self._registrations)
            )

        for sid, registration in targets.items():
            try:
                report = await registration.supervisor.health()
                healthy = report.healthy
            except Exception:
                healthy = False
            async with self._lock:
                if sid in self._registrations:
                    self._registrations[sid].healthy = healthy
                    self._registrations[sid].last_health_check = datetime.now(timezone.utc)
            results[sid] = healthy

        return results

    async def register_all_defaults(self, memory: Any) -> DomainRegistry:
        """Register all three built-in domain supervisors."""
        from backend.agents.domain.emergency_supervisor import EmergencySupervisor
        from backend.agents.domain.environmental_supervisor import EnvironmentalSupervisor
        from backend.agents.domain.infrastructure_supervisor import InfrastructureSupervisor

        for supervisor in (
            EnvironmentalSupervisor(memory=memory),
            InfrastructureSupervisor(memory=memory),
            EmergencySupervisor(memory=memory),
        ):
            await self.register_supervisor(supervisor)
        return self
