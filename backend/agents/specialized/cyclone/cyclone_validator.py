"""Cyclone-specific input and output validation."""

from __future__ import annotations

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_validator import (
    AgentValidator,
    ValidationCategory,
    ValidationIssue,
    ValidationResult,
)
from backend.agents.specialized.cyclone.cyclone_context import CycloneInputs
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


class CycloneValidator:
    """Validates forecast, SST, pressure, wind, climate state, and digital twin."""

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
        issues.extend(self._validate_sst(inputs, tool_results, strict))
        issues.extend(self._validate_pressure(inputs, tool_results, strict))
        issues.extend(self._validate_wind(inputs, tool_results, strict))
        issues.extend(self._validate_forecast(context, inputs, strict))
        issues.extend(self._validate_climate_state(context, strict))
        issues.extend(self._validate_digital_twin(context, inputs, strict))
        issues.extend(self._validate_tool_outputs(tool_results))

        for issue in issues:
            context.add_validation_error(issue.message)

        blocking = [i for i in issues if i.severity >= 0.8]
        valid = len(blocking) == 0 if strict else len([i for i in issues if i.severity >= 0.9]) == 0
        return ValidationResult(valid=valid, issues=issues)

    def _resolve_inputs(self, context: AgentContext) -> CycloneInputs:
        stored = context.metadata.get("cyclone_inputs")
        if isinstance(stored, CycloneInputs):
            return stored
        return CycloneInputs.from_request_context(context.request.context)

    def _validate_sst(
        self, inputs: CycloneInputs, tool_results: list[ToolResult], strict: bool,
    ) -> list[ValidationIssue]:
        has_data = (
            inputs.ocean.sst_c is not None
            or any(r.tool_name == "sst_tool" and r.success for r in tool_results)
        )
        if not has_data:
            return [ValidationIssue(
                category=ValidationCategory.REQUIRED_INPUTS,
                field="sst",
                message="Sea surface temperature data required for cyclone analysis",
                severity=0.9 if strict else 0.6,
            )]
        return []

    def _validate_pressure(
        self, inputs: CycloneInputs, tool_results: list[ToolResult], strict: bool,
    ) -> list[ValidationIssue]:
        has_data = (
            inputs.ocean.sea_level_pressure_hpa is not None
            or any(r.tool_name == "pressure_tool" and r.success for r in tool_results)
        )
        if not has_data:
            return [ValidationIssue(
                category=ValidationCategory.REQUIRED_INPUTS,
                field="pressure",
                message="Sea level pressure data required for cyclone detection",
                severity=0.85 if strict else 0.55,
            )]
        return []

    def _validate_wind(
        self, inputs: CycloneInputs, tool_results: list[ToolResult], strict: bool,
    ) -> list[ValidationIssue]:
        has_data = (
            inputs.ocean.wind_speed_kt is not None
            or inputs.forecast.max_wind_kt_forecast is not None
            or any(r.tool_name == "wind_tool" and r.success for r in tool_results)
        )
        if not has_data:
            return [ValidationIssue(
                category=ValidationCategory.REQUIRED_INPUTS,
                field="wind",
                message="Wind speed data required for intensity classification",
                severity=0.85 if strict else 0.5,
            )]
        return []

    def _validate_forecast(
        self, context: AgentContext, inputs: CycloneInputs, strict: bool,
    ) -> list[ValidationIssue]:
        has_forecast = (
            inputs.forecast_available
            or bool(context.forecast.references)
            or bool(inputs.forecast.track_points)
            or inputs.forecast.landfall_probability is not None
        )
        if not has_forecast:
            return [ValidationIssue(
                category=ValidationCategory.FORECAST_CONSISTENCY,
                field="forecast",
                message="Track forecast not available for landfall assessment",
                severity=0.7 if strict else 0.4,
            )]
        return []

    def _validate_climate_state(self, context: AgentContext, strict: bool) -> list[ValidationIssue]:
        if not context.climate_state:
            return [ValidationIssue(
                category=ValidationCategory.CLIMATE_CONSISTENCY,
                field="climate_state",
                message="Climate state not attached to request",
                severity=0.75 if strict else 0.45,
            )]
        return []

    def _validate_digital_twin(
        self, context: AgentContext, inputs: CycloneInputs, strict: bool,
    ) -> list[ValidationIssue]:
        has_twin = (
            inputs.digital_twin_available
            or bool(context.digital_twin_state)
            or (context.climate_state and context.climate_state.digital_twin is not None)
        )
        if not has_twin:
            return [ValidationIssue(
                category=ValidationCategory.REQUIRED_INPUTS,
                field="digital_twin",
                message="Digital twin state not available",
                severity=0.6 if strict else 0.3,
            )]
        return []

    def _validate_tool_outputs(self, tool_results: list[ToolResult]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for result in tool_results:
            if not result.success:
                issues.append(ValidationIssue(
                    category=ValidationCategory.TOOL_OUTPUTS,
                    field=result.tool_name,
                    message=f"Cyclone tool '{result.tool_name}' failed: {result.error}",
                    severity=0.65,
                ))
        return issues
