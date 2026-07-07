"""Agent registry for domain supervisor discovery and health management."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.agents.supervisor.execution_context import DomainSupervisorHandler
from backend.config.logger import get_logger
from backend.utils.errors import DependencyNotFoundError, DependencyRegistrationError

logger = get_logger(__name__)


@dataclass
class SupervisorRegistration:
    """Registered domain supervisor metadata."""

    supervisor_id: str
    handler: DomainSupervisorHandler
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    healthy: bool = True
    last_health_check: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRegistry:
    """
    Central registry for domain supervisor handlers.

    Future domain supervisors register themselves at application startup.
  Supports discovery, resolution, listing, and health monitoring.
    """

    def __init__(self) -> None:
        self._registrations: dict[str, SupervisorRegistration] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        handler: DomainSupervisorHandler,
        *,
        description: str = "",
        capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Register a domain supervisor handler."""
        supervisor_id = handler.supervisor_id
        async with self._lock:
            if supervisor_id in self._registrations:
                raise DependencyRegistrationError(
                    f"Supervisor '{supervisor_id}' is already registered",
                    details={"supervisor_id": supervisor_id},
                )
            self._registrations[supervisor_id] = SupervisorRegistration(
                supervisor_id=supervisor_id,
                handler=handler,
                description=description,
                capabilities=capabilities or [],
                metadata=metadata or {},
            )
        logger.info("supervisor_registered", supervisor_id=supervisor_id)

    async def unregister(self, supervisor_id: str) -> bool:
        """Remove a supervisor from the registry."""
        async with self._lock:
            if supervisor_id not in self._registrations:
                return False
            del self._registrations[supervisor_id]
        logger.info("supervisor_unregistered", supervisor_id=supervisor_id)
        return True

    async def resolve(self, supervisor_id: str) -> DomainSupervisorHandler:
        """Resolve a registered supervisor handler by ID."""
        async with self._lock:
            registration = self._registrations.get(supervisor_id)
            if registration is None:
                raise DependencyNotFoundError(
                    f"Supervisor '{supervisor_id}' is not registered",
                    details={"supervisor_id": supervisor_id},
                )
            return registration.handler

    async def list(self) -> list[SupervisorRegistration]:
        """Return all registered supervisors."""
        async with self._lock:
            return list(self._registrations.values())

    async def list_ids(self) -> list[str]:
        """Return sorted list of registered supervisor IDs."""
        async with self._lock:
            return sorted(self._registrations.keys())

    async def health(self, supervisor_id: str | None = None) -> dict[str, bool]:
        """
        Run health checks on one or all registered supervisors.

        Returns a mapping of supervisor_id → healthy boolean.
        """
        results: dict[str, bool] = {}
        async with self._lock:
            targets = (
                {supervisor_id: self._registrations[supervisor_id]}
                if supervisor_id
                else dict(self._registrations)
            )

        for sid, registration in targets.items():
            try:
                healthy = await registration.handler.health_check()
            except Exception:
                healthy = False
            async with self._lock:
                if sid in self._registrations:
                    self._registrations[sid].healthy = healthy
                    self._registrations[sid].last_health_check = datetime.now(timezone.utc)
            results[sid] = healthy
            logger.debug("supervisor_health_check", supervisor_id=sid, healthy=healthy)

        return results

    async def is_registered(self, supervisor_id: str) -> bool:
        async with self._lock:
            return supervisor_id in self._registrations

    async def count(self) -> int:
        async with self._lock:
            return len(self._registrations)
