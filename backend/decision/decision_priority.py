"""Priority definitions and comparison utilities for decision requests."""

from __future__ import annotations

from enum import IntEnum

from pydantic import BaseModel, Field


class DecisionPriority(IntEnum):
    """Ordinal priority for decision request scheduling.

    Higher numeric value indicates higher urgency.
    """

    DEFERRED = 0
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


PRIORITY_LABELS: dict[DecisionPriority, str] = {
    DecisionPriority.DEFERRED: "deferred",
    DecisionPriority.LOW: "low",
    DecisionPriority.NORMAL: "normal",
    DecisionPriority.HIGH: "high",
    DecisionPriority.URGENT: "urgent",
    DecisionPriority.CRITICAL: "critical",
}

LABEL_TO_PRIORITY: dict[str, DecisionPriority] = {v: k for k, v in PRIORITY_LABELS.items()}


def priority_from_label(label: str) -> DecisionPriority:
    """Convert a string priority label to ``DecisionPriority``."""
    normalized = label.strip().lower()
    return LABEL_TO_PRIORITY.get(normalized, DecisionPriority.NORMAL)


def compare_priority(a: DecisionPriority, b: DecisionPriority) -> int:
    """Compare two priorities. Returns positive if *a* is higher than *b*."""
    return int(a) - int(b)


def escalate_priority(current: DecisionPriority, steps: int = 1) -> DecisionPriority:
    """Escalate priority by *steps*, capped at CRITICAL."""
    new_value = min(int(current) + steps, int(DecisionPriority.CRITICAL))
    return DecisionPriority(new_value)


class PriorityContext(BaseModel):
    """Additional context influencing priority resolution."""

    base_priority: DecisionPriority = DecisionPriority.NORMAL
    risk_escalation: bool = False
    human_waiting: bool = False
    deadline_utc: str | None = None
    override: DecisionPriority | None = None

    def resolve(self) -> DecisionPriority:
        if self.override is not None:
            return self.override
        priority = self.base_priority
        if self.risk_escalation:
            priority = escalate_priority(priority)
        if self.human_waiting:
            priority = escalate_priority(priority)
        return priority
