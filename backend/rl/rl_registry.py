"""RL algorithm registry and policy metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RLAlgorithm(StrEnum):
    """Supported reinforcement learning algorithms."""

    PPO = "ppo"
    SAC = "sac"
    DQN = "dqn"
    A2C = "a2c"
    MAPPO = "mappo"


DEFAULT_ALGORITHM = RLAlgorithm.PPO


class PolicyStatus(StrEnum):
    """Lifecycle status of a registered policy."""

    ACTIVE = "active"
    STAGED = "staged"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class PolicyMetadata(BaseModel):
    """Versioned metadata for an RL policy artifact."""

    policy_id: str
    name: str
    algorithm: RLAlgorithm
    version: str
    status: PolicyStatus = PolicyStatus.ACTIVE
    decision_types: list[str] = Field(default_factory=list)
    description: str = ""
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RLRegistry:
    """In-memory registry for policy metadata and algorithm factories."""

    def __init__(self) -> None:
        self._policies: dict[str, PolicyMetadata] = {}
        self._active_policy_id: str | None = None
        self._algorithm_defaults: dict[RLAlgorithm, dict[str, Any]] = {
            RLAlgorithm.PPO: {"clip_epsilon": 0.2, "gamma": 0.99, "gae_lambda": 0.95},
            RLAlgorithm.SAC: {"alpha": 0.2, "gamma": 0.99, "tau": 0.005},
            RLAlgorithm.DQN: {"epsilon": 0.1, "gamma": 0.99, "target_update_freq": 100},
            RLAlgorithm.A2C: {"gamma": 0.99, "entropy_coef": 0.01, "value_coef": 0.5},
            RLAlgorithm.MAPPO: {"clip_epsilon": 0.2, "gamma": 0.99, "num_agents": 1},
        }

    def register(self, metadata: PolicyMetadata) -> PolicyMetadata:
        metadata.updated_at = datetime.now(timezone.utc)
        self._policies[metadata.policy_id] = metadata
        if metadata.status == PolicyStatus.ACTIVE and self._active_policy_id is None:
            self._active_policy_id = metadata.policy_id
        return metadata

    def get(self, policy_id: str) -> PolicyMetadata | None:
        return self._policies.get(policy_id)

    def list_policies(
        self,
        *,
        algorithm: RLAlgorithm | None = None,
        status: PolicyStatus | None = None,
    ) -> list[PolicyMetadata]:
        results = list(self._policies.values())
        if algorithm:
            results = [p for p in results if p.algorithm == algorithm]
        if status:
            results = [p for p in results if p.status == status]
        return sorted(results, key=lambda p: p.updated_at, reverse=True)

    def set_active(self, policy_id: str) -> PolicyMetadata:
        if policy_id not in self._policies:
            raise KeyError(f"Policy not found: {policy_id}")
        for pid, meta in self._policies.items():
            if meta.status == PolicyStatus.ACTIVE and pid != policy_id:
                meta.status = PolicyStatus.STAGED
        active = self._policies[policy_id]
        active.status = PolicyStatus.ACTIVE
        active.updated_at = datetime.now(timezone.utc)
        self._active_policy_id = policy_id
        return active

    @property
    def active_policy_id(self) -> str | None:
        return self._active_policy_id

    def get_active(self) -> PolicyMetadata | None:
        if self._active_policy_id:
            return self._policies.get(self._active_policy_id)
        return None

    def default_hyperparameters(self, algorithm: RLAlgorithm) -> dict[str, Any]:
        return dict(self._algorithm_defaults.get(algorithm, {}))

    def remove(self, policy_id: str) -> bool:
        if policy_id not in self._policies:
            return False
        del self._policies[policy_id]
        if self._active_policy_id == policy_id:
            self._active_policy_id = None
        return True
