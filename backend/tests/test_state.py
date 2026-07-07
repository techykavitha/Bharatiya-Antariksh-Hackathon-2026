"""Tests for LangGraph-compatible workflow state."""

from backend.agents.state import (
    ClimateState,
    ConversationState,
    WorkflowState,
    create_initial_workflow_state,
)
from backend.utils.enums import AgentStatus, ScenarioType


def test_create_initial_workflow_state() -> None:
    state = create_initial_workflow_state(
        current_scenario="baseline-2026",
        scenario_type=ScenarioType.BASELINE,
    )
    assert state["messages"] == []
    assert state["agent_status"] == AgentStatus.IDLE
    assert state["current_scenario"] == "baseline-2026"
    assert state["scenario_type"] == ScenarioType.BASELINE
    assert state["tool_outputs"] == {}
    assert state["rl_outputs"] == {}


def test_climate_state_model() -> None:
    climate = ClimateState(scenario_id="sc-001")
    assert climate.scenario_id == "sc-001"
    assert climate.measurements == []


def test_conversation_state_append() -> None:
    from backend.agents.state.conversation_state import ConversationTurn

    conv = ConversationState()
    conv.append_turn(ConversationTurn(role="user", content="What is the flood risk?"))
    assert conv.message_count == 1
    assert conv.last_user_message() == "What is the flood risk?"


def test_workflow_state_is_typed_dict() -> None:
    state: WorkflowState = create_initial_workflow_state()
    assert isinstance(state, dict)
