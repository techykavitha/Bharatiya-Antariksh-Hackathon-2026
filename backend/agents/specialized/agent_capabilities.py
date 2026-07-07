"""Capability declaration and registry for specialized agents."""

from __future__ import annotations

import asyncio
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from backend.utils.errors import DependencyRegistrationError


class CapabilityCategory(StrEnum):
    """High-level capability families for specialized agents."""

    ANALYSIS = "analysis"
    PREDICTION = "prediction"
    OPTIMIZATION = "optimization"
    SIMULATION = "simulation"
    PLANNING = "planning"
    INTERPRETATION = "interpretation"
    FORECAST = "forecast"
    MONITORING = "monitoring"
    COMMUNICATION = "communication"


class AgentCapability(BaseModel):
    """
    Declarative capability exposed by a specialized agent.

    Future agents register one or more capabilities describing what they can do.
    Examples (declared by subclasses, not hard-coded here):
      - Flood Analysis
      - Heat Index
      - AQI Prediction
      - Reservoir Optimization
      - Simulation
      - Planning
      - Forecast Interpretation
    """

    capability_id: str
    name: str
    category: CapabilityCategory
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    requires_simulation: bool = False
    requires_forecast: bool = False
    requires_rl: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    def matches_query(self, query: str) -> float:
        """Return a confidence score [0, 1] for query relevance."""
        if not self.keywords:
            return 0.0
        lowered = query.lower()
        hits = sum(1 for kw in self.keywords if kw.lower() in lowered)
        return min(hits / len(self.keywords), 1.0)


class CapabilityRegistry:
    """Per-agent registry of declared capabilities."""

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id
        self._capabilities: dict[str, AgentCapability] = {}
        self._lock = asyncio.Lock()

    @property
    def agent_id(self) -> str:
        return self._agent_id

    async def register(self, capability: AgentCapability) -> None:
        async with self._lock:
            if capability.capability_id in self._capabilities:
                raise DependencyRegistrationError(
                    f"Capability '{capability.capability_id}' already registered "
                    f"for agent '{self._agent_id}'",
                    details={"agent_id": self._agent_id, "capability_id": capability.capability_id},
                )
            self._capabilities[capability.capability_id] = capability

    async def unregister(self, capability_id: str) -> bool:
        async with self._lock:
            return self._capabilities.pop(capability_id, None) is not None

    async def list_capabilities(self) -> list[AgentCapability]:
        async with self._lock:
            return list(self._capabilities.values())

    async def resolve(self, capability_id: str) -> AgentCapability | None:
        async with self._lock:
            return self._capabilities.get(capability_id)

    async def match_query(self, query: str, *, min_score: float = 0.2) -> list[AgentCapability]:
        async with self._lock:
            scored = [
                (cap, cap.matches_query(query))
                for cap in self._capabilities.values()
            ]
        matches = [(cap, score) for cap, score in scored if score >= min_score]
        matches.sort(key=lambda item: item[1], reverse=True)
        return [cap for cap, _ in matches]

    async def capability_names(self) -> list[str]:
        caps = await self.list_capabilities()
        return [cap.name for cap in caps]
