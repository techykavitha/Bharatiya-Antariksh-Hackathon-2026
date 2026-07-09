"""Disaster response agent metrics tracking."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.agents.specialized.agent_metrics import AgentMetricsCollector
from backend.agents.specialized.disaster_response.disaster_models import EmergencyPriority


class DisasterExecutionMetrics(BaseModel):
    """Extended metrics for disaster response agent invocations."""

    agent_id: str
    request_id: str
    reasoning_time_ms: float = 0.0
    tool_usage_count: int = 0
    memory_reads: int = 0
    memory_writes: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    emergency_priority: EmergencyPriority = EmergencyPriority.ROUTINE
    emergency_priority_score: float = Field(default=0.0, ge=0.0, le=1.0)
    hazard_agents_consulted: int = 0
    decision_requests: int = 0
    rl_calls: int = 0
    knowledge_graph_queries: int = 0
    explainability_calls: int = 0
    tools_used: list[str] = Field(default_factory=list)
    total_duration_ms: float = 0.0


class DisasterMetricsCollector(AgentMetricsCollector):
    """Metrics collector with disaster-response-specific dimensions."""

    def __init__(self, *, agent_id: str, request_id: str) -> None:
        super().__init__(agent_id=agent_id, request_id=request_id)
        self._emergency_priority = EmergencyPriority.ROUTINE
        self._priority_score = 0.0
        self._hazard_agents_consulted = 0
        self._decision_requests = 0
        self._rl_calls = 0
        self._ckg_queries = 0
        self._xai_calls = 0
        self._tools_used: list[str] = []

    def set_emergency_priority(self, priority: EmergencyPriority) -> None:
        self._emergency_priority = priority

    def set_priority_score(self, score: float) -> None:
        self._priority_score = score

    def record_hazard_agents_consulted(self, count: int) -> None:
        self._hazard_agents_consulted = count

    def record_decision_request(self) -> None:
        self._decision_requests += 1

    def record_rl_call(self) -> None:
        self._rl_calls += 1

    def record_ckg_query(self, count: int = 1) -> None:
        self._ckg_queries += count

    def record_explainability_call(self) -> None:
        self._xai_calls += 1

    def record_tool_name(self, tool_name: str) -> None:
        if tool_name not in self._tools_used:
            self._tools_used.append(tool_name)

    def finalize_disaster(self) -> DisasterExecutionMetrics:
        base = self.finalize()
        return DisasterExecutionMetrics(
            agent_id=base.agent_id,
            request_id=base.request_id,
            reasoning_time_ms=base.reasoning_time_ms,
            tool_usage_count=base.tool_count,
            memory_reads=base.memory_reads,
            memory_writes=base.memory_writes,
            confidence=base.confidence,
            emergency_priority=self._emergency_priority,
            emergency_priority_score=self._priority_score,
            hazard_agents_consulted=self._hazard_agents_consulted,
            decision_requests=self._decision_requests,
            rl_calls=self._rl_calls,
            knowledge_graph_queries=self._ckg_queries,
            explainability_calls=self._xai_calls,
            tools_used=list(self._tools_used),
            total_duration_ms=base.total_duration_ms,
        )
