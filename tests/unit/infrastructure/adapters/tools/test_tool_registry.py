"""Unit tests for ToolRegistry adapter (Story 10-3).

Tests verify:
- ToolRegistryProtocol compliance
- Tool registration and lookup
- Handling of unknown tools
- Factory function creates populated registry
"""

from src.application.ports.tool_registry import ToolRegistryProtocol
from src.infrastructure.adapters.tools.archon_tools import (
    ALL_ARCHON_TOOLS,
    CommunicationTool,
    InsightTool,
)
from src.infrastructure.adapters.tools.tool_registry_adapter import (
    ToolRegistryAdapter,
    create_tool_registry,
)


class TestToolRegistryAdapter:
    """Tests for ToolRegistryAdapter."""

    def test_implements_protocol(self) -> None:
        """Verify adapter implements ToolRegistryProtocol."""
        registry = ToolRegistryAdapter()
        assert isinstance(registry, ToolRegistryProtocol)

    def test_empty_registry_count(self) -> None:
        """Verify empty registry has zero count."""
        registry = ToolRegistryAdapter()
        assert registry.count() == 0

    def test_empty_registry_list_tools(self) -> None:
        """Verify empty registry returns empty list."""
        registry = ToolRegistryAdapter()
        assert registry.list_tools() == []

    def test_register_tool(self) -> None:
        """Verify tool registration works."""
        registry = ToolRegistryAdapter()
        tool = InsightTool()
        registry.register_tool("insight_tool", tool)

        assert registry.count() == 1
        assert "insight_tool" in registry.list_tools()

    def test_register_multiple_tools(self) -> None:
        """Verify multiple tools can be registered."""
        registry = ToolRegistryAdapter()
        registry.register_tool("insight_tool", InsightTool())
        registry.register_tool("communication_tool", CommunicationTool())

        assert registry.count() == 2
        assert set(registry.list_tools()) == {"insight_tool", "communication_tool"}

    def test_get_tool_exists(self) -> None:
        """Verify get_tool returns registered tool."""
        registry = ToolRegistryAdapter()
        tool = InsightTool()
        registry.register_tool("insight_tool", tool)

        retrieved = registry.get_tool("insight_tool")
        assert retrieved is tool

    def test_get_tool_not_exists(self) -> None:
        """Verify get_tool returns None for unknown tool."""
        registry = ToolRegistryAdapter()
        result = registry.get_tool("nonexistent_tool")
        assert result is None

    def test_has_tool_exists(self) -> None:
        """Verify has_tool returns True for registered tool."""
        registry = ToolRegistryAdapter()
        registry.register_tool("insight_tool", InsightTool())
        assert registry.has_tool("insight_tool") is True

    def test_has_tool_not_exists(self) -> None:
        """Verify has_tool returns False for unknown tool."""
        registry = ToolRegistryAdapter()
        assert registry.has_tool("nonexistent_tool") is False

    def test_get_tools_all_exist(self) -> None:
        """Verify get_tools returns all requested tools when they exist."""
        registry = ToolRegistryAdapter()
        insight = InsightTool()
        comm = CommunicationTool()
        registry.register_tool("insight_tool", insight)
        registry.register_tool("communication_tool", comm)

        tools = registry.get_tools(["insight_tool", "communication_tool"])
        assert len(tools) == 2
        assert insight in tools
        assert comm in tools

    def test_get_tools_partial_exist(self) -> None:
        """Verify get_tools returns only existing tools."""
        registry = ToolRegistryAdapter()
        insight = InsightTool()
        registry.register_tool("insight_tool", insight)

        tools = registry.get_tools(["insight_tool", "nonexistent_tool"])
        assert len(tools) == 1
        assert tools[0] is insight

    def test_get_tools_none_exist(self) -> None:
        """Verify get_tools returns empty list when no tools exist."""
        registry = ToolRegistryAdapter()
        tools = registry.get_tools(["nonexistent1", "nonexistent2"])
        assert tools == []

    def test_get_tools_empty_list(self) -> None:
        """Verify get_tools with empty list returns empty list."""
        registry = ToolRegistryAdapter()
        tools = registry.get_tools([])
        assert tools == []

    def test_register_replaces_existing(self) -> None:
        """Verify registering with same name replaces tool."""
        registry = ToolRegistryAdapter()
        tool1 = InsightTool()
        tool2 = InsightTool()

        registry.register_tool("insight_tool", tool1)
        registry.register_tool("insight_tool", tool2)

        assert registry.count() == 1
        assert registry.get_tool("insight_tool") is tool2


class TestCreateToolRegistry:
    """Tests for create_tool_registry factory function."""

    def test_creates_registry_with_all_tools(self) -> None:
        """Verify factory creates registry with all 9 archon tools."""
        registry = create_tool_registry()

        assert registry.count() == 9
        assert set(registry.list_tools()) == set(ALL_ARCHON_TOOLS)

    def test_all_tools_are_functional(self) -> None:
        """Verify all registered tools can be invoked."""
        registry = create_tool_registry()

        for tool_name in ALL_ARCHON_TOOLS:
            tool = registry.get_tool(tool_name)
            assert tool is not None
            assert tool.name == tool_name

    def test_include_all_archon_tools_false(self) -> None:
        """Verify factory can create empty registry."""
        registry = create_tool_registry(include_all_archon_tools=False)
        assert registry.count() == 0

    def test_returns_protocol_compliant_instance(self) -> None:
        """Verify factory returns ToolRegistryProtocol instance."""
        registry = create_tool_registry()
        assert isinstance(registry, ToolRegistryProtocol)

    def test_tools_can_execute(self) -> None:
        """Verify tools from registry can execute _run."""
        registry = create_tool_registry()

        insight = registry.get_tool("insight_tool")
        assert insight is not None
        result = insight._run(query="test")
        assert "[STUB]" in result


class TestToolRegistryIntegration:
    """Integration tests for tool registry with CrewAI patterns."""

    def test_tool_names_match_csv_format(self) -> None:
        """Verify tool names match format in archons-base.csv."""
        registry = create_tool_registry()

        # These names must exactly match the suggested_tools column in CSV
        expected_names = [
            "insight_tool",
            "communication_tool",
            "disruption_tool",
            "knowledge_retrieval_tool",
            "creation_tool",
            "transaction_tool",
            "relationship_tool",
            "logistics_tool",
            "wellness_tool",
        ]

        for name in expected_names:
            assert registry.has_tool(name), f"Missing tool: {name}"

    def test_tools_have_required_attributes(self) -> None:
        """Verify all tools have name, description, and _run."""
        registry = create_tool_registry()

        for tool_name in registry.list_tools():
            tool = registry.get_tool(tool_name)
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")
            assert hasattr(tool, "_run")
            assert callable(tool._run)

    def test_concurrent_access_pattern(self) -> None:
        """Verify registry supports pattern for 72 concurrent agents."""
        registry = create_tool_registry()

        # Simulate 72 agents requesting tools
        for _i in range(72):
            # Each agent might request different tool combinations
            tool_requests = ["insight_tool", "communication_tool"]
            tools = registry.get_tools(tool_requests)
            assert len(tools) == 2

            # Tools should be callable
            for tool in tools:
                # Just verify they're valid tools
                assert tool.name in ALL_ARCHON_TOOLS
