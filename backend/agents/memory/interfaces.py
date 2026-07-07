"""Memory subsystem interfaces for Hyperion Climate Twin."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    """A single retrievable memory record."""

    key: str
    value: Any
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: float | None = Field(default=None, description="Relevance score for ranked retrieval")


class AgentMemory(ABC):
    """
    Abstract interface for all agent memory backends.

    Concrete implementations (Redis, vector store, knowledge graph,
    digital twin) must subclass this interface.
    """

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Return the canonical backend identifier."""

    @abstractmethod
    async def write(self, key: str, value: Any, *, metadata: dict[str, Any] | None = None) -> None:
        """Persist a value under the given key."""

    @abstractmethod
    async def read(self, key: str) -> MemoryEntry | None:
        """Retrieve a single entry by key, or None if not found."""

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete an entry. Returns True if the key existed."""

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[MemoryEntry]:
        """Search memory for entries relevant to the query."""

    @abstractmethod
    async def clear(self, namespace: str | None = None) -> int:
        """Clear entries, optionally scoped to a namespace. Returns count removed."""


class RedisMemory(AgentMemory):
    """
    Interface for short-term, session-scoped memory backed by Redis.

    Implementation deferred to infrastructure layer.
    """

    @property
    def backend_name(self) -> str:
        return "redis"

    @abstractmethod
    async def write(self, key: str, value: Any, *, metadata: dict[str, Any] | None = None) -> None: ...

    @abstractmethod
    async def read(self, key: str) -> MemoryEntry | None: ...

    @abstractmethod
    async def delete(self, key: str) -> bool: ...

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[MemoryEntry]: ...

    @abstractmethod
    async def clear(self, namespace: str | None = None) -> int: ...

    @abstractmethod
    async def set_ttl(self, key: str, ttl_seconds: int) -> None:
        """Set or refresh the time-to-live for a key."""

    @abstractmethod
    async def get_session_keys(self, session_id: str) -> list[str]:
        """Return all keys associated with a session."""


class VectorMemory(AgentMemory):
    """
    Interface for semantic retrieval memory backed by a vector database.

    Implementation deferred to infrastructure layer (Qdrant).
    """

    @property
    def backend_name(self) -> str:
        return "vector"

    @abstractmethod
    async def write(self, key: str, value: Any, *, metadata: dict[str, Any] | None = None) -> None: ...

    @abstractmethod
    async def read(self, key: str) -> MemoryEntry | None: ...

    @abstractmethod
    async def delete(self, key: str) -> bool: ...

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[MemoryEntry]: ...

    @abstractmethod
    async def clear(self, namespace: str | None = None) -> int: ...

    @abstractmethod
    async def upsert_embedding(
        self,
        key: str,
        embedding: list[float],
        payload: dict[str, Any],
    ) -> None:
        """Store or update a vector embedding with associated payload."""

    @abstractmethod
    async def similarity_search(
        self,
        embedding: list[float],
        *,
        limit: int = 10,
        collection: str | None = None,
    ) -> list[MemoryEntry]:
        """Retrieve entries by vector similarity."""


class KnowledgeGraphMemory(AgentMemory):
    """
    Interface for relational climate knowledge stored as a graph.

    Implementation deferred to infrastructure layer (NetworkX / PostGIS).
    """

    @property
    def backend_name(self) -> str:
        return "knowledge_graph"

    @abstractmethod
    async def write(self, key: str, value: Any, *, metadata: dict[str, Any] | None = None) -> None: ...

    @abstractmethod
    async def read(self, key: str) -> MemoryEntry | None: ...

    @abstractmethod
    async def delete(self, key: str) -> bool: ...

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[MemoryEntry]: ...

    @abstractmethod
    async def clear(self, namespace: str | None = None) -> int: ...

    @abstractmethod
    async def add_node(self, node_id: str, attributes: dict[str, Any]) -> None:
        """Add or update a node in the knowledge graph."""

    @abstractmethod
    async def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        *,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Add a directed edge between two nodes."""

    @abstractmethod
    async def traverse(
        self,
        start_node: str,
        *,
        relation: str | None = None,
        max_depth: int = 3,
    ) -> list[MemoryEntry]:
        """Traverse the graph from a starting node."""


class DigitalTwinMemory(AgentMemory):
    """
    Interface for digital twin state persistence and retrieval.

    Implementation deferred to infrastructure layer.
    """

    @property
    def backend_name(self) -> str:
        return "digital_twin"

    @abstractmethod
    async def write(self, key: str, value: Any, *, metadata: dict[str, Any] | None = None) -> None: ...

    @abstractmethod
    async def read(self, key: str) -> MemoryEntry | None: ...

    @abstractmethod
    async def delete(self, key: str) -> bool: ...

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[MemoryEntry]: ...

    @abstractmethod
    async def clear(self, namespace: str | None = None) -> int: ...

    @abstractmethod
    async def snapshot(self, twin_id: str) -> MemoryEntry:
        """Capture a point-in-time snapshot of the digital twin."""

    @abstractmethod
    async def restore(self, twin_id: str, version: str) -> MemoryEntry:
        """Restore the digital twin to a specific version."""

    @abstractmethod
    async def get_layer(self, twin_id: str, layer_name: str) -> MemoryEntry | None:
        """Retrieve a specific data layer from the digital twin."""
