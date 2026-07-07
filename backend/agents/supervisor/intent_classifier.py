"""Intent classification for Climate Supervisor request routing."""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.agents.supervisor.execution_context import IntentClassification, SupervisorIntent
from backend.config.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class _IntentSignal:
    """Weighted keyword/phrase signal for intent matching."""

    intent: SupervisorIntent
    patterns: tuple[str, ...]
    weight: float = 1.0


# Domain supervisor identifiers mapped from intents
INTENT_SUPERVISOR_MAP: dict[SupervisorIntent, list[str]] = {
    SupervisorIntent.NOWCAST: ["nowcast_supervisor"],
    SupervisorIntent.FORECAST: ["forecast_supervisor"],
    SupervisorIntent.WHAT_IF: [
        "simulation_supervisor",
        "agriculture_supervisor",
        "water_resources_supervisor",
        "rl_engine",
    ],
    SupervisorIntent.ALERT: ["alert_supervisor"],
    SupervisorIntent.ANALYTICS: ["analytics_supervisor"],
    SupervisorIntent.SIMULATION: ["simulation_supervisor"],
    SupervisorIntent.POLICY: ["policy_supervisor"],
    SupervisorIntent.REPORT: ["report_supervisor"],
    SupervisorIntent.GENERAL_QA: ["general_qa_supervisor"],
}


class IntentClassifier:
    """
    Rule-based intent classifier for incoming user queries.

    Uses weighted keyword and phrase matching. Designed to be replaced
    or augmented with an LLM classifier without changing the supervisor API.
    """

    DEFAULT_SIGNALS: tuple[_IntentSignal, ...] = (
        _IntentSignal(SupervisorIntent.NOWCAST, ("nowcast", "right now", "current weather", "live conditions"), 1.2),
        _IntentSignal(SupervisorIntent.FORECAST, ("forecast", "predict", "prediction", "next week", "tomorrow", "upcoming"), 1.1),
        _IntentSignal(SupervisorIntent.WHAT_IF, ("what if", "what happens if", "scenario", "decrease", "increase", "hypothetical"), 1.3),
        _IntentSignal(SupervisorIntent.ALERT, ("alert", "warning", "emergency", "evacuation", "severe"), 1.2),
        _IntentSignal(SupervisorIntent.ANALYTICS, ("analyze", "analytics", "trend", "statistics", "correlation", "insight"), 1.0),
        _IntentSignal(SupervisorIntent.SIMULATION, ("simulate", "simulation", "model run", "run model"), 1.2),
        _IntentSignal(SupervisorIntent.POLICY, ("policy", "regulation", "compliance", "governance", "framework"), 1.1),
        _IntentSignal(SupervisorIntent.REPORT, ("report", "summary", "briefing", "document"), 1.0),
    )

    def __init__(self, *, signals: tuple[_IntentSignal, ...] | None = None) -> None:
        self._signals = signals or self.DEFAULT_SIGNALS

    async def classify(self, query: str) -> IntentClassification:
        """
        Classify a user query into a ``SupervisorIntent``.

        Returns the highest-scoring intent with confidence in [0, 1].
        """
        normalized = query.strip().lower()
        scores: dict[SupervisorIntent, float] = {intent: 0.0 for intent in SupervisorIntent}
        matched: dict[SupervisorIntent, list[str]] = {intent: [] for intent in SupervisorIntent}

        for signal in self._signals:
            for pattern in signal.patterns:
                if pattern in normalized or re.search(rf"\b{re.escape(pattern)}\b", normalized):
                    scores[signal.intent] += signal.weight
                    matched[signal.intent].append(pattern)

        best_intent = max(scores, key=lambda k: scores[k])
        best_score = scores[best_intent]

        if best_score == 0.0:
            best_intent = SupervisorIntent.GENERAL_QA
            confidence = 0.5
        else:
            total = sum(scores.values()) or 1.0
            confidence = min(best_score / total, 1.0)

        classification = IntentClassification(
            intent=best_intent,
            confidence=round(confidence, 4),
            matched_signals=matched[best_intent],
            raw_query=query,
        )
        logger.info(
            "intent_classified",
            intent=classification.intent.value,
            confidence=classification.confidence,
            signals=classification.matched_signals,
        )
        return classification

    def get_supervisors_for_intent(self, intent: SupervisorIntent) -> list[str]:
        """Return the domain supervisor IDs associated with an intent."""
        return list(INTENT_SUPERVISOR_MAP.get(intent, ["general_qa_supervisor"]))
