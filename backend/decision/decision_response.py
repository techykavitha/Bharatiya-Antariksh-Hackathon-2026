"""Decision response schema returned by RL or heuristic engines."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.decision.decision_actions import ActionRanking, DecisionAction, RejectedAction
from backend.decision.decision_types import DecisionStatus


class DecisionResponse(BaseModel):
    """
    Response to a ``DecisionRequest``, typically produced by the RL engine.

    Contains the chosen action, ranking of alternatives, and rejection reasons.
    """

    response_id: str = Field(default_factory=lambda: str(uuid4()))
    decision_id: str
    status: DecisionStatus = DecisionStatus.COMPLETED

    chosen_action: DecisionAction | None = None
    ranking: list[ActionRanking] = Field(default_factory=list)
    reward: float | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""
    rejected_actions: list[RejectedAction] = Field(default_factory=list)

    engine_id: str = "rl_engine"
    processing_time_ms: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def chosen_action_id(self) -> str | None:
        return self.chosen_action.action_id if self.chosen_action else None

    @property
    def top_ranked_action_id(self) -> str | None:
        if not self.ranking:
            return self.chosen_action_id
        return min(self.ranking, key=lambda r: r.rank).action_id

    def is_successful(self) -> bool:
        return self.status == DecisionStatus.COMPLETED and self.chosen_action is not None
