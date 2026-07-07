"""Constraint validation engine for RL action selection."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from backend.decision.decision_actions import DecisionAction
from backend.decision.decision_constraints import ConstraintCategory, DecisionConstraints
from backend.decision.decision_request import DecisionRequest


class ViolationSeverity(StrEnum):
    """Severity of a constraint violation."""

    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ConstraintViolation(BaseModel):
    """A single constraint violation."""

    category: ConstraintCategory
    field: str
    message: str
    severity: ViolationSeverity = ViolationSeverity.ERROR
    action_id: str = ""


class ConstraintValidationResult(BaseModel):
    """Outcome of constraint validation for an action."""

    feasible: bool
    violations: list[ConstraintViolation] = Field(default_factory=list)
    action_id: str = ""

    @property
    def blocking_violations(self) -> list[ConstraintViolation]:
        return [
            v for v in self.violations
            if v.severity in (ViolationSeverity.ERROR, ViolationSeverity.CRITICAL)
        ]


class RLConstraintEngine:
    """
    Validates actions against budget, safety, legal, environmental,
    and resource availability constraints.
    """

    def validate_action(
        self,
        action: DecisionAction,
        constraints: DecisionConstraints,
    ) -> ConstraintValidationResult:
        violations: list[ConstraintViolation] = []
        violations.extend(self._check_budget(action, constraints))
        violations.extend(self._check_safety(action, constraints))
        violations.extend(self._check_time(action, constraints))
        violations.extend(self._check_water(action, constraints))
        violations.extend(self._check_power(action, constraints))
        violations.extend(self._check_population(action, constraints))
        violations.extend(self._check_environment(action, constraints))
        violations.extend(self._check_policy(action, constraints))

        blocking = [v for v in violations if v.severity in (
            ViolationSeverity.ERROR, ViolationSeverity.CRITICAL,
        )]
        return ConstraintValidationResult(
            feasible=len(blocking) == 0,
            violations=violations,
            action_id=action.action_id,
        )

    def filter_feasible(
        self,
        request: DecisionRequest,
    ) -> tuple[list[DecisionAction], list[ConstraintValidationResult]]:
        feasible: list[DecisionAction] = []
        results: list[ConstraintValidationResult] = []
        for action in request.possible_actions:
            result = self.validate_action(action, request.constraints)
            results.append(result)
            if result.feasible:
                feasible.append(action)
        return feasible, results

    def validate_all(
        self,
        request: DecisionRequest,
    ) -> list[ConstraintValidationResult]:
        return [
            self.validate_action(action, request.constraints)
            for action in request.possible_actions
        ]

    def _check_budget(
        self,
        action: DecisionAction,
        constraints: DecisionConstraints,
    ) -> list[ConstraintViolation]:
        if constraints.budget and action.cost > constraints.budget.max_cost:
            return [ConstraintViolation(
                category=ConstraintCategory.BUDGET,
                field="cost",
                message=f"Cost {action.cost} exceeds budget {constraints.budget.max_cost}",
                action_id=action.action_id,
            )]
        return []

    def _check_safety(
        self,
        action: DecisionAction,
        constraints: DecisionConstraints,
    ) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        if constraints.safety:
            if action.risk_score > constraints.safety.max_risk_score:
                violations.append(ConstraintViolation(
                    category=ConstraintCategory.SAFETY,
                    field="risk_score",
                    message="Action risk exceeds safety threshold",
                    action_id=action.action_id,
                ))
            for region in action.affected_regions:
                if region in constraints.safety.no_go_regions:
                    violations.append(ConstraintViolation(
                        category=ConstraintCategory.SAFETY,
                        field="affected_regions",
                        message=f"No-go region: {region}",
                        severity=ViolationSeverity.CRITICAL,
                        action_id=action.action_id,
                    ))
        return violations

    def _check_time(
        self,
        action: DecisionAction,
        constraints: DecisionConstraints,
    ) -> list[ConstraintViolation]:
        return []

    def _check_water(
        self,
        action: DecisionAction,
        constraints: DecisionConstraints,
    ) -> list[ConstraintViolation]:
        return []

    def _check_power(
        self,
        action: DecisionAction,
        constraints: DecisionConstraints,
    ) -> list[ConstraintViolation]:
        return []

    def _check_population(
        self,
        action: DecisionAction,
        constraints: DecisionConstraints,
    ) -> list[ConstraintViolation]:
        if (
            constraints.population
            and constraints.population.max_affected_population is not None
            and action.affected_population > constraints.population.max_affected_population
        ):
            return [ConstraintViolation(
                category=ConstraintCategory.POPULATION,
                field="affected_population",
                message="Exceeds maximum affected population",
                action_id=action.action_id,
            )]
        return []

    def _check_environment(
        self,
        action: DecisionAction,
        constraints: DecisionConstraints,
    ) -> list[ConstraintViolation]:
        if not constraints.environment:
            return []
        violations: list[ConstraintViolation] = []
        for region in action.affected_regions:
            if region in constraints.environment.protected_areas:
                violations.append(ConstraintViolation(
                    category=ConstraintCategory.ENVIRONMENT,
                    field="affected_regions",
                    message=f"Protected area affected: {region}",
                    severity=ViolationSeverity.CRITICAL,
                    action_id=action.action_id,
                ))
        return violations

    def _check_policy(
        self,
        action: DecisionAction,
        constraints: DecisionConstraints,
    ) -> list[ConstraintViolation]:
        if constraints.policy and constraints.policy.approval_required and action.cost > 100.0:
            return [ConstraintViolation(
                category=ConstraintCategory.POLICY,
                field="approval",
                message="High-cost action requires policy approval",
                severity=ViolationSeverity.WARNING,
                action_id=action.action_id,
            )]
        return []
