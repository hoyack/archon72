"""Unit tests for RollbackCompletedEvent payload (Story 3.10, Task 5).

Tests the event payload for successful rollback completion (AC3).

Constitutional Constraints:
- FR143: Rollback logged as constitutional event
- CT-11: Rollback must be witnessed
- PREVENT_DELETE: Events are orphaned, not deleted
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.rollback_completed import (
    ROLLBACK_COMPLETED_EVENT_TYPE,
    RollbackCompletedPayload,
)


class TestEventTypeConstant:
    """Tests for event type constant."""

    def test_event_type_constant(self) -> None:
        """Event type constant should be defined correctly."""
        assert ROLLBACK_COMPLETED_EVENT_TYPE == "rollback_completed"


class TestPayloadCreation:
    """Tests for payload creation."""

    def test_payload_creation(self) -> None:
        """RollbackCompletedPayload should be created with all required fields."""
        checkpoint_id = uuid4()
        ceremony_id = uuid4()
        timestamp = datetime.now(timezone.utc)

        payload = RollbackCompletedPayload(
            target_checkpoint_id=checkpoint_id,
            previous_head_sequence=1000,
            new_head_sequence=500,
            orphaned_event_count=500,
            orphaned_sequence_range=(501, 1001),  # exclusive end
            rollback_timestamp=timestamp,
            ceremony_id=ceremony_id,
            approving_keepers=("keeper-001", "keeper-002"),
        )

        assert payload.target_checkpoint_id == checkpoint_id
        assert payload.previous_head_sequence == 1000
        assert payload.new_head_sequence == 500
        assert payload.orphaned_event_count == 500
        assert payload.orphaned_sequence_range == (501, 1001)
        assert payload.rollback_timestamp == timestamp
        assert payload.ceremony_id == ceremony_id
        assert payload.approving_keepers == ("keeper-001", "keeper-002")


class TestPayloadImmutability:
    """Tests for payload immutability."""

    def test_payload_immutable(self) -> None:
        """RollbackCompletedPayload should be immutable."""
        payload = RollbackCompletedPayload(
            target_checkpoint_id=uuid4(),
            previous_head_sequence=1000,
            new_head_sequence=500,
            orphaned_event_count=500,
            orphaned_sequence_range=(501, 1001),
            rollback_timestamp=datetime.now(timezone.utc),
            ceremony_id=uuid4(),
            approving_keepers=("keeper-001",),
        )

        with pytest.raises(AttributeError):
            payload.new_head_sequence = 600  # type: ignore[misc]


class TestPayloadCheckpointDetails:
    """Tests for checkpoint details in payload."""

    def test_payload_includes_checkpoint_details(self) -> None:
        """Payload should include checkpoint ID."""
        checkpoint_id = uuid4()

        payload = RollbackCompletedPayload(
            target_checkpoint_id=checkpoint_id,
            previous_head_sequence=1000,
            new_head_sequence=500,
            orphaned_event_count=500,
            orphaned_sequence_range=(501, 1001),
            rollback_timestamp=datetime.now(timezone.utc),
            ceremony_id=uuid4(),
            approving_keepers=("keeper-001",),
        )

        assert payload.target_checkpoint_id == checkpoint_id


class TestPayloadOrphanedEventCount:
    """Tests for orphaned event count in payload."""

    def test_payload_includes_orphaned_event_count(self) -> None:
        """Payload should include count of orphaned events."""
        payload = RollbackCompletedPayload(
            target_checkpoint_id=uuid4(),
            previous_head_sequence=1500,
            new_head_sequence=800,
            orphaned_event_count=700,
            orphaned_sequence_range=(801, 1501),
            rollback_timestamp=datetime.now(timezone.utc),
            ceremony_id=uuid4(),
            approving_keepers=("keeper-001",),
        )

        assert payload.orphaned_event_count == 700
        # Range should be (start, end) exclusive
        assert payload.orphaned_sequence_range[0] == 801
        assert payload.orphaned_sequence_range[1] == 1501


class TestPayloadNewHeadSequence:
    """Tests for new head sequence in payload."""

    def test_payload_includes_new_head_sequence(self) -> None:
        """Payload should include new HEAD sequence after rollback."""
        payload = RollbackCompletedPayload(
            target_checkpoint_id=uuid4(),
            previous_head_sequence=1000,
            new_head_sequence=500,
            orphaned_event_count=500,
            orphaned_sequence_range=(501, 1001),
            rollback_timestamp=datetime.now(timezone.utc),
            ceremony_id=uuid4(),
            approving_keepers=("keeper-001",),
        )

        assert payload.new_head_sequence == 500
        assert payload.previous_head_sequence == 1000


class TestPayloadCeremonyId:
    """Tests for ceremony ID in payload."""

    def test_payload_includes_ceremony_id(self) -> None:
        """Payload should include ceremony ID for audit trail."""
        ceremony_id = uuid4()

        payload = RollbackCompletedPayload(
            target_checkpoint_id=uuid4(),
            previous_head_sequence=1000,
            new_head_sequence=500,
            orphaned_event_count=500,
            orphaned_sequence_range=(501, 1001),
            rollback_timestamp=datetime.now(timezone.utc),
            ceremony_id=ceremony_id,
            approving_keepers=("keeper-001", "keeper-002"),
        )

        assert payload.ceremony_id == ceremony_id
        assert payload.approving_keepers == ("keeper-001", "keeper-002")


class TestPayloadSignableContent:
    """Tests for signable_content method."""

    def test_payload_signable_content(self) -> None:
        """signable_content should return canonical bytes for signing."""
        checkpoint_id = uuid4()
        ceremony_id = uuid4()
        timestamp = datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc)

        payload = RollbackCompletedPayload(
            target_checkpoint_id=checkpoint_id,
            previous_head_sequence=1000,
            new_head_sequence=500,
            orphaned_event_count=500,
            orphaned_sequence_range=(501, 1001),
            rollback_timestamp=timestamp,
            ceremony_id=ceremony_id,
            approving_keepers=("keeper-001", "keeper-002"),
        )

        content = payload.signable_content()

        # Should be bytes
        assert isinstance(content, bytes)

        # Should contain key fields
        assert str(checkpoint_id).encode() in content
        assert b"500" in content
        assert b"1000" in content

    def test_payload_signable_content_deterministic(self) -> None:
        """signable_content should return same bytes for same payload."""
        checkpoint_id = uuid4()
        ceremony_id = uuid4()
        timestamp = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        payload = RollbackCompletedPayload(
            target_checkpoint_id=checkpoint_id,
            previous_head_sequence=1000,
            new_head_sequence=500,
            orphaned_event_count=500,
            orphaned_sequence_range=(501, 1001),
            rollback_timestamp=timestamp,
            ceremony_id=ceremony_id,
            approving_keepers=("keeper-001",),
        )

        content1 = payload.signable_content()
        content2 = payload.signable_content()

        assert content1 == content2
