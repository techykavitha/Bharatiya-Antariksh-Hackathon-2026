"""Unit tests for memory ranker."""

from backend.agents.memory.interfaces import MemoryEntry
from backend.agents.memory.memory_ranker import MemoryRanker, RankingWeights
from backend.agents.memory.memory_types import MemoryDomain


def test_ranker_orders_by_relevance() -> None:
    ranker = MemoryRanker()
    entries = [
        (MemoryEntry(key="a", value="flood chennai", metadata={"importance": 0.9}, score=0.8), MemoryDomain.VECTOR),
        (MemoryEntry(key="b", value="unrelated topic", metadata={}, score=0.2), MemoryDomain.VECTOR),
    ]
    ranked = ranker.rank(entries, query="flood chennai", limit=2)
    assert ranked[0].entry.key == "a"
    assert ranked[0].final_score > ranked[1].final_score


def test_ranker_domain_boost() -> None:
    ranker = MemoryRanker()
    entries = [
        (MemoryEntry(key="c", value="climate data", score=0.5), MemoryDomain.CLIMATE),
        (MemoryEntry(key="w", value="climate data", score=0.5), MemoryDomain.WORKING),
    ]
    ranked = ranker.rank(entries, query="climate", target_domains=[MemoryDomain.CLIMATE])
    climate = next(r for r in ranked if r.entry.key == "c")
    working = next(r for r in ranked if r.entry.key == "w")
    assert climate.final_score >= working.final_score


def test_ranker_custom_weights() -> None:
    weights = RankingWeights(recency=0.0, similarity=1.0, importance=0.0, frequency=0.0, domain_relevance=0.0)
    ranker = MemoryRanker(weights=weights)
    entries = [
        (MemoryEntry(key="x", value="exact match query", score=0.95), MemoryDomain.VECTOR),
        (MemoryEntry(key="y", value="other", score=0.1), MemoryDomain.VECTOR),
    ]
    ranked = ranker.rank(entries, query="exact match query")
    assert ranked[0].entry.key == "x"


def test_ranker_frequency_increases_on_repeated_access() -> None:
    ranker = MemoryRanker()
    entry = (MemoryEntry(key="freq", value="test", score=0.5), MemoryDomain.VECTOR)
    ranker.rank([entry], query="test")
    ranker.rank([entry], query="test")
    ranked = ranker.rank([entry], query="test")
    assert ranked[0].frequency_score > 0
