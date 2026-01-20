"""Phase witness batching stub for testing (Story 2A.7, Story 2B.5).

This module provides a test stub for PhaseWitnessBatchingProtocol
that allows for controlled test scenarios without full service
dependencies.

Updated for Story 2B.5: Now uses TranscriptStoreProtocol for
content-addressed transcript storage.

Usage:
    from src.infrastructure.stubs.phase_witness_batching_stub import (
        PhaseWitnessBatchingStub,
    )
    from src.infrastructure.stubs.transcript_store_stub import TranscriptStoreStub

    transcript_store = TranscriptStoreStub()
    stub = PhaseWitnessBatchingStub(transcript_store=transcript_store)
    stub.set_force_error(True)  # Force errors for testing

    # In tests
    assert len(stub.witness_phase_calls) == 1
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


class PhaseWitnessBatchingStub:
    """Stub implementation of PhaseWitnessBatchingProtocol for testing.

    Updated for Story 2B.5: Uses TranscriptStoreProtocol for content-addressed
    transcript storage instead of in-memory dictionary.

    Provides configurable witness event generation for unit tests
    without requiring full service dependencies.

    Features:
    - Tracks all method calls for assertions
    - Configurable error forcing for error path testing
    - Proper hash chain generation for integration tests
    - Uses TranscriptStoreProtocol for transcript storage
    """

    def __init__(self, transcript_store: TranscriptStoreProtocol) -> None:
        """Initialize the stub.

        Args:
            transcript_store: Content-addressed transcript storage protocol.
                Typically use TranscriptStoreStub for testing.
        """
        self._transcript_store = transcript_store

        self.witness_phase_calls: list[
            tuple[DeliberationSession, DeliberationPhase, str, dict[str, Any]]
        ] = []
        self.get_phase_witness_calls: list[tuple[UUID, DeliberationPhase]] = []
        self.get_all_witnesses_calls: list[UUID] = []
        self.get_transcript_by_hash_calls: list[bytes] = []
        self.verify_witness_chain_calls: list[UUID] = []

        self._events: dict[UUID, dict[DeliberationPhase, PhaseWitnessEvent]] = {}
        self._force_error: bool = False
        self._force_chain_invalid: bool = False

    def set_force_error(self, force: bool) -> None:
        """Force errors for testing error paths.

        Args:
            force: If True, witness_phase will raise RuntimeError.
        """
        self._force_error = force

    def set_force_chain_invalid(self, force: bool) -> None:
        """Force chain verification to return False.

        Args:
            force: If True, verify_witness_chain returns False.
        """
        self._force_chain_invalid = force

    def _compute_hash(self, content: str) -> bytes:
        """Compute Blake3 hash."""
        return blake3.blake3(content.encode("utf-8")).digest()

    def _get_previous_witness_hash(
        self,
        session_id: UUID,
        phase: DeliberationPhase,
    ) -> bytes | None:
        """Get previous phase's witness hash."""
        current_idx = PHASE_ORDER.index(phase)
        if current_idx == 0:
            return None

        previous_phase = PHASE_ORDER[current_idx - 1]
        session_events = self._events.get(session_id, {})
        previous_event = session_events.get(previous_phase)

        if previous_event is not None:
            return previous_event.event_hash
        return None

    async def witness_phase(
        self,
        session: DeliberationSession,
        phase: DeliberationPhase,
        transcript: str,
        metadata: dict[str, Any],
        start_timestamp: datetime,
        end_timestamp: datetime,
    ) -> PhaseWitnessEvent:
        """Record call and return stub event.

        Args:
            session: The deliberation session.
            phase: The phase that completed.
            transcript: Full transcript text.
            metadata: Phase metadata.
            start_timestamp: When phase started.
            end_timestamp: When phase completed.

        Returns:
            PhaseWitnessEvent with proper hash chain.

        Raises:
            RuntimeError: If force_error is True.
        """
        self.witness_phase_calls.append((session, phase, transcript, metadata))

        if self._force_error:
            raise RuntimeError("Forced error for testing")

        # Store transcript via content-addressed store (Story 2B.5)
        transcript_ref = await self._transcript_store.store(transcript)
        transcript_hash = transcript_ref.content_hash

        # Get previous hash for chaining
        previous_hash = self._get_previous_witness_hash(session.session_id, phase)

        event = PhaseWitnessEvent(
            event_id=uuid4(),
            session_id=session.session_id,
            phase=phase,
            transcript_hash=transcript_hash,
            participating_archons=session.assigned_archons,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            phase_metadata=dict(metadata),
            previous_witness_hash=previous_hash,
        )

        if session.session_id not in self._events:
            self._events[session.session_id] = {}
        self._events[session.session_id][phase] = event

        return event

    async def get_phase_witness(
        self,
        session_id: UUID,
        phase: DeliberationPhase,
    ) -> PhaseWitnessEvent | None:
        """Get recorded event for phase.

        Args:
            session_id: Session UUID.
            phase: Phase to retrieve.

        Returns:
            PhaseWitnessEvent if found, None otherwise.
        """
        self.get_phase_witness_calls.append((session_id, phase))
        return self._events.get(session_id, {}).get(phase)

    async def get_all_witnesses(
        self,
        session_id: UUID,
    ) -> list[PhaseWitnessEvent]:
        """Get all events for session in order.

        Args:
            session_id: Session UUID.

        Returns:
            List of events in phase order.
        """
        self.get_all_witnesses_calls.append(session_id)
        session_events = self._events.get(session_id, {})
        return [session_events[p] for p in PHASE_ORDER if p in session_events]

    async def get_transcript_by_hash(
        self,
        transcript_hash: bytes,
    ) -> str | None:
        """Get transcript by hash.

        Story 2B.5: Delegates to TranscriptStoreProtocol for retrieval.

        Args:
            transcript_hash: Blake3 hash (32 bytes).

        Returns:
            Transcript text if found, None otherwise.
        """
        self.get_transcript_by_hash_calls.append(transcript_hash)
        return await self._transcript_store.retrieve(transcript_hash)

    async def verify_witness_chain(
        self,
        session_id: UUID,
    ) -> bool:
        """Verify chain integrity.

        Args:
            session_id: Session UUID.

        Returns:
            True if valid (or force_chain_invalid is False).
        """
        self.verify_witness_chain_calls.append(session_id)

        if self._force_chain_invalid:
            return False

        # Actually verify the chain
        witnesses = await self.get_all_witnesses(session_id)

        if not witnesses:
            return True

        if witnesses[0].previous_witness_hash is not None:
            return False

        for i in range(1, len(witnesses)):
            if witnesses[i].previous_witness_hash != witnesses[i - 1].event_hash:
                return False

        return True

    def reset(self) -> None:
        """Reset all recorded calls and state.

        Note: Does not clear transcript store - call transcript_store.clear()
        separately if needed.
        """
        self.witness_phase_calls.clear()
        self.get_phase_witness_calls.clear()
        self.get_all_witnesses_calls.clear()
        self.get_transcript_by_hash_calls.clear()
        self.verify_witness_chain_calls.clear()
        self._events.clear()
        self._force_error = False
        self._force_chain_invalid = False

    def get_witness_count(self, session_id: UUID) -> int:
        """Get number of witnesses for session."""
        return len(self._events.get(session_id, {}))

    def has_complete_witnessing(self, session_id: UUID) -> bool:
        """Check if all 4 phases are witnessed."""
        return self.get_witness_count(session_id) == len(PHASE_ORDER)
