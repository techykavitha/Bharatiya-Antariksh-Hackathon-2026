"""Environmental domain supervisor for weather and climate risk orchestration."""

from __future__ import annotations

from backend.agents.domain.base_domain_supervisor import BaseDomainSupervisor
from backend.agents.domain.domain_context import (
    DomainAgentRegistration,
    DomainExecutionMode,
    DomainTask,
    DomainType,
)
from backend.agents.memory.memory_manager import MemoryManager


class EnvironmentalSupervisor(BaseDomainSupervisor):
    """
    Domain supervisor for environmental hazards and monitoring.

    Manages future specialized agents for flood, heatwave, and air quality.
    Supports weather risk assessment, climate analysis, and environmental monitoring.
    """

    SUPERVISOR_ID = "environmental_supervisor"

    TASK_WEATHER_RISK = "weather_risk"
    TASK_CLIMATE_ANALYSIS = "climate_analysis"
    TASK_ENV_MONITORING = "environmental_monitoring"

    AGENT_FLOOD = "flood_agent"
    AGENT_HEATWAVE = "heatwave_agent"
    AGENT_AIR_QUALITY = "air_quality_agent"

    def __init__(self, *, memory: MemoryManager) -> None:
        super().__init__(memory=memory)

    @property
    def supervisor_id(self) -> str:
        return self.SUPERVISOR_ID

    @property
    def domain_type(self) -> DomainType:
        return DomainType.ENVIRONMENTAL

    @property
    def supported_tasks(self) -> list[DomainTask]:
        return [
            DomainTask(
                task_id=self.TASK_WEATHER_RISK,
                name="Weather Risk",
                description="Assess weather-related risks and exposure",
                keywords=["weather", "risk", "rainfall", "storm", "flood", "drought", "hazard"],
                preferred_agents=[self.AGENT_FLOOD, self.AGENT_HEATWAVE],
                execution_mode=DomainExecutionMode.PARALLEL,
            ),
            DomainTask(
                task_id=self.TASK_CLIMATE_ANALYSIS,
                name="Climate Analysis",
                description="Analyze climate trends and variability",
                keywords=["climate", "analysis", "trend", "temperature", "precipitation", "variability"],
                preferred_agents=[self.AGENT_HEATWAVE, self.AGENT_FLOOD],
                execution_mode=DomainExecutionMode.SEQUENTIAL,
            ),
            DomainTask(
                task_id=self.TASK_ENV_MONITORING,
                name="Environmental Monitoring",
                description="Monitor environmental conditions and air quality",
                keywords=["monitor", "monitoring", "air quality", "pollution", "aqi", "environment"],
                preferred_agents=[self.AGENT_AIR_QUALITY, self.AGENT_FLOOD],
                execution_mode=DomainExecutionMode.SEQUENTIAL,
            ),
        ]

    @property
    def agent_slots(self) -> list[DomainAgentRegistration]:
        return [
            DomainAgentRegistration(
                agent_id=self.AGENT_FLOOD,
                name="Flood Agent",
                description="Future specialized agent for flood risk and inundation analysis",
                supported_tasks=[self.TASK_WEATHER_RISK, self.TASK_CLIMATE_ANALYSIS],
            ),
            DomainAgentRegistration(
                agent_id=self.AGENT_HEATWAVE,
                name="Heatwave Agent",
                description="Future specialized agent for heatwave detection and impact",
                supported_tasks=[self.TASK_WEATHER_RISK, self.TASK_CLIMATE_ANALYSIS],
            ),
            DomainAgentRegistration(
                agent_id=self.AGENT_AIR_QUALITY,
                name="Air Quality Agent",
                description="Future specialized agent for air quality monitoring",
                supported_tasks=[self.TASK_ENV_MONITORING],
            ),
        ]
