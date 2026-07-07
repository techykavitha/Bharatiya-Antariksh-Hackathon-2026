"""Shared types and schemas for the Hyperion memory subsystem."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.agents.memory.interfaces import MemoryEntry


class MemoryDomain(StrEnum):
    """Logical memory domain routing keys for MemoryManager."""

    CONVERSATION = "conversation"
    CLIMATE = "climate"
    DIGITAL_TWIN = "digital_twin"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    VECTOR = "vector"
    WORKING = "working"
    SESSION = "session"
    WORKFLOW = "workflow"


class GraphNodeType(StrEnum):
    """Canonical knowledge graph node types."""

    CITY = "city"
    STATE = "state"
    RIVER = "river"
    RESERVOIR = "reservoir"
    CYCLONE = "cyclone"
    FLOOD = "flood"
    HEATWAVE = "heatwave"
    AGRICULTURE = "agriculture"
    POLICY = "policy"
    WEATHER_VARIABLE = "weather_variable"
    CLIMATE_VARIABLE = "climate_variable"


class GraphEdgeType(StrEnum):
    """Canonical knowledge graph edge relations."""

    AFFECTS = "affects"
    LOCATED_IN = "located_in"
    CONNECTED_TO = "connected_to"
    DEPENDS_ON = "depends_on"
    CAUSES = "causes"
    IMPACTS = "impacts"


class VectorDocumentType(StrEnum):
    """Categories of documents stored in vector memory."""

    HISTORICAL_EVENT = "historical_event"
    PREVIOUS_SIMULATION = "previous_simulation"
    FORECAST_SUMMARY = "forecast_summary"
    POLICY_REPORT = "policy_report"
    RESEARCH_DOCUMENT = "research_document"
    DISASTER_HISTORY = "disaster_history"
    CLIMATE_OBSERVATION = "climate_observation"
    EMBEDDING = "embedding"


class TwinStateLayer(StrEnum):
    """Digital twin state layers."""

    CURRENT_CLIMATE = "current_climate"
    PAST_CLIMATE = "past_climate"
    FORECAST = "forecast"
    SIMULATION = "simulation"
    HISTORICAL_REPLAY = "historical_replay"


class MemoryStoreRequest(BaseModel):
    """Unified store request for MemoryManager."""

    domain: MemoryDomain
    key: str
    value: Any
    metadata: dict[str, Any] = Field(default_factory=dict)
    ttl_seconds: int | None = None
    session_id: str | None = None
    embedding: list[float] | None = None
    collection: str | None = None


class MemoryRetrieveRequest(BaseModel):
    """Unified retrieve request for MemoryManager."""

    domain: MemoryDomain
    key: str
    session_id: str | None = None
    twin_id: str | None = None
    layer_name: str | None = None


class MemorySearchRequest(BaseModel):
    """Unified search request for MemoryManager."""

    query: str
    domains: list[MemoryDomain] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=100)
    filters: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None
    twin_id: str | None = None
    climate_context: dict[str, Any] | None = None
    embedding: list[float] | None = None
    collection: str | None = None


class RankedMemory(BaseModel):
    """A memory entry enriched with ranking metadata."""

    entry: MemoryEntry
    domain: MemoryDomain
    final_score: float = Field(ge=0.0, le=1.0)
    recency_score: float = Field(default=0.0, ge=0.0, le=1.0)
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    importance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    frequency_score: float = Field(default=0.0, ge=0.0, le=1.0)
    domain_relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)


class HybridRetrievalResult(BaseModel):
    """Aggregated result from hybrid retrieval across memory backends."""

    query: str
    results: list[RankedMemory] = Field(default_factory=list)
    vector_count: int = 0
    graph_count: int = 0
    redis_count: int = 0
    climate_count: int = 0
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CheckpointRecord(BaseModel):
    """Metadata for a digital twin or workflow checkpoint."""

    checkpoint_id: str = Field(default_factory=lambda: str(uuid4()))
    twin_id: str
    version: str
    label: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    layers: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StateComparisonResult(BaseModel):
    """Result of comparing two digital twin states."""

    twin_id: str
    version_a: str
    version_b: str
    identical: bool
    changed_layers: list[str] = Field(default_factory=list)
    diff: dict[str, Any] = Field(default_factory=dict)


class MemorySummary(BaseModel):
    """Condensed summary of memory contents for agent context windows."""

    summary_id: str = Field(default_factory=lambda: str(uuid4()))
    domain: MemoryDomain | None = None
    content: str
    source_keys: list[str] = Field(default_factory=list)
    token_estimate: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
