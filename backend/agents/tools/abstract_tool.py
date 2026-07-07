"""Abstract tool interface for Hyperion Climate Twin agents."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from backend.config.logger import Logger, get_logger
from backend.utils.enums import ToolCategory
from backend.utils.errors import ToolExecutionError, ToolValidationError


class ToolInput(BaseModel):
    """Validated input envelope for tool execution."""

    parameters: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Standardized output envelope returned by tool execution."""

    tool_name: str
    success: bool = True
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class AbstractTool(ABC):
    """
    Abstract base class for all Hyperion agent tools.

    Subclasses must implement ``_execute`` with domain-specific logic.
    The public ``run`` method handles validation, timing, and error wrapping.
    """

    def __init__(self) -> None:
        self._logger: Logger = get_logger(self.__class__.__name__)

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier used in agent tool registries."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for LLM tool selection."""

    @property
    @abstractmethod
    def category(self) -> ToolCategory:
        """Tool capability category."""

    @property
    def version(self) -> str:
        """Semantic version of the tool implementation."""
        return "1.0.0"

    @abstractmethod
    def get_input_schema(self) -> dict[str, Any]:
        """Return a JSON Schema describing accepted input parameters."""

    @abstractmethod
    async def _execute(self, tool_input: ToolInput) -> Any:
        """Domain-specific tool logic implemented by subclasses."""

    def validate_input(self, tool_input: ToolInput) -> None:
        """
        Validate tool input before execution.

        Override in subclasses for custom validation logic.
        Raises ``ToolValidationError`` on failure.
        """
        if not isinstance(tool_input.parameters, dict):
            raise ToolValidationError(
                f"Tool '{self.name}' requires parameters to be a dictionary",
                details={"tool": self.name},
            )

    async def run(self, tool_input: ToolInput) -> ToolResult:
        """
        Execute the tool with validation, timing, and error handling.

        This is the primary entry point called by ``BaseAgent.use_tools``.
        """
        start = time.perf_counter()
        try:
            self.validate_input(tool_input)
            output = await self._execute(tool_input)
            duration_ms = (time.perf_counter() - start) * 1000
            self._logger.info(
                "tool_executed",
                tool=self.name,
                duration_ms=round(duration_ms, 2),
            )
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=output,
                duration_ms=duration_ms,
            )
        except ToolValidationError:
            raise
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            self._logger.error(
                "tool_execution_failed",
                tool=self.name,
                error=str(exc),
                duration_ms=round(duration_ms, 2),
            )
            raise ToolExecutionError(
                f"Tool '{self.name}' execution failed: {exc}",
                details={"tool": self.name, "error": str(exc)},
            ) from exc

    def to_langchain_tool_schema(self) -> dict[str, Any]:
        """Export tool metadata in a LangChain-compatible tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.get_input_schema(),
        }
