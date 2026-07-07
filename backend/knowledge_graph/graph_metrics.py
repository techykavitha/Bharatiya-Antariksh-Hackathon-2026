"""Climate Knowledge Graph metrics tracking."""

from __future__ import annotations

import time

from pydantic import BaseModel, Field

from backend.knowledge_graph.entity_models import EntityType
from backend.knowledge_graph.relationship_models import RelationshipType


class GraphExecutionMetrics(BaseModel):
    """Metrics for a CKG operation batch."""

    operation: str
    entity_count: int = 0
    relationship_count: int = 0
    query_count: int = 0
    reasoning_count: int = 0
    validation_count: int = 0
    duration_ms: float = Field(default=0.0, ge=0.0)
    entity_type_counts: dict[str, int] = Field(default_factory=dict)
    relationship_type_counts: dict[str, int] = Field(default_factory=dict)
    metadata: dict[str, float | int | str] = Field(default_factory=dict)


class GraphMetricsCollector:
    """Mutable metrics accumulator for CKG operations."""

    def __init__(self, *, operation: str = "graph") -> None:
        self._operation = operation
        self._start = time.perf_counter()
        self._metrics = GraphExecutionMetrics(operation=operation)
        self._entity_types: dict[str, int] = {}
        self._relationship_types: dict[str, int] = {}

    @property
    def metrics(self) -> GraphExecutionMetrics:
        return self._metrics

    def record_entity(self, entity_type: EntityType) -> None:
        self._metrics.entity_count += 1
        key = entity_type.value
        self._entity_types[key] = self._entity_types.get(key, 0) + 1

    def record_relationship(self, relationship_type: RelationshipType) -> None:
        self._metrics.relationship_count += 1
        key = relationship_type.value
        self._relationship_types[key] = self._relationship_types.get(key, 0) + 1

    def record_query(self) -> None:
        self._metrics.query_count += 1

    def record_reasoning(self) -> None:
        self._metrics.reasoning_count += 1

    def record_validation(self) -> None:
        self._metrics.validation_count += 1

    def finalize(self) -> GraphExecutionMetrics:
        self._metrics.duration_ms = round((time.perf_counter() - self._start) * 1000, 2)
        self._metrics.entity_type_counts = dict(self._entity_types)
        self._metrics.relationship_type_counts = dict(self._relationship_types)
        return self._metrics
