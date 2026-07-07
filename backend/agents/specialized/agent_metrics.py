"""Execution metrics for specialized agents."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from pydantic import BaseModel, Field


class AgentExecutionMetrics(BaseModel):
    """Metrics collected during a specialized agent invocation."""

    agent_id: str
    request_id: str
    reasoning_time_ms: float = 0.0
    reflection_count: int = 0
    tool_count: int = 0
    tool_duration_ms: float = 0.0
    memory_reads: int = 0
    memory_writes: int = 0
    agent_calls: int = 0
    rl_calls: int = 0
    validation_count: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    total_duration_ms: float = 0.0
    metadata: dict[str, float | int | str] = Field(default_factory=dict)


class AgentMetricsCollector:
    """Mutable metrics accumulator for a single agent invocation."""

    def __init__(self, *, agent_id: str, request_id: str) -> None:
        self._agent_id = agent_id
        self._request_id = request_id
        self._start = time.perf_counter()
        self._metrics = AgentExecutionMetrics(agent_id=agent_id, request_id=request_id)

    @property
    def metrics(self) -> AgentExecutionMetrics:
        return self._metrics

    def record_reasoning(self, duration_ms: float) -> None:
        self._metrics.reasoning_time_ms += duration_ms

    def record_reflection(self) -> None:
        self._metrics.reflection_count += 1

    def record_tools(self, count: int, duration_ms: float) -> None:
        self._metrics.tool_count += count
        self._metrics.tool_duration_ms += duration_ms

    def record_memory_read(self, count: int = 1) -> None:
        self._metrics.memory_reads += count

    def record_memory_write(self, count: int = 1) -> None:
        self._metrics.memory_writes += count

    def record_agent_call(self, count: int = 1) -> None:
        self._metrics.agent_calls += count

    def record_rl_call(self, count: int = 1) -> None:
        self._metrics.rl_calls += count

    def record_validation(self) -> None:
        self._metrics.validation_count += 1

    def set_confidence(self, value: float) -> None:
        self._metrics.confidence = max(0.0, min(1.0, value))

    def finalize(self) -> AgentExecutionMetrics:
        self._metrics.total_duration_ms = (time.perf_counter() - self._start) * 1000
        return self._metrics

    @asynccontextmanager
    async def track_phase(self, phase_name: str) -> AsyncIterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            self._metrics.metadata[f"{phase_name}_ms"] = round(elapsed, 2)
