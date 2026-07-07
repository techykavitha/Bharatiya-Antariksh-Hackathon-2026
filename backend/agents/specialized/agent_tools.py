"""Tool orchestration for specialized climate agents."""

from __future__ import annotations

import asyncio
import time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from backend.agents.tools.abstract_tool import AbstractTool, ToolInput, ToolResult
from backend.config.logger import get_logger
from backend.utils.constants import MAX_TOOL_CALLS_PER_INVOCATION
from backend.utils.errors import ToolNotFoundError

logger = get_logger(__name__)


class ToolExecutionMode(StrEnum):
    """Tool execution topology."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class ToolCallSpec(BaseModel):
    """Specification for a single tool invocation."""

    tool_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolExecutionResult(BaseModel):
    """Aggregated tool execution outcome."""

    results: list[ToolResult] = Field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    total_duration_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def all_succeeded(self) -> bool:
        return self.failure_count == 0 and bool(self.results)


class ToolManager:
    """
    Central tool registry and execution engine for specialized agents.

    Supports sequential and parallel tool execution with per-call timeouts.
    """

    def __init__(self, *, agent_id: str) -> None:
        self._agent_id = agent_id
        self._tools: dict[str, AbstractTool] = {}

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def register(self, tool: AbstractTool) -> None:
        self._tools[tool.name] = tool
        logger.debug("tool_registered", agent_id=self._agent_id, tool=tool.name)

    def unregister(self, tool_name: str) -> bool:
        removed = self._tools.pop(tool_name, None)
        return removed is not None

    def get(self, tool_name: str) -> AbstractTool:
        if tool_name not in self._tools:
            raise ToolNotFoundError(
                f"Tool '{tool_name}' is not registered on agent '{self._agent_id}'",
                details={"agent_id": self._agent_id, "tool": tool_name},
            )
        return self._tools[tool_name]

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self._tools

    def list_tools(self) -> list[AbstractTool]:
        return list(self._tools.values())

    def to_langchain_schemas(self) -> list[dict[str, Any]]:
        return [tool.to_langchain_tool_schema() for tool in self._tools.values()]

    async def execute(
        self,
        calls: list[ToolCallSpec],
        *,
        context: dict[str, Any] | None = None,
        mode: ToolExecutionMode = ToolExecutionMode.SEQUENTIAL,
    ) -> ToolExecutionResult:
        if not calls:
            return ToolExecutionResult()

        limited = calls[:MAX_TOOL_CALLS_PER_INVOCATION]
        if len(calls) > MAX_TOOL_CALLS_PER_INVOCATION:
            logger.warning(
                "tool_call_limit_exceeded",
                agent_id=self._agent_id,
                requested=len(calls),
                limit=MAX_TOOL_CALLS_PER_INVOCATION,
            )

        start = time.perf_counter()
        if mode == ToolExecutionMode.PARALLEL:
            results = await self._execute_parallel(limited, context=context or {})
        else:
            results = await self._execute_sequential(limited, context=context or {})

        elapsed = (time.perf_counter() - start) * 1000
        success = sum(1 for r in results if r.success)
        failure = len(results) - success
        return ToolExecutionResult(
            results=results,
            success_count=success,
            failure_count=failure,
            total_duration_ms=elapsed,
        )

    async def execute_single(
        self,
        tool_name: str,
        parameters: dict[str, Any] | None = None,
        *,
        context: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> ToolResult:
        spec = ToolCallSpec(
            tool_name=tool_name,
            parameters=parameters or {},
            timeout_seconds=timeout_seconds,
        )
        outcome = await self.execute([spec], context=context)
        if not outcome.results:
            raise ToolNotFoundError(
                f"No result returned for tool '{tool_name}'",
                details={"agent_id": self._agent_id, "tool": tool_name},
            )
        return outcome.results[0]

    async def _execute_sequential(
        self,
        calls: list[ToolCallSpec],
        *,
        context: dict[str, Any],
    ) -> list[ToolResult]:
        results: list[ToolResult] = []
        for spec in calls:
            result = await self._run_tool(spec, context=context)
            results.append(result)
        return results

    async def _execute_parallel(
        self,
        calls: list[ToolCallSpec],
        *,
        context: dict[str, Any],
    ) -> list[ToolResult]:
        tasks = [self._run_tool(spec, context=context) for spec in calls]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        results: list[ToolResult] = []
        for spec, outcome in zip(calls, outcomes, strict=True):
            if isinstance(outcome, Exception):
                results.append(
                    ToolResult(
                        tool_name=spec.tool_name,
                        success=False,
                        error=str(outcome),
                    ),
                )
            else:
                results.append(outcome)
        return results

    async def _run_tool(self, spec: ToolCallSpec, *, context: dict[str, Any]) -> ToolResult:
        tool = self.get(spec.tool_name)
        tool_input = ToolInput(parameters=spec.parameters, context=context)
        if spec.timeout_seconds:
            return await asyncio.wait_for(
                tool.run(tool_input),
                timeout=spec.timeout_seconds,
            )
        return await tool.run(tool_input)
