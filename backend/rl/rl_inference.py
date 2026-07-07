"""RL inference API for action optimization."""

from __future__ import annotations

import time
from typing import Any

from backend.decision.decision_actions import ActionRanking, DecisionAction, RejectedAction
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.decision.decision_types import DecisionStatus
from backend.rl.rl_action_space import ActionSpace
from backend.rl.rl_constraints import RLConstraintEngine
from backend.rl.rl_engine import RLEngine, PolicyOutput, create_policy
from backend.rl.rl_environment import RLEnvironment
from backend.rl.rl_metrics import RLMetricsCollector
from backend.rl.rl_multi_objective import MultiObjectiveOptimizer, MultiObjectiveResult
from backend.rl.rl_policy_manager import PolicyManager
from backend.rl.rl_registry import RLAlgorithm
from backend.rl.rl_reward_engine import RewardBreakdown, RewardEngine
from backend.rl.rl_state_encoder import EncodedState, StateEncoder
from backend.config.logger import get_logger

logger = get_logger(__name__)


class RLInference:
    """
    Inference layer exposing optimize, rank_actions, evaluate, and
    simulate_reward for the RL optimization service.
    """

    def __init__(
        self,
        *,
        engine: RLEngine | None = None,
        state_encoder: StateEncoder | None = None,
        reward_engine: RewardEngine | None = None,
        constraint_engine: RLConstraintEngine | None = None,
        multi_objective: MultiObjectiveOptimizer | None = None,
        environment: RLEnvironment | None = None,
        policy_manager: PolicyManager | None = None,
        algorithm: RLAlgorithm | None = None,
    ) -> None:
        self._policy_manager = policy_manager or PolicyManager()
        self._engine = engine or RLEngine(policy_manager=self._policy_manager)
        self._encoder = state_encoder or StateEncoder()
        self._reward_engine = reward_engine or RewardEngine()
        self._constraints = constraint_engine or RLConstraintEngine()
        self._multi_objective = multi_objective or MultiObjectiveOptimizer(
            reward_engine=self._reward_engine,
        )
        self._environment = environment or RLEnvironment(state_encoder=self._encoder)
        self._default_algorithm = algorithm

    @property
    def policy_manager(self) -> PolicyManager:
        return self._policy_manager

    async def optimize(
        self,
        request: DecisionRequest,
        *,
        memory_context: dict[str, Any] | None = None,
        algorithm: RLAlgorithm | None = None,
        metrics: RLMetricsCollector | None = None,
    ) -> DecisionResponse:
        """Select the optimal action and return a ``DecisionResponse``."""
        start = time.perf_counter()
        algo = algorithm or self._default_algorithm

        state = await self._environment.reset(request, memory_context=memory_context)
        action_space = self._environment.action_space
        if action_space is None:
            raise RuntimeError("Failed to initialize action space")

        if metrics:
            metrics.set_state_dimension(state.dimension)

        feasible, validation_results = self._constraints.filter_feasible(request)
        violation_count = sum(len(r.blocking_violations) for r in validation_results)

        if metrics:
            metrics.record_violations(violation_count)
            metrics.record_actions(
                len(request.possible_actions),
                len(feasible),
                len(request.possible_actions) - len(feasible),
            )

        if not feasible:
            return self._failed_response(
                request,
                reason="No feasible actions after constraint validation",
                processing_time_ms=(time.perf_counter() - start) * 1000,
            )

        scores = self._score_feasible(feasible, request, state)
        policy_output = self._engine.run_policy(
            state, action_space, scores, algorithm=algo,
        )

        chosen = action_space.decode_index(policy_output.selected_index)
        reward_breakdown = self._multi_objective.evaluate_action(chosen, request, state).reward_breakdown
        reward = reward_breakdown.total if reward_breakdown else 0.0

        ranking = self._build_ranking(scores, policy_output)
        rejected = self._build_rejected(request, feasible, validation_results, scores)

        policy = self._engine.get_policy(algo)
        elapsed = (time.perf_counter() - start) * 1000

        if metrics:
            metrics.set_reward(reward)
            metrics.set_confidence(policy_output.confidence)
            metrics.set_policy_version(policy.version)

        response = DecisionResponse(
            decision_id=request.decision_id,
            status=DecisionStatus.COMPLETED,
            chosen_action=chosen,
            ranking=ranking,
            reward=reward,
            confidence=policy_output.confidence,
            reason=(
                f"Optimized via {policy.algorithm.value} policy v{policy.version} "
                f"(reward={reward:.4f})"
            ),
            rejected_actions=rejected,
            engine_id=f"rl_{policy.algorithm.value}",
            processing_time_ms=round(elapsed, 2),
            metadata={
                "policy_id": policy.policy_id,
                "algorithm": policy.algorithm.value,
                "value_estimate": policy_output.value_estimate,
                "feasible_actions": len(feasible),
                "state_dimension": state.dimension,
            },
        )

        self._environment.step(chosen, reward)
        logger.info(
            "rl_optimize_complete",
            decision_id=request.decision_id,
            algorithm=policy.algorithm.value,
            reward=reward,
            action_id=chosen.action_id,
        )
        return response

    async def rank_actions(
        self,
        request: DecisionRequest,
        *,
        memory_context: dict[str, Any] | None = None,
    ) -> list[ActionRanking]:
        """Rank all feasible actions by expected reward."""
        state = await self._encoder.encode(request, memory_context=memory_context)
        feasible, _ = self._constraints.filter_feasible(request)
        scores = self._score_feasible(feasible, request, state)
        scores.sort(key=lambda s: s.total_score, reverse=True)

        rankings: list[ActionRanking] = []
        for rank, result in enumerate(scores, start=1):
            rb = result.reward_breakdown
            rankings.append(ActionRanking(
                action_id=result.action_id,
                rank=rank,
                score=result.total_score,
                expected_reward=rb.total if rb else 0.0,
                confidence=rb.confidence if rb else 0.5,
                rationale=f"Pareto rank {result.pareto_rank}",
            ))
        return rankings

    async def evaluate(
        self,
        request: DecisionRequest,
        action: DecisionAction,
        *,
        memory_context: dict[str, Any] | None = None,
    ) -> MultiObjectiveResult:
        """Evaluate a single action against the request."""
        state = await self._encoder.encode(request, memory_context=memory_context)
        return self._multi_objective.evaluate_action(action, request, state)

    async def simulate_reward(
        self,
        request: DecisionRequest,
        action: DecisionAction,
        *,
        memory_context: dict[str, Any] | None = None,
    ) -> RewardBreakdown:
        """Simulate reward for an action without selecting."""
        state = await self._encoder.encode(request, memory_context=memory_context)
        return self._reward_engine.compute(action, request, state)

    def _score_feasible(
        self,
        feasible: list[DecisionAction],
        request: DecisionRequest,
        state: EncodedState,
    ) -> list[MultiObjectiveResult]:
        modified = request.model_copy(update={"possible_actions": feasible})
        return self._multi_objective.evaluate_all(modified, state)

    def _build_ranking(
        self,
        scores: list[MultiObjectiveResult],
        policy_output: PolicyOutput,
    ) -> list[ActionRanking]:
        sorted_scores = sorted(scores, key=lambda s: s.total_score, reverse=True)
        rankings: list[ActionRanking] = []
        for rank, result in enumerate(sorted_scores, start=1):
            rb = result.reward_breakdown
            prob = 0.0
            if policy_output.probabilities and result.action_id in [
                s.action_id for s in sorted_scores
            ]:
                idx = next(
                    (i for i, s in enumerate(sorted_scores) if s.action_id == result.action_id),
                    0,
                )
                if idx < len(policy_output.probabilities):
                    prob = policy_output.probabilities[idx]

            rankings.append(ActionRanking(
                action_id=result.action_id,
                rank=rank,
                score=result.total_score,
                expected_reward=rb.total if rb else 0.0,
                confidence=max(prob, rb.confidence if rb else 0.0),
            ))
        return rankings

    def _build_rejected(
        self,
        request: DecisionRequest,
        feasible: list[DecisionAction],
        validation_results: list,
        scores: list[MultiObjectiveResult],
    ) -> list[RejectedAction]:
        feasible_ids = {a.action_id for a in feasible}
        rejected: list[RejectedAction] = []

        for result in validation_results:
            if not result.feasible:
                violation = result.blocking_violations[0] if result.blocking_violations else None
                rejected.append(RejectedAction(
                    action_id=result.action_id,
                    reason=violation.message if violation else "Constraint violation",
                    constraint_violated=violation.category.value if violation else None,
                ))

        score_map = {s.action_id: s.total_score for s in scores}
        for action in request.possible_actions:
            if action.action_id not in feasible_ids:
                continue
            if action.action_id not in {s.action_id for s in scores[:1]}:
                rejected.append(RejectedAction(
                    action_id=action.action_id,
                    reason="Lower ranked alternative",
                    score=score_map.get(action.action_id),
                ))

        return rejected

    def _failed_response(
        self,
        request: DecisionRequest,
        *,
        reason: str,
        processing_time_ms: float,
    ) -> DecisionResponse:
        return DecisionResponse(
            decision_id=request.decision_id,
            status=DecisionStatus.FAILED,
            confidence=0.0,
            reason=reason,
            engine_id="rl_engine",
            processing_time_ms=round(processing_time_ms, 2),
        )
