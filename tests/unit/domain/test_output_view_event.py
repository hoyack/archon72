"""Unit tests for OutputViewEvent (Story 2.1, Task 3).

Tests:
- OutputViewPayload creation and validation
- Event type constants
- No infrastructure imports

Constitutional Constraints:
- FR9: Agent outputs recorded before any human sees them
- CT-12: Witnessing creates accountability - view events create audit trail
- AC2: Hash Verification on View - view event logged with viewer identity
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest


class TestOutputViewPayload:
    """Test OutputViewPayload dataclass."""

    def test_payload_creation_with_all_required_fields(self) -> None:
        """Payload can be created with all required fields."""
        from src.domain.events.output_view import OutputViewPayload

        output_id = uuid4()
        viewed_at = datetime.now(timezone.utc)
        payload = OutputViewPayload(
            output_id=output_id,
            viewer_id="user-123",
            viewer_type="human",
            viewed_at=viewed_at,
        )

        assert payload.output_id == output_id
        assert payload.viewer_id == "user-123"
        assert payload.viewer_type == "human"
        assert payload.viewed_at == viewed_at

    def test_payload_is_frozen_dataclass(self) -> None:
        """Payload is immutable (frozen dataclass)."""
        from src.domain.events.output_view import OutputViewPayload

        payload = OutputViewPayload(
            output_id=uuid4(),
            viewer_id="user-123",
            viewer_type="human",
            viewed_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            payload.viewer_id = "user-456"  # type: ignore[misc]

    def test_payload_to_dict(self) -> None:
        """Payload can be converted to dict for event payload."""
        from src.domain.events.output_view import OutputViewPayload

        output_id = uuid4()
        viewed_at = datetime(2026, 1, 6, 12, 0, 0, tzinfo=UTC)
        payload = OutputViewPayload(
            output_id=output_id,
            viewer_id="user-123",
            viewer_type="api_client",
            viewed_at=viewed_at,
        )

        as_dict = payload.to_dict()

        assert as_dict["output_id"] == str(output_id)
        assert as_dict["viewer_id"] == "user-123"
        assert as_dict["viewer_type"] == "api_client"
        assert as_dict["viewed_at"] == viewed_at.isoformat()

    def test_payload_validates_output_id_is_uuid(self) -> None:
        """Payload validates output_id is UUID."""
        from src.domain.events.output_view import OutputViewPayload

        with pytest.raises((TypeError, ValueError)):
            OutputViewPayload(
                output_id="not-a-uuid",  # type: ignore[arg-type]
                viewer_id="user-123",
                viewer_type="human",
                viewed_at=datetime.now(timezone.utc),
            )

    def test_payload_validates_viewer_id_not_empty(self) -> None:
        """Payload validates viewer_id is not empty."""
        from src.domain.events.output_view import OutputViewPayload

        with pytest.raises(ValueError, match="viewer_id"):
            OutputViewPayload(
                output_id=uuid4(),
                viewer_id="",
                viewer_type="human",
                viewed_at=datetime.now(timezone.utc),
            )

    def test_payload_validates_viewer_type_not_empty(self) -> None:
        """Payload validates viewer_type is not empty."""
        from src.domain.events.output_view import OutputViewPayload

        with pytest.raises(ValueError, match="viewer_type"):
            OutputViewPayload(
                output_id=uuid4(),
                viewer_id="user-123",
                viewer_type="",
                viewed_at=datetime.now(timezone.utc),
            )

    def test_payload_validates_viewed_at_is_datetime(self) -> None:
        """Payload validates viewed_at is datetime."""
        from src.domain.events.output_view import OutputViewPayload

        with pytest.raises((TypeError, ValueError)):
            OutputViewPayload(
                output_id=uuid4(),
                viewer_id="user-123",
                viewer_type="human",
                viewed_at="2026-01-06",  # type: ignore[arg-type]
            )


class TestOutputViewEventType:
    """Test event type constants."""

    def test_event_type_constant_exists(self) -> None:
        """OUTPUT_VIEW_EVENT_TYPE constant is defined."""
        from src.domain.events.output_view import OUTPUT_VIEW_EVENT_TYPE

        assert OUTPUT_VIEW_EVENT_TYPE == "output.view"

    def test_event_type_is_lowercase_dot_notation(self) -> None:
        """Event type follows lowercase.dot.notation convention."""
        from src.domain.events.output_view import OUTPUT_VIEW_EVENT_TYPE

        assert "." in OUTPUT_VIEW_EVENT_TYPE
        assert OUTPUT_VIEW_EVENT_TYPE.islower()


class TestNoInfrastructureImports:
    """Verify domain layer has no infrastructure imports."""

    def test_output_view_no_infrastructure_imports(self) -> None:
        """output_view.py has no infrastructure imports."""
        import ast
        from pathlib import Path

        file_path = Path("src/domain/events/output_view.py")
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
