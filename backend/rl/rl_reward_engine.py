"""Configurable reward functions for RL optimization."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from backend.decision.decision_actions import DecisionAction
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_types import RISK_LEVEL_ORDER, RiskLevel
from backend.rl.rl_state_encoder import EncodedState


class RewardComponent(StrEnum):
    """Configurable reward dimensions."""

    FLOOD_REDUCTION = "flood_reduction"
    WATER_CONSERVATION = "water_conservation"
    CROP_YIELD = "crop_yield"
    POPULATION_SAFETY = "population_safety"
    ECONOMIC_IMPACT = "economic_impact"
    INFRASTRUCTURE_PROTECTION = "infrastructure_protection"
    ENVIRONMENTAL_SUSTAINABILITY = "environmental_sustainability"
    POLICY_COMPLIANCE = "policy_compliance"


DEFAULT_REWARD_WEIGHTS: dict[RewardComponent, float] = {
    RewardComponent.FLOOD_REDUCTION: 0.20,
    RewardComponent.WATER_CONSERVATION: 0.15,
    RewardComponent.CROP_YIELD: 0.10,
    RewardComponent.POPULATION_SAFETY: 0.20,
    RewardComponent.ECONOMIC_IMPACT: 0.10,
    RewardComponent.INFRASTRUCTURE_PROTECTION: 0.10,
    RewardComponent.ENVIRONMENTAL_SUSTAINABILITY: 0.10,
    RewardComponent.POLICY_COMPLIANCE: 0.05,
}


class RewardConfig(BaseModel):
    """Configuration for reward computation."""

    weights: dict[str, float] = Field(default_factory=lambda: {
        c.value: w for c, w in DEFAULT_REWARD_WEIGHTS.items()
    })
    cost_penalty_factor: float = Field(default=0.01, ge=0.0)
    risk_penalty_factor: float = Field(default=0.5, ge=0.0)
    normalize: bool = True

    def get_weight(self, component: RewardComponent) -> float:
        return self.weights.get(component.value, 0.0)


class RewardBreakdown(BaseModel):
    """Detailed reward decomposition for an action."""

    total: float = 0.0
    components: dict[str, float] = Field(default_factory=dict)
    penalties: dict[str, float] = Field(default_factory=dict)
    action_id: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class RewardEngine:
    """
    Configurable multi-component reward engine.

    Supports flood reduction, water conservation, crop yield, population
    safety, economic impact, infrastructure protection, environmental
    sustainability, and policy compliance objectives.
    """

    def __init__(self, *, config: RewardConfig | None = None) -> None:
        self._config = config or RewardConfig()

    @property
    def config(self) -> RewardConfig:
        return self._config

    def compute(
        self,
        action: DecisionAction,
        request: DecisionRequest,
        state: EncodedState,
    ) -> RewardBreakdown:
        components: dict[str, float] = {}
        penalties: dict[str, float] = {}

        components[RewardComponent.FLOOD_REDUCTION.value] = self._flood_reduction(action, request, state)
        components[RewardComponent.WATER_CONSERVATION.value] = self._water_conservation(action, request)
        components[RewardComponent.CROP_YIELD.value] = self._crop_yield(action, request)
        components[RewardComponent.POPULATION_SAFETY.value] = self._population_safety(action, request)
        components[RewardComponent.ECONOMIC_IMPACT.value] = self._economic_impact(action)
        components[RewardComponent.INFRASTRUCTURE_PROTECTION.value] = self._infrastructure(action)
        components[RewardComponent.ENVIRONMENTAL_SUSTAINABILITY.value] = self._environmental(action)
        components[RewardComponent.POLICY_COMPLIANCE.value] = self._policy_compliance(action, request)

        weighted = sum(
            components[c.value] * self._config.get_weight(c)
            for c in RewardComponent
        )

        penalties["cost"] = action.cost * self._config.cost_penalty_factor
        penalties["risk"] = action.risk_score * self._config.risk_penalty_factor

        total = weighted - sum(penalties.values())
        if self._config.normalize:
            total = max(min(total, 100.0), -100.0) / 100.0

        confidence = min(
            request.confidence,
            1.0 - action.risk_score * 0.3,
        )

        return RewardBreakdown(
            total=round(total, 6),
            components={k: round(v, 4) for k, v in components.items()},
            penalties={k: round(v, 4) for k, v in penalties.items()},
            action_id=action.action_id,
            confidence=round(max(confidence, 0.0), 4),
        )

    def _flood_reduction(
        self,
        action: DecisionAction,
        request: DecisionRequest,
        state: EncodedState,
    ) -> float:
        risk_factor = request.risk.score
        benefit = action.expected_benefit / max(action.cost + 1.0, 1.0)
        flood_keywords = ("flood", "evacuat", "release", "warning", "inundat")
        keyword_boost = 1.2 if any(k in action.description.lower() for k in flood_keywords) else 1.0
        return min(benefit * risk_factor * keyword_boost * 10.0, 10.0)

    def _water_conservation(self, action: DecisionAction, request: DecisionRequest) -> float:
        conserve_keywords = ("conserv", "hold", "restrict", "ration", "release")
        if any(k in action.description.lower() for k in conserve_keywords):
            return 8.0 * (1.0 - action.cost / 100.0)
        return action.expected_benefit * 0.05

    def _crop_yield(self, action: DecisionAction, request: DecisionRequest) -> float:
        agri_keywords = ("irrigat", "crop", "farm", "agricult", "harvest")
        if any(k in action.description.lower() for k in agri_keywords):
            return action.expected_benefit * 0.15
        return 0.0

    def _population_safety(self, action: DecisionAction, request: DecisionRequest) -> float:
        pop_factor = min(action.affected_population / 100_000.0, 5.0)
        risk_reduction = 1.0 - action.risk_score
        safety_keywords = ("evacuat", "warn", "shelter", "protect", "alert")
        boost = 1.5 if any(k in action.description.lower() for k in safety_keywords) else 1.0
        return min(pop_factor * risk_reduction * boost * 3.0, 10.0)

    def _economic_impact(self, action: DecisionAction) -> float:
        return action.net_value / max(action.expected_benefit + 1.0, 1.0) * 10.0

    def _infrastructure(self, action: DecisionAction) -> float:
        infra_keywords = ("dam", "reservoir", "grid", "infrastructure", "spillway")
        if any(k in action.description.lower() for k in infra_keywords):
            return 7.0 * (1.0 - action.risk_score)
        return action.expected_benefit * 0.08

    def _environmental(self, action: DecisionAction) -> float:
        if action.reversible:
            return 5.0 * (1.0 - action.risk_score)
        return 2.0 * (1.0 - action.risk_score)

    def _policy_compliance(self, action: DecisionAction, request: DecisionRequest) -> float:
        score = 5.0
        if request.constraints.policy and request.constraints.policy.approval_required:
            if action.cost > 50.0:
                score -= 2.0
        if request.constraints.safety:
            if action.risk_score > request.constraints.safety.max_risk_score:
                score -= 3.0
        return max(score, 0.0)
