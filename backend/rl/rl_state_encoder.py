"""State encoder converting DecisionRequest into RL observations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_types import DecisionType, RISK_LEVEL_ORDER, RiskLevel
from backend.rl.rl_observation_space import ObservationSpace, build_default_observation_space
from backend.utils.enums import ClimateVariable

DECISION_TYPE_INDEX: dict[DecisionType, int] = {dt: i for i, dt in enumerate(DecisionType)}


class EncodedState(BaseModel):
    """RL observation produced from a decision request."""

    vector: list[float] = Field(default_factory=list)
    features: dict[str, Any] = Field(default_factory=dict)
    observation_space: ObservationSpace = Field(default_factory=build_default_observation_space)
    decision_id: str = ""
    scenario_id: str = ""
    dimension: int = 0
    memory_context_used: bool = False

    def get_feature_vector(self, name: str) -> list[float]:
        value = self.features.get(name)
        if isinstance(value, list):
            return value
        if isinstance(value, (int, float)):
            return [float(value)]
        return []


class StateEncoder:
    """
    Converts agent-agnostic ``DecisionRequest`` objects into RL observations.

    Encodes climate variables, forecast, constraints, risk, objectives,
    possible actions, confidence, and simulation references.
    """

    def __init__(self, *, observation_space: ObservationSpace | None = None) -> None:
        self._space = observation_space or build_default_observation_space()

    @property
    def observation_space(self) -> ObservationSpace:
        return self._space

    async def encode(
        self,
        request: DecisionRequest,
        *,
        memory_context: dict[str, Any] | None = None,
    ) -> EncodedState:
        payload = request.to_rl_payload()
        features: dict[str, Any] = {}

        features["decision_type"] = self._one_hot_decision_type(request.decision_type)
        features["priority"] = float(int(request.priority))
        features["confidence"] = request.confidence
        features["risk_score"] = request.risk.score
        features["risk_level"] = self._one_hot_risk(request.risk.level)
        features["objective_weights"] = self._encode_objectives(request)
        features["constraint_budget"] = (
            request.constraints.budget.max_cost if request.constraints.budget else 0.0
        )
        features["constraint_safety"] = (
            request.constraints.safety.max_risk_score if request.constraints.safety else 1.0
        )
        features["climate_variables"] = self._encode_climate(request)
        features["forecast_present"] = 1.0 if request.forecast_reference else 0.0
        features["simulation_present"] = 1.0 if request.simulation_reference else 0.0
        features["action_count"] = float(len(request.possible_actions))
        features["need_flags"] = [
            1.0 if request.need_simulation else 0.0,
            1.0 if request.need_rl else 0.0,
            1.0 if request.need_human else 0.0,
            float(len(request.need_other_agents)),
        ]
        features["historical_reward"] = self._extract_historical_reward(memory_context)

        vector = self._flatten(features)
        return EncodedState(
            vector=vector,
            features=features,
            observation_space=self._space,
            decision_id=request.decision_id,
            scenario_id=request.scenario,
            dimension=len(vector),
            memory_context_used=memory_context is not None,
        )

    def _one_hot_decision_type(self, decision_type: DecisionType) -> list[float]:
        vec = [0.0] * len(DecisionType)
        idx = DECISION_TYPE_INDEX.get(decision_type, len(DecisionType) - 1)
        if idx < len(vec):
            vec[idx] = 1.0
        return vec

    def _one_hot_risk(self, level: RiskLevel) -> list[float]:
        vec = [0.0] * len(RiskLevel)
        idx = RISK_LEVEL_ORDER.get(level, 0)
        if idx < len(vec):
            vec[idx] = 1.0
        return vec

    def _encode_objectives(self, request: DecisionRequest) -> list[float]:
        vec = [0.0] * 8
        for i, obj in enumerate(request.objectives[:8]):
            vec[i] = obj.weight * (1.0 if obj.maximize else -1.0)
        return vec

    def _encode_climate(self, request: DecisionRequest) -> list[float]:
        vec = [0.0] * 12
        climate = request.context.climate_state
        if not climate:
            return vec

        variable_map = {
            ClimateVariable.PRECIPITATION: 0,
            ClimateVariable.TEMPERATURE: 1,
            ClimateVariable.HUMIDITY: 2,
            ClimateVariable.WIND_SPEED: 3,
            ClimateVariable.SOIL_MOISTURE: 4,
            ClimateVariable.RIVER_DISCHARGE: 5,
        }
        for measurement in climate.measurements:
            idx = variable_map.get(measurement.variable)
            if idx is not None and idx < len(vec):
                vec[idx] = self._normalize(measurement.value, measurement.variable)

        if climate.location:
            vec[6] = (climate.location.latitude + 90.0) / 180.0
            vec[7] = (climate.location.longitude + 180.0) / 360.0

        vec[8] = 1.0 if climate.forecast_references else 0.0
        vec[9] = 1.0 if climate.active_simulation else 0.0
        vec[10] = 1.0 if climate.digital_twin else 0.0
        vec[11] = float(len(climate.measurements)) / 10.0
        return vec

    def _normalize(self, value: float, variable: ClimateVariable) -> float:
        scales: dict[ClimateVariable, float] = {
            ClimateVariable.PRECIPITATION: 200.0,
            ClimateVariable.TEMPERATURE: 50.0,
            ClimateVariable.HUMIDITY: 100.0,
            ClimateVariable.WIND_SPEED: 100.0,
            ClimateVariable.SOIL_MOISTURE: 1.0,
            ClimateVariable.RIVER_DISCHARGE: 5000.0,
        }
        scale = scales.get(variable, 100.0)
        return min(max(value / scale, 0.0), 1.0)

    def _extract_historical_reward(self, memory_context: dict[str, Any] | None) -> float:
        if not memory_context:
            return 0.0
        rewards = memory_context.get("historical_rewards", [])
        if not rewards:
            return 0.0
        return sum(float(r) for r in rewards) / len(rewards)

    def _flatten(self, features: dict[str, Any]) -> list[float]:
        vector: list[float] = []
        for key in (
            "decision_type", "priority", "confidence", "risk_score", "risk_level",
            "objective_weights", "constraint_budget", "constraint_safety",
            "climate_variables", "forecast_present", "simulation_present",
            "action_count", "need_flags", "historical_reward",
        ):
            value = features.get(key, 0.0)
            if isinstance(value, list):
                vector.extend(value)
            else:
                vector.append(float(value))
        return vector
