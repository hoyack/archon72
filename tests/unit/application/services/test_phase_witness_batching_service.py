"""Unit tests for PhaseWitnessBatchingService (Story 2A.7, FR-11.7).

Tests the phase witness batching service for:
- Phase witnessing
- Hash chain integrity
- Content-addressed storage
- Validation
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import blake3
import pytest

from src.application.services.phase_witness_batching_service import (
    PHASE_ORDER,
    PhaseWitnessBatchingService,
)
from src.domain.events.phase_witness import BLAKE3_HASH_SIZE
from src.domain.models.deliberation_session import (
    DeliberationPhase,
    DeliberationSession,
)


def _create_session() -> DeliberationSession:
    """Create a valid deliberation session for testing."""
    return DeliberationSession.create(
        session_id=uuid4(),
        petition_id=uuid4(),
        assigned_archons=(uuid4(), uuid4(), uuid4()),
    )


def _create_timestamps() -> tuple[datetime, datetime]:
    """Create valid start/end timestamps."""
    start = datetime.now(timezone.utc)
    end = start + timedelta(minutes=5)
    return start, end


class TestPhaseWitnessBatchingServiceWitnessPhase:
    """Tests for witness_phase method."""

    @pytest.mark.asyncio
    async def test_witness_assess_phase(self) -> None:
        """Test witnessing ASSESS phase (first phase)."""
        service = PhaseWitnessBatchingService()
        session = _create_session()
        start, end = _create_timestamps()
        transcript = "Archon 1: Assessment...\nArchon 2: I observe..."

        event = await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
            metadata={"assessments_recorded": 3},
            start_timestamp=start,
            end_timestamp=end,
        )

        assert event.session_id == session.session_id
        assert event.phase == DeliberationPhase.ASSESS
        assert event.participating_archons == session.assigned_archons
        assert event.start_timestamp == start
        assert event.end_timestamp == end
        assert event.phase_metadata == {"assessments_recorded": 3}
        assert event.previous_witness_hash is None  # ASSESS has no previous
        assert len(event.transcript_hash) == BLAKE3_HASH_SIZE

    @pytest.mark.asyncio
    async def test_witness_position_phase_after_assess(self) -> None:
        """Test witnessing POSITION phase after ASSESS."""
        service = PhaseWitnessBatchingService()
        session = _create_session()
        start, end = _create_timestamps()

        # First witness ASSESS
        assess_event = await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript="ASSESS transcript",
            metadata={},
            start_timestamp=start,
            end_timestamp=end,
        )

        # Then witness POSITION
        position_start = end
        position_end = position_start + timedelta(minutes=3)

        position_event = await service.witness_phase(
            session=session,
            phase=DeliberationPhase.POSITION,
            transcript="POSITION transcript",
            metadata={"positions_converged": True},
            start_timestamp=position_start,
            end_timestamp=position_end,
        )

        assert position_event.phase == DeliberationPhase.POSITION
        assert position_event.previous_witness_hash == assess_event.event_hash

    @pytest.mark.asyncio
    async def test_witness_all_four_phases(self) -> None:
        """Test witnessing all 4 phases in order."""
        service = PhaseWitnessBatchingService()
        session = _create_session()
        current_time = datetime.now(timezone.utc)

        events = []
        for phase in PHASE_ORDER:
            start = current_time
            end = current_time + timedelta(minutes=3)

            event = await service.witness_phase(
                session=session,
                phase=phase,
                transcript=f"{phase.value} transcript content",
                metadata={"phase": phase.value},
                start_timestamp=start,
                end_timestamp=end,
            )
            events.append(event)
            current_time = end

        assert len(events) == 4

        # Verify chain
        assert events[0].previous_witness_hash is None  # ASSESS
        assert events[1].previous_witness_hash == events[0].event_hash
        assert events[2].previous_witness_hash == events[1].event_hash
        assert events[3].previous_witness_hash == events[2].event_hash

    @pytest.mark.asyncio
    async def test_witness_out_of_order_raises_error(self) -> None:
        """Test witnessing out of order raises ValueError."""
        service = PhaseWitnessBatchingService()
        session = _create_session()
        start, end = _create_timestamps()

        # Try to witness POSITION without ASSESS
        with pytest.raises(
            ValueError, match="Cannot witness POSITION without prior ASSESS"
        ):
            await service.witness_phase(
                session=session,
                phase=DeliberationPhase.POSITION,
                transcript="POSITION transcript",
                metadata={},
                start_timestamp=start,
                end_timestamp=end,
            )

    @pytest.mark.asyncio
    async def test_witness_cross_examine_without_position_raises(self) -> None:
        """Test witnessing CROSS_EXAMINE without POSITION raises error."""
        service = PhaseWitnessBatchingService()
        session = _create_session()
        start, end = _create_timestamps()

        # Witness ASSESS
        await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript="ASSESS transcript",
            metadata={},
            start_timestamp=start,
            end_timestamp=end,
        )

        # Try to witness CROSS_EXAMINE without POSITION
        with pytest.raises(
            ValueError, match="Cannot witness CROSS_EXAMINE without prior POSITION"
        ):
            await service.witness_phase(
                session=session,
                phase=DeliberationPhase.CROSS_EXAMINE,
                transcript="CROSS_EXAMINE transcript",
                metadata={},
                start_timestamp=start,
                end_timestamp=end,
            )

    @pytest.mark.asyncio
    async def test_transcript_hash_is_blake3(self) -> None:
        """Test transcript hash is computed using Blake3."""
        service = PhaseWitnessBatchingService()
        session = _create_session()
        start, end = _create_timestamps()
        transcript = "Test transcript content for hashing"

        event = await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
            metadata={},
            start_timestamp=start,
            end_timestamp=end,
        )

        # Manually compute expected hash
        expected_hash = blake3.blake3(transcript.encode("utf-8")).digest()

        assert event.transcript_hash == expected_hash


class TestPhaseWitnessBatchingServiceRetrieval:
    """Tests for retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_phase_witness(self) -> None:
        """Test retrieving a specific phase witness."""
        service = PhaseWitnessBatchingService()
        session = _create_session()
        start, end = _create_timestamps()

        await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript="ASSESS transcript",
            metadata={"key": "value"},
            start_timestamp=start,
            end_timestamp=end,
        )

        event = await service.get_phase_witness(
            session.session_id, DeliberationPhase.ASSESS
        )

        assert event is not None
        assert event.phase == DeliberationPhase.ASSESS
        assert event.session_id == session.session_id

    @pytest.mark.asyncio
    async def test_get_phase_witness_not_found(self) -> None:
        """Test retrieving non-existent phase witness returns None."""
        service = PhaseWitnessBatchingService()

        event = await service.get_phase_witness(uuid4(), DeliberationPhase.ASSESS)

        assert event is None

    @pytest.mark.asyncio
    async def test_get_all_witnesses_empty(self) -> None:
        """Test get_all_witnesses returns empty list for new session."""
        service = PhaseWitnessBatchingService()

        events = await service.get_all_witnesses(uuid4())

        assert events == []

    @pytest.mark.asyncio
    async def test_get_all_witnesses_in_order(self) -> None:
        """Test get_all_witnesses returns events in phase order."""
        service = PhaseWitnessBatchingService()
        session = _create_session()
        current_time = datetime.now(timezone.utc)

        # Witness all phases
        for phase in PHASE_ORDER:
            await service.witness_phase(
                session=session,
                phase=phase,
                transcript=f"{phase.value} transcript",
                metadata={},
                start_timestamp=current_time,
                end_timestamp=current_time + timedelta(minutes=1),
            )
            current_time += timedelta(minutes=2)

        events = await service.get_all_witnesses(session.session_id)

        assert len(events) == 4
        assert events[0].phase == DeliberationPhase.ASSESS
        assert events[1].phase == DeliberationPhase.POSITION
        assert events[2].phase == DeliberationPhase.CROSS_EXAMINE
        assert events[3].phase == DeliberationPhase.VOTE

    @pytest.mark.asyncio
    async def test_get_transcript_by_hash(self) -> None:
        """Test retrieving transcript by hash."""
        service = PhaseWitnessBatchingService()
        session = _create_session()
        start, end = _create_timestamps()
        transcript = "Original transcript content for retrieval test"

        event = await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
            metadata={},
            start_timestamp=start,
            end_timestamp=end,
        )

        retrieved = await service.get_transcript_by_hash(event.transcript_hash)

        assert retrieved == transcript

    @pytest.mark.asyncio
    async def test_get_transcript_by_hash_not_found(self) -> None:
        """Test retrieving non-existent transcript returns None."""
        service = PhaseWitnessBatchingService()
        fake_hash = blake3.blake3(b"nonexistent").digest()

        retrieved = await service.get_transcript_by_hash(fake_hash)

        assert retrieved is None


class TestPhaseWitnessBatchingServiceVerification:
    """Tests for verification methods."""

    @pytest.mark.asyncio
    async def test_verify_witness_chain_empty(self) -> None:
        """Test verifying empty chain returns True."""
        service = PhaseWitnessBatchingService()

        is_valid = await service.verify_witness_chain(uuid4())

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_witness_chain_valid(self) -> None:
        """Test verifying valid chain returns True."""
        service = PhaseWitnessBatchingService()
        session = _create_session()
        current_time = datetime.now(timezone.utc)

        # Witness all phases in order
        for phase in PHASE_ORDER:
            await service.witness_phase(
                session=session,
                phase=phase,
                transcript=f"{phase.value} transcript",
                metadata={},
                start_timestamp=current_time,
                end_timestamp=current_time + timedelta(minutes=1),
            )
            current_time += timedelta(minutes=2)

        is_valid = await service.verify_witness_chain(session.session_id)

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_transcript_integrity_valid(self) -> None:
        """Test verifying valid transcript integrity returns True."""
        service = PhaseWitnessBatchingService()
        session = _create_session()
        start, end = _create_timestamps()

        await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript="Test transcript",
            metadata={},
            start_timestamp=start,
            end_timestamp=end,
        )

        is_valid = await service.verify_transcript_integrity(session.session_id)

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_transcript_integrity_empty(self) -> None:
        """Test verifying empty session returns True."""
        service = PhaseWitnessBatchingService()

        is_valid = await service.verify_transcript_integrity(uuid4())

        assert is_valid is True


class TestPhaseWitnessBatchingServiceHelpers:
    """Tests for helper methods."""

    @pytest.mark.asyncio
    async def test_get_witness_count_zero(self) -> None:
        """Test witness count is 0 for new session."""
        service = PhaseWitnessBatchingService()

        count = service.get_witness_count(uuid4())

        assert count == 0

    @pytest.mark.asyncio
    async def test_get_witness_count_increments(self) -> None:
        """Test witness count increments with each witness."""
        service = PhaseWitnessBatchingService()
        session = _create_session()
        start, end = _create_timestamps()

        # Initially 0
        assert service.get_witness_count(session.session_id) == 0

        # After ASSESS
        await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript="ASSESS",
            metadata={},
            start_timestamp=start,
            end_timestamp=end,
        )
        assert service.get_witness_count(session.session_id) == 1

        # After POSITION
        await service.witness_phase(
            session=session,
            phase=DeliberationPhase.POSITION,
            transcript="POSITION",
            metadata={},
            start_timestamp=start,
            end_timestamp=end,
        )
        assert service.get_witness_count(session.session_id) == 2

    @pytest.mark.asyncio
    async def test_has_complete_witnessing_false(self) -> None:
        """Test has_complete_witnessing is False with incomplete witnessing."""
        service = PhaseWitnessBatchingService()
        session = _create_session()
        start, end = _create_timestamps()

        # Only ASSESS
        await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript="ASSESS",
            metadata={},
            start_timestamp=start,
            end_timestamp=end,
        )

        assert service.has_complete_witnessing(session.session_id) is False

    @pytest.mark.asyncio
    async def test_has_complete_witnessing_true(self) -> None:
        """Test has_complete_witnessing is True with all 4 phases."""
        service = PhaseWitnessBatchingService()
        session = _create_session()
        current_time = datetime.now(timezone.utc)

        for phase in PHASE_ORDER:
            await service.witness_phase(
                session=session,
                phase=phase,
                transcript=f"{phase.value}",
                metadata={},
                start_timestamp=current_time,
                end_timestamp=current_time + timedelta(minutes=1),
            )
            current_time += timedelta(minutes=2)

        assert service.has_complete_witnessing(session.session_id) is True


class TestPhaseWitnessBatchingServiceIsolation:
    """Tests for session isolation."""

    @pytest.mark.asyncio
    async def test_sessions_are_isolated(self) -> None:
        """Test different sessions are isolated."""
        service = PhaseWitnessBatchingService()
        session1 = _create_session()
        session2 = _create_session()
        start, end = _create_timestamps()

        # Witness ASSESS for session1
        event1 = await service.witness_phase(
            session=session1,
            phase=DeliberationPhase.ASSESS,
            transcript="Session 1 ASSESS",
            metadata={"session": 1},
            start_timestamp=start,
            end_timestamp=end,
        )

        # Witness ASSESS for session2
        event2 = await service.witness_phase(
            session=session2,
            phase=DeliberationPhase.ASSESS,
            transcript="Session 2 ASSESS",
            metadata={"session": 2},
            start_timestamp=start,
            end_timestamp=end,
        )

        # Events should be different
        assert event1.session_id != event2.session_id
        assert event1.transcript_hash != event2.transcript_hash

        # Counts should be separate
        assert service.get_witness_count(session1.session_id) == 1
        assert service.get_witness_count(session2.session_id) == 1

        # Retrieval should be separate
        retrieved1 = await service.get_phase_witness(
            session1.session_id, DeliberationPhase.ASSESS
        )
        retrieved2 = await service.get_phase_witness(
            session2.session_id, DeliberationPhase.ASSESS
        )

        assert retrieved1.phase_metadata == {"session": 1}
        assert retrieved2.phase_metadata == {"session": 2}


class TestPhaseOrderConstant:
    """Tests for PHASE_ORDER constant."""

    def test_phase_order_contains_all_phases(self) -> None:
        """Test PHASE_ORDER contains all deliberation phases."""
        assert len(PHASE_ORDER) == 4
        assert DeliberationPhase.ASSESS in PHASE_ORDER
        assert DeliberationPhase.POSITION in PHASE_ORDER
        assert DeliberationPhase.CROSS_EXAMINE in PHASE_ORDER
        assert DeliberationPhase.VOTE in PHASE_ORDER

    def test_phase_order_is_correct(self) -> None:
        """Test PHASE_ORDER is in correct sequence."""
        assert PHASE_ORDER[0] == DeliberationPhase.ASSESS
        assert PHASE_ORDER[1] == DeliberationPhase.POSITION
        assert PHASE_ORDER[2] == DeliberationPhase.CROSS_EXAMINE
        assert PHASE_ORDER[3] == DeliberationPhase.VOTE
