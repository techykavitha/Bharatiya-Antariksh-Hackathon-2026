"""Climate Knowledge Graph relationship models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.knowledge_graph.entity_models import ClimateEntity, EntityType


class RelationshipType(StrEnum):
    """Canonical CKG relationship types."""

    CAUSES = "causes"
    AFFECTS = "affects"
    DEPENDS_ON = "depends_on"
    LOCATED_IN = "located_in"
    FEEDS = "feeds"
    BLOCKS = "blocks"
    MITIGATES = "mitigates"
    SUPPORTS = "supports"
    CONNECTED_TO = "connected_to"
    HISTORICALLY_RELATED = "historically_related"


class GraphRelationship(BaseModel):
    """Directed relationship between two CKG entities."""

    relationship_id: str = Field(default_factory=lambda: str(uuid4()))
    source_id: str
    target_id: str
    relationship_type: RelationshipType
    weight: float = Field(default=1.0, ge=0.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    bidirectional: bool = False
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NeighborResult(BaseModel):
    """Result of a neighbor query."""

    entity: ClimateEntity
    relationship: GraphRelationship
    direction: str = "out"


class PathResult(BaseModel):
    """Result of a shortest-path query."""

    source_id: str
    target_id: str
    path: list[str] = Field(default_factory=list)
    relationships: list[RelationshipType] = Field(default_factory=list)
    total_weight: float = Field(default=0.0, ge=0.0)
    hops: int = Field(default=0, ge=0)


class ImpactChainResult(BaseModel):
    """Cascading impact chain from a source entity."""

    source_id: str
    chain: list[ClimateEntity] = Field(default_factory=list)
    relationships: list[GraphRelationship] = Field(default_factory=list)
    depth: int = Field(default=0, ge=0)
    summary: str = ""


class AgentDependencyResult(BaseModel):
    """Specialized agents related to an entity."""

    entity_id: str
    agents: list[ClimateEntity] = Field(default_factory=list)
    relationships: list[GraphRelationship] = Field(default_factory=list)
    dependency_paths: list[list[str]] = Field(default_factory=list)


class RelatedEventResult(BaseModel):
    """Historically or causally related weather events."""

    entity_id: str
    events: list[ClimateEntity] = Field(default_factory=list)
    relationships: list[GraphRelationship] = Field(default_factory=list)
    similarity_scores: dict[str, float] = Field(default_factory=dict)


class HistoricalSimilarityResult(BaseModel):
    """Historical similarity comparison result."""

    entity_id: str
    candidates: list[ClimateEntity] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    best_match_id: str | None = None
    best_match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: list[str] = Field(default_factory=list)


class ReasoningInsight(BaseModel):
    """Single inferred insight from graph reasoning."""

    insight_id: str = Field(default_factory=lambda: str(uuid4()))
    category: str
    title: str
    description: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    affected_entity_ids: list[str] = Field(default_factory=list)
    supporting_relationships: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphReasoningResult(BaseModel):
    """Aggregated graph reasoning output."""

    source_entity_id: str
    secondary_impacts: list[ReasoningInsight] = Field(default_factory=list)
    cascading_failures: list[ReasoningInsight] = Field(default_factory=list)
    compound_disasters: list[ReasoningInsight] = Field(default_factory=list)
    agent_dependencies: list[ReasoningInsight] = Field(default_factory=list)
    summary: str = ""
