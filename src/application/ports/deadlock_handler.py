"""Deadlock handler protocol (Story 2B.3, FR-11.10).

This module defines the protocol for deliberation deadlock detection and handling.
Deadlock occurs when 3 consecutive voting rounds produce no supermajority (1-1-1 splits).

Constitutional Constraints:
- FR-11.10: System SHALL auto-ESCALATE after 3 rounds without supermajority (deadlock)
- CT-11: Silent failure destroys legitimacy - deadlock MUST terminate
- CT-14: Silence is expensive - every petition terminates in witnessed fate
- AT-1: Every petition terminates in exactly one of Three Fates
- AT-6: Deliberation is collective judgment - deadlock is collective conclusion
- NFR-10.3: Consensus determinism - 100% reproducible
- NFR-10.4: 100% witness completeness
- NFR-6.5: Audit trail completeness - complete reconstruction possible
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.events.deadlock import (
    CrossExamineRoundTriggeredEvent,
    DeadlockDetectedEvent,
)
from src.domain.models.deliberation_session import DeliberationSession


class DeadlockHandlerProtocol(Protocol):
    """Protocol for deliberation deadlock handling (Story 2B.3, FR-11.10).

    Implementations detect deadlock conditions (3 consecutive 1-1-1 votes)
    and handle the transition to another round or auto-ESCALATE.

    Constitutional Constraints:
    - FR-11.10: Auto-ESCALATE after 3 rounds without supermajority
    - CT-11: Deadlock MUST terminate (no silent failures)
    - AT-1: Every petition terminates in one of Three Fates
    - NFR-10.3: Consensus determinism
    """

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
        ...

    def can_continue_deliberation(
        self,
        session: DeliberationSession,
        max_rounds: int,
    ) -> bool:
        """Check if deliberation can continue with another round.

        Args:
            session: Current deliberation session.
            max_rounds: Maximum allowed rounds before deadlock (default: 3).

        Returns:
            True if round_count < max_rounds, False if deadlock imminent.
        """
        ...

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

        This is the main entry point for deadlock detection. When called
        after a VOTE phase with no supermajority:

        1. If round_count < max_rounds: return to CROSS_EXAMINE for another round
           - Emit CrossExamineRoundTriggeredEvent
           - Increment round_count
        2. If round_count >= max_rounds: deadlock detected, auto-ESCALATE
           - Emit DeadlockDetectedEvent
           - Set outcome=ESCALATE, is_deadlocked=True

        Args:
            session: The deliberation session with failed consensus.
            vote_distribution: The vote split from the current round.
            max_rounds: Maximum rounds allowed (from config, default: 3).

        Returns:
            Tuple of (updated session, event emitted).
            Event is CrossExamineRoundTriggeredEvent for retry,
            or DeadlockDetectedEvent for final deadlock.

        Raises:
            SessionAlreadyCompleteError: If session is already complete.
            ValueError: If vote_distribution is not a valid deadlock pattern.
        """
        ...

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
        ...

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
        ...

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
        ...

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
        ...
