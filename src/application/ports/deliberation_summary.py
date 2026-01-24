"""Deliberation Summary Repository Port (Story 7.4, FR-7.4).

This module defines the port interface for accessing deliberation session
data needed to build mediated summaries for Observers.

Constitutional Constraints:
- Ruling-2: Tiered transcript access - port provides raw data, service mediates
- FR-7.4: System SHALL provide deliberation summary to Observer
- CT-12: Witnessing creates accountability - access to witness events
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.events.phase_witness import PhaseWitnessEvent
    from src.domain.models.deliberation_session import DeliberationSession


class DeliberationSummaryRepositoryProtocol(Protocol):
    """Protocol for accessing deliberation data for summary generation (Story 7.4).

    This port provides access to the raw deliberation session and witness events
    that the TranscriptAccessMediationService uses to build mediated summaries.

    Constitutional Constraints:
    - Ruling-2: Raw data access for mediation layer
    - FR-7.4: Support deliberation summary retrieval
    - CT-12: Access to witness records for hash reference
    """

    async def get_session_by_petition_id(
        self,
        petition_id: UUID,
    ) -> DeliberationSession | None:
        """Get deliberation session for a petition.

        Args:
            petition_id: UUID of the petition.

        Returns:
            DeliberationSession if exists, None otherwise.
            Returns None if petition was auto-escalated (no deliberation).
        """
        ...

    async def get_phase_witnesses(
        self,
        session_id: UUID,
    ) -> list[PhaseWitnessEvent]:
        """Get phase witness events for a deliberation session.

        Returns witness events in phase order (ASSESS, POSITION, CROSS_EXAMINE, VOTE).

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            List of PhaseWitnessEvent records, ordered by phase.
            Empty list if session has no witnesses yet.
        """
        ...

    async def get_session_by_session_id(
        self,
        session_id: UUID,
    ) -> DeliberationSession | None:
        """Get deliberation session by session ID (Story 7.6, AC-1, AC-5).

        Required for elevated transcript access where lookup is by session_id
        rather than petition_id.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            DeliberationSession if exists, None otherwise.
        """
        ...
