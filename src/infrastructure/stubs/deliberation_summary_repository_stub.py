"""Deliberation Summary Repository Stub (Story 7.4, FR-7.4).

This module provides an in-memory stub implementation of
DeliberationSummaryRepositoryProtocol for development and testing.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy - All operations logged
- Ruling-2: Tiered transcript access - raw data for mediation layer
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from src.application.ports.deliberation_summary import (
    DeliberationSummaryRepositoryProtocol,
)

if TYPE_CHECKING:
    from src.domain.events.phase_witness import PhaseWitnessEvent
    from src.domain.models.deliberation_session import DeliberationSession


class DeliberationSummaryRepositoryStub(DeliberationSummaryRepositoryProtocol):
    """In-memory stub implementation of DeliberationSummaryRepositoryProtocol.

    This stub stores deliberation sessions and witness events in memory
    for development and testing. It is NOT suitable for production use.

    Attributes:
        sessions: Dictionary mapping petition_id to DeliberationSession.
        witnesses: Dictionary mapping session_id to list of PhaseWitnessEvent.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._sessions_by_petition: dict[UUID, DeliberationSession] = {}
        self._sessions_by_id: dict[UUID, DeliberationSession] = {}
        self._witnesses_by_session: dict[UUID, list[PhaseWitnessEvent]] = {}

    def add_session(self, session: DeliberationSession) -> None:
        """Add a session to the stub storage (test helper).

        Args:
            session: The session to store.
        """
        self._sessions_by_petition[session.petition_id] = session
        self._sessions_by_id[session.session_id] = session

    def add_witnesses(
        self,
        session_id: UUID,
        witnesses: list[PhaseWitnessEvent],
    ) -> None:
        """Add witnesses to the stub storage (test helper).

        Args:
            session_id: The session ID.
            witnesses: The witness events to store.
        """
        self._witnesses_by_session[session_id] = witnesses

    def clear(self) -> None:
        """Clear all stored data (test helper)."""
        self._sessions_by_petition.clear()
        self._sessions_by_id.clear()
        self._witnesses_by_session.clear()

    async def get_session_by_petition_id(
        self,
        petition_id: UUID,
    ) -> DeliberationSession | None:
        """Get deliberation session for a petition.

        Args:
            petition_id: UUID of the petition.

        Returns:
            DeliberationSession if exists, None otherwise.
        """
        return self._sessions_by_petition.get(petition_id)

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
            Empty list if session has no witnesses.
        """
        witnesses = self._witnesses_by_session.get(session_id, [])
        # Sort by phase order
        phase_order = {"ASSESS": 0, "POSITION": 1, "CROSS_EXAMINE": 2, "VOTE": 3}
        return sorted(witnesses, key=lambda w: phase_order.get(w.phase.value, 99))

    async def get_session_by_session_id(
        self,
        session_id: UUID,
    ) -> DeliberationSession | None:
        """Get deliberation session by session ID (Story 7.6, AC-1, AC-5).

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            DeliberationSession if exists, None otherwise.
        """
        return self._sessions_by_id.get(session_id)
