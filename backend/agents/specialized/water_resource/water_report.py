"""Water resource report generation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.agents.schemas.response import ToolOutputRecord
from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.specialized.agent_reflection import ReflectionResult
from backend.agents.specialized.water_resource.water_context import (
    DecisionRequest,
    ReservoirStatusReport,
    WaterAvailabilityEstimate,
    WaterInputs,
)
from backend.agents.specialized.water_resource.water_metrics import WaterExecutionMetrics
from backend.agents.specialized.water_resource.water_models import (
    ReleaseStrategy,
    ReservoirStatus,
    WaterStressLevel,
)
from backend.agents.specialized.water_resource.water_validator import ValidationResult
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


class RequiredAction(BaseModel):
    """Action required from downstream systems or agents."""

    action_id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    priority: str = "normal"
    target_agent: str | None = None
    category: str = "operational"


class DemandSummary(BaseModel):
    """Sector-wise water demand summary."""

    urban_m3d: float = Field(default=0.0, ge=0.0)
    agricultural_m3d: float = Field(default=0.0, ge=0.0)
    industrial_m3d: float = Field(default=0.0, ge=0.0)
    total_m3d: float = Field(default=0.0, ge=0.0)


class GroundwaterSummary(BaseModel):
    """Groundwater assessment summary."""

    depth_to_water_m: float = Field(default=0.0, ge=0.0)
    trend: str = "unknown"
    declining: bool = False
    sustainable: bool = True
    score: float = Field(default=0.5, ge=0.0, le=1.0)


class WaterResourceReport(BaseModel):
    """Professional water resource analysis report."""

    report_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    request_id: str
    executive_summary: str = ""
    reservoir_status: list[ReservoirStatusReport] = Field(default_factory=list)
    water_stress: WaterStressLevel = WaterStressLevel.NONE
    water_availability: WaterAvailabilityEstimate = Field(default_factory=WaterAvailabilityEstimate)
    groundwater: GroundwaterSummary = Field(default_factory=GroundwaterSummary)
    demand: DemandSummary = Field(default_factory=DemandSummary)
    release_strategy: ReleaseStrategy = ReleaseStrategy.HOLD
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    required_actions: list[RequiredAction] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    tool_outputs: list[ToolOutputRecord] = Field(default_factory=list)
    decision_request: DecisionRequest = Field(default_factory=DecisionRequest)
    need_rl: bool = False
    need_simulation: bool = False
    need_other_agents: list[str] = Field(default_factory=list)
    metrics: WaterExecutionMetrics | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_executive_text(self) -> str:
        return self.executive_summary


class WaterReportBuilder:
    """Assembles a ``WaterResourceReport`` from analysis artifacts."""

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id

    def build(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        tool_results: list[ToolResult],
        reflection: ReflectionResult,
        validation: ValidationResult,
        decision: DecisionRequest,
    ) -> WaterResourceReport:
        inputs = self._resolve_inputs(context)
        signals = reasoning.metadata.get("water_signals", {})
        outputs = self._index_outputs(tool_results)

        stress = WaterStressLevel(reasoning.metadata.get("stress_level", WaterStressLevel.NONE.value))
        availability = self._resolve_availability(reasoning)
        strategy = ReleaseStrategy(
            reasoning.metadata.get("release_strategy", ReleaseStrategy.HOLD.value),
        )
        reservoirs = self._build_reservoir_status(outputs, inputs)
        groundwater = self._build_groundwater_summary(outputs)
        demand = self._build_demand_summary(outputs)
        recommendations = self._extract_recommendations(reasoning)
        required_actions = self._build_required_actions(decision, reflection)
        confidence = reasoning.overall_confidence
        if not validation.valid:
            confidence = min(confidence, 0.5)

        summary = self._executive_summary(
            stress, availability, reservoirs, demand, strategy,
        )

        tool_records = [
            ToolOutputRecord(
                tool_name=r.tool_name,
                output=r.output,
                success=r.success,
                error=r.error,
                duration_ms=r.duration_ms,
            )
            for r in tool_results
        ]

        report = WaterResourceReport(
            agent_id=self._agent_id,
            request_id=context.request_id,
            executive_summary=summary,
            reservoir_status=reservoirs,
            water_stress=stress,
            water_availability=availability,
            groundwater=groundwater,
            demand=demand,
            release_strategy=strategy,
            confidence=confidence,
            reasoning=reasoning.trace,
            recommendations=recommendations,
            required_actions=required_actions,
            references=list(context.memory.references),
            tool_outputs=tool_records,
            decision_request=decision,
            need_rl=decision.need_rl,
            need_simulation=decision.need_simulation,
            need_other_agents=decision.suggested_agents,
            metadata={
                "validation_valid": validation.valid,
                "region_id": inputs.region_id,
                "basin_id": inputs.basin_id,
                "signals": signals,
            },
        )
        logger.info(
            "water_report_generated",
            agent_id=self._agent_id,
            stress_level=stress.value,
            availability_band=availability.band.value,
        )
        return report

    def _resolve_inputs(self, context: AgentContext) -> WaterInputs:
        stored = context.metadata.get("water_inputs")
        if isinstance(stored, WaterInputs):
            return stored
        return WaterInputs.from_request_context(context.request.context)

    def _index_outputs(self, results: list[ToolResult]) -> dict[str, Any]:
        return {
            r.tool_name: r.output
            for r in results
            if r.success and isinstance(r.output, dict)
        }

    def _resolve_availability(self, reasoning: ReasoningResult) -> WaterAvailabilityEstimate:
        raw = reasoning.metadata.get("availability")
        if isinstance(raw, dict):
            return WaterAvailabilityEstimate.model_validate(raw)
        if isinstance(raw, WaterAvailabilityEstimate):
            return raw
        return WaterAvailabilityEstimate()

    def _build_reservoir_status(
        self,
        outputs: dict[str, Any],
        inputs: WaterInputs,
    ) -> list[ReservoirStatusReport]:
        reservoir = outputs.get("reservoir_tool", {})
        if not reservoir:
            return []

        try:
            status = ReservoirStatus(reservoir.get("status", ReservoirStatus.UNKNOWN.value))
        except ValueError:
            status = ReservoirStatus.UNKNOWN

        try:
            release = ReleaseStrategy(reservoir.get("recommended_release", ReleaseStrategy.HOLD.value))
        except ValueError:
            release = ReleaseStrategy.HOLD

        return [
            ReservoirStatusReport(
                reservoir_id=inputs.reservoir.name or "primary_reservoir",
                name=reservoir.get("reservoir_name", "Primary Reservoir"),
                level_pct=float(reservoir.get("level_pct", 0.0)),
                status=status,
                live_storage_mcm=float(reservoir.get("live_storage_mcm", 0.0)),
                recommended_release=release,
                overflow_risk=bool(reservoir.get("overflow_risk")),
            ),
        ]

    def _build_groundwater_summary(self, outputs: dict[str, Any]) -> GroundwaterSummary:
        gw = outputs.get("groundwater_tool", {})
        if not gw:
            return GroundwaterSummary()
        return GroundwaterSummary(
            depth_to_water_m=float(gw.get("depth_to_water_m", 0.0)),
            trend=str(gw.get("trend", "unknown")),
            declining=bool(gw.get("declining")),
            sustainable=bool(gw.get("sustainable", True)),
            score=float(gw.get("groundwater_score", 0.5)),
        )

    def _build_demand_summary(self, outputs: dict[str, Any]) -> DemandSummary:
        demand = outputs.get("demand_tool", {})
        if not demand:
            return DemandSummary()
        return DemandSummary(
            urban_m3d=float(demand.get("urban_demand_m3d", 0.0)),
            agricultural_m3d=float(demand.get("agricultural_demand_m3d", 0.0)),
            industrial_m3d=float(demand.get("industrial_demand_m3d", 0.0)),
            total_m3d=float(demand.get("total_demand_m3d", 0.0)),
        )

    def _extract_recommendations(self, reasoning: ReasoningResult) -> list[str]:
        for step in reasoning.steps:
            recs = step.metadata.get("recommendations")
            if isinstance(recs, list) and recs:
                return [str(r) for r in recs]
        return ["Monitor water resources and update assessment as new data arrives"]

    def _build_required_actions(
        self,
        decision: DecisionRequest,
        reflection: ReflectionResult,
    ) -> list[RequiredAction]:
        actions: list[RequiredAction] = []
        if decision.need_flood_agent:
            actions.append(RequiredAction(
                description="Coordinate with flood agent for downstream impact assessment",
                priority="high",
                target_agent="flood_agent",
                category="coordination",
            ))
        if decision.need_agriculture_agent:
            actions.append(RequiredAction(
                description="Request agricultural water demand optimization",
                priority="normal",
                target_agent="agriculture_agent",
                category="demand",
            ))
        if decision.need_urban_planning_agent:
            actions.append(RequiredAction(
                description="Coordinate urban water supply planning",
                priority="normal",
                target_agent="urban_planning_agent",
                category="planning",
            ))
        if decision.need_disaster_agent:
            actions.append(RequiredAction(
                description="Activate disaster response for water scarcity",
                priority="high",
                target_agent="disaster_response_agent",
                category="emergency",
            ))
        if decision.need_simulation:
            actions.append(RequiredAction(
                description="Run basin-scale water allocation simulation",
                priority="normal",
                category="simulation",
            ))
        if decision.need_forecast_update:
            actions.append(RequiredAction(
                description="Refresh rainfall forecast for planning horizon",
                priority="normal",
                category="forecast",
            ))
        if decision.need_rl:
            actions.append(RequiredAction(
                description="Request RL policy for optimal reservoir release scheduling",
                priority="high",
                category="rl",
            ))
        return actions

    def _executive_summary(
        self,
        stress: WaterStressLevel,
        availability: WaterAvailabilityEstimate,
        reservoirs: list[ReservoirStatusReport],
        demand: DemandSummary,
        strategy: ReleaseStrategy,
    ) -> str:
        region = "target basin"
        if reservoirs:
            level = reservoirs[0].level_pct
            status = reservoirs[0].status.value
            reservoir_text = f"Primary reservoir at {level:.0f}% ({status}). "
        else:
            reservoir_text = ""

        return (
            f"Water resource assessment for {region}: {reservoir_text}"
            f"Water stress rated {stress.value}. "
            f"Availability: {availability.band.value} "
            f"(supply {availability.supply_m3d:.0f} m3/d vs demand {availability.demand_m3d:.0f} m3/d). "
            f"Total sector demand: {demand.total_m3d:.0f} m3/d. "
            f"Recommended release strategy: {strategy.value}."
        )
