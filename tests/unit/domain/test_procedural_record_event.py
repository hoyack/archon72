"""Unit tests for ProceduralRecordPayload domain event (Story 2.8, FR141-FR142).

Tests the procedural record event payload for deliberation records.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType
from uuid import uuid4

import pytest

from src.domain.events.procedural_record import (
    PROCEDURAL_RECORD_EVENT_TYPE,
    ProceduralRecordPayload,
)


class TestProceduralRecordEventType:
    """Tests for PROCEDURAL_RECORD_EVENT_TYPE constant."""

    def test_event_type_follows_naming_convention(self) -> None:
        """Event type should follow lowercase.dot.notation convention."""
        assert PROCEDURAL_RECORD_EVENT_TYPE == "deliberation.record.procedural"

    def test_event_type_is_string(self) -> None:
        """Event type should be a string."""
        assert isinstance(PROCEDURAL_RECORD_EVENT_TYPE, str)


class TestProceduralRecordPayload:
    """Tests for ProceduralRecordPayload frozen dataclass."""

    def test_create_valid_payload(self) -> None:
        """Should create a valid ProceduralRecordPayload with all fields."""
        record_id = uuid4()
        deliberation_id = uuid4()
        agenda_items = ("Motion A", "Motion B")
        participant_ids = ("agent-1", "agent-2", "agent-3")
        vote_summary = MappingProxyType({"aye": 45, "nay": 20, "abstain": 7})
        timeline_events = (
            MappingProxyType({"timestamp": "2025-12-28T10:00:00Z", "event": "started"}),
            MappingProxyType({"timestamp": "2025-12-28T11:00:00Z", "event": "ended"}),
        )
        decisions = ("Approved Motion A", "Rejected Motion B")
        record_hash = "a" * 64
        created_at = datetime.now(timezone.utc)

        payload = ProceduralRecordPayload(
            record_id=record_id,
            deliberation_id=deliberation_id,
            agenda_items=agenda_items,
            participant_ids=participant_ids,
            vote_summary=vote_summary,
            timeline_events=timeline_events,
            decisions=decisions,
            record_hash=record_hash,
            created_at=created_at,
        )

        assert payload.record_id == record_id
        assert payload.deliberation_id == deliberation_id
        assert payload.agenda_items == agenda_items
        assert payload.participant_ids == participant_ids
        assert payload.vote_summary == vote_summary
        assert payload.timeline_events == timeline_events
        assert payload.decisions == decisions
        assert payload.record_hash == record_hash
        assert payload.created_at == created_at

    def test_payload_is_frozen(self) -> None:
        """Payload should be immutable (frozen dataclass)."""
        payload = ProceduralRecordPayload(
            record_id=uuid4(),
            deliberation_id=uuid4(),
            agenda_items=("Motion A",),
            participant_ids=("agent-1",),
            vote_summary=MappingProxyType({"aye": 10}),
            timeline_events=(),
            decisions=(),
            record_hash="b" * 64,
            created_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            payload.record_hash = "c" * 64  # type: ignore[misc]

    def test_invalid_record_id_not_uuid(self) -> None:
        """Should raise TypeError if record_id is not a UUID."""
        with pytest.raises(TypeError, match="record_id must be UUID"):
            ProceduralRecordPayload(
                record_id="not-a-uuid",  # type: ignore[arg-type]
                deliberation_id=uuid4(),
                agenda_items=(),
                participant_ids=(),
                vote_summary=MappingProxyType({}),
                timeline_events=(),
                decisions=(),
                record_hash="d" * 64,
                created_at=datetime.now(timezone.utc),
            )

    def test_invalid_deliberation_id_not_uuid(self) -> None:
        """Should raise TypeError if deliberation_id is not a UUID."""
        with pytest.raises(TypeError, match="deliberation_id must be UUID"):
            ProceduralRecordPayload(
                record_id=uuid4(),
                deliberation_id="not-a-uuid",  # type: ignore[arg-type]
                agenda_items=(),
                participant_ids=(),
                vote_summary=MappingProxyType({}),
                timeline_events=(),
                decisions=(),
                record_hash="e" * 64,
                created_at=datetime.now(timezone.utc),
            )

    def test_invalid_record_hash_wrong_length(self) -> None:
        """Should raise ValueError if record_hash is not 64 characters."""
        with pytest.raises(
            ValueError, match="record_hash must be 64 character hex string"
        ):
            ProceduralRecordPayload(
                record_id=uuid4(),
                deliberation_id=uuid4(),
                agenda_items=(),
                participant_ids=(),
                vote_summary=MappingProxyType({}),
                timeline_events=(),
                decisions=(),
                record_hash="short",
                created_at=datetime.now(timezone.utc),
            )

    def test_empty_collections_allowed(self) -> None:
        """Should allow empty collections (edge case)."""
        payload = ProceduralRecordPayload(
            record_id=uuid4(),
            deliberation_id=uuid4(),
            agenda_items=(),
            participant_ids=(),
            vote_summary=MappingProxyType({}),
            timeline_events=(),
            decisions=(),
            record_hash="f" * 64,
            created_at=datetime.now(timezone.utc),
        )
        assert payload.agenda_items == ()
        assert payload.participant_ids == ()
        assert payload.decisions == ()

    def test_invalid_agenda_items_not_tuple(self) -> None:
        """Should raise TypeError if agenda_items is not a tuple."""
        with pytest.raises(TypeError, match="agenda_items must be tuple"):
            ProceduralRecordPayload(
                record_id=uuid4(),
                deliberation_id=uuid4(),
                agenda_items=["Motion A"],  # type: ignore[arg-type]
                participant_ids=(),
                vote_summary=MappingProxyType({}),
                timeline_events=(),
                decisions=(),
                record_hash="0" * 64,
                created_at=datetime.now(timezone.utc),
            )

    def test_invalid_participant_ids_not_tuple(self) -> None:
        """Should raise TypeError if participant_ids is not a tuple."""
        with pytest.raises(TypeError, match="participant_ids must be tuple"):
            ProceduralRecordPayload(
                record_id=uuid4(),
                deliberation_id=uuid4(),
                agenda_items=(),
                participant_ids=["agent-1"],  # type: ignore[arg-type]
                vote_summary=MappingProxyType({}),
                timeline_events=(),
                decisions=(),
                record_hash="1" * 64,
                created_at=datetime.now(timezone.utc),
            )


class TestProceduralRecordPayloadToDict:
    """Tests for ProceduralRecordPayload.to_dict() method."""

    def test_to_dict_returns_all_fields(self) -> None:
        """to_dict should return all fields suitable for JSON."""
        record_id = uuid4()
        deliberation_id = uuid4()
        agenda_items = ("Motion A", "Motion B")
        participant_ids = ("agent-1", "agent-2")
        vote_summary = MappingProxyType({"aye": 45, "nay": 20})
        timeline_events = (
            MappingProxyType({"timestamp": "2025-12-28T10:00:00Z", "event": "started"}),
        )
        decisions = ("Approved Motion A",)
        record_hash = "2" * 64
        created_at = datetime(2025, 12, 28, 12, 0, 0, tzinfo=timezone.utc)

        payload = ProceduralRecordPayload(
            record_id=record_id,
            deliberation_id=deliberation_id,
            agenda_items=agenda_items,
            participant_ids=participant_ids,
            vote_summary=vote_summary,
            timeline_events=timeline_events,
            decisions=decisions,
            record_hash=record_hash,
            created_at=created_at,
        )

        result = payload.to_dict()

        assert result["record_id"] == str(record_id)
        assert result["deliberation_id"] == str(deliberation_id)
        assert result["agenda_items"] == list(agenda_items)
        assert result["participant_ids"] == list(participant_ids)
        assert result["vote_summary"] == dict(vote_summary)
        assert result["timeline_events"] == [dict(e) for e in timeline_events]
        assert result["decisions"] == list(decisions)
        assert result["record_hash"] == record_hash
        assert result["created_at"] == created_at.isoformat()

    def test_to_dict_returns_json_serializable(self) -> None:
        """to_dict result should be JSON serializable."""
        import json

        payload = ProceduralRecordPayload(
            record_id=uuid4(),
            deliberation_id=uuid4(),
            agenda_items=("Motion A",),
            participant_ids=("agent-1",),
            vote_summary=MappingProxyType({"aye": 10}),
            timeline_events=(),
            decisions=(),
            record_hash="3" * 64,
            created_at=datetime.now(timezone.utc),
        )

        result = payload.to_dict()
        # Should not raise
        json_str = json.dumps(result)
        assert isinstance(json_str, str)


class TestProceduralRecordPayloadEquality:
    """Tests for ProceduralRecordPayload equality."""

    def test_equal_payloads_are_equal(self) -> None:
        """Payloads with same values should be equal."""
        record_id = uuid4()
        deliberation_id = uuid4()
        timestamp = datetime.now(timezone.utc)

        payload1 = ProceduralRecordPayload(
            record_id=record_id,
            deliberation_id=deliberation_id,
            agenda_items=("Motion A",),
            participant_ids=("agent-1",),
            vote_summary=MappingProxyType({"aye": 10}),
            timeline_events=(),
            decisions=(),
            record_hash="4" * 64,
            created_at=timestamp,
        )

        payload2 = ProceduralRecordPayload(
            record_id=record_id,
            deliberation_id=deliberation_id,
            agenda_items=("Motion A",),
            participant_ids=("agent-1",),
            vote_summary=MappingProxyType({"aye": 10}),
            timeline_events=(),
            decisions=(),
            record_hash="4" * 64,
            created_at=timestamp,
        )

        assert payload1 == payload2

    def test_different_payloads_are_not_equal(self) -> None:
        """Payloads with different values should not be equal."""
        timestamp = datetime.now(timezone.utc)

        payload1 = ProceduralRecordPayload(
            record_id=uuid4(),
            deliberation_id=uuid4(),
            agenda_items=("Motion A",),
            participant_ids=("agent-1",),
            vote_summary=MappingProxyType({"aye": 10}),
            timeline_events=(),
            decisions=(),
            record_hash="5" * 64,
            created_at=timestamp,
        )

        payload2 = ProceduralRecordPayload(
            record_id=uuid4(),
            deliberation_id=uuid4(),
            agenda_items=("Motion B",),
            participant_ids=("agent-2",),
            vote_summary=MappingProxyType({"nay": 20}),
            timeline_events=(),
            decisions=(),
            record_hash="6" * 64,
            created_at=timestamp,
        )

        assert payload1 != payload2
