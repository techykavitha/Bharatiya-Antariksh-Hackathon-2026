"""Unit tests for NetworkX knowledge graph memory."""

import pytest

from backend.agents.memory.knowledge_graph import NetworkXKnowledgeGraph
from backend.agents.memory.memory_types import GraphEdgeType, GraphNodeType
from backend.utils.errors import MemoryNotFoundError, MemoryWriteError


@pytest.fixture
async def populated_graph(graph_store: NetworkXKnowledgeGraph) -> NetworkXKnowledgeGraph:
    await graph_store.add_node("chennai", {"node_type": GraphNodeType.CITY.value, "name": "Chennai"})
    await graph_store.add_node("tamil_nadu", {"node_type": GraphNodeType.STATE.value, "name": "Tamil Nadu"})
    await graph_store.add_node("cooum", {"node_type": GraphNodeType.RIVER.value, "name": "Cooum River"})
    await graph_store.add_node("flood_2015", {"node_type": GraphNodeType.FLOOD.value, "name": "Chennai Flood 2015"})
    await graph_store.add_edge("chennai", "tamil_nadu", GraphEdgeType.LOCATED_IN.value)
    await graph_store.add_edge("cooum", "chennai", GraphEdgeType.LOCATED_IN.value)
    await graph_store.add_edge("flood_2015", "chennai", GraphEdgeType.IMPACTS.value)
    await graph_store.add_edge("cooum", "flood_2015", GraphEdgeType.CAUSES.value)
    return graph_store


@pytest.mark.asyncio
async def test_graph_add_node_and_read(populated_graph: NetworkXKnowledgeGraph) -> None:
    entry = await populated_graph.read("chennai")
    assert entry is not None
    assert entry.value["name"] == "Chennai"


@pytest.mark.asyncio
async def test_graph_neighbors(populated_graph: NetworkXKnowledgeGraph) -> None:
    neighbors = await populated_graph.neighbors("chennai", relation=GraphEdgeType.LOCATED_IN.value, direction="out")
    assert any(n.key == "tamil_nadu" for n in neighbors)


@pytest.mark.asyncio
async def test_graph_shortest_path(populated_graph: NetworkXKnowledgeGraph) -> None:
    path = await populated_graph.shortest_path("cooum", "tamil_nadu")
    assert "chennai" in path


@pytest.mark.asyncio
async def test_graph_subgraph(populated_graph: NetworkXKnowledgeGraph) -> None:
    sub = await populated_graph.subgraph("chennai", radius=2)
    assert "nodes" in sub
    assert len(sub["nodes"]) >= 2


@pytest.mark.asyncio
async def test_graph_query(populated_graph: NetworkXKnowledgeGraph) -> None:
    results = await populated_graph.query("flood", node_type=GraphNodeType.FLOOD.value)
    assert len(results) == 1
    assert results[0].key == "flood_2015"


@pytest.mark.asyncio
async def test_graph_traverse(populated_graph: NetworkXKnowledgeGraph) -> None:
    results = await populated_graph.traverse("cooum", max_depth=3)
    assert len(results) >= 2


@pytest.mark.asyncio
async def test_graph_invalid_relation(graph_store: NetworkXKnowledgeGraph) -> None:
    await graph_store.add_node("a", {"node_type": GraphNodeType.CITY.value})
    await graph_store.add_node("b", {"node_type": GraphNodeType.CITY.value})
    with pytest.raises(MemoryWriteError):
        await graph_store.add_edge("a", "b", "invalid_relation")


@pytest.mark.asyncio
async def test_graph_shortest_path_not_found(populated_graph: NetworkXKnowledgeGraph) -> None:
    await populated_graph.add_node("isolated", {"node_type": GraphNodeType.CITY.value})
    with pytest.raises(MemoryNotFoundError):
        await populated_graph.shortest_path("chennai", "isolated")


@pytest.mark.asyncio
async def test_graph_delete(populated_graph: NetworkXKnowledgeGraph) -> None:
    assert await populated_graph.delete("cooum") is True
    assert await populated_graph.read("cooum") is None
