"""LangGraph construction and execution for the Climate Supervisor."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from backend.agents.state.workflow_state import WorkflowState
from backend.agents.supervisor.climate_supervisor import ClimateSupervisor
from backend.config.logger import get_logger

logger = get_logger(__name__)

# Compiled graph type alias
CompiledSupervisorGraph = Any


def build_graph(supervisor: ClimateSupervisor) -> StateGraph:
    """
    Build the LangGraph ``StateGraph`` for the Climate Supervisor workflow.

    Graph topology::

        classify_intent → plan → execute → merge_results → store_memory → return_response → END

    Parameters
    ----------
    supervisor:
        Configured ``ClimateSupervisor`` instance providing node functions.
    """
    graph: StateGraph = StateGraph(WorkflowState)

    graph.add_node("classify_intent", supervisor.node_classify_intent)
    graph.add_node("plan", supervisor.node_plan)
    graph.add_node("execute", supervisor.node_execute)
    graph.add_node("merge_results", supervisor.node_merge_results)
    graph.add_node("store_memory", supervisor.node_store_memory)
    graph.add_node("return_response", supervisor.node_return_response)

    graph.set_entry_point("classify_intent")
    graph.add_edge("classify_intent", "plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "merge_results")
    graph.add_edge("merge_results", "store_memory")
    graph.add_edge("store_memory", "return_response")
    graph.add_edge("return_response", END)

    logger.info("supervisor_graph_built")
    return graph


def compile_graph(graph: StateGraph) -> CompiledSupervisorGraph:
    """Compile a ``StateGraph`` into an executable graph."""
    compiled = graph.compile()
    logger.info("supervisor_graph_compiled")
    return compiled


async def run_graph(
    compiled: CompiledSupervisorGraph,
    initial_state: WorkflowState,
    *,
    config: dict[str, Any] | None = None,
) -> WorkflowState:
    """
    Execute a compiled supervisor graph asynchronously.

    Parameters
    ----------
    compiled:
        Output of ``compile_graph``.
    initial_state:
        Initial ``WorkflowState`` (use ``create_initial_workflow_state``).
    config:
        Optional LangGraph runnable configuration.
    """
    logger.info("supervisor_graph_run_started")
    final_state = await compiled.ainvoke(initial_state, config or {})
    logger.info(
        "supervisor_graph_run_completed",
        agent_status=final_state.get("agent_status"),
    )
    return final_state
