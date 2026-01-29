"""Port definition for Tool Execution operations (Lane B).

This port defines the interface for executing tasks via internal
tool adapters (archon_tools). Tools are artifact producers - no tool
output may be treated as "work completed" without a result artifact pathway.

Principle: "No tool output may be treated as work completed without
a result artifact pathway."
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models.execution_program import (
    TaskActivationRequest,
    TaskResultArtifact,
)


class ToolExecutionProtocol(ABC):
    """Port for Lane B tool execution.

    Implementations wrap internal tool adapters (archon_tools)
    to produce draft artifacts from task activation requests.
    """

    @abstractmethod
    async def execute_task(
        self, request: TaskActivationRequest
    ) -> TaskResultArtifact:
        """Execute a task via internal tools.

        Args:
            request: The task activation request to execute.

        Returns:
            A TaskResultArtifact with the execution results.
        """
        ...

    @abstractmethod
    async def get_available_tools(self) -> list[str]:
        """Return names of available tools.

        Returns:
            List of tool identifiers that can handle requests.
        """
        ...

    @abstractmethod
    async def check_tool_health(self, tool_name: str) -> bool:
        """Check if a specific tool is available and healthy.

        Args:
            tool_name: The tool identifier to check.

        Returns:
            True if the tool is available, False otherwise.
        """
        ...
