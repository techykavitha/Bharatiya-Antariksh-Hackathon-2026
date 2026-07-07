"""Emergency domain supervisor for disaster and cyclone response orchestration."""

from __future__ import annotations

from backend.agents.domain.base_domain_supervisor import BaseDomainSupervisor
from backend.agents.domain.domain_context import (
    DomainAgentRegistration,
    DomainExecutionMode,
    DomainTask,
    DomainType,
)
from backend.agents.memory.memory_manager import MemoryManager


class EmergencySupervisor(BaseDomainSupervisor):
    """
    Domain supervisor for emergency and disaster response.

    Manages future specialized agents for cyclone tracking and disaster
    response coordination. Supports emergency planning, evacuation,
    cyclone monitoring, and disaster coordination.
    """

    SUPERVISOR_ID = "emergency_supervisor"

    TASK_EMERGENCY_PLANNING = "emergency_planning"
    TASK_EVACUATION = "evacuation"
    TASK_CYCLONE_MONITORING = "cyclone_monitoring"
    TASK_DISASTER_COORDINATION = "disaster_coordination"

    AGENT_CYCLONE = "cyclone_agent"
    AGENT_DISASTER = "disaster_response_agent"

    def __init__(self, *, memory: MemoryManager) -> None:
        super().__init__(memory=memory)

    @property
    def supervisor_id(self) -> str:
        return self.SUPERVISOR_ID

    @property
    def domain_type(self) -> DomainType:
        return DomainType.EMERGENCY

    @property
    def supported_tasks(self) -> list[DomainTask]:
        return [
            DomainTask(
                task_id=self.TASK_EMERGENCY_PLANNING,
                name="Emergency Planning",
                description="Plan emergency response operations",
                keywords=["emergency", "plan", "planning", "preparedness", "response plan"],
                preferred_agents=[self.AGENT_DISASTER, self.AGENT_CYCLONE],
                execution_mode=DomainExecutionMode.SEQUENTIAL,
            ),
            DomainTask(
                task_id=self.TASK_EVACUATION,
                name="Evacuation",
                description="Coordinate evacuation routes and logistics",
                keywords=["evacuation", "evacuate", "shelter", "route", "relief"],
                preferred_agents=[self.AGENT_DISASTER],
                execution_mode=DomainExecutionMode.SEQUENTIAL,
            ),
            DomainTask(
                task_id=self.TASK_CYCLONE_MONITORING,
                name="Cyclone Monitoring",
                description="Monitor cyclone development and track",
                keywords=["cyclone", "hurricane", "typhoon", "track", "landfall", "wind"],
                preferred_agents=[self.AGENT_CYCLONE, self.AGENT_DISASTER],
                execution_mode=DomainExecutionMode.PARALLEL,
            ),
            DomainTask(
                task_id=self.TASK_DISASTER_COORDINATION,
                name="Disaster Coordination",
                description="Coordinate multi-agency disaster response",
                keywords=["disaster", "coordination", "relief", "rescue", "crisis"],
                preferred_agents=[self.AGENT_DISASTER, self.AGENT_CYCLONE],
                execution_mode=DomainExecutionMode.PARALLEL,
            ),
        ]

    @property
    def agent_slots(self) -> list[DomainAgentRegistration]:
        return [
            DomainAgentRegistration(
                agent_id=self.AGENT_CYCLONE,
                name="Cyclone Agent",
                description="Future specialized agent for cyclone monitoring",
                supported_tasks=[self.TASK_CYCLONE_MONITORING, self.TASK_EMERGENCY_PLANNING],
            ),
            DomainAgentRegistration(
                agent_id=self.AGENT_DISASTER,
                name="Disaster Response Agent",
                description="Future specialized agent for disaster coordination",
                supported_tasks=[
                    self.TASK_DISASTER_COORDINATION,
                    self.TASK_EVACUATION,
                    self.TASK_EMERGENCY_PLANNING,
                ],
            ),
        ]
