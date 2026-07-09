"""Provider-agnostic RAG interface for agricultural knowledge retrieval."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

from backend.agents.specialized.agriculture.agriculture_context import (
    GovernmentAdvisory,
    RagDocument,
    RagRetrievalResult,
)
from backend.config.logger import get_logger

logger = get_logger(__name__)


@runtime_checkable
class AgricultureKnowledgeRetriever(Protocol):
    """Provider-agnostic protocol for agricultural knowledge retrieval."""

    async def retrieve(
        self,
        query: str,
        *,
        crop_type: str | None = None,
        region: str | None = None,
        season: str | None = None,
        limit: int = 5,
        categories: list[str] | None = None,
    ) -> RagRetrievalResult:
        """Retrieve relevant agricultural knowledge documents."""


class BaseAgricultureRAG(ABC):
    """Abstract base for agriculture RAG implementations."""

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        *,
        crop_type: str | None = None,
        region: str | None = None,
        season: str | None = None,
        limit: int = 5,
        categories: list[str] | None = None,
    ) -> RagRetrievalResult:
        """Retrieve knowledge documents matching the query and filters."""


# Seeded knowledge corpus for in-memory / test retrieval
SEEDED_AGRICULTURE_KNOWLEDGE: list[dict[str, Any]] = [
    {
        "document_id": "cal-wheat-rabi",
        "category": "crop_calendar",
        "title": "Wheat Rabi Calendar — Punjab/Haryana",
        "content": (
            "Wheat (rabi): sowing Oct-Nov, tillering Dec-Jan, flowering Feb-Mar, "
            "grain filling Mar-Apr, harvest Apr-May. Critical irrigation at crown root "
            "initiation and flowering stages."
        ),
        "crops": ["wheat"], "regions": ["punjab", "haryana"], "seasons": ["rabi"],
    },
    {
        "document_id": "cal-paddy-kharif",
        "category": "crop_calendar",
        "title": "Paddy Kharif Calendar — Tamil Nadu Delta",
        "content": (
            "Paddy (kharif): nursery Jun, transplanting Jul-Aug, tillering Aug-Sep, "
            "panicle initiation Sep-Oct, flowering Oct-Nov, harvest Dec-Jan. "
            "Maintain 5-7 cm standing water during vegetative stage."
        ),
        "crops": ["paddy", "rice"], "regions": ["tamil_nadu", "chennai", "delta"], "seasons": ["kharif"],
    },
    {
        "document_id": "cal-cotton-kharif",
        "category": "crop_calendar",
        "title": "Cotton Kharif Calendar — Maharashtra",
        "content": (
            "Cotton (kharif): sowing Jun-Jul, square formation Aug, flowering Sep-Oct, "
            "boll development Oct-Nov, harvest Nov-Jan. Susceptible to water stress "
            "during flowering and boll formation."
        ),
        "crops": ["cotton"], "regions": ["maharashtra", "vidarbha"], "seasons": ["kharif"],
    },
    {
        "document_id": "adv-icar-drought",
        "category": "government_advisory",
        "title": "ICAR Drought Management Advisory",
        "content": (
            "During drought: adopt micro-irrigation, apply mulch, shift to short-duration "
            "varieties, prioritize critical growth stage irrigation, register for PM-KISAN "
            "and state drought relief schemes."
        ),
        "crops": ["wheat", "paddy", "cotton", "millet"], "regions": ["karnataka", "maharashtra"], "seasons": [],
    },
    {
        "document_id": "adv-imd-heatwave-crop",
        "category": "government_advisory",
        "title": "IMD Heatwave Crop Protection Advisory",
        "content": (
            "When max temperature exceeds 40°C during grain filling: schedule irrigation "
            "in early morning/evening, apply potassium spray, avoid nitrogen top-dressing, "
            "provide shade nets for horticulture."
        ),
        "crops": ["wheat", "paddy", "cotton"], "regions": [], "seasons": ["rabi", "kharif"],
    },
    {
        "document_id": "practice-micro-irrigation",
        "category": "best_practice",
        "title": "Micro-Irrigation Best Practices",
        "content": (
            "Drip irrigation saves 40-60% water vs flood irrigation. Install pressure-compensating "
            "emitters, maintain filters, fertigate during peak demand, monitor soil moisture at root zone."
        ),
        "crops": ["cotton", "sugarcane", "vegetables"], "regions": [], "seasons": [],
    },
    {
        "document_id": "hist-chennai-flood-crops",
        "category": "historical_failure",
        "title": "Chennai 2015 Flood — Crop Loss Analysis",
        "content": (
            "December 2015 floods destroyed standing paddy and vegetable crops across Cauvery delta. "
            "Post-flood: drain fields within 48h, apply gypsum for sodic soils, delay rabi sowing."
        ),
        "crops": ["paddy"], "regions": ["tamil_nadu", "chennai"], "seasons": ["kharif"],
    },
    {
        "document_id": "adapt-climate-resilient-varieties",
        "category": "adaptation_guideline",
        "title": "Climate-Resilient Crop Varieties — India",
        "content": (
            "Recommended varieties: HD-3086 (heat-tolerant wheat), CO-51 (flood-tolerant paddy), "
            "Suraj (drought-tolerant cotton), DH-40 (early millet). Consult KVK for local suitability."
        ),
        "crops": ["wheat", "paddy", "cotton", "millet"], "regions": [], "seasons": [],
    },
    {
        "document_id": "adv-karnataka-drought-millet",
        "category": "government_advisory",
        "title": "Karnataka Drought — Millet Promotion Advisory",
        "content": (
            "In drought-affected districts: promote ragi and jowar, provide seed subsidies, "
            "activate cattle fodder camps, implement watershed programs under MGNREGA."
        ),
        "crops": ["millet", "ragi", "jowar"], "regions": ["karnataka"], "seasons": ["kharif", "rabi"],
    },
    {
        "document_id": "practice-pest-heat-humidity",
        "category": "best_practice",
        "title": "Pest Management in High Humidity",
        "content": (
            "Elevated humidity favors fungal diseases and bollworm in cotton. Monitor with pheromone "
            "traps, apply IPM, avoid broad-spectrum pesticides during flowering."
        ),
        "crops": ["cotton", "paddy"], "regions": ["maharashtra", "tamil_nadu"], "seasons": ["kharif"],
    },
]


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _score_document(
    doc: dict[str, Any],
    query_tokens: set[str],
    crop_type: str | None,
    region: str | None,
    season: str | None,
    categories: list[str] | None,
) -> float:
    content_tokens = _tokenize(doc.get("title", "") + " " + doc.get("content", ""))
    overlap = len(query_tokens & content_tokens) / max(len(query_tokens), 1)
    score = overlap * 0.5

    if crop_type and crop_type.lower() in [c.lower() for c in doc.get("crops", [])]:
        score += 0.25
    if region:
        region_lower = region.lower().replace(" ", "_")
        if any(region_lower in r or r in region_lower for r in doc.get("regions", [])):
            score += 0.15
    if season and season.lower() in [s.lower() for s in doc.get("seasons", [])]:
        score += 0.1
    if categories and doc.get("category") in categories:
        score += 0.1

    return min(score, 1.0)


class InMemoryAgricultureRAG(BaseAgricultureRAG):
    """In-memory RAG implementation with seeded agricultural knowledge."""

    def __init__(self, corpus: list[dict[str, Any]] | None = None) -> None:
        self._corpus = corpus or SEEDED_AGRICULTURE_KNOWLEDGE

    async def retrieve(
        self,
        query: str,
        *,
        crop_type: str | None = None,
        region: str | None = None,
        season: str | None = None,
        limit: int = 5,
        categories: list[str] | None = None,
    ) -> RagRetrievalResult:
        query_tokens = _tokenize(query)
        if crop_type:
            query_tokens |= _tokenize(crop_type)
        if region:
            query_tokens |= _tokenize(region)
        if season:
            query_tokens |= _tokenize(season)

        scored: list[tuple[float, dict[str, Any]]] = []
        for doc in self._corpus:
            if categories and doc.get("category") not in categories:
                continue
            score = _score_document(doc, query_tokens, crop_type, region, season, categories)
            if score > 0.05:
                scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:limit]

        documents: list[RagDocument] = []
        advisories: list[GovernmentAdvisory] = []
        for score, doc in top:
            rag_doc = RagDocument(
                document_id=doc["document_id"],
                category=doc["category"],
                title=doc["title"],
                content=doc["content"],
                relevance_score=round(score, 3),
                metadata={"crops": doc.get("crops", []), "regions": doc.get("regions", [])},
            )
            documents.append(rag_doc)
            if doc.get("category") == "government_advisory":
                advisories.append(GovernmentAdvisory(
                    source="Government Advisory",
                    title=doc["title"],
                    content=doc["content"],
                    relevance_score=round(score, 3),
                ))

        logger.debug(
            "agriculture_rag_retrieved",
            query=query[:80],
            document_count=len(documents),
        )
        return RagRetrievalResult(
            query=query,
            documents=documents,
            advisories=advisories,
            retrieval_count=len(documents),
        )


class AgricultureRagService:
    """Facade for agriculture knowledge retrieval with optional provider injection."""

    def __init__(self, retriever: AgricultureKnowledgeRetriever | None = None) -> None:
        self._retriever: AgricultureKnowledgeRetriever = retriever or InMemoryAgricultureRAG()

    @property
    def retriever(self) -> AgricultureKnowledgeRetriever:
        return self._retriever

    async def retrieve_for_context(
        self,
        query: str,
        *,
        crop_type: str | None = None,
        region: str | None = None,
        state: str | None = None,
        season: str | None = None,
        stress_signals: dict[str, Any] | None = None,
        limit: int = 5,
    ) -> RagRetrievalResult:
        categories: list[str] | None = None
        if stress_signals:
            if stress_signals.get("drought_risk"):
                categories = ["government_advisory", "adaptation_guideline", "best_practice"]
            elif stress_signals.get("flood_impact"):
                categories = ["historical_failure", "government_advisory", "crop_calendar"]
            elif stress_signals.get("heat_stress"):
                categories = ["government_advisory", "best_practice"]

        region_key = state or region
        return await self._retriever.retrieve(
            query,
            crop_type=crop_type,
            region=region_key,
            season=season,
            limit=limit,
            categories=categories,
        )
