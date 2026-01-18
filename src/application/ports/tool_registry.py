"""Tool Registry port definition (Story 10-3).

Defines the abstract interface for tool registration and lookup.
Tools are mapped to archons via suggested_tools in ArchonProfile.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> log all tool lookups, never silently fail
- CT-12: Witnessing creates accountability -> tool outputs may flow through FR9 pipeline
- NFR5: 72 concurrent agent deliberations -> tools must be stateless and thread-safe
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crewai_tools import BaseTool

__all__ = [
    "ToolRegistryProtocol",
]


class ToolRegistryProtocol(ABC):
    """Abstract interface for tool registration and lookup.

    The tool registry maps tool names (e.g., "insight_tool") to
    CrewAI Tool instances. This enables archons to use domain-specific
    tools based on their suggested_tools configuration.

    Tool names are defined in docs/archons-base.csv and include:
    - insight_tool: Analytical capabilities for pattern recognition
    - communication_tool: Inter-agent communication and messaging
    - disruption_tool: Challenge assumptions, introduce alternatives
    - knowledge_retrieval_tool: Access to knowledge bases
    - creation_tool: Content generation and creative output
    - transaction_tool: Transaction handling and workflow management
    - relationship_tool: Relationship mapping and social analysis
    - logistics_tool: Resource allocation and coordination
    - wellness_tool: Agent health monitoring and self-assessment

    Constitutional Constraints:
    - CT-11: Must log all lookups, never silently return None without logging
    - NFR5: Tools must be stateless for concurrent agent access
    """

    @abstractmethod
    def get_tool(self, name: str) -> BaseTool | None:
        """Get a tool by name.

        Args:
            name: The tool identifier (e.g., "insight_tool")

        Returns:
            The Tool instance if found, None otherwise.
            Implementations MUST log when returning None (CT-11).
        """
        ...

    @abstractmethod
    def get_tools(self, names: list[str]) -> list[BaseTool]:
        """Get multiple tools by name.

        Returns only the tools that exist in the registry.
        Missing tools are logged but not included in result.

        Args:
            names: List of tool identifiers

        Returns:
            List of Tool instances for names that exist.
            Order matches input order for existing tools.
        """
        ...

    @abstractmethod
    def list_tools(self) -> list[str]:
        """List all registered tool names.

        Returns:
            List of all tool names in the registry.
        """
        ...

    @abstractmethod
    def register_tool(self, name: str, tool: BaseTool) -> None:
        """Register a tool with the given name.

        If a tool with this name already exists, it will be replaced.
        Implementations MUST log registration events.

        Args:
            name: The tool identifier
            tool: The Tool instance to register
        """
        ...

    @abstractmethod
    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered.

        Args:
            name: The tool identifier

        Returns:
            True if the tool exists, False otherwise.
        """
        ...

    @abstractmethod
    def count(self) -> int:
        """Get the number of registered tools.

        Returns:
            Number of tools in the registry.
        """
        ...
