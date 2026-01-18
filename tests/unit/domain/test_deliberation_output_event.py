"""Unit tests for DeliberationOutputEvent (Story 2.1, Task 1).

Tests:
- DeliberationOutputPayload creation and validation
- Event type constants
- No infrastructure imports

Constitutional Constraints:
- FR9: Agent outputs recorded before any human sees them
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from uuid import uuid4

import pytest


class TestDeliberationOutputPayload:
    """Test DeliberationOutputPayload dataclass."""

    def test_payload_creation_with_all_required_fields(self) -> None:
        """Payload can be created with all required fields."""
        from src.domain.events.deliberation_output import DeliberationOutputPayload

        output_id = uuid4()
        payload = DeliberationOutputPayload(
            output_id=output_id,
            agent_id="archon-42",
            content_hash="abc123" + "0" * 58,  # 64 char hash
            content_type="text/plain",
            raw_content="This is the agent output",
        )

        assert payload.output_id == output_id
        assert payload.agent_id == "archon-42"
        assert payload.content_hash == "abc123" + "0" * 58
        assert payload.content_type == "text/plain"
        assert payload.raw_content == "This is the agent output"

    def test_payload_is_frozen_dataclass(self) -> None:
        """Payload is immutable (frozen dataclass)."""
        from src.domain.events.deliberation_output import DeliberationOutputPayload

        payload = DeliberationOutputPayload(
            output_id=uuid4(),
            agent_id="archon-42",
            content_hash="a" * 64,
            content_type="text/plain",
            raw_content="Test output",
        )

        with pytest.raises(AttributeError):
            payload.agent_id = "archon-99"  # type: ignore[misc]

    def test_payload_to_dict(self) -> None:
        """Payload can be converted to dict for event payload."""
        from src.domain.events.deliberation_output import DeliberationOutputPayload

        output_id = uuid4()
        payload = DeliberationOutputPayload(
            output_id=output_id,
            agent_id="archon-42",
            content_hash="b" * 64,
            content_type="application/json",
            raw_content='{"key": "value"}',
        )

        as_dict = payload.to_dict()

        assert as_dict["output_id"] == str(output_id)
        assert as_dict["agent_id"] == "archon-42"
        assert as_dict["content_hash"] == "b" * 64
        assert as_dict["content_type"] == "application/json"
        assert as_dict["raw_content"] == '{"key": "value"}'

    def test_payload_validates_output_id_is_uuid(self) -> None:
        """Payload validates output_id is UUID."""
        from src.domain.events.deliberation_output import DeliberationOutputPayload

        with pytest.raises((TypeError, ValueError)):
            DeliberationOutputPayload(
                output_id="not-a-uuid",  # type: ignore[arg-type]
                agent_id="archon-42",
                content_hash="c" * 64,
                content_type="text/plain",
                raw_content="Test",
            )

    def test_payload_validates_agent_id_not_empty(self) -> None:
        """Payload validates agent_id is not empty."""
        from src.domain.events.deliberation_output import DeliberationOutputPayload

        with pytest.raises(ValueError, match="agent_id"):
            DeliberationOutputPayload(
                output_id=uuid4(),
                agent_id="",
                content_hash="d" * 64,
                content_type="text/plain",
                raw_content="Test",
            )

    def test_payload_validates_content_hash_length(self) -> None:
        """Payload validates content_hash is 64 characters (SHA-256 hex)."""
        from src.domain.events.deliberation_output import DeliberationOutputPayload

        with pytest.raises(ValueError, match="content_hash"):
            DeliberationOutputPayload(
                output_id=uuid4(),
                agent_id="archon-42",
                content_hash="tooshort",
                content_type="text/plain",
                raw_content="Test",
            )


class TestDeliberationOutputEventType:
    """Test event type constants."""

    def test_event_type_constant_exists(self) -> None:
        """DELIBERATION_OUTPUT_EVENT_TYPE constant is defined."""
        from src.domain.events.deliberation_output import DELIBERATION_OUTPUT_EVENT_TYPE

        assert DELIBERATION_OUTPUT_EVENT_TYPE == "deliberation.output"

    def test_event_type_is_lowercase_dot_notation(self) -> None:
        """Event type follows lowercase.dot.notation convention."""
        from src.domain.events.deliberation_output import DELIBERATION_OUTPUT_EVENT_TYPE

        assert "." in DELIBERATION_OUTPUT_EVENT_TYPE
        assert DELIBERATION_OUTPUT_EVENT_TYPE.islower()


class TestNoInfrastructureImports:
    """Verify domain layer has no infrastructure imports."""

    def test_deliberation_output_no_infrastructure_imports(self) -> None:
        """deliberation_output.py has no infrastructure imports."""
        import ast
        from pathlib import Path

        file_path = Path("src/domain/events/deliberation_output.py")
        source = file_path.read_text()
        tree = ast.parse(source)

        forbidden_modules = ["src.infrastructure", "sqlalchemy", "redis", "supabase"]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_modules:
                        assert not alias.name.startswith(forbidden), (
                            f"Forbidden import: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom) and node.module:
                for forbidden in forbidden_modules:
                    assert not node.module.startswith(forbidden), (
                        f"Forbidden import: {node.module}"
                    )
