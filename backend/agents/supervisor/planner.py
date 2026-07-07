"""Workflow planner for Climate Supervisor execution plans."""

from __future__ import annotations

from backend.agents.supervisor.execution_context import (
    ExecutionMode,
    ExecutionPlan,
    ExecutionPlanStep,
    IntentClassification,
    SupervisorIntent,
)
from backend.agents.supervisor.intent_classifier import INTENT_SUPERVISOR_MAP, IntentClassifier
from backend.config.logger import get_logger

logger = get_logger(__name__)


class Planner:
    """
    Generates structured execution plans from classified user intents.

    Maps intents to ordered domain supervisor steps with dependency
    chains, parallel groups, and RL/digital-twin requirements.
    """

    # Step action templates per intent
    _ACTION_TEMPLATES: dict[SupervisorIntent, list[tuple[str, str]]] = {
        SupervisorIntent.NOWCAST: [("nowcast_supervisor", "retrieve_nowcast")],
        SupervisorIntent.FORECAST: [("forecast_supervisor", "generate_forecast")],
        SupervisorIntent.WHAT_IF: [
            ("simulation_supervisor", "run_scenario_simulation"),
            ("agriculture_supervisor", "assess_agriculture_impact"),
            ("water_resources_supervisor", "assess_water_impact"),
            ("rl_engine", "optimize_policy"),
        ],
        SupervisorIntent.ALERT: [("alert_supervisor", "evaluate_alerts")],
        SupervisorIntent.ANALYTICS: [("analytics_supervisor", "run_analytics")],
        SupervisorIntent.SIMULATION: [("simulation_supervisor", "run_simulation")],
        SupervisorIntent.POLICY: [("policy_supervisor", "evaluate_policy")],
        SupervisorIntent.REPORT: [("report_supervisor", "generate_report")],
        SupervisorIntent.GENERAL_QA: [("general_qa_supervisor", "answer_query")],
    }

    def __init__(self, *, classifier: IntentClassifier | None = None) -> None:
        self._classifier = classifier or IntentClassifier()

    async def plan(
        self,
        classification: IntentClassification,
        *,
        query: str,
        available_supervisors: list[str] | None = None,
    ) -> ExecutionPlan:
        """
        Generate an execution plan for the classified intent.

        Parameters
        ----------
        classification:
            Output from ``IntentClassifier``.
        query:
            Original user query.
        available_supervisors:
            Optional filter — only include steps for registered supervisors.
        """
        intent = classification.intent
        templates = self._ACTION_TEMPLATES.get(intent, self._ACTION_TEMPLATES[SupervisorIntent.GENERAL_QA])
        supervisor_ids = INTENT_SUPERVISOR_MAP.get(intent, ["general_qa_supervisor"])

        if available_supervisors is not None:
            templates = [(sid, act) for sid, act in templates if sid in available_supervisors]
            supervisor_ids = [s for s in supervisor_ids if s in available_supervisors]

        steps: list[ExecutionPlanStep] = []
        previous_step_id: str | None = None
        parallel_group: str | None = None

        execution_mode = ExecutionMode.SEQUENTIAL
        if intent in (SupervisorIntent.WHAT_IF, SupervisorIntent.ANALYTICS):
            execution_mode = ExecutionMode.PARALLEL if len(templates) > 2 else ExecutionMode.SEQUENTIAL

        for idx, (supervisor_id, action) in enumerate(templates):
            step = ExecutionPlanStep(
                supervisor_id=supervisor_id,
                action=action,
                description=f"Execute {action} via {supervisor_id}",
                dependencies=[previous_step_id] if previous_step_id and execution_mode == ExecutionMode.SEQUENTIAL else [],
                parallel_group=parallel_group if execution_mode == ExecutionMode.PARALLEL else None,
                requires_rl=supervisor_id == "rl_engine",
                requires_digital_twin=intent in (SupervisorIntent.WHAT_IF, SupervisorIntent.SIMULATION),
                metadata={"intent": intent.value, "step_index": idx},
            )
            if execution_mode == ExecutionMode.PARALLEL and idx > 0:
                step.parallel_group = f"parallel_{intent.value}"
            steps.append(step)
            previous_step_id = step.step_id

        plan = ExecutionPlan(
            intent=intent,
            query=query,
            steps=steps,
            execution_mode=execution_mode,
            metadata={
                "confidence": classification.confidence,
                "matched_signals": classification.matched_signals,
                "supervisor_ids": supervisor_ids,
            },
        )
        logger.info(
            "execution_plan_created",
            plan_id=plan.plan_id,
            intent=intent.value,
            step_count=len(steps),
            mode=execution_mode.value,
        )
        return plan

    async def replan_on_failure(
        self,
        plan: ExecutionPlan,
        failed_step_id: str,
        *,
        fallback_supervisor: str | None = None,
    ) -> ExecutionPlan:
        """Produce a revised plan after a step failure, optionally swapping in a fallback."""
        revised_steps: list[ExecutionPlanStep] = []
        for step in plan.steps:
            if step.step_id == failed_step_id and fallback_supervisor:
                revised_steps.append(
                    step.model_copy(
                        update={
                            "supervisor_id": fallback_supervisor,
                            "retry_count": step.retry_count + 1,
                            "metadata": {**step.metadata, "replanned": True},
                        },
                    ),
                )
            else:
                revised_steps.append(step)

        return plan.model_copy(update={"steps": revised_steps})
