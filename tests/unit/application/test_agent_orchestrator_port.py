"""Unit tests for AgentOrchestratorPort (Story 2.2, Task 1).

Tests:
- AgentStatus enum
- ContextBundle dataclass
- AgentRequest dataclass
- AgentOutput dataclass
- AgentStatusInfo dataclass
- AgentOrchestratorProtocol interface
- No infrastructure imports in port

Constitutional Constraints:
- FR10: 72 agents can deliberate concurrently without degradation
- NFR5: 72 concurrent agent deliberations without degradation
- CT-11: Silent failure destroys legitimacy -> report all agent failures
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest


class TestAgentStatus:
    """Test AgentStatus enum."""

    def test_agent_status_values(self) -> None:
        """AgentStatus has expected values."""
        from src.application.ports.agent_orchestrator import AgentStatus

        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.BUSY.value == "busy"
        assert AgentStatus.FAILED.value == "failed"
        assert AgentStatus.UNKNOWN.value == "unknown"

    def test_agent_status_count(self) -> None:
        """AgentStatus has exactly 4 values."""
        from src.application.ports.agent_orchestrator import AgentStatus

        assert len(AgentStatus) == 4


class TestContextBundle:
    """Test ContextBundle dataclass."""

    def test_context_bundle_creation(self) -> None:
        """ContextBundle can be created with all fields."""
        from src.application.ports.agent_orchestrator import ContextBundle

        bundle_id = uuid4()
        created_at = datetime.now(timezone.utc)
        bundle = ContextBundle(
            bundle_id=bundle_id,
            topic_id="topic-123",
            topic_content="What should we decide?",
            metadata={"key": "value"},
            created_at=created_at,
        )

        assert bundle.bundle_id == bundle_id
        assert bundle.topic_id == "topic-123"
        assert bundle.topic_content == "What should we decide?"
        assert bundle.metadata == {"key": "value"}
        assert bundle.created_at == created_at

    def test_context_bundle_is_frozen(self) -> None:
        """ContextBundle is immutable (frozen dataclass)."""
        from src.application.ports.agent_orchestrator import ContextBundle

        bundle = ContextBundle(
            bundle_id=uuid4(),
            topic_id="topic-456",
            topic_content="Test content",
            metadata=None,
            created_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            bundle.topic_id = "changed"  # type: ignore[misc]

    def test_context_bundle_with_none_metadata(self) -> None:
        """ContextBundle accepts None for optional metadata."""
        from src.application.ports.agent_orchestrator import ContextBundle

        bundle = ContextBundle(
            bundle_id=uuid4(),
            topic_id="topic-789",
            topic_content="Content",
            metadata=None,
            created_at=datetime.now(timezone.utc),
        )

        assert bundle.metadata is None


class TestAgentRequest:
    """Test AgentRequest dataclass."""

    def test_agent_request_creation(self) -> None:
        """AgentRequest can be created with all fields."""
        from src.application.ports.agent_orchestrator import (
            AgentRequest,
            ContextBundle,
        )

        request_id = uuid4()
        context = ContextBundle(
            bundle_id=uuid4(),
            topic_id="topic-1",
            topic_content="Content",
            metadata=None,
            created_at=datetime.now(timezone.utc),
        )

        request = AgentRequest(
            request_id=request_id,
            agent_id="archon-42",
            context=context,
        )

        assert request.request_id == request_id
        assert request.agent_id == "archon-42"
        assert request.context == context

    def test_agent_request_is_frozen(self) -> None:
        """AgentRequest is immutable (frozen dataclass)."""
        from src.application.ports.agent_orchestrator import (
            AgentRequest,
            ContextBundle,
        )

        context = ContextBundle(
            bundle_id=uuid4(),
            topic_id="topic",
            topic_content="Content",
            metadata=None,
            created_at=datetime.now(timezone.utc),
        )

        request = AgentRequest(
            request_id=uuid4(),
            agent_id="archon-1",
            context=context,
        )

        with pytest.raises(AttributeError):
            request.agent_id = "archon-2"  # type: ignore[misc]


class TestAgentOutput:
    """Test AgentOutput dataclass."""

    def test_agent_output_creation(self) -> None:
        """AgentOutput can be created with all fields."""
        from src.application.ports.agent_orchestrator import AgentOutput

        output_id = uuid4()
        request_id = uuid4()
        generated_at = datetime.now(timezone.utc)

        output = AgentOutput(
            output_id=output_id,
            agent_id="archon-72",
            request_id=request_id,
            content="The Conclave has decided...",
            content_type="text/plain",
            generated_at=generated_at,
        )

        assert output.output_id == output_id
        assert output.agent_id == "archon-72"
        assert output.request_id == request_id
        assert output.content == "The Conclave has decided..."
        assert output.content_type == "text/plain"
        assert output.generated_at == generated_at

    def test_agent_output_is_frozen(self) -> None:
        """AgentOutput is immutable (frozen dataclass)."""
        from src.application.ports.agent_orchestrator import AgentOutput

        output = AgentOutput(
            output_id=uuid4(),
            agent_id="archon-1",
            request_id=uuid4(),
            content="Output",
            content_type="text/plain",
            generated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            output.content = "Changed"  # type: ignore[misc]


class TestAgentStatusInfo:
    """Test AgentStatusInfo dataclass."""

    def test_agent_status_info_creation(self) -> None:
        """AgentStatusInfo can be created with all fields."""
        from src.application.ports.agent_orchestrator import (
            AgentStatus,
            AgentStatusInfo,
        )

        last_invocation = datetime.now(timezone.utc)

        info = AgentStatusInfo(
            agent_id="archon-7",
            status=AgentStatus.IDLE,
            last_invocation=last_invocation,
            last_error=None,
        )

        assert info.agent_id == "archon-7"
        assert info.status == AgentStatus.IDLE
        assert info.last_invocation == last_invocation
        assert info.last_error is None

    def test_agent_status_info_with_error(self) -> None:
        """AgentStatusInfo captures error information."""
        from src.application.ports.agent_orchestrator import (
            AgentStatus,
            AgentStatusInfo,
        )

        info = AgentStatusInfo(
            agent_id="archon-13",
            status=AgentStatus.FAILED,
            last_invocation=datetime.now(timezone.utc),
            last_error="Connection timeout",
        )

        assert info.status == AgentStatus.FAILED
        assert info.last_error == "Connection timeout"

    def test_agent_status_info_is_frozen(self) -> None:
        """AgentStatusInfo is immutable (frozen dataclass)."""
        from src.application.ports.agent_orchestrator import (
            AgentStatus,
            AgentStatusInfo,
        )

        info = AgentStatusInfo(
            agent_id="archon-1",
            status=AgentStatus.BUSY,
            last_invocation=None,
            last_error=None,
        )

        with pytest.raises(AttributeError):
            info.status = AgentStatus.IDLE  # type: ignore[misc]


class TestAgentOrchestratorProtocol:
    """Test AgentOrchestratorProtocol abstract interface."""

    def test_protocol_is_abstract_class(self) -> None:
        """AgentOrchestratorProtocol is an abstract base class."""
        from abc import ABC

        from src.application.ports.agent_orchestrator import (
            AgentOrchestratorProtocol,
        )

        assert issubclass(AgentOrchestratorProtocol, ABC)

    def test_protocol_has_invoke_method(self) -> None:
        """Protocol defines invoke abstract method."""
        from src.application.ports.agent_orchestrator import (
            AgentOrchestratorProtocol,
        )

        assert hasattr(AgentOrchestratorProtocol, "invoke")

    def test_protocol_has_invoke_batch_method(self) -> None:
        """Protocol defines invoke_batch abstract method."""
        from src.application.ports.agent_orchestrator import (
            AgentOrchestratorProtocol,
        )

        assert hasattr(AgentOrchestratorProtocol, "invoke_batch")

    def test_protocol_has_get_agent_status_method(self) -> None:
        """Protocol defines get_agent_status abstract method."""
        from src.application.ports.agent_orchestrator import (
            AgentOrchestratorProtocol,
        )

        assert hasattr(AgentOrchestratorProtocol, "get_agent_status")

    def test_protocol_cannot_be_instantiated(self) -> None:
        """AgentOrchestratorProtocol cannot be instantiated directly."""
        from src.application.ports.agent_orchestrator import (
            AgentOrchestratorProtocol,
        )

        with pytest.raises(TypeError, match="abstract"):
            AgentOrchestratorProtocol()  # type: ignore[abstract]


class TestNoInfrastructureImports:
    """Verify application port has no infrastructure imports."""

    def test_port_no_infrastructure_imports(self) -> None:
        """agent_orchestrator.py port has no infrastructure imports."""
        import ast
        from pathlib import Path

        file_path = Path("src/application/ports/agent_orchestrator.py")
        source = file_path.read_text()
        tree = ast.parse(source)

        forbidden_modules = [
            "src.infrastructure",
            "sqlalchemy",
            "redis",
            "supabase",
            "crewai",
        ]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_modules:
                        assert not alias.name.startswith(forbidden), (
                            f"Forbidden import: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for forbidden in forbidden_modules:
                        assert not node.module.startswith(forbidden), (
                            f"Forbidden import: {node.module}"
                        )


class TestExportedFromPackage:
    """Verify types are exported from ports package."""

    def test_types_exported_from_package(self) -> None:
        """All new types are exported from application.ports package."""
        from src.application.ports import (
            AgentOrchestratorProtocol,
            AgentOutput,
            AgentRequest,
            AgentStatus,
            AgentStatusInfo,
            ContextBundle,
        )

        # Just verify they can be imported
        assert AgentOrchestratorProtocol is not None
        assert AgentOutput is not None
        assert AgentRequest is not None
        assert AgentStatus is not None
        assert AgentStatusInfo is not None
        assert ContextBundle is not None
