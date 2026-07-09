"""Urban planning input and output validation."""

from __future__ import annotations

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_validator import (
    AgentValidator,
    ValidationCategory,
    ValidationIssue,
    ValidationResult,
)
from backend.agents.specialized.urban_planning.urban_context import UrbanInputs
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


class UrbanValidator:
    """Validates urban planning inputs, forecast, climate state, and digital twin."""

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id
        self._base = AgentValidator(agent_id=agent_id)

    async def validate(
        self,
        context: AgentContext,
        tool_results: list[ToolResult],
        *,
        strict: bool = False,
    ) -> ValidationResult:
        issues: list[ValidationIssue] = []
        inputs = self._resolve_inputs(context)

        base_result = await self._base.validate(context, tool_results, required_inputs=["query"])
        issues.extend(base_result.issues)
        issues.extend(self._validate_urban_data(inputs, strict))
        issues.extend(self._validate_forecast(context, inputs, strict))
        issues.extend(self._validate_climate_state(context, strict))
        issues.extend(self._validate_digital_twin(context, inputs, strict))
        issues.extend(self._validate_tool_outputs(tool_results))

        for issue in issues:
            context.add_validation_error(issue.message)

        blocking = [i for i in issues if i.severity >= 0.8]
        valid = len(blocking) == 0 if strict else len([i for i in issues if i.severity >= 0.9]) == 0
        return ValidationResult(valid=valid, issues=issues)

    def _resolve_inputs(self, context: AgentContext) -> UrbanInputs:
        stored = context.metadata.get("urban_inputs")
        if isinstance(stored, UrbanInputs):
            return stored
        return UrbanInputs.from_request_context(context.request.context)

    def _validate_urban_data(self, inputs: UrbanInputs, strict: bool) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not inputs.region_id and not inputs.city_name:
            issues.append(ValidationIssue(
                category=ValidationCategory.REQUIRED_INPUTS,
                field="region_id",
                message="Urban region or city identifier required for planning",
                severity=0.7 if strict else 0.4,
            ))
        if inputs.environment.population_density <= 0 and not inputs.districts:
            issues.append(ValidationIssue(
                category=ValidationCategory.REQUIRED_INPUTS,
                field="population_density",
                message="Population density or district list needed for exposure analysis",
                severity=0.55 if strict else 0.35,
            ))
        return issues

    def _validate_forecast(
        self, context: AgentContext, inputs: UrbanInputs, strict: bool,
    ) -> list[ValidationIssue]:
        has_forecast = inputs.forecast_available or bool(context.forecast.references)
        if not has_forecast:
            return [ValidationIssue(
                category=ValidationCategory.FORECAST_CONSISTENCY,
                field="forecast",
                message="Climate forecast not available for long-term planning horizon",
                severity=0.5 if strict else 0.3,
            )]
        return []

    def _validate_climate_state(self, context: AgentContext, strict: bool) -> list[ValidationIssue]:
        if not context.climate_state:
            return [ValidationIssue(
                category=ValidationCategory.CLIMATE_CONSISTENCY,
                field="climate_state",
                message="Climate state not attached to urban planning request",
                severity=0.65 if strict else 0.35,
            )]
        return []

    def _validate_digital_twin(
        self, context: AgentContext, inputs: UrbanInputs, strict: bool,
    ) -> list[ValidationIssue]:
        has_twin = inputs.digital_twin_available or bool(context.digital_twin_state)
        if not has_twin:
            return [ValidationIssue(
                category=ValidationCategory.REQUIRED_INPUTS,
                field="digital_twin",
                message="Digital twin not available for scenario-ready planning",
                severity=0.5 if strict else 0.25,
            )]
        return []

    def _validate_tool_outputs(self, tool_results: list[ToolResult]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for result in tool_results:
            if not result.success:
                issues.append(ValidationIssue(
                    category=ValidationCategory.TOOL_OUTPUTS,
                    field=result.tool_name,
                    message=f"Urban tool '{result.tool_name}' failed: {result.error}",
                    severity=0.55,
                ))
        return issues
