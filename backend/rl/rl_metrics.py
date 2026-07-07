"""RL execution metrics tracking."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from pydantic import BaseModel, Field

from backend.rl.rl_registry import RLAlgorithm


class RLExecutionMetrics(BaseModel):
    """Metrics from a single RL optimization invocation."""

    decision_id: str
    algorithm: str
    policy_version: str = ""
    inference_latency_ms: float = 0.0
    reward: float | None = None
    constraint_violations: int = 0
    optimization_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    actions_evaluated: int = 0
    actions_feasible: int = 0
    actions_rejected: int = 0
    memory_reads: int = 0
    state_dimension: int = 0
    phase_timings: dict[str, float] = Field(default_factory=dict)


class RLMetricsCollector:
    """Mutable metrics accumulator for RL service invocations."""

    def __init__(self, *, decision_id: str, algorithm: RLAlgorithm) -> None:
        self._decision_id = decision_id
        self._algorithm = algorithm
        self._start = time.perf_counter()
        self._metrics = RLExecutionMetrics(
            decision_id=decision_id,
            algorithm=algorithm.value,
        )

    @property
    def metrics(self) -> RLExecutionMetrics:
        return self._metrics

    def set_policy_version(self, version: str) -> None:
        self._metrics.policy_version = version

    def record_violations(self, count: int) -> None:
        self._metrics.constraint_violations += count

    def record_actions(self, evaluated: int, feasible: int, rejected: int) -> None:
        self._metrics.actions_evaluated = evaluated
        self._metrics.actions_feasible = feasible
        self._metrics.actions_rejected = rejected

    def set_reward(self, reward: float) -> None:
        self._metrics.reward = reward

    def set_confidence(self, confidence: float) -> None:
        self._metrics.optimization_confidence = max(0.0, min(1.0, confidence))

    def set_state_dimension(self, dim: int) -> None:
        self._metrics.state_dimension = dim

    def record_memory_reads(self, count: int = 1) -> None:
        self._metrics.memory_reads += count

    def finalize(self) -> RLExecutionMetrics:
        self._metrics.inference_latency_ms = (time.perf_counter() - self._start) * 1000
        return self._metrics

    @asynccontextmanager
    async def track_phase(self, phase_name: str) -> AsyncIterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            self._metrics.phase_timings[phase_name] = elapsed
