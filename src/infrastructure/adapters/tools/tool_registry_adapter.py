"""Tool Registry adapter implementation (Story 10-3).

This adapter implements ToolRegistryProtocol with in-memory storage.
Tools are registered at startup and looked up by name during agent creation.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> log all lookups
- NFR5: 72 concurrent agents -> stateless, thread-safe implementation
"""

from __future__ import annotations

from structlog import get_logger

from src.application.ports.tool_registry import ToolRegistryProtocol
from src.infrastructure.adapters.tools.archon_tools import (
    ALL_ARCHON_TOOLS,
    TOOL_NAME_TO_CLASS,
)
from src.optional_deps.crewai import BaseTool

logger = get_logger(__name__)


class ToolRegistryAdapter(ToolRegistryProtocol):
    """In-memory tool registry implementation.

    Stores tool instances keyed by name and provides lookup methods.
    Thread-safe as tools are stateless and the registry is read-mostly.

    Attributes:
        _tools: Dictionary mapping tool names to Tool instances
    """

    def __init__(self) -> None:
        """Initialize empty tool registry."""
        self._tools: dict[str, BaseTool] = {}
        logger.info("tool_registry_initialized")

    def get_tool(self, name: str) -> BaseTool | None:
        """Get a tool by name.

        Args:
            name: The tool identifier (e.g., "insight_tool")

        Returns:
            The Tool instance if found, None otherwise.
        """
        tool = self._tools.get(name)
        if tool is None:
            # CT-11: Log when tool not found
            logger.warning(
                "tool_not_found",
                tool_name=name,
                available_tools=list(self._tools.keys()),
            )
        else:
            logger.debug(
                "tool_retrieved",
                tool_name=name,
            )
        return tool

    def get_tools(self, names: list[str]) -> list[BaseTool]:
        """Get multiple tools by name.

        Returns only the tools that exist in the registry.
        Missing tools are logged but not included in result.

        Args:
            names: List of tool identifiers

        Returns:
            List of Tool instances for names that exist.
        """
        tools: list[BaseTool] = []
        missing: list[str] = []

        for name in names:
            tool = self._tools.get(name)
            if tool is not None:
                tools.append(tool)
            else:
                missing.append(name)

        if missing:
            # CT-11: Log missing tools
            logger.warning(
                "tools_not_found",
                missing_tools=missing,
                found_count=len(tools),
                requested_count=len(names),
            )

        logger.debug(
            "tools_retrieved",
            found_count=len(tools),
            requested_count=len(names),
        )

        return tools

    def list_tools(self) -> list[str]:
        """List all registered tool names.

        Returns:
            List of all tool names in the registry.
        """
        return list(self._tools.keys())

    def register_tool(self, name: str, tool: BaseTool) -> None:
        """Register a tool with the given name.

        If a tool with this name already exists, it will be replaced.

        Args:
            name: The tool identifier
            tool: The Tool instance to register
        """
        existing = name in self._tools
        self._tools[name] = tool

        logger.info(
            "tool_registered",
            tool_name=name,
            replaced=existing,
            total_tools=len(self._tools),
        )

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered.

        Args:
            name: The tool identifier

        Returns:
            True if the tool exists, False otherwise.
        """
        return name in self._tools

    def count(self) -> int:
        """Get the number of registered tools.

        Returns:
            Number of tools in the registry.
        """
        return len(self._tools)


def create_tool_registry(
    include_all_archon_tools: bool = True,
) -> ToolRegistryAdapter:
    """Factory function to create a pre-populated ToolRegistry.

    Creates a new ToolRegistryAdapter and optionally registers all
    9 archon tools from archon_tools.py.

    Args:
        include_all_archon_tools: If True, pre-registers all 9 archon tools.
            Default is True for production use.

    Returns:
        Configured ToolRegistryAdapter instance
    """
    registry = ToolRegistryAdapter()

    if include_all_archon_tools:
        for tool_name in ALL_ARCHON_TOOLS:
            tool_class = TOOL_NAME_TO_CLASS[tool_name]
            # Instantiate the tool class
            tool_instance = tool_class()
            registry.register_tool(tool_name, tool_instance)

        logger.info(
            "tool_registry_created",
            tool_count=registry.count(),
            tools=registry.list_tools(),
        )

    return registry
