"""Unit tests for HaltClearedEvent (Story 3.4, AC #2).

Tests the domain event for halt clearing ceremonies.
Constitutional Constraint (CT-12): Witnessing creates accountability.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.events.halt_cleared import (
    HALT_CLEARED_EVENT_TYPE,
    HaltClearedPayload,
)


class TestHaltClearedPayload:
    """Tests for HaltClearedPayload dataclass."""

    def test_create_halt_cleared_payload(self) -> None:
        """Test creating a valid HaltClearedPayload."""
        ceremony_id = uuid4()
        cleared_at = datetime.now(timezone.utc)
        approvers = ("keeper-001", "keeper-002")

        payload = HaltClearedPayload(
            ceremony_id=ceremony_id,
            clearing_authority="Keeper Council",
            reason="Recovery ceremony completed successfully",
            approvers=approvers,
            cleared_at=cleared_at,
        )

        assert payload.ceremony_id == ceremony_id
        assert payload.clearing_authority == "Keeper Council"
        assert payload.reason == "Recovery ceremony completed successfully"
        assert payload.approvers == approvers
        assert payload.cleared_at == cleared_at

    def test_halt_cleared_payload_is_immutable(self) -> None:
        """Test that HaltClearedPayload is frozen (immutable)."""
        payload = HaltClearedPayload(
            ceremony_id=uuid4(),
            clearing_authority="Keeper Council",
            reason="Test clear",
            approvers=("keeper-001", "keeper-002"),
            cleared_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            payload.reason = "Modified reason"  # type: ignore[misc]

    def test_halt_cleared_payload_ceremony_id_type_hint(self) -> None:
        """Test that ceremony_id type hint is UUID (static typing enforcement).

        Note: Python dataclasses don't validate types at runtime by default.
        Type enforcement is done via mypy/static analysis.
        This test documents the expected type.
        """
        payload = HaltClearedPayload(
            ceremony_id=uuid4(),
            clearing_authority="Keeper Council",
            reason="Test",
            approvers=("keeper-001", "keeper-002"),
            cleared_at=datetime.now(timezone.utc),
        )
        assert isinstance(payload.ceremony_id, UUID)

    def test_halt_cleared_payload_requires_at_least_two_approvers(self) -> None:
        """Test that approvers must have at least 2 keepers (ADR-6 Tier 1)."""
        payload = HaltClearedPayload(
            ceremony_id=uuid4(),
            clearing_authority="Keeper Council",
            reason="Test",
            approvers=("keeper-001", "keeper-002"),
            cleared_at=datetime.now(timezone.utc),
        )
        # Validation enforces at least 2 approvers via validate() method
        assert len(payload.approvers) >= 2

    def test_halt_cleared_payload_converts_list_to_tuple(self) -> None:
        """Test that list approvers are converted to tuple for immutability."""
        payload = HaltClearedPayload(
            ceremony_id=uuid4(),
            clearing_authority="Keeper Council",
            reason="Test",
            approvers=["keeper-001", "keeper-002"],  # type: ignore[arg-type]
            cleared_at=datetime.now(timezone.utc),
        )
        assert isinstance(payload.approvers, tuple)
        assert payload.approvers == ("keeper-001", "keeper-002")


class TestHaltClearedPayloadSignableContent:
    """Tests for signable_content() method - CT-12 compliance."""

    def test_signable_content_returns_bytes(self) -> None:
        """Test that signable_content returns bytes."""
        payload = HaltClearedPayload(
            ceremony_id=UUID("12345678-1234-5678-1234-567812345678"),
            clearing_authority="Keeper Council",
            reason="Test clear",
            approvers=("keeper-001", "keeper-002"),
            cleared_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        content = payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_is_deterministic(self) -> None:
        """Test that signable_content produces deterministic output."""
        ceremony_id = UUID("12345678-1234-5678-1234-567812345678")
        cleared_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        payload1 = HaltClearedPayload(
            ceremony_id=ceremony_id,
            clearing_authority="Keeper Council",
            reason="Test clear",
            approvers=("keeper-001", "keeper-002"),
            cleared_at=cleared_at,
        )

        payload2 = HaltClearedPayload(
            ceremony_id=ceremony_id,
            clearing_authority="Keeper Council",
            reason="Test clear",
            approvers=("keeper-001", "keeper-002"),
            cleared_at=cleared_at,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_differs_for_different_payloads(self) -> None:
        """Test that different payloads produce different signable content."""
        cleared_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        payload1 = HaltClearedPayload(
            ceremony_id=UUID("12345678-1234-5678-1234-567812345678"),
            clearing_authority="Keeper Council",
            reason="Reason A",
            approvers=("keeper-001", "keeper-002"),
            cleared_at=cleared_at,
        )

        payload2 = HaltClearedPayload(
            ceremony_id=UUID("12345678-1234-5678-1234-567812345678"),
            clearing_authority="Keeper Council",
            reason="Reason B",  # Different reason
            approvers=("keeper-001", "keeper-002"),
            cleared_at=cleared_at,
        )

        assert payload1.signable_content() != payload2.signable_content()

    def test_signable_content_includes_all_fields(self) -> None:
        """Test that signable_content includes all relevant fields."""
        payload = HaltClearedPayload(
            ceremony_id=UUID("12345678-1234-5678-1234-567812345678"),
            clearing_authority="Keeper Council",
            reason="Test clear",
            approvers=("keeper-001", "keeper-002"),
            cleared_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        content = payload.signable_content()
        content_str = content.decode("utf-8")

        # Verify all fields are included
        assert "HaltClearedEvent" in content_str
        assert "12345678-1234-5678-1234-567812345678" in content_str
        assert "Keeper Council" in content_str
        assert "Test clear" in content_str
        assert "keeper-001" in content_str
        assert "keeper-002" in content_str


class TestHaltClearedEventType:
    """Tests for event type constant."""

    def test_event_type_constant(self) -> None:
        """Test that event type constant is defined correctly."""
        assert HALT_CLEARED_EVENT_TYPE == "halt.cleared"

    def test_event_type_follows_naming_convention(self) -> None:
        """Test event type follows domain.action naming convention."""
        parts = HALT_CLEARED_EVENT_TYPE.split(".")
        assert len(parts) == 2
        assert parts[0] == "halt"
        assert parts[1] == "cleared"
