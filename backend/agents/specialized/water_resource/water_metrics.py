"""Water resource agent metrics tracking."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.agents.specialized.agent_metrics import AgentMetricsCollector
from backend.agents.specialized.water_resource.water_models import WaterStressLevel


class WaterExecutionMetrics(BaseModel):
    """Extended metrics for water resource agent invocations."""

    agent_id: str
    request_id: str
    reasoning_time_ms: float = 0.0
    tool_usage_count: int = 0
    memory_reads: int = 0
    memory_writes: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    water_stress_level: WaterStressLevel = WaterStressLevel.NONE
    reservoir_analyses: int = 0
    decision_requests: int = 0
    tools_used: list[str] = Field(default_factory=list)
    total_duration_ms: float = 0.0


class WaterMetricsCollector(AgentMetricsCollector):
    """Metrics collector with water-specific dimensions."""

    def __init__(self, *, agent_id: str, request_id: str) -> None:
        super().__init__(agent_id=agent_id, request_id=request_id)
        self._stress_level = WaterStressLevel.NONE
        self._decision_requests = 0
        self._reservoir_analyses = 0
        self._tools_used: list[str] = []

    def set_stress_level(self, stress: WaterStressLevel) -> None:
        self._stress_level = stress

    def record_decision_request(self) -> None:
        self._decision_requests += 1

    def record_reservoir_analysis(self) -> None:
        self._reservoir_analyses += 1

    def record_tool_name(self, tool_name: str) -> None:
        if tool_name not in self._tools_used:
            self._tools_used.append(tool_name)

    def finalize_water(self) -> WaterExecutionMetrics:
        base = self.finalize()
        return WaterExecutionMetrics(
            agent_id=base.agent_id,
            request_id=base.request_id,
            reasoning_time_ms=base.reasoning_time_ms,
            tool_usage_count=base.tool_count,
            memory_reads=base.memory_reads,
            memory_writes=base.memory_writes,
            confidence=base.confidence,
            water_stress_level=self._stress_level,
            reservoir_analyses=self._reservoir_analyses,
            decision_requests=self._decision_requests,
            tools_used=list(self._tools_used),
            total_duration_ms=base.total_duration_ms,
        )
