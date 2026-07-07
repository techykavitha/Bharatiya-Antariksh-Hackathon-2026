"""Serialization utilities for the Climate Knowledge Graph."""

from __future__ import annotations

import json
from typing import Any, TypeVar

import networkx as nx
from pydantic import BaseModel

from backend.knowledge_graph.entity_models import ClimateEntity, EntityType, ENTITY_MODEL_REGISTRY
from backend.knowledge_graph.graph_schema import GraphSchemaVersion
from backend.knowledge_graph.relationship_models import GraphRelationship, RelationshipType
from backend.utils.errors import SchemaValidationError

T = TypeVar("T", bound=BaseModel)


class GraphSerializer:
    """Serializes and deserializes CKG artifacts."""

    SCHEMA_VERSION = GraphSchemaVersion.V1.value

    def entity_to_dict(self, entity: ClimateEntity) -> dict[str, Any]:
        return entity.model_dump(mode="json")

    def entity_from_dict(self, data: dict[str, Any]) -> ClimateEntity:
        entity_type = EntityType(data["entity_type"])
        model_cls = ENTITY_MODEL_REGISTRY.get(entity_type, ClimateEntity)
        try:
            return model_cls.model_validate(data)
        except Exception as exc:
            raise SchemaValidationError(
                f"Failed to validate entity: {exc}",
                details={"entity_type": entity_type.value},
            ) from exc

    def relationship_to_dict(self, relationship: GraphRelationship) -> dict[str, Any]:
        return relationship.model_dump(mode="json")

    def relationship_from_dict(self, data: dict[str, Any]) -> GraphRelationship:
        try:
            return GraphRelationship.model_validate(data)
        except Exception as exc:
            raise SchemaValidationError(f"Failed to validate relationship: {exc}") from exc

    def to_json(self, model: BaseModel, *, indent: int | None = None) -> str:
        return json.dumps(model.model_dump(mode="json"), indent=indent, default=str)

    def graph_to_node_link(
        self,
        graph: nx.DiGraph,
        *,
        entities: dict[str, ClimateEntity],
        relationships: dict[str, GraphRelationship],
    ) -> dict[str, Any]:
        data = nx.node_link_data(graph)
        data["schema_version"] = self.SCHEMA_VERSION
        data["entity_records"] = {
            eid: self.entity_to_dict(entities[eid])
            for eid in entities
            if graph.has_node(eid)
        }
        data["relationship_records"] = {
            rid: self.relationship_to_dict(rel)
            for rid, rel in relationships.items()
        }
        return data

    def graph_from_node_link(self, data: dict[str, Any]) -> tuple[nx.DiGraph, dict[str, ClimateEntity], dict[str, GraphRelationship]]:
        graph = nx.node_link_graph(data, directed=True)
        entities: dict[str, ClimateEntity] = {}
        relationships: dict[str, GraphRelationship] = {}

        for eid, record in data.get("entity_records", {}).items():
            entities[eid] = self.entity_from_dict(record)

        for rid, record in data.get("relationship_records", {}).items():
            rel = self.relationship_from_dict(record)
            relationships[rid] = rel
            if graph.has_edge(rel.source_id, rel.target_id):
                graph.edges[rel.source_id, rel.target_id]["relationship_id"] = rid
                graph.edges[rel.source_id, rel.target_id]["relationship_type"] = rel.relationship_type.value

        return graph, entities, relationships

    def export_snapshot(
        self,
        *,
        entities: list[ClimateEntity],
        relationships: list[GraphRelationship],
    ) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "entities": [self.entity_to_dict(e) for e in entities],
            "relationships": [self.relationship_to_dict(r) for r in relationships],
        }

    def import_snapshot(self, data: dict[str, Any]) -> tuple[list[ClimateEntity], list[GraphRelationship]]:
        entities = [self.entity_from_dict(e) for e in data.get("entities", [])]
        relationships = [self.relationship_from_dict(r) for r in data.get("relationships", [])]
        return entities, relationships
