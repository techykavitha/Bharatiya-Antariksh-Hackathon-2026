"""Global registry for specialized climate agents."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from backend.agents.specialized.agent_execution import SpecializedAgentHandler
from backend.config.logger import get_logger
from backend.utils.errors import DependencyNotFoundError, DependencyRegistrationError

logger = get_logger(__name__)


class SpecializedAgentRegistration(BaseModel):
    """Metadata for a registered specialized agent."""

    agent_id: str
    name: str
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    healthy: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class SpecializedAgentRegistry:
    """
    Global registry for specialized agent discovery and health tracking.

    Domain supervisors resolve agents through their own ``InternalAgentRegistry``;
    this registry supports application-level bootstrap and cross-domain discovery.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, SpecializedAgentHandler] = {}
        self._metadata: dict[str, SpecializedAgentRegistration] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        handler: SpecializedAgentHandler,
        *,
        name: str | None = None,
        description: str = "",
        capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        agent_id = handler.agent_id
        async with self._lock:
            if agent_id in self._handlers:
                raise DependencyRegistrationError(
                    f"Specialized agent '{agent_id}' is already registered",
                    details={"agent_id": agent_id},
                )
            self._handlers[agent_id] = handler
            self._metadata[agent_id] = SpecializedAgentRegistration(
                agent_id=agent_id,
                name=name or agent_id,
                description=description,
                capabilities=capabilities or [],
                metadata=metadata or {},
            )
            logger.info("specialized_agent_registered", agent_id=agent_id)

    async def unregister(self, agent_id: str) -> bool:
        async with self._lock:
            if agent_id not in self._handlers:
                return False
            del self._handlers[agent_id]
            self._metadata.pop(agent_id, None)
            logger.info("specialized_agent_unregistered", agent_id=agent_id)
            return True

    async def resolve(self, agent_id: str) -> SpecializedAgentHandler:
        async with self._lock:
            handler = self._handlers.get(agent_id)
        if handler is None:
            raise DependencyNotFoundError(
                f"Specialized agent '{agent_id}' is not registered",
                details={"agent_id": agent_id},
            )
        return handler

    async def list_agents(self) -> list[SpecializedAgentRegistration]:
        async with self._lock:
            return list(self._metadata.values())

    async def list_ids(self) -> list[str]:
        async with self._lock:
            return list(self._handlers.keys())

    async def is_registered(self, agent_id: str) -> bool:
        async with self._lock:
            return agent_id in self._handlers

    async def health(self, agent_id: str | None = None) -> dict[str, bool]:
        async with self._lock:
            targets = (
                {agent_id: self._handlers[agent_id]}
                if agent_id
                else dict(self._handlers)
            )

        results: dict[str, bool] = {}
        for aid, handler in targets.items():
            try:
                results[aid] = await handler.health_check()
            except Exception:
                results[aid] = False
            async with self._lock:
                if aid in self._metadata:
                    self._metadata[aid].healthy = results[aid]
        return results

    async def mark_invoked(self, agent_id: str) -> None:
        async with self._lock:
            if agent_id in self._metadata:
                self._metadata[agent_id].metadata["last_invoked"] = True
