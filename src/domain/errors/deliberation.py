"""Deliberation domain errors (Story 2A.1, FR-11.1, FR-11.4).

This module defines domain-specific exceptions for the Three Fates
deliberation system. All errors inherit from ConclaveError and include
constitutional references where applicable.

Constitutional Constraints:
- D7: All errors include trace_id and constitutional references
- CT-14: Silence is expensive - errors must be clear and actionable
- AT-6: Deliberation is collective judgment - consensus errors are domain errors
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.exceptions import ConclaveError

if TYPE_CHECKING:
    from src.domain.models.deliberation_session import DeliberationPhase


class DeliberationError(ConclaveError):
    """Base class for deliberation-related errors."""

    pass


class InvalidPhaseTransitionError(DeliberationError):
    """Raised when attempting invalid phase transition (FR-11.4).

    The deliberation protocol requires strict phase progression:
    ASSESS -> POSITION -> CROSS_EXAMINE -> VOTE -> COMPLETE

    Skipping phases or going backwards is not permitted.

    Attributes:
        from_phase: Current phase.
        to_phase: Attempted target phase.
        expected_phase: The expected next phase in sequence.
    """

    def __init__(
        self,
        from_phase: DeliberationPhase,
        to_phase: DeliberationPhase,
        expected_phase: DeliberationPhase | None,
    ) -> None:
        """Initialize InvalidPhaseTransitionError.

        Args:
            from_phase: Current phase.
            to_phase: Attempted target phase.
            expected_phase: The expected next phase (None if terminal).
        """
        self.from_phase = from_phase
        self.to_phase = to_phase
        self.expected_phase = expected_phase

        expected_str = expected_phase.value if expected_phase else "None (terminal)"
        message = (
            f"Invalid phase transition from {from_phase.value} to {to_phase.value}. "
            f"Expected next phase: {expected_str}. "
            "Deliberation protocol requires strict sequence: "
            "ASSESS -> POSITION -> CROSS_EXAMINE -> VOTE -> COMPLETE (FR-11.4)"
        )
        super().__init__(message)


class ConsensusNotReachedError(DeliberationError):
    """Raised when setting outcome without 2-of-3 consensus (AT-6).

    Constitutional Truth AT-6: "Deliberation is collective judgment,
    not unilateral decision." This requires 2-of-3 supermajority
    for any outcome to be valid.

    Attributes:
        votes_received: Number of votes received.
        votes_required: Number of votes required.
        message: Descriptive error message.
    """

    def __init__(
        self,
        message: str,
        votes_received: int,
        votes_required: int,
    ) -> None:
        """Initialize ConsensusNotReachedError.

        Args:
            message: Descriptive error message.
            votes_received: Number of votes received.
            votes_required: Number of votes required for consensus.
        """
        self.votes_received = votes_received
        self.votes_required = votes_required

        full_message = (
            f"{message} "
            f"(votes_received={votes_received}, votes_required={votes_required}). "
            "Constitutional Truth AT-6: Deliberation is collective judgment."
        )
        super().__init__(full_message)


class SessionAlreadyCompleteError(DeliberationError):
    """Raised when modifying a completed session (AC-6).

    Once a deliberation session reaches COMPLETE phase, it becomes
    immutable. This preserves the integrity of the witnessed record.

    Attributes:
        session_id: ID of the completed session.
        message: Descriptive error message.
    """

    def __init__(
        self,
        session_id: str,
        message: str,
    ) -> None:
        """Initialize SessionAlreadyCompleteError.

        Args:
            session_id: ID of the completed session.
            message: Descriptive error message.
        """
        self.session_id = session_id

        full_message = (
            f"Session {session_id}: {message}. "
            "Completed sessions are immutable to preserve witness integrity (CT-12)."
        )
        super().__init__(full_message)


class InvalidArchonAssignmentError(DeliberationError):
    """Raised when archon assignment violates invariants (FR-11.1).

    FR-11.1 requires exactly 3 Marquis-rank Archons to be assigned
    to each deliberation. This error is raised when:
    - Fewer or more than 3 archons are assigned
    - Duplicate archon IDs are provided
    - An archon not in the assigned set attempts to vote

    Attributes:
        message: Descriptive error message.
        archon_count: Number of archons provided (if applicable).
    """

    def __init__(
        self,
        message: str,
        archon_count: int | None = None,
    ) -> None:
        """Initialize InvalidArchonAssignmentError.

        Args:
            message: Descriptive error message.
            archon_count: Number of archons provided.
        """
        self.archon_count = archon_count

        full_message = (
            f"{message}. "
            "FR-11.1: System SHALL assign exactly 3 Marquis-rank Archons."
        )
        super().__init__(full_message)
