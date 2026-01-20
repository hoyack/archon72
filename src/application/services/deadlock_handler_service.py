"""Deadlock handler service (Story 2B.3, FR-11.10).

This module implements the DeadlockHandlerProtocol for detecting deliberation
deadlock and handling the transition to another round or auto-ESCALATE.

Constitutional Constraints:
- FR-11.10: System SHALL auto-ESCALATE after 3 rounds without supermajority (deadlock)
- CT-11: Silent failure destroys legitimacy - deadlock MUST terminate
- CT-14: Silence is expensive - every petition terminates in witnessed fate
- AT-1: Every petition terminates in exactly one of Three Fates
- AT-6: Deliberation is collective judgment - deadlock is collective conclusion
- NFR-10.3: Consensus determinism - 100% reproducible
- NFR-10.4: 100% witness completeness
- NFR-6.5: Audit trail completeness - complete reconstruction possible

Usage:
    from src.application.services.deadlock_handler_service import (
        DeadlockHandlerService,
    )
    from src.config.deliberation_config import DEFAULT_DELIBERATION_CONFIG

    service = DeadlockHandlerService(
        event_emitter=emitter,
        config=DEFAULT_DELIBERATION_CONFIG,
    )

    # Check if vote pattern is deadlock (1-1-1)
    is_deadlock = service.is_deadlock_vote_pattern(vote_distribution)

    # Handle no consensus after VOTE phase
    session, event = await service.handle_no_consensus(
        session, vote_distribution, max_rounds=3
    )
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from uuid6 import uuid7

from src.config.deliberation_config import (
    DEFAULT_DELIBERATION_CONFIG,
    DeliberationConfig,
)
from src.domain.events.deadlock import (
    CrossExamineRoundTriggeredEvent,
    DeadlockDetectedEvent,
)
from src.domain.models.deliberation_session import DeliberationSession

if TYPE_CHECKING:
    from src.application.ports.event_store import EventStorePort


class DeadlockHandlerService:
    """Service for deliberation deadlock handling (Story 2B.3, FR-11.10).

    Handles detection of deadlock conditions (3 consecutive 1-1-1 votes)
    and the transition to another CROSS_EXAMINE round or auto-ESCALATE.

    Deadlock Detection Logic:
    - 1-1-1 vote split (all 3 archons vote differently) = potential deadlock
    - 2-1 vote split (2 archons agree) = NOT deadlock (supermajority reached)
    - After max_rounds (default 3) 1-1-1 splits = deadlock → auto-ESCALATE

    Constitutional Constraints:
    - FR-11.10: Auto-ESCALATE after 3 rounds without supermajority
    - CT-11: Deadlock MUST terminate
    - AT-1: Every petition terminates in one of Three Fates
    - NFR-10.3: Consensus determinism

    Attributes:
        _event_emitter: Protocol for emitting events (optional).
        _config: Deliberation configuration.
        _sessions: In-memory session storage (for stub/testing).
    """

    def __init__(
        self,
        event_emitter: EventStorePort | None = None,
        config: DeliberationConfig | None = None,
    ) -> None:
        """Initialize the deadlock handler service.

        Args:
            event_emitter: Protocol for emitting deadlock events (optional).
            config: Deliberation configuration. Uses default if not provided.
        """
        self._event_emitter = event_emitter
        self._config = config or DEFAULT_DELIBERATION_CONFIG
        # In-memory session storage for development/testing
        # Production would use a repository
        self._sessions: dict[UUID, DeliberationSession] = {}

    def _utc_now(self) -> datetime:
        """Return current UTC time with timezone info."""
        return datetime.now(timezone.utc)

    def register_session(self, session: DeliberationSession) -> None:
        """Register a session for deadlock tracking (development helper).

        In production, sessions would be stored in a repository.

        Args:
            session: The session to register.
        """
        self._sessions[session.session_id] = session

    def get_session(self, session_id: UUID) -> DeliberationSession | None:
        """Get a session by ID (development helper).

        Args:
            session_id: UUID of the session.

        Returns:
            DeliberationSession if found, None otherwise.
        """
        return self._sessions.get(session_id)

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
        max_rounds: int | None = None,
    ) -> bool:
        """Check if deliberation can continue with another round.

        Args:
            session: Current deliberation session.
            max_rounds: Maximum allowed rounds before deadlock (default from config).

        Returns:
            True if round_count < max_rounds, False if deadlock imminent.
        """
        if max_rounds is None:
            max_rounds = self._config.max_rounds
        return session.can_retry_cross_examine(max_rounds)

    async def handle_no_consensus(
        self,
        session: DeliberationSession,
        vote_distribution: dict[str, int],
        max_rounds: int | None = None,
    ) -> tuple[
        DeliberationSession,
        CrossExamineRoundTriggeredEvent | DeadlockDetectedEvent,
    ]:
        """Handle a voting round that failed to reach consensus (FR-11.10).

        This is the main entry point for deadlock detection. When called
        after a VOTE phase with no supermajority:

        1. If round_count < max_rounds: return to CROSS_EXAMINE for another round
           - Emit CrossExamineRoundTriggeredEvent
           - Increment round_count
        2. If round_count >= max_rounds: deadlock detected, auto-ESCALATE
           - Emit DeadlockDetectedEvent
           - Set outcome=ESCALATE, is_deadlocked=True

        Constitutional Constraints:
        - FR-11.10: Auto-ESCALATE after max rounds
        - CT-11: Deadlock MUST terminate
        - AT-1: Every petition terminates in one of Three Fates

        Args:
            session: The deliberation session with failed consensus.
            vote_distribution: The vote split from the current round.
            max_rounds: Maximum rounds allowed (from config if not provided).

        Returns:
            Tuple of (updated session, event emitted).
            Event is CrossExamineRoundTriggeredEvent for retry,
            or DeadlockDetectedEvent for final deadlock.

        Raises:
            SessionAlreadyCompleteError: If session is already complete.
            ValueError: If vote_distribution is not a valid deadlock pattern.
        """
        from src.domain.errors.deliberation import SessionAlreadyCompleteError

        if max_rounds is None:
            max_rounds = self._config.max_rounds

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
            # Retry with new round
            return await self.trigger_new_round(session, vote_distribution)
        else:
            # Max rounds reached - deadlock
            return await self.trigger_deadlock_escalation(session, vote_distribution)

    async def trigger_new_round(
        self,
        session: DeliberationSession,
        vote_distribution: dict[str, int],
    ) -> tuple[DeliberationSession, CrossExamineRoundTriggeredEvent]:
        """Trigger a new CROSS_EXAMINE round after no consensus.

        Called when deadlock check passes but consensus not reached.
        Returns session to CROSS_EXAMINE phase with incremented round.

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
            round_number=updated_session.round_count,  # The new round number
            previous_vote_distribution=vote_distribution,
            participating_archons=session.assigned_archons,
        )

        # Emit event if event emitter available
        if self._event_emitter is not None:
            # Note: Actual event store integration would go here
            # await self._event_emitter.append(event.to_dict())
            pass

        # Store updated session
        self._sessions[session.session_id] = updated_session

        return updated_session, event

    async def trigger_deadlock_escalation(
        self,
        session: DeliberationSession,
        vote_distribution: dict[str, int],
    ) -> tuple[DeliberationSession, DeadlockDetectedEvent]:
        """Trigger deadlock escalation after max rounds exceeded (FR-11.10).

        Called when max_rounds reached without consensus.
        Terminates session with ESCALATE outcome.

        Constitutional Constraint (FR-11.10): Auto-ESCALATE is mandatory
        after deadlock to ensure petition terminates.

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

        # Apply deadlock outcome (sets ESCALATE, is_deadlocked=True)
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
            phase_at_deadlock=session.phase,  # Phase BEFORE deadlock
            participating_archons=session.assigned_archons,
        )

        # Emit event if event emitter available
        if self._event_emitter is not None:
            # Note: Actual event store integration would go here
            # await self._event_emitter.append(event.to_dict())
            pass

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

    @property
    def max_rounds(self) -> int:
        """Get configured maximum rounds before deadlock.

        Returns:
            Maximum rounds allowed.
        """
        return self._config.max_rounds
