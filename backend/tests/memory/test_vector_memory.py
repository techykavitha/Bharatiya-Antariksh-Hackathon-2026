"""Unit tests for Qdrant vector memory."""

import pytest

from backend.agents.memory.memory_types import VectorDocumentType
from backend.agents.memory.vector_memory import QdrantVectorMemory


@pytest.mark.asyncio
async def test_vector_insert_and_read(vector_store: QdrantVectorMemory) -> None:
    key = await vector_store.insert(
        "doc-1",
        "Major flood event in Chennai 2015",
        {"severity": "high"},
        document_type=VectorDocumentType.DISASTER_HISTORY,
    )
    entry = await vector_store.read(key)
    assert entry is not None
    assert entry.value["severity"] == "high"


@pytest.mark.asyncio
async def test_vector_semantic_search(vector_store: QdrantVectorMemory) -> None:
    await vector_store.insert(
        "flood-1",
        "Chennai flood disaster December 2015",
        {"region": "chennai"},
        document_type=VectorDocumentType.DISASTER_HISTORY,
    )
    await vector_store.insert(
        "heat-1",
        "Heatwave in Rajasthan summer 2023",
        {"region": "rajasthan"},
        document_type=VectorDocumentType.HISTORICAL_EVENT,
    )
    results = await vector_store.search("Chennai flood", limit=5)
    assert len(results) >= 1
    assert any("flood" in str(r.metadata.get("text", "")).lower() for r in results)


@pytest.mark.asyncio
async def test_vector_hybrid_search(vector_store: QdrantVectorMemory) -> None:
    await vector_store.insert(
        "policy-1",
        "National disaster management policy framework 2019",
        {},
        document_type=VectorDocumentType.POLICY_REPORT,
    )
    results = await vector_store.hybrid_search("disaster management policy", limit=3)
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_vector_update(vector_store: QdrantVectorMemory) -> None:
    await vector_store.insert("upd-1", "original text", {}, document_type=VectorDocumentType.RESEARCH_DOCUMENT)
    await vector_store.update("upd-1", text="updated research findings", value={"status": "revised"})
    entry = await vector_store.read("upd-1")
    assert entry is not None
    assert entry.value["status"] == "revised"


@pytest.mark.asyncio
async def test_vector_delete(vector_store: QdrantVectorMemory) -> None:
    await vector_store.insert("del-1", "to delete", {}, document_type=VectorDocumentType.EMBEDDING)
    assert await vector_store.delete("del-1") is True
    assert await vector_store.read("del-1") is None


@pytest.mark.asyncio
async def test_vector_similarity_search(vector_store: QdrantVectorMemory, embedding_provider) -> None:
    await vector_store.insert("sim-1", "cyclone Amphan impact", {}, document_type=VectorDocumentType.DISASTER_HISTORY)
    embedding = await embedding_provider.embed("cyclone Amphan impact")
    results = await vector_store.similarity_search(embedding, limit=3)
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_vector_metadata_filter(vector_store: QdrantVectorMemory) -> None:
    await vector_store.insert("fc-1", "forecast rain Mumbai", {"region": "mumbai"}, document_type=VectorDocumentType.FORECAST_SUMMARY)
    await vector_store.insert("fc-2", "forecast rain Delhi", {"region": "delhi"}, document_type=VectorDocumentType.FORECAST_SUMMARY)
    results = await vector_store.search("forecast rain", filters={"region": "mumbai"}, limit=5)
    assert all(r.metadata.get("region") == "mumbai" for r in results)
