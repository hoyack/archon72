"""Unit tests for archon tool implementations (Story 10-3).

Tests verify:
- All 9 tools can be instantiated
- Each tool has correct name and description
- Each tool's _run method returns stub response
- Tools are stateless (can be called multiple times)
"""

import pytest

from src.infrastructure.adapters.tools.archon_tools import (
    ALL_ARCHON_TOOLS,
    TOOL_NAME_TO_CLASS,
    CommunicationTool,
    CreationTool,
    DisruptionTool,
    InsightTool,
    KnowledgeRetrievalTool,
    LogisticsTool,
    RelationshipTool,
    TransactionTool,
    WellnessTool,
)


class TestAllArchonTools:
    """Tests for the complete set of archon tools."""

    def test_all_archon_tools_count(self) -> None:
        """Verify exactly 9 tools are defined."""
        assert len(ALL_ARCHON_TOOLS) == 9

    def test_all_tool_names_in_mapping(self) -> None:
        """Verify all tool names have class mappings."""
        for tool_name in ALL_ARCHON_TOOLS:
            assert tool_name in TOOL_NAME_TO_CLASS

    def test_all_tools_can_be_instantiated(self) -> None:
        """Verify all tools can be instantiated without error."""
        for tool_name, tool_class in TOOL_NAME_TO_CLASS.items():
            tool = tool_class()
            assert tool.name == tool_name
            assert len(tool.description) > 10

    def test_expected_tool_names(self) -> None:
        """Verify expected tool names match CSV data."""
        expected_tools = {
            "insight_tool",
            "communication_tool",
            "disruption_tool",
            "knowledge_retrieval_tool",
            "creation_tool",
            "transaction_tool",
            "relationship_tool",
            "logistics_tool",
            "wellness_tool",
        }
        assert set(ALL_ARCHON_TOOLS) == expected_tools


class TestInsightTool:
    """Tests for InsightTool."""

    def test_instantiation(self) -> None:
        """Verify tool can be instantiated."""
        tool = InsightTool()
        assert tool.name == "insight_tool"
        assert "analyze" in tool.description.lower() or "insight" in tool.description.lower()

    def test_run_returns_stub_response(self) -> None:
        """Verify _run returns stub response."""
        tool = InsightTool()
        result = tool._run(query="test query", context="test context")
        assert "[STUB]" in result
        assert "test query" in result.lower() or "query" in result.lower()

    def test_run_without_context(self) -> None:
        """Verify _run works without context."""
        tool = InsightTool()
        result = tool._run(query="analysis request")
        assert "[STUB]" in result

    def test_run_is_stateless(self) -> None:
        """Verify tool can be called multiple times."""
        tool = InsightTool()
        result1 = tool._run(query="first")
        result2 = tool._run(query="second")
        assert "first" in result1.lower() or "[STUB]" in result1
        assert "second" in result2.lower() or "[STUB]" in result2


class TestCommunicationTool:
    """Tests for CommunicationTool."""

    def test_instantiation(self) -> None:
        """Verify tool can be instantiated."""
        tool = CommunicationTool()
        assert tool.name == "communication_tool"
        assert "communicate" in tool.description.lower() or "message" in tool.description.lower()

    def test_run_returns_stub_response(self) -> None:
        """Verify _run returns stub response."""
        tool = CommunicationTool()
        result = tool._run(message="hello world", target_agent="Paimon")
        assert "[STUB]" in result

    def test_run_broadcast(self) -> None:
        """Verify broadcast mode (no target)."""
        tool = CommunicationTool()
        result = tool._run(message="broadcast message")
        assert "[STUB]" in result
        assert "broadcast" in result.lower()


class TestDisruptionTool:
    """Tests for DisruptionTool."""

    def test_instantiation(self) -> None:
        """Verify tool can be instantiated."""
        tool = DisruptionTool()
        assert tool.name == "disruption_tool"
        assert "challenge" in tool.description.lower() or "alternative" in tool.description.lower()

    def test_run_returns_stub_response(self) -> None:
        """Verify _run returns stub response."""
        tool = DisruptionTool()
        result = tool._run(assumption="the sky is blue", perspective="but at sunset...")
        assert "[STUB]" in result

    def test_run_without_perspective(self) -> None:
        """Verify _run works without alternative perspective."""
        tool = DisruptionTool()
        result = tool._run(assumption="conventional wisdom")
        assert "[STUB]" in result


class TestKnowledgeRetrievalTool:
    """Tests for KnowledgeRetrievalTool."""

    def test_instantiation(self) -> None:
        """Verify tool can be instantiated."""
        tool = KnowledgeRetrievalTool()
        assert tool.name == "knowledge_retrieval_tool"
        assert "knowledge" in tool.description.lower() or "retrieve" in tool.description.lower()

    def test_run_returns_stub_response(self) -> None:
        """Verify _run returns stub response."""
        tool = KnowledgeRetrievalTool()
        result = tool._run(query="what is the meaning of life", domain="philosophy")
        assert "[STUB]" in result

    def test_run_without_domain(self) -> None:
        """Verify _run works without domain restriction."""
        tool = KnowledgeRetrievalTool()
        result = tool._run(query="general knowledge query")
        assert "[STUB]" in result


class TestCreationTool:
    """Tests for CreationTool."""

    def test_instantiation(self) -> None:
        """Verify tool can be instantiated."""
        tool = CreationTool()
        assert tool.name == "creation_tool"
        assert "generate" in tool.description.lower() or "create" in tool.description.lower()

    def test_run_returns_stub_response(self) -> None:
        """Verify _run returns stub response."""
        tool = CreationTool()
        result = tool._run(prompt="write a haiku", format="text")
        assert "[STUB]" in result
        assert "text" in result.lower()

    def test_run_with_json_format(self) -> None:
        """Verify format parameter is respected."""
        tool = CreationTool()
        result = tool._run(prompt="create structured data", format="json")
        assert "[STUB]" in result
        assert "json" in result.lower()


class TestTransactionTool:
    """Tests for TransactionTool."""

    def test_instantiation(self) -> None:
        """Verify tool can be instantiated."""
        tool = TransactionTool()
        assert tool.name == "transaction_tool"
        assert "transaction" in tool.description.lower() or "workflow" in tool.description.lower()

    def test_run_returns_stub_response(self) -> None:
        """Verify _run returns stub response."""
        tool = TransactionTool()
        result = tool._run(action="initiate", parameters='{"type": "vote"}')
        assert "[STUB]" in result

    def test_run_with_default_parameters(self) -> None:
        """Verify _run works with default parameters."""
        tool = TransactionTool()
        result = tool._run(action="query")
        assert "[STUB]" in result


class TestRelationshipTool:
    """Tests for RelationshipTool."""

    def test_instantiation(self) -> None:
        """Verify tool can be instantiated."""
        tool = RelationshipTool()
        assert tool.name == "relationship_tool"
        assert "relationship" in tool.description.lower() or "network" in tool.description.lower()

    def test_run_returns_stub_response(self) -> None:
        """Verify _run returns stub response."""
        tool = RelationshipTool()
        result = tool._run(entity="Paimon", relationship_type="colleague")
        assert "[STUB]" in result

    def test_run_without_relationship_type(self) -> None:
        """Verify _run works without relationship type."""
        tool = RelationshipTool()
        result = tool._run(entity="Belial")
        assert "[STUB]" in result


class TestLogisticsTool:
    """Tests for LogisticsTool."""

    def test_instantiation(self) -> None:
        """Verify tool can be instantiated."""
        tool = LogisticsTool()
        assert tool.name == "logistics_tool"
        assert "resource" in tool.description.lower() or "allocate" in tool.description.lower()

    def test_run_returns_stub_response(self) -> None:
        """Verify _run returns stub response."""
        tool = LogisticsTool()
        result = tool._run(resource="compute_time", action="allocate")
        assert "[STUB]" in result

    def test_run_analyze_action(self) -> None:
        """Verify default analyze action."""
        tool = LogisticsTool()
        result = tool._run(resource="meeting_room")
        assert "[STUB]" in result
        assert "analyze" in result.lower()


class TestWellnessTool:
    """Tests for WellnessTool."""

    def test_instantiation(self) -> None:
        """Verify tool can be instantiated."""
        tool = WellnessTool()
        assert tool.name == "wellness_tool"
        assert "health" in tool.description.lower() or "monitor" in tool.description.lower()

    def test_run_returns_stub_response(self) -> None:
        """Verify _run returns stub response."""
        tool = WellnessTool()
        result = tool._run(metric="performance")
        assert "[STUB]" in result
        assert "performance" in result.lower()

    def test_run_overall_metric(self) -> None:
        """Verify default overall metric."""
        tool = WellnessTool()
        result = tool._run()
        assert "[STUB]" in result
        assert "overall" in result.lower()
