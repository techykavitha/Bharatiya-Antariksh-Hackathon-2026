"""Water resource-specific input and output validation."""

from __future__ import annotations

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_validator import (
    AgentValidator,
    ValidationCategory,
    ValidationIssue,
    ValidationResult,
)
from backend.agents.specialized.water_resource.water_context import WaterInputs
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


class WaterValidator:
    """
    Validates water resource analysis prerequisites:
    reservoir, forecast, groundwater, climate state, and digital twin.
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

        issues.extend(self._validate_reservoir(inputs, tool_results, strict))
        issues.extend(self._validate_forecast(context, inputs, strict))
        issues.extend(self._validate_groundwater(inputs, tool_results, strict))
        issues.extend(self._validate_climate_state(context, strict))
        issues.extend(self._validate_digital_twin(context, inputs, strict))
        issues.extend(self._validate_tool_outputs(tool_results))

        for issue in issues:
            context.add_validation_error(issue.message)

        blocking = [i for i in issues if i.severity >= 0.8]
        valid = len(blocking) == 0 if strict else len([i for i in issues if i.severity >= 0.9]) == 0

        result = ValidationResult(valid=valid, issues=issues)
        logger.debug(
            "water_validation_completed",
            agent_id=self._agent_id,
            valid=valid,
            issues=len(issues),
        )
        return result

    def _resolve_inputs(self, context: AgentContext) -> WaterInputs:
        stored = context.metadata.get("water_inputs")
        if isinstance(stored, WaterInputs):
            return stored
        return WaterInputs.from_request_context(context.request.context)

    def _validate_reservoir(
        self,
        inputs: WaterInputs,
        tool_results: list[ToolResult],
        strict: bool,
    ) -> list[ValidationIssue]:
        has_data = (
            inputs.reservoir_available
            or inputs.reservoir.level_pct is not None
            or any(r.tool_name == "reservoir_tool" and r.success for r in tool_results)
        )
        if not has_data:
            return [ValidationIssue(
                category=ValidationCategory.REQUIRED_INPUTS,
                field="reservoir",
                message="Reservoir storage data is required for water resource analysis",
                severity=0.9 if strict else 0.65,
            )]
        return []

    def _validate_forecast(
        self,
        context: AgentContext,
        inputs: WaterInputs,
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
                message="Rainfall forecast not available for water availability projection",
                severity=0.7 if strict else 0.4,
            )]
        return []

    def _validate_groundwater(
        self,
        inputs: WaterInputs,
        tool_results: list[ToolResult],
        strict: bool,
    ) -> list[ValidationIssue]:
        has_gw = (
            inputs.groundwater_available
            or inputs.groundwater.depth_to_water_m is not None
            or any(r.tool_name == "groundwater_tool" and r.success for r in tool_results)
        )
        if not has_gw:
            return [ValidationIssue(
                category=ValidationCategory.REQUIRED_INPUTS,
                field="groundwater",
                message="Groundwater data not available for aquifer assessment",
                severity=0.75 if strict else 0.45,
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
        inputs: WaterInputs,
        strict: bool,
    ) -> list[ValidationIssue]:
        has_twin = (
            inputs.digital_twin_available
            or bool(context.digital_twin_state)
            or (
                context.climate_state is not None
                and context.climate_state.digital_twin is not None
            )
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
                    message=f"Water tool '{result.tool_name}' failed: {result.error}",
                    severity=0.65,
                ))
        return issues
