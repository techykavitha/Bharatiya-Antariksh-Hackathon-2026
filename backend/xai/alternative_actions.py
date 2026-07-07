"""Alternative and rejected action explanation engine."""

from __future__ import annotations

from backend.decision.decision_actions import ActionRanking, DecisionAction, RejectedAction
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.xai.explanation_report import (
    AlternativeActionExplanation,
    AlternativeActionsAnalysis,
    ExplanationInput,
    RejectedActionExplanation,
)


class AlternativeActionsEngine:
    """Explains chosen, alternative, and rejected actions."""

    async def analyze(self, explanation_input: ExplanationInput) -> AlternativeActionsAnalysis:
        decision = explanation_input.decision_request
        response = explanation_input.decision_response

        if not decision and not response:
            return AlternativeActionsAnalysis(
                summary="No decision artifacts available for alternative action analysis",
            )

        chosen = response.chosen_action if response else None
        ranking = list(response.ranking) if response else []
        rejected = self._explain_rejected(response.rejected_actions if response else [])
        alternatives = self._explain_alternatives(
            decision=decision,
            response=response,
            chosen=chosen,
            ranking=ranking,
            rejected_raw=response.rejected_actions if response else [],
        )

        summary = self._build_summary(chosen, alternatives, rejected)
        return AlternativeActionsAnalysis(
            chosen_action=chosen,
            alternatives=alternatives,
            rejected=rejected,
            ranking=ranking,
            summary=summary,
        )

    def _explain_rejected(self, rejected: list[RejectedAction]) -> list[RejectedActionExplanation]:
        explanations: list[RejectedActionExplanation] = []
        for item in rejected:
            explanations.append(RejectedActionExplanation(
                action_id=item.action_id,
                reason=item.reason,
                constraint_violated=item.constraint_violated,
                score=item.score,
            ))
        return explanations

    def _explain_alternatives(
        self,
        *,
        decision: DecisionRequest | None,
        response: DecisionResponse | None,
        chosen: DecisionAction | None,
        ranking: list[ActionRanking],
        rejected_raw: list[RejectedAction],
    ) -> list[AlternativeActionExplanation]:
        explanations: list[AlternativeActionExplanation] = []
        rejected_ids = {r.action_id for r in rejected_raw}
        action_lookup = {a.action_id: a for a in (decision.possible_actions if decision else [])}

        if ranking:
            for entry in ranking:
                if chosen and entry.action_id == chosen.action_id:
                    continue
                action = action_lookup.get(entry.action_id)
                if action is None:
                    continue
                explanations.append(AlternativeActionExplanation(
                    action=action,
                    rank=entry.rank,
                    score=entry.score,
                    expected_reward=entry.expected_reward,
                    confidence=entry.confidence,
                    rationale=entry.rationale,
                    why_not_chosen=self._why_not_chosen(action, chosen, entry, rejected_ids),
                    trade_offs=self._trade_offs(action, chosen),
                ))
            return explanations

        if not decision or not chosen:
            return explanations

        for action in decision.possible_actions:
            if action.action_id == chosen.action_id:
                continue
            if action.action_id in rejected_ids:
                continue
            explanations.append(AlternativeActionExplanation(
                action=action,
                rationale="Candidate action not selected by optimization engine",
                why_not_chosen=self._compare_to_chosen(action, chosen),
                trade_offs=self._trade_offs(action, chosen),
            ))

        return explanations

    def _why_not_chosen(
        self,
        action: DecisionAction,
        chosen: DecisionAction | None,
        ranking: ActionRanking,
        rejected_ids: set[str],
    ) -> str:
        if action.action_id in rejected_ids:
            return "Rejected due to constraint violation"
        if chosen is None:
            return ranking.rationale or "Lower optimization score"
        if ranking.rank > 1:
            return (
                f"Ranked #{ranking.rank} with score {ranking.score:.2f} "
                f"vs chosen action score based on net value {chosen.net_value:.1f}"
            )
        return ranking.rationale or self._compare_to_chosen(action, chosen)

    def _compare_to_chosen(self, action: DecisionAction, chosen: DecisionAction | None) -> str:
        if chosen is None:
            return "No chosen action to compare against"
        if action.net_value < chosen.net_value:
            return (
                f"Lower net value ({action.net_value:.1f} vs {chosen.net_value:.1f}); "
                f"higher cost ({action.cost:.1f}) or lower benefit ({action.expected_benefit:.1f})"
            )
        if action.risk_score > chosen.risk_score:
            return f"Higher risk score ({action.risk_score:.2f} vs {chosen.risk_score:.2f})"
        return "Lower composite optimization score"

    def _trade_offs(self, action: DecisionAction, chosen: DecisionAction | None) -> list[str]:
        trade_offs: list[str] = []
        if chosen is None:
            return trade_offs
        cost_delta = action.cost - chosen.cost
        benefit_delta = action.expected_benefit - chosen.expected_benefit
        if cost_delta > 5:
            trade_offs.append(f"Higher cost by {cost_delta:.1f} units")
        elif cost_delta < -5:
            trade_offs.append(f"Lower cost by {abs(cost_delta):.1f} units")
        if benefit_delta > 5:
            trade_offs.append(f"Higher expected benefit by {benefit_delta:.1f}")
        elif benefit_delta < -5:
            trade_offs.append(f"Lower expected benefit by {abs(benefit_delta):.1f}")
        if action.risk != chosen.risk:
            trade_offs.append(f"Risk profile: {action.risk.value} vs {chosen.risk.value}")
        return trade_offs

    def _build_summary(
        self,
        chosen: DecisionAction | None,
        alternatives: list[AlternativeActionExplanation],
        rejected: list[RejectedActionExplanation],
    ) -> str:
        if chosen is None:
            return f"No action selected; {len(alternatives)} alternatives evaluated"
        return (
            f"Selected: {chosen.description}. "
            f"{len(alternatives)} alternatives considered, {len(rejected)} rejected."
        )
