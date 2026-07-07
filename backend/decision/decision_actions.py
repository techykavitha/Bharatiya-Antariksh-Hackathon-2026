"""Action models for the unified decision framework."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.decision.decision_types import RiskLevel


class DecisionAction(BaseModel):
    """A candidate action for RL or rule-based selection.

    Represents every possible action the decision engine may evaluate.
    """

    action_id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    cost: float = Field(default=0.0, ge=0.0)
    risk: RiskLevel = RiskLevel.MODERATE
    risk_score: float = Field(default=0.5, ge=0.0, le=1.0)
    expected_benefit: float = Field(default=0.0)
    affected_regions: list[str] = Field(default_factory=list)
    affected_population: int = Field(default=0, ge=0)
    category: str = "operational"
    reversible: bool = True
    prerequisites: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def net_value(self) -> float:
        """Simple net value heuristic: benefit minus cost."""
        return self.expected_benefit - self.cost


class ActionRanking(BaseModel):
    """Ranked action entry returned by RL or heuristic selection."""

    action_id: str
    rank: int = Field(..., ge=1)
    score: float = Field(default=0.0)
    expected_reward: float = Field(default=0.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = ""


class RejectedAction(BaseModel):
    """An action evaluated but not selected."""

    action_id: str
    reason: str
    constraint_violated: str | None = None
    score: float | None = None
