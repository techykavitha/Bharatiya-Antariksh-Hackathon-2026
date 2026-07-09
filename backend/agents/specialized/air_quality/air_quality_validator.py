"""Air quality input and output validation."""

from __future__ import annotations

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_validator import (
    AgentValidator,
    ValidationCategory,
    ValidationIssue,
    ValidationResult,
)
from backend.agents.specialized.air_quality.air_quality_context import AirQualityInputs
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


class AirQualityValidator:
    """Validates air quality inputs, forecast, climate state, and digital twin."""

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
        issues.extend(self._validate_pollution_data(inputs, strict))
        issues.extend(self._validate_forecast(context, inputs, strict))
        issues.extend(self._validate_climate_state(context, strict))
        issues.extend(self._validate_digital_twin(context, inputs, strict))
        issues.extend(self._validate_tool_outputs(tool_results))

        for issue in issues:
            context.add_validation_error(issue.message)

        blocking = [i for i in issues if i.severity >= 0.8]
        valid = len(blocking) == 0 if strict else len([i for i in issues if i.severity >= 0.9]) == 0
        return ValidationResult(valid=valid, issues=issues)

    def _resolve_inputs(self, context: AgentContext) -> AirQualityInputs:
        stored = context.metadata.get("air_quality_inputs")
        if isinstance(stored, AirQualityInputs):
            return stored
        return AirQualityInputs.from_request_context(context.request.context)

    def _validate_pollution_data(self, inputs: AirQualityInputs, strict: bool) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not inputs.region_id and not inputs.city_name:
            issues.append(ValidationIssue(
                category=ValidationCategory.REQUIRED_INPUTS,
                field="region_id",
                message="Region or city identifier required for air quality assessment",
                severity=0.7 if strict else 0.4,
            ))
        if not inputs.pollutants:
            issues.append(ValidationIssue(
                category=ValidationCategory.REQUIRED_INPUTS,
                field="pollutants",
                message="At least one pollutant concentration required for AQI computation",
                severity=0.75 if strict else 0.45,
            ))
        if inputs.population_total <= 0 and inputs.population_density <= 0:
            issues.append(ValidationIssue(
                category=ValidationCategory.REQUIRED_INPUTS,
                field="population_total",
                message="Population data needed for exposure analysis",
                severity=0.55 if strict else 0.35,
            ))
        return issues

    def _validate_forecast(
        self, context: AgentContext, inputs: AirQualityInputs, strict: bool,
    ) -> list[ValidationIssue]:
        has_forecast = inputs.forecast_available or bool(context.forecast.references)
        if not has_forecast:
            return [ValidationIssue(
                category=ValidationCategory.FORECAST_CONSISTENCY,
                field="forecast",
                message="Air quality forecast not available for trend projection",
                severity=0.5 if strict else 0.3,
            )]
        return []

    def _validate_climate_state(self, context: AgentContext, strict: bool) -> list[ValidationIssue]:
        if not context.climate_state:
            return [ValidationIssue(
                category=ValidationCategory.CLIMATE_CONSISTENCY,
                field="climate_state",
                message="Climate state not attached to air quality request",
                severity=0.65 if strict else 0.35,
            )]
        return []

    def _validate_digital_twin(
        self, context: AgentContext, inputs: AirQualityInputs, strict: bool,
    ) -> list[ValidationIssue]:
        has_twin = inputs.digital_twin_available or bool(context.digital_twin_state)
        if not has_twin:
            return [ValidationIssue(
                category=ValidationCategory.REQUIRED_INPUTS,
                field="digital_twin",
                message="Digital twin not available for spatial pollution mapping",
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
                    message=f"Air quality tool '{result.tool_name}' failed: {result.error}",
                    severity=0.55,
                ))
        return issues
