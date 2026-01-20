"""Unit tests for DeliberationTimeoutEvent (Story 2B.2, AC-2, AC-8).

Tests the timeout event model and its invariants.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.events.deliberation_timeout import (
    DELIBERATION_TIMEOUT_EVENT_TYPE,
    DELIBERATION_TIMEOUT_SCHEMA_VERSION,
    DeliberationTimeoutEvent,
)
from src.domain.models.deliberation_session import DeliberationPhase


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class TestDeliberationTimeoutEvent:
    """Tests for DeliberationTimeoutEvent model."""

    def test_create_valid_timeout_event(self) -> None:
        """Should create a valid timeout event with all required fields."""
        event_id = uuid4()
        session_id = uuid4()
        petition_id = uuid4()
        archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
        started_at = _utc_now() - timedelta(minutes=5)
        timeout_at = _utc_now()

        event = DeliberationTimeoutEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            phase_at_timeout=DeliberationPhase.ASSESS,
            started_at=started_at,
            timeout_at=timeout_at,
            configured_timeout_seconds=300,
            participating_archons=(archon1, archon2, archon3),
        )

        assert event.event_id == event_id
        assert event.session_id == session_id
        assert event.petition_id == petition_id
        assert event.phase_at_timeout == DeliberationPhase.ASSESS
        assert event.started_at == started_at
        assert event.timeout_at == timeout_at
        assert event.configured_timeout_seconds == 300
        assert event.participating_archons == (archon1, archon2, archon3)
        assert event.schema_version == DELIBERATION_TIMEOUT_SCHEMA_VERSION

    def test_event_type_constant(self) -> None:
        """Event type constant should be correct."""
        assert DELIBERATION_TIMEOUT_EVENT_TYPE == "deliberation.timeout.expired"

    def test_schema_version_constant(self) -> None:
        """Schema version constant should be 1."""
        assert DELIBERATION_TIMEOUT_SCHEMA_VERSION == 1

    def test_elapsed_seconds_property(self) -> None:
        """Should calculate elapsed time correctly."""
        started_at = _utc_now() - timedelta(minutes=5, seconds=30)
        timeout_at = _utc_now()

        event = DeliberationTimeoutEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            phase_at_timeout=DeliberationPhase.POSITION,
            started_at=started_at,
            timeout_at=timeout_at,
            configured_timeout_seconds=300,
            participating_archons=(uuid4(), uuid4(), uuid4()),
        )

        # Should be approximately 330 seconds (5 min 30 sec)
        assert 329 <= event.elapsed_seconds <= 331

    def test_was_phase_in_progress_active_phase(self) -> None:
        """Should return True for active phases."""
        active_phases = [
            DeliberationPhase.ASSESS,
            DeliberationPhase.POSITION,
            DeliberationPhase.CROSS_EXAMINE,
            DeliberationPhase.VOTE,
        ]

        for phase in active_phases:
            event = DeliberationTimeoutEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                petition_id=uuid4(),
                phase_at_timeout=phase,
                started_at=_utc_now() - timedelta(minutes=5),
                timeout_at=_utc_now(),
                configured_timeout_seconds=300,
                participating_archons=(uuid4(), uuid4(), uuid4()),
            )
            assert event.was_phase_in_progress is True, f"Failed for phase {phase}"

    def test_was_phase_in_progress_terminal_phase(self) -> None:
        """Should return False for terminal phase."""
        event = DeliberationTimeoutEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            phase_at_timeout=DeliberationPhase.COMPLETE,
            started_at=_utc_now() - timedelta(minutes=5),
            timeout_at=_utc_now(),
            configured_timeout_seconds=300,
            participating_archons=(uuid4(), uuid4(), uuid4()),
        )
        assert event.was_phase_in_progress is False

    def test_to_dict_serialization(self) -> None:
        """Should serialize to dictionary correctly."""
        event_id = uuid4()
        session_id = uuid4()
        petition_id = uuid4()
        archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
        started_at = _utc_now() - timedelta(minutes=5)
        timeout_at = _utc_now()

        event = DeliberationTimeoutEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            phase_at_timeout=DeliberationPhase.VOTE,
            started_at=started_at,
            timeout_at=timeout_at,
            configured_timeout_seconds=300,
            participating_archons=(archon1, archon2, archon3),
        )

        result = event.to_dict()

        assert result["event_id"] == str(event_id)
        assert result["session_id"] == str(session_id)
        assert result["petition_id"] == str(petition_id)
        assert result["phase_at_timeout"] == "VOTE"
        assert result["started_at"] == started_at.isoformat()
        assert result["timeout_at"] == timeout_at.isoformat()
        assert result["configured_timeout_seconds"] == 300
        assert result["participating_archons"] == [str(archon1), str(archon2), str(archon3)]
        assert result["schema_version"] == 1
        assert "elapsed_seconds" in result
        assert "created_at" in result


class TestDeliberationTimeoutEventValidation:
    """Tests for timeout event validation."""

    def test_invalid_archon_count_less_than_3(self) -> None:
        """Should raise ValueError if fewer than 3 archons."""
        with pytest.raises(ValueError) as exc_info:
            DeliberationTimeoutEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                petition_id=uuid4(),
                phase_at_timeout=DeliberationPhase.ASSESS,
                started_at=_utc_now() - timedelta(minutes=5),
                timeout_at=_utc_now(),
                configured_timeout_seconds=300,
                participating_archons=(uuid4(), uuid4()),  # Only 2
            )

        assert "must contain exactly 3 UUIDs" in str(exc_info.value)

    def test_invalid_archon_count_more_than_3(self) -> None:
        """Should raise ValueError if more than 3 archons."""
        with pytest.raises(ValueError) as exc_info:
            DeliberationTimeoutEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                petition_id=uuid4(),
                phase_at_timeout=DeliberationPhase.ASSESS,
                started_at=_utc_now() - timedelta(minutes=5),
                timeout_at=_utc_now(),
                configured_timeout_seconds=300,
                participating_archons=(uuid4(), uuid4(), uuid4(), uuid4()),  # 4
            )

        assert "must contain exactly 3 UUIDs" in str(exc_info.value)

    def test_invalid_timestamp_order(self) -> None:
        """Should raise ValueError if timeout_at is before started_at."""
        now = _utc_now()
        with pytest.raises(ValueError) as exc_info:
            DeliberationTimeoutEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                petition_id=uuid4(),
                phase_at_timeout=DeliberationPhase.ASSESS,
                started_at=now,
                timeout_at=now - timedelta(minutes=1),  # Before started_at
                configured_timeout_seconds=300,
                participating_archons=(uuid4(), uuid4(), uuid4()),
            )

        assert "timeout_at must be >= started_at" in str(exc_info.value)

    def test_invalid_timeout_duration_zero(self) -> None:
        """Should raise ValueError if configured_timeout_seconds is 0."""
        with pytest.raises(ValueError) as exc_info:
            DeliberationTimeoutEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                petition_id=uuid4(),
                phase_at_timeout=DeliberationPhase.ASSESS,
                started_at=_utc_now() - timedelta(minutes=5),
                timeout_at=_utc_now(),
                configured_timeout_seconds=0,
                participating_archons=(uuid4(), uuid4(), uuid4()),
            )

        assert "configured_timeout_seconds must be positive" in str(exc_info.value)

    def test_invalid_timeout_duration_negative(self) -> None:
        """Should raise ValueError if configured_timeout_seconds is negative."""
        with pytest.raises(ValueError) as exc_info:
            DeliberationTimeoutEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                petition_id=uuid4(),
                phase_at_timeout=DeliberationPhase.ASSESS,
                started_at=_utc_now() - timedelta(minutes=5),
                timeout_at=_utc_now(),
                configured_timeout_seconds=-60,
                participating_archons=(uuid4(), uuid4(), uuid4()),
            )

        assert "configured_timeout_seconds must be positive" in str(exc_info.value)

    def test_invalid_schema_version(self) -> None:
        """Should raise ValueError if schema_version is not current."""
        with pytest.raises(ValueError) as exc_info:
            DeliberationTimeoutEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                petition_id=uuid4(),
                phase_at_timeout=DeliberationPhase.ASSESS,
                started_at=_utc_now() - timedelta(minutes=5),
                timeout_at=_utc_now(),
                configured_timeout_seconds=300,
                participating_archons=(uuid4(), uuid4(), uuid4()),
                schema_version=999,  # Invalid
            )

        assert "schema_version must be" in str(exc_info.value)


class TestDeliberationTimeoutEventImmutability:
    """Tests for timeout event immutability."""

    def test_event_is_frozen(self) -> None:
        """Event should be immutable (frozen dataclass)."""
        event = DeliberationTimeoutEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            phase_at_timeout=DeliberationPhase.ASSESS,
            started_at=_utc_now() - timedelta(minutes=5),
            timeout_at=_utc_now(),
            configured_timeout_seconds=300,
            participating_archons=(uuid4(), uuid4(), uuid4()),
        )

        with pytest.raises(AttributeError):
            event.session_id = uuid4()  # type: ignore[misc]

    def test_event_equality(self) -> None:
        """Events with same values should be equal."""
        event_id = uuid4()
        session_id = uuid4()
        petition_id = uuid4()
        archons = (uuid4(), uuid4(), uuid4())
        started_at = _utc_now() - timedelta(minutes=5)
        timeout_at = _utc_now()

        created_at = _utc_now()
        event1 = DeliberationTimeoutEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            phase_at_timeout=DeliberationPhase.ASSESS,
            started_at=started_at,
            timeout_at=timeout_at,
            configured_timeout_seconds=300,
            participating_archons=archons,
            created_at=created_at,
        )

        event2 = DeliberationTimeoutEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            phase_at_timeout=DeliberationPhase.ASSESS,
            started_at=started_at,
            timeout_at=timeout_at,
            configured_timeout_seconds=300,
            participating_archons=archons,
            created_at=created_at,
        )

        assert event1 == event2
