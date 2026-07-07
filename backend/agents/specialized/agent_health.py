"""Health monitoring for specialized agents."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class HealthStatus(StrEnum):
    """Aggregate health status for a specialized agent."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentHealth(BaseModel):
    """Health of an individual agent subsystem."""

    name: str
    healthy: bool
    message: str = ""
    latency_ms: float | None = None


class AgentHealthReport(BaseModel):
    """Full health report for a specialized agent."""

    agent_id: str
    status: HealthStatus
    initialized: bool
    tool_count: int = 0
    capability_count: int = 0
    components: list[ComponentHealth] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, str | bool | int] = Field(default_factory=dict)


class AgentHealthChecker:
    """Evaluates specialized agent health across subsystems."""

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id

    async def check(
        self,
        *,
        initialized: bool,
        tool_healthy: bool,
        memory_healthy: bool,
        capability_count: int,
        tool_count: int,
        extra_checks: list[ComponentHealth] | None = None,
    ) -> AgentHealthReport:
        components: list[ComponentHealth] = [
            ComponentHealth(name="initialization", healthy=initialized),
            ComponentHealth(name="tools", healthy=tool_healthy),
            ComponentHealth(name="memory", healthy=memory_healthy),
        ]
        if extra_checks:
            components.extend(extra_checks)

        unhealthy = [c for c in components if not c.healthy]
        if not initialized or len(unhealthy) > 1:
            status = HealthStatus.UNHEALTHY
        elif unhealthy:
            status = HealthStatus.DEGRADED
        elif initialized:
            status = HealthStatus.HEALTHY
        else:
            status = HealthStatus.UNKNOWN

        return AgentHealthReport(
            agent_id=self._agent_id,
            status=status,
            initialized=initialized,
            tool_count=tool_count,
            capability_count=capability_count,
            components=components,
        )
