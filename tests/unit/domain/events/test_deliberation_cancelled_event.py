"""Unit tests for DeliberationCancelledEvent (Story 5.6, AC4).

Tests the deliberation cancelled event payload used when a deliberation session
is cancelled, typically due to auto-escalation.

Constitutional Constraints:
- FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached [P0]
- CT-12: All outputs through witnessing pipeline
- D2: Use to_dict() not asdict(), include schema_version
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.deliberation_cancelled import (
    DELIBERATION_CANCELLED_EVENT_TYPE,
    DELIBERATION_CANCELLED_SCHEMA_VERSION,
    CancelReason,
    DeliberationCancelledEvent,
)


class TestDeliberationCancelledEventConstants:
    """Test module constants."""

    def test_event_type_constant(self) -> None:
        """Event type constant is correctly defined."""
        assert DELIBERATION_CANCELLED_EVENT_TYPE == "deliberation.session.cancelled"

    def test_schema_version_constant(self) -> None:
        """Schema version is 1 per D2 compliance."""
        assert DELIBERATION_CANCELLED_SCHEMA_VERSION == 1


class TestCancelReason:
    """Test CancelReason enum."""

    def test_auto_escalated_value(self) -> None:
        """AUTO_ESCALATED has correct value."""
        assert CancelReason.AUTO_ESCALATED.value == "AUTO_ESCALATED"

    def test_timeout_value(self) -> None:
        """TIMEOUT has correct value."""
        assert CancelReason.TIMEOUT.value == "TIMEOUT"

    def test_manual_value(self) -> None:
        """MANUAL has correct value."""
        assert CancelReason.MANUAL.value == "MANUAL"

    def test_petition_withdrawn_value(self) -> None:
        """PETITION_WITHDRAWN has correct value."""
        assert CancelReason.PETITION_WITHDRAWN.value == "PETITION_WITHDRAWN"

    def test_all_reasons(self) -> None:
        """All expected cancel reasons exist."""
        expected = {"AUTO_ESCALATED", "TIMEOUT", "MANUAL", "PETITION_WITHDRAWN"}
        actual = {r.value for r in CancelReason}
        assert actual == expected


class TestDeliberationCancelledEventCreation:
    """Test event creation and field values."""

    def test_create_with_required_fields(self) -> None:
        """Event can be created with required fields only."""
        event_id = uuid4()
        session_id = uuid4()
        petition_id = uuid4()
        escalation_id = uuid4()
        cancelled_at = datetime.now(timezone.utc)

        event = DeliberationCancelledEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            cancel_reason=CancelReason.AUTO_ESCALATED,
            cancelled_at=cancelled_at,
            escalation_id=escalation_id,
        )

        assert event.event_id == event_id
        assert event.session_id == session_id
        assert event.petition_id == petition_id
        assert event.cancel_reason == CancelReason.AUTO_ESCALATED
        assert event.cancelled_at == cancelled_at
        assert event.escalation_id == escalation_id

    def test_default_values(self) -> None:
        """Event has correct default values."""
        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=datetime.now(timezone.utc),
        )

        assert event.cancelled_by is None
        assert event.transcript_preserved is True
        assert event.participating_archons == ()
        assert event.escalation_id is None
        assert event.schema_version == 1

    def test_create_with_all_fields(self) -> None:
        """Event can be created with all optional fields."""
        event_id = uuid4()
        session_id = uuid4()
        petition_id = uuid4()
        cancelled_by = uuid4()
        escalation_id = uuid4()
        archon1 = uuid4()
        archon2 = uuid4()
        cancelled_at = datetime.now(timezone.utc)

        event = DeliberationCancelledEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            cancel_reason=CancelReason.AUTO_ESCALATED,
            cancelled_at=cancelled_at,
            cancelled_by=cancelled_by,
            transcript_preserved=True,
            participating_archons=(archon1, archon2),
            escalation_id=escalation_id,
        )

        assert event.cancelled_by == cancelled_by
        assert event.transcript_preserved is True
        assert event.participating_archons == (archon1, archon2)
        assert event.escalation_id == escalation_id


class TestDeliberationCancelledEventValidation:
    """Test event validation in __post_init__."""

    def test_auto_escalated_requires_escalation_id(self) -> None:
        """AUTO_ESCALATED reason requires escalation_id."""
        with pytest.raises(ValueError, match="escalation_id is required"):
            DeliberationCancelledEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                petition_id=uuid4(),
                cancel_reason=CancelReason.AUTO_ESCALATED,
                cancelled_at=datetime.now(timezone.utc),
                escalation_id=None,  # Invalid for AUTO_ESCALATED
            )

    def test_timeout_allows_none_escalation_id(self) -> None:
        """TIMEOUT reason allows None escalation_id."""
        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=datetime.now(timezone.utc),
            escalation_id=None,
        )
        assert event.escalation_id is None

    def test_manual_allows_none_escalation_id(self) -> None:
        """MANUAL reason allows None escalation_id."""
        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.MANUAL,
            cancelled_at=datetime.now(timezone.utc),
            escalation_id=None,
        )
        assert event.escalation_id is None

    def test_invalid_schema_version_rejected(self) -> None:
        """Invalid schema_version is rejected."""
        with pytest.raises(ValueError, match="schema_version must be 1"):
            DeliberationCancelledEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                petition_id=uuid4(),
                cancel_reason=CancelReason.TIMEOUT,
                cancelled_at=datetime.now(timezone.utc),
                schema_version=2,  # Invalid
            )


class TestDeliberationCancelledEventImmutability:
    """Test event immutability (frozen dataclass)."""

    def test_frozen(self) -> None:
        """Event is immutable (frozen dataclass)."""
        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            event.cancel_reason = CancelReason.MANUAL  # type: ignore[misc]


class TestDeliberationCancelledEventEquality:
    """Test event equality comparison."""

    def test_equality(self) -> None:
        """Events with same fields are equal."""
        event_id = uuid4()
        session_id = uuid4()
        petition_id = uuid4()
        cancelled_at = datetime.now(timezone.utc)

        event1 = DeliberationCancelledEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=cancelled_at,
        )
        event2 = DeliberationCancelledEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=cancelled_at,
        )

        assert event1 == event2

    def test_inequality_different_event_id(self) -> None:
        """Events with different event_id are not equal."""
        session_id = uuid4()
        petition_id = uuid4()
        cancelled_at = datetime.now(timezone.utc)

        event1 = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=session_id,
            petition_id=petition_id,
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=cancelled_at,
        )
        event2 = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=session_id,
            petition_id=petition_id,
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=cancelled_at,
        )

        assert event1 != event2


class TestDeliberationCancelledEventSignableContent:
    """Test signable_content method for CT-12 witnessing."""

    def test_signable_content_returns_bytes(self) -> None:
        """signable_content returns UTF-8 encoded bytes."""
        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=datetime.now(timezone.utc),
        )

        content = event.signable_content()

        assert isinstance(content, bytes)

    def test_signable_content_is_valid_json(self) -> None:
        """signable_content produces valid JSON."""
        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=datetime.now(timezone.utc),
        )

        content = event.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert isinstance(parsed, dict)

    def test_signable_content_is_deterministic(self) -> None:
        """signable_content produces deterministic output (CT-12)."""
        event_id = uuid4()
        session_id = uuid4()
        petition_id = uuid4()
        cancelled_at = datetime.now(timezone.utc)

        event1 = DeliberationCancelledEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=cancelled_at,
        )
        event2 = DeliberationCancelledEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=cancelled_at,
        )

        assert event1.signable_content() == event2.signable_content()

    def test_signable_content_includes_all_fields(self) -> None:
        """signable_content includes all event fields."""
        event_id = uuid4()
        session_id = uuid4()
        petition_id = uuid4()
        cancelled_by = uuid4()
        escalation_id = uuid4()
        archon1 = uuid4()
        archon2 = uuid4()
        cancelled_at = datetime.now(timezone.utc)

        event = DeliberationCancelledEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            cancel_reason=CancelReason.AUTO_ESCALATED,
            cancelled_at=cancelled_at,
            cancelled_by=cancelled_by,
            transcript_preserved=True,
            participating_archons=(archon1, archon2),
            escalation_id=escalation_id,
        )

        content = event.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert parsed["event_id"] == str(event_id)
        assert parsed["session_id"] == str(session_id)
        assert parsed["petition_id"] == str(petition_id)
        assert parsed["cancel_reason"] == "AUTO_ESCALATED"
        assert parsed["cancelled_at"] == cancelled_at.isoformat()
        assert parsed["cancelled_by"] == str(cancelled_by)
        assert parsed["transcript_preserved"] is True
        assert parsed["participating_archons"] == [str(archon1), str(archon2)]
        assert parsed["escalation_id"] == str(escalation_id)
        assert parsed["schema_version"] == 1

    def test_signable_content_handles_none_values(self) -> None:
        """signable_content handles None values correctly."""
        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=datetime.now(timezone.utc),
            cancelled_by=None,
            escalation_id=None,
        )

        content = event.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert parsed["cancelled_by"] is None
        assert parsed["escalation_id"] is None

    def test_signable_content_sorted_keys(self) -> None:
        """signable_content JSON has sorted keys for determinism."""
        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=datetime.now(timezone.utc),
        )

        content = event.signable_content()
        parsed = json.loads(content.decode("utf-8"))
        keys = list(parsed.keys())

        assert keys == sorted(keys)


class TestDeliberationCancelledEventToDict:
    """Test to_dict method for D2 compliance."""

    def test_to_dict_returns_dict(self) -> None:
        """to_dict returns a dictionary."""
        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=datetime.now(timezone.utc),
        )

        result = event.to_dict()

        assert isinstance(result, dict)

    def test_to_dict_serializes_uuids_as_strings(self) -> None:
        """to_dict serializes UUIDs as strings (D2)."""
        event_id = uuid4()
        session_id = uuid4()
        petition_id = uuid4()
        cancelled_by = uuid4()
        escalation_id = uuid4()

        event = DeliberationCancelledEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            cancel_reason=CancelReason.AUTO_ESCALATED,
            cancelled_at=datetime.now(timezone.utc),
            cancelled_by=cancelled_by,
            escalation_id=escalation_id,
        )

        result = event.to_dict()

        assert result["event_id"] == str(event_id)
        assert result["session_id"] == str(session_id)
        assert result["petition_id"] == str(petition_id)
        assert result["cancelled_by"] == str(cancelled_by)
        assert result["escalation_id"] == str(escalation_id)

    def test_to_dict_serializes_datetime_as_iso8601(self) -> None:
        """to_dict serializes datetime as ISO 8601 string (D2)."""
        cancelled_at = datetime.now(timezone.utc)

        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=cancelled_at,
        )

        result = event.to_dict()

        assert result["cancelled_at"] == cancelled_at.isoformat()

    def test_to_dict_includes_schema_version(self) -> None:
        """to_dict includes schema_version for D2 compliance."""
        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=datetime.now(timezone.utc),
        )

        result = event.to_dict()

        assert "schema_version" in result
        assert result["schema_version"] == 1

    def test_to_dict_serializes_cancel_reason_as_value(self) -> None:
        """to_dict serializes cancel_reason as its string value."""
        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.AUTO_ESCALATED,
            cancelled_at=datetime.now(timezone.utc),
            escalation_id=uuid4(),
        )

        result = event.to_dict()

        assert result["cancel_reason"] == "AUTO_ESCALATED"

    def test_to_dict_serializes_participating_archons(self) -> None:
        """to_dict serializes participating_archons as list of strings."""
        archon1 = uuid4()
        archon2 = uuid4()

        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=datetime.now(timezone.utc),
            participating_archons=(archon1, archon2),
        )

        result = event.to_dict()

        assert result["participating_archons"] == [str(archon1), str(archon2)]

    def test_to_dict_includes_all_fields(self) -> None:
        """to_dict includes all event fields."""
        event_id = uuid4()
        session_id = uuid4()
        petition_id = uuid4()
        cancelled_by = uuid4()
        escalation_id = uuid4()
        archon1 = uuid4()
        cancelled_at = datetime.now(timezone.utc)

        event = DeliberationCancelledEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            cancel_reason=CancelReason.AUTO_ESCALATED,
            cancelled_at=cancelled_at,
            cancelled_by=cancelled_by,
            transcript_preserved=True,
            participating_archons=(archon1,),
            escalation_id=escalation_id,
        )

        result = event.to_dict()

        assert result["event_id"] == str(event_id)
        assert result["session_id"] == str(session_id)
        assert result["petition_id"] == str(petition_id)
        assert result["cancel_reason"] == "AUTO_ESCALATED"
        assert result["cancelled_at"] == cancelled_at.isoformat()
        assert result["cancelled_by"] == str(cancelled_by)
        assert result["transcript_preserved"] is True
        assert result["participating_archons"] == [str(archon1)]
        assert result["escalation_id"] == str(escalation_id)
        assert result["schema_version"] == 1

    def test_to_dict_handles_none_values(self) -> None:
        """to_dict handles None values correctly."""
        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=datetime.now(timezone.utc),
            cancelled_by=None,
            escalation_id=None,
        )

        result = event.to_dict()

        assert result["cancelled_by"] is None
        assert result["escalation_id"] is None

    def test_to_dict_is_json_serializable(self) -> None:
        """to_dict result can be JSON serialized."""
        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.AUTO_ESCALATED,
            cancelled_at=datetime.now(timezone.utc),
            cancelled_by=uuid4(),
            participating_archons=(uuid4(), uuid4()),
            escalation_id=uuid4(),
        )

        result = event.to_dict()

        # Should not raise
        json_str = json.dumps(result)
        assert isinstance(json_str, str)
