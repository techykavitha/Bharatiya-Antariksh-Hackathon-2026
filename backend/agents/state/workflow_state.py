"""LangGraph-compatible workflow state definitions."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from backend.agents.state.climate_state import ClimateState
from backend.agents.state.conversation_state import ActiveUser, ConversationState
from backend.utils.enums import AgentStatus, ScenarioType


def merge_dicts(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    """Reducer that shallow-merges two dictionaries (right overrides left)."""
    merged: dict[str, Any] = dict(left or {})
    merged.update(right or {})
    return merged


def append_lists(left: list[Any] | None, right: list[Any] | None) -> list[Any]:
    """Reducer that concatenates two lists."""
    return list(left or []) + list(right or [])


def replace_value(_left: Any, right: Any) -> Any:
    """Reducer that always takes the latest value (last-write-wins)."""
    return right


class WorkflowState(TypedDict, total=False):
    """
    Root LangGraph state schema for the Hyperion multi-agent workflow.

    All fields use reducers compatible with LangGraph's ``StateGraph``.
    Domain agents read and write slices of this state during graph execution.

    Field groups
    ------------
  conversation:
        ``messages``, ``conversation``, ``active_user``
    climate:
        ``climate_state``, ``digital_twin_state``, ``forecast_references``
    execution:
        ``called_agents``, ``tool_outputs``, ``rl_outputs``, ``agent_status``
    memory & knowledge:
        ``memory_references``, ``knowledge_graph_references``
    scenario:
        ``current_scenario``, ``scenario_type``, ``active_simulation``
    control:
        ``error``, ``metadata``, ``next_agent``
    """

    # --- Conversation (LangChain message channel) ---
    messages: Annotated[list[BaseMessage], add_messages]
    conversation: Annotated[ConversationState | None, replace_value]
    active_user: Annotated[ActiveUser | None, replace_value]

    # --- Climate context ---
    climate_state: Annotated[ClimateState | None, replace_value]
    digital_twin_state: Annotated[dict[str, Any], merge_dicts]
    forecast_references: Annotated[list[dict[str, Any]], append_lists]
    active_simulation: Annotated[dict[str, Any] | None, replace_value]

    # --- Scenario ---
    current_scenario: Annotated[str | None, replace_value]
    scenario_type: Annotated[ScenarioType | None, replace_value]

    # --- Agent execution trace ---
    called_agents: Annotated[list[str], append_lists]
    tool_outputs: Annotated[dict[str, Any], merge_dicts]
    rl_outputs: Annotated[dict[str, Any], merge_dicts]
    agent_status: Annotated[AgentStatus, replace_value]

    # --- Memory & knowledge ---
    memory_references: Annotated[list[str], append_lists]
    knowledge_graph_references: Annotated[list[str], append_lists]

    # --- Control flow ---
    next_agent: Annotated[str | None, replace_value]
    error: Annotated[str | None, replace_value]
    metadata: Annotated[dict[str, Any], merge_dicts]


def create_initial_workflow_state(
    *,
    conversation: ConversationState | None = None,
    active_user: ActiveUser | None = None,
    climate_state: ClimateState | None = None,
    current_scenario: str | None = None,
    scenario_type: ScenarioType | None = None,
    metadata: dict[str, Any] | None = None,
) -> WorkflowState:
    """
    Construct a fully-initialized ``WorkflowState`` with safe defaults.

    Use this factory when bootstrapping a new LangGraph execution.
    """
    return WorkflowState(
        messages=[],
        conversation=conversation,
        active_user=active_user,
        climate_state=climate_state,
        digital_twin_state={},
        forecast_references=[],
        active_simulation=None,
        current_scenario=current_scenario,
        scenario_type=scenario_type,
        called_agents=[],
        tool_outputs={},
        rl_outputs={},
        agent_status=AgentStatus.IDLE,
        memory_references=[],
        knowledge_graph_references=[],
        next_agent=None,
        error=None,
        metadata=metadata or {},
    )
