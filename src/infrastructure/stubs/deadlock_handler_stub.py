"""Deadlock handler stub implementation (Story 2B.3, AC-6).

This module provides an in-memory stub implementation of
DeadlockHandlerProtocol for development and testing purposes.

Constitutional Constraints:
- FR-11.10: System SHALL auto-ESCALATE after 3 rounds without supermajority
- CT-11: Silent failure destroys legitimacy - deadlock MUST terminate
- AT-1: Every petition terminates in exactly one of Three Fates
- NFR-10.3: Consensus determinism - 100% reproducible
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from uuid6 import uuid7

from src.application.ports.deadlock_handler import DeadlockHandlerProtocol
from src.config.deliberation_config import (
    DEFAULT_DELIBERATION_CONFIG,
    DeliberationConfig,
)
from src.domain.events.deadlock import (
    CrossExamineRoundTriggeredEvent,
    DeadlockDetectedEvent,
)
from src.domain.models.deliberation_session import DeliberationSession


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class DeadlockHandlerStub(DeadlockHandlerProtocol):
    """In-memory stub implementation of DeadlockHandlerProtocol.

    This stub provides a simple implementation for development and testing
    that stores sessions and deadlock state in memory.

    NOT suitable for production use.

    Constitutional Compliance:
    - FR-11.10: Deadlock detection and auto-ESCALATE (simulated)
    - CT-11: Deadlock MUST terminate (simulated)
    - AT-1: Every petition terminates in one of Three Fates (simulated)
    - NFR-10.3: Consensus determinism (simulated)

    Attributes:
        _sessions: Dictionary mapping session_id to DeliberationSession.
        _deadlocks: Set of session IDs where deadlock was detected.
        _new_rounds: List of (session_id, round_number) for triggered rounds.
        _config: Deliberation configuration.
        _events_emitted: List of emitted events.
    """

    def __init__(
        self,
        config: DeliberationConfig | None = None,
    ) -> None:
        """Initialize the stub with empty storage.

        Args:
            config: Deliberation configuration. Uses default if not provided.
        """
        self._sessions: dict[UUID, DeliberationSession] = {}
        self._deadlocks: set[UUID] = set()
        self._new_rounds: list[tuple[UUID, int]] = []
        self._config = config or DEFAULT_DELIBERATION_CONFIG
        self._events_emitted: list[
            CrossExamineRoundTriggeredEvent | DeadlockDetectedEvent
        ] = []

    def register_session(self, session: DeliberationSession) -> None:
        """Register a session for deadlock tracking (test helper).

        Args:
            session: The session to register.
        """
        self._sessions[session.session_id] = session

    def is_deadlock_vote_pattern(
        self,
        vote_distribution: dict[str, int],
    ) -> bool:
        """Check if vote distribution represents a deadlock pattern (1-1-1).

        A deadlock vote pattern occurs when all 3 archons vote for
        different outcomes (1 vote each for 3 different outcomes).
        2-1 votes are NOT deadlocks (2 >= threshold of 2).

        Args:
            vote_distribution: Map of outcome name to vote count.

        Returns:
            True if votes show 1-1-1 split (deadlock), False otherwise.
        """
        # Sum total votes
        total_votes = sum(vote_distribution.values())
        if total_votes != 3:
            return False

        # Count how many outcomes have votes
        outcomes_with_votes = len([v for v in vote_distribution.values() if v > 0])

        # Deadlock = 3 different outcomes with 1 vote each
        if outcomes_with_votes == 3:
            # Verify each outcome has exactly 1 vote
            return all(v == 1 for v in vote_distribution.values())

        return False

    def can_continue_deliberation(
        self,
        session: DeliberationSession,
        max_rounds: int,
    ) -> bool:
        """Check if deliberation can continue with another round.

        Args:
            session: Current deliberation session.
            max_rounds: Maximum allowed rounds before deadlock.

        Returns:
            True if round_count < max_rounds, False if deadlock imminent.
        """
        return session.can_retry_cross_examine(max_rounds)

    async def handle_no_consensus(
        self,
        session: DeliberationSession,
        vote_distribution: dict[str, int],
        max_rounds: int,
    ) -> tuple[
        DeliberationSession,
        CrossExamineRoundTriggeredEvent | DeadlockDetectedEvent,
    ]:
        """Handle a voting round that failed to reach consensus (FR-11.10).

        Args:
            session: The deliberation session with failed consensus.
            vote_distribution: The vote split from the current round.
            max_rounds: Maximum rounds allowed.

        Returns:
            Tuple of (updated session, event emitted).

        Raises:
            SessionAlreadyCompleteError: If session is already complete.
            ValueError: If vote_distribution is not a valid deadlock pattern.
        """
        from src.domain.errors.deliberation import SessionAlreadyCompleteError

        # Validate session is not complete
        if session.phase.is_terminal():
            raise SessionAlreadyCompleteError(
                session_id=str(session.session_id),
                message="Cannot handle no consensus on completed session",
            )

        # Validate vote pattern is deadlock (1-1-1)
        if not self.is_deadlock_vote_pattern(vote_distribution):
            raise ValueError(
                f"Vote distribution {vote_distribution} is not a deadlock pattern (1-1-1). "
                "2-1 votes should use normal consensus resolution."
            )

        # Check if we can retry
        if self.can_continue_deliberation(session, max_rounds):
            return await self.trigger_new_round(session, vote_distribution)
        else:
            return await self.trigger_deadlock_escalation(session, vote_distribution)

    async def trigger_new_round(
        self,
        session: DeliberationSession,
        vote_distribution: dict[str, int],
    ) -> tuple[DeliberationSession, CrossExamineRoundTriggeredEvent]:
        """Trigger a new CROSS_EXAMINE round after no consensus.

        Args:
            session: Current session in VOTE phase.
            vote_distribution: Vote split from failed consensus.

        Returns:
            Tuple of (session in CROSS_EXAMINE with round+1, event).

        Raises:
            SessionAlreadyCompleteError: If session is already complete.
        """
        from src.domain.errors.deliberation import SessionAlreadyCompleteError

        if session.phase.is_terminal():
            raise SessionAlreadyCompleteError(
                session_id=str(session.session_id),
                message="Cannot start new round on completed session",
            )

        # Transition to new round (clears votes, returns to CROSS_EXAMINE)
        updated_session = session.with_new_round(vote_distribution)

        # Create event for new round
        event = CrossExamineRoundTriggeredEvent(
            event_id=uuid7(),
            session_id=session.session_id,
            petition_id=session.petition_id,
            round_number=updated_session.round_count,
            previous_vote_distribution=vote_distribution,
            participating_archons=session.assigned_archons,
        )

        # Track new round
        self._new_rounds.append((session.session_id, updated_session.round_count))
        self._events_emitted.append(event)

        # Store updated session
        self._sessions[session.session_id] = updated_session

        return updated_session, event

    async def trigger_deadlock_escalation(
        self,
        session: DeliberationSession,
        vote_distribution: dict[str, int],
    ) -> tuple[DeliberationSession, DeadlockDetectedEvent]:
        """Trigger deadlock escalation after max rounds exceeded (FR-11.10).

        Args:
            session: Current session at max rounds.
            vote_distribution: Final vote split.

        Returns:
            Tuple of (session with ESCALATE and is_deadlocked=True, event).

        Raises:
            SessionAlreadyCompleteError: If session is already complete.
        """
        from src.domain.errors.deliberation import SessionAlreadyCompleteError

        if session.phase.is_terminal():
            raise SessionAlreadyCompleteError(
                session_id=str(session.session_id),
                message="Cannot apply deadlock outcome to completed session",
            )

        # Apply deadlock outcome
        updated_session = session.with_deadlock_outcome(vote_distribution)

        # Collect all vote distributions including final
        all_votes_by_round = session.votes_by_round + (vote_distribution,)

        # Create deadlock event
        event = DeadlockDetectedEvent(
            event_id=uuid7(),
            session_id=session.session_id,
            petition_id=session.petition_id,
            round_count=session.round_count,
            votes_by_round=all_votes_by_round,
            final_vote_distribution=vote_distribution,
            phase_at_deadlock=session.phase,
            participating_archons=session.assigned_archons,
        )

        # Track deadlock
        self._deadlocks.add(session.session_id)
        self._events_emitted.append(event)

        # Store updated session
        self._sessions[session.session_id] = updated_session

        return updated_session, event

    async def get_deadlock_status(
        self,
        session_id: UUID,
    ) -> tuple[bool, int, int]:
        """Get deadlock tracking status for a session.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            Tuple of (is_deadlocked, current_round, max_rounds).

        Raises:
            SessionNotFoundError: If session doesn't exist.
        """
        from src.domain.errors.deliberation import SessionNotFoundError

        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(
                session_id=str(session_id),
                message=f"Session {session_id} not found for deadlock status",
            )

        return (
            session.is_deadlocked,
            session.round_count,
            self._config.max_rounds,
        )

    async def get_vote_history(
        self,
        session_id: UUID,
    ) -> tuple[dict[str, int], ...]:
        """Get vote distribution history for all rounds.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            Tuple of vote distributions from each completed round.

        Raises:
            SessionNotFoundError: If session doesn't exist.
        """
        from src.domain.errors.deliberation import SessionNotFoundError

        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(
                session_id=str(session_id),
                message=f"Session {session_id} not found for vote history",
            )

        return session.votes_by_round

    # Test helper methods

    def clear(self) -> None:
        """Clear all sessions and deadlock state (for testing)."""
        self._sessions.clear()
        self._deadlocks.clear()
        self._new_rounds.clear()
        self._events_emitted.clear()

    def get_session(self, session_id: UUID) -> DeliberationSession | None:
        """Get a session by ID (for testing).

        Args:
            session_id: UUID of the session.

        Returns:
            DeliberationSession if found, None otherwise.
        """
        return self._sessions.get(session_id)

    def get_deadlocks(self) -> set[UUID]:
        """Get set of session IDs where deadlock was detected (for testing).

        Returns:
            Set of session UUIDs.
        """
        return self._deadlocks.copy()

    def get_new_rounds(self) -> list[tuple[UUID, int]]:
        """Get list of (session_id, round_number) for triggered rounds.

        Returns:
            List of tuples.
        """
        return self._new_rounds.copy()

    def get_emitted_events(
        self,
    ) -> list[CrossExamineRoundTriggeredEvent | DeadlockDetectedEvent]:
        """Get list of emitted events (for testing).

        Returns:
            List of event instances.
        """
        return self._events_emitted.copy()

    @property
    def max_rounds(self) -> int:
        """Get configured maximum rounds before deadlock.

        Returns:
            Maximum rounds allowed.
        """
        return self._config.max_rounds
