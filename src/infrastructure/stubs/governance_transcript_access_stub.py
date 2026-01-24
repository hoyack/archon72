"""Governance Transcript Access Stub (Story 7.6, FR-7.4).

This module provides a stub implementation of GovernanceTranscriptAccessProtocol
for development and testing.

Constitutional Constraints:
- Ruling-2: Elevated tier access for governance actors
- FR-7.4: Full transcript access
- CT-12: Access logging for audit trail
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from uuid import UUID

from src.application.dtos.governance_transcript import (
    FullTranscriptResponse,
    PhaseTranscriptDetail,
    TranscriptUtterance,
)
from src.application.ports.governance_transcript_access import (
    GovernanceTranscriptAccessProtocol,
)
from src.domain.errors.deliberation import SessionNotFoundError


class StubOperation(Enum):
    """Operations that can be recorded on the stub (for testing)."""

    GET_FULL_TRANSCRIPT = auto()


@dataclass
class StubAccessRecord:
    """Record of an access attempt (for testing)."""

    session_id: UUID
    accessor_archon_id: UUID
    accessor_role: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class GovernanceTranscriptAccessStub(GovernanceTranscriptAccessProtocol):
    """Stub implementation of GovernanceTranscriptAccessProtocol.

    This stub provides configurable responses for testing the elevated
    transcript access functionality.

    Attributes:
        _responses: Pre-configured responses by session_id.
        _access_records: Records of all access attempts (for audit testing).
        _operations: List of operations for test verification.
        _error_sessions: Session IDs that should raise SessionNotFoundError.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._responses: dict[UUID, FullTranscriptResponse] = {}
        self._access_records: list[StubAccessRecord] = []
        self._operations: list[tuple[StubOperation, dict]] = []
        self._error_sessions: set[UUID] = set()

    async def get_full_transcript(
        self,
        session_id: UUID,
        accessor_archon_id: UUID,
        accessor_role: str,
    ) -> FullTranscriptResponse:
        """Get full transcript for a deliberation session.

        Args:
            session_id: UUID of the deliberation session.
            accessor_archon_id: UUID of the accessor (for audit logging).
            accessor_role: Role of the accessor (HIGH_ARCHON or AUDITOR).

        Returns:
            FullTranscriptResponse with complete transcript data.

        Raises:
            SessionNotFoundError: If session is in error set or not found.
        """
        # Record operation
        self._operations.append(
            (
                StubOperation.GET_FULL_TRANSCRIPT,
                {
                    "session_id": str(session_id),
                    "accessor_archon_id": str(accessor_archon_id),
                    "accessor_role": accessor_role,
                },
            )
        )

        # Record access for audit verification
        self._access_records.append(
            StubAccessRecord(
                session_id=session_id,
                accessor_archon_id=accessor_archon_id,
                accessor_role=accessor_role,
            )
        )

        # Check if session should error
        if session_id in self._error_sessions:
            raise SessionNotFoundError(
                session_id=str(session_id),
                message="Deliberation session not found",
            )

        # Return configured response or error
        if session_id in self._responses:
            return self._responses[session_id]

        raise SessionNotFoundError(
            session_id=str(session_id),
            message="Deliberation session not found",
        )

    # Test helper methods

    def configure_response(
        self,
        session_id: UUID,
        response: FullTranscriptResponse,
    ) -> None:
        """Configure a response for a specific session (test helper).

        Args:
            session_id: Session to configure response for.
            response: Response to return.
        """
        self._responses[session_id] = response

    def configure_session_not_found(self, session_id: UUID) -> None:
        """Configure a session to raise SessionNotFoundError (test helper).

        Args:
            session_id: Session that should raise error.
        """
        self._error_sessions.add(session_id)

    def clear(self) -> None:
        """Clear all stored data (test helper)."""
        self._responses.clear()
        self._access_records.clear()
        self._operations.clear()
        self._error_sessions.clear()

    def get_access_records(self) -> list[StubAccessRecord]:
        """Get all access records for audit verification (test helper).

        Returns:
            List of access records.
        """
        return self._access_records.copy()

    def get_operations(self) -> list[tuple[StubOperation, dict]]:
        """Get list of operations for test verification.

        Returns:
            List of (operation, args) tuples.
        """
        return self._operations.copy()

    def get_access_count(self) -> int:
        """Get total count of access attempts (test helper).

        Returns:
            Number of access attempts.
        """
        return len(self._access_records)

    def was_accessed_by(
        self,
        session_id: UUID,
        accessor_archon_id: UUID,
    ) -> bool:
        """Check if a session was accessed by a specific archon (test helper).

        Args:
            session_id: Session to check.
            accessor_archon_id: Archon to check for.

        Returns:
            True if the archon accessed the session.
        """
        return any(
            r.session_id == session_id and r.accessor_archon_id == accessor_archon_id
            for r in self._access_records
        )


def create_test_transcript_response(
    session_id: UUID,
    petition_id: UUID,
    outcome: str = "ACKNOWLEDGE",
    has_dissent: bool = False,
) -> FullTranscriptResponse:
    """Create a test transcript response (factory helper).

    Args:
        session_id: Session ID.
        petition_id: Petition ID.
        outcome: Deliberation outcome.
        has_dissent: Whether there was dissent.

    Returns:
        FullTranscriptResponse for testing.
    """
    from uuid import uuid4

    now = datetime.now(timezone.utc)
    archon_ids = (uuid4(), uuid4(), uuid4())

    # Create sample utterances
    utterances = [
        TranscriptUtterance(
            archon_id=archon_ids[0],
            timestamp=now,
            content="I assess this petition as concerning realm boundaries.",
            sequence=0,
        ),
        TranscriptUtterance(
            archon_id=archon_ids[1],
            timestamp=now,
            content="I concur with the assessment.",
            sequence=1,
        ),
        TranscriptUtterance(
            archon_id=archon_ids[2],
            timestamp=now,
            content="I agree as well.",
            sequence=2,
        ),
    ]

    # Create phases
    phases = [
        PhaseTranscriptDetail(
            phase="ASSESS",
            start_timestamp=now,
            end_timestamp=now,
            utterances=utterances,
            transcript_hash_hex="a" * 64,
        ),
        PhaseTranscriptDetail(
            phase="POSITION",
            start_timestamp=now,
            end_timestamp=now,
            utterances=utterances,
            transcript_hash_hex="b" * 64,
        ),
        PhaseTranscriptDetail(
            phase="CROSS_EXAMINE",
            start_timestamp=now,
            end_timestamp=now,
            utterances=utterances,
            transcript_hash_hex="c" * 64,
        ),
        PhaseTranscriptDetail(
            phase="VOTE",
            start_timestamp=now,
            end_timestamp=now,
            utterances=utterances,
            transcript_hash_hex="d" * 64,
        ),
    ]

    return FullTranscriptResponse(
        session_id=session_id,
        petition_id=petition_id,
        phases=phases,
        outcome=outcome,
        has_dissent=has_dissent,
        dissent_text="I respectfully dissent from the majority." if has_dissent else None,
        completed_at=now,
    )
