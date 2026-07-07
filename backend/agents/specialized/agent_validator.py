"""Validation engine for specialized agent inputs and outputs."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


class ValidationCategory(StrEnum):
    """Categories of validation performed by specialized agents."""

    REQUIRED_INPUTS = "required_inputs"
    TOOL_OUTPUTS = "tool_outputs"
    FORECAST_CONSISTENCY = "forecast_consistency"
    MEMORY_CONSISTENCY = "memory_consistency"
    CLIMATE_CONSISTENCY = "climate_consistency"


class ValidationIssue(BaseModel):
    """A single validation issue."""

    category: ValidationCategory
    message: str
    field: str | None = None
    severity: float = Field(default=0.5, ge=0.0, le=1.0)


class ValidationResult(BaseModel):
    """Aggregated validation outcome."""

    valid: bool = True
    issues: list[ValidationIssue] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def error_messages(self) -> list[str]:
        return [issue.message for issue in self.issues]


class AgentValidator:
    """
    Validates tool outputs, forecast consistency, memory consistency,
    and required inputs before report generation.
    """

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id

    async def validate(
        self,
        context: AgentContext,
        tool_results: list[ToolResult],
        *,
        required_inputs: list[str] | None = None,
        require_forecast: bool = False,
        require_memory: bool = False,
    ) -> ValidationResult:
        issues: list[ValidationIssue] = []

        issues.extend(self._validate_required_inputs(context, required_inputs or []))
        issues.extend(self._validate_tool_outputs(tool_results))
        issues.extend(self._validate_forecast_consistency(context, require_forecast))
        issues.extend(self._validate_memory_consistency(context, require_memory))
        issues.extend(self._validate_climate_consistency(context))

        for issue in issues:
            context.add_validation_error(issue.message)

        valid = not any(issue.severity >= 0.8 for issue in issues)
        result = ValidationResult(valid=valid, issues=issues)

        logger.debug(
            "validation_completed",
            agent_id=self._agent_id,
            valid=valid,
            issue_count=len(issues),
        )
        return result

    def _validate_required_inputs(
        self,
        context: AgentContext,
        required: list[str],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for field in required:
            if field == "query" and not context.query.strip():
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.REQUIRED_INPUTS,
                        field=field,
                        message="Query is required",
                        severity=1.0,
                    ),
                )
            elif field == "climate_state" and context.climate_state is None:
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.REQUIRED_INPUTS,
                        field=field,
                        message="Climate state is required",
                        severity=0.9,
                    ),
                )
            elif field == "scenario_id" and not context.scenario.scenario_id:
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.REQUIRED_INPUTS,
                        field=field,
                        message="Scenario ID is required",
                        severity=0.9,
                    ),
                )
            elif field in context.request.context and not context.request.context.get(field):
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.REQUIRED_INPUTS,
                        field=field,
                        message=f"Required context field '{field}' is missing or empty",
                        severity=0.85,
                    ),
                )
        return issues

    def _validate_tool_outputs(self, tool_results: list[ToolResult]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for result in tool_results:
            if not result.success:
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.TOOL_OUTPUTS,
                        field=result.tool_name,
                        message=f"Tool '{result.tool_name}' failed: {result.error or 'unknown error'}",
                        severity=0.7,
                    ),
                )
            elif result.output is None:
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.TOOL_OUTPUTS,
                        field=result.tool_name,
                        message=f"Tool '{result.tool_name}' returned no output",
                        severity=0.4,
                    ),
                )
        return issues

    def _validate_forecast_consistency(
        self,
        context: AgentContext,
        require_forecast: bool,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        forecast = context.forecast
        climate = context.climate_state

        if require_forecast and not forecast.references and not forecast.payload:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.FORECAST_CONSISTENCY,
                    message="Forecast data is required but not present",
                    severity=0.9,
                ),
            )

        if climate and forecast.references:
            climate_ids = {ref.forecast_id for ref in climate.forecast_references}
            context_ids = {ref.forecast_id for ref in forecast.references}
            orphan = context_ids - climate_ids
            if orphan and climate_ids:
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.FORECAST_CONSISTENCY,
                        message=f"Forecast references not present in climate state: {orphan}",
                        severity=0.5,
                    ),
                )
        return issues

    def _validate_memory_consistency(
        self,
        context: AgentContext,
        require_memory: bool,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if require_memory and not context.memory.entries and not context.memory.ranked_results:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.MEMORY_CONSISTENCY,
                    message="Memory retrieval required but no entries found",
                    severity=0.8,
                ),
            )

        ref_set = set(context.memory.references)
        for entry in context.memory.entries:
            if entry.key and entry.key not in ref_set and context.memory.references:
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.MEMORY_CONSISTENCY,
                        message=f"Memory entry '{entry.key}' missing from references",
                        severity=0.3,
                    ),
                )
        return issues

    def _validate_climate_consistency(self, context: AgentContext) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        climate = context.climate_state
        if not climate:
            return issues

        if context.scenario.scenario_id and climate.scenario_id:
            if context.scenario.scenario_id != climate.scenario_id:
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.CLIMATE_CONSISTENCY,
                        message="Scenario ID mismatch between context and climate state",
                        severity=0.6,
                    ),
                )
        return issues
