"""Validation for decision requests and responses."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from backend.decision.decision_actions import DecisionAction
from backend.decision.decision_constraints import DecisionConstraints
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.decision.decision_types import Objective, RiskAssessment, RiskLevel
from backend.utils.errors import HyperionError


class ValidationSeverity(StrEnum):
    """Severity of a validation issue."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationIssue(BaseModel):
    """A single validation finding."""

    field: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    code: str = "validation_error"


class ValidationResult(BaseModel):
    """Outcome of decision validation."""

    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def blocking_issues(self) -> list[ValidationIssue]:
        return [
            i for i in self.issues
            if i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)
        ]


class DecisionValidationError(HyperionError):
    """Raised when decision validation fails in strict mode."""


class DecisionValidator:
    """Validates objectives, actions, constraints, confidence, and risk."""

    MIN_ACTIONS = 1
    MIN_CONFIDENCE = 0.0
    MAX_CONFIDENCE = 1.0

    def validate_request(
        self,
        request: DecisionRequest,
        *,
        strict: bool = False,
    ) -> ValidationResult:
        issues: list[ValidationIssue] = []
        issues.extend(self._validate_objectives(request.objectives))
        issues.extend(self._validate_actions(request.possible_actions, request.constraints))
        issues.extend(self._validate_constraints(request.constraints))
        issues.extend(self._validate_confidence(request.confidence))
        issues.extend(self._validate_risk(request.risk, request.possible_actions))
        issues.extend(self._validate_context(request))
        issues.extend(self._validate_flags(request))

        blocking = [i for i in issues if i.severity in (
            ValidationSeverity.ERROR, ValidationSeverity.CRITICAL,
        )]
        valid = len(blocking) == 0

        if strict and not valid:
            raise DecisionValidationError(
                "Decision request validation failed",
                details={"issues": [i.model_dump() for i in blocking]},
            )

        return ValidationResult(valid=valid, issues=issues)

    def validate_response(
        self,
        response: DecisionResponse,
        request: DecisionRequest,
        *,
        strict: bool = False,
    ) -> ValidationResult:
        issues: list[ValidationIssue] = []

        if response.decision_id != request.decision_id:
            issues.append(ValidationIssue(
                field="decision_id",
                message="Response decision_id does not match request",
                severity=ValidationSeverity.CRITICAL,
                code="id_mismatch",
            ))

        if response.chosen_action is None and response.status == response.status.COMPLETED:
            issues.append(ValidationIssue(
                field="chosen_action",
                message="Completed response must include chosen_action",
                severity=ValidationSeverity.ERROR,
                code="missing_chosen_action",
            ))

        if response.chosen_action:
            known_ids = {a.action_id for a in request.possible_actions}
            if response.chosen_action.action_id not in known_ids:
                issues.append(ValidationIssue(
                    field="chosen_action",
                    message="Chosen action not in request possible_actions",
                    severity=ValidationSeverity.WARNING,
                    code="unknown_action",
                ))
            issues.extend(
                self._validate_action_against_constraints(
                    response.chosen_action, request.constraints,
                ),
            )

        issues.extend(self._validate_confidence(response.confidence))

        for rank in response.ranking:
            if rank.rank < 1:
                issues.append(ValidationIssue(
                    field="ranking",
                    message=f"Invalid rank {rank.rank} for action {rank.action_id}",
                    severity=ValidationSeverity.ERROR,
                    code="invalid_rank",
                ))

        blocking = [i for i in issues if i.severity in (
            ValidationSeverity.ERROR, ValidationSeverity.CRITICAL,
        )]
        valid = len(blocking) == 0

        if strict and not valid:
            raise DecisionValidationError(
                "Decision response validation failed",
                details={"issues": [i.model_dump() for i in blocking]},
            )

        return ValidationResult(valid=valid, issues=issues)

    def _validate_objectives(self, objectives: list[Objective]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not objectives:
            issues.append(ValidationIssue(
                field="objectives",
                message="At least one objective is recommended",
                severity=ValidationSeverity.WARNING,
                code="empty_objectives",
            ))
        ids = [o.objective_id for o in objectives]
        if len(ids) != len(set(ids)):
            issues.append(ValidationIssue(
                field="objectives",
                message="Duplicate objective_id values detected",
                severity=ValidationSeverity.ERROR,
                code="duplicate_objectives",
            ))
        total_weight = sum(o.weight for o in objectives)
        if objectives and total_weight <= 0:
            issues.append(ValidationIssue(
                field="objectives",
                message="Total objective weight must be positive",
                severity=ValidationSeverity.ERROR,
                code="invalid_objective_weights",
            ))
        return issues

    def _validate_actions(
        self,
        actions: list[DecisionAction],
        constraints: DecisionConstraints,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if len(actions) < self.MIN_ACTIONS:
            issues.append(ValidationIssue(
                field="possible_actions",
                message=f"At least {self.MIN_ACTIONS} possible action(s) required",
                severity=ValidationSeverity.ERROR,
                code="insufficient_actions",
            ))

        ids = [a.action_id for a in actions]
        if len(ids) != len(set(ids)):
            issues.append(ValidationIssue(
                field="possible_actions",
                message="Duplicate action_id values detected",
                severity=ValidationSeverity.ERROR,
                code="duplicate_actions",
            ))

        for action in actions:
            issues.extend(self._validate_action_against_constraints(action, constraints))
        return issues

    def _validate_action_against_constraints(
        self,
        action: DecisionAction,
        constraints: DecisionConstraints,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if constraints.budget and action.cost > constraints.budget.max_cost:
            issues.append(ValidationIssue(
                field=f"possible_actions.{action.action_id}.cost",
                message=f"Action cost {action.cost} exceeds budget {constraints.budget.max_cost}",
                severity=ValidationSeverity.ERROR,
                code="budget_exceeded",
            ))

        if constraints.safety and action.risk_score > constraints.safety.max_risk_score:
            issues.append(ValidationIssue(
                field=f"possible_actions.{action.action_id}.risk_score",
                message=(
                    f"Action risk {action.risk_score} exceeds safety threshold "
                    f"{constraints.safety.max_risk_score}"
                ),
                severity=ValidationSeverity.ERROR,
                code="safety_violation",
            ))

        if constraints.population and constraints.population.max_affected_population is not None:
            if action.affected_population > constraints.population.max_affected_population:
                issues.append(ValidationIssue(
                    field=f"possible_actions.{action.action_id}.affected_population",
                    message="Action exceeds maximum affected population constraint",
                    severity=ValidationSeverity.ERROR,
                    code="population_exceeded",
                ))

        if constraints.safety:
            for region in action.affected_regions:
                if region in constraints.safety.no_go_regions:
                    issues.append(ValidationIssue(
                        field=f"possible_actions.{action.action_id}.affected_regions",
                        message=f"Action affects no-go region: {region}",
                        severity=ValidationSeverity.CRITICAL,
                        code="no_go_region",
                    ))
        return issues

    def _validate_constraints(self, constraints: DecisionConstraints) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if constraints.time and constraints.time.max_hours <= 0:
            issues.append(ValidationIssue(
                field="constraints.time.max_hours",
                message="Time constraint max_hours must be positive",
                severity=ValidationSeverity.ERROR,
                code="invalid_time_constraint",
            ))
        if constraints.water:
            if (
                constraints.water.min_reserve_pct is not None
                and constraints.water.max_release_m3 is not None
                and constraints.water.min_reserve_pct > 100
            ):
                issues.append(ValidationIssue(
                    field="constraints.water",
                    message="Invalid water constraint configuration",
                    severity=ValidationSeverity.ERROR,
                    code="invalid_water_constraint",
                ))
        return issues

    def _validate_confidence(self, confidence: float) -> list[ValidationIssue]:
        if confidence < self.MIN_CONFIDENCE or confidence > self.MAX_CONFIDENCE:
            return [ValidationIssue(
                field="confidence",
                message=f"Confidence must be between {self.MIN_CONFIDENCE} and {self.MAX_CONFIDENCE}",
                severity=ValidationSeverity.ERROR,
                code="invalid_confidence",
            )]
        return []

    def _validate_risk(
        self,
        risk: RiskAssessment,
        actions: list[DecisionAction],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if risk.level == RiskLevel.CRITICAL and risk.score < 0.7:
            issues.append(ValidationIssue(
                field="risk",
                message="Critical risk level should have score >= 0.7",
                severity=ValidationSeverity.WARNING,
                code="risk_inconsistency",
            ))
        if actions and risk.affected_population > 0:
            max_action_pop = max(a.affected_population for a in actions)
            if risk.affected_population < max_action_pop:
                issues.append(ValidationIssue(
                    field="risk.affected_population",
                    message="Risk affected_population is less than max action exposure",
                    severity=ValidationSeverity.WARNING,
                    code="population_mismatch",
                ))
        return issues

    def _validate_context(self, request: DecisionRequest) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if request.need_simulation and not request.simulation_reference:
            issues.append(ValidationIssue(
                field="simulation_reference",
                message="need_simulation is True but no simulation reference provided",
                severity=ValidationSeverity.WARNING,
                code="missing_simulation_ref",
            ))
        if request.need_rl and not request.possible_actions:
            issues.append(ValidationIssue(
                field="need_rl",
                message="need_rl is True but no possible_actions defined",
                severity=ValidationSeverity.ERROR,
                code="rl_without_actions",
            ))
        return issues

    def _validate_flags(self, request: DecisionRequest) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if request.need_human and request.confidence > 0.9:
            issues.append(ValidationIssue(
                field="need_human",
                message="High confidence with need_human flag may be inconsistent",
                severity=ValidationSeverity.INFO,
                code="human_review_info",
            ))
        return issues
