"""Tests for intent classification."""

import pytest

from backend.agents.supervisor.intent_classifier import INTENT_SUPERVISOR_MAP, IntentClassifier
from backend.agents.supervisor.execution_context import SupervisorIntent


@pytest.fixture
def classifier() -> IntentClassifier:
    return IntentClassifier()


@pytest.mark.asyncio
async def test_classify_what_if(classifier: IntentClassifier) -> None:
    result = await classifier.classify("What happens if rainfall decreases 20% in Karnataka?")
    assert result.intent == SupervisorIntent.WHAT_IF
    assert result.confidence > 0


@pytest.mark.asyncio
async def test_classify_forecast(classifier: IntentClassifier) -> None:
    result = await classifier.classify("Show me the 7-day weather forecast for Mumbai")
    assert result.intent == SupervisorIntent.FORECAST


@pytest.mark.asyncio
async def test_classify_general_fallback(classifier: IntentClassifier) -> None:
    result = await classifier.classify("Hello there")
    assert result.intent == SupervisorIntent.GENERAL_QA


def test_intent_supervisor_map_coverage() -> None:
    for intent in SupervisorIntent:
        assert intent in INTENT_SUPERVISOR_MAP
        assert len(INTENT_SUPERVISOR_MAP[intent]) >= 1
