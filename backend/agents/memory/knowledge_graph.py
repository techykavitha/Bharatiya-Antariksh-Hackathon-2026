"""NetworkX-backed knowledge graph memory for climate domain relationships."""

from __future__ import annotations

import asyncio
from typing import Any

import networkx as nx

from backend.agents.memory.interfaces import KnowledgeGraphMemory, MemoryEntry
from backend.agents.memory.memory_cache import AsyncLRUMemoryCache
from backend.agents.memory.memory_types import GraphEdgeType, GraphNodeType
from backend.agents.memory.serialization import pydantic_to_dict
from backend.utils.constants import KNOWLEDGE_GRAPH_MAX_DEPTH
from backend.utils.errors import MemoryNotFoundError, MemoryReadError, MemoryWriteError


class NetworkXKnowledgeGraph(KnowledgeGraphMemory):
    """
    In-process knowledge graph using NetworkX for climate domain relationships.

    Supports typed nodes (city, river, cyclone, etc.) and typed edges
    (affects, located_in, causes, etc.) with full graph query APIs.
    """

    def __init__(
        self,
        graph: nx.DiGraph | None = None,
        *,
        cache: AsyncLRUMemoryCache[MemoryEntry] | None = None,
    ) -> None:
        self._graph = graph if graph is not None else nx.DiGraph()
        self._cache = cache or AsyncLRUMemoryCache[MemoryEntry](max_size=512)
        self._lock = asyncio.Lock()
        self._node_index: dict[str, dict[str, Any]] = {}

    @property
    def backend_name(self) -> str:
        return "knowledge_graph"

    @property
    def graph(self) -> nx.DiGraph:
        """Return the underlying NetworkX graph (read-only access)."""
        return self._graph

    async def write(self, key: str, value: Any, *, metadata: dict[str, Any] | None = None) -> None:
        """Store a node payload keyed by node_id."""
        node_type = (metadata or {}).get("node_type", GraphNodeType.CLIMATE_VARIABLE.value)
        attributes = pydantic_to_dict(value) if not isinstance(value, dict) else value
        attributes.update(metadata or {})
        await self.add_node(key, {"node_type": node_type, **attributes})

    async def read(self, key: str) -> MemoryEntry | None:
        cached = await self._cache.get(key)
        if cached:
            return cached
        async with self._lock:
            if not self._graph.has_node(key):
                return None
            attrs = dict(self._graph.nodes[key])
            entry = MemoryEntry(key=key, value=attrs, metadata={"node_type": attrs.get("node_type")})
            await self._cache.set(key, entry)
            return entry

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if not self._graph.has_node(key):
                return False
            self._graph.remove_node(key)
            self._node_index.pop(key, None)
        await self._cache.delete(key)
        return True

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[MemoryEntry]:
        return await self.query(query, node_type=filters.get("node_type") if filters else None, limit=limit)

    async def clear(self, namespace: str | None = None) -> int:
        async with self._lock:
            if namespace:
                nodes = [
                    n for n, d in self._graph.nodes(data=True)
                    if d.get("node_type") == namespace
                ]
                self._graph.remove_nodes_from(nodes)
                for n in nodes:
                    self._node_index.pop(n, None)
                await self._cache.invalidate_prefix(namespace)
                return len(nodes)
            count = self._graph.number_of_nodes()
            self._graph.clear()
            self._node_index.clear()
        await self._cache.clear()
        return count

    async def add_node(self, node_id: str, attributes: dict[str, Any]) -> None:
        async with self._lock:
            self._graph.add_node(node_id, **attributes)
            self._node_index[node_id] = attributes
        await self._cache.delete(node_id)

    async def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        *,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        valid_relations = {e.value for e in GraphEdgeType}
        if relation not in valid_relations:
            raise MemoryWriteError(
                f"Invalid relation '{relation}'. Must be one of: {sorted(valid_relations)}",
                details={"relation": relation},
            )
        async with self._lock:
            if not self._graph.has_node(source_id):
                raise MemoryNotFoundError(f"Source node '{source_id}' not found")
            if not self._graph.has_node(target_id):
                raise MemoryNotFoundError(f"Target node '{target_id}' not found")
            edge_attrs = {"relation": relation, **(attributes or {})}
            self._graph.add_edge(source_id, target_id, **edge_attrs)

    async def neighbors(
        self,
        node_id: str,
        *,
        relation: str | None = None,
        direction: str = "out",
    ) -> list[MemoryEntry]:
        async with self._lock:
            if not self._graph.has_node(node_id):
                raise MemoryNotFoundError(f"Node '{node_id}' not found")
            if direction == "in":
                neighbor_ids = list(self._graph.predecessors(node_id))
            elif direction == "both":
                neighbor_ids = list(set(self._graph.successors(node_id)) | set(self._graph.predecessors(node_id)))
            else:
                neighbor_ids = list(self._graph.successors(node_id))

        entries: list[MemoryEntry] = []
        for nid in neighbor_ids:
            if relation:
                edge_data = self._get_edge_data(node_id, nid, relation, direction)
                if edge_data is None:
                    continue
            node_entry = await self.read(nid)
            if node_entry:
                entries.append(node_entry)
        return entries

    async def shortest_path(
        self,
        source_id: str,
        target_id: str,
        *,
        relation: str | None = None,
    ) -> list[str]:
        async with self._lock:
            if relation:
                subgraph = self._relation_subgraph(relation)
                try:
                    return nx.shortest_path(subgraph, source_id, target_id)
                except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
                    raise MemoryNotFoundError(
                        f"No path from '{source_id}' to '{target_id}' via '{relation}'",
                    ) from exc
            try:
                return nx.shortest_path(self._graph, source_id, target_id)
            except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
                raise MemoryNotFoundError(
                    f"No path from '{source_id}' to '{target_id}'",
                ) from exc

    async def subgraph(
        self,
        center_node: str,
        *,
        radius: int = 2,
        relation: str | None = None,
    ) -> dict[str, Any]:
        async with self._lock:
            if not self._graph.has_node(center_node):
                raise MemoryNotFoundError(f"Node '{center_node}' not found")
            if relation:
                base = self._relation_subgraph(relation)
            else:
                base = self._graph
            nodes = {center_node}
            frontier = {center_node}
            for _ in range(radius):
                next_frontier: set[str] = set()
                for node in frontier:
                    next_frontier |= set(base.successors(node)) | set(base.predecessors(node))
                nodes |= next_frontier
                frontier = next_frontier
            sub = base.subgraph(nodes).copy()
            return nx.node_link_data(sub)

    async def query(
        self,
        query: str,
        *,
        node_type: str | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        query_lower = query.lower()
        results: list[MemoryEntry] = []
        async with self._lock:
            for node_id, attrs in self._graph.nodes(data=True):
                if node_type and attrs.get("node_type") != node_type:
                    continue
                searchable = f"{node_id} {attrs.get('name', '')} {attrs.get('label', '')}".lower()
                if query_lower in searchable or any(query_lower in str(v).lower() for v in attrs.values()):
                    results.append(MemoryEntry(key=node_id, value=dict(attrs), metadata={"node_type": attrs.get("node_type")}))
                if len(results) >= limit:
                    break
        return results

    async def traverse(
        self,
        start_node: str,
        *,
        relation: str | None = None,
        max_depth: int = KNOWLEDGE_GRAPH_MAX_DEPTH,
    ) -> list[MemoryEntry]:
        visited: set[str] = set()
        results: list[MemoryEntry] = []
        queue: list[tuple[str, int]] = [(start_node, 0)]

        while queue:
            node_id, depth = queue.pop(0)
            if node_id in visited or depth > max_depth:
                continue
            visited.add(node_id)
            entry = await self.read(node_id)
            if entry:
                entry.metadata["depth"] = depth
                results.append(entry)
            if depth < max_depth:
                for neighbor in await self.neighbors(node_id, relation=relation):
                    if neighbor.key not in visited:
                        queue.append((neighbor.key, depth + 1))
        return results

    def _relation_subgraph(self, relation: str) -> nx.DiGraph:
        edges = [
            (u, v) for u, v, d in self._graph.edges(data=True) if d.get("relation") == relation
        ]
        nodes = set()
        for u, v in edges:
            nodes.add(u)
            nodes.add(v)
        return self._graph.subgraph(nodes).edge_subgraph(edges).copy()

    def _get_edge_data(
        self,
        node_id: str,
        neighbor_id: str,
        relation: str,
        direction: str,
    ) -> dict[str, Any] | None:
        if direction in ("out", "both") and self._graph.has_edge(node_id, neighbor_id):
            data = self._graph.edges[node_id, neighbor_id]
            if data.get("relation") == relation:
                return data
        if direction in ("in", "both") and self._graph.has_edge(neighbor_id, node_id):
            data = self._graph.edges[neighbor_id, node_id]
            if data.get("relation") == relation:
                return data
        return None

    @classmethod
    def create_climate_graph(cls) -> NetworkXKnowledgeGraph:
        """Create a knowledge graph pre-populated with node type metadata."""
        graph = cls()
        return graph
