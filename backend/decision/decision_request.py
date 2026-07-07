"""Unified decision request schema for all specialized agents."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from backend.decision.decision_actions import DecisionAction
from backend.decision.decision_constraints import DecisionConstraints
from backend.decision.decision_context import DecisionContext
from backend.decision.decision_priority import DecisionPriority
from backend.decision.decision_types import (
    DecisionStatus,
    DecisionType,
    Objective,
    RiskAssessment,
)


class DecisionRequest(BaseModel):
    """
    Agent-agnostic decision request consumed by RL and orchestration layers.

    Every specialized agent produces exactly this schema. The RL engine
    receives a uniform structure regardless of originating agent.
    """

    decision_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    decision_type: DecisionType
    priority: DecisionPriority = DecisionPriority.NORMAL
    status: DecisionStatus = DecisionStatus.DRAFT

    context: DecisionContext = Field(default_factory=DecisionContext)

    objectives: list[Objective] = Field(default_factory=list)
    constraints: DecisionConstraints = Field(default_factory=DecisionConstraints)
    possible_actions: list[DecisionAction] = Field(default_factory=list)

    risk: RiskAssessment = Field(default_factory=RiskAssessment)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    expected_reward: float | None = Field(default=None)

    need_simulation: bool = False
    need_other_agents: list[str] = Field(default_factory=list)
    need_human: bool = False
    need_rl: bool = False

    rationale: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("agent_id")
    @classmethod
    def agent_id_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("agent_id must not be empty")
        return value.strip()

    @property
    def scenario(self) -> str:
        return self.context.scenario.scenario_id

    @property
    def forecast_reference(self) -> str | None:
        ref = self.context.forecast_reference
        return ref.forecast_id if ref else None

    @property
    def simulation_reference(self) -> str | None:
        ref = self.context.simulation_reference
        return ref.simulation_id if ref else None

    def mark_updated(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def to_rl_payload(self) -> dict[str, Any]:
        """Serialize for RL consumption with agent identity stripped."""
        data = self.model_dump(mode="json")
        data.pop("agent_id", None)
        data.pop("metadata", None)
        data.pop("rationale", None)
        data.pop("created_at", None)
        data.pop("updated_at", None)
        data.pop("status", None)
        return data
