"""Shared fixtures for decision framework tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.agents.state.climate_state import (
    ClimateMeasurement,
    ClimateState,
    ForecastReference,
    GeoLocation,
)
from backend.decision import (
    BudgetConstraint,
    DecisionAction,
    DecisionConstraints,
    DecisionContext,
    DecisionManager,
    DecisionPriority,
    DecisionRequest,
    DecisionSerializer,
    DecisionType,
    DecisionValidator,
    Objective,
    RiskAssessment,
    RiskLevel,
    SafetyConstraint,
    ScenarioContext,
)
from backend.utils.enums import ClimateVariable


def sample_action(
    description: str = "Controlled reservoir release",
    cost: float = 10.0,
    benefit: float = 50.0,
    risk: RiskLevel = RiskLevel.MODERATE,
) -> DecisionAction:
    return DecisionAction(
        description=description,
        cost=cost,
        expected_benefit=benefit,
        risk=risk,
        risk_score=0.4,
        affected_regions=["krishna_basin"],
        affected_population=50_000,
    )


def sample_objectives() -> list[Objective]:
    return [
        Objective(objective_id="minimize_flood_risk", description="Minimize downstream flood risk", weight=0.6),
        Objective(objective_id="maximize_supply", description="Maintain urban water supply", weight=0.4),
    ]


def sample_constraints() -> DecisionConstraints:
    return DecisionConstraints(
        budget=BudgetConstraint(max_cost=100.0),
        safety=SafetyConstraint(max_risk_score=0.8),
    )


def build_flood_decision_request() -> DecisionRequest:
    manager = DecisionManager()
    return manager.create(
        agent_id="flood_agent",
        decision_type=DecisionType.FLOOD,
        objectives=sample_objectives(),
        possible_actions=[
            sample_action("Issue flood warning", 5.0, 30.0),
            sample_action("Controlled reservoir release", 15.0, 60.0),
            sample_action("Emergency evacuation", 80.0, 90.0, RiskLevel.HIGH),
        ],
        constraints=sample_constraints(),
        context=DecisionContext(
            scenario=ScenarioContext(name="chennai_flood", region_id="chennai"),
        ),
        risk=RiskAssessment(level=RiskLevel.HIGH, score=0.75, affected_population=100_000),
        priority=DecisionPriority.HIGH,
        confidence=0.72,
        need_rl=True,
        need_simulation=True,
        need_other_agents=["water_resource_agent", "disaster_response_agent"],
        rationale=["Reservoir stressed", "River overflow imminent"],
    )


def build_water_decision_request() -> DecisionRequest:
    manager = DecisionManager()
    return manager.create(
        agent_id="water_resource_agent",
        decision_type=DecisionType.WATER,
        objectives=[
            Objective(objective_id="balance_supply", description="Balance supply and demand", weight=1.0),
        ],
        possible_actions=[
            sample_action("Gradual release", 8.0, 40.0),
            sample_action("Hold storage", 1.0, 20.0),
        ],
        risk=RiskAssessment(level=RiskLevel.MODERATE, score=0.5),
        priority=DecisionPriority.NORMAL,
        confidence=0.65,
        need_rl=False,
        need_simulation=True,
        need_other_agents=["flood_agent"],
    )


def build_climate_state() -> ClimateState:
    now = datetime.now(timezone.utc)
    return ClimateState(
        location=GeoLocation(latitude=13.0827, longitude=80.2707, region_id="chennai"),
        measurements=[
            ClimateMeasurement(
                variable=ClimateVariable.PRECIPITATION,
                value=120.0,
                unit="mm",
                timestamp=now,
            ),
        ],
        forecast_references=[
            ForecastReference(
                forecast_id="fcst-001",
                model_name="imd_gfs",
                horizon_hours=72,
                generated_at=now,
            ),
        ],
        scenario_id="scenario-001",
    )


@pytest.fixture
def decision_manager() -> DecisionManager:
    return DecisionManager()


@pytest.fixture
def decision_validator() -> DecisionValidator:
    return DecisionValidator()


@pytest.fixture
def decision_serializer() -> DecisionSerializer:
    return DecisionSerializer()


@pytest.fixture
def flood_request() -> DecisionRequest:
    return build_flood_decision_request()


@pytest.fixture
def water_request() -> DecisionRequest:
    return build_water_decision_request()
