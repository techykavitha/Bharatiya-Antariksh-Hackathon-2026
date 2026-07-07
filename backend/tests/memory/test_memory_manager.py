"""Integration tests for MemoryManager."""

import pytest

from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.memory.memory_types import MemoryDomain, MemoryRetrieveRequest, MemorySearchRequest, MemoryStoreRequest
from backend.agents.memory.memory_types import VectorDocumentType
from backend.agents.memory.memory_types import GraphEdgeType, GraphNodeType
from backend.agents.state.climate_state import ClimateState
from backend.agents.state.conversation_state import ConversationTurn


@pytest.mark.asyncio
async def test_manager_store_and_retrieve_working(memory_manager: MemoryManager) -> None:
    await memory_manager.store(MemoryStoreRequest(
        domain=MemoryDomain.WORKING,
        key="calc-1",
        value={"result": 99},
        metadata={"agent_id": "agent-1"},
    ))
    entry = await memory_manager.retrieve(MemoryRetrieveRequest(
        domain=MemoryDomain.WORKING,
        key="calc-1",
    ))
    assert entry is not None
    assert entry.value["result"] == 99


@pytest.mark.asyncio
async def test_manager_conversation_flow(memory_manager: MemoryManager) -> None:
    session_id = "integration-sess-1"
    await memory_manager.store(MemoryStoreRequest(
        domain=MemoryDomain.CONVERSATION,
        key="turn",
        value={"role": "user", "content": "Analyze cyclone risk"},
        session_id=session_id,
    ))
    entry = await memory_manager.retrieve(MemoryRetrieveRequest(
        domain=MemoryDomain.CONVERSATION,
        key="chat_history",
        session_id=session_id,
    ))
    assert entry is not None


@pytest.mark.asyncio
async def test_manager_vector_and_search(memory_manager: MemoryManager) -> None:
    await memory_manager.store(MemoryStoreRequest(
        domain=MemoryDomain.VECTOR,
        key="vec-1",
        value={"event": "cyclone"},
        metadata={"text": "Cyclone Amphan hit West Bengal", "document_type": VectorDocumentType.DISASTER_HISTORY.value},
    ))
    results = await memory_manager.search(MemorySearchRequest(
        query="cyclone West Bengal",
        domains=[MemoryDomain.VECTOR],
        limit=5,
    ))
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_manager_knowledge_graph(memory_manager: MemoryManager) -> None:
    await memory_manager.graph.add_node("mumbai", {"node_type": GraphNodeType.CITY.value, "name": "Mumbai"})
    await memory_manager.graph.add_node("maharashtra", {"node_type": GraphNodeType.STATE.value, "name": "Maharashtra"})
    await memory_manager.graph.add_edge("mumbai", "maharashtra", GraphEdgeType.LOCATED_IN.value)
    results = await memory_manager.search(MemorySearchRequest(
        query="Mumbai",
        domains=[MemoryDomain.KNOWLEDGE_GRAPH],
    ))
    assert any(r.entry.key == "mumbai" for r in results)


@pytest.mark.asyncio
async def test_manager_digital_twin_checkpoint_rollback(memory_manager: MemoryManager) -> None:
    await memory_manager.store(MemoryStoreRequest(
        domain=MemoryDomain.DIGITAL_TWIN,
        key="twin-a",
        value={"temp": 28},
        metadata={"twin_id": "twin-a", "layer": "current_climate"},
    ))
    cp = await memory_manager.checkpoint("twin-a", label="baseline")
    await memory_manager.store(MemoryStoreRequest(
        domain=MemoryDomain.DIGITAL_TWIN,
        key="twin-a",
        value={"temp": 40},
        metadata={"twin_id": "twin-a", "layer": "current_climate"},
    ))
    await memory_manager.rollback("twin-a", cp.version)
    layer = await memory_manager.retrieve(MemoryRetrieveRequest(
        domain=MemoryDomain.DIGITAL_TWIN,
        key="twin-a",
        twin_id="twin-a",
        layer_name="current_climate",
    ))
    assert layer is not None


@pytest.mark.asyncio
async def test_manager_hybrid_retrieve(memory_manager: MemoryManager) -> None:
    session_id = "hybrid-sess"
    await memory_manager.store(MemoryStoreRequest(
        domain=MemoryDomain.VECTOR,
        key="h-1",
        value={"type": "flood"},
        metadata={"text": "Chennai urban flood 2023", "document_type": VectorDocumentType.DISASTER_HISTORY.value},
    ))
    await memory_manager.graph.add_node("chennai", {"node_type": GraphNodeType.CITY.value, "name": "Chennai"})
    result = await memory_manager.hybrid_retrieve(MemorySearchRequest(
        query="Chennai flood",
        session_id=session_id,
        limit=10,
    ))
    assert result.vector_count + result.graph_count >= 1
    assert len(result.results) >= 1


@pytest.mark.asyncio
async def test_manager_summarize(memory_manager: MemoryManager) -> None:
    await memory_manager.store(MemoryStoreRequest(
        domain=MemoryDomain.VECTOR,
        key="sum-1",
        value={},
        metadata={"text": "Heatwave alert for North India", "document_type": VectorDocumentType.HISTORICAL_EVENT.value},
    ))
    summary = await memory_manager.summarize(MemorySearchRequest(
        query="heatwave",
        domains=[MemoryDomain.VECTOR],
    ))
    assert summary.content
    assert summary.token_estimate > 0


@pytest.mark.asyncio
async def test_manager_climate_store(memory_manager: MemoryManager) -> None:
    climate = ClimateState(scenario_id="scenario-2026")
    await memory_manager.store(MemoryStoreRequest(
        domain=MemoryDomain.CLIMATE,
        key="current_climate",
        value=climate,
        session_id="cl-sess",
    ))
    entry = await memory_manager.retrieve(MemoryRetrieveRequest(
        domain=MemoryDomain.CLIMATE,
        key="current_climate",
        session_id="cl-sess",
    ))
    assert entry is not None


@pytest.mark.asyncio
async def test_manager_delete(memory_manager: MemoryManager) -> None:
    await memory_manager.store(MemoryStoreRequest(
        domain=MemoryDomain.WORKING,
        key="to-delete",
        value="x",
    ))
    assert await memory_manager.delete(MemoryDomain.WORKING, "to-delete") is True
    entry = await memory_manager.retrieve(MemoryRetrieveRequest(
        domain=MemoryDomain.WORKING,
        key="to-delete",
    ))
    assert entry is None


@pytest.mark.asyncio
async def test_manager_similar(memory_manager: MemoryManager) -> None:
    await memory_manager.store(MemoryStoreRequest(
        domain=MemoryDomain.VECTOR,
        key="sim-doc",
        value={},
        metadata={"text": "monsoon rainfall pattern", "document_type": VectorDocumentType.FORECAST_SUMMARY.value},
    ))
    embedding = await memory_manager.retriever._embedding.embed("monsoon rainfall")  # type: ignore[union-attr]
    results = await memory_manager.similar(embedding, limit=3)
    assert isinstance(results, list)
