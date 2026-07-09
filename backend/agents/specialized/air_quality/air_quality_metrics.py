"""Air quality agent metrics tracking."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.agents.specialized.agent_metrics import AgentMetricsCollector
from backend.agents.specialized.air_quality.air_quality_models import AQICategory


class AirQualityExecutionMetrics(BaseModel):
    """Extended metrics for air quality agent invocations."""

    agent_id: str
    request_id: str
    reasoning_time_ms: float = 0.0
    tool_usage_count: int = 0
    memory_reads: int = 0
    memory_writes: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    aqi: int = Field(default=0, ge=0)
    aqi_category: AQICategory = AQICategory.GOOD
    health_risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    peer_agents_consulted: int = 0
    decision_requests: int = 0
    rl_calls: int = 0
    knowledge_graph_queries: int = 0
    explainability_calls: int = 0
    tools_used: list[str] = Field(default_factory=list)
    total_duration_ms: float = 0.0


class AirQualityMetricsCollector(AgentMetricsCollector):
    """Metrics collector with air-quality-specific dimensions."""

    def __init__(self, *, agent_id: str, request_id: str) -> None:
        super().__init__(agent_id=agent_id, request_id=request_id)
        self._aqi = 0
        self._aqi_category = AQICategory.GOOD
        self._health_risk_score = 0.0
        self._peer_agents_consulted = 0
        self._decision_requests = 0
        self._rl_calls = 0
        self._ckg_queries = 0
        self._xai_calls = 0
        self._tools_used: list[str] = []

    def set_aqi(self, aqi: int, category: AQICategory) -> None:
        self._aqi = aqi
        self._aqi_category = category

    def set_health_risk_score(self, score: float) -> None:
        self._health_risk_score = score

    def record_peer_agents_consulted(self, count: int) -> None:
        self._peer_agents_consulted = count

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

    def finalize_air_quality(self) -> AirQualityExecutionMetrics:
        base = self.finalize()
        return AirQualityExecutionMetrics(
            agent_id=base.agent_id,
            request_id=base.request_id,
            reasoning_time_ms=base.reasoning_time_ms,
            tool_usage_count=base.tool_count,
            memory_reads=base.memory_reads,
            memory_writes=base.memory_writes,
            confidence=base.confidence,
            aqi=self._aqi,
            aqi_category=self._aqi_category,
            health_risk_score=self._health_risk_score,
            peer_agents_consulted=self._peer_agents_consulted,
            decision_requests=self._decision_requests,
            rl_calls=self._rl_calls,
            knowledge_graph_queries=self._ckg_queries,
            explainability_calls=self._xai_calls,
            tools_used=list(self._tools_used),
            total_duration_ms=base.total_duration_ms,
        )
