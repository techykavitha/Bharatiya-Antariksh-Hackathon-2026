"""Abstract base agent for the Hyperion Climate Twin multi-agent system."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.agents.memory.interfaces import AgentMemory, MemoryEntry
from backend.agents.prompts.templates import REASONING_PROMPT, SYSTEM_PROMPT, PromptTemplate
from backend.agents.schemas.request import AgentRequest
from backend.agents.schemas.response import AgentResponse, ToolOutputRecord
from backend.agents.state.workflow_state import WorkflowState
from backend.agents.tools.abstract_tool import AbstractTool, ToolInput, ToolResult
from backend.config.logger import Logger, get_logger
from backend.utils.constants import MAX_TOOL_CALLS_PER_INVOCATION
from backend.utils.enums import AgentRole, AgentStatus
from backend.utils.errors import (
    AgentInitializationError,
    AgentInvocationError,
    ToolNotFoundError,
)


class BaseAgent(ABC):
    """
    Abstract base class that every Hyperion agent must inherit from.

    Provides the canonical lifecycle (initialize → invoke → respond),
    tool orchestration, memory access, and structured reasoning hooks.
    Domain and specialized agents override ``reason`` and ``generate_response``.
    """

    def __init__(
        self,
        agent_id: str,
        role: AgentRole,
        *,
        description: str = "",
        tools: list[AbstractTool] | None = None,
        memory_backends: dict[str, AgentMemory] | None = None,
        system_prompt: PromptTemplate | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.role = role
        self.description = description
        self._tools: dict[str, AbstractTool] = {
            tool.name: tool for tool in (tools or [])
        }
        self._memory_backends: dict[str, AgentMemory] = memory_backends or {}
        self._system_prompt = system_prompt or SYSTEM_PROMPT
        self._logger: Logger = get_logger(f"agent.{agent_id}")
        self._status: AgentStatus = AgentStatus.IDLE
        self._initialized: bool = False
        self._reasoning_trace: list[str] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def status(self) -> AgentStatus:
        """Current lifecycle status of the agent."""
        return self._status

    @property
    def is_initialized(self) -> bool:
        """Return True after ``initialize`` has completed successfully."""
        return self._initialized

    @property
    def tool_names(self) -> list[str]:
        """Names of tools registered on this agent."""
        return list(self._tools.keys())

    @property
    def capabilities(self) -> list[str]:
        """Human-readable capability list for system prompt rendering."""
        caps = [self.description] if self.description else []
        caps.extend(f"tool:{name}" for name in self.tool_names)
        return caps

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """
        Prepare the agent for invocation.

        Subclasses may override ``_on_initialize`` to perform async setup
        (model loading, connection pooling, etc.).
        """
        self._status = AgentStatus.INITIALIZING
        self._logger.info("agent_initializing", agent_id=self.agent_id, role=self.role)
        try:
            await self._on_initialize()
            self._initialized = True
            self._status = AgentStatus.IDLE
            self._logger.info("agent_initialized", agent_id=self.agent_id)
        except Exception as exc:
            self._status = AgentStatus.FAILED
            raise AgentInitializationError(
                f"Agent '{self.agent_id}' failed to initialize: {exc}",
                details={"agent_id": self.agent_id},
            ) from exc

    async def _on_initialize(self) -> None:
        """Hook for subclass-specific async initialization logic."""

    async def invoke(self, request: AgentRequest) -> AgentResponse:
        """
        Primary entry point for agent execution.

        Orchestrates reasoning, tool use, memory access, and response
        generation within a single standardized pipeline.
        """
        if not self._initialized:
            await self.initialize()

        self._status = AgentStatus.REASONING
        self._reasoning_trace = []
        self._logger.info(
            "agent_invoked",
            agent_id=self.agent_id,
            request_id=request.request_id,
        )

        try:
            reasoning = await self.reason(request)
            self._reasoning_trace.extend(reasoning)

            tool_results = await self._execute_planned_tools(request, reasoning)
            memory_refs = await self._persist_invocation_memory(request, tool_results)

            self._status = AgentStatus.EXECUTING
            response = await self.generate_response(
                request,
                reasoning=self._reasoning_trace,
                tool_results=tool_results,
                memory_references=memory_refs,
            )
            self._status = AgentStatus.COMPLETED
            self._logger.info(
                "agent_completed",
                agent_id=self.agent_id,
                request_id=request.request_id,
            )
            return response

        except Exception as exc:
            self._status = AgentStatus.FAILED
            self._logger.error(
                "agent_failed",
                agent_id=self.agent_id,
                request_id=request.request_id,
                error=str(exc),
            )
            raise AgentInvocationError(
                f"Agent '{self.agent_id}' invocation failed: {exc}",
                details={"agent_id": self.agent_id, "request_id": request.request_id},
            ) from exc

    # ------------------------------------------------------------------
    # Abstract hooks
    # ------------------------------------------------------------------

    @abstractmethod
    async def reason(self, request: AgentRequest) -> list[str]:
        """
        Perform structured reasoning on the request.

        Returns an ordered list of reasoning step descriptions.
        """

    @abstractmethod
    async def generate_response(
        self,
        request: AgentRequest,
        *,
        reasoning: list[str],
        tool_results: list[ToolResult],
        memory_references: list[str],
    ) -> AgentResponse:
        """Synthesize the final ``AgentResponse`` from reasoning and tool outputs."""

    # ------------------------------------------------------------------
    # Tool orchestration
    # ------------------------------------------------------------------

    def register_tool(self, tool: AbstractTool) -> None:
        """Register a tool available to this agent."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> AbstractTool:
        """Retrieve a registered tool by name."""
        if name not in self._tools:
            raise ToolNotFoundError(
                f"Tool '{name}' is not registered on agent '{self.agent_id}'",
                details={"agent_id": self.agent_id, "tool": name},
            )
        return self._tools[name]

    async def use_tools(
        self,
        tool_calls: list[tuple[str, dict[str, Any]]],
        *,
        context: dict[str, Any] | None = None,
    ) -> list[ToolResult]:
        """
        Execute one or more tools sequentially.

        Parameters
        ----------
        tool_calls:
            List of ``(tool_name, parameters)`` tuples.
        context:
            Shared execution context passed to each tool.

        Raises
        ------
        ToolNotFoundError
            If a requested tool is not registered.
        """
        if len(tool_calls) > MAX_TOOL_CALLS_PER_INVOCATION:
            self._logger.warning(
                "tool_call_limit_exceeded",
                requested=len(tool_calls),
                limit=MAX_TOOL_CALLS_PER_INVOCATION,
            )
            tool_calls = tool_calls[:MAX_TOOL_CALLS_PER_INVOCATION]

        results: list[ToolResult] = []
        shared_context = context or {}

        for tool_name, parameters in tool_calls:
            tool = self.get_tool(tool_name)
            tool_input = ToolInput(parameters=parameters, context=shared_context)
            result = await tool.run(tool_input)
            results.append(result)
            self._logger.debug(
                "tool_used",
                agent_id=self.agent_id,
                tool=tool_name,
                success=result.success,
            )

        return results

    # ------------------------------------------------------------------
    # Memory access
    # ------------------------------------------------------------------

    def register_memory_backend(self, name: str, backend: AgentMemory) -> None:
        """Attach a memory backend to this agent."""
        self._memory_backends[name] = backend

    def _resolve_memory_backend(self, backend: str | None = None) -> AgentMemory:
        """Resolve a memory backend by name, defaulting to the first registered."""
        if backend and backend in self._memory_backends:
            return self._memory_backends[backend]
        if len(self._memory_backends) == 1:
            return next(iter(self._memory_backends.values()))
        if not self._memory_backends:
            raise AgentInvocationError(
                f"Agent '{self.agent_id}' has no memory backends registered",
                details={"agent_id": self.agent_id},
            )
        raise AgentInvocationError(
            f"Agent '{self.agent_id}' requires explicit backend selection; "
            f"available: {list(self._memory_backends)}",
            details={"agent_id": self.agent_id},
        )

    async def write_memory(
        self,
        key: str,
        value: Any,
        *,
        backend: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Write a value to the configured memory backend."""
        mem = self._resolve_memory_backend(backend)
        await mem.write(key, value, metadata=metadata)
        self._logger.debug(
            "memory_written",
            agent_id=self.agent_id,
            key=key,
            backend=mem.backend_name,
        )

    async def read_memory(
        self,
        key: str,
        *,
        backend: str | None = None,
    ) -> MemoryEntry | None:
        """Read a value from the configured memory backend."""
        mem = self._resolve_memory_backend(backend)
        entry = await mem.read(key)
        self._logger.debug(
            "memory_read",
            agent_id=self.agent_id,
            key=key,
            found=entry is not None,
            backend=mem.backend_name,
        )
        return entry

    # ------------------------------------------------------------------
    # Prompt helpers
    # ------------------------------------------------------------------

    def render_system_prompt(self, **extra: Any) -> str:
        """Render the agent's system prompt with identity and capabilities."""
        return self._system_prompt.render(
            agent_name=self.agent_id,
            agent_role=self.role.value,
            capabilities="\n".join(f"- {cap}" for cap in self.capabilities),
            **extra,
        )

    def render_reasoning_prompt(self, request: AgentRequest) -> str:
        """Render the standard reasoning prompt for a given request."""
        context_parts: list[str] = []
        if request.climate_state:
            context_parts.append(f"Climate state: {request.climate_state.model_dump_json()}")
        if request.current_scenario:
            context_parts.append(f"Scenario: {request.current_scenario}")
        if request.context:
            context_parts.append(f"Additional context: {request.context}")

        return REASONING_PROMPT.render(
            query=request.query,
            context="\n".join(context_parts) or "No additional context.",
            available_tools=", ".join(self.tool_names) or "None",
        )

    # ------------------------------------------------------------------
    # LangGraph integration
    # ------------------------------------------------------------------

    async def as_graph_node(self, state: WorkflowState) -> dict[str, Any]:
        """
        Adapt this agent as a LangGraph node function.

        Reads the current ``WorkflowState``, constructs an ``AgentRequest``,
        invokes the agent, and returns a partial state update.
        """
        from backend.agents.state.conversation_state import ConversationTurn

        conversation = state.get("conversation")
        query = ""
        if conversation:
            query = conversation.last_user_message() or ""
        if not query and state.get("messages"):
            last_msg = state["messages"][-1]
            query = getattr(last_msg, "content", str(last_msg))

        request = AgentRequest(
            query=query,
            conversation=conversation,
            active_user=state.get("active_user"),
            climate_state=state.get("climate_state"),
            current_scenario=state.get("current_scenario"),
            scenario_type=state.get("scenario_type"),
            context=state.get("metadata", {}),
        )

        response = await self.invoke(request)

        update: dict[str, Any] = {
            "called_agents": [self.agent_id],
            "agent_status": response.status,
            "tool_outputs": {
                record.tool_name: record.output for record in response.tool_outputs
            },
            "memory_references": response.memory_references,
            "knowledge_graph_references": response.knowledge_graph_references,
            "forecast_references": [
                {"ref": ref} for ref in response.forecast_references
            ],
        }

        if conversation:
            conversation.append_turn(
                ConversationTurn(
                    role="assistant",
                    content=response.content,
                    agent_id=self.agent_id,
                ),
            )
            update["conversation"] = conversation

        if response.failed:
            update["error"] = response.error

        return update

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _execute_planned_tools(
        self,
        request: AgentRequest,
        reasoning: list[str],
    ) -> list[ToolResult]:
        """Execute tools planned during reasoning. Override for custom planning."""
        if not request.tool_names:
            return []
        tool_calls = [(name, request.context) for name in request.tool_names]
        return await self.use_tools(tool_calls, context=request.context)

    async def _persist_invocation_memory(
        self,
        request: AgentRequest,
        tool_results: list[ToolResult],
    ) -> list[str]:
        """Persist invocation artifacts to memory. Returns reference keys."""
        if not self._memory_backends:
            return []

        ref_key = f"{self.agent_id}:{request.request_id}"
        await self.write_memory(
            ref_key,
            {
                "request_id": request.request_id,
                "reasoning": self._reasoning_trace,
                "tool_results": [r.model_dump() for r in tool_results],
            },
            metadata={"agent_id": self.agent_id, "type": "invocation_record"},
        )
        return [ref_key]

    @staticmethod
    def _tool_results_to_records(results: list[ToolResult]) -> list[ToolOutputRecord]:
        """Convert ``ToolResult`` instances to ``ToolOutputRecord`` schemas."""
        return [
            ToolOutputRecord(
                tool_name=r.tool_name,
                output=r.output,
                success=r.success,
                error=r.error,
                duration_ms=r.duration_ms,
            )
            for r in results
        ]
