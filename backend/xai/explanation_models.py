"""Core type definitions for the Explainability Framework."""

from __future__ import annotations

from enum import StrEnum


class ExplanationType(StrEnum):
    """Scope of explanation generation."""

    REASONING = "reasoning"
    DECISION = "decision"
    RL = "rl"
    FULL_PIPELINE = "full_pipeline"


class EvidenceSource(StrEnum):
    """Origin of an evidence item."""

    CLIMATE_VARIABLE = "climate_variable"
    FORECAST = "forecast"
    HISTORICAL_EVENT = "historical_event"
    DIGITAL_TWIN = "digital_twin"
    MEMORY = "memory"
    TOOL_OUTPUT = "tool_output"
    REASONING = "reasoning"
    DECISION = "decision"
    RL = "rl"


class ConfidenceDimension(StrEnum):
    """Dimensions used in confidence estimation."""

    MODEL = "model"
    DATA_QUALITY = "data_quality"
    FORECAST_RELIABILITY = "forecast_reliability"
    TOOL_CONSISTENCY = "tool_consistency"
    HISTORICAL_SIMILARITY = "historical_similarity"


class UncertaintyDimension(StrEnum):
    """Dimensions used in uncertainty estimation."""

    FORECAST = "forecast"
    MISSING_DATA = "missing_data"
    MODEL = "model"
    SIMULATION = "simulation"


class CounterfactualType(StrEnum):
    """Type of counterfactual scenario."""

    ALTERNATIVE_ACTION = "alternative_action"
    ALTERNATIVE_SCENARIO = "alternative_scenario"
    ALTERNATIVE_DECISION = "alternative_decision"
