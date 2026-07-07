"""Action space representation for RL optimization."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from backend.decision.decision_actions import DecisionAction
from backend.decision.decision_request import DecisionRequest


class ActionSpaceType(StrEnum):
    """Action space topology."""

    DISCRETE = "discrete"
    CONTINUOUS = "continuous"
    HYBRID = "hybrid"


class ContinuousActionParams(BaseModel):
    """Continuous parameters associated with a discrete action selection."""

    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    duration_hours: float = Field(default=24.0, ge=0.0)
    allocation_fraction: float = Field(default=1.0, ge=0.0, le=1.0)


class EncodedAction(BaseModel):
    """RL-internal action encoding."""

    discrete_index: int = Field(..., ge=0)
    action_id: str
    continuous: ContinuousActionParams = Field(default_factory=ContinuousActionParams)
    feature_vector: list[float] = Field(default_factory=list)


class ActionSpace(BaseModel):
    """
    Standardized action space derived from a ``DecisionRequest``.

    Maps candidate ``DecisionAction`` entries to discrete indices with
    optional continuous modulation parameters.
    """

    space_type: ActionSpaceType = ActionSpaceType.HYBRID
    actions: list[DecisionAction] = Field(default_factory=list)
    continuous_dim: int = Field(default=3, ge=0)
    version: str = "1.0"

    @property
    def discrete_size(self) -> int:
        return len(self.actions)

    @classmethod
    def from_request(cls, request: DecisionRequest) -> ActionSpace:
        return cls(
            actions=list(request.possible_actions),
            space_type=ActionSpaceType.HYBRID if request.possible_actions else ActionSpaceType.DISCRETE,
        )

    def encode(self, action: DecisionAction) -> EncodedAction:
        index = self._index_of(action.action_id)
        return EncodedAction(
            discrete_index=index,
            action_id=action.action_id,
            continuous=ContinuousActionParams(
                intensity=min(action.expected_benefit / max(action.cost + 1.0, 1.0), 1.0),
                duration_hours=24.0,
                allocation_fraction=0.8 if action.reversible else 1.0,
            ),
            feature_vector=self._action_features(action),
        )

    def decode(self, encoded: EncodedAction) -> DecisionAction:
        if encoded.discrete_index < 0 or encoded.discrete_index >= len(self.actions):
            raise IndexError(f"Invalid action index: {encoded.discrete_index}")
        return self.actions[encoded.discrete_index]

    def decode_index(self, index: int) -> DecisionAction:
        return self.decode(EncodedAction(discrete_index=index, action_id=self.actions[index].action_id))

    def all_encoded(self) -> list[EncodedAction]:
        return [self.encode(a) for a in self.actions]

    def _index_of(self, action_id: str) -> int:
        for i, action in enumerate(self.actions):
            if action.action_id == action_id:
                return i
        raise KeyError(f"Action not in space: {action_id}")

    def _action_features(self, action: DecisionAction) -> list[float]:
        return [
            action.cost,
            action.expected_benefit,
            action.risk_score,
            float(action.affected_population) / 1_000_000.0,
            1.0 if action.reversible else 0.0,
            action.net_value,
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "space_type": self.space_type.value,
            "discrete_size": self.discrete_size,
            "continuous_dim": self.continuous_dim,
            "action_ids": [a.action_id for a in self.actions],
        }
