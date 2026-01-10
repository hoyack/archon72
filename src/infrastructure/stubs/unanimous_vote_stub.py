"""Unanimous vote stub implementation (Story 2.4, FR12).

In-memory stub for UnanimousVotePort for development and testing.
Follows DEV_MODE_WATERMARK pattern per RT-1/ADR-4.

Constitutional Constraints:
- FR12: Dissent percentages visible in every vote tally
- CT-12: Witnessing creates accountability
- RT-1/ADR-4: DEV_MODE_WATERMARK pattern for dev stubs
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from src.application.ports.unanimous_vote import StoredUnanimousVote
from src.domain.events.unanimous_vote import UnanimousVotePayload

# DEV_MODE_WATERMARK per RT-1/ADR-4
DEV_MODE_WATERMARK: str = "DEV_STUB:UnanimousVoteStub:v1"


class UnanimousVoteStub:
    """In-memory stub for UnanimousVotePort (FR12).

    Development and testing implementation that stores unanimous votes
    in memory. Follows DEV_MODE_WATERMARK pattern.

    WARNING: This is a development stub. Not for production use.

    Attributes:
        _votes: In-memory dict of vote_id -> payload.
        _sequence: Auto-incrementing sequence counter.
    """

    def __init__(self) -> None:
        """Initialize empty unanimous vote store."""
        self._votes: dict[UUID, UnanimousVotePayload] = {}
        self._sequence: int = 0

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
        self._sequence += 1
        self._votes[payload.vote_id] = payload

        return StoredUnanimousVote(
            vote_id=payload.vote_id,
            output_id=payload.output_id,
            outcome=payload.outcome,
            voter_count=payload.voter_count,
            event_sequence=self._sequence,
            stored_at=datetime.now(timezone.utc),
        )

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
        return self._votes.get(vote_id)

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
        return [v for v in self._votes.values() if v.output_id == output_id]
