"""Tests for state manager and workflow monitor."""

import pytest

from backend.agents.state.workflow_state import create_initial_workflow_state
from backend.agents.supervisor.execution_context import (
    ExecutionPlan,
    ExecutionResult,
    IntentClassification,
    SupervisorIntent,
)
from backend.agents.supervisor.state_manager import StateManager
from backend.agents.supervisor.workflow_monitor import WorkflowMonitor
from backend.utils.enums import AgentStatus


def test_state_manager_classification() -> None:
    sm = StateManager()
    state = create_initial_workflow_state()
    classification = IntentClassification(
        intent=SupervisorIntent.FORECAST,
        confidence=0.9,
        raw_query="forecast",
    )
    update = sm.apply_classification(state, classification)
    assert update["metadata"][StateManager.META_INTENT] == "forecast"


def test_state_manager_plan_tracking() -> None:
    sm = StateManager()
    state = create_initial_workflow_state()
    plan = ExecutionPlan(intent=SupervisorIntent.ALERT, query="alert test")
    update = sm.apply_plan(state, plan)
    assert update["metadata"][StateManager.META_PENDING_NODES] == []


def test_workflow_monitor_metrics() -> None:
    monitor = WorkflowMonitor()
    monitor.start_execution()
    monitor.record_supervisor_start("simulation_supervisor")
    monitor.record_supervisor_end("simulation_supervisor", duration_ms=100.0, success=True)
    monitor.record_memory_retrieval(2)
    metrics = monitor.get_metrics()
    assert metrics.supervisor_count == 1
    assert metrics.memory_retrieval_count == 2
    assert metrics.execution_duration_ms >= 0
