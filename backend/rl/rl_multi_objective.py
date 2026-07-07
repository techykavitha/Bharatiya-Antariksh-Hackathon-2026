"""Multi-objective optimization for RL action selection."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.decision.decision_actions import DecisionAction
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_types import Objective
from backend.rl.rl_reward_engine import RewardBreakdown, RewardEngine
from backend.rl.rl_state_encoder import EncodedState


class ObjectiveScore(BaseModel):
    """Score for a single objective against an action."""

    objective_id: str
    description: str
    raw_score: float = 0.0
    weighted_score: float = 0.0
    weight: float = Field(default=1.0, ge=0.0)


class MultiObjectiveResult(BaseModel):
    """Aggregated multi-objective evaluation."""

    action_id: str
    total_score: float = 0.0
    objective_scores: list[ObjectiveScore] = Field(default_factory=list)
    reward_breakdown: RewardBreakdown | None = None
    pareto_rank: int = Field(default=1, ge=1)


class MultiObjectiveOptimizer:
    """Weighted multi-objective optimization across decision objectives."""

    def __init__(self, *, reward_engine: RewardEngine | None = None) -> None:
        self._reward_engine = reward_engine or RewardEngine()

    def evaluate_action(
        self,
        action: DecisionAction,
        request: DecisionRequest,
        state: EncodedState,
    ) -> MultiObjectiveResult:
        reward = self._reward_engine.compute(action, request, state)
        obj_scores = self._score_objectives(action, request)
        objective_total = sum(s.weighted_score for s in obj_scores)
        combined = 0.6 * reward.total + 0.4 * objective_total

        return MultiObjectiveResult(
            action_id=action.action_id,
            total_score=round(combined, 6),
            objective_scores=obj_scores,
            reward_breakdown=reward,
        )

    def evaluate_all(
        self,
        request: DecisionRequest,
        state: EncodedState,
    ) -> list[MultiObjectiveResult]:
        results = [
            self.evaluate_action(action, request, state)
            for action in request.possible_actions
        ]
        return self._assign_pareto_ranks(results)

    def best_action(
        self,
        request: DecisionRequest,
        state: EncodedState,
    ) -> MultiObjectiveResult | None:
        results = self.evaluate_all(request, state)
        if not results:
            return None
        return max(results, key=lambda r: r.total_score)

    def _score_objectives(
        self,
        action: DecisionAction,
        request: DecisionRequest,
    ) -> list[ObjectiveScore]:
        scores: list[ObjectiveScore] = []
        for obj in request.objectives:
            raw = self._objective_raw_score(obj, action)
            direction = 1.0 if obj.maximize else -1.0
            weighted = raw * obj.weight * direction
            scores.append(ObjectiveScore(
                objective_id=obj.objective_id,
                description=obj.description,
                raw_score=round(raw, 4),
                weighted_score=round(weighted, 4),
                weight=obj.weight,
            ))
        return scores

    def _objective_raw_score(self, objective: Objective, action: DecisionAction) -> float:
        desc = objective.description.lower()
        if "flood" in desc or "risk" in desc:
            return action.expected_benefit * (1.0 - action.risk_score)
        if "water" in desc or "supply" in desc:
            return action.net_value
        if "safety" in desc or "population" in desc:
            return (1.0 - action.risk_score) * 10.0
        if "cost" in desc or "economic" in desc:
            return max(10.0 - action.cost, 0.0)
        return action.expected_benefit / max(action.cost + 1.0, 1.0)

    def _assign_pareto_ranks(
        self,
        results: list[MultiObjectiveResult],
    ) -> list[MultiObjectiveResult]:
        if not results:
            return results
        sorted_results = sorted(results, key=lambda r: r.total_score, reverse=True)
        for rank, result in enumerate(sorted_results, start=1):
            result.pareto_rank = rank
        return sorted_results
