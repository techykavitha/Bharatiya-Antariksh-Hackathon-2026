"""Pluggable RL algorithm engines and policy interfaces."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from backend.decision.decision_actions import DecisionAction
from backend.rl.rl_action_space import ActionSpace, EncodedAction
from backend.rl.rl_multi_objective import MultiObjectiveOptimizer, MultiObjectiveResult
from backend.rl.rl_policy_manager import PolicyArtifact
from backend.rl.rl_registry import RLAlgorithm
from backend.rl.rl_state_encoder import EncodedState
from backend.config.logger import get_logger

logger = get_logger(__name__)


class PolicyOutput(BaseModel):
    """Output from a policy forward pass."""

    selected_index: int
    action_id: str
    logits: list[float] = Field(default_factory=list)
    probabilities: list[float] = Field(default_factory=list)
    value_estimate: float = 0.0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    algorithm: str = ""


class RLPolicy(ABC):
    """Abstract policy interface for all RL algorithms."""

    def __init__(self, *, artifact: PolicyArtifact) -> None:
        self._artifact = artifact
        self._algorithm = artifact.metadata.algorithm

    @property
    def algorithm(self) -> RLAlgorithm:
        return self._algorithm

    @property
    def policy_id(self) -> str:
        return self._artifact.metadata.policy_id

    @property
    def version(self) -> str:
        return self._artifact.metadata.version

    @abstractmethod
    def select(
        self,
        state: EncodedState,
        action_space: ActionSpace,
        scores: list[MultiObjectiveResult],
    ) -> PolicyOutput:
        """Select an action index given state and pre-computed scores."""


def _softmax(values: list[float], temperature: float = 1.0) -> list[float]:
    if not values:
        return []
    scaled = [v / max(temperature, 1e-6) for v in values]
    max_v = max(scaled)
    exps = [math.exp(v - max_v) for v in scaled]
    total = sum(exps)
    return [e / total for e in exps] if total > 0 else [1.0 / len(values)] * len(values)


class PPOPolicy(RLPolicy):
    """Proximal Policy Optimization inference policy."""

    def select(
        self,
        state: EncodedState,
        action_space: ActionSpace,
        scores: list[MultiObjectiveResult],
    ) -> PolicyOutput:
        weights = self._artifact.weights
        temperature = float(weights.get("temperature", 0.8))
        entropy_coef = float(weights.get("entropy_coef", 0.01))

        raw_scores = [s.total_score for s in scores]
        conf = float(state.features.get("confidence", 0.5))
        logits = [s + entropy_coef * conf for s in raw_scores]
        if not logits:
            logits = [0.0]

        probs = _softmax(logits, temperature)
        best_idx = max(range(len(probs)), key=lambda i: probs[i])
        value = sum(p * s for p, s in zip(probs, raw_scores, strict=False))

        return PolicyOutput(
            selected_index=best_idx,
            action_id=scores[best_idx].action_id if scores else "",
            logits=logits,
            probabilities=probs,
            value_estimate=round(value, 6),
            confidence=round(probs[best_idx], 4),
            algorithm=RLAlgorithm.PPO.value,
        )


class SACPolicy(RLPolicy):
    """Soft Actor-Critic inference policy with entropy regularization."""

    def select(
        self,
        state: EncodedState,
        action_space: ActionSpace,
        scores: list[MultiObjectiveResult],
    ) -> PolicyOutput:
        alpha = float(self._artifact.weights.get("temperature", 1.0))
        raw = [s.total_score for s in scores]
        logits = [s / alpha for s in raw] if raw else [0.0]
        probs = _softmax(logits, alpha)
        best_idx = max(range(len(probs)), key=lambda i: probs[i])

        return PolicyOutput(
            selected_index=best_idx,
            action_id=scores[best_idx].action_id if scores else "",
            logits=logits,
            probabilities=probs,
            value_estimate=round(sum(raw) / max(len(raw), 1), 6),
            confidence=round(probs[best_idx], 4),
            algorithm=RLAlgorithm.SAC.value,
        )


class DQNPolicy(RLPolicy):
    """Deep Q-Network inference policy with epsilon-greedy selection."""

    def select(
        self,
        state: EncodedState,
        action_space: ActionSpace,
        scores: list[MultiObjectiveResult],
    ) -> PolicyOutput:
        epsilon = float(self._artifact.metadata.hyperparameters.get("epsilon", 0.1))
        exploration = float(self._artifact.weights.get("exploration_bonus", 0.05))

        q_values = [s.total_score + exploration for s in scores]
        if not q_values:
            q_values = [0.0]

        best_idx = max(range(len(q_values)), key=lambda i: q_values[i])
        greedy_prob = 1.0 - epsilon
        probs = [epsilon / max(len(q_values), 1)] * len(q_values)
        probs[best_idx] += greedy_prob

        return PolicyOutput(
            selected_index=best_idx,
            action_id=scores[best_idx].action_id if scores else "",
            logits=q_values,
            probabilities=probs,
            value_estimate=round(q_values[best_idx], 6),
            confidence=round(probs[best_idx], 4),
            algorithm=RLAlgorithm.DQN.value,
        )


class A2CPolicy(RLPolicy):
    """Advantage Actor-Critic inference policy."""

    def select(
        self,
        state: EncodedState,
        action_space: ActionSpace,
        scores: list[MultiObjectiveResult],
    ) -> PolicyOutput:
        value_coef = float(self._artifact.metadata.hyperparameters.get("value_coef", 0.5))
        baseline = float(self._artifact.weights.get("value_baseline", 0.0))

        advantages = [s.total_score - baseline for s in scores]
        probs = _softmax(advantages)
        best_idx = max(range(len(probs)), key=lambda i: probs[i])
        value = baseline + value_coef * advantages[best_idx]

        return PolicyOutput(
            selected_index=best_idx,
            action_id=scores[best_idx].action_id if scores else "",
            logits=advantages,
            probabilities=probs,
            value_estimate=round(value, 6),
            confidence=round(probs[best_idx], 4),
            algorithm=RLAlgorithm.A2C.value,
        )


class MAPPOPolicy(RLPolicy):
    """Multi-Agent PPO inference policy with cooperation factor."""

    def select(
        self,
        state: EncodedState,
        action_space: ActionSpace,
        scores: list[MultiObjectiveResult],
    ) -> PolicyOutput:
        coop = float(self._artifact.weights.get("cooperation_factor", 1.0))
        need_flags = state.features.get("need_flags", [0.0, 0.0, 0.0, 0.0])
        multi_agent_pressure = float(need_flags[3]) if isinstance(need_flags, list) else 0.0

        adjusted = [s.total_score * (1.0 + coop * multi_agent_pressure * 0.1) for s in scores]
        probs = _softmax(adjusted)
        best_idx = max(range(len(probs)), key=lambda i: probs[i])

        return PolicyOutput(
            selected_index=best_idx,
            action_id=scores[best_idx].action_id if scores else "",
            logits=adjusted,
            probabilities=probs,
            value_estimate=round(adjusted[best_idx], 6),
            confidence=round(probs[best_idx], 4),
            algorithm=RLAlgorithm.MAPPO.value,
        )


POLICY_FACTORY: dict[RLAlgorithm, type[RLPolicy]] = {
    RLAlgorithm.PPO: PPOPolicy,
    RLAlgorithm.SAC: SACPolicy,
    RLAlgorithm.DQN: DQNPolicy,
    RLAlgorithm.A2C: A2CPolicy,
    RLAlgorithm.MAPPO: MAPPOPolicy,
}


def create_policy(artifact: PolicyArtifact) -> RLPolicy:
    """Instantiate the correct policy class for an artifact."""
    policy_cls = POLICY_FACTORY.get(artifact.metadata.algorithm, PPOPolicy)
    return policy_cls(artifact=artifact)


class RLEngine:
    """
    Core RL engine orchestrating state encoding, policy selection,
    reward estimation, and constraint validation.
    """

    def __init__(
        self,
        *,
        policy_manager: Any | None = None,
        multi_objective: MultiObjectiveOptimizer | None = None,
    ) -> None:
        from backend.rl.rl_policy_manager import PolicyManager

        self._policy_manager = policy_manager or PolicyManager()
        self._multi_objective = multi_objective or MultiObjectiveOptimizer()

    @property
    def policy_manager(self) -> Any:
        return self._policy_manager

    def get_policy(self, algorithm: RLAlgorithm | None = None) -> RLPolicy:
        if algorithm:
            policies = self._policy_manager.list_versions(algorithm=algorithm)
            if policies:
                target = next(
                    (p for p in policies if p.status.value == "active"),
                    policies[0],
                )
                artifact = self._policy_manager.get_artifact(target.policy_id)
                if artifact:
                    return create_policy(artifact)
        artifact = self._policy_manager.get_active_artifact()
        return create_policy(artifact)

    def run_policy(
        self,
        state: EncodedState,
        action_space: ActionSpace,
        scores: list[MultiObjectiveResult],
        *,
        algorithm: RLAlgorithm | None = None,
    ) -> PolicyOutput:
        policy = self.get_policy(algorithm)
        return policy.select(state, action_space, scores)
