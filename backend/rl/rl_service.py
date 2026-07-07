"""RL Optimization Service — agent-agnostic decision optimization."""

from __future__ import annotations

from typing import Any

from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.memory.memory_types import MemoryDomain, MemorySearchRequest
from backend.decision.decision_actions import ActionRanking
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.decision.decision_validator import DecisionValidator
from backend.rl.rl_engine import RLEngine
from backend.rl.rl_inference import RLInference
from backend.rl.rl_metrics import RLExecutionMetrics, RLMetricsCollector
from backend.rl.rl_multi_objective import MultiObjectiveResult
from backend.rl.rl_policy_manager import PolicyManager
from backend.rl.rl_registry import DEFAULT_ALGORITHM, RLAlgorithm
from backend.rl.rl_reward_engine import RewardBreakdown
from backend.rl.rl_training_manager import InMemoryTrainingManager, RLTrainingManager, TrainingEpisode
from backend.config.logger import get_logger
from backend.utils.errors import HyperionError

logger = get_logger(__name__)


class RLOptimizationError(HyperionError):
    """Raised when RL optimization fails."""


class RLOptimizationService:
    """
    Production-grade RL optimization service.

    Accepts ONLY ``DecisionRequest`` objects and returns ONLY
    ``DecisionResponse`` objects. Completely agent-agnostic — never
    depends on Flood, Water, or any specialized agent module.

    Pipeline:
    DecisionRequest → State Encoder → Observation Space → Policy →
    Action Selection → Reward Estimation → Constraint Validation →
    DecisionResponse
    """

    def __init__(
        self,
        *,
        memory: MemoryManager | None = None,
        inference: RLInference | None = None,
        policy_manager: PolicyManager | None = None,
        training_manager: RLTrainingManager | None = None,
        algorithm: RLAlgorithm = DEFAULT_ALGORITHM,
        record_episodes: bool = True,
    ) -> None:
        self._memory = memory
        self._policy_manager = policy_manager or PolicyManager()
        self._inference = inference or RLInference(
            policy_manager=self._policy_manager,
            algorithm=algorithm,
        )
        self._training = training_manager or InMemoryTrainingManager(memory=memory)
        self._validator = DecisionValidator()
        self._algorithm = algorithm
        self._record_episodes = record_episodes
        self._last_metrics: RLExecutionMetrics | None = None

    @property
    def last_metrics(self) -> RLExecutionMetrics | None:
        return self._last_metrics

    @property
    def policy_manager(self) -> PolicyManager:
        return self._policy_manager

    @property
    def inference(self) -> RLInference:
        return self._inference

    @classmethod
    async def create(
        cls,
        memory: MemoryManager | None = None,
        *,
        algorithm: RLAlgorithm = DEFAULT_ALGORITHM,
    ) -> RLOptimizationService:
        return cls(memory=memory, algorithm=algorithm)

    async def optimize(
        self,
        request: DecisionRequest,
        *,
        algorithm: RLAlgorithm | None = None,
        validate: bool = True,
    ) -> DecisionResponse:
        """
        Optimize a decision request and return the best action.

        This is the primary entry point for all specialized agents.
        """
        if validate:
            validation = self._validator.validate_request(request)
            if not validation.valid:
                logger.warning(
                    "rl_request_validation_issues",
                    decision_id=request.decision_id,
                    issues=len(validation.issues),
                )

        metrics = RLMetricsCollector(
            decision_id=request.decision_id,
            algorithm=algorithm or self._algorithm,
        )

        memory_context = await self._retrieve_memory_context(request)

        try:
            response = await self._inference.optimize(
                request,
                memory_context=memory_context,
                algorithm=algorithm or self._algorithm,
                metrics=metrics,
            )
            self._last_metrics = metrics.finalize()

            if self._record_episodes and response.is_successful():
                await self._training.record_episode(request, response)

            response.metadata = {
                **response.metadata,
                "rl_metrics": self._last_metrics.model_dump(),
            }
            return response

        except Exception as exc:
            metrics.finalize()
            logger.error("rl_optimize_failed", decision_id=request.decision_id, error=str(exc))
            raise RLOptimizationError(
                f"RL optimization failed: {exc}",
                details={"decision_id": request.decision_id},
            ) from exc

    async def rank_actions(self, request: DecisionRequest) -> list[ActionRanking]:
        memory_context = await self._retrieve_memory_context(request)
        return await self._inference.rank_actions(request, memory_context=memory_context)

    async def evaluate(
        self,
        request: DecisionRequest,
        action_id: str,
    ) -> MultiObjectiveResult:
        action = next(
            (a for a in request.possible_actions if a.action_id == action_id),
            None,
        )
        if action is None:
            raise RLOptimizationError(
                f"Action not found: {action_id}",
                details={"decision_id": request.decision_id},
            )
        memory_context = await self._retrieve_memory_context(request)
        return await self._inference.evaluate(request, action, memory_context=memory_context)

    async def simulate_reward(
        self,
        request: DecisionRequest,
        action_id: str,
    ) -> RewardBreakdown:
        action = next(
            (a for a in request.possible_actions if a.action_id == action_id),
            None,
        )
        if action is None:
            raise RLOptimizationError(
                f"Action not found: {action_id}",
                details={"decision_id": request.decision_id},
            )
        memory_context = await self._retrieve_memory_context(request)
        return await self._inference.simulate_reward(
            request, action, memory_context=memory_context,
        )

    async def switch_policy(self, policy_id: str) -> str:
        meta = self._policy_manager.switch(policy_id)
        return meta.policy_id

    async def list_policies(self) -> list[dict[str, Any]]:
        return [p.model_dump(mode="json") for p in self._policy_manager.list_versions()]

    async def get_training_episodes(self, *, limit: int = 50) -> list[TrainingEpisode]:
        return await self._training.list_episodes(limit=limit)

    async def _retrieve_memory_context(self, request: DecisionRequest) -> dict[str, Any]:
        if self._memory is None:
            return {}

        context: dict[str, Any] = {"historical_rewards": []}
        try:
            results = await self._memory.search(
                MemorySearchRequest(
                    query=f"rl_episode decision {request.decision_type.value}",
                    domains=[MemoryDomain.WORKING],
                    limit=10,
                ),
            )
            for ranked in results:
                value = ranked.entry.value
                if isinstance(value, dict) and "reward" in value:
                    context["historical_rewards"].append(float(value["reward"]))
        except Exception as exc:
            logger.debug("rl_memory_context_skipped", error=str(exc))

        return context
