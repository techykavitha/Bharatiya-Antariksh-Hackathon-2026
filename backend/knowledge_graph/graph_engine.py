"""Climate Knowledge Graph core engine."""

from __future__ import annotations

import asyncio
from typing import Any

import networkx as nx

from backend.config.logger import get_logger
from backend.knowledge_graph.entity_models import ClimateEntity, EntityType
from backend.knowledge_graph.graph_metrics import GraphExecutionMetrics, GraphMetricsCollector
from backend.knowledge_graph.graph_query import GraphQueryEngine
from backend.knowledge_graph.graph_reasoning import GraphReasoningEngine
from backend.knowledge_graph.graph_serializer import GraphSerializer
from backend.knowledge_graph.graph_validator import GraphValidationResult, GraphValidator
from backend.knowledge_graph.relationship_models import GraphRelationship, RelationshipType
from backend.utils.errors import HyperionError

logger = get_logger(__name__)


class GraphEngineError(HyperionError):
    """Raised when a graph engine operation fails."""


class GraphEngine:
    """
    Central Climate Knowledge Graph (CKG) engine.

    Models relationships between climate variables, weather phenomena,
    infrastructure, policies, population, resources, agents, and digital twin.
    """

    def __init__(
        self,
        *,
        graph: nx.DiGraph | None = None,
        validator: GraphValidator | None = None,
        serializer: GraphSerializer | None = None,
    ) -> None:
        self._graph = graph if graph is not None else nx.DiGraph()
        self._entities: dict[str, ClimateEntity] = {}
        self._relationships: dict[str, GraphRelationship] = {}
        self._lock = asyncio.Lock()
        self._validator = validator or GraphValidator()
        self._serializer = serializer or GraphSerializer()
        self._query_engine = GraphQueryEngine(self)
        self._reasoning_engine = GraphReasoningEngine(self)
        self._metrics: GraphMetricsCollector | None = None
        self._last_metrics: GraphExecutionMetrics | None = None

    @property
    def query(self) -> GraphQueryEngine:
        return self._query_engine

    @property
    def reasoning(self) -> GraphReasoningEngine:
        return self._reasoning_engine

    @property
    def serializer(self) -> GraphSerializer:
        return self._serializer

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    @property
    def relationship_count(self) -> int:
        return len(self._relationships)

    @property
    def last_metrics(self) -> GraphExecutionMetrics | None:
        return self._last_metrics

    @classmethod
    async def create(cls, *, seed_india: bool = False) -> GraphEngine:
        engine = cls()
        if seed_india:
            from backend.knowledge_graph.graph_builder import ClimateGraphBuilder
            await ClimateGraphBuilder(engine).build_india_climate_graph()
        return engine

    def start_metrics(self, *, operation: str = "graph") -> GraphMetricsCollector:
        self._metrics = GraphMetricsCollector(operation=operation)
        return self._metrics

    async def add_entity(
        self,
        entity: ClimateEntity,
        *,
        validate: bool = True,
    ) -> ClimateEntity:
        result = self._validator.validate_entity(entity) if validate else GraphValidationResult(valid=True)
        if not result.valid:
            raise GraphEngineError(
                "Entity validation failed",
                details={"issues": [i.message for i in result.errors]},
            )

        async with self._lock:
            self._graph.add_node(
                entity.entity_id,
                entity_type=entity.entity_type.value,
                name=entity.name,
                region_id=entity.region_id,
            )
            self._entities[entity.entity_id] = entity

        self._metrics and self._metrics.record_entity(entity.entity_type)
        logger.debug("ckg_entity_added", entity_id=entity.entity_id, entity_type=entity.entity_type.value)
        return entity

    async def get_entity(self, entity_id: str) -> ClimateEntity | None:
        return self._entities.get(entity_id)

    async def update_entity(self, entity: ClimateEntity) -> ClimateEntity:
        await self._ensure_entity(entity.entity_id)
        entity.touch()
        async with self._lock:
            self._entities[entity.entity_id] = entity
            if self._graph.has_node(entity.entity_id):
                self._graph.nodes[entity.entity_id].update({
                    "entity_type": entity.entity_type.value,
                    "name": entity.name,
                    "region_id": entity.region_id,
                })
        return entity

    async def remove_entity(self, entity_id: str) -> bool:
        async with self._lock:
            if entity_id not in self._entities:
                return False
            self._entities.pop(entity_id)
            if self._graph.has_node(entity_id):
                self._graph.remove_node(entity_id)
            to_remove = [
                rid for rid, rel in self._relationships.items()
                if rel.source_id == entity_id or rel.target_id == entity_id
            ]
            for rid in to_remove:
                self._relationships.pop(rid, None)
        return True

    async def list_entities(
        self,
        *,
        entity_type: EntityType | None = None,
        region_id: str | None = None,
    ) -> list[ClimateEntity]:
        entities = list(self._entities.values())
        if entity_type:
            entities = [e for e in entities if e.entity_type == entity_type]
        if region_id:
            entities = [e for e in entities if e.region_id == region_id]
        return entities

    async def add_relationship(
        self,
        relationship: GraphRelationship,
        *,
        validate: bool = True,
    ) -> GraphRelationship:
        source = self._entities.get(relationship.source_id)
        target = self._entities.get(relationship.target_id)
        if validate:
            result = self._validator.validate_relationship(relationship, source, target)
            if not result.valid:
                raise GraphEngineError(
                    "Relationship validation failed",
                    details={"issues": [i.message for i in result.errors]},
                )

        async with self._lock:
            if not self._graph.has_node(relationship.source_id):
                raise GraphEngineError(f"Source entity '{relationship.source_id}' not found")
            if not self._graph.has_node(relationship.target_id):
                raise GraphEngineError(f"Target entity '{relationship.target_id}' not found")

            self._graph.add_edge(
                relationship.source_id,
                relationship.target_id,
                relationship_id=relationship.relationship_id,
                relationship_type=relationship.relationship_type.value,
                weight=relationship.weight,
                confidence=relationship.confidence,
                source_id=relationship.source_id,
                target_id=relationship.target_id,
            )
            self._relationships[relationship.relationship_id] = relationship

            if relationship.bidirectional:
                self._graph.add_edge(
                    relationship.target_id,
                    relationship.source_id,
                    relationship_id=f"{relationship.relationship_id}_reverse",
                    relationship_type=relationship.relationship_type.value,
                    weight=relationship.weight,
                    confidence=relationship.confidence,
                    source_id=relationship.target_id,
                    target_id=relationship.source_id,
                )

        self._metrics and self._metrics.record_relationship(relationship.relationship_type)
        logger.debug(
            "ckg_relationship_added",
            relationship_id=relationship.relationship_id,
            relationship_type=relationship.relationship_type.value,
        )
        return relationship

    async def link(
        self,
        source_id: str,
        target_id: str,
        relationship_type: RelationshipType,
        *,
        weight: float = 1.0,
        confidence: float = 1.0,
        attributes: dict[str, Any] | None = None,
    ) -> GraphRelationship:
        """Convenience method to create and add a relationship."""
        relationship = GraphRelationship(
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
            weight=weight,
            confidence=confidence,
            attributes=attributes or {},
        )
        return await self.add_relationship(relationship)

    async def get_relationship(self, relationship_id: str) -> GraphRelationship | None:
        return self._relationships.get(relationship_id)

    async def list_relationships(
        self,
        *,
        relationship_type: RelationshipType | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
    ) -> list[GraphRelationship]:
        relationships = list(self._relationships.values())
        if relationship_type:
            relationships = [r for r in relationships if r.relationship_type == relationship_type]
        if source_id:
            relationships = [r for r in relationships if r.source_id == source_id]
        if target_id:
            relationships = [r for r in relationships if r.target_id == target_id]
        return relationships

    async def validate(self) -> GraphValidationResult:
        self._metrics and self._metrics.record_validation()
        return self._validator.validate_graph(
            list(self._entities.values()),
            list(self._relationships.values()),
        )

    async def export_snapshot(self) -> dict[str, Any]:
        return self._serializer.export_snapshot(
            entities=list(self._entities.values()),
            relationships=list(self._relationships.values()),
        )

    async def import_snapshot(self, data: dict[str, Any]) -> None:
        entities, relationships = self._serializer.import_snapshot(data)
        async with self._lock:
            self._graph.clear()
            self._entities.clear()
            self._relationships.clear()

        for entity in entities:
            await self.add_entity(entity, validate=False)
        for relationship in relationships:
            await self.add_relationship(relationship, validate=False)

    async def export_node_link(self) -> dict[str, Any]:
        async with self._lock:
            return self._serializer.graph_to_node_link(
                self._graph,
                entities=self._entities,
                relationships=self._relationships,
            )

    async def finalize_metrics(self) -> GraphExecutionMetrics | None:
        if self._metrics:
            self._last_metrics = self._metrics.finalize()
            return self._last_metrics
        return None

    async def _ensure_entity(self, entity_id: str) -> ClimateEntity:
        entity = self._entities.get(entity_id)
        if entity is None:
            raise GraphEngineError(f"Entity '{entity_id}' not found")
        return entity
