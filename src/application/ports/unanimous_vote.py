"""Unanimous vote port interface (Story 2.4, FR12).

Defines the UnanimousVotePort Protocol for storing unanimous vote events.
FR12 requires special tracking of unanimous votes as they indicate
0% dissent (potential groupthink indicator).

Constitutional Constraints:
- FR12: Dissent percentages visible in every vote tally
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.domain.events.unanimous_vote import UnanimousVotePayload, VoteOutcome


@dataclass(frozen=True, eq=True)
class StoredUnanimousVote:
    """Result of storing a unanimous vote event.

    Attributes:
        vote_id: UUID of the unanimous vote.
        output_id: UUID of the collective output.
        outcome: Direction of the unanimous vote.
        voter_count: Number of voters.
        event_sequence: Sequence number in event store (if applicable).
        stored_at: UTC timestamp when stored.
    """

    vote_id: UUID
    output_id: UUID
    outcome: VoteOutcome
    voter_count: int
    event_sequence: int
    stored_at: datetime


class UnanimousVotePort(Protocol):
    """Port for unanimous vote event storage (FR12).

    Protocol defining the interface for storing and retrieving
    unanimous vote events. Unanimous votes (0% dissent) get special
    tracking for groupthink detection.

    Methods:
        store_unanimous_vote: Store a unanimous vote event.
        get_unanimous_vote: Retrieve a unanimous vote by vote_id.
        get_unanimous_votes_for_output: Get unanimous votes for an output.
    """

    async def store_unanimous_vote(
        self,
        payload: UnanimousVotePayload,
    ) -> StoredUnanimousVote:
        """Store a unanimous vote event.

        Args:
            payload: The unanimous vote payload to store.

        Returns:
            StoredUnanimousVote with storage metadata.
        """
        ...

    async def get_unanimous_vote(
        self,
        vote_id: UUID,
    ) -> UnanimousVotePayload | None:
        """Retrieve a unanimous vote by ID.

        Args:
            vote_id: UUID of the unanimous vote.

        Returns:
            UnanimousVotePayload if found, None otherwise.
        """
        ...

    async def get_unanimous_votes_for_output(
        self,
        output_id: UUID,
    ) -> list[UnanimousVotePayload]:
        """Get all unanimous votes for a collective output.

        Args:
            output_id: UUID of the collective output.

        Returns:
            List of UnanimousVotePayload objects.
        """
        ...
