"""Disaster response report generation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.agents.schemas.response import ToolOutputRecord
from backend.agents.specialized.agent_context import AgentContext
from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.specialized.agent_reflection import ReflectionResult
from backend.agents.specialized.agent_validator import ValidationResult
from backend.agents.specialized.disaster_response.disaster_context import (
    DisasterInputs,
    EvacuationStrategy,
    MedicalSupportPlan,
    PriorityRanking,
    RecoveryPriority,
    ResourceRequirement,
)
from backend.agents.specialized.disaster_response.disaster_metrics import DisasterExecutionMetrics
from backend.agents.specialized.disaster_response.disaster_models import EmergencyPriority, HazardType
from backend.agents.tools.abstract_tool import ToolResult
from backend.config.logger import get_logger
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.xai.explanation_report import ExplainabilityReport

logger = get_logger(__name__)


class RequiredAction(BaseModel):
    """Operational action item for disaster response."""

    action_id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    priority: str = "normal"
    category: str = "operational"
    target_agent: str | None = None


class DisasterResponseReport(BaseModel):
    """Professional multi-hazard disaster response coordination report."""

    report_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    request_id: str
    executive_summary: str = ""
    hazard_overview: list[dict[str, Any]] = Field(default_factory=list)
    priority_ranking: list[PriorityRanking] = Field(default_factory=list)
    emergency_priority: EmergencyPriority = EmergencyPriority.ROUTINE
    affected_population: int = Field(default=0, ge=0)
    vulnerable_population: int = Field(default=0, ge=0)
    critical_infrastructure: list[dict[str, Any]] = Field(default_factory=list)
    emergency_resources: list[ResourceRequirement] = Field(default_factory=list)
    evacuation_strategy: EvacuationStrategy = Field(default_factory=EvacuationStrategy)
    medical_support: MedicalSupportPlan = Field(default_factory=MedicalSupportPlan)
    recovery_priorities: list[RecoveryPriority] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    required_actions: list[RequiredAction] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    references: list[str] = Field(default_factory=list)
    tool_outputs: list[ToolOutputRecord] = Field(default_factory=list)
    decision_request: DecisionRequest | None = None
    rl_response: DecisionResponse | None = None
    explainability_report: ExplainabilityReport | None = None
    chosen_action: str | None = None
    need_rl: bool = False
    need_simulation: bool = False
    need_other_agents: list[str] = Field(default_factory=list)
    alternative_plans: list[str] = Field(default_factory=list)
    counterfactuals: list[str] = Field(default_factory=list)
    metrics: DisasterExecutionMetrics | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DisasterReportBuilder:
    """Assembles a DisasterResponseReport from analysis artifacts."""

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id

    def build(
        self,
        context: AgentContext,
        reasoning: ReasoningResult,
        tool_results: list[ToolResult],
        validation: ValidationResult,
        decision: DecisionRequest,
        reflection: ReflectionResult | None = None,
        rl_response: DecisionResponse | None = None,
        explainability: ExplainabilityReport | None = None,
    ) -> DisasterResponseReport:
        inputs = self._resolve_inputs(context)
        signals = reasoning.metadata.get("disaster_signals", {})
        outputs = self._index_outputs(tool_results)
        rankings = [
            PriorityRanking.model_validate(r)
            for r in reasoning.metadata.get("priority_rankings", [])
            if isinstance(r, dict)
        ]
        resources = [
            ResourceRequirement.model_validate(r)
            for r in reasoning.metadata.get("resource_requirements", [])
            if isinstance(r, dict)
        ]
        evacuation = EvacuationStrategy.model_validate(
            reasoning.metadata.get("evacuation_strategy", {}),
        )
        medical = MedicalSupportPlan.model_validate(
            reasoning.metadata.get("medical_support", {}),
        )
        recovery = [
            RecoveryPriority.model_validate(r)
            for r in reasoning.metadata.get("recovery_priorities", [])
            if isinstance(r, dict)
        ]

        pop_out = outputs.get("population_tool", {})
        affected = int(pop_out.get("total_affected_population", 0))
        vulnerable = int(pop_out.get("vulnerable_population", 0))
        infra = outputs.get("critical_infrastructure_tool", {}).get("infrastructure_assets", [])
        emergency_priority = self._resolve_emergency_priority(decision, signals)
        recommendations = self._extract_recommendations(reasoning)
        evidence = self._build_evidence(tool_results, reasoning, inputs)
        hazard_overview = self._build_hazard_overview(inputs)
        required_actions = self._build_required_actions(decision)
        alternatives, counterfactuals = self._extract_xai(explainability)
        summary = self._build_summary(inputs, rankings, emergency_priority, affected, decision)

        chosen = None
        if rl_response and rl_response.chosen_action:
            chosen = rl_response.chosen_action.description

        return DisasterResponseReport(
            agent_id=self._agent_id,
            request_id=context.request_id,
            executive_summary=summary,
            hazard_overview=hazard_overview,
            priority_ranking=rankings,
            emergency_priority=emergency_priority,
            affected_population=affected,
            vulnerable_population=vulnerable,
            critical_infrastructure=[i for i in infra if isinstance(i, dict)],
            emergency_resources=resources,
            evacuation_strategy=evacuation,
            medical_support=medical,
            recovery_priorities=recovery,
            recommendations=recommendations,
            required_actions=required_actions,
            reasoning=[s.content for s in reasoning.steps],
            evidence=evidence,
            confidence=reasoning.overall_confidence,
            references=self._build_references(inputs),
            tool_outputs=[
                ToolOutputRecord(tool_name=r.tool_name, output=r.output or {}, success=r.success)
                for r in tool_results
            ],
            decision_request=decision,
            rl_response=rl_response,
            explainability_report=explainability,
            chosen_action=chosen,
            need_rl=decision.need_rl,
            need_simulation=decision.need_simulation,
            need_other_agents=list(decision.need_other_agents),
            alternative_plans=alternatives,
            counterfactuals=counterfactuals,
            metadata={
                "validation_valid": validation.valid,
                "disaster_signals": signals,
                "reflection_confidence": reflection.confidence if reflection else None,
                "compound_disaster": signals.get("compound_disaster", False),
            },
        )

    def _resolve_inputs(self, context: AgentContext) -> DisasterInputs:
        stored = context.metadata.get("disaster_inputs")
        if isinstance(stored, DisasterInputs):
            return stored
        return DisasterInputs.from_request_context(context.request.context)

    def _index_outputs(self, tool_results: list[ToolResult]) -> dict[str, Any]:
        return {r.tool_name: r.output for r in tool_results if r.success and r.output}

    def _resolve_emergency_priority(
        self, decision: DecisionRequest, signals: dict[str, Any],
    ) -> EmergencyPriority:
        raw = decision.metadata.get("emergency_priority")
        if raw:
            try:
                return EmergencyPriority(raw)
            except ValueError:
                pass
        composite = float(signals.get("composite_priority_score", 0.0))
        if composite >= 0.85:
            return EmergencyPriority.CATASTROPHIC
        if composite >= 0.7:
            return EmergencyPriority.SEVERE
        if composite >= 0.55:
            return EmergencyPriority.HIGH
        if composite >= 0.35:
            return EmergencyPriority.ELEVATED
        return EmergencyPriority.ROUTINE

    def _build_hazard_overview(self, inputs: DisasterInputs) -> list[dict[str, Any]]:
        return [
            {
                "agent_id": h.agent_id,
                "hazard_type": h.hazard_type.value,
                "severity": h.severity,
                "risk_level": h.risk_level,
                "confidence": h.confidence,
                "affected_population": h.affected_population,
                "summary": h.summary,
                "consulted_live": h.consulted_live,
            }
            for h in inputs.hazard_agent_outputs.values()
        ]

    def _extract_recommendations(self, reasoning: ReasoningResult) -> list[str]:
        for step in reversed(reasoning.steps):
            recs = step.metadata.get("recommendations")
            if recs:
                return list(recs)
        return [s.content for s in reasoning.steps if s.phase.value in ("act", "verify")]

    def _build_evidence(
        self,
        tool_results: list[ToolResult],
        reasoning: ReasoningResult,
        inputs: DisasterInputs,
    ) -> list[str]:
        evidence: list[str] = []
        for h in inputs.hazard_agent_outputs.values():
            evidence.append(
                f"hazard:{h.agent_id} severity={h.severity} confidence={h.confidence:.2f}",
            )
        for r in tool_results:
            if r.success and r.output:
                evidence.append(f"{r.tool_name}: {list(r.output.keys())[:4]}")
        evidence.append(f"reasoning_confidence={reasoning.overall_confidence:.2f}")
        return evidence

    def _build_required_actions(self, decision: DecisionRequest) -> list[RequiredAction]:
        actions: list[RequiredAction] = []
        for action in decision.possible_actions:
            actions.append(RequiredAction(
                description=action.description,
                priority=decision.priority.name.lower(),
                category=action.category or "operational",
            ))
        return actions

    def _extract_xai(
        self, explainability: ExplainabilityReport | None,
    ) -> tuple[list[str], list[str]]:
        if not explainability:
            return [], []
        alternatives = [
            (alt.action.description if alt.action else "") or alt.rationale or alt.why_not_chosen
            for alt in explainability.alternatives.alternatives
            if (alt.action and alt.action.description) or alt.rationale or alt.why_not_chosen
        ]
        counterfactuals = [
            scenario.description or scenario.title
            for scenario in explainability.counterfactuals.scenarios
            if scenario.description or scenario.title
        ]
        if explainability.reasoning_trace.narrative and not alternatives:
            alternatives = explainability.reasoning_trace.narrative[:2]
        return alternatives, counterfactuals

    def _build_references(self, inputs: DisasterInputs) -> list[str]:
        refs = [f"region:{inputs.region_id or 'unknown'}"]
        for agent_id, h in inputs.hazard_agent_outputs.items():
            refs.append(f"hazard:{agent_id}:{h.hazard_type.value}")
        return refs

    def _build_summary(
        self,
        inputs: DisasterInputs,
        rankings: list[PriorityRanking],
        emergency: EmergencyPriority,
        affected: int,
        decision: DecisionRequest,
    ) -> str:
        region = inputs.region_id or "target region"
        hazard_count = len(inputs.hazard_agent_outputs)
        top = rankings[0].hazard_type.value if rankings else HazardType.UNKNOWN.value
        return (
            f"Multi-hazard emergency response plan for {region}: "
            f"{hazard_count} active hazard(s), top priority {top}, "
            f"emergency level {emergency.value}. "
            f"Estimated affected population {affected:,}. "
            f"{len(decision.possible_actions)} response actions evaluated."
        )
