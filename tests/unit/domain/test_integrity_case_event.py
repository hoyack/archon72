"""Unit tests for Integrity Case event payloads (Story 7.10, FR144).

Tests event payloads for amendment synchronization of the
Integrity Case Artifact.

Constitutional Constraints:
- FR144: System SHALL maintain published Integrity Case Artifact
- CT-12: Witnessing creates accountability -> Events must be witnessed
"""

from datetime import datetime, timezone

from src.domain.events.integrity_case import (
    INTEGRITY_CASE_UPDATED_EVENT_TYPE,
    IntegrityCaseUpdatedEventPayload,
)


class TestIntegrityCaseUpdatedEventPayload:
    """Tests for IntegrityCaseUpdatedEventPayload."""

    def test_create_payload_with_additions(self) -> None:
        """Payload should create with added guarantees."""
        now = datetime.now(timezone.utc)
        payload = IntegrityCaseUpdatedEventPayload(
            artifact_version="1.0.1",
            previous_version="1.0.0",
            amendment_event_id="amend-123",
            guarantees_added=("fr-200-new",),
            guarantees_modified=(),
            guarantees_removed=(),
            updated_at=now,
            reason="Added FR200 guarantee",
        )

        assert payload.artifact_version == "1.0.1"
        assert payload.previous_version == "1.0.0"
        assert payload.amendment_event_id == "amend-123"
        assert "fr-200-new" in payload.guarantees_added
        assert len(payload.guarantees_modified) == 0
        assert len(payload.guarantees_removed) == 0

    def test_create_payload_with_modifications(self) -> None:
        """Payload should create with modified guarantees."""
        now = datetime.now(timezone.utc)
        payload = IntegrityCaseUpdatedEventPayload(
            artifact_version="1.0.2",
            previous_version="1.0.1",
            amendment_event_id="amend-456",
            guarantees_added=(),
            guarantees_modified=("ct-1-audit-trail",),
            guarantees_removed=(),
            updated_at=now,
            reason="Updated CT-1 mechanism",
        )

        assert "ct-1-audit-trail" in payload.guarantees_modified

    def test_create_payload_with_removals(self) -> None:
        """Payload should create with removed guarantees."""
        now = datetime.now(timezone.utc)
        payload = IntegrityCaseUpdatedEventPayload(
            artifact_version="1.0.3",
            previous_version="1.0.2",
            amendment_event_id="amend-789",
            guarantees_added=(),
            guarantees_modified=(),
            guarantees_removed=("fr-deprecated",),
            updated_at=now,
            reason="Removed deprecated guarantee",
        )

        assert "fr-deprecated" in payload.guarantees_removed

    def test_signable_content_deterministic(self) -> None:
        """signable_content should be deterministic for witnessing (CT-12)."""
        now = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        payload = IntegrityCaseUpdatedEventPayload(
            artifact_version="1.0.1",
            previous_version="1.0.0",
            amendment_event_id="amend-123",
            guarantees_added=("new-guarantee",),
            guarantees_modified=(),
            guarantees_removed=(),
            updated_at=now,
            reason="Test reason",
        )

        content1 = payload.signable_content()
        content2 = payload.signable_content()

        assert content1 == content2
        assert isinstance(content1, bytes)
        assert b"integrity_case.updated" in content1
        assert b"amend-123" in content1

    def test_to_dict_serialization(self) -> None:
        """to_dict should serialize all fields correctly."""
        now = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        payload = IntegrityCaseUpdatedEventPayload(
            artifact_version="1.0.1",
            previous_version="1.0.0",
            amendment_event_id="amend-123",
            guarantees_added=("new-1", "new-2"),
            guarantees_modified=("mod-1",),
            guarantees_removed=("rem-1",),
            updated_at=now,
            reason="Full test",
        )

        data = payload.to_dict()

        assert data["artifact_version"] == "1.0.1"
        assert data["previous_version"] == "1.0.0"
        assert data["amendment_event_id"] == "amend-123"
        assert data["guarantees_added"] == ["new-1", "new-2"]
        assert data["guarantees_modified"] == ["mod-1"]
        assert data["guarantees_removed"] == ["rem-1"]
        assert data["reason"] == "Full test"
        assert "updated_at" in data


class TestEventTypeConstant:
    """Tests for event type constant."""

    def test_event_type_value(self) -> None:
        """INTEGRITY_CASE_UPDATED_EVENT_TYPE should have correct value."""
        assert INTEGRITY_CASE_UPDATED_EVENT_TYPE == "integrity_case.updated"
