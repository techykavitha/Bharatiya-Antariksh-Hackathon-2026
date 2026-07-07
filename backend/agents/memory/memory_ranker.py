"""Weighted memory ranking for hybrid retrieval results."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

from backend.agents.memory.interfaces import MemoryEntry
from backend.agents.memory.memory_types import MemoryDomain, RankedMemory


@dataclass(frozen=True)
class RankingWeights:
    """Configurable weights for memory ranking dimensions."""

    recency: float = 0.20
    similarity: float = 0.35
    importance: float = 0.20
    frequency: float = 0.10
    domain_relevance: float = 0.15

    def __post_init__(self) -> None:
        total = self.recency + self.similarity + self.importance + self.frequency + self.domain_relevance
        if not math.isclose(total, 1.0, rel_tol=1e-3):
            raise ValueError(f"Ranking weights must sum to 1.0, got {total}")


class MemoryRanker:
    """
    Ranks retrieved memory entries using multi-factor weighted scoring.

    Factors: recency, similarity, importance, access frequency, and
    domain relevance to the active query context.
    """

    def __init__(
        self,
        *,
        weights: RankingWeights | None = None,
        domain_boost: dict[MemoryDomain, float] | None = None,
    ) -> None:
        self._weights = weights or RankingWeights()
        self._domain_boost = domain_boost or {
            MemoryDomain.CLIMATE: 1.2,
            MemoryDomain.DIGITAL_TWIN: 1.15,
            MemoryDomain.VECTOR: 1.0,
            MemoryDomain.KNOWLEDGE_GRAPH: 1.1,
            MemoryDomain.CONVERSATION: 0.9,
            MemoryDomain.WORKING: 0.7,
            MemoryDomain.SESSION: 0.8,
            MemoryDomain.WORKFLOW: 1.0,
        }
        self._access_counts: dict[str, int] = {}

    def rank(
        self,
        entries: list[tuple[MemoryEntry, MemoryDomain]],
        *,
        query: str,
        target_domains: list[MemoryDomain] | None = None,
        limit: int = 10,
    ) -> list[RankedMemory]:
        """Score and rank a list of memory entries."""
        ranked: list[RankedMemory] = []
        now = time.time()

        for entry, domain in entries:
            recency = self._score_recency(entry, now)
            similarity = self._score_similarity(entry, query)
            importance = self._score_importance(entry)
            frequency = self._score_frequency(entry.key)
            domain_rel = self._score_domain_relevance(domain, target_domains)

            final = (
                self._weights.recency * recency
                + self._weights.similarity * similarity
                + self._weights.importance * importance
                + self._weights.frequency * frequency
                + self._weights.domain_relevance * domain_rel
            )
            boost = self._domain_boost.get(domain, 1.0)
            final = min(final * boost, 1.0)

            ranked.append(
                RankedMemory(
                    entry=entry,
                    domain=domain,
                    final_score=round(final, 4),
                    recency_score=round(recency, 4),
                    similarity_score=round(similarity, 4),
                    importance_score=round(importance, 4),
                    frequency_score=round(frequency, 4),
                    domain_relevance_score=round(domain_rel, 4),
                ),
            )
            self._access_counts[entry.key] = self._access_counts.get(entry.key, 0) + 1

        ranked.sort(key=lambda r: r.final_score, reverse=True)
        return ranked[:limit]

    def _score_recency(self, entry: MemoryEntry, now: float) -> float:
        stored_at = entry.metadata.get("stored_at") or entry.metadata.get("created_at")
        if stored_at is None:
            return 0.5
        if isinstance(stored_at, str):
            from datetime import datetime

            try:
                stored_at = datetime.fromisoformat(stored_at.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return 0.5
        age_hours = max((now - float(stored_at)) / 3600, 0.0)
        return math.exp(-age_hours / 168.0)  # half-life ~1 week

    def _score_similarity(self, entry: MemoryEntry, query: str) -> float:
        if entry.score is not None:
            return min(max(float(entry.score), 0.0), 1.0)
        query_tokens = set(query.lower().split())
        text = str(entry.value).lower() + " " + str(entry.metadata).lower()
        text_tokens = set(text.split())
        if not query_tokens:
            return 0.0
        return len(query_tokens & text_tokens) / len(query_tokens)

    def _score_importance(self, entry: MemoryEntry) -> float:
        importance = entry.metadata.get("importance")
        if importance is not None:
            return min(max(float(importance), 0.0), 1.0)
        doc_type = entry.metadata.get("document_type")
        high_importance = {"disaster_history", "policy_report", "forecast_summary"}
        if doc_type in high_importance:
            return 0.9
        if entry.metadata.get("type") == "reasoning":
            return 0.6
        return 0.4

    def _score_frequency(self, key: str) -> float:
        count = self._access_counts.get(key, 0)
        return min(count / 10.0, 1.0)

    def _score_domain_relevance(
        self,
        domain: MemoryDomain,
        target_domains: list[MemoryDomain] | None,
    ) -> float:
        if not target_domains:
            return 0.7
        if domain in target_domains:
            return 1.0
        related = {
            MemoryDomain.CLIMATE: {MemoryDomain.DIGITAL_TWIN, MemoryDomain.VECTOR},
            MemoryDomain.DIGITAL_TWIN: {MemoryDomain.CLIMATE, MemoryDomain.VECTOR},
            MemoryDomain.VECTOR: {MemoryDomain.CLIMATE, MemoryDomain.KNOWLEDGE_GRAPH},
            MemoryDomain.KNOWLEDGE_GRAPH: {MemoryDomain.CLIMATE, MemoryDomain.VECTOR},
        }
        if domain in related and any(d in target_domains for d in related[domain]):
            return 0.6
        return 0.2
