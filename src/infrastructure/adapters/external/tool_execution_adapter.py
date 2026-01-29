"""Tool Execution Adapter (Lane B).

Implements ToolExecutionProtocol by wrapping archon_tools via the
ToolRegistryAdapter. All tool outputs are draft artifacts until
verified - no tool output may be treated as "work completed" without
a result artifact pathway.

Principle: "No tool output may be treated as work completed without
a result artifact pathway."
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from structlog import get_logger

from src.application.ports.tool_execution import ToolExecutionProtocol
from src.domain.models.execution_program import (
    ResultType,
    TaskActivationRequest,
    TaskResultArtifact,
)
from src.infrastructure.adapters.tools.tool_registry_adapter import (
    ToolRegistryAdapter,
    create_tool_registry,
)

logger = get_logger(__name__)

ISO = "%Y-%m-%dT%H:%M:%SZ"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime(ISO)


def _new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


class ToolExecutionAdapter(ToolExecutionProtocol):
    """Lane B tool execution via archon_tools registry.

    Wraps the ToolRegistryAdapter to execute tasks and produce
    TaskResultArtifact with result_type=DRAFT_PRODUCED. All tool
    outputs are drafts until independently verified.
    """

    def __init__(
        self,
        registry: ToolRegistryAdapter | None = None,
        verbose: bool = False,
    ) -> None:
        self._registry = registry or create_tool_registry(include_all_archon_tools=True)
        self._verbose = verbose

        logger.info(
            "tool_execution_adapter_initialized",
            tool_count=self._registry.count(),
            verbose=verbose,
        )

    async def execute_task(self, request: TaskActivationRequest) -> TaskResultArtifact:
        """Execute a task by routing to the best matching tool.

        Selects a tool based on required_capabilities or falls back
        to the first available tool. Returns a DRAFT_PRODUCED artifact.
        """
        tool_name = self._select_tool(request)

        logger.info(
            "tool_execution_start",
            task_id=request.task_id,
            program_id=request.program_id,
            tool=tool_name,
        )

        tool = self._registry.get_tool(tool_name) if tool_name else None

        if tool is None:
            logger.warning(
                "tool_execution_no_tool_available",
                task_id=request.task_id,
                required_capabilities=request.required_capabilities,
            )
            return TaskResultArtifact(
                result_id=_new_id("res_"),
                task_id=request.task_id,
                request_id=request.request_id,
                result_type=ResultType.DRAFT_PRODUCED,
                action_reversibility=request.action_reversibility,
                deliverable_ref="",
                summary=f"No tool available for task {request.task_id}",
                submitted_at=_now_iso(),
            )

        # Execute via tool._run (CrewAI BaseTool interface)
        try:
            raw_output = tool._run(request.scope_description)

            result = TaskResultArtifact(
                result_id=_new_id("res_"),
                task_id=request.task_id,
                request_id=request.request_id,
                result_type=ResultType.DRAFT_PRODUCED,
                action_reversibility=request.action_reversibility,
                deliverable_ref="",
                summary=str(raw_output)[:500],
                submitted_at=_now_iso(),
            )

            logger.info(
                "tool_execution_complete",
                task_id=request.task_id,
                tool=tool_name,
                result_id=result.result_id,
            )

            return result

        except Exception as exc:
            logger.warning(
                "tool_execution_error",
                task_id=request.task_id,
                tool=tool_name,
                error=str(exc),
            )
            raise

    async def get_available_tools(self) -> list[str]:
        """Return names of all registered tools."""
        return self._registry.list_tools()

    async def check_tool_health(self, tool_name: str) -> bool:
        """Check if a specific tool is registered and available."""
        return self._registry.has_tool(tool_name)

    def _select_tool(self, request: TaskActivationRequest) -> str | None:
        """Select best tool for the request.

        Matches required_capabilities to tool names. Falls back to
        the first available tool if no capability match.
        """
        available = self._registry.list_tools()
        if not available:
            return None

        # Match by required capabilities
        for cap in request.required_capabilities:
            cap_lower = cap.lower().replace(" ", "_")
            for tool_name in available:
                if cap_lower in tool_name or tool_name in cap_lower:
                    return tool_name

        # Fallback: use logistics_tool for coordination tasks,
        # or the first available tool
        if "logistics_tool" in available:
            return "logistics_tool"
        return available[0]


def create_tool_executor(
    verbose: bool = False,
) -> ToolExecutionAdapter:
    """Factory function to create a ToolExecutionAdapter.

    Creates a ToolExecutionAdapter with a fully populated tool registry.

    Args:
        verbose: Enable verbose logging.

    Returns:
        Configured ToolExecutionAdapter instance.
    """
    registry = create_tool_registry(include_all_archon_tools=True)
    return ToolExecutionAdapter(registry=registry, verbose=verbose)
