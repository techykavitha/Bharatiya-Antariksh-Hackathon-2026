"""Tests for prompt templates."""

import pytest

from backend.agents.prompts import (
    REASONING_PROMPT,
    SYSTEM_PROMPT,
    get_prompt,
)


def test_system_prompt_render() -> None:
    rendered = SYSTEM_PROMPT.render(
        agent_name="test-agent",
        agent_role="domain",
        capabilities="- forecast\n- analysis",
    )
    assert "test-agent" in rendered
    assert "Hyperion Climate Twin" in rendered


def test_reasoning_prompt_missing_variable_raises() -> None:
    with pytest.raises(KeyError):
        REASONING_PROMPT.render(query="test", context="ctx")


def test_get_prompt_registry() -> None:
    prompt = get_prompt("planning")
    assert prompt.name == "planning"


def test_get_unknown_prompt_raises() -> None:
    with pytest.raises(KeyError):
        get_prompt("nonexistent")
