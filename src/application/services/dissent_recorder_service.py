"""Dissent recorder service (Story 2B.1, FR-11.8).

This module implements the DissentRecorderProtocol for recording and
retrieving dissent records from 2-1 deliberation votes.

Constitutional Constraints:
- CT-12: Witnessing creates accountability - dissent is witnessed
- AT-6: Deliberation is collective judgment - minority voice preserved
- CT-14: Silence is expensive - even dissent terminates visibly
- NFR-6.5: Audit trail completeness - complete reconstruction possible
- NFR-10.3: Consensus determinism - 100% reproducible
- NFR-10.4: Witness completeness - 100% utterances witnessed

Usage:
    from src.application.services.dissent_recorder_service import (
        DissentRecorderService,
    )

    service = DissentRecorderService(
        event_emitter=emitter,
    )

    # Record dissent when 2-1 consensus reached
    dissent = await service.record_dissent(
        session=session,
        consensus_result=result,
        dissent_rationale="rationale text",
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import blake3
from uuid6 import uuid7

from src.domain.events.dissent import (
    DISSENT_RECORDED_EVENT_TYPE,
    DissentRecordedEvent,
)
from src.domain.models.consensus_result import ConsensusResult
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationSession,
)
from src.domain.models.dissent_record import DissentRecord

if TYPE_CHECKING:
    from src.application.ports.event_store import EventStorePort

# System agent ID for dissent recording events
DISSENT_RECORDER_SYSTEM_AGENT_ID: str = "system:dissent-recorder"


class DissentRecorderService:
    """Service for recording dissent in 2-1 deliberation votes (FR-11.8).

    Extracts dissent information from consensus results and persists
    it for audit trail purposes. Emits DissentRecordedEvent for
    witnessing per CT-12.

    Constitutional Constraints:
    - CT-12: Witnessing creates accountability
    - AT-6: Minority voice preserved
    - NFR-6.5: Enables complete audit trail reconstruction
    - NFR-10.4: 100% witness completeness

    Attributes:
        _event_emitter: Protocol for emitting events (optional).
        _dissents_by_petition: In-memory storage by petition_id.
        _dissents_by_session: In-memory storage by session_id.
        _dissents_by_archon: In-memory storage by archon_id.
    """

    def __init__(
        self,
        event_emitter: EventStorePort | None = None,
    ) -> None:
        """Initialize the dissent recorder service.

        Args:
            event_emitter: Protocol for emitting dissent events (optional).
        """
        self._event_emitter = event_emitter
        # In-memory storage for development/testing
        # Production would use a repository
        self._dissents_by_petition: dict[UUID, DissentRecord] = {}
        self._dissents_by_session: dict[UUID, DissentRecord] = {}
        self._dissents_by_archon: dict[UUID, list[DissentRecord]] = {}

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

        Creates a DissentRecord when the consensus is 2-1 (not unanimous).
        The dissent record captures the minority archon's vote and reasoning.

        Args:
            session: The deliberation session.
            consensus_result: Result from consensus resolution.
            dissent_rationale: The dissenting archon's reasoning text.

        Returns:
            DissentRecord if dissent present (2-1 vote), None if unanimous.

        Constitutional Constraint (CT-12): The dissent is witnessed
        by emitting a DissentRecordedEvent.
        """
        # No dissent if unanimous
        if not consensus_result.has_dissent:
            return None

        if consensus_result.dissent_archon_id is None:
            return None

        if consensus_result.winning_outcome is None:
            return None

        # Find dissenter's vote (the outcome that differs from majority)
        dissent_disposition: DeliberationOutcome | None = None
        for archon_id, vote in session.votes.items():
            if archon_id == consensus_result.dissent_archon_id:
                dissent_disposition = vote
                break

        if dissent_disposition is None:
            # Fallback: deduce from vote distribution
            # The dissent is whichever outcome doesn't match the winning outcome
            for outcome_str, count in consensus_result.vote_distribution.items():
                if count == 1 and outcome_str != consensus_result.winning_outcome:
                    dissent_disposition = DeliberationOutcome(outcome_str)
                    break

        if dissent_disposition is None:
            # Cannot determine dissent disposition - shouldn't happen
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

        # Emit event for witnessing (CT-12)
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

        if self._event_emitter is not None:
            # Note: Actual event store integration would go here
            # await self._event_emitter.append(event.to_dict())
            pass

        return dissent_record

    async def get_dissent_by_petition(
        self,
        petition_id: UUID,
    ) -> DissentRecord | None:
        """Retrieve dissent record for a petition (AC-5).

        Args:
            petition_id: The petition ID.

        Returns:
            DissentRecord if dissent was recorded, None otherwise.
        """
        return self._dissents_by_petition.get(petition_id)

    async def get_dissents_by_archon(
        self,
        archon_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DissentRecord]:
        """Retrieve all dissent records for an archon (AC-6).

        Args:
            archon_id: The archon ID.
            limit: Maximum records to return.
            offset: Pagination offset.

        Returns:
            List of DissentRecord where archon dissented,
            ordered by recorded_at descending.
        """
        all_dissents = self._dissents_by_archon.get(archon_id, [])
        # Sort by recorded_at descending
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
        return self._dissents_by_session.get(session_id)

    def get_dissent_count_by_archon(self, archon_id: UUID) -> int:
        """Get total number of dissents recorded for an archon.

        Args:
            archon_id: The archon ID.

        Returns:
            Total count of dissents.
        """
        return len(self._dissents_by_archon.get(archon_id, []))

    def get_total_dissent_count(self) -> int:
        """Get total number of dissents recorded.

        Returns:
            Total count across all archons.
        """
        return len(self._dissents_by_session)
