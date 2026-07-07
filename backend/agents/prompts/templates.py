"""Reusable prompt templates for Hyperion Climate Twin agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from string import Template
from typing import Any


@dataclass(frozen=True)
class PromptTemplate:
    """
    Immutable prompt template with safe variable substitution.

    Uses ``string.Template`` for ``$variable`` placeholders, avoiding
    conflicts with JSON or Python brace syntax in prompt bodies.
    """

    name: str
    template: str
    description: str = ""
    required_variables: frozenset[str] = field(default_factory=frozenset)

    def render(self, **kwargs: Any) -> str:
        """
        Render the template with the provided variables.

        Raises
        ------
        KeyError
            If a required variable is missing from ``kwargs``.
        """
        missing = self.required_variables - set(kwargs)
        if missing:
            raise KeyError(f"Missing required prompt variables: {sorted(missing)}")
        return Template(self.template).safe_substitute(**kwargs)

    def partial_render(self, **kwargs: Any) -> str:
        """Render with partial substitution; unreplaced placeholders remain."""
        return Template(self.template).safe_substitute(**kwargs)


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = PromptTemplate(
    name="system",
    description="Core system identity and behavioral constraints for all agents.",
    required_variables=frozenset({"agent_name", "agent_role", "capabilities"}),
    template="""\
You are $agent_name, a specialized agent in the Hyperion Climate Twin platform.

Role: $agent_role

Capabilities:
$capabilities

Operating principles:
- Ground all responses in verified climate data and simulation outputs.
- Clearly distinguish observations, forecasts, and model projections.
- Cite data sources and express uncertainty when confidence is limited.
- Never fabricate measurements, simulation results, or forecast values.
- Escalate to the supervisor agent when a request exceeds your scope.

You operate within an enterprise climate intelligence system serving \
decision-makers, scientists, and emergency response teams.
""",
)


# ---------------------------------------------------------------------------
# Reasoning Prompt
# ---------------------------------------------------------------------------
REASONING_PROMPT = PromptTemplate(
    name="reasoning",
    description="Structured chain-of-thought reasoning for agent decision-making.",
    required_variables=frozenset({"query", "context", "available_tools"}),
    template="""\
Analyze the following request using structured reasoning.

## User Query
$query

## Available Context
$context

## Available Tools
$available_tools

## Instructions
1. Identify the core intent and any implicit sub-questions.
2. Assess which climate variables, locations, or simulations are relevant.
3. Determine which tools (if any) are needed to answer accurately.
4. Identify gaps in available data and state assumptions explicitly.
5. Formulate a concise answer plan before executing tools.

Provide your reasoning as numbered steps. Do not execute tools in this phase.
""",
)


# ---------------------------------------------------------------------------
# Planning Prompt
# ---------------------------------------------------------------------------
PLANNING_PROMPT = PromptTemplate(
    name="planning",
    description="Multi-step execution plan for complex climate workflows.",
    required_variables=frozenset({"objective", "constraints", "resources"}),
    template="""\
Create a step-by-step execution plan for the following objective.

## Objective
$objective

## Constraints
$constraints

## Available Resources
$resources

## Plan Requirements
- Each step must be atomic and independently verifiable.
- Specify which agent or tool handles each step.
- Include rollback or fallback steps for simulation failures.
- Estimate data dependencies for each step.
- Flag steps requiring human approval.

Output the plan as a numbered list with: step_id, action, agent/tool, \
expected_output, and dependencies.
""",
)


# ---------------------------------------------------------------------------
# Simulation Prompt
# ---------------------------------------------------------------------------
SIMULATION_PROMPT = PromptTemplate(
    name="simulation",
    description="Guidance for configuring and interpreting climate simulations.",
    required_variables=frozenset(
        {"scenario_type", "location", "parameters", "horizon"},
    ),
    template="""\
Configure and interpret a climate simulation with the following parameters.

## Scenario Type
$scenario_type

## Location
$location

## Simulation Parameters
$parameters

## Forecast Horizon
$horizon

## Instructions
- Validate all input parameters against physical and model constraints.
- Describe expected outputs and key climate variables to monitor.
- Define success criteria and acceptable error bounds.
- Identify sensitivity parameters that most affect outcomes.
- Specify how results should be stored in the digital twin state.
""",
)


# ---------------------------------------------------------------------------
# Reflection Prompt
# ---------------------------------------------------------------------------
REFLECTION_PROMPT = PromptTemplate(
    name="reflection",
    description="Post-execution self-evaluation and quality assurance.",
    required_variables=frozenset({"query", "response", "tool_outputs", "criteria"}),
    template="""\
Evaluate the quality and completeness of the agent response.

## Original Query
$query

## Agent Response
$response

## Tool Outputs
$tool_outputs

## Quality Criteria
$criteria

## Reflection Tasks
1. Did the response fully address the user's query?
2. Are all claims supported by tool outputs or cited data?
3. Were uncertainties and limitations communicated?
4. Were any tools used unnecessarily or omitted when needed?
5. Should the response be revised, escalated, or accepted?

Provide: verdict (accept | revise | escalate), confidence (0.0–1.0), \
and specific improvement recommendations.
""",
)


# Registry of all built-in templates
PROMPT_REGISTRY: dict[str, PromptTemplate] = {
    SYSTEM_PROMPT.name: SYSTEM_PROMPT,
    REASONING_PROMPT.name: REASONING_PROMPT,
    PLANNING_PROMPT.name: PLANNING_PROMPT,
    SIMULATION_PROMPT.name: SIMULATION_PROMPT,
    REFLECTION_PROMPT.name: REFLECTION_PROMPT,
}


def get_prompt(name: str) -> PromptTemplate:
    """
    Retrieve a registered prompt template by name.

    Raises
    ------
    KeyError
        If no template is registered under ``name``.
    """
    if name not in PROMPT_REGISTRY:
        raise KeyError(f"Unknown prompt template: '{name}'")
    return PROMPT_REGISTRY[name]
