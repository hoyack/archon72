"""Unit tests for DissentRecordedEvent (Story 2B.1, FR-11.8).

Tests the dissent event model and its invariants.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import blake3
import pytest
from uuid6 import uuid7

from src.domain.events.dissent import (
    DISSENT_RECORDED_EVENT_TYPE,
    DISSENT_RECORDED_SCHEMA_VERSION,
    DissentRecordedEvent,
)


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


def _compute_rationale_hash_hex(rationale: str) -> str:
    """Compute Blake3 hash of rationale as hex string."""
    return blake3.blake3(rationale.encode("utf-8")).hexdigest()


class TestDissentRecordedEventCreation:
    """Tests for DissentRecordedEvent creation."""

    def test_create_valid_event(self) -> None:
        """Should create a valid dissent event with all required fields."""
        event_id = uuid7()
        session_id = uuid7()
        petition_id = uuid7()
        archon_id = uuid4()
        rationale_hash = _compute_rationale_hash_hex("Test rationale")
        recorded_at = _utc_now()

        event = DissentRecordedEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            dissent_archon_id=archon_id,
            dissent_disposition="REFER",
            rationale_hash=rationale_hash,
            majority_disposition="ACKNOWLEDGE",
            recorded_at=recorded_at,
        )

        assert event.event_id == event_id
        assert event.session_id == session_id
        assert event.petition_id == petition_id
        assert event.dissent_archon_id == archon_id
        assert event.dissent_disposition == "REFER"
        assert event.rationale_hash == rationale_hash
        assert event.majority_disposition == "ACKNOWLEDGE"
        assert event.recorded_at == recorded_at

    def test_event_type_constant(self) -> None:
        """Event type constant should be correct."""
        assert DISSENT_RECORDED_EVENT_TYPE == "deliberation.dissent.recorded"

    def test_schema_version_constant(self) -> None:
        """Schema version constant should be 1."""
        assert DISSENT_RECORDED_SCHEMA_VERSION == 1

    def test_event_type_property(self) -> None:
        """event_type property should return correct type."""
        event = DissentRecordedEvent(
            event_id=uuid7(),
            session_id=uuid7(),
            petition_id=uuid7(),
            dissent_archon_id=uuid4(),
            dissent_disposition="ESCALATE",
            rationale_hash=_compute_rationale_hash_hex("Rationale"),
            majority_disposition="ACKNOWLEDGE",
        )

        assert event.event_type == DISSENT_RECORDED_EVENT_TYPE


class TestDissentRecordedEventValidation:
    """Tests for DissentRecordedEvent validation."""

    def test_invalid_same_dispositions(self) -> None:
        """Should raise ValueError if dissent matches majority."""
        with pytest.raises(ValueError) as exc_info:
            DissentRecordedEvent(
                event_id=uuid7(),
                session_id=uuid7(),
                petition_id=uuid7(),
                dissent_archon_id=uuid4(),
                dissent_disposition="ACKNOWLEDGE",
                rationale_hash=_compute_rationale_hash_hex("Rationale"),
                majority_disposition="ACKNOWLEDGE",  # Same!
            )

        assert "cannot match majority disposition" in str(exc_info.value)

    def test_invalid_hash_too_short(self) -> None:
        """Should raise ValueError if rationale_hash is too short."""
        with pytest.raises(ValueError) as exc_info:
            DissentRecordedEvent(
                event_id=uuid7(),
                session_id=uuid7(),
                petition_id=uuid7(),
                dissent_archon_id=uuid4(),
                dissent_disposition="REFER",
                rationale_hash="abc123",  # Too short
                majority_disposition="ACKNOWLEDGE",
            )

        assert "must be 64 hex characters" in str(exc_info.value)

    def test_invalid_hash_too_long(self) -> None:
        """Should raise ValueError if rationale_hash is too long."""
        with pytest.raises(ValueError) as exc_info:
            DissentRecordedEvent(
                event_id=uuid7(),
                session_id=uuid7(),
                petition_id=uuid7(),
                dissent_archon_id=uuid4(),
                dissent_disposition="REFER",
                rationale_hash="a" * 128,  # Too long
                majority_disposition="ACKNOWLEDGE",
            )

        assert "must be 64 hex characters" in str(exc_info.value)

    def test_invalid_hash_not_hex(self) -> None:
        """Should raise ValueError if rationale_hash is not valid hex."""
        with pytest.raises(ValueError) as exc_info:
            DissentRecordedEvent(
                event_id=uuid7(),
                session_id=uuid7(),
                petition_id=uuid7(),
                dissent_archon_id=uuid4(),
                dissent_disposition="REFER",
                rationale_hash="g" * 64,  # 'g' is not hex
                majority_disposition="ACKNOWLEDGE",
            )

        assert "must be valid hex" in str(exc_info.value)


class TestDissentRecordedEventSerialization:
    """Tests for DissentRecordedEvent serialization."""

    def test_to_dict_serialization(self) -> None:
        """Should serialize to dictionary correctly."""
        event_id = uuid7()
        session_id = uuid7()
        petition_id = uuid7()
        archon_id = uuid4()
        rationale_hash = _compute_rationale_hash_hex("Test rationale")
        recorded_at = _utc_now()

        event = DissentRecordedEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            dissent_archon_id=archon_id,
            dissent_disposition="ESCALATE",
            rationale_hash=rationale_hash,
            majority_disposition="REFER",
            recorded_at=recorded_at,
        )

        result = event.to_dict()

        assert result["event_type"] == DISSENT_RECORDED_EVENT_TYPE
        assert result["event_id"] == str(event_id)
        assert result["session_id"] == str(session_id)
        assert result["petition_id"] == str(petition_id)
        assert result["dissent_archon_id"] == str(archon_id)
        assert result["dissent_disposition"] == "ESCALATE"
        assert result["rationale_hash"] == rationale_hash
        assert result["majority_disposition"] == "REFER"
        assert result["recorded_at"] == recorded_at.isoformat()
        assert result["schema_version"] == DISSENT_RECORDED_SCHEMA_VERSION


class TestDissentRecordedEventImmutability:
    """Tests for DissentRecordedEvent immutability."""

    def test_event_is_frozen(self) -> None:
        """Event should be immutable (frozen dataclass)."""
        event = DissentRecordedEvent(
            event_id=uuid7(),
            session_id=uuid7(),
            petition_id=uuid7(),
            dissent_archon_id=uuid4(),
            dissent_disposition="REFER",
            rationale_hash=_compute_rationale_hash_hex("Rationale"),
            majority_disposition="ACKNOWLEDGE",
        )

        with pytest.raises(AttributeError):
            event.dissent_disposition = "ESCALATE"  # type: ignore[misc]

    def test_event_equality(self) -> None:
        """Events with same values should be equal."""
        event_id = uuid7()
        session_id = uuid7()
        petition_id = uuid7()
        archon_id = uuid4()
        rationale_hash = _compute_rationale_hash_hex("Same rationale")
        recorded_at = _utc_now()
        created_at = _utc_now()

        event1 = DissentRecordedEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            dissent_archon_id=archon_id,
            dissent_disposition="ESCALATE",
            rationale_hash=rationale_hash,
            majority_disposition="ACKNOWLEDGE",
            recorded_at=recorded_at,
            created_at=created_at,
        )

        event2 = DissentRecordedEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            dissent_archon_id=archon_id,
            dissent_disposition="ESCALATE",
            rationale_hash=rationale_hash,
            majority_disposition="ACKNOWLEDGE",
            recorded_at=recorded_at,
            created_at=created_at,
        )

        assert event1 == event2
