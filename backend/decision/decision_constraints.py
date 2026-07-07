"""Constraint models governing feasible decision actions."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ConstraintCategory(StrEnum):
    """Categories of operational constraints."""

    BUDGET = "budget"
    TIME = "time"
    WATER = "water"
    POWER = "power"
    POPULATION = "population"
    ENVIRONMENT = "environment"
    POLICY = "policy"
    SAFETY = "safety"


class BudgetConstraint(BaseModel):
    """Financial budget limit for action execution."""

    max_cost: float = Field(..., ge=0.0)
    currency: str = "INR"
    unit: str = "lakhs"


class TimeConstraint(BaseModel):
    """Temporal window for decision execution."""

    max_hours: float = Field(..., ge=0.0)
    deadline_utc: str | None = None
    min_lead_time_hours: float = Field(default=0.0, ge=0.0)


class WaterConstraint(BaseModel):
    """Water volume allocation limits."""

    max_release_m3: float | None = Field(default=None, ge=0.0)
    min_reserve_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    max_extraction_m3d: float | None = Field(default=None, ge=0.0)


class PowerConstraint(BaseModel):
    """Energy and grid capacity limits."""

    max_load_mw: float | None = Field(default=None, ge=0.0)
    backup_required: bool = False


class PopulationConstraint(BaseModel):
    """Population exposure and evacuation limits."""

    max_affected_population: int | None = Field(default=None, ge=0)
    evacuation_required_above: int | None = Field(default=None, ge=0)


class EnvironmentConstraint(BaseModel):
    """Environmental impact thresholds."""

    max_emissions_tons: float | None = Field(default=None, ge=0.0)
    protected_areas: list[str] = Field(default_factory=list)
    min_eco_flow_m3s: float | None = Field(default=None, ge=0.0)


class PolicyConstraint(BaseModel):
    """Regulatory and governance constraints."""

    policies: list[str] = Field(default_factory=list)
    approval_required: bool = False
    regulatory_body: str | None = None


class SafetyConstraint(BaseModel):
    """Safety thresholds that must not be violated."""

    max_risk_score: float = Field(default=0.85, ge=0.0, le=1.0)
    mandatory_protocols: list[str] = Field(default_factory=list)
    no_go_regions: list[str] = Field(default_factory=list)


class DecisionConstraints(BaseModel):
    """Aggregated constraint set for a decision request."""

    budget: BudgetConstraint | None = None
    time: TimeConstraint | None = None
    water: WaterConstraint | None = None
    power: PowerConstraint | None = None
    population: PopulationConstraint | None = None
    environment: EnvironmentConstraint | None = None
    policy: PolicyConstraint | None = None
    safety: SafetyConstraint | None = None
    custom: dict[str, Any] = Field(default_factory=dict)

    def active_categories(self) -> list[ConstraintCategory]:
        mapping: list[tuple[ConstraintCategory, object | None]] = [
            (ConstraintCategory.BUDGET, self.budget),
            (ConstraintCategory.TIME, self.time),
            (ConstraintCategory.WATER, self.water),
            (ConstraintCategory.POWER, self.power),
            (ConstraintCategory.POPULATION, self.population),
            (ConstraintCategory.ENVIRONMENT, self.environment),
            (ConstraintCategory.POLICY, self.policy),
            (ConstraintCategory.SAFETY, self.safety),
        ]
        return [cat for cat, value in mapping if value is not None]

    @model_validator(mode="after")
    def ensure_safety_default(self) -> DecisionConstraints:
        if self.safety is None:
            self.safety = SafetyConstraint()
        return self
