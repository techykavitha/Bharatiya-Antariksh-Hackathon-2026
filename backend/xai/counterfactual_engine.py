"""Counterfactual analysis engine for explainability."""

from __future__ import annotations

from backend.decision.decision_actions import DecisionAction
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.xai.explanation_models import CounterfactualType
from backend.xai.explanation_report import CounterfactualAnalysis, CounterfactualScenario, ExplanationInput


class CounterfactualEngine:
    """
    Generates counterfactual what-if analyses.

    Answers: "What if another action had been selected?"
    """

    async def analyze(self, explanation_input: ExplanationInput) -> CounterfactualAnalysis:
        decision = explanation_input.decision_request
        response = explanation_input.decision_response

        if not decision:
            return CounterfactualAnalysis(
                summary="No decision request available for counterfactual analysis",
            )

        chosen = response.chosen_action if response else None
        scenarios: list[CounterfactualScenario] = []

        scenarios.extend(self._alternative_action_scenarios(decision, chosen, response))
        scenarios.extend(self._alternative_decision_scenarios(decision))
        scenarios.extend(self._alternative_scenario_contexts(decision, chosen))

        summary = self._build_summary(chosen, scenarios)
        return CounterfactualAnalysis(
            question="What if another action had been selected?",
            scenarios=scenarios,
            summary=summary,
        )

    def _alternative_action_scenarios(
        self,
        decision: DecisionRequest,
        chosen: DecisionAction | None,
        response: DecisionResponse | None,
    ) -> list[CounterfactualScenario]:
        scenarios: list[CounterfactualScenario] = []
        ranking_lookup: dict[str, float] = {}
        if response:
            ranking_lookup = {r.action_id: r.expected_reward for r in response.ranking}

        for action in decision.possible_actions:
            if chosen and action.action_id == chosen.action_id:
                continue

            baseline_reward = response.reward if response and response.reward is not None else chosen.net_value if chosen else 0.0
            alt_reward = ranking_lookup.get(action.action_id, action.net_value)
            delta = alt_reward - baseline_reward

            scenarios.append(CounterfactualScenario(
                counterfactual_type=CounterfactualType.ALTERNATIVE_ACTION,
                title=f"What if '{action.description}' had been selected?",
                description=(
                    f"Counterfactual assuming action '{action.category}' "
                    f"was implemented instead of the chosen mitigation."
                ),
                assumed_action=action,
                baseline_outcome=self._outcome_narrative(chosen, baseline_reward),
                counterfactual_outcome=self._outcome_narrative(action, alt_reward),
                outcome_delta=self._delta_narrative(delta),
                confidence=0.65 if ranking_lookup else 0.5,
                assumptions=[
                    "Other environmental conditions remain unchanged",
                    "Action feasibility constraints are satisfied",
                    f"Decision horizon: {decision.context.scenario.horizon_hours} hours",
                ],
                metadata={
                    "cost": action.cost,
                    "expected_benefit": action.expected_benefit,
                    "risk": action.risk.value,
                },
            ))

        return scenarios[:5]

    def _alternative_decision_scenarios(self, decision: DecisionRequest) -> list[CounterfactualScenario]:
        scenarios: list[CounterfactualScenario] = []

        if decision.need_rl:
            scenarios.append(CounterfactualScenario(
                counterfactual_type=CounterfactualType.ALTERNATIVE_DECISION,
                title="What if RL optimization had not been used?",
                description="Heuristic selection based on highest net value among feasible actions",
                baseline_outcome="RL-optimized action balancing objectives and constraints",
                counterfactual_outcome="Highest net-value action without policy optimization",
                outcome_delta="Potentially suboptimal multi-objective trade-off",
                confidence=0.55,
                assumptions=["Constraint validation still applied"],
            ))

        if decision.need_simulation:
            scenarios.append(CounterfactualScenario(
                counterfactual_type=CounterfactualType.ALTERNATIVE_DECISION,
                title="What if a simulation had been run before deciding?",
                description="Decision informed by dynamic scenario simulation",
                baseline_outcome="Decision based on current observations and forecasts",
                counterfactual_outcome="Refined action selection with simulated impact trajectories",
                outcome_delta="Reduced simulation uncertainty and improved spatial precision",
                confidence=0.6,
                assumptions=["Simulation completes within decision time window"],
            ))

        return scenarios

    def _alternative_scenario_contexts(
        self,
        decision: DecisionRequest,
        chosen: DecisionAction | None,
    ) -> list[CounterfactualScenario]:
        scenario = decision.context.scenario
        if not scenario.region_id:
            return []

        worsening = CounterfactualScenario(
            counterfactual_type=CounterfactualType.ALTERNATIVE_SCENARIO,
            title=f"What if conditions in {scenario.region_id} worsen?",
            description="Stress scenario with intensified hazard drivers",
            baseline_outcome=self._outcome_narrative(chosen, decision.risk.score),
            counterfactual_outcome="Higher population exposure and infrastructure stress",
            outcome_delta="May require escalation to emergency response actions",
            confidence=0.5,
            assumptions=[
                "Hazard intensity increases 20-30%",
                "Vulnerable population exposure rises",
            ],
            metadata={"region_id": scenario.region_id},
        )

        improving = CounterfactualScenario(
            counterfactual_type=CounterfactualType.ALTERNATIVE_SCENARIO,
            title=f"What if conditions in {scenario.region_id} improve?",
            description="Moderating scenario with reduced hazard drivers",
            baseline_outcome=self._outcome_narrative(chosen, decision.risk.score),
            counterfactual_outcome="Lower mitigation intensity may suffice",
            outcome_delta="Potential to downgrade to monitoring and public alerts",
            confidence=0.5,
            assumptions=[
                "Hazard drivers decrease within 24-48 hours",
                "No compound event escalation",
            ],
            metadata={"region_id": scenario.region_id},
        )

        return [worsening, improving]

    def _outcome_narrative(self, action: DecisionAction | None, score: float) -> str:
        if action is None:
            return f"Expected outcome score approximately {score:.1f}"
        return (
            f"Action '{action.description}' with net value {action.net_value:.1f} "
            f"and risk {action.risk.value}"
        )

    def _delta_narrative(self, delta: float) -> str:
        if delta > 5:
            return f"Counterfactual outcome improves expected reward by {delta:.1f}"
        if delta < -5:
            return f"Chosen action improves expected reward by {abs(delta):.1f} over counterfactual"
        return "Marginal difference between counterfactual and chosen action"

    def _build_summary(
        self,
        chosen: DecisionAction | None,
        scenarios: list[CounterfactualScenario],
    ) -> str:
        action_count = sum(
            1 for s in scenarios if s.counterfactual_type == CounterfactualType.ALTERNATIVE_ACTION
        )
        if chosen is None:
            return f"Generated {len(scenarios)} counterfactual scenarios without a chosen action"
        return (
            f"Compared chosen action '{chosen.description}' against "
            f"{action_count} alternative actions and {len(scenarios) - action_count} contextual scenarios."
        )
