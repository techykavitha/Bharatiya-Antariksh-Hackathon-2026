"""RL environment abstraction for single-step decision optimization."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.decision.decision_actions import DecisionAction
from backend.decision.decision_request import DecisionRequest
from backend.rl.rl_action_space import ActionSpace
from backend.rl.rl_state_encoder import EncodedState, StateEncoder


class EnvironmentStepResult(BaseModel):
    """Result of a single environment step."""

    observation: EncodedState
    reward: float = 0.0
    done: bool = True
    info: dict[str, float] = Field(default_factory=dict)


class RLEnvironment:
    """
    Stateless single-step environment for decision optimization.

    Each ``DecisionRequest`` defines an episode with one decision step.
    The environment encodes the request as observation and evaluates
    actions through the reward engine at step time.
    """

    def __init__(self, *, state_encoder: StateEncoder | None = None) -> None:
        self._encoder = state_encoder or StateEncoder()
        self._request: DecisionRequest | None = None
        self._action_space: ActionSpace | None = None
        self._observation: EncodedState | None = None
        self._step_count: int = 0

    @property
    def request(self) -> DecisionRequest | None:
        return self._request

    @property
    def action_space(self) -> ActionSpace | None:
        return self._action_space

    @property
    def observation(self) -> EncodedState | None:
        return self._observation

    @property
    def is_done(self) -> bool:
        return self._step_count > 0

    async def reset(
        self,
        request: DecisionRequest,
        *,
        memory_context: dict | None = None,
    ) -> EncodedState:
        self._request = request
        self._action_space = ActionSpace.from_request(request)
        self._observation = await self._encoder.encode(request, memory_context=memory_context)
        self._step_count = 0
        return self._observation

    def step(self, action: DecisionAction, reward: float) -> EnvironmentStepResult:
        if self._request is None or self._observation is None:
            raise RuntimeError("Environment not reset — call reset() first")
        self._step_count += 1
        return EnvironmentStepResult(
            observation=self._observation,
            reward=reward,
            done=True,
            info={"step": float(self._step_count)},
        )

    def get_action_by_index(self, index: int) -> DecisionAction:
        if self._action_space is None:
            raise RuntimeError("Environment not reset")
        return self._action_space.decode_index(index)
