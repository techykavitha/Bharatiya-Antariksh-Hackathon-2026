"""Climate Knowledge Graph query engine."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

import networkx as nx

from backend.knowledge_graph.entity_models import ClimateEntity, EntityType
from backend.knowledge_graph.graph_schema import IMPACT_RELATIONSHIPS
from backend.knowledge_graph.relationship_models import (
    AgentDependencyResult,
    GraphRelationship,
    HistoricalSimilarityResult,
    ImpactChainResult,
    NeighborResult,
    PathResult,
    RelatedEventResult,
    RelationshipType,
)
from backend.utils.constants import KNOWLEDGE_GRAPH_MAX_DEPTH
from backend.utils.errors import HyperionError

if TYPE_CHECKING:
    from backend.knowledge_graph.graph_engine import GraphEngine


class GraphQueryError(HyperionError):
    """Raised when a graph query fails."""


class GraphQueryEngine:
    """Query interface for the Climate Knowledge Graph."""

    EVENT_ENTITY_TYPES: set[EntityType] = {
        EntityType.WEATHER_EVENT,
        EntityType.FLOOD,
        EntityType.CYCLONE,
        EntityType.HEATWAVE,
        EntityType.DROUGHT,
    }

    def __init__(self, engine: GraphEngine) -> None:
        self._engine = engine

    async def neighbors(
        self,
        entity_id: str,
        *,
        relationship: RelationshipType | None = None,
        direction: str = "out",
    ) -> list[NeighborResult]:
        """Return neighboring entities optionally filtered by relationship type."""
        await self._engine._ensure_entity(entity_id)
        results: list[NeighborResult] = []

        async with self._engine._lock:
            if direction in ("out", "both"):
                for _, target_id, edge_data in self._engine._graph.out_edges(entity_id, data=True):
                    rel = self._edge_relationship(edge_data)
                    if relationship and rel.relationship_type != relationship:
                        continue
                    target = self._engine._entities.get(target_id)
                    if target:
                        results.append(NeighborResult(entity=target, relationship=rel, direction="out"))

            if direction in ("in", "both"):
                for source_id, _, edge_data in self._engine._graph.in_edges(entity_id, data=True):
                    rel = self._edge_relationship(edge_data)
                    if relationship and rel.relationship_type != relationship:
                        continue
                    source = self._engine._entities.get(source_id)
                    if source:
                        results.append(NeighborResult(entity=source, relationship=rel, direction="in"))

        self._engine._metrics and self._engine._metrics.record_query()
        return results

    async def shortest_path(
        self,
        source_id: str,
        target_id: str,
        *,
        relationship: RelationshipType | None = None,
    ) -> PathResult:
        """Find shortest path between two entities."""
        await self._engine._ensure_entity(source_id)
        await self._engine._ensure_entity(target_id)

        async with self._engine._lock:
            graph = self._relation_subgraph(relationship) if relationship else self._engine._graph
            try:
                node_path = nx.shortest_path(graph, source_id, target_id)
            except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
                raise GraphQueryError(
                    f"No path from '{source_id}' to '{target_id}'",
                    details={"relationship": relationship.value if relationship else None},
                ) from exc

            rel_types: list[RelationshipType] = []
            total_weight = 0.0
            for i in range(len(node_path) - 1):
                edge_data = graph.get_edge_data(node_path[i], node_path[i + 1]) or {}
                rel = self._edge_relationship(edge_data)
                rel_types.append(rel.relationship_type)
                total_weight += rel.weight

        self._engine._metrics and self._engine._metrics.record_query()
        return PathResult(
            source_id=source_id,
            target_id=target_id,
            path=node_path,
            relationships=rel_types,
            total_weight=round(total_weight, 3),
            hops=len(node_path) - 1,
        )

    async def impact_chain(
        self,
        entity_id: str,
        *,
        max_depth: int = KNOWLEDGE_GRAPH_MAX_DEPTH,
        relationships: set[RelationshipType] | None = None,
    ) -> ImpactChainResult:
        """Traverse causal and impact relationships from a source entity."""
        await self._engine._ensure_entity(entity_id)
        rel_filter = relationships or IMPACT_RELATIONSHIPS

        chain: list[ClimateEntity] = []
        rels: list[GraphRelationship] = []
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(entity_id, 0)])

        while queue:
            current_id, depth = queue.popleft()
            if current_id in visited or depth > max_depth:
                continue
            visited.add(current_id)
            entity = self._engine._entities.get(current_id)
            if entity and current_id != entity_id:
                chain.append(entity)

            if depth >= max_depth:
                continue

            neighbors = await self.neighbors(current_id, direction="out")
            for neighbor in neighbors:
                if neighbor.relationship.relationship_type not in rel_filter:
                    continue
                if neighbor.entity.entity_id not in visited:
                    rels.append(neighbor.relationship)
                    queue.append((neighbor.entity.entity_id, depth + 1))

        source = self._engine._entities[entity_id]
        summary = (
            f"Impact chain from {source.name}: {len(chain)} affected entities "
            f"within {max_depth} hops via {', '.join(r.value for r in rel_filter)}"
        )
        self._engine._metrics and self._engine._metrics.record_query()
        return ImpactChainResult(
            source_id=entity_id,
            chain=chain,
            relationships=rels,
            depth=max_depth,
            summary=summary,
        )

    async def affected_agents(self, entity_id: str) -> AgentDependencyResult:
        """Find specialized agents that support, mitigate, or depend on an entity."""
        await self._engine._ensure_entity(entity_id)
        agents: list[ClimateEntity] = []
        relationships: list[GraphRelationship] = []
        paths: list[list[str]] = []

        inbound = await self.neighbors(entity_id, direction="in")
        for neighbor in inbound:
            if neighbor.entity.entity_type != EntityType.SPECIALIZED_AGENT:
                continue
            if neighbor.relationship.relationship_type in {
                RelationshipType.SUPPORTS,
                RelationshipType.MITIGATES,
                RelationshipType.DEPENDS_ON,
            }:
                agents.append(neighbor.entity)
                relationships.append(neighbor.relationship)
                paths.append([neighbor.entity.entity_id, entity_id])

        outbound = await self.neighbors(entity_id, direction="out")
        for neighbor in outbound:
            if neighbor.entity.entity_type == EntityType.SPECIALIZED_AGENT:
                agents.append(neighbor.entity)
                relationships.append(neighbor.relationship)
                paths.append([entity_id, neighbor.entity.entity_id])

        for agent_entity in list(self._engine._entities.values()):
            if agent_entity.entity_type != EntityType.SPECIALIZED_AGENT:
                continue
            if agent_entity in agents:
                continue
            try:
                path = await self.shortest_path(agent_entity.entity_id, entity_id)
                if path.hops <= 3:
                    agents.append(agent_entity)
                    paths.append(path.path)
            except GraphQueryError:
                continue

        unique_agents = list({a.entity_id: a for a in agents}.values())
        self._engine._metrics and self._engine._metrics.record_query()
        return AgentDependencyResult(
            entity_id=entity_id,
            agents=unique_agents,
            relationships=relationships,
            dependency_paths=paths,
        )

    async def related_events(self, entity_id: str, *, limit: int = 10) -> RelatedEventResult:
        """Find historically or causally related weather events."""
        await self._engine._ensure_entity(entity_id)
        events: list[ClimateEntity] = []
        relationships: list[GraphRelationship] = []
        scores: dict[str, float] = {}

        for direction in ("out", "in"):
            neighbors = await self.neighbors(
                entity_id,
                relationship=RelationshipType.HISTORICALLY_RELATED,
                direction=direction,
            )
            for neighbor in neighbors:
                if neighbor.entity.entity_id == entity_id:
                    continue
                events.append(neighbor.entity)
                relationships.append(neighbor.relationship)
                scores[neighbor.entity.entity_id] = neighbor.relationship.confidence

        causal_neighbors = await self.neighbors(entity_id, relationship=RelationshipType.CAUSES, direction="out")
        causal_neighbors += await self.neighbors(entity_id, relationship=RelationshipType.AFFECTS, direction="out")
        for neighbor in causal_neighbors:
            if neighbor.entity.entity_type in self.EVENT_ENTITY_TYPES:
                if neighbor.entity.entity_id not in scores:
                    events.append(neighbor.entity)
                    relationships.append(neighbor.relationship)
                    scores[neighbor.entity.entity_id] = neighbor.relationship.confidence * 0.8

        if len(events) < limit:
            source = self._engine._entities[entity_id]
            for candidate in self._engine._entities.values():
                if candidate.entity_id == entity_id:
                    continue
                if candidate.entity_type not in self.EVENT_ENTITY_TYPES:
                    continue
                if candidate.entity_id in scores:
                    continue
                score = self._event_similarity(source, candidate)
                if score >= 0.5:
                    events.append(candidate)
                    scores[candidate.entity_id] = score
                if len(events) >= limit:
                    break

        self._engine._metrics and self._engine._metrics.record_query()
        return RelatedEventResult(
            entity_id=entity_id,
            events=events[:limit],
            relationships=relationships,
            similarity_scores=scores,
        )

    async def historical_similarity(
        self,
        entity_id: str,
        *,
        limit: int = 5,
    ) -> HistoricalSimilarityResult:
        """Score historical similarity against past events of the same type."""
        await self._engine._ensure_entity(entity_id)
        source = self._engine._entities[entity_id]
        candidates: list[ClimateEntity] = []
        scores: dict[str, float] = {}
        rationale: list[str] = []

        for candidate in self._engine._entities.values():
            if candidate.entity_id == entity_id:
                continue
            if candidate.entity_type != source.entity_type:
                continue
            if candidate.entity_type not in self.EVENT_ENTITY_TYPES:
                continue
            score = self._event_similarity(source, candidate)
            scores[candidate.entity_id] = score
            candidates.append(candidate)

        ranked = sorted(candidates, key=lambda c: scores.get(c.entity_id, 0.0), reverse=True)[:limit]
        best_id = ranked[0].entity_id if ranked else None
        best_score = scores.get(best_id, 0.0) if best_id else 0.0

        if best_id:
            rationale.append(
                f"Best historical match: {ranked[0].name} (score={best_score:.2f})"
            )
        related = await self.related_events(entity_id, limit=limit)
        for eid, score in related.similarity_scores.items():
            if eid not in scores:
                scores[eid] = score

        self._engine._metrics and self._engine._metrics.record_query()
        return HistoricalSimilarityResult(
            entity_id=entity_id,
            candidates=ranked,
            scores=scores,
            best_match_id=best_id,
            best_match_score=best_score,
            rationale=rationale,
        )

    async def search(
        self,
        query: str,
        *,
        entity_type: EntityType | None = None,
        limit: int = 10,
    ) -> list[ClimateEntity]:
        """Text search across entity names, descriptions, and tags."""
        query_lower = query.lower()
        results: list[ClimateEntity] = []
        for entity in self._engine._entities.values():
            if entity_type and entity.entity_type != entity_type:
                continue
            searchable = f"{entity.name} {entity.description} {' '.join(entity.tags)} {entity.region_id or ''}".lower()
            if query_lower in searchable:
                results.append(entity)
            if len(results) >= limit:
                break
        self._engine._metrics and self._engine._metrics.record_query()
        return results

    def _relation_subgraph(self, relationship: RelationshipType) -> nx.DiGraph:
        edges = [
            (u, v)
            for u, v, d in self._engine._graph.edges(data=True)
            if d.get("relationship_type") == relationship.value
        ]
        return self._engine._graph.edge_subgraph(edges).copy()

    def _edge_relationship(self, edge_data: dict[str, Any]) -> GraphRelationship:
        rel_id = edge_data.get("relationship_id", "")
        if rel_id and rel_id in self._engine._relationships:
            return self._engine._relationships[rel_id]
        return GraphRelationship(
            relationship_id=rel_id or edge_data.get("relationship_id", ""),
            source_id=edge_data.get("source_id", ""),
            target_id=edge_data.get("target_id", ""),
            relationship_type=RelationshipType(edge_data.get("relationship_type", RelationshipType.AFFECTS.value)),
            weight=float(edge_data.get("weight", 1.0)),
            confidence=float(edge_data.get("confidence", 1.0)),
        )

    def _event_similarity(self, source: ClimateEntity, candidate: ClimateEntity) -> float:
        score = 0.0
        if source.entity_type == candidate.entity_type:
            score += 0.3
        if source.region_id and source.region_id == candidate.region_id:
            score += 0.25

        numeric_keys = ("peak_depth_m", "peak_temp_c", "amount_mm", "affected_population", "duration_days")
        for key in numeric_keys:
            s_val = source.attributes.get(key)
            c_val = candidate.attributes.get(key)
            if isinstance(s_val, (int, float)) and isinstance(c_val, (int, float)) and s_val > 0:
                ratio = min(s_val, c_val) / max(s_val, c_val)
                score += 0.15 * ratio

        source_year = source.attributes.get("year")
        cand_year = candidate.attributes.get("year")
        if isinstance(source_year, int) and isinstance(cand_year, int):
            year_gap = abs(source_year - cand_year)
            score += max(0.15 - year_gap * 0.02, 0.0)

        return min(score, 1.0)
