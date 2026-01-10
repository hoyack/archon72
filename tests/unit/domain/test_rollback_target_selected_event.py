"""Unit tests for RollbackTargetSelectedEvent payload (Story 3.10, Task 4).

Tests the event payload for when Keepers select a rollback target (AC2).

Constitutional Constraints:
- FR143: Rollback to checkpoint logged as constitutional event
- CT-11: Silent failure destroys legitimacy - selection must be witnessed
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.rollback_target_selected import (
    ROLLBACK_TARGET_SELECTED_EVENT_TYPE,
    RollbackTargetSelectedPayload,
)


class TestEventTypeConstant:
    """Tests for event type constant."""

    def test_event_type_constant(self) -> None:
        """Event type constant should be defined correctly."""
        assert ROLLBACK_TARGET_SELECTED_EVENT_TYPE == "rollback_target_selected"


class TestPayloadCreation:
    """Tests for payload creation."""

    def test_payload_creation(self) -> None:
        """RollbackTargetSelectedPayload should be created with all required fields."""
        checkpoint_id = uuid4()
        timestamp = datetime.now(timezone.utc)

        payload = RollbackTargetSelectedPayload(
            target_checkpoint_id=checkpoint_id,
            target_event_sequence=500,
            target_anchor_hash="a" * 64,
            selecting_keepers=("keeper-001", "keeper-002"),
            selection_reason="Fork detected - rolling back to last known good state",
            selection_timestamp=timestamp,
        )

        assert payload.target_checkpoint_id == checkpoint_id
        assert payload.target_event_sequence == 500
        assert payload.target_anchor_hash == "a" * 64
        assert payload.selecting_keepers == ("keeper-001", "keeper-002")
        assert "Fork detected" in payload.selection_reason
        assert payload.selection_timestamp == timestamp


class TestPayloadImmutability:
    """Tests for payload immutability."""

    def test_payload_immutable(self) -> None:
        """RollbackTargetSelectedPayload should be immutable."""
        payload = RollbackTargetSelectedPayload(
            target_checkpoint_id=uuid4(),
            target_event_sequence=100,
            target_anchor_hash="b" * 64,
            selecting_keepers=("keeper-001",),
            selection_reason="Test reason",
            selection_timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            payload.target_event_sequence = 200  # type: ignore[misc]


class TestPayloadCheckpointDetails:
    """Tests for checkpoint details in payload."""

    def test_payload_includes_checkpoint_details(self) -> None:
        """Payload should include checkpoint ID, sequence, and hash."""
        checkpoint_id = uuid4()

        payload = RollbackTargetSelectedPayload(
            target_checkpoint_id=checkpoint_id,
            target_event_sequence=1000,
            target_anchor_hash="c" * 64,
            selecting_keepers=("keeper-001",),
            selection_reason="Recovery",
            selection_timestamp=datetime.now(timezone.utc),
        )

        assert payload.target_checkpoint_id == checkpoint_id
        assert payload.target_event_sequence == 1000
        assert len(payload.target_anchor_hash) == 64


class TestPayloadSelectingKeepers:
    """Tests for selecting keepers in payload."""

    def test_payload_includes_selecting_keepers(self) -> None:
        """Payload should include tuple of selecting keeper IDs."""
        keepers = ("keeper-001", "keeper-002", "keeper-003")

        payload = RollbackTargetSelectedPayload(
            target_checkpoint_id=uuid4(),
            target_event_sequence=100,
            target_anchor_hash="d" * 64,
            selecting_keepers=keepers,
            selection_reason="Multiple keepers agree",
            selection_timestamp=datetime.now(timezone.utc),
        )

        assert payload.selecting_keepers == keepers
        assert len(payload.selecting_keepers) == 3


class TestPayloadReason:
    """Tests for selection reason in payload."""

    def test_payload_includes_reason(self) -> None:
        """Payload should include selection reason."""
        reason = "Fork detected at sequence 1234 - hash mismatch"

        payload = RollbackTargetSelectedPayload(
            target_checkpoint_id=uuid4(),
            target_event_sequence=100,
            target_anchor_hash="e" * 64,
            selecting_keepers=("keeper-001",),
            selection_reason=reason,
            selection_timestamp=datetime.now(timezone.utc),
        )

        assert payload.selection_reason == reason


class TestPayloadSignableContent:
    """Tests for signable_content method."""

    def test_payload_signable_content(self) -> None:
        """signable_content should return canonical bytes for signing."""
        checkpoint_id = uuid4()
        timestamp = datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc)

        payload = RollbackTargetSelectedPayload(
            target_checkpoint_id=checkpoint_id,
            target_event_sequence=500,
            target_anchor_hash="f" * 64,
            selecting_keepers=("keeper-001", "keeper-002"),
            selection_reason="Test rollback",
            selection_timestamp=timestamp,
        )

        content = payload.signable_content()

        # Should be bytes
        assert isinstance(content, bytes)

        # Should contain key fields
        assert str(checkpoint_id).encode() in content
        assert b"500" in content
        assert b"keeper-001" in content

    def test_payload_signable_content_deterministic(self) -> None:
        """signable_content should return same bytes for same payload."""
        checkpoint_id = uuid4()
        timestamp = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        payload = RollbackTargetSelectedPayload(
            target_checkpoint_id=checkpoint_id,
            target_event_sequence=100,
            target_anchor_hash="g" * 64,
            selecting_keepers=("keeper-001",),
            selection_reason="Test",
            selection_timestamp=timestamp,
        )

        content1 = payload.signable_content()
        content2 = payload.signable_content()

        assert content1 == content2
