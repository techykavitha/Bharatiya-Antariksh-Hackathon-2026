"""Dedicated tools for disaster response coordination and planning."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.agents.specialized.disaster_response.disaster_context import DisasterInputs
from backend.agents.specialized.disaster_response.disaster_models import EmergencyPriority
from backend.agents.tools.abstract_tool import AbstractTool, ToolInput
from backend.utils.enums import ToolCategory


def _extract_inputs(tool_input: ToolInput) -> DisasterInputs:
    ctx = {**tool_input.context, **tool_input.parameters}
    return DisasterInputs.from_request_context(ctx)


def _region(tool_input: ToolInput) -> str:
    return _extract_inputs(tool_input).region_id or "unknown_region"


def _schema(*properties: str) -> dict[str, Any]:
    return {"type": "object", "properties": {name: {"type": "number"} for name in properties}}


class EmergencyResourceTool(AbstractTool):
    @property
    def name(self) -> str:
        return "emergency_resource_tool"

    @property
    def description(self) -> str:
        return "Assess emergency relief resource availability and gaps"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("affected_population", "hazard_count")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        pop = sum(h.affected_population for h in inputs.hazard_agent_outputs.values())
        hazard_count = len(inputs.hazard_agent_outputs)
        food_units = max(pop // 500, hazard_count * 1000)
        water_litres = max(pop * 3, hazard_count * 5000)
        tents = max(pop // 200, hazard_count * 50)
        gap = hazard_count >= 2 or pop > 500_000
        return {
            "region": _region(tool_input),
            "food_packets": food_units,
            "water_litres": water_litres,
            "shelter_tents": tents,
            "resource_gap": gap,
            "urgency": EmergencyPriority.SEVERE.value if gap else EmergencyPriority.ELEVATED.value,
        }


class ShelterTool(AbstractTool):
    @property
    def name(self) -> str:
        return "shelter_tool"

    @property
    def description(self) -> str:
        return "Plan emergency shelter capacity and assignments"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.PLANNING

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        pop = sum(h.affected_population for h in inputs.hazard_agent_outputs.values())
        capacity = max(5000, pop // 10)
        shelters = [
            {"shelter_id": f"shelter-{d.lower().replace(' ', '_')}", "district": d, "capacity": capacity // max(len(inputs.districts), 1)}
            for d in (inputs.districts or ["central_zone"])
        ]
        return {
            "region": _region(tool_input),
            "total_capacity": capacity,
            "shelters": shelters,
            "activation_required": pop > 50_000,
        }


class HospitalTool(AbstractTool):
    @property
    def name(self) -> str:
        return "hospital_tool"

    @property
    def description(self) -> str:
        return "Assess hospital capacity and medical surge requirements"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("affected_population")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        pop = sum(h.affected_population for h in inputs.hazard_agent_outputs.values())
        hospitals = tool_input.context.get("hospitals", [
            {"hospital_id": "hosp-01", "name": "District Hospital", "beds": 250},
            {"hospital_id": "hosp-02", "name": "Medical College", "beds": 500},
        ])
        total_beds = sum(h.get("beds", 100) for h in hospitals if isinstance(h, dict))
        surge_needed = pop > total_beds * 5
        ambulances = max(pop // 5000, 10)
        return {
            "region": _region(tool_input),
            "hospitals": hospitals,
            "total_bed_capacity": total_beds,
            "ambulances_required": ambulances,
            "medical_surge_required": surge_needed,
            "trauma_capacity_pct": min(100.0, pop / max(total_beds, 1) * 10),
        }


class RoadNetworkTool(AbstractTool):
    @property
    def name(self) -> str:
        return "road_network_tool"

    @property
    def description(self) -> str:
        return "Assess road network vulnerability and evacuation corridors"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        corridors = tool_input.context.get("evacuation_corridors", [
            "NH-16", "SH-42", "Coastal Highway",
        ])
        closures = []
        for h in inputs.hazard_agent_outputs.values():
            if h.hazard_type.value in ("flood", "cyclone"):
                closures.extend(corridors[:2])
        return {
            "region": _region(tool_input),
            "evacuation_corridors": corridors,
            "recommended_closures": list(dict.fromkeys(closures)),
            "road_closure_required": len(closures) > 0,
        }


class PopulationTool(AbstractTool):
    @property
    def name(self) -> str:
        return "population_tool"

    @property
    def description(self) -> str:
        return "Estimate total affected population across all hazards"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("population_density")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        density = float(tool_input.context.get("population_density", 6000.0))
        hazard_pop = sum(h.affected_population for h in inputs.hazard_agent_outputs.values())
        district_pop = int(density * 40 * max(len(inputs.districts), 1))
        total = max(hazard_pop, district_pop)
        vulnerable = int(total * 0.22)
        return {
            "region": _region(tool_input),
            "total_affected_population": total,
            "vulnerable_population": vulnerable,
            "high_impact": total >= 500_000,
            "districts": inputs.districts,
        }


class CriticalInfrastructureTool(AbstractTool):
    @property
    def name(self) -> str:
        return "critical_infrastructure_tool"

    @property
    def description(self) -> str:
        return "Identify critical infrastructure requiring protection"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        infra = tool_input.context.get("critical_infrastructure", [
            {"id": "power-01", "name": "Grid Substation", "category": "power"},
            {"id": "water-01", "name": "Water Treatment Plant", "category": "water"},
            {"id": "hosp-01", "name": "District Hospital", "category": "healthcare"},
            {"id": "port-01", "name": "Major Port", "category": "transport"},
        ])
        at_risk = [i for i in infra if isinstance(i, dict)]
        return {
            "region": _region(tool_input),
            "infrastructure_assets": at_risk,
            "critical_count": len(at_risk),
            "protection_required": len(at_risk) >= 2,
        }


class ForecastTool(AbstractTool):
    @property
    def name(self) -> str:
        return "forecast_tool"

    @property
    def description(self) -> str:
        return "Assess multi-hazard forecast horizon for response planning"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FORECAST

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"horizon_hours": {"type": "number"}}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        horizon = float(tool_input.context.get("forecast_horizon_hours", 72.0))
        inputs = _extract_inputs(tool_input)
        escalating = len(inputs.hazard_agent_outputs) >= 2
        return {
            "region": _region(tool_input),
            "forecast_horizon_hours": horizon,
            "escalating_multi_hazard": escalating,
            "forecast_available": inputs.forecast_available,
        }


class DigitalTwinTool(AbstractTool):
    @property
    def name(self) -> str:
        return "digital_twin_tool"

    @property
    def description(self) -> str:
        return "Access disaster scenario digital twin state"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SIMULATION

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"twin_id": {"type": "string"}}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        twin = tool_input.context.get("digital_twin_state") or {}
        layers = twin.get("layers", {}) if isinstance(twin, dict) else {}
        emergency = layers.get("emergency", layers.get("disaster", {}))
        return {
            "twin_id": tool_input.context.get("twin_id"),
            "digital_twin_available": bool(twin),
            "emergency_layers": emergency if isinstance(emergency, dict) else {},
            "active_scenario": twin.get("scenario_id") if isinstance(twin, dict) else None,
        }


class KnowledgeGraphTool(AbstractTool):
    @property
    def name(self) -> str:
        return "knowledge_graph_tool"

    @property
    def description(self) -> str:
        return "Surface Climate Knowledge Graph disaster coordination insights"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        from backend.agents.specialized.disaster_response.disaster_context import KnowledgeGraphInsights
        raw = tool_input.context.get("ckg_insights") or tool_input.parameters.get("ckg_insights")
        if isinstance(raw, KnowledgeGraphInsights):
            insights = raw
        elif isinstance(raw, dict):
            insights = KnowledgeGraphInsights.model_validate(raw)
        else:
            insights = KnowledgeGraphInsights()
        return {
            "region": _region(tool_input),
            "affected_infrastructure": insights.affected_infrastructure,
            "population_dependencies": insights.population_dependencies,
            "cascade_impacts": insights.cascade_impacts,
            "historical_responses": insights.historical_responses,
            "query_count": insights.query_count,
            "ckg_available": insights.query_count > 0,
        }


class ReliefInventoryTool(AbstractTool):
    @property
    def name(self) -> str:
        return "relief_inventory_tool"

    @property
    def description(self) -> str:
        return "Inventory available relief supplies and logistics capacity"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inventory = tool_input.context.get("relief_inventory", {
            "food_packets": 50_000,
            "water_litres": 200_000,
            "medical_kits": 2000,
            "generators": 150,
            "vehicles": 80,
        })
        inputs = _extract_inputs(tool_input)
        pop = sum(h.affected_population for h in inputs.hazard_agent_outputs.values())
        food_need = max(pop // 500, 1000)
        shortfall = inventory.get("food_packets", 0) < food_need
        return {
            "region": _region(tool_input),
            "inventory": inventory,
            "estimated_food_need": food_need,
            "inventory_shortfall": shortfall,
        }


class CommunicationTool(AbstractTool):
    @property
    def name(self) -> str:
        return "communication_tool"

    @property
    def description(self) -> str:
        return "Plan emergency communication channels and alert dissemination"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.PLANNING

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        channels = ["SMS", "Radio", "Siren", "Social Media", "Door-to-door"]
        priority = EmergencyPriority.SEVERE if len(inputs.hazard_agent_outputs) >= 2 else EmergencyPriority.ELEVATED
        return {
            "region": _region(tool_input),
            "channels": channels,
            "alert_priority": priority.value,
            "multilingual_required": True,
            "communication_plan_ready": True,
        }


def create_disaster_tools() -> list[AbstractTool]:
    return [
        EmergencyResourceTool(),
        ShelterTool(),
        HospitalTool(),
        RoadNetworkTool(),
        PopulationTool(),
        CriticalInfrastructureTool(),
        ForecastTool(),
        DigitalTwinTool(),
        KnowledgeGraphTool(),
        ReliefInventoryTool(),
        CommunicationTool(),
    ]


ALL_DISASTER_TOOL_NAMES: list[str] = [t().name for t in (
    EmergencyResourceTool, ShelterTool, HospitalTool, RoadNetworkTool,
    PopulationTool, CriticalInfrastructureTool, ForecastTool,
    DigitalTwinTool, KnowledgeGraphTool, ReliefInventoryTool, CommunicationTool,
)]
