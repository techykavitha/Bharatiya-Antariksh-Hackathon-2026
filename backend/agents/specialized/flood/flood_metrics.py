"""Flood agent metrics tracking."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.agents.specialized.agent_metrics import AgentMetricsCollector
from backend.agents.specialized.flood.flood_models import FloodRiskLevel, FloodSeverity


class FloodExecutionMetrics(BaseModel):
    """Extended metrics for flood agent invocations."""

    agent_id: str
    request_id: str
    reasoning_time_ms: float = 0.0
    tool_usage_count: int = 0
    memory_reads: int = 0
    memory_writes: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    flood_severity: FloodSeverity = FloodSeverity.NONE
    flood_risk_level: FloodRiskLevel = FloodRiskLevel.MINIMAL
    decision_requests: int = 0
    tools_used: list[str] = Field(default_factory=list)
    total_duration_ms: float = 0.0


class FloodMetricsCollector(AgentMetricsCollector):
    """Metrics collector with flood-specific dimensions."""

    def __init__(self, *, agent_id: str, request_id: str) -> None:
        super().__init__(agent_id=agent_id, request_id=request_id)
        self._severity = FloodSeverity.NONE
        self._risk_level = FloodRiskLevel.MINIMAL
        self._decision_requests = 0
        self._tools_used: list[str] = []

    def set_severity(self, severity: FloodSeverity) -> None:
        self._severity = severity

    def set_risk_level(self, risk: FloodRiskLevel) -> None:
        self._risk_level = risk

    def record_decision_request(self) -> None:
        self._decision_requests += 1

    def record_tool_name(self, tool_name: str) -> None:
        if tool_name not in self._tools_used:
            self._tools_used.append(tool_name)

    def finalize_flood(self) -> FloodExecutionMetrics:
        base = self.finalize()
        return FloodExecutionMetrics(
            agent_id=base.agent_id,
            request_id=base.request_id,
            reasoning_time_ms=base.reasoning_time_ms,
            tool_usage_count=base.tool_count,
            memory_reads=base.memory_reads,
            memory_writes=base.memory_writes,
            confidence=base.confidence,
            flood_severity=self._severity,
            flood_risk_level=self._risk_level,
            decision_requests=self._decision_requests,
            tools_used=list(self._tools_used),
            total_duration_ms=base.total_duration_ms,
        )
