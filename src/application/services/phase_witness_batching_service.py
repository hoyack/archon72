"""Phase witness batching service implementation (Story 2A.7, FR-11.7).

This module implements phase-level witness batching for the deliberation
system. Per Ruling-1, witnessing occurs at phase boundaries to avoid
witness volume explosion while maintaining 100% auditability.

Updated for Story 2B.5: Now uses TranscriptStoreProtocol for content-addressed
transcript storage instead of in-memory storage.

Constitutional Constraints:
- CT-12: Every action must be witnessed
- CT-14: Every claim terminates in witnessed fate
- FR-11.7: Hash-referenced ledger witnessing at phase boundaries
- NFR-10.4: 100% witness completeness
- NFR-4.2: Hash guarantees immutability (append-only semantic)
- Ruling-1: Phase-level batching

Usage:
    from src.application.services.phase_witness_batching_service import (
        PhaseWitnessBatchingService,
    )
    from src.infrastructure.stubs.transcript_store_stub import TranscriptStoreStub

    transcript_store = TranscriptStoreStub()
    service = PhaseWitnessBatchingService(transcript_store=transcript_store)

    event = await service.witness_phase(
        session=session,
        phase=DeliberationPhase.ASSESS,
        transcript="Phase transcript...",
        metadata={"assessments_recorded": 3},
        start_timestamp=start,
        end_timestamp=end,
    )
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import blake3

from src.application.ports.transcript_store import TranscriptStoreProtocol
from src.domain.events.phase_witness import PhaseWitnessEvent
from src.domain.models.deliberation_session import (
    DeliberationPhase,
    DeliberationSession,
)

# Ordered list of deliberation phases
PHASE_ORDER: list[DeliberationPhase] = [
    DeliberationPhase.ASSESS,
    DeliberationPhase.POSITION,
    DeliberationPhase.CROSS_EXAMINE,
    DeliberationPhase.VOTE,
]


class PhaseWitnessBatchingService:
    """Service for phase-level witness batching (Story 2A.7, FR-11.7, Story 2B.5).

    Batches all utterances in a deliberation phase and emits a single
    witness event at the phase boundary. Maintains hash chain between
    phases for audit trail integrity.

    Updated for Story 2B.5: Uses TranscriptStoreProtocol for content-addressed
    transcript storage, enabling persistent storage and audit trail reconstruction.

    Constitutional Constraints:
    - CT-12: Every action witnessed
    - FR-11.7: Phase boundary witnessing
    - NFR-10.4: 100% witness completeness
    - NFR-4.2: Hash guarantees immutability (append-only semantic)
    - Ruling-1: Phase-level batching

    The service:
    1. Computes Blake3 hash of full phase transcript
    2. Stores transcript via TranscriptStoreProtocol (content-addressed)
    3. Links to previous phase's witness (hash chain)
    4. Emits PhaseWitnessEvent with all metadata

    Attributes:
        _transcript_store: Content-addressed transcript storage.
        _witness_events: In-memory storage for witness events (by session).
    """

    def __init__(self, transcript_store: TranscriptStoreProtocol) -> None:
        """Initialize the phase witness batching service.

        Args:
            transcript_store: Content-addressed transcript storage protocol.
                Use TranscriptStoreStub for testing, PostgresTranscriptStore
                for production.
        """
        self._transcript_store = transcript_store
        # In-memory witness events - could be moved to repository in future
        self._witness_events: dict[
            UUID, dict[DeliberationPhase, PhaseWitnessEvent]
        ] = {}

    def _compute_hash(self, content: str) -> bytes:
        """Compute Blake3 hash of content.

        Args:
            content: String content to hash.

        Returns:
            32-byte Blake3 hash.
        """
        return blake3.blake3(content.encode("utf-8")).digest()

    def _get_previous_witness_hash(
        self,
        session_id: UUID,
        phase: DeliberationPhase,
    ) -> bytes | None:
        """Get the witness hash from the previous phase.

        Enforces phase order and ensures proper chaining.

        Args:
            session_id: The session ID.
            phase: The current phase (to find previous).

        Returns:
            Hash of previous phase's witness event, or None for ASSESS.

        Raises:
            ValueError: If witnessing out of order (missing prior witness).
        """
        current_idx = PHASE_ORDER.index(phase)
        if current_idx == 0:
            return None  # ASSESS has no previous

        previous_phase = PHASE_ORDER[current_idx - 1]
        session_events = self._witness_events.get(session_id, {})
        previous_event = session_events.get(previous_phase)

        if previous_event is None:
            raise ValueError(
                f"Cannot witness {phase.value} without prior {previous_phase.value} witness"
            )

        return previous_event.event_hash

    async def witness_phase(
        self,
        session: DeliberationSession,
        phase: DeliberationPhase,
        transcript: str,
        metadata: dict[str, Any],
        start_timestamp: datetime,
        end_timestamp: datetime,
    ) -> PhaseWitnessEvent:
        """Witness a completed phase with its full transcript.

        Creates a witness event with:
        - Blake3 hash of the full transcript
        - Content-addressed storage via TranscriptStoreProtocol
        - Chain link to previous phase's witness

        Constitutional Constraints:
        - FR-11.7: Hash-referenced witnessing at phase boundaries
        - NFR-10.4: 100% witness completeness
        - NFR-4.2: Hash guarantees immutability

        Args:
            session: The deliberation session.
            phase: The phase that completed.
            transcript: Full text transcript of the phase.
            metadata: Phase-specific metadata.
            start_timestamp: When phase started.
            end_timestamp: When phase completed.

        Returns:
            PhaseWitnessEvent with hash-referenced transcript.

        Raises:
            ValueError: If witnessing out of order or invalid input.
        """
        # Validate phase is in order
        if phase not in PHASE_ORDER:
            raise ValueError(f"Invalid phase for witnessing: {phase}")

        # Store transcript via content-addressed store (Story 2B.5)
        # Returns TranscriptReference with content_hash
        transcript_ref = await self._transcript_store.store(transcript)
        transcript_hash = transcript_ref.content_hash

        # Get previous witness hash for chaining (validates order)
        previous_hash = self._get_previous_witness_hash(session.session_id, phase)

        # Create witness event
        event = PhaseWitnessEvent(
            event_id=uuid4(),  # Should be UUIDv7 in production
            session_id=session.session_id,
            phase=phase,
            transcript_hash=transcript_hash,
            participating_archons=session.assigned_archons,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            phase_metadata=dict(metadata),
            previous_witness_hash=previous_hash,
        )

        # Store event
        if session.session_id not in self._witness_events:
            self._witness_events[session.session_id] = {}
        self._witness_events[session.session_id][phase] = event

        return event

    async def get_phase_witness(
        self,
        session_id: UUID,
        phase: DeliberationPhase,
    ) -> PhaseWitnessEvent | None:
        """Retrieve witness event for a specific phase.

        Args:
            session_id: UUID of the deliberation session.
            phase: The phase to retrieve.

        Returns:
            PhaseWitnessEvent if found, None otherwise.
        """
        session_events = self._witness_events.get(session_id, {})
        return session_events.get(phase)

    async def get_all_witnesses(
        self,
        session_id: UUID,
    ) -> list[PhaseWitnessEvent]:
        """Retrieve all witness events for a session in phase order.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            List of PhaseWitnessEvents in chronological order.
        """
        session_events = self._witness_events.get(session_id, {})

        return [
            session_events[phase] for phase in PHASE_ORDER if phase in session_events
        ]

    async def get_transcript_by_hash(
        self,
        transcript_hash: bytes,
    ) -> str | None:
        """Retrieve raw transcript by content hash.

        Used for audit trail reconstruction to verify witness
        events against their original content.

        Constitutional Constraint (CT-12):
        Enables accountability verification through audit.

        Story 2B.5: Delegates to TranscriptStoreProtocol for retrieval.

        Args:
            transcript_hash: Blake3 hash of the transcript (32 bytes).

        Returns:
            Raw transcript text if found, None otherwise.
        """
        return await self._transcript_store.retrieve(transcript_hash)

    async def verify_witness_chain(
        self,
        session_id: UUID,
    ) -> bool:
        """Verify the hash chain integrity of all witness events.

        Ensures that each witness event correctly references the
        previous phase's witness hash, creating an unbroken chain
        of accountability.

        Constitutional Constraint (CT-12):
        Creates an unbroken chain of accountability.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            True if chain is valid, False if integrity is compromised.
        """
        witnesses = await self.get_all_witnesses(session_id)

        if not witnesses:
            return True  # Empty chain is valid

        # First witness (ASSESS) should have no previous hash
        if witnesses[0].previous_witness_hash is not None:
            return False

        # Verify each subsequent witness links to previous
        for i in range(1, len(witnesses)):
            previous_event = witnesses[i - 1]
            current_event = witnesses[i]

            # Current's previous_witness_hash should match previous's event_hash
            if current_event.previous_witness_hash != previous_event.event_hash:
                return False

        return True

    async def verify_transcript_integrity(
        self,
        session_id: UUID,
    ) -> bool:
        """Verify all stored transcripts match their hashes.

        Ensures content-addressed integrity - that stored transcripts
        when re-hashed produce the same hash as recorded.

        Story 2B.5: Uses TranscriptStoreProtocol.verify() for verification.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            True if all transcripts verify, False if any mismatch.
        """
        witnesses = await self.get_all_witnesses(session_id)

        for witness in witnesses:
            transcript = await self.get_transcript_by_hash(witness.transcript_hash)

            if transcript is None:
                return False  # Transcript missing

            # Use transcript store's verify method for integrity check
            is_valid = await self._transcript_store.verify(
                witness.transcript_hash, transcript
            )
            if not is_valid:
                return False  # Hash mismatch

        return True

    def get_witness_count(self, session_id: UUID) -> int:
        """Get the number of witness events for a session.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            Number of witness events (0-4).
        """
        return len(self._witness_events.get(session_id, {}))

    def has_complete_witnessing(self, session_id: UUID) -> bool:
        """Check if a session has all 4 phase witnesses.

        A complete deliberation should have exactly 4 witness events:
        ASSESS, POSITION, CROSS_EXAMINE, VOTE.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            True if all 4 phases are witnessed, False otherwise.
        """
        return self.get_witness_count(session_id) == len(PHASE_ORDER)
