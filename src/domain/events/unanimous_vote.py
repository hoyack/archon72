"""Unanimous vote event types (Story 2.4, FR12).

This module defines the UnanimousVotePayload and VoteOutcome types
for recording unanimous vote events. FR12 requires tracking dissent
percentages, and unanimous votes (0% dissent) get special handling.

Constitutional Constraints:
- FR12: Dissent percentages visible in every vote tally
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
- CT-13: Integrity outranks availability

A UnanimousVoteEvent is created when a vote has 100% agreement
(all YES, all NO, or all ABSTAIN).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from src.domain.events.collective_output import VoteCounts

# Event type constant following lowercase.dot.notation convention
UNANIMOUS_VOTE_EVENT_TYPE: str = "vote.unanimous"


class VoteOutcome(Enum):
    """Outcome of a unanimous vote (FR12).

    Represents the direction of a unanimous vote, where all voters
    agreed on the same option.

    Values:
        YES_UNANIMOUS: All voters voted YES
        NO_UNANIMOUS: All voters voted NO
        ABSTAIN_UNANIMOUS: All voters abstained
    """

    YES_UNANIMOUS = "yes_unanimous"
    NO_UNANIMOUS = "no_unanimous"
    ABSTAIN_UNANIMOUS = "abstain_unanimous"


@dataclass(frozen=True, eq=True)
class UnanimousVotePayload:
    """Payload for unanimous vote events (FR12).

    Records a vote where 100% of participants agreed on the same option.
    This is a special event separate from standard vote events, used
    to track potential groupthink patterns.

    Attributes:
        vote_id: UUID linking to the original vote event.
        output_id: UUID linking to the collective output.
        vote_counts: Breakdown of votes (reused from collective_output).
        outcome: Direction of the unanimous vote.
        voter_count: Total number of voters (must equal vote_counts.total).
        recorded_at: UTC timestamp when the unanimous vote was recorded.

    Constitutional Constraints:
        - Vote must actually be unanimous (all same type)
        - outcome must match the actual vote direction
        - voter_count must match vote_counts.total

    Example:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> payload = UnanimousVotePayload(
        ...     vote_id=uuid4(),
        ...     output_id=uuid4(),
        ...     vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
        ...     outcome=VoteOutcome.YES_UNANIMOUS,
        ...     voter_count=72,
        ...     recorded_at=datetime.now(timezone.utc),
        ... )
    """

    vote_id: UUID
    output_id: UUID
    vote_counts: VoteCounts
    outcome: VoteOutcome
    voter_count: int
    recorded_at: datetime

    def __post_init__(self) -> None:
        """Validate payload fields for FR12 compliance.

        Raises:
            TypeError: If vote_id or output_id is not a UUID.
            ValueError: If unanimity constraints are violated.
        """
        self._validate_vote_id()
        self._validate_output_id()
        self._validate_voter_count()
        self._validate_unanimity()
        self._validate_outcome_matches_counts()

    def _validate_vote_id(self) -> None:
        """Validate vote_id is a UUID."""
        if not isinstance(self.vote_id, UUID):
            raise TypeError(f"vote_id must be UUID, got {type(self.vote_id).__name__}")

    def _validate_output_id(self) -> None:
        """Validate output_id is a UUID."""
        if not isinstance(self.output_id, UUID):
            raise TypeError(
                f"output_id must be UUID, got {type(self.output_id).__name__}"
            )

    def _validate_voter_count(self) -> None:
        """Validate voter_count matches vote_counts.total."""
        if self.voter_count != self.vote_counts.total:
            raise ValueError(
                f"voter_count ({self.voter_count}) must equal "
                f"vote_counts.total ({self.vote_counts.total})"
            )

    def _validate_unanimity(self) -> None:
        """Validate that the vote is actually unanimous.

        A vote is unanimous if all votes are for the same option
        (100% yes, 100% no, or 100% abstain).
        """
        total = self.vote_counts.total
        if total == 0:
            return  # Edge case: empty vote is considered unanimous

        majority = max(
            self.vote_counts.yes_count,
            self.vote_counts.no_count,
            self.vote_counts.abstain_count,
        )

        if majority != total:
            raise ValueError(
                f"Vote is not unanimous - "
                f"expected all votes for same option, but got "
                f"yes={self.vote_counts.yes_count}, "
                f"no={self.vote_counts.no_count}, "
                f"abstain={self.vote_counts.abstain_count}"
            )

    def _validate_outcome_matches_counts(self) -> None:
        """Validate that outcome matches the actual vote direction."""
        expected_outcome = self._determine_expected_outcome()

        if self.outcome != expected_outcome:
            raise ValueError(
                f"outcome mismatch - expected {expected_outcome.value} "
                f"based on vote counts, got {self.outcome.value}"
            )

    def _determine_expected_outcome(self) -> VoteOutcome:
        """Determine the expected outcome based on vote counts."""
        if self.vote_counts.yes_count == self.vote_counts.total:
            return VoteOutcome.YES_UNANIMOUS
        elif self.vote_counts.no_count == self.vote_counts.total:
            return VoteOutcome.NO_UNANIMOUS
        else:
            return VoteOutcome.ABSTAIN_UNANIMOUS

    def to_dict(self) -> dict[str, object]:
        """Convert payload to dictionary for event serialization.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        return {
            "vote_id": str(self.vote_id),
            "output_id": str(self.output_id),
            "vote_counts": self.vote_counts.to_dict(),
            "outcome": self.outcome.value,
            "voter_count": self.voter_count,
            "recorded_at": self.recorded_at.isoformat(),
        }
