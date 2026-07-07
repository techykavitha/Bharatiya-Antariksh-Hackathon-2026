"""Heatwave agent metrics tracking."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.agents.specialized.agent_metrics import AgentMetricsCollector
from backend.agents.specialized.heatwave.heatwave_models import HeatRiskLevel, HeatwaveSeverity


class HeatwaveExecutionMetrics(BaseModel):
    """Extended metrics for heatwave agent invocations."""

    agent_id: str
    request_id: str
    reasoning_time_ms: float = 0.0
    tool_usage_count: int = 0
    memory_reads: int = 0
    memory_writes: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    heatwave_severity: HeatwaveSeverity = HeatwaveSeverity.NONE
    heat_risk_level: HeatRiskLevel = HeatRiskLevel.MINIMAL
    decision_requests: int = 0
    rl_calls: int = 0
    tools_used: list[str] = Field(default_factory=list)
    total_duration_ms: float = 0.0


class HeatwaveMetricsCollector(AgentMetricsCollector):
    """Metrics collector with heatwave-specific dimensions."""

    def __init__(self, *, agent_id: str, request_id: str) -> None:
        super().__init__(agent_id=agent_id, request_id=request_id)
        self._severity = HeatwaveSeverity.NONE
        self._risk_level = HeatRiskLevel.MINIMAL
        self._decision_requests = 0
        self._rl_calls = 0
        self._tools_used: list[str] = []

    def set_severity(self, severity: HeatwaveSeverity) -> None:
        self._severity = severity

    def set_risk_level(self, risk: HeatRiskLevel) -> None:
        self._risk_level = risk

    def record_decision_request(self) -> None:
        self._decision_requests += 1

    def record_rl_call(self) -> None:
        self._rl_calls += 1

    def record_tool_name(self, tool_name: str) -> None:
        if tool_name not in self._tools_used:
            self._tools_used.append(tool_name)

    def finalize_heatwave(self) -> HeatwaveExecutionMetrics:
        base = self.finalize()
        return HeatwaveExecutionMetrics(
            agent_id=base.agent_id,
            request_id=base.request_id,
            reasoning_time_ms=base.reasoning_time_ms,
            tool_usage_count=base.tool_count,
            memory_reads=base.memory_reads,
            memory_writes=base.memory_writes,
            confidence=base.confidence,
            heatwave_severity=self._severity,
            heat_risk_level=self._risk_level,
            decision_requests=self._decision_requests,
            rl_calls=self._rl_calls,
            tools_used=list(self._tools_used),
            total_duration_ms=base.total_duration_ms,
        )
