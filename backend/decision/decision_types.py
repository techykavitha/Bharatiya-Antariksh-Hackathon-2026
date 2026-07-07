"""Core type definitions for the Hyperion decision framework."""

from __future__ import annotations

from enum import IntEnum, StrEnum

from pydantic import BaseModel, Field


class DecisionType(StrEnum):
    """Domain classification for decision requests.

    RL receives the same schema regardless of decision type.
    """

    FLOOD = "flood"
    WATER = "water"
    AGRICULTURE = "agriculture"
    HEATWAVE = "heatwave"
    URBAN = "urban"
    AQI = "aqi"
    CYCLONE = "cyclone"
    DISASTER = "disaster"
    GENERAL = "general"


class RiskLevel(StrEnum):
    """Ordinal risk classification for decisions and actions."""

    NEGLIGIBLE = "negligible"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"
    CRITICAL = "critical"


class DecisionStatus(StrEnum):
    """Lifecycle status for queued decision requests."""

    DRAFT = "draft"
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RiskLevelScore(IntEnum):
    """Numeric ordering for risk level comparison."""

    NEGLIGIBLE = 0
    LOW = 1
    MODERATE = 2
    HIGH = 3
    SEVERE = 4
    CRITICAL = 5


RISK_LEVEL_ORDER: dict[RiskLevel, int] = {
    RiskLevel.NEGLIGIBLE: RiskLevelScore.NEGLIGIBLE,
    RiskLevel.LOW: RiskLevelScore.LOW,
    RiskLevel.MODERATE: RiskLevelScore.MODERATE,
    RiskLevel.HIGH: RiskLevelScore.HIGH,
    RiskLevel.SEVERE: RiskLevelScore.SEVERE,
    RiskLevel.CRITICAL: RiskLevelScore.CRITICAL,
}


class Objective(BaseModel):
    """Weighted optimization objective for RL policy selection."""

    objective_id: str
    description: str
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    maximize: bool = True
    metric: str | None = None


class RiskAssessment(BaseModel):
    """Structured risk profile attached to a decision request."""

    level: RiskLevel = RiskLevel.MODERATE
    score: float = Field(default=0.5, ge=0.0, le=1.0)
    factors: list[str] = Field(default_factory=list)
    affected_regions: list[str] = Field(default_factory=list)
    affected_population: int = Field(default=0, ge=0)
    horizon_hours: int = Field(default=72, ge=1)

    def exceeds(self, other: RiskLevel) -> bool:
        return RISK_LEVEL_ORDER[self.level] >= RISK_LEVEL_ORDER[other]
