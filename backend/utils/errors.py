"""Custom exception hierarchy for the Hyperion Climate Twin AI layer."""

from __future__ import annotations

from typing import Any


class HyperionError(Exception):
    """Base exception for all Hyperion Climate Twin errors."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


class ConfigurationError(HyperionError):
    """Raised when application configuration is invalid or missing."""


class DependencyNotFoundError(HyperionError):
    """Raised when a requested dependency is not registered in the DI container."""


class DependencyRegistrationError(HyperionError):
    """Raised when dependency registration fails due to conflicts or invalid state."""


class AgentError(HyperionError):
    """Base exception for agent-related failures."""


class AgentInitializationError(AgentError):
    """Raised when an agent fails during initialization."""


class AgentInvocationError(AgentError):
    """Raised when an agent invocation fails at runtime."""


class AgentReasoningError(AgentError):
    """Raised when the agent reasoning loop encounters an unrecoverable error."""


class ToolError(HyperionError):
    """Base exception for tool execution failures."""


class ToolNotFoundError(ToolError):
    """Raised when a requested tool is not registered or available."""


class ToolExecutionError(ToolError):
    """Raised when a tool fails during execution."""


class ToolValidationError(ToolError):
    """Raised when tool input validation fails."""


class MemoryError(HyperionError):
    """Base exception for memory subsystem failures."""


class MemoryReadError(MemoryError):
    """Raised when reading from a memory backend fails."""


class MemoryWriteError(MemoryError):
    """Raised when writing to a memory backend fails."""


class MemoryNotFoundError(MemoryError):
    """Raised when a memory entry cannot be located."""


class StateError(HyperionError):
    """Base exception for workflow state management failures."""


class StateValidationError(StateError):
    """Raised when workflow state fails schema validation."""


class StateTransitionError(StateError):
    """Raised when an invalid state transition is attempted."""


class SchemaValidationError(HyperionError):
    """Raised when request/response schema validation fails."""
