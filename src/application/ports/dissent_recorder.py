"""Dissent recorder protocol (Story 2B.1, FR-11.8).

This module defines the protocol for recording dissent in 2-1 deliberation
votes. Dissent records capture the minority archon's vote and reasoning
for audit and governance review purposes.

Constitutional Constraints:
- CT-12: Witnessing creates accountability - dissent is witnessed
- AT-6: Deliberation is collective judgment - minority voice preserved
- CT-14: Silence is expensive - even dissent terminates visibly
- NFR-6.5: Audit trail completeness - complete reconstruction possible
- NFR-10.3: Consensus determinism - 100% reproducible
- NFR-10.4: Witness completeness - 100% utterances witnessed
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.models.consensus_result import ConsensusResult
from src.domain.models.deliberation_session import DeliberationSession
from src.domain.models.dissent_record import DissentRecord


class DissentRecorderProtocol(Protocol):
    """Protocol for recording dissent in 2-1 deliberation votes (FR-11.8).

    Implementations extract dissent information from consensus results
    and persist it for audit trail purposes.

    Constitutional Constraints:
    - CT-12: Witnessing creates accountability
    - AT-6: Minority voice preserved
    - NFR-6.5: Enables complete audit trail reconstruction
    """

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
        ...

    async def get_dissent_by_petition(
        self,
        petition_id: UUID,
    ) -> DissentRecord | None:
        """Retrieve dissent record for a petition (AC-5).

        Args:
            petition_id: The petition ID.

        Returns:
            DissentRecord if dissent was recorded, None otherwise.

        Performance (NFR-3.2): Query executes in < 50ms.
        """
        ...

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
        ...

    async def has_dissent(self, session_id: UUID) -> bool:
        """Check if a session has a recorded dissent.

        Args:
            session_id: The deliberation session ID.

        Returns:
            True if dissent was recorded, False otherwise.
        """
        ...

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
        ...
