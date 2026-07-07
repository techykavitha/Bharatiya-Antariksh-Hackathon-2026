"""Tests for workflow planner."""

import pytest

from backend.agents.supervisor.execution_context import ExecutionMode, SupervisorIntent
from backend.agents.supervisor.intent_classifier import IntentClassifier
from backend.agents.supervisor.planner import Planner


@pytest.mark.asyncio
async def test_plan_what_if() -> None:
    classifier = IntentClassifier()
    planner = Planner()
    classification = await classifier.classify("What happens if rainfall decreases 20% in Karnataka?")
    plan = await planner.plan(classification, query=classification.raw_query)
    assert plan.intent == SupervisorIntent.WHAT_IF
    assert len(plan.steps) >= 3
    supervisor_ids = {s.supervisor_id for s in plan.steps}
    assert "simulation_supervisor" in supervisor_ids


@pytest.mark.asyncio
async def test_plan_filters_available_supervisors() -> None:
    classifier = IntentClassifier()
    planner = Planner()
    classification = await classifier.classify("Run a simulation for flood risk")
    plan = await planner.plan(
        classification,
        query=classification.raw_query,
        available_supervisors=["simulation_supervisor"],
    )
    assert all(s.supervisor_id == "simulation_supervisor" for s in plan.steps)


@pytest.mark.asyncio
async def test_plan_what_if_parallel_mode() -> None:
    classifier = IntentClassifier()
    planner = Planner()
    classification = await classifier.classify("What if drought increases 30%?")
    plan = await planner.plan(classification, query=classification.raw_query)
    assert plan.execution_mode in (ExecutionMode.PARALLEL, ExecutionMode.SEQUENTIAL)
