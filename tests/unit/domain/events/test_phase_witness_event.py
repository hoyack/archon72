"""Unit tests for PhaseWitnessEvent (Story 2A.7, FR-11.7).

Tests the phase witness event domain model for:
- Valid event creation
- Validation of all fields
- Hash chain integrity
- Serialization
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import blake3
import pytest

from src.domain.events.phase_witness import (
    BLAKE3_HASH_SIZE,
    PHASE_WITNESS_EVENT_TYPE,
    PhaseWitnessEvent,
)
from src.domain.models.deliberation_session import DeliberationPhase


def _create_valid_hash() -> bytes:
    """Create a valid 32-byte Blake3 hash."""
    return blake3.blake3(b"test content").digest()


def _create_archons() -> tuple:
    """Create 3 valid archon UUIDs."""
    return (uuid4(), uuid4(), uuid4())


class TestPhaseWitnessEventCreation:
    """Tests for PhaseWitnessEvent creation."""

    def test_create_assess_phase_event(self) -> None:
        """Test creating a valid ASSESS phase event."""
        event_id = uuid4()
        session_id = uuid4()
        archons = _create_archons()
        transcript_hash = _create_valid_hash()
        start = datetime.now(timezone.utc)
        end = start + timedelta(minutes=5)

        event = PhaseWitnessEvent(
            event_id=event_id,
            session_id=session_id,
            phase=DeliberationPhase.ASSESS,
            transcript_hash=transcript_hash,
            participating_archons=archons,
            start_timestamp=start,
            end_timestamp=end,
            phase_metadata={"assessments_recorded": 3},
            previous_witness_hash=None,  # ASSESS has no previous
        )

        assert event.event_id == event_id
        assert event.session_id == session_id
        assert event.phase == DeliberationPhase.ASSESS
        assert event.transcript_hash == transcript_hash
        assert event.participating_archons == archons
        assert event.start_timestamp == start
        assert event.end_timestamp == end
        assert event.phase_metadata == {"assessments_recorded": 3}
        assert event.previous_witness_hash is None

    def test_create_position_phase_event_with_previous_hash(self) -> None:
        """Test creating a POSITION phase event with previous hash."""
        previous_hash = _create_valid_hash()
        start = datetime.now(timezone.utc)
        end = start + timedelta(minutes=3)

        event = PhaseWitnessEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            phase=DeliberationPhase.POSITION,
            transcript_hash=_create_valid_hash(),
            participating_archons=_create_archons(),
            start_timestamp=start,
            end_timestamp=end,
            phase_metadata={"positions_converged": True},
            previous_witness_hash=previous_hash,
        )

        assert event.phase == DeliberationPhase.POSITION
        assert event.previous_witness_hash == previous_hash

    def test_create_all_phases(self) -> None:
        """Test creating events for all 4 phases."""
        phases = [
            (DeliberationPhase.ASSESS, None),
            (DeliberationPhase.POSITION, _create_valid_hash()),
            (DeliberationPhase.CROSS_EXAMINE, _create_valid_hash()),
            (DeliberationPhase.VOTE, _create_valid_hash()),
        ]

        for phase, prev_hash in phases:
            start = datetime.now(timezone.utc)
            end = start + timedelta(minutes=2)

            event = PhaseWitnessEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                phase=phase,
                transcript_hash=_create_valid_hash(),
                participating_archons=_create_archons(),
                start_timestamp=start,
                end_timestamp=end,
                previous_witness_hash=prev_hash,
            )

            assert event.phase == phase


class TestPhaseWitnessEventValidation:
    """Tests for PhaseWitnessEvent validation."""

    def test_invalid_transcript_hash_length(self) -> None:
        """Test rejection of invalid transcript hash length."""
        start = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="transcript_hash must be 32 bytes"):
            PhaseWitnessEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                phase=DeliberationPhase.ASSESS,
                transcript_hash=b"too short",  # Invalid
                participating_archons=_create_archons(),
                start_timestamp=start,
                end_timestamp=start + timedelta(minutes=1),
                previous_witness_hash=None,
            )

    def test_invalid_archon_count_too_few(self) -> None:
        """Test rejection of fewer than 3 archons."""
        start = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="exactly 3 UUIDs"):
            PhaseWitnessEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                phase=DeliberationPhase.ASSESS,
                transcript_hash=_create_valid_hash(),
                participating_archons=(uuid4(), uuid4()),  # Only 2
                start_timestamp=start,
                end_timestamp=start + timedelta(minutes=1),
                previous_witness_hash=None,
            )

    def test_invalid_archon_count_too_many(self) -> None:
        """Test rejection of more than 3 archons."""
        start = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="exactly 3 UUIDs"):
            PhaseWitnessEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                phase=DeliberationPhase.ASSESS,
                transcript_hash=_create_valid_hash(),
                participating_archons=(uuid4(), uuid4(), uuid4(), uuid4()),  # 4
                start_timestamp=start,
                end_timestamp=start + timedelta(minutes=1),
                previous_witness_hash=None,
            )

    def test_invalid_timestamps_end_before_start(self) -> None:
        """Test rejection when end_timestamp < start_timestamp."""
        start = datetime.now(timezone.utc)
        end = start - timedelta(minutes=1)  # Before start

        with pytest.raises(ValueError, match="end_timestamp must be >= start_timestamp"):
            PhaseWitnessEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                phase=DeliberationPhase.ASSESS,
                transcript_hash=_create_valid_hash(),
                participating_archons=_create_archons(),
                start_timestamp=start,
                end_timestamp=end,
                previous_witness_hash=None,
            )

    def test_assess_with_previous_hash_rejected(self) -> None:
        """Test ASSESS phase rejects previous_witness_hash."""
        start = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="ASSESS phase should not have previous"):
            PhaseWitnessEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                phase=DeliberationPhase.ASSESS,
                transcript_hash=_create_valid_hash(),
                participating_archons=_create_archons(),
                start_timestamp=start,
                end_timestamp=start + timedelta(minutes=1),
                previous_witness_hash=_create_valid_hash(),  # Invalid for ASSESS
            )

    def test_position_without_previous_hash_rejected(self) -> None:
        """Test POSITION phase requires previous_witness_hash."""
        start = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="POSITION phase must have previous"):
            PhaseWitnessEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                phase=DeliberationPhase.POSITION,
                transcript_hash=_create_valid_hash(),
                participating_archons=_create_archons(),
                start_timestamp=start,
                end_timestamp=start + timedelta(minutes=1),
                previous_witness_hash=None,  # Required for POSITION
            )

    def test_cross_examine_without_previous_hash_rejected(self) -> None:
        """Test CROSS_EXAMINE phase requires previous_witness_hash."""
        start = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="CROSS_EXAMINE phase must have previous"):
            PhaseWitnessEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                phase=DeliberationPhase.CROSS_EXAMINE,
                transcript_hash=_create_valid_hash(),
                participating_archons=_create_archons(),
                start_timestamp=start,
                end_timestamp=start + timedelta(minutes=1),
                previous_witness_hash=None,
            )

    def test_vote_without_previous_hash_rejected(self) -> None:
        """Test VOTE phase requires previous_witness_hash."""
        start = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="VOTE phase must have previous"):
            PhaseWitnessEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                phase=DeliberationPhase.VOTE,
                transcript_hash=_create_valid_hash(),
                participating_archons=_create_archons(),
                start_timestamp=start,
                end_timestamp=start + timedelta(minutes=1),
                previous_witness_hash=None,
            )

    def test_invalid_previous_hash_length(self) -> None:
        """Test rejection of invalid previous_witness_hash length."""
        start = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="previous_witness_hash must be 32 bytes"):
            PhaseWitnessEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                phase=DeliberationPhase.POSITION,
                transcript_hash=_create_valid_hash(),
                participating_archons=_create_archons(),
                start_timestamp=start,
                end_timestamp=start + timedelta(minutes=1),
                previous_witness_hash=b"too short",  # Invalid length
            )


class TestPhaseWitnessEventProperties:
    """Tests for PhaseWitnessEvent properties."""

    def test_transcript_hash_hex(self) -> None:
        """Test transcript_hash_hex property."""
        transcript_hash = _create_valid_hash()
        start = datetime.now(timezone.utc)

        event = PhaseWitnessEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            phase=DeliberationPhase.ASSESS,
            transcript_hash=transcript_hash,
            participating_archons=_create_archons(),
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=1),
            previous_witness_hash=None,
        )

        assert event.transcript_hash_hex == transcript_hash.hex()
        assert len(event.transcript_hash_hex) == 64  # 32 bytes = 64 hex chars

    def test_previous_witness_hash_hex_none(self) -> None:
        """Test previous_witness_hash_hex when None."""
        start = datetime.now(timezone.utc)

        event = PhaseWitnessEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            phase=DeliberationPhase.ASSESS,
            transcript_hash=_create_valid_hash(),
            participating_archons=_create_archons(),
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=1),
            previous_witness_hash=None,
        )

        assert event.previous_witness_hash_hex is None

    def test_previous_witness_hash_hex_present(self) -> None:
        """Test previous_witness_hash_hex when present."""
        previous_hash = _create_valid_hash()
        start = datetime.now(timezone.utc)

        event = PhaseWitnessEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            phase=DeliberationPhase.POSITION,
            transcript_hash=_create_valid_hash(),
            participating_archons=_create_archons(),
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=1),
            previous_witness_hash=previous_hash,
        )

        assert event.previous_witness_hash_hex == previous_hash.hex()

    def test_event_hash_deterministic(self) -> None:
        """Test event_hash is deterministic."""
        event_id = uuid4()
        session_id = uuid4()
        archons = _create_archons()
        transcript_hash = _create_valid_hash()
        start = datetime(2026, 1, 19, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 19, 10, 5, 0, tzinfo=timezone.utc)

        event = PhaseWitnessEvent(
            event_id=event_id,
            session_id=session_id,
            phase=DeliberationPhase.ASSESS,
            transcript_hash=transcript_hash,
            participating_archons=archons,
            start_timestamp=start,
            end_timestamp=end,
            previous_witness_hash=None,
        )

        # Call multiple times - should be same
        hash1 = event.event_hash
        hash2 = event.event_hash

        assert hash1 == hash2
        assert len(hash1) == BLAKE3_HASH_SIZE

    def test_event_hash_different_for_different_events(self) -> None:
        """Test event_hash differs for different events."""
        start = datetime.now(timezone.utc)
        end = start + timedelta(minutes=5)

        event1 = PhaseWitnessEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            phase=DeliberationPhase.ASSESS,
            transcript_hash=_create_valid_hash(),
            participating_archons=_create_archons(),
            start_timestamp=start,
            end_timestamp=end,
            previous_witness_hash=None,
        )

        event2 = PhaseWitnessEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            phase=DeliberationPhase.ASSESS,
            transcript_hash=_create_valid_hash(),
            participating_archons=_create_archons(),
            start_timestamp=start,
            end_timestamp=end,
            previous_witness_hash=None,
        )

        assert event1.event_hash != event2.event_hash

    def test_event_hash_hex(self) -> None:
        """Test event_hash_hex property."""
        start = datetime.now(timezone.utc)

        event = PhaseWitnessEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            phase=DeliberationPhase.ASSESS,
            transcript_hash=_create_valid_hash(),
            participating_archons=_create_archons(),
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=1),
            previous_witness_hash=None,
        )

        assert event.event_hash_hex == event.event_hash.hex()
        assert len(event.event_hash_hex) == 64


class TestPhaseWitnessEventSerialization:
    """Tests for PhaseWitnessEvent serialization."""

    def test_to_dict(self) -> None:
        """Test to_dict serialization."""
        event_id = uuid4()
        session_id = uuid4()
        archons = _create_archons()
        transcript_hash = _create_valid_hash()
        start = datetime(2026, 1, 19, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 19, 10, 5, 0, tzinfo=timezone.utc)
        metadata = {"key": "value"}

        event = PhaseWitnessEvent(
            event_id=event_id,
            session_id=session_id,
            phase=DeliberationPhase.ASSESS,
            transcript_hash=transcript_hash,
            participating_archons=archons,
            start_timestamp=start,
            end_timestamp=end,
            phase_metadata=metadata,
            previous_witness_hash=None,
        )

        result = event.to_dict()

        assert result["event_id"] == str(event_id)
        assert result["session_id"] == str(session_id)
        assert result["phase"] == "ASSESS"
        assert result["transcript_hash"] == transcript_hash.hex()
        assert result["participating_archons"] == [str(a) for a in archons]
        assert result["start_timestamp"] == start.isoformat()
        assert result["end_timestamp"] == end.isoformat()
        assert result["phase_metadata"] == metadata
        assert result["previous_witness_hash"] is None
        assert "created_at" in result
        assert "event_hash" in result

    def test_to_dict_with_previous_hash(self) -> None:
        """Test to_dict with previous_witness_hash."""
        previous_hash = _create_valid_hash()
        start = datetime.now(timezone.utc)

        event = PhaseWitnessEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            phase=DeliberationPhase.POSITION,
            transcript_hash=_create_valid_hash(),
            participating_archons=_create_archons(),
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=1),
            phase_metadata={},
            previous_witness_hash=previous_hash,
        )

        result = event.to_dict()

        assert result["previous_witness_hash"] == previous_hash.hex()


class TestPhaseWitnessEventConstants:
    """Tests for module constants."""

    def test_event_type_constant(self) -> None:
        """Test event type constant is defined."""
        assert PHASE_WITNESS_EVENT_TYPE == "deliberation.phase.witnessed"

    def test_blake3_hash_size_constant(self) -> None:
        """Test Blake3 hash size constant."""
        assert BLAKE3_HASH_SIZE == 32


class TestPhaseWitnessEventEquality:
    """Tests for PhaseWitnessEvent equality."""

    def test_equal_events(self) -> None:
        """Test equal events compare as equal."""
        event_id = uuid4()
        session_id = uuid4()
        archons = _create_archons()
        transcript_hash = _create_valid_hash()
        start = datetime(2026, 1, 19, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 19, 10, 5, 0, tzinfo=timezone.utc)
        created = datetime(2026, 1, 19, 10, 6, 0, tzinfo=timezone.utc)

        event1 = PhaseWitnessEvent(
            event_id=event_id,
            session_id=session_id,
            phase=DeliberationPhase.ASSESS,
            transcript_hash=transcript_hash,
            participating_archons=archons,
            start_timestamp=start,
            end_timestamp=end,
            phase_metadata={"key": "value"},
            previous_witness_hash=None,
            created_at=created,
        )

        event2 = PhaseWitnessEvent(
            event_id=event_id,
            session_id=session_id,
            phase=DeliberationPhase.ASSESS,
            transcript_hash=transcript_hash,
            participating_archons=archons,
            start_timestamp=start,
            end_timestamp=end,
            phase_metadata={"key": "value"},
            previous_witness_hash=None,
            created_at=created,
        )

        assert event1 == event2

    def test_different_events_not_equal(self) -> None:
        """Test different events compare as not equal."""
        start = datetime.now(timezone.utc)
        end = start + timedelta(minutes=1)

        event1 = PhaseWitnessEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            phase=DeliberationPhase.ASSESS,
            transcript_hash=_create_valid_hash(),
            participating_archons=_create_archons(),
            start_timestamp=start,
            end_timestamp=end,
            previous_witness_hash=None,
        )

        event2 = PhaseWitnessEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            phase=DeliberationPhase.ASSESS,
            transcript_hash=_create_valid_hash(),
            participating_archons=_create_archons(),
            start_timestamp=start,
            end_timestamp=end,
            previous_witness_hash=None,
        )

        assert event1 != event2

    def test_frozen_immutability(self) -> None:
        """Test event is frozen (immutable)."""
        start = datetime.now(timezone.utc)

        event = PhaseWitnessEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            phase=DeliberationPhase.ASSESS,
            transcript_hash=_create_valid_hash(),
            participating_archons=_create_archons(),
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=1),
            previous_witness_hash=None,
        )

        with pytest.raises(AttributeError):
            event.phase = DeliberationPhase.POSITION  # type: ignore
