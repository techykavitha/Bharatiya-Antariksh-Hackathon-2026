"""Infrastructure domain supervisor for agriculture, water, and urban systems."""

from __future__ import annotations

from backend.agents.domain.base_domain_supervisor import BaseDomainSupervisor
from backend.agents.domain.domain_context import (
    DomainAgentRegistration,
    DomainExecutionMode,
    DomainTask,
    DomainType,
)
from backend.agents.memory.memory_manager import MemoryManager


class InfrastructureSupervisor(BaseDomainSupervisor):
    """
    Domain supervisor for infrastructure and resource systems.

    Manages future specialized agents for agriculture, water resources,
    and urban planning. Supports water management, agricultural analysis,
    and urban climate assessment.
    """

    SUPERVISOR_ID = "infrastructure_supervisor"

    TASK_WATER_MANAGEMENT = "water_management"
    TASK_AGRICULTURAL_ANALYSIS = "agricultural_analysis"
    TASK_URBAN_CLIMATE = "urban_climate"

    AGENT_AGRICULTURE = "agriculture_agent"
    AGENT_WATER = "water_resource_agent"
    AGENT_URBAN = "urban_planning_agent"

    def __init__(self, *, memory: MemoryManager) -> None:
        super().__init__(memory=memory)

    @property
    def supervisor_id(self) -> str:
        return self.SUPERVISOR_ID

    @property
    def domain_type(self) -> DomainType:
        return DomainType.INFRASTRUCTURE

    @property
    def supported_tasks(self) -> list[DomainTask]:
        return [
            DomainTask(
                task_id=self.TASK_WATER_MANAGEMENT,
                name="Water Management",
                description="Manage and analyze water resource systems",
                keywords=["water", "reservoir", "irrigation", "supply", "groundwater", "basin"],
                preferred_agents=[self.AGENT_WATER, self.AGENT_AGRICULTURE],
                execution_mode=DomainExecutionMode.SEQUENTIAL,
            ),
            DomainTask(
                task_id=self.TASK_AGRICULTURAL_ANALYSIS,
                name="Agricultural Analysis",
                description="Analyze agricultural impacts and crop conditions",
                keywords=["agriculture", "crop", "farm", "harvest", "yield", "soil"],
                preferred_agents=[self.AGENT_AGRICULTURE, self.AGENT_WATER],
                execution_mode=DomainExecutionMode.PARALLEL,
            ),
            DomainTask(
                task_id=self.TASK_URBAN_CLIMATE,
                name="Urban Climate",
                description="Assess urban climate and planning considerations",
                keywords=["urban", "city", "planning", "infrastructure", "heat island", "zoning"],
                preferred_agents=[self.AGENT_URBAN, self.AGENT_WATER],
                execution_mode=DomainExecutionMode.SEQUENTIAL,
            ),
        ]

    @property
    def agent_slots(self) -> list[DomainAgentRegistration]:
        return [
            DomainAgentRegistration(
                agent_id=self.AGENT_AGRICULTURE,
                name="Agriculture Agent",
                description="Future specialized agent for agricultural analysis",
                supported_tasks=[self.TASK_AGRICULTURAL_ANALYSIS, self.TASK_WATER_MANAGEMENT],
            ),
            DomainAgentRegistration(
                agent_id=self.AGENT_WATER,
                name="Water Resource Agent",
                description="Future specialized agent for water resource management",
                supported_tasks=[self.TASK_WATER_MANAGEMENT, self.TASK_AGRICULTURAL_ANALYSIS],
            ),
            DomainAgentRegistration(
                agent_id=self.AGENT_URBAN,
                name="Urban Planning Agent",
                description="Future specialized agent for urban climate planning",
                supported_tasks=[self.TASK_URBAN_CLIMATE],
            ),
        ]
