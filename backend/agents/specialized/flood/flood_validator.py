"""Flood-specific input and output validation."""

from __future__ import annotations

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_validator import (
    AgentValidator,
    ValidationCategory,
    ValidationIssue,
    ValidationResult,
)
from backend.agents.specialized.flood.flood_context import FloodInputs
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


class FloodValidator:
    """
    Validates flood analysis prerequisites:
    rainfall, DEM, forecast, climate state, and digital twin.
    """

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

        base_result = await self._base.validate(
            context,
            tool_results,
            required_inputs=["query"],
        )
        issues.extend(base_result.issues)

        issues.extend(self._validate_rainfall(inputs, tool_results, strict))
        issues.extend(self._validate_dem(inputs, tool_results, strict))
        issues.extend(self._validate_forecast(context, inputs, strict))
        issues.extend(self._validate_climate_state(context, strict))
        issues.extend(self._validate_digital_twin(context, inputs, strict))
        issues.extend(self._validate_tool_outputs(tool_results))

        for issue in issues:
            context.add_validation_error(issue.message)

        blocking = [i for i in issues if i.severity >= 0.8]
        valid = len(blocking) == 0 if strict else len([i for i in issues if i.severity >= 0.9]) == 0

        result = ValidationResult(valid=valid, issues=issues)
        logger.debug(
            "flood_validation_completed",
            agent_id=self._agent_id,
            valid=valid,
            issues=len(issues),
        )
        return result

    def _resolve_inputs(self, context: AgentContext) -> FloodInputs:
        stored = context.metadata.get("flood_inputs")
        if isinstance(stored, FloodInputs):
            return stored
        return FloodInputs.from_request_context(context.request.context)

    def _validate_rainfall(
        self,
        inputs: FloodInputs,
        tool_results: list[ToolResult],
        strict: bool,
    ) -> list[ValidationIssue]:
        has_data = (
            inputs.rainfall.current_mm is not None
            or inputs.rainfall.forecast_24h_mm is not None
            or any(r.tool_name == "rainfall_tool" and r.success for r in tool_results)
        )
        if not has_data:
            return [ValidationIssue(
                category=ValidationCategory.REQUIRED_INPUTS,
                field="rainfall",
                message="Rainfall data is required for flood analysis",
                severity=0.9 if strict else 0.6,
            )]
        return []

    def _validate_dem(
        self,
        inputs: FloodInputs,
        tool_results: list[ToolResult],
        strict: bool,
    ) -> list[ValidationIssue]:
        has_dem = (
            inputs.dem_available
            or inputs.terrain.dem_resolution_m is not None
            or any(r.tool_name == "dem_tool" and r.success for r in tool_results)
        )
        if not has_dem:
            return [ValidationIssue(
                category=ValidationCategory.REQUIRED_INPUTS,
                field="dem",
                message="DEM data is required for inundation depth estimation",
                severity=0.85 if strict else 0.5,
            )]
        return []

    def _validate_forecast(
        self,
        context: AgentContext,
        inputs: FloodInputs,
        strict: bool,
    ) -> list[ValidationIssue]:
        has_forecast = (
            inputs.forecast_available
            or bool(context.forecast.references)
            or bool(context.forecast.payload)
            or inputs.rainfall.forecast_24h_mm is not None
        )
        if not has_forecast:
            return [ValidationIssue(
                category=ValidationCategory.FORECAST_CONSISTENCY,
                field="forecast",
                message="Forecast data not available for forward-looking assessment",
                severity=0.7 if strict else 0.4,
            )]
        return []

    def _validate_climate_state(
        self,
        context: AgentContext,
        strict: bool,
    ) -> list[ValidationIssue]:
        if not context.climate_state:
            return [ValidationIssue(
                category=ValidationCategory.CLIMATE_CONSISTENCY,
                field="climate_state",
                message="Climate state not attached to request",
                severity=0.75 if strict else 0.45,
            )]
        return []

    def _validate_digital_twin(
        self,
        context: AgentContext,
        inputs: FloodInputs,
        strict: bool,
    ) -> list[ValidationIssue]:
        has_twin = (
            inputs.digital_twin_available
            or bool(context.digital_twin_state)
            or context.climate_state is not None and context.climate_state.digital_twin is not None
        )
        if not has_twin:
            return [ValidationIssue(
                category=ValidationCategory.REQUIRED_INPUTS,
                field="digital_twin",
                message="Digital twin state not available",
                severity=0.6 if strict else 0.35,
            )]
        return []

    def _validate_tool_outputs(self, tool_results: list[ToolResult]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for result in tool_results:
            if not result.success:
                issues.append(ValidationIssue(
                    category=ValidationCategory.TOOL_OUTPUTS,
                    field=result.tool_name,
                    message=f"Flood tool '{result.tool_name}' failed: {result.error}",
                    severity=0.65,
                ))
        return issues
