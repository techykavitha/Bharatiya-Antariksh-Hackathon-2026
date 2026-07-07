"""Pydantic models for explanation inputs and structured outputs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.agents.specialized.agent_reasoning import ReasoningResult
from backend.agents.specialized.agent_reflection import ReflectionResult
from backend.agents.specialized.agent_validator import ValidationResult as AgentValidationResult
from backend.agents.schemas.response import ToolOutputRecord
from backend.agents.tools.abstract_tool import ToolResult
from backend.decision.decision_actions import ActionRanking, DecisionAction, RejectedAction
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.xai.explanation_models import (
    ConfidenceDimension,
    CounterfactualType,
    EvidenceSource,
    ExplanationType,
    UncertaintyDimension,
)


class ExplanationInput(BaseModel):
    """
    Unified input bundle for the Explainability Framework.

    Specialized agents and the RL service pass pipeline artifacts without
    depending on agent-specific report schemas.
    """

    request_id: str
    agent_id: str
    explanation_type: ExplanationType = ExplanationType.FULL_PIPELINE
    query: str = ""
    reasoning: ReasoningResult | None = None
    tool_results: list[ToolResult] = Field(default_factory=list)
    tool_output_records: list[ToolOutputRecord] = Field(default_factory=list)
    reflection: ReflectionResult | None = None
    validation: AgentValidationResult | None = None
    decision_request: DecisionRequest | None = None
    decision_response: DecisionResponse | None = None
    memory_references: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceStep(BaseModel):
    """Enriched reasoning trace step for explainability."""

    step_index: int = Field(ge=0)
    phase: str
    content: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    duration_ms: float = Field(default=0.0, ge=0.0)
    stage: str | None = None
    supporting_tools: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReasoningTraceReport(BaseModel):
    """Structured reasoning trace with narrative."""

    steps: list[TraceStep] = Field(default_factory=list)
    narrative: list[str] = Field(default_factory=list)
    stage_sequence: list[str] = Field(default_factory=list)
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    total_duration_ms: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    """Single piece of supporting evidence."""

    evidence_id: str = Field(default_factory=lambda: str(uuid4()))
    source: EvidenceSource
    label: str
    value: Any = None
    unit: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    provenance: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceBundle(BaseModel):
    """Collected evidence supporting a recommendation."""

    items: list[EvidenceItem] = Field(default_factory=list)
    climate_variables: list[EvidenceItem] = Field(default_factory=list)
    forecast_outputs: list[EvidenceItem] = Field(default_factory=list)
    historical_events: list[EvidenceItem] = Field(default_factory=list)
    digital_twin_state: list[EvidenceItem] = Field(default_factory=list)
    memory_references: list[str] = Field(default_factory=list)
    tool_evidence: list[EvidenceItem] = Field(default_factory=list)
    reasoning_evidence: list[EvidenceItem] = Field(default_factory=list)
    summary: str = ""


class ConfidenceComponent(BaseModel):
    """Single confidence dimension score."""

    dimension: ConfidenceDimension
    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(default=0.2, ge=0.0, le=1.0)
    rationale: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConfidenceEstimate(BaseModel):
    """Aggregated confidence assessment."""

    overall: float = Field(default=0.0, ge=0.0, le=1.0)
    components: list[ConfidenceComponent] = Field(default_factory=list)
    model_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    data_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    forecast_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    tool_consistency: float = Field(default=0.0, ge=0.0, le=1.0)
    historical_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""


class UncertaintyComponent(BaseModel):
    """Single uncertainty dimension score."""

    dimension: UncertaintyDimension
    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(default=0.25, ge=0.0, le=1.0)
    description: str = ""
    mitigations: list[str] = Field(default_factory=list)


class UncertaintyEstimate(BaseModel):
    """Aggregated uncertainty assessment."""

    overall: float = Field(default=0.0, ge=0.0, le=1.0)
    components: list[UncertaintyComponent] = Field(default_factory=list)
    forecast_uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    missing_data: float = Field(default=0.0, ge=0.0, le=1.0)
    model_uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    simulation_uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""


class AlternativeActionExplanation(BaseModel):
    """Explanation for a non-selected action."""

    action: DecisionAction
    rank: int | None = None
    score: float | None = None
    expected_reward: float | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = ""
    why_not_chosen: str = ""
    trade_offs: list[str] = Field(default_factory=list)


class RejectedActionExplanation(BaseModel):
    """Explanation for a constraint-rejected action."""

    action_id: str
    description: str = ""
    reason: str
    constraint_violated: str | None = None
    score: float | None = None


class AlternativeActionsAnalysis(BaseModel):
    """Analysis of alternative and rejected actions."""

    chosen_action: DecisionAction | None = None
    alternatives: list[AlternativeActionExplanation] = Field(default_factory=list)
    rejected: list[RejectedActionExplanation] = Field(default_factory=list)
    ranking: list[ActionRanking] = Field(default_factory=list)
    summary: str = ""


class CounterfactualScenario(BaseModel):
    """A what-if scenario comparing an alternative path."""

    scenario_id: str = Field(default_factory=lambda: str(uuid4()))
    counterfactual_type: CounterfactualType
    title: str
    description: str
    assumed_action: DecisionAction | None = None
    baseline_outcome: str = ""
    counterfactual_outcome: str = ""
    outcome_delta: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    assumptions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CounterfactualAnalysis(BaseModel):
    """Counterfactual what-if analysis bundle."""

    question: str = "What if another action had been selected?"
    scenarios: list[CounterfactualScenario] = Field(default_factory=list)
    summary: str = ""


class ExplainabilityReport(BaseModel):
    """
    Standardized explainability report for any specialized agent or RL output.

  Every recommendation should be accompanied by this schema.
    """

    explanation_id: str = Field(default_factory=lambda: str(uuid4()))
    request_id: str
    agent_id: str
    explanation_type: ExplanationType = ExplanationType.FULL_PIPELINE

    executive_summary: str = ""
    reasoning_trace: ReasoningTraceReport = Field(default_factory=ReasoningTraceReport)
    evidence: EvidenceBundle = Field(default_factory=EvidenceBundle)
    confidence: ConfidenceEstimate = Field(default_factory=ConfidenceEstimate)
    uncertainty: UncertaintyEstimate = Field(default_factory=UncertaintyEstimate)
    alternatives: AlternativeActionsAnalysis = Field(default_factory=AlternativeActionsAnalysis)
    counterfactuals: CounterfactualAnalysis = Field(default_factory=CounterfactualAnalysis)

    chosen_action_summary: str = ""
    recommendations: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    processing_time_ms: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence.overall >= 0.7 and self.uncertainty.overall <= 0.4

    def to_audit_trace(self) -> list[str]:
        """Flatten key explanation lines for agent response reasoning_trace."""
        lines = [self.executive_summary]
        lines.extend(self.reasoning_trace.narrative[:5])
        if self.chosen_action_summary:
            lines.append(self.chosen_action_summary)
        lines.extend(self.caveats[:3])
        return [line for line in lines if line]
