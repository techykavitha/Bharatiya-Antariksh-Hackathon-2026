"""Disaster response input and output validation."""

from __future__ import annotations

from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_validator import (
    AgentValidator,
    ValidationCategory,
    ValidationIssue,
    ValidationResult,
)
from backend.agents.specialized.disaster_response.disaster_context import DisasterInputs
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


class DisasterValidator:
    """Validates hazard outputs, forecast, climate state, and digital twin."""

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
        issues.extend(self._validate_hazard_outputs(inputs, strict))
        issues.extend(self._validate_forecast(context, inputs, strict))
        issues.extend(self._validate_climate_state(context, strict))
        issues.extend(self._validate_digital_twin(context, inputs, strict))
        issues.extend(self._validate_tool_outputs(tool_results))

        for issue in issues:
            context.add_validation_error(issue.message)

        blocking = [i for i in issues if i.severity >= 0.8]
        valid = len(blocking) == 0 if strict else len([i for i in issues if i.severity >= 0.9]) == 0
        return ValidationResult(valid=valid, issues=issues)

    def _resolve_inputs(self, context: AgentContext) -> DisasterInputs:
        stored = context.metadata.get("disaster_inputs")
        if isinstance(stored, DisasterInputs):
            return stored
        return DisasterInputs.from_request_context(context.request.context)

    def _validate_hazard_outputs(
        self, inputs: DisasterInputs, strict: bool,
    ) -> list[ValidationIssue]:
        if not inputs.hazard_agent_outputs:
            return [ValidationIssue(
                category=ValidationCategory.REQUIRED_INPUTS,
                field="hazard_agent_outputs",
                message="At least one hazard agent output required for coordination",
                severity=0.85 if strict else 0.55,
            )]
        invalid = [
            agent_id for agent_id, h in inputs.hazard_agent_outputs.items()
            if h.confidence <= 0 and not h.summary
        ]
        if invalid:
            return [ValidationIssue(
                category=ValidationCategory.TOOL_OUTPUTS,
                field="hazard_agent_outputs",
                message=f"Incomplete hazard outputs from: {', '.join(invalid)}",
                severity=0.6,
            )]
        return []

    def _validate_forecast(
        self, context: AgentContext, inputs: DisasterInputs, strict: bool,
    ) -> list[ValidationIssue]:
        has_forecast = inputs.forecast_available or bool(context.forecast.references)
        if not has_forecast:
            return [ValidationIssue(
                category=ValidationCategory.FORECAST_CONSISTENCY,
                field="forecast",
                message="Forecast not available for multi-hazard planning horizon",
                severity=0.65 if strict else 0.35,
            )]
        return []

    def _validate_climate_state(self, context: AgentContext, strict: bool) -> list[ValidationIssue]:
        if not context.climate_state:
            return [ValidationIssue(
                category=ValidationCategory.CLIMATE_CONSISTENCY,
                field="climate_state",
                message="Climate state not attached to request",
                severity=0.7 if strict else 0.4,
            )]
        return []

    def _validate_digital_twin(
        self, context: AgentContext, inputs: DisasterInputs, strict: bool,
    ) -> list[ValidationIssue]:
        has_twin = inputs.digital_twin_available or bool(context.digital_twin_state)
        if not has_twin:
            return [ValidationIssue(
                category=ValidationCategory.REQUIRED_INPUTS,
                field="digital_twin",
                message="Digital twin state not available",
                severity=0.55 if strict else 0.3,
            )]
        return []

    def _validate_tool_outputs(self, tool_results: list[ToolResult]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for result in tool_results:
            if not result.success:
                issues.append(ValidationIssue(
                    category=ValidationCategory.TOOL_OUTPUTS,
                    field=result.tool_name,
                    message=f"Disaster tool '{result.tool_name}' failed: {result.error}",
                    severity=0.6,
                ))
        return issues
