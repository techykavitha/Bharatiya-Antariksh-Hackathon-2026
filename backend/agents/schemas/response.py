"""Response schemas for agent invocations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.utils.enums import AgentStatus


class ToolOutputRecord(BaseModel):
    """Record of a single tool execution within an agent invocation."""

    tool_name: str
    output: Any
    success: bool = True
    error: str | None = None
    duration_ms: float | None = None


class AgentResponse(BaseModel):
    """
    Standardized output payload returned by any agent.

    Provides the natural-language answer, structured data, execution
    trace metadata, and references to memory or knowledge artifacts.
    """

    response_id: str = Field(default_factory=lambda: str(uuid4()))
    request_id: str
    agent_id: str
    content: str = Field(..., description="Primary natural-language response")
    status: AgentStatus = AgentStatus.COMPLETED
    structured_output: dict[str, Any] = Field(default_factory=dict)
    tool_outputs: list[ToolOutputRecord] = Field(default_factory=list)
    memory_references: list[str] = Field(default_factory=list)
    knowledge_graph_references: list[str] = Field(default_factory=list)
    forecast_references: list[str] = Field(default_factory=list)
    delegated_to: list[str] = Field(
        default_factory=list,
        description="Agent IDs that were invoked as part of this response",
    )
    reasoning_trace: list[str] = Field(
        default_factory=list,
        description="Ordered reasoning steps for auditability",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_success(self) -> bool:
        """Return True when the agent completed without failure."""
        return self.status == AgentStatus.COMPLETED and self.error is None

    @property
    def failed(self) -> bool:
        """Return True when the agent invocation failed."""
        return self.status == AgentStatus.FAILED or self.error is not None
