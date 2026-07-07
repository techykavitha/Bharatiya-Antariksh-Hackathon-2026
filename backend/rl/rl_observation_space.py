"""Observation space definitions for RL state encoding."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class FeatureType(StrEnum):
    """Data type of an observation feature."""

    SCALAR = "scalar"
    VECTOR = "vector"
    CATEGORICAL = "categorical"
    BINARY = "binary"


class ObservationFeature(BaseModel):
    """Single feature in the observation space."""

    name: str
    feature_type: FeatureType
    dimension: int = Field(default=1, ge=1)
    low: float = 0.0
    high: float = 1.0
    description: str = ""


class ObservationSpace(BaseModel):
    """Complete observation space specification."""

    features: list[ObservationFeature] = Field(default_factory=list)
    version: str = "1.0"

    @property
    def dimension(self) -> int:
        return sum(f.dimension for f in self.features)

    def feature_index(self, name: str) -> int:
        offset = 0
        for feature in self.features:
            if feature.name == name:
                return offset
            offset += feature.dimension
        raise KeyError(f"Feature not found: {name}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "dimension": self.dimension,
            "features": [f.model_dump() for f in self.features],
        }


def build_default_observation_space() -> ObservationSpace:
    """Build the standard Hyperion RL observation space."""
    return ObservationSpace(
        features=[
            ObservationFeature(name="decision_type", feature_type=FeatureType.CATEGORICAL, dimension=9),
            ObservationFeature(name="priority", feature_type=FeatureType.SCALAR, dimension=1, high=5.0),
            ObservationFeature(name="confidence", feature_type=FeatureType.SCALAR, dimension=1),
            ObservationFeature(name="risk_score", feature_type=FeatureType.SCALAR, dimension=1),
            ObservationFeature(name="risk_level", feature_type=FeatureType.CATEGORICAL, dimension=6),
            ObservationFeature(name="objective_weights", feature_type=FeatureType.VECTOR, dimension=8),
            ObservationFeature(name="constraint_budget", feature_type=FeatureType.SCALAR, dimension=1, high=1000.0),
            ObservationFeature(name="constraint_safety", feature_type=FeatureType.SCALAR, dimension=1),
            ObservationFeature(name="climate_variables", feature_type=FeatureType.VECTOR, dimension=12),
            ObservationFeature(name="forecast_present", feature_type=FeatureType.BINARY, dimension=1),
            ObservationFeature(name="simulation_present", feature_type=FeatureType.BINARY, dimension=1),
            ObservationFeature(name="action_count", feature_type=FeatureType.SCALAR, dimension=1, high=20.0),
            ObservationFeature(name="need_flags", feature_type=FeatureType.VECTOR, dimension=4),
            ObservationFeature(name="historical_reward", feature_type=FeatureType.SCALAR, dimension=1, low=-1.0, high=1.0),
        ],
    )
