"""Domain errors for vote reconciliation.

Story 4.1: Implement Reconciliation Service
Pre-mortems: P2 (Hard gate - raises error, NOT a warning)

These errors are raised when reconciliation fails and MUST NOT
be caught by the application (per P2). They cause the session
to HALT, which is the desired behavior for data integrity.
"""

from typing import Any
from uuid import UUID


class ReconciliationError(Exception):
    """Base error for reconciliation failures.

    All reconciliation errors are FATAL - they must not be caught
    and must cause the session to halt (P2).
    """

    def __init__(
        self,
        message: str,
        session_id: UUID | None = None,
        motion_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            message: Error message
            session_id: The session that failed
            motion_id: The motion being reconciled
            details: Additional error details
        """
        super().__init__(message)
        self.session_id = session_id
        self.motion_id = motion_id
        self.details = details or {}


class ReconciliationIncompleteError(ReconciliationError):
    """Raised when reconciliation times out with pending votes (P1, P2).

    This error indicates that not all votes could be validated before
    the timeout expired. The session MUST halt to prevent data loss.

    Per P2: This is a HARD ERROR, not a warning. It propagates up
    and causes the session to halt.
    """

    def __init__(
        self,
        session_id: UUID,
        motion_id: UUID,
        pending_count: int,
        consumer_lag: int,
        dlq_count: int,
        timeout_seconds: float,
    ) -> None:
        """Initialize the error.

        Args:
            session_id: The session that failed
            motion_id: The motion being reconciled
            pending_count: Number of votes still pending
            consumer_lag: Current consumer lag
            dlq_count: Number of votes in DLQ
            timeout_seconds: How long we waited
        """
        message = (
            f"Reconciliation incomplete after {timeout_seconds}s: "
            f"pending={pending_count}, lag={consumer_lag}, dlq={dlq_count}. "
            f"Session MUST halt to prevent data loss."
        )
        super().__init__(
            message=message,
            session_id=session_id,
            motion_id=motion_id,
            details={
                "pending_count": pending_count,
                "consumer_lag": consumer_lag,
                "dlq_count": dlq_count,
                "timeout_seconds": timeout_seconds,
            },
        )
        self.pending_count = pending_count
        self.consumer_lag = consumer_lag
        self.dlq_count = dlq_count
        self.timeout_seconds = timeout_seconds


class ReconciliationLagError(ReconciliationError):
    """Raised when consumer lag is non-zero at adjournment (R3).

    Per R3: Consumer lag MUST be zero before session can adjourn.
    Non-zero lag means there are unprocessed validation results.
    """

    def __init__(
        self,
        session_id: UUID,
        motion_id: UUID,
        consumer_lag: int,
    ) -> None:
        """Initialize the error.

        Args:
            session_id: The session that failed
            motion_id: The motion being reconciled
            consumer_lag: Current consumer lag
        """
        message = (
            f"Consumer lag is {consumer_lag}, must be 0 for adjournment (R3). "
            f"Session MUST halt until all validations are processed."
        )
        super().__init__(
            message=message,
            session_id=session_id,
            motion_id=motion_id,
            details={"consumer_lag": consumer_lag},
        )
        self.consumer_lag = consumer_lag


class VoteOverrideError(ReconciliationError):
    """Raised when vote override fails.

    This can occur if the validated choice is invalid or if
    tally recomputation fails invariant checks (P6).
    """

    def __init__(
        self,
        session_id: UUID,
        motion_id: UUID,
        vote_id: UUID,
        reason: str,
    ) -> None:
        """Initialize the error.

        Args:
            session_id: The session that failed
            motion_id: The motion being reconciled
            vote_id: The vote that failed override
            reason: Why the override failed
        """
        message = f"Vote override failed for {vote_id}: {reason}"
        super().__init__(
            message=message,
            session_id=session_id,
            motion_id=motion_id,
            details={"vote_id": str(vote_id), "reason": reason},
        )
        self.vote_id = vote_id
        self.reason = reason


class TallyInvariantError(ReconciliationError):
    """Raised when tally invariant check fails (P6).

    Per P6: ayes + nays + abstains MUST equal len(votes).
    If this invariant is violated, there's a data integrity issue.
    """

    def __init__(
        self,
        session_id: UUID,
        motion_id: UUID,
        ayes: int,
        nays: int,
        abstains: int,
        total_votes: int,
    ) -> None:
        """Initialize the error.

        Args:
            session_id: The session that failed
            motion_id: The motion being reconciled
            ayes: Number of aye votes
            nays: Number of nay votes
            abstains: Number of abstain votes
            total_votes: Expected total votes
        """
        tally_sum = ayes + nays + abstains
        message = (
            f"Tally invariant violated (P6): "
            f"ayes({ayes}) + nays({nays}) + abstains({abstains}) = {tally_sum} "
            f"!= total_votes({total_votes})"
        )
        super().__init__(
            message=message,
            session_id=session_id,
            motion_id=motion_id,
            details={
                "ayes": ayes,
                "nays": nays,
                "abstains": abstains,
                "tally_sum": tally_sum,
                "total_votes": total_votes,
            },
        )
        self.ayes = ayes
        self.nays = nays
        self.abstains = abstains
        self.total_votes = total_votes
