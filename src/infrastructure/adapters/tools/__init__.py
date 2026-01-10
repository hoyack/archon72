"""Tool adapters for CrewAI agent orchestration (Story 10-3).

This module provides tool implementations that can be used by Archon agents
during deliberation. Tools are registered in the ToolRegistry and mapped
to agents based on their suggested_tools configuration.

Available tools:
- InsightTool: Analytical capabilities for pattern recognition
- CommunicationTool: Inter-agent communication and messaging
- DisruptionTool: Challenge assumptions, introduce alternatives
- KnowledgeRetrievalTool: Access to knowledge bases
- CreationTool: Content generation and creative output
- TransactionTool: Transaction handling and workflow management
- RelationshipTool: Relationship mapping and social analysis
- LogisticsTool: Resource allocation and coordination
- WellnessTool: Agent health monitoring and self-assessment
"""

from src.infrastructure.adapters.tools.archon_tools import (
    CommunicationTool,
    CreationTool,
    DisruptionTool,
    InsightTool,
    KnowledgeRetrievalTool,
    LogisticsTool,
    RelationshipTool,
    TransactionTool,
    WellnessTool,
    ALL_ARCHON_TOOLS,
    TOOL_NAME_TO_CLASS,
)
from src.infrastructure.adapters.tools.tool_registry_adapter import (
    ToolRegistryAdapter,
    create_tool_registry,
)

__all__ = [
    # Tool classes
    "InsightTool",
    "CommunicationTool",
    "DisruptionTool",
    "KnowledgeRetrievalTool",
    "CreationTool",
    "TransactionTool",
    "RelationshipTool",
    "LogisticsTool",
    "WellnessTool",
    # Tool mappings
    "ALL_ARCHON_TOOLS",
    "TOOL_NAME_TO_CLASS",
    # Registry
    "ToolRegistryAdapter",
    "create_tool_registry",
]
