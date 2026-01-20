"""Audit trail reconstructor protocol (Story 2B.6, FR-11.12, NFR-6.5).

This module defines the protocol for audit trail reconstruction,
enabling complete deliberation timeline replay and verification.

Constitutional Constraints:
- FR-11.12: Complete deliberation transcript preservation for audit
- NFR-6.5: Full state history reconstruction from event log
- CT-12: Verify unbroken chain of accountability
- CT-14: Every claim terminates in visible, witnessed fate
- NFR-4.2: Event log durability - append-only, no deletion
- NFR-10.4: 100% witness completeness
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.models.audit_timeline import (
    AuditTimeline,
    TimelineEvent,
    WitnessChainVerification,
)


class SessionNotFoundError(Exception):
    """Raised when a deliberation session is not found.

    This error indicates that the requested session_id does not exist
    in the event store or session repository.

    Attributes:
        session_id: The UUID of the session that was not found.
    """

    def __init__(self, session_id: UUID, message: str | None = None) -> None:
        """Initialize SessionNotFoundError.

        Args:
            session_id: The UUID of the session that was not found.
            message: Optional custom error message.
        """
        self.session_id = session_id
        if message is None:
            message = f"Deliberation session not found: {session_id}"
        super().__init__(message)


class AuditTrailReconstructorProtocol(Protocol):
    """Protocol for audit trail reconstruction (Story 2B.6, FR-11.12).

    Implementations reconstruct complete deliberation timelines from
    the event log, enabling full audit trail verification per NFR-6.5.

    The protocol supports three main operations:
    1. `reconstruct_timeline`: Full timeline with transcripts
    2. `get_session_events`: Raw events without transcript content
    3. `verify_witness_chain`: Cryptographic chain verification

    Constitutional Constraints:
    - FR-11.12: Complete transcript preservation for audit reconstruction
    - NFR-6.5: Full state history reconstruction from event log
    - CT-12: Verify unbroken chain of accountability through witness hashes
    - CT-14: Every claim terminates in visible, witnessed fate
    - NFR-10.4: 100% witness completeness verification

    Example:
        ```python
        # Reconstruct full timeline for audit
        reconstructor = AuditTrailReconstructorService(transcript_store)
        timeline = await reconstructor.reconstruct_timeline(session_id)

        # Verify witness chain integrity
        verification = await reconstructor.verify_witness_chain(session_id)
        if not verification.is_valid:
            logger.error(f"Witness chain broken: {verification.broken_links}")
        ```
    """

    async def reconstruct_timeline(
        self,
        session_id: UUID,
    ) -> AuditTimeline:
        """Reconstruct complete audit timeline for a session.

        Retrieves all events for the session, fetches transcript content
        from the TranscriptStore, and builds a chronological timeline
        for audit purposes.

        The returned AuditTimeline includes:
        - All events in chronological order
        - Transcript content for each phase (if available)
        - Dissent record (if any)
        - Substitution records (if any)
        - Termination reason (NORMAL, TIMEOUT, DEADLOCK, ABORT)

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            AuditTimeline with all events, transcripts, and metadata.

        Raises:
            SessionNotFoundError: If session_id doesn't exist.

        Constitutional Constraint (FR-11.12):
        Complete deliberation transcript preservation for audit reconstruction.
        """
        ...

    async def get_session_events(
        self,
        session_id: UUID,
    ) -> list[TimelineEvent]:
        """Get all events for a session in chronological order.

        Returns raw events without transcript content or verification.
        This is a lightweight operation for event listing without
        the overhead of transcript retrieval.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            List of TimelineEvents ordered by occurred_at.

        Raises:
            SessionNotFoundError: If session_id doesn't exist.

        Constitutional Constraint (NFR-6.5):
        Full state history reconstruction from event log.
        """
        ...

    async def verify_witness_chain(
        self,
        session_id: UUID,
    ) -> WitnessChainVerification:
        """Verify the witness hash chain for a session.

        Performs cryptographic verification of the witness chain:
        1. Verifies ASSESS phase has no previous_witness_hash (chain start)
        2. Verifies each subsequent phase links to prior event_hash
        3. Verifies all transcript hashes exist in the transcript store
        4. Verifies all transcripts re-hash to their stored hash

        A broken chain indicates potential tampering or data corruption.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            WitnessChainVerification with:
            - is_valid: Overall pass/fail
            - broken_links: List of broken chain links
            - missing_transcripts: List of missing transcript hashes
            - integrity_failures: List of hash mismatches
            - verified_events: Count of verified events
            - total_events: Total events checked

        Raises:
            SessionNotFoundError: If session_id doesn't exist.

        Constitutional Constraint (CT-12):
        Every action must be witnessed by another Archon, creating an
        unbroken chain of accountability.
        """
        ...
