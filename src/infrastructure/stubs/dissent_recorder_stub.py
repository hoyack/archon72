"""Dissent recorder stub implementation (Story 2B.1, AC-7).

This module provides an in-memory stub implementation of
DissentRecorderProtocol for development and testing purposes.

Constitutional Constraints:
- FR-11.8: System SHALL record dissent opinions in 2-1 votes
- CT-12: Witnessing creates accountability - dissent is witnessed
- AT-6: Deliberation is collective judgment - minority voice preserved
- NFR-6.5: Audit trail completeness - complete reconstruction possible
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING
from uuid import UUID

import blake3
from uuid6 import uuid7

from src.application.ports.dissent_recorder import DissentRecorderProtocol
from src.domain.events.dissent import DissentRecordedEvent
from src.domain.models.consensus_result import ConsensusResult
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationSession,
)
from src.domain.models.dissent_record import DissentRecord

if TYPE_CHECKING:
    pass


class DissentRecorderOperation(Enum):
    """Operations that can be recorded on the stub (for testing)."""

    RECORD_DISSENT = auto()
    GET_BY_PETITION = auto()
    GET_BY_ARCHON = auto()
    GET_BY_SESSION = auto()
    HAS_DISSENT = auto()


class DissentRecorderStub(DissentRecorderProtocol):
    """In-memory stub implementation of DissentRecorderProtocol.

    This stub provides a simple implementation for development and testing
    that stores dissent records in memory.

    NOT suitable for production use.

    Constitutional Compliance:
    - FR-11.8: Dissent recording (simulated)
    - CT-12: Witnessing creates accountability (simulated)
    - NFR-6.5: Audit trail completeness (simulated)

    Attributes:
        _dissents_by_petition: Dictionary mapping petition_id to DissentRecord.
        _dissents_by_session: Dictionary mapping session_id to DissentRecord.
        _dissents_by_archon: Dictionary mapping archon_id to list of DissentRecord.
        _events_emitted: List of DissentRecordedEvent instances emitted.
        _operations: List of operations for test verification.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._dissents_by_petition: dict[UUID, DissentRecord] = {}
        self._dissents_by_session: dict[UUID, DissentRecord] = {}
        self._dissents_by_archon: dict[UUID, list[DissentRecord]] = {}
        self._events_emitted: list[DissentRecordedEvent] = []
        self._operations: list[tuple[DissentRecorderOperation, dict]] = []

    def _compute_rationale_hash(self, rationale: str) -> bytes:
        """Compute Blake3 hash of rationale text.

        Args:
            rationale: The rationale text.

        Returns:
            32-byte Blake3 hash.
        """
        return blake3.blake3(rationale.encode("utf-8")).digest()

    async def record_dissent(
        self,
        session: DeliberationSession,
        consensus_result: ConsensusResult,
        dissent_rationale: str,
    ) -> DissentRecord | None:
        """Record dissent if present in the consensus result (FR-11.8).

        Args:
            session: The deliberation session.
            consensus_result: Result from consensus resolution.
            dissent_rationale: The dissenting archon's reasoning text.

        Returns:
            DissentRecord if dissent present (2-1 vote), None if unanimous.
        """
        self._operations.append((
            DissentRecorderOperation.RECORD_DISSENT,
            {
                "session_id": session.session_id,
                "petition_id": session.petition_id,
                "consensus_result": consensus_result,
            },
        ))

        # No dissent if unanimous
        if not consensus_result.has_dissent:
            return None

        if consensus_result.dissent_archon_id is None:
            return None

        if consensus_result.winning_outcome is None:
            return None

        # Find dissenter's vote
        dissent_disposition: DeliberationOutcome | None = None
        for archon_id, vote in session.votes.items():
            if archon_id == consensus_result.dissent_archon_id:
                dissent_disposition = vote
                break

        if dissent_disposition is None:
            for outcome_str, count in consensus_result.vote_distribution.items():
                if count == 1 and outcome_str != consensus_result.winning_outcome:
                    dissent_disposition = DeliberationOutcome(outcome_str)
                    break

        if dissent_disposition is None:
            return None

        # Create dissent record
        rationale_hash = self._compute_rationale_hash(dissent_rationale)
        majority_disposition = DeliberationOutcome(consensus_result.winning_outcome)

        dissent_record = DissentRecord(
            dissent_id=uuid7(),
            session_id=session.session_id,
            petition_id=session.petition_id,
            dissent_archon_id=consensus_result.dissent_archon_id,
            dissent_disposition=dissent_disposition,
            dissent_rationale=dissent_rationale,
            rationale_hash=rationale_hash,
            majority_disposition=majority_disposition,
        )

        # Store in-memory
        self._dissents_by_petition[session.petition_id] = dissent_record
        self._dissents_by_session[session.session_id] = dissent_record

        if consensus_result.dissent_archon_id not in self._dissents_by_archon:
            self._dissents_by_archon[consensus_result.dissent_archon_id] = []
        self._dissents_by_archon[consensus_result.dissent_archon_id].append(
            dissent_record
        )

        # Emit event (simulated)
        event = DissentRecordedEvent(
            event_id=uuid7(),
            session_id=session.session_id,
            petition_id=session.petition_id,
            dissent_archon_id=consensus_result.dissent_archon_id,
            dissent_disposition=dissent_disposition.value,
            rationale_hash=rationale_hash.hex(),
            majority_disposition=majority_disposition.value,
            recorded_at=dissent_record.recorded_at,
        )
        self._events_emitted.append(event)

        return dissent_record

    async def get_dissent_by_petition(
        self,
        petition_id: UUID,
    ) -> DissentRecord | None:
        """Retrieve dissent record for a petition.

        Args:
            petition_id: The petition ID.

        Returns:
            DissentRecord if dissent was recorded, None otherwise.
        """
        self._operations.append((
            DissentRecorderOperation.GET_BY_PETITION,
            {"petition_id": petition_id},
        ))
        return self._dissents_by_petition.get(petition_id)

    async def get_dissents_by_archon(
        self,
        archon_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DissentRecord]:
        """Retrieve all dissent records for an archon.

        Args:
            archon_id: The archon ID.
            limit: Maximum records to return.
            offset: Pagination offset.

        Returns:
            List of DissentRecord where archon dissented.
        """
        self._operations.append((
            DissentRecorderOperation.GET_BY_ARCHON,
            {"archon_id": archon_id, "limit": limit, "offset": offset},
        ))
        all_dissents = self._dissents_by_archon.get(archon_id, [])
        sorted_dissents = sorted(
            all_dissents, key=lambda d: d.recorded_at, reverse=True
        )
        return sorted_dissents[offset : offset + limit]

    async def has_dissent(self, session_id: UUID) -> bool:
        """Check if a session has a recorded dissent.

        Args:
            session_id: The deliberation session ID.

        Returns:
            True if dissent was recorded, False otherwise.
        """
        self._operations.append((
            DissentRecorderOperation.HAS_DISSENT,
            {"session_id": session_id},
        ))
        return session_id in self._dissents_by_session

    async def get_dissent_by_session(
        self,
        session_id: UUID,
    ) -> DissentRecord | None:
        """Retrieve dissent record for a session.

        Args:
            session_id: The deliberation session ID.

        Returns:
            DissentRecord if dissent was recorded, None otherwise.
        """
        self._operations.append((
            DissentRecorderOperation.GET_BY_SESSION,
            {"session_id": session_id},
        ))
        return self._dissents_by_session.get(session_id)

    # Test helper methods

    def clear(self) -> None:
        """Clear all dissent records and state (for testing)."""
        self._dissents_by_petition.clear()
        self._dissents_by_session.clear()
        self._dissents_by_archon.clear()
        self._events_emitted.clear()
        self._operations.clear()

    def get_dissent_count(self) -> int:
        """Get total number of dissents recorded.

        Returns:
            Total count.
        """
        return len(self._dissents_by_session)

    def get_dissent_count_by_archon(self, archon_id: UUID) -> int:
        """Get number of dissents for a specific archon.

        Args:
            archon_id: The archon ID.

        Returns:
            Count of dissents.
        """
        return len(self._dissents_by_archon.get(archon_id, []))

    def get_emitted_events(self) -> list[DissentRecordedEvent]:
        """Get list of emitted events (for testing).

        Returns:
            List of DissentRecordedEvent instances.
        """
        return self._events_emitted.copy()

    def get_operations(self) -> list[tuple[DissentRecorderOperation, dict]]:
        """Get list of operations for test verification.

        Returns:
            List of (operation, args) tuples.
        """
        return self._operations.copy()

    def inject_dissent(self, dissent: DissentRecord) -> None:
        """Inject a dissent record for testing.

        Args:
            dissent: The dissent record to inject.
        """
        self._dissents_by_petition[dissent.petition_id] = dissent
        self._dissents_by_session[dissent.session_id] = dissent

        if dissent.dissent_archon_id not in self._dissents_by_archon:
            self._dissents_by_archon[dissent.dissent_archon_id] = []
        self._dissents_by_archon[dissent.dissent_archon_id].append(dissent)
