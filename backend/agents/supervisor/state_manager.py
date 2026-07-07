"""WorkflowState read/write helpers for the Climate Supervisor."""

from __future__ import annotations

from typing import Any

from backend.agents.state.workflow_state import WorkflowState
from backend.agents.supervisor.execution_context import (
    ExecutionPlan,
    ExecutionResult,
    IntentClassification,
    SupervisorIntent,
)
from backend.utils.enums import AgentStatus


class StateManager:
    """
    Reads and updates ``WorkflowState`` without modifying its schema.

    Execution tracking data is stored in the ``metadata`` dict field.
    """

    META_CURRENT_NODE = "supervisor_current_node"
    META_COMPLETED_NODES = "supervisor_completed_nodes"
    META_PENDING_NODES = "supervisor_pending_nodes"
    META_EXECUTION_HISTORY = "supervisor_execution_history"
    META_PLAN = "supervisor_plan"
    META_INTENT = "supervisor_intent"
    META_INTENT_CONFIDENCE = "supervisor_intent_confidence"
    META_EXECUTION_RESULT = "supervisor_execution_result"

    def get_current_node(self, state: WorkflowState) -> str | None:
        return self._meta(state).get(self.META_CURRENT_NODE)

    def get_completed_nodes(self, state: WorkflowState) -> list[str]:
        return list(self._meta(state).get(self.META_COMPLETED_NODES, []))

    def get_pending_nodes(self, state: WorkflowState) -> list[str]:
        return list(self._meta(state).get(self.META_PENDING_NODES, []))

    def get_execution_history(self, state: WorkflowState) -> list[dict[str, Any]]:
        return list(self._meta(state).get(self.META_EXECUTION_HISTORY, []))

    def get_plan(self, state: WorkflowState) -> dict[str, Any] | None:
        return self._meta(state).get(self.META_PLAN)

    def get_intent(self, state: WorkflowState) -> SupervisorIntent | None:
        raw = self._meta(state).get(self.META_INTENT)
        return SupervisorIntent(raw) if raw else None

    def apply_classification(
        self,
        state: WorkflowState,
        classification: IntentClassification,
    ) -> dict[str, Any]:
        """Return a partial state update with intent metadata."""
        return {
            "metadata": {
                self.META_INTENT: classification.intent.value,
                self.META_INTENT_CONFIDENCE: classification.confidence,
                self.META_CURRENT_NODE: "classify_intent",
            },
            "agent_status": AgentStatus.REASONING,
        }

    def apply_plan(self, state: WorkflowState, plan: ExecutionPlan) -> dict[str, Any]:
        """Return a partial state update with plan and pending nodes."""
        pending = [step.step_id for step in plan.steps]
        return {
            "metadata": {
                self.META_PLAN: plan.model_dump(mode="json"),
                self.META_PENDING_NODES: pending,
                self.META_COMPLETED_NODES: self.get_completed_nodes(state),
                self.META_CURRENT_NODE: "plan",
            },
            "agent_status": AgentStatus.PLANNING,
        }

    def apply_node_start(self, state: WorkflowState, node_name: str) -> dict[str, Any]:
        return {"metadata": {self.META_CURRENT_NODE: node_name}}

    def apply_node_complete(
        self,
        state: WorkflowState,
        node_name: str,
        *,
        result_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        completed = self.get_completed_nodes(state)
        if node_name not in completed:
            completed.append(node_name)
        pending = [n for n in self.get_pending_nodes(state) if n != node_name]
        history = self.get_execution_history(state)
        history.append({
            "node": node_name,
            "summary": result_summary or {},
        })
        return {
            "metadata": {
                self.META_CURRENT_NODE: node_name,
                self.META_COMPLETED_NODES: completed,
                self.META_PENDING_NODES: pending,
                self.META_EXECUTION_HISTORY: history,
            },
        }

    def apply_execution_result(
        self,
        state: WorkflowState,
        result: ExecutionResult,
        *,
        called_agents: list[str],
        tool_outputs: dict[str, Any],
        memory_refs: list[str],
    ) -> dict[str, Any]:
        """Return a partial state update after plan execution."""
        return {
            "called_agents": called_agents,
            "tool_outputs": tool_outputs,
            "memory_references": memory_refs,
            "agent_status": result.status,
            "metadata": {
                self.META_EXECUTION_RESULT: result.model_dump(mode="json"),
                self.META_CURRENT_NODE: "execute",
                self.META_COMPLETED_NODES: self.get_completed_nodes(state) + ["execute"],
            },
            "error": result.metadata.get("error"),
        }

    def apply_response(self, state: WorkflowState, *, content: str) -> dict[str, Any]:
        return {
            "agent_status": AgentStatus.COMPLETED,
            "metadata": {
                self.META_CURRENT_NODE: "return_response",
                "supervisor_response": content,
            },
        }

    def apply_error(self, state: WorkflowState, error: str) -> dict[str, Any]:
        return {
            "agent_status": AgentStatus.FAILED,
            "error": error,
            "metadata": {self.META_CURRENT_NODE: "error"},
        }

    @staticmethod
    def _meta(state: WorkflowState) -> dict[str, Any]:
        return dict(state.get("metadata") or {})
