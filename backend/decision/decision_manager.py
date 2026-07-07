"""Central decision management API."""

from __future__ import annotations

import asyncio
import heapq
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from backend.decision.decision_actions import DecisionAction
from backend.decision.decision_constraints import DecisionConstraints
from backend.decision.decision_context import DecisionContext, ScenarioContext
from backend.decision.decision_priority import (
    DecisionPriority,
    PriorityContext,
    compare_priority,
    priority_from_label,
)
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.decision.decision_serializer import DecisionSerializer
from backend.decision.decision_types import (
    RISK_LEVEL_ORDER,
    DecisionStatus,
    DecisionType,
    Objective,
    RiskAssessment,
    RiskLevel,
)
from backend.decision.decision_validator import DecisionValidator, ValidationResult
from backend.config.logger import get_logger

logger = get_logger(__name__)


@dataclass(order=True)
class _QueuedDecision:
    """Internal queue entry ordered by priority (negated for max-heap)."""

    sort_key: tuple[int, float, str] = field(compare=True)
    request: DecisionRequest = field(compare=False)


class DecisionComparison(BaseModel):
    """Result of comparing two decision requests."""

    decision_id_a: str
    decision_id_b: str
    priority_delta: int
    confidence_delta: float
    risk_delta: float
    same_type: bool
    same_agent: bool
    higher_priority: str
    higher_confidence: str
    higher_risk: str


class DecisionManager:
    """
    Central API for creating, validating, serializing, merging, comparing,
    queuing, and prioritizing unified decision requests.
    """

    def __init__(
        self,
        *,
        validator: DecisionValidator | None = None,
        serializer: DecisionSerializer | None = None,
    ) -> None:
        self._validator = validator or DecisionValidator()
        self._serializer = serializer or DecisionSerializer()
        self._queue: list[_QueuedDecision] = []
        self._requests: dict[str, DecisionRequest] = {}
        self._responses: dict[str, DecisionResponse] = {}
        self._lock = asyncio.Lock()

    @property
    def validator(self) -> DecisionValidator:
        return self._validator

    @property
    def serializer(self) -> DecisionSerializer:
        return self._serializer

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(
        self,
        *,
        agent_id: str,
        decision_type: DecisionType,
        objectives: list[Objective],
        possible_actions: list[DecisionAction],
        constraints: DecisionConstraints | None = None,
        context: DecisionContext | None = None,
        risk: RiskAssessment | None = None,
        priority: DecisionPriority = DecisionPriority.NORMAL,
        confidence: float = 0.5,
        expected_reward: float | None = None,
        need_simulation: bool = False,
        need_other_agents: list[str] | None = None,
        need_human: bool = False,
        need_rl: bool = False,
        rationale: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        validate: bool = True,
        strict: bool = False,
    ) -> DecisionRequest:
        request = DecisionRequest(
            agent_id=agent_id,
            decision_type=decision_type,
            priority=priority,
            context=context or DecisionContext(),
            objectives=objectives,
            constraints=constraints or DecisionConstraints(),
            possible_actions=possible_actions,
            risk=risk or RiskAssessment(),
            confidence=confidence,
            expected_reward=expected_reward,
            need_simulation=need_simulation,
            need_other_agents=list(need_other_agents or []),
            need_human=need_human,
            need_rl=need_rl,
            rationale=list(rationale or []),
            metadata=dict(metadata or {}),
            status=DecisionStatus.PENDING,
        )
        if validate:
            self.validate(request, strict=strict)
        self._requests[request.decision_id] = request
        logger.debug(
            "decision_created",
            decision_id=request.decision_id,
            agent_id=agent_id,
            decision_type=decision_type.value,
        )
        return request

    def create_from_builder(
        self,
        *,
        agent_id: str,
        decision_type: DecisionType,
        scenario_name: str,
        region_id: str | None = None,
        objectives: list[str],
        actions: list[tuple[str, float, float]],
        priority_label: str = "normal",
        confidence: float = 0.6,
        risk_level: RiskLevel = RiskLevel.MODERATE,
        need_rl: bool = False,
        need_simulation: bool = False,
        need_other_agents: list[str] | None = None,
        validate: bool = True,
    ) -> DecisionRequest:
        """Convenience builder for agents to produce uniform decision requests."""
        objective_models = [
            Objective(objective_id=f"obj_{i}", description=desc, weight=1.0 / len(objectives))
            for i, desc in enumerate(objectives)
        ]
        action_models = [
            DecisionAction(
                description=desc,
                cost=cost,
                expected_benefit=benefit,
                risk=risk_level,
            )
            for desc, cost, benefit in actions
        ]
        context = DecisionContext(
            scenario=ScenarioContext(
                name=scenario_name,
                region_id=region_id,
            ),
        )

        return self.create(
            agent_id=agent_id,
            decision_type=decision_type,
            objectives=objective_models,
            possible_actions=action_models,
            context=context,
            risk=RiskAssessment(level=risk_level, score=0.5),
            priority=priority_from_label(priority_label),
            confidence=confidence,
            need_rl=need_rl,
            need_simulation=need_simulation,
            need_other_agents=need_other_agents,
            validate=validate,
        )

    # ------------------------------------------------------------------
    # Validate / Serialize
    # ------------------------------------------------------------------

    def validate(
        self,
        request: DecisionRequest,
        *,
        strict: bool = False,
    ) -> ValidationResult:
        return self._validator.validate_request(request, strict=strict)

    def validate_response(
        self,
        response: DecisionResponse,
        request: DecisionRequest,
        *,
        strict: bool = False,
    ) -> ValidationResult:
        return self._validator.validate_response(response, request, strict=strict)

    def serialize_json(self, model: DecisionRequest | DecisionResponse) -> str:
        return self._serializer.to_json(model)

    def deserialize_request_json(self, data: str) -> DecisionRequest:
        return self._serializer.from_json(data, DecisionRequest)

    def deserialize_response_json(self, data: str) -> DecisionResponse:
        return self._serializer.from_json(data, DecisionResponse)

    def to_db_record(self, model: DecisionRequest | DecisionResponse) -> dict[str, Any]:
        if isinstance(model, DecisionRequest):
            return self._serializer.request_to_db_record(model)
        return self._serializer.response_to_db_record(model)

    def from_db_record(self, record: dict[str, Any]) -> DecisionRequest | DecisionResponse:
        record_type = record.get("record_type", "")
        if record_type == "decision_response" or record.get("table") == DecisionSerializer.DB_RESPONSE_TABLE:
            return self._serializer.response_from_db_record(record)
        return self._serializer.request_from_db_record(record)

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    def merge(
        self,
        requests: list[DecisionRequest],
        *,
        agent_id: str = "decision_orchestrator",
        decision_type: DecisionType = DecisionType.GENERAL,
    ) -> DecisionRequest:
        """Merge multiple agent decision requests into a single unified request."""
        if not requests:
            raise ValueError("Cannot merge empty request list")

        merged_objectives: list[Objective] = []
        merged_actions: list[DecisionAction] = []
        merged_agents: list[str] = []
        merged_rationale: list[str] = []
        seen_obj_ids: set[str] = set()
        seen_action_ids: set[str] = set()

        max_priority = DecisionPriority.DEFERRED
        max_risk = RiskLevel.NEGLIGIBLE
        max_risk_score = 0.0
        total_confidence = 0.0
        need_sim = False
        need_human = False
        need_rl = False

        for req in requests:
            if compare_priority(req.priority, max_priority) > 0:
                max_priority = req.priority
            if RISK_LEVEL_ORDER[req.risk.level] > RISK_LEVEL_ORDER[max_risk]:
                max_risk = req.risk.level
            max_risk_score = max(max_risk_score, req.risk.score)
            total_confidence += req.confidence
            need_sim = need_sim or req.need_simulation
            need_human = need_human or req.need_human
            need_rl = need_rl or req.need_rl
            merged_agents.extend(req.need_other_agents)
            merged_rationale.extend(req.rationale)

            for obj in req.objectives:
                if obj.objective_id not in seen_obj_ids:
                    merged_objectives.append(obj)
                    seen_obj_ids.add(obj.objective_id)

            for action in req.possible_actions:
                if action.action_id not in seen_action_ids:
                    merged_actions.append(action)
                    seen_action_ids.add(action.action_id)

        avg_confidence = total_confidence / len(requests)
        primary_context = requests[0].context

        merged = DecisionRequest(
            decision_id=str(uuid4()),
            agent_id=agent_id,
            decision_type=decision_type,
            priority=max_priority,
            context=primary_context,
            objectives=merged_objectives,
            constraints=requests[0].constraints,
            possible_actions=merged_actions,
            risk=RiskAssessment(
                level=max_risk,
                score=max_risk_score,
                factors=[f"merged_from_{len(requests)}_requests"],
            ),
            confidence=round(avg_confidence, 4),
            need_simulation=need_sim,
            need_other_agents=list(dict.fromkeys(merged_agents)),
            need_human=need_human,
            need_rl=need_rl,
            rationale=merged_rationale,
            metadata={"merged_from": [r.decision_id for r in requests]},
            status=DecisionStatus.PENDING,
        )
        self._requests[merged.decision_id] = merged
        logger.info(
            "decisions_merged",
            merged_id=merged.decision_id,
            source_count=len(requests),
        )
        return merged

    # ------------------------------------------------------------------
    # Compare
    # ------------------------------------------------------------------

    def compare(self, a: DecisionRequest, b: DecisionRequest) -> DecisionComparison:
        priority_delta = compare_priority(a.priority, b.priority)
        confidence_delta = a.confidence - b.confidence
        risk_delta = a.risk.score - b.risk.score

        return DecisionComparison(
            decision_id_a=a.decision_id,
            decision_id_b=b.decision_id,
            priority_delta=priority_delta,
            confidence_delta=confidence_delta,
            risk_delta=risk_delta,
            same_type=a.decision_type == b.decision_type,
            same_agent=a.agent_id == b.agent_id,
            higher_priority=a.decision_id if priority_delta >= 0 else b.decision_id,
            higher_confidence=a.decision_id if confidence_delta >= 0 else b.decision_id,
            higher_risk=a.decision_id if risk_delta >= 0 else b.decision_id,
        )

    # ------------------------------------------------------------------
    # Queue / Prioritize
    # ------------------------------------------------------------------

    async def queue(self, request: DecisionRequest) -> None:
        """Add a validated decision request to the priority queue."""
        self.validate(request)
        async with self._lock:
            request.status = DecisionStatus.QUEUED
            request.mark_updated()
            entry = _QueuedDecision(
                sort_key=(-int(request.priority), -request.confidence, request.decision_id),
                request=request,
            )
            heapq.heappush(self._queue, entry)
            self._requests[request.decision_id] = request
        logger.debug("decision_queued", decision_id=request.decision_id)

    async def dequeue(self) -> DecisionRequest | None:
        """Remove and return the highest-priority queued decision."""
        async with self._lock:
            if not self._queue:
                return None
            entry = heapq.heappop(self._queue)
            entry.request.status = DecisionStatus.PROCESSING
            entry.request.mark_updated()
            return entry.request

    async def queue_size(self) -> int:
        async with self._lock:
            return len(self._queue)

    def prioritize(
        self,
        request: DecisionRequest,
        priority_context: PriorityContext | None = None,
    ) -> DecisionPriority:
        """Resolve effective priority for a decision request."""
        ctx = priority_context or PriorityContext(base_priority=request.priority)
        resolved = ctx.resolve()
        request.priority = resolved
        request.mark_updated()
        return resolved

    def store_response(self, response: DecisionResponse) -> None:
        self._responses[response.response_id] = response
        if response.decision_id in self._requests:
            req = self._requests[response.decision_id]
            req.status = response.status
            req.mark_updated()

    def get_request(self, decision_id: str) -> DecisionRequest | None:
        return self._requests.get(decision_id)

    def get_response(self, response_id: str) -> DecisionResponse | None:
        return self._responses.get(response_id)

    def list_requests(
        self,
        *,
        decision_type: DecisionType | None = None,
        status: DecisionStatus | None = None,
    ) -> list[DecisionRequest]:
        results = list(self._requests.values())
        if decision_type:
            results = [r for r in results if r.decision_type == decision_type]
        if status:
            results = [r for r in results if r.status == status]
        return sorted(results, key=lambda r: (-int(r.priority), -r.confidence))

    async def clear_queue(self) -> int:
        async with self._lock:
            count = len(self._queue)
            self._queue.clear()
            return count
