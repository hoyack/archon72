"""Phase witness batching protocol (Story 2A.7, FR-11.7).

This module defines the protocol for phase-level witness batching
in the deliberation system. Per Ruling-1, witnessing occurs at phase
boundaries to avoid witness volume explosion.

Constitutional Constraints:
- CT-12: Every action must be witnessed
- FR-11.7: Hash-referenced ledger witnessing at phase boundaries
- NFR-10.4: 100% witness completeness
- Ruling-1: Phase-level batching
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from src.domain.events.phase_witness import PhaseWitnessEvent
from src.domain.models.deliberation_session import (
    DeliberationPhase,
    DeliberationSession,
)


class PhaseWitnessBatchingProtocol(Protocol):
    """Protocol for phase-level witness batching (Story 2A.7, FR-11.7).

    Implementations batch utterances by phase and emit a single witness
    event per phase boundary, avoiding witness volume explosion while
    maintaining 100% auditability.

    Constitutional Constraints:
    - CT-12: Every action witnessed
    - FR-11.7: Phase boundary witnessing
    - NFR-10.4: 100% witness completeness
    """

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

        Creates a witness event containing:
        - Blake3 hash of the full transcript (32 bytes)
        - Link to previous phase's witness (hash chain)
        - Phase-specific metadata
        - Timestamps

        The raw transcript is stored as a content-addressed artifact
        referenced by hash for audit retrieval.

        Args:
            session: The deliberation session.
            phase: The phase that completed.
            transcript: Full text transcript of the phase.
            metadata: Phase-specific metadata.
            start_timestamp: When phase started (UTC).
            end_timestamp: When phase completed (UTC).

        Returns:
            PhaseWitnessEvent with hash-referenced transcript.

        Raises:
            ValueError: If witnessing out of order or invalid input.
        """
        ...

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
        ...

    async def get_all_witnesses(
        self,
        session_id: UUID,
    ) -> list[PhaseWitnessEvent]:
        """Retrieve all witness events for a session in phase order.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            List of PhaseWitnessEvents in chronological order.
            Empty list if no witnesses found.
        """
        ...

    async def get_transcript_by_hash(
        self,
        transcript_hash: bytes,
    ) -> str | None:
        """Retrieve raw transcript by content hash.

        Used for audit trail reconstruction to verify witness
        events against their original content.

        Args:
            transcript_hash: Blake3 hash of the transcript (32 bytes).

        Returns:
            Raw transcript text if found, None otherwise.
        """
        ...

    async def verify_witness_chain(
        self,
        session_id: UUID,
    ) -> bool:
        """Verify the hash chain integrity of all witness events.

        Ensures that each witness event correctly references the
        previous phase's witness hash.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            True if chain is valid, False if integrity is compromised.
        """
        ...
