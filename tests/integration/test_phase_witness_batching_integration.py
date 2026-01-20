"""Integration tests for Phase Witness Batching (Story 2A.7, FR-11.7).

Tests end-to-end phase witness batching including:
- Full deliberation witness flow
- Content-addressed artifact retrieval
- Audit trail reconstruction
- Integration with DeliberationSession
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.services.phase_witness_batching_service import (
    PHASE_ORDER,
    PhaseWitnessBatchingService,
)
from src.domain.events.phase_witness import BLAKE3_HASH_SIZE, PhaseWitnessEvent
from src.domain.models.deliberation_session import (
    DeliberationPhase,
    DeliberationSession,
)


class TestFullDeliberationWitnessing:
    """Integration tests for complete deliberation witness flow."""

    @pytest.mark.asyncio
    async def test_full_deliberation_produces_four_witness_events(self) -> None:
        """Test that a full deliberation produces exactly 4 witness events."""
        service = PhaseWitnessBatchingService()
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        current_time = datetime.now(timezone.utc)
        transcripts = {
            DeliberationPhase.ASSESS: "Archon-1: I assess the petition...\nArchon-2: My assessment...\nArchon-3: Analysis complete.",
            DeliberationPhase.POSITION: "Archon-1: My position is APPROVE.\nArchon-2: I position APPROVE.\nArchon-3: APPROVE position.",
            DeliberationPhase.CROSS_EXAMINE: "Archon-1: Question for Archon-2...\nArchon-2: Response...\nArchon-3: Follow-up.",
            DeliberationPhase.VOTE: "Archon-1: APPROVE\nArchon-2: APPROVE\nArchon-3: REJECT",
        }

        events = []
        for phase in PHASE_ORDER:
            start = current_time
            end = current_time + timedelta(minutes=5)

            event = await service.witness_phase(
                session=session,
                phase=phase,
                transcript=transcripts[phase],
                metadata={"phase_name": phase.value},
                start_timestamp=start,
                end_timestamp=end,
            )
            events.append(event)
            current_time = end + timedelta(seconds=30)

        # Verify 4 events
        assert len(events) == 4

        # Verify all phases covered
        phases = [e.phase for e in events]
        assert phases == list(PHASE_ORDER)

        # Verify session consistency
        for event in events:
            assert event.session_id == session.session_id
            assert event.participating_archons == session.assigned_archons

    @pytest.mark.asyncio
    async def test_witness_chain_integrity_after_full_deliberation(self) -> None:
        """Test that witness chain is valid after full deliberation."""
        service = PhaseWitnessBatchingService()
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        current_time = datetime.now(timezone.utc)

        for phase in PHASE_ORDER:
            await service.witness_phase(
                session=session,
                phase=phase,
                transcript=f"Transcript for {phase.value}",
                metadata={},
                start_timestamp=current_time,
                end_timestamp=current_time + timedelta(minutes=3),
            )
            current_time += timedelta(minutes=5)

        # Verify chain integrity
        is_valid = await service.verify_witness_chain(session.session_id)
        assert is_valid is True

        # Verify transcript integrity
        transcript_valid = await service.verify_transcript_integrity(session.session_id)
        assert transcript_valid is True

        # Verify complete witnessing
        assert service.has_complete_witnessing(session.session_id) is True


class TestContentAddressedArtifactRetrieval:
    """Integration tests for content-addressed storage."""

    @pytest.mark.asyncio
    async def test_transcript_retrievable_by_hash(self) -> None:
        """Test transcripts can be retrieved by their Blake3 hash."""
        service = PhaseWitnessBatchingService()
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        original_transcript = (
            "Archon-1: The petition requests budget allocation.\n"
            "Archon-2: I observe compliance with Motion Gate P2.\n"
            "Archon-3: Assessment complete - within bounds."
        )
        start = datetime.now(timezone.utc)

        event = await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript=original_transcript,
            metadata={"assessments": 3},
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=5),
        )

        # Retrieve by hash
        retrieved = await service.get_transcript_by_hash(event.transcript_hash)

        assert retrieved == original_transcript
        assert len(event.transcript_hash) == BLAKE3_HASH_SIZE

    @pytest.mark.asyncio
    async def test_multiple_transcripts_independently_retrievable(self) -> None:
        """Test multiple phase transcripts are independently retrievable."""
        service = PhaseWitnessBatchingService()
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        transcripts = {
            DeliberationPhase.ASSESS: "ASSESS phase content - unique string 1",
            DeliberationPhase.POSITION: "POSITION phase content - unique string 2",
        }

        current_time = datetime.now(timezone.utc)
        events = {}

        for phase, transcript in transcripts.items():
            event = await service.witness_phase(
                session=session,
                phase=phase,
                transcript=transcript,
                metadata={},
                start_timestamp=current_time,
                end_timestamp=current_time + timedelta(minutes=3),
            )
            events[phase] = event
            current_time += timedelta(minutes=5)

        # Retrieve each transcript independently
        for phase, original in transcripts.items():
            retrieved = await service.get_transcript_by_hash(events[phase].transcript_hash)
            assert retrieved == original

        # Verify hashes are different
        assert events[DeliberationPhase.ASSESS].transcript_hash != events[DeliberationPhase.POSITION].transcript_hash


class TestAuditTrailReconstruction:
    """Integration tests for audit trail reconstruction."""

    @pytest.mark.asyncio
    async def test_audit_trail_reconstruction_from_events(self) -> None:
        """Test complete audit trail can be reconstructed from witness events."""
        service = PhaseWitnessBatchingService()
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        transcripts = {
            DeliberationPhase.ASSESS: "ASSESS content",
            DeliberationPhase.POSITION: "POSITION content",
            DeliberationPhase.CROSS_EXAMINE: "CROSS_EXAMINE content",
            DeliberationPhase.VOTE: "VOTE content",
        }

        current_time = datetime.now(timezone.utc)
        for phase in PHASE_ORDER:
            await service.witness_phase(
                session=session,
                phase=phase,
                transcript=transcripts[phase],
                metadata={"phase_order": PHASE_ORDER.index(phase)},
                start_timestamp=current_time,
                end_timestamp=current_time + timedelta(minutes=3),
            )
            current_time += timedelta(minutes=5)

        # Reconstruct audit trail
        events = await service.get_all_witnesses(session.session_id)

        assert len(events) == 4

        # Verify chronological order
        for i, event in enumerate(events):
            assert event.phase == PHASE_ORDER[i]
            if i == 0:
                assert event.previous_witness_hash is None
            else:
                assert event.previous_witness_hash == events[i - 1].event_hash

        # Verify all transcripts retrievable
        for event in events:
            transcript = await service.get_transcript_by_hash(event.transcript_hash)
            assert transcript == transcripts[event.phase]

    @pytest.mark.asyncio
    async def test_partial_audit_trail_reconstruction(self) -> None:
        """Test partial audit trail for incomplete deliberation."""
        service = PhaseWitnessBatchingService()
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        start = datetime.now(timezone.utc)

        # Only witness ASSESS and POSITION
        await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript="ASSESS transcript",
            metadata={},
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=3),
        )

        await service.witness_phase(
            session=session,
            phase=DeliberationPhase.POSITION,
            transcript="POSITION transcript",
            metadata={},
            start_timestamp=start + timedelta(minutes=5),
            end_timestamp=start + timedelta(minutes=8),
        )

        # Reconstruct partial trail
        events = await service.get_all_witnesses(session.session_id)

        assert len(events) == 2
        assert events[0].phase == DeliberationPhase.ASSESS
        assert events[1].phase == DeliberationPhase.POSITION

        # Verify chain is valid even though incomplete
        is_valid = await service.verify_witness_chain(session.session_id)
        assert is_valid is True

        # But not complete
        assert service.has_complete_witnessing(session.session_id) is False


class TestDeliberationSessionIntegration:
    """Integration tests with DeliberationSession model."""

    @pytest.mark.asyncio
    async def test_witness_uses_session_archons(self) -> None:
        """Test witness event uses session's assigned archons."""
        service = PhaseWitnessBatchingService()
        archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()

        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(archon1, archon2, archon3),
        )

        start = datetime.now(timezone.utc)
        event = await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript="Test",
            metadata={},
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=1),
        )

        assert event.participating_archons == (archon1, archon2, archon3)
        assert event.session_id == session.session_id

    @pytest.mark.asyncio
    async def test_multiple_sessions_independent_witnessing(self) -> None:
        """Test multiple sessions have independent witness chains."""
        service = PhaseWitnessBatchingService()

        session1 = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        session2 = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        start = datetime.now(timezone.utc)

        # Witness both sessions
        await service.witness_phase(
            session=session1,
            phase=DeliberationPhase.ASSESS,
            transcript="Session 1 ASSESS",
            metadata={},
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=3),
        )

        await service.witness_phase(
            session=session2,
            phase=DeliberationPhase.ASSESS,
            transcript="Session 2 ASSESS",
            metadata={},
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=3),
        )

        # Verify independence
        events1 = await service.get_all_witnesses(session1.session_id)
        events2 = await service.get_all_witnesses(session2.session_id)

        assert len(events1) == 1
        assert len(events2) == 1
        assert events1[0].session_id != events2[0].session_id
        assert events1[0].transcript_hash != events2[0].transcript_hash


class TestPhaseMetadataPreservation:
    """Integration tests for metadata preservation."""

    @pytest.mark.asyncio
    async def test_metadata_preserved_across_phases(self) -> None:
        """Test phase-specific metadata is preserved in witness events."""
        service = PhaseWitnessBatchingService()
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        metadata_by_phase = {
            DeliberationPhase.ASSESS: {"assessments_complete": True, "motion_gate": "P2"},
            DeliberationPhase.POSITION: {"positions": ["APPROVE", "APPROVE", "APPROVE"]},
            DeliberationPhase.CROSS_EXAMINE: {"questions_asked": 5, "rebuttals": 2},
            DeliberationPhase.VOTE: {"final_votes": {"approve": 3, "reject": 0}},
        }

        current_time = datetime.now(timezone.utc)
        for phase in PHASE_ORDER:
            await service.witness_phase(
                session=session,
                phase=phase,
                transcript=f"{phase.value} transcript",
                metadata=metadata_by_phase[phase],
                start_timestamp=current_time,
                end_timestamp=current_time + timedelta(minutes=3),
            )
            current_time += timedelta(minutes=5)

        # Retrieve and verify metadata
        events = await service.get_all_witnesses(session.session_id)

        for event in events:
            assert event.phase_metadata == metadata_by_phase[event.phase]


class TestEdgeCases:
    """Integration tests for edge cases."""

    @pytest.mark.asyncio
    async def test_empty_transcript_still_witnesses(self) -> None:
        """Test empty transcript still creates valid witness event."""
        service = PhaseWitnessBatchingService()
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        start = datetime.now(timezone.utc)
        event = await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript="",
            metadata={},
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=1),
        )

        assert event is not None
        assert len(event.transcript_hash) == BLAKE3_HASH_SIZE

        # Empty string still has a hash
        retrieved = await service.get_transcript_by_hash(event.transcript_hash)
        assert retrieved == ""

    @pytest.mark.asyncio
    async def test_large_transcript_handling(self) -> None:
        """Test handling of large transcripts."""
        service = PhaseWitnessBatchingService()
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        # Create a large transcript (100KB+)
        large_transcript = "Archon dialogue line. " * 5000

        start = datetime.now(timezone.utc)
        event = await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript=large_transcript,
            metadata={},
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=30),
        )

        assert event is not None
        assert len(event.transcript_hash) == BLAKE3_HASH_SIZE

        # Verify retrieval
        retrieved = await service.get_transcript_by_hash(event.transcript_hash)
        assert retrieved == large_transcript

    @pytest.mark.asyncio
    async def test_unicode_transcript_handling(self) -> None:
        """Test handling of unicode in transcripts."""
        service = PhaseWitnessBatchingService()
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        unicode_transcript = (
            "Archon-1: 测试内容 🎯\n"
            "Archon-2: Тест контент 🔥\n"
            "Archon-3: テスト内容 ✅"
        )

        start = datetime.now(timezone.utc)
        event = await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript=unicode_transcript,
            metadata={},
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=5),
        )

        # Verify hash is valid
        assert len(event.transcript_hash) == BLAKE3_HASH_SIZE

        # Verify retrieval preserves unicode
        retrieved = await service.get_transcript_by_hash(event.transcript_hash)
        assert retrieved == unicode_transcript
