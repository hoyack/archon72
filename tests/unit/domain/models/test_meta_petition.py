"""Unit tests for META petition domain models (Story 8.5, FR-10.4).

These tests verify:
1. PetitionType enum includes META
2. MetaPetitionReceived event model structure
3. MetaPetitionResolved event model structure
4. MetaDisposition enum values
5. MetaPetitionQueueItem model
6. MetaPetitionStatus enum values
7. Signable content and to_dict methods

Constitutional Constraints:
- CT-12: Witnessing creates accountability - Events must be signable
- FR-10.4: META petitions route to High Archon
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.models.petition_submission import PetitionType


class TestPetitionTypeMeta:
    """Tests for META petition type in PetitionType enum."""

    def test_meta_type_exists(self) -> None:
        """Test that META type exists in PetitionType enum (FR-10.4)."""
        assert hasattr(PetitionType, "META"), "PetitionType must include META"
        assert PetitionType.META.value == "META"

    def test_meta_type_is_distinct(self) -> None:
        """Test that META type is distinct from other types."""
        all_types = [t.value for t in PetitionType]
        assert "META" in all_types
        assert all_types.count("META") == 1  # Only one META

    def test_all_petition_types_present(self) -> None:
        """Test all required petition types are present."""
        expected_types = {"GENERAL", "CESSATION", "GRIEVANCE", "COLLABORATION", "META"}
        actual_types = {t.value for t in PetitionType}
        assert expected_types == actual_types


class TestMetaDisposition:
    """Tests for MetaDisposition enum."""

    def test_acknowledge_disposition_exists(self) -> None:
        """Test ACKNOWLEDGE disposition exists."""
        from src.domain.models.meta_petition import MetaDisposition

        assert hasattr(MetaDisposition, "ACKNOWLEDGE")
        assert MetaDisposition.ACKNOWLEDGE.value == "ACKNOWLEDGE"

    def test_create_action_disposition_exists(self) -> None:
        """Test CREATE_ACTION disposition exists."""
        from src.domain.models.meta_petition import MetaDisposition

        assert hasattr(MetaDisposition, "CREATE_ACTION")
        assert MetaDisposition.CREATE_ACTION.value == "CREATE_ACTION"

    def test_forward_disposition_exists(self) -> None:
        """Test FORWARD disposition exists."""
        from src.domain.models.meta_petition import MetaDisposition

        assert hasattr(MetaDisposition, "FORWARD")
        assert MetaDisposition.FORWARD.value == "FORWARD"

    def test_all_dispositions_present(self) -> None:
        """Test all required dispositions are present."""
        from src.domain.models.meta_petition import MetaDisposition

        expected = {"ACKNOWLEDGE", "CREATE_ACTION", "FORWARD"}
        actual = {d.value for d in MetaDisposition}
        assert expected == actual


class TestMetaPetitionStatus:
    """Tests for MetaPetitionStatus enum."""

    def test_pending_status_exists(self) -> None:
        """Test PENDING status exists."""
        from src.domain.models.meta_petition import MetaPetitionStatus

        assert hasattr(MetaPetitionStatus, "PENDING")
        assert MetaPetitionStatus.PENDING.value == "PENDING"

    def test_resolved_status_exists(self) -> None:
        """Test RESOLVED status exists."""
        from src.domain.models.meta_petition import MetaPetitionStatus

        assert hasattr(MetaPetitionStatus, "RESOLVED")
        assert MetaPetitionStatus.RESOLVED.value == "RESOLVED"


class TestMetaPetitionReceivedEventPayload:
    """Tests for MetaPetitionReceivedEventPayload (AC2, AC6)."""

    def test_event_creation(self) -> None:
        """Test MetaPetitionReceivedEventPayload creation."""
        from src.domain.events.meta_petition import MetaPetitionReceivedEventPayload

        event = MetaPetitionReceivedEventPayload(
            petition_id=uuid4(),
            submitter_id=uuid4(),
            petition_text_preview="Test petition about the petition system",
            received_at=datetime.now(timezone.utc),
            routing_reason="EXPLICIT_META_TYPE",
        )

        assert event.petition_id is not None
        assert event.submitter_id is not None
        assert event.petition_text_preview == "Test petition about the petition system"
        assert event.routing_reason == "EXPLICIT_META_TYPE"

    def test_event_is_frozen(self) -> None:
        """Test MetaPetitionReceivedEventPayload is immutable (CT-12)."""
        from src.domain.events.meta_petition import MetaPetitionReceivedEventPayload

        event = MetaPetitionReceivedEventPayload(
            petition_id=uuid4(),
            submitter_id=uuid4(),
            petition_text_preview="Test",
            received_at=datetime.now(timezone.utc),
            routing_reason="EXPLICIT_META_TYPE",
        )

        with pytest.raises(Exception):  # FrozenInstanceError or similar
            event.routing_reason = "MODIFIED"  # type: ignore[misc]

    def test_signable_content_returns_bytes(self) -> None:
        """Test signable_content returns bytes for witnessing (CT-12)."""
        from src.domain.events.meta_petition import MetaPetitionReceivedEventPayload

        event = MetaPetitionReceivedEventPayload(
            petition_id=uuid4(),
            submitter_id=uuid4(),
            petition_text_preview="Test",
            received_at=datetime.now(timezone.utc),
            routing_reason="EXPLICIT_META_TYPE",
        )

        content = event.signable_content()
        assert isinstance(content, bytes)
        assert len(content) > 0

    def test_signable_content_is_deterministic(self) -> None:
        """Test signable_content is deterministic (same inputs = same output)."""
        from src.domain.events.meta_petition import MetaPetitionReceivedEventPayload

        petition_id = uuid4()
        submitter_id = uuid4()
        timestamp = datetime(2026, 1, 22, 12, 0, 0, tzinfo=timezone.utc)

        event1 = MetaPetitionReceivedEventPayload(
            petition_id=petition_id,
            submitter_id=submitter_id,
            petition_text_preview="Test",
            received_at=timestamp,
            routing_reason="EXPLICIT_META_TYPE",
        )

        event2 = MetaPetitionReceivedEventPayload(
            petition_id=petition_id,
            submitter_id=submitter_id,
            petition_text_preview="Test",
            received_at=timestamp,
            routing_reason="EXPLICIT_META_TYPE",
        )

        assert event1.signable_content() == event2.signable_content()

    def test_to_dict_includes_schema_version(self) -> None:
        """Test to_dict includes schema_version (D2 compliance)."""
        from src.domain.events.meta_petition import MetaPetitionReceivedEventPayload

        event = MetaPetitionReceivedEventPayload(
            petition_id=uuid4(),
            submitter_id=uuid4(),
            petition_text_preview="Test",
            received_at=datetime.now(timezone.utc),
            routing_reason="EXPLICIT_META_TYPE",
        )

        result = event.to_dict()
        assert "schema_version" in result
        assert result["schema_version"] == "1.0.0"

    def test_to_dict_serializes_uuids_as_strings(self) -> None:
        """Test to_dict serializes UUIDs as strings."""
        from src.domain.events.meta_petition import MetaPetitionReceivedEventPayload

        petition_id = uuid4()
        submitter_id = uuid4()

        event = MetaPetitionReceivedEventPayload(
            petition_id=petition_id,
            submitter_id=submitter_id,
            petition_text_preview="Test",
            received_at=datetime.now(timezone.utc),
            routing_reason="EXPLICIT_META_TYPE",
        )

        result = event.to_dict()
        assert result["petition_id"] == str(petition_id)
        assert result["submitter_id"] == str(submitter_id)


class TestMetaPetitionResolvedEventPayload:
    """Tests for MetaPetitionResolvedEventPayload (AC4, AC6)."""

    def test_event_creation_acknowledge(self) -> None:
        """Test MetaPetitionResolvedEventPayload creation with ACKNOWLEDGE."""
        from src.domain.events.meta_petition import MetaPetitionResolvedEventPayload
        from src.domain.models.meta_petition import MetaDisposition

        event = MetaPetitionResolvedEventPayload(
            petition_id=uuid4(),
            disposition=MetaDisposition.ACKNOWLEDGE,
            rationale="Acknowledged the system feedback concern",
            high_archon_id=uuid4(),
            resolved_at=datetime.now(timezone.utc),
            forward_target=None,
        )

        assert event.disposition == MetaDisposition.ACKNOWLEDGE
        assert event.forward_target is None

    def test_event_creation_forward_with_target(self) -> None:
        """Test MetaPetitionResolvedEventPayload creation with FORWARD and target."""
        from src.domain.events.meta_petition import MetaPetitionResolvedEventPayload
        from src.domain.models.meta_petition import MetaDisposition

        event = MetaPetitionResolvedEventPayload(
            petition_id=uuid4(),
            disposition=MetaDisposition.FORWARD,
            rationale="Forwarding to governance council for review",
            high_archon_id=uuid4(),
            resolved_at=datetime.now(timezone.utc),
            forward_target="governance_council",
        )

        assert event.disposition == MetaDisposition.FORWARD
        assert event.forward_target == "governance_council"

    def test_event_is_frozen(self) -> None:
        """Test MetaPetitionResolvedEventPayload is immutable (CT-12)."""
        from src.domain.events.meta_petition import MetaPetitionResolvedEventPayload
        from src.domain.models.meta_petition import MetaDisposition

        event = MetaPetitionResolvedEventPayload(
            petition_id=uuid4(),
            disposition=MetaDisposition.ACKNOWLEDGE,
            rationale="Test rationale",
            high_archon_id=uuid4(),
            resolved_at=datetime.now(timezone.utc),
            forward_target=None,
        )

        with pytest.raises(Exception):  # FrozenInstanceError or similar
            event.rationale = "MODIFIED"  # type: ignore[misc]

    def test_signable_content_returns_bytes(self) -> None:
        """Test signable_content returns bytes for witnessing (CT-12)."""
        from src.domain.events.meta_petition import MetaPetitionResolvedEventPayload
        from src.domain.models.meta_petition import MetaDisposition

        event = MetaPetitionResolvedEventPayload(
            petition_id=uuid4(),
            disposition=MetaDisposition.ACKNOWLEDGE,
            rationale="Test",
            high_archon_id=uuid4(),
            resolved_at=datetime.now(timezone.utc),
            forward_target=None,
        )

        content = event.signable_content()
        assert isinstance(content, bytes)
        assert len(content) > 0

    def test_to_dict_includes_schema_version(self) -> None:
        """Test to_dict includes schema_version (D2 compliance)."""
        from src.domain.events.meta_petition import MetaPetitionResolvedEventPayload
        from src.domain.models.meta_petition import MetaDisposition

        event = MetaPetitionResolvedEventPayload(
            petition_id=uuid4(),
            disposition=MetaDisposition.ACKNOWLEDGE,
            rationale="Test",
            high_archon_id=uuid4(),
            resolved_at=datetime.now(timezone.utc),
            forward_target=None,
        )

        result = event.to_dict()
        assert "schema_version" in result
        assert result["schema_version"] == "1.0.0"

    def test_to_dict_includes_all_fields(self) -> None:
        """Test to_dict includes all required fields."""
        from src.domain.events.meta_petition import MetaPetitionResolvedEventPayload
        from src.domain.models.meta_petition import MetaDisposition

        event = MetaPetitionResolvedEventPayload(
            petition_id=uuid4(),
            disposition=MetaDisposition.FORWARD,
            rationale="Test rationale",
            high_archon_id=uuid4(),
            resolved_at=datetime.now(timezone.utc),
            forward_target="target_body",
        )

        result = event.to_dict()
        assert "petition_id" in result
        assert "disposition" in result
        assert "rationale" in result
        assert "high_archon_id" in result
        assert "resolved_at" in result
        assert "forward_target" in result
        assert result["forward_target"] == "target_body"


class TestMetaPetitionQueueItem:
    """Tests for MetaPetitionQueueItem model (AC3)."""

    def test_queue_item_creation(self) -> None:
        """Test MetaPetitionQueueItem creation."""
        from src.domain.models.meta_petition import MetaPetitionQueueItem, MetaPetitionStatus

        item = MetaPetitionQueueItem(
            petition_id=uuid4(),
            submitter_id=uuid4(),
            petition_text="Test petition about system improvements",
            received_at=datetime.now(timezone.utc),
            status=MetaPetitionStatus.PENDING,
        )

        assert item.status == MetaPetitionStatus.PENDING
        assert item.petition_text == "Test petition about system improvements"

    def test_queue_item_is_frozen(self) -> None:
        """Test MetaPetitionQueueItem is immutable."""
        from src.domain.models.meta_petition import MetaPetitionQueueItem, MetaPetitionStatus

        item = MetaPetitionQueueItem(
            petition_id=uuid4(),
            submitter_id=uuid4(),
            petition_text="Test",
            received_at=datetime.now(timezone.utc),
            status=MetaPetitionStatus.PENDING,
        )

        with pytest.raises(Exception):  # FrozenInstanceError or similar
            item.status = MetaPetitionStatus.RESOLVED  # type: ignore[misc]

    def test_queue_item_with_resolved_status(self) -> None:
        """Test MetaPetitionQueueItem with RESOLVED status."""
        from src.domain.models.meta_petition import MetaPetitionQueueItem, MetaPetitionStatus

        item = MetaPetitionQueueItem(
            petition_id=uuid4(),
            submitter_id=uuid4(),
            petition_text="Test",
            received_at=datetime.now(timezone.utc),
            status=MetaPetitionStatus.RESOLVED,
        )

        assert item.status == MetaPetitionStatus.RESOLVED
