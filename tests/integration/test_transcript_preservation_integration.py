"""Integration tests for Transcript Preservation (Story 2B.5, AC-10).

Tests end-to-end transcript preservation including:
- Content-addressed storage workflow
- Hash-referenced retrieval for audit trails
- Integration with PhaseWitnessBatchingService
- Idempotent storage semantics

Constitutional Constraints:
- CT-12: Witnessing creates accountability - hash enables verification
- FR-11.7: Hash-referenced preservation requirement
- NFR-6.5: Audit trail completeness - transcripts retrievable by hash
- NFR-4.2: Hash guarantees immutability (append-only semantic)
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
from src.domain.models.deliberation_session import (
    DeliberationPhase,
    DeliberationSession,
)
from src.infrastructure.stubs.transcript_store_stub import (
    TranscriptStoreOperation,
    TranscriptStoreStub,
)


class TestTranscriptPreservationWorkflow:
    """Integration tests for transcript preservation workflow."""

    @pytest.mark.asyncio
    async def test_phase_witness_stores_transcript_via_protocol(self) -> None:
        """Test PhaseWitnessBatchingService stores transcripts via TranscriptStoreProtocol.

        FR-11.7: Hash-referenced preservation at phase boundaries.
        """
        transcript_store = TranscriptStoreStub()
        service = PhaseWitnessBatchingService(transcript_store=transcript_store)

        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        transcript = "Archon-1: Assessment begins...\nArchon-2: I concur..."
        start = datetime.now(timezone.utc)

        await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
            metadata={"assessments": 2},
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=5),
        )

        # Verify transcript was stored via protocol
        assert transcript_store.get_transcript_count() == 1

        # Verify STORE operation was recorded
        ops = transcript_store.get_operations()
        store_ops = [op for op in ops if op[0] == TranscriptStoreOperation.STORE]
        assert len(store_ops) == 1

    @pytest.mark.asyncio
    async def test_full_deliberation_stores_all_transcripts(self) -> None:
        """Test full deliberation stores all 4 phase transcripts.

        NFR-10.4: 100% witness completeness.
        """
        transcript_store = TranscriptStoreStub()
        service = PhaseWitnessBatchingService(transcript_store=transcript_store)

        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        transcripts = {
            DeliberationPhase.ASSESS: "ASSESS phase transcript content",
            DeliberationPhase.POSITION: "POSITION phase transcript content",
            DeliberationPhase.CROSS_EXAMINE: "CROSS_EXAMINE phase transcript content",
            DeliberationPhase.VOTE: "VOTE phase transcript content",
        }

        current_time = datetime.now(timezone.utc)

        for phase in PHASE_ORDER:
            await service.witness_phase(
                session=session,
                phase=phase,
                transcript=transcripts[phase],
                metadata={},
                start_timestamp=current_time,
                end_timestamp=current_time + timedelta(minutes=3),
            )
            current_time += timedelta(minutes=5)

        # All 4 transcripts should be stored
        assert transcript_store.get_transcript_count() == 4


class TestAuditTrailReconstruction:
    """Integration tests for audit trail reconstruction via hash-referenced retrieval."""

    @pytest.mark.asyncio
    async def test_transcript_retrievable_by_witness_event_hash(self) -> None:
        """Test transcripts retrievable using hash from witness event.

        NFR-6.5: Audit trail completeness.
        """
        transcript_store = TranscriptStoreStub()
        service = PhaseWitnessBatchingService(transcript_store=transcript_store)

        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        original_transcript = (
            "Archon-1: The petition addresses budget allocation.\n"
            "Archon-2: I observe compliance with Motion Gate P2.\n"
            "Archon-3: Assessment complete."
        )
        start = datetime.now(timezone.utc)

        event = await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript=original_transcript,
            metadata={},
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=5),
        )

        # Use event's transcript_hash to retrieve via service
        retrieved = await service.get_transcript_by_hash(event.transcript_hash)

        assert retrieved == original_transcript

    @pytest.mark.asyncio
    async def test_full_audit_trail_reconstruction(self) -> None:
        """Test complete audit trail can be reconstructed from witness events.

        CT-12: Witnessing creates accountability.
        """
        transcript_store = TranscriptStoreStub()
        service = PhaseWitnessBatchingService(transcript_store=transcript_store)

        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        transcripts = {
            DeliberationPhase.ASSESS: "ASSESS: All archons analyze the petition.",
            DeliberationPhase.POSITION: "POSITION: Archons state their positions.",
            DeliberationPhase.CROSS_EXAMINE: "CROSS: Questions and rebuttals.",
            DeliberationPhase.VOTE: "VOTE: Final votes recorded.",
        }

        current_time = datetime.now(timezone.utc)
        for phase in PHASE_ORDER:
            await service.witness_phase(
                session=session,
                phase=phase,
                transcript=transcripts[phase],
                metadata={},
                start_timestamp=current_time,
                end_timestamp=current_time + timedelta(minutes=3),
            )
            current_time += timedelta(minutes=5)

        # Reconstruct full audit trail
        events = await service.get_all_witnesses(session.session_id)

        assert len(events) == 4

        # Verify each transcript is retrievable and matches original
        for event in events:
            retrieved = await service.get_transcript_by_hash(event.transcript_hash)
            assert retrieved == transcripts[event.phase]


class TestIdempotentStorage:
    """Integration tests for idempotent storage semantics."""

    @pytest.mark.asyncio
    async def test_duplicate_transcript_not_stored_twice(self) -> None:
        """Test duplicate content is deduplicated via content-addressing.

        NFR-4.2: Hash guarantees immutability (append-only, no duplication).
        """
        transcript_store = TranscriptStoreStub()
        service = PhaseWitnessBatchingService(transcript_store=transcript_store)

        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        # Use same transcript for two different phases
        # (unlikely in practice but tests deduplication)
        same_content = "Identical transcript content for testing"
        current_time = datetime.now(timezone.utc)

        event1 = await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript=same_content,
            metadata={},
            start_timestamp=current_time,
            end_timestamp=current_time + timedelta(minutes=3),
        )

        event2 = await service.witness_phase(
            session=session,
            phase=DeliberationPhase.POSITION,
            transcript=same_content,
            metadata={},
            start_timestamp=current_time + timedelta(minutes=5),
            end_timestamp=current_time + timedelta(minutes=8),
        )

        # Both events should have same transcript hash
        assert event1.transcript_hash == event2.transcript_hash

        # Only one copy should be stored
        assert transcript_store.get_transcript_count() == 1


class TestHashVerification:
    """Integration tests for hash-based integrity verification."""

    @pytest.mark.asyncio
    async def test_verify_transcript_integrity(self) -> None:
        """Test transcript integrity verification works correctly.

        CT-12: Hash enables verification.
        """
        transcript_store = TranscriptStoreStub()
        service = PhaseWitnessBatchingService(transcript_store=transcript_store)

        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        transcript = "Transcript content for integrity verification"
        start = datetime.now(timezone.utc)

        event = await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
            metadata={},
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=5),
        )

        # Verify using transcript store's verify method
        is_valid = await transcript_store.verify(event.transcript_hash, transcript)
        assert is_valid is True

        # Verify with wrong content returns False
        is_invalid = await transcript_store.verify(
            event.transcript_hash, "Wrong content"
        )
        assert is_invalid is False

    @pytest.mark.asyncio
    async def test_service_verify_transcript_integrity(self) -> None:
        """Test service-level transcript integrity verification."""
        transcript_store = TranscriptStoreStub()
        service = PhaseWitnessBatchingService(transcript_store=transcript_store)

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

        # Service-level verification should pass
        is_valid = await service.verify_transcript_integrity(session.session_id)
        assert is_valid is True


class TestTranscriptStoreOperationsTracking:
    """Integration tests for operation tracking (test verification support)."""

    @pytest.mark.asyncio
    async def test_operations_tracked_through_witness_flow(self) -> None:
        """Test all transcript store operations are tracked through witness flow."""
        transcript_store = TranscriptStoreStub()
        service = PhaseWitnessBatchingService(transcript_store=transcript_store)

        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        start = datetime.now(timezone.utc)

        # Witness a phase (triggers STORE)
        event = await service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript="Test transcript",
            metadata={},
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=5),
        )

        # Retrieve (triggers RETRIEVE)
        await service.get_transcript_by_hash(event.transcript_hash)

        # Verify (triggers multiple operations during verify_transcript_integrity)
        await service.verify_transcript_integrity(session.session_id)

        ops = transcript_store.get_operations()

        # Should have STORE, RETRIEVE, and more from verify
        op_types = [op[0] for op in ops]
        assert TranscriptStoreOperation.STORE in op_types
        assert TranscriptStoreOperation.RETRIEVE in op_types


class TestMultiSessionIsolation:
    """Integration tests for session isolation in transcript storage."""

    @pytest.mark.asyncio
    async def test_multiple_sessions_with_shared_store(self) -> None:
        """Test multiple sessions can share same transcript store."""
        transcript_store = TranscriptStoreStub()
        service = PhaseWitnessBatchingService(transcript_store=transcript_store)

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

        # Witness for session 1
        event1 = await service.witness_phase(
            session=session1,
            phase=DeliberationPhase.ASSESS,
            transcript="Session 1 transcript",
            metadata={},
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=5),
        )

        # Witness for session 2
        event2 = await service.witness_phase(
            session=session2,
            phase=DeliberationPhase.ASSESS,
            transcript="Session 2 transcript",
            metadata={},
            start_timestamp=start,
            end_timestamp=start + timedelta(minutes=5),
        )

        # Both transcripts should be stored
        assert transcript_store.get_transcript_count() == 2

        # Each should be retrievable independently
        retrieved1 = await service.get_transcript_by_hash(event1.transcript_hash)
        retrieved2 = await service.get_transcript_by_hash(event2.transcript_hash)

        assert retrieved1 == "Session 1 transcript"
        assert retrieved2 == "Session 2 transcript"
