"""Shared enumerations for the Hyperion Climate Twin AI layer."""

from __future__ import annotations

from enum import StrEnum


class AgentRole(StrEnum):
    """Hierarchical role classification for agents in the multi-agent system."""

    SUPERVISOR = "supervisor"
    DOMAIN = "domain"
    SPECIALIZED = "specialized"
    TOOL = "tool"


class AgentStatus(StrEnum):
    """Lifecycle status of an agent invocation."""

    IDLE = "idle"
    INITIALIZING = "initializing"
    REASONING = "reasoning"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"


class MemoryBackend(StrEnum):
    """Supported memory persistence backends."""

    REDIS = "redis"
    VECTOR = "vector"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    DIGITAL_TWIN = "digital_twin"


class ToolCategory(StrEnum):
    """Classification of tool capabilities."""

    RETRIEVAL = "retrieval"
    SIMULATION = "simulation"
    FORECAST = "forecast"
    GEOSPATIAL = "geospatial"
    ANALYSIS = "analysis"
    COMMUNICATION = "communication"


class ClimateVariable(StrEnum):
    """Canonical climate variables tracked across the digital twin."""

    TEMPERATURE = "temperature"
    PRECIPITATION = "precipitation"
    HUMIDITY = "humidity"
    WIND_SPEED = "wind_speed"
    WIND_DIRECTION = "wind_direction"
    SEA_LEVEL = "sea_level"
    PRESSURE = "pressure"
    SOIL_MOISTURE = "soil_moisture"


class SimulationStatus(StrEnum):
    """Status of an active climate simulation run."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScenarioType(StrEnum):
    """Types of climate scenarios the system can model."""

    BASELINE = "baseline"
    FLOOD = "flood"
    CYCLONE = "cyclone"
    DROUGHT = "drought"
    HEATWAVE = "heatwave"
    CUSTOM = "custom"


class LogLevel(StrEnum):
    """Application log severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Environment(StrEnum):
    """Deployment environment identifiers."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"
