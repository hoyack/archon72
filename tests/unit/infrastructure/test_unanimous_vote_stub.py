"""Unit tests for UnanimousVoteStub (Story 2.4, FR12).

Tests the in-memory stub implementation for UnanimousVotePort.

Test categories:
- DEV_MODE_WATERMARK pattern
- store_unanimous_vote method
- get_unanimous_vote method
- get_unanimous_votes_for_output method
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.collective_output import VoteCounts
from src.domain.events.unanimous_vote import UnanimousVotePayload, VoteOutcome
from src.infrastructure.stubs.unanimous_vote_stub import (
    DEV_MODE_WATERMARK,
    UnanimousVoteStub,
)


class TestDevModeWatermark:
    """Tests for DEV_MODE_WATERMARK pattern."""

    def test_dev_mode_watermark_exists(self) -> None:
        """DEV_MODE_WATERMARK constant exists."""
        assert DEV_MODE_WATERMARK is not None

    def test_dev_mode_watermark_is_string(self) -> None:
        """DEV_MODE_WATERMARK is a string."""
        assert isinstance(DEV_MODE_WATERMARK, str)


class TestUnanimousVoteStub:
    """Tests for UnanimousVoteStub implementation."""

    @pytest.fixture
    def stub(self) -> UnanimousVoteStub:
        return UnanimousVoteStub()

    @pytest.fixture
    def yes_unanimous_payload(self) -> UnanimousVotePayload:
        return UnanimousVotePayload(
            vote_id=uuid4(),
            output_id=uuid4(),
            vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
            outcome=VoteOutcome.YES_UNANIMOUS,
            voter_count=72,
            recorded_at=datetime.now(timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_store_unanimous_vote(
        self,
        stub: UnanimousVoteStub,
        yes_unanimous_payload: UnanimousVotePayload,
    ) -> None:
        """store_unanimous_vote stores vote in memory."""
        result = await stub.store_unanimous_vote(yes_unanimous_payload)

        assert result.vote_id == yes_unanimous_payload.vote_id
        assert result.output_id == yes_unanimous_payload.output_id
        assert result.outcome == VoteOutcome.YES_UNANIMOUS
        assert result.voter_count == 72
        assert result.event_sequence == 1

    @pytest.mark.asyncio
    async def test_store_unanimous_vote_auto_increments_sequence(
        self,
        stub: UnanimousVoteStub,
    ) -> None:
        """store_unanimous_vote auto-increments sequence number."""
        payload1 = UnanimousVotePayload(
            vote_id=uuid4(),
            output_id=uuid4(),
            vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
            outcome=VoteOutcome.YES_UNANIMOUS,
            voter_count=72,
            recorded_at=datetime.now(timezone.utc),
        )
        payload2 = UnanimousVotePayload(
            vote_id=uuid4(),
            output_id=uuid4(),
            vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
            outcome=VoteOutcome.YES_UNANIMOUS,
            voter_count=72,
            recorded_at=datetime.now(timezone.utc),
        )

        result1 = await stub.store_unanimous_vote(payload1)
        result2 = await stub.store_unanimous_vote(payload2)

        assert result1.event_sequence == 1
        assert result2.event_sequence == 2

    @pytest.mark.asyncio
    async def test_get_unanimous_vote_found(
        self,
        stub: UnanimousVoteStub,
        yes_unanimous_payload: UnanimousVotePayload,
    ) -> None:
        """get_unanimous_vote returns stored vote."""
        await stub.store_unanimous_vote(yes_unanimous_payload)

        result = await stub.get_unanimous_vote(yes_unanimous_payload.vote_id)

        assert result is not None
        assert result.vote_id == yes_unanimous_payload.vote_id

    @pytest.mark.asyncio
    async def test_get_unanimous_vote_not_found(
        self,
        stub: UnanimousVoteStub,
    ) -> None:
        """get_unanimous_vote returns None for unknown vote_id."""
        result = await stub.get_unanimous_vote(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_unanimous_votes_for_output(
        self,
        stub: UnanimousVoteStub,
    ) -> None:
        """get_unanimous_votes_for_output returns votes for specific output."""
        output_id = uuid4()
        other_output_id = uuid4()

        payload1 = UnanimousVotePayload(
            vote_id=uuid4(),
            output_id=output_id,
            vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
            outcome=VoteOutcome.YES_UNANIMOUS,
            voter_count=72,
            recorded_at=datetime.now(timezone.utc),
        )
        payload2 = UnanimousVotePayload(
            vote_id=uuid4(),
            output_id=other_output_id,  # Different output
            vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
            outcome=VoteOutcome.YES_UNANIMOUS,
            voter_count=72,
            recorded_at=datetime.now(timezone.utc),
        )

        await stub.store_unanimous_vote(payload1)
        await stub.store_unanimous_vote(payload2)

        results = await stub.get_unanimous_votes_for_output(output_id)

        assert len(results) == 1
        assert results[0].output_id == output_id

    @pytest.mark.asyncio
    async def test_get_unanimous_votes_for_output_empty(
        self,
        stub: UnanimousVoteStub,
    ) -> None:
        """get_unanimous_votes_for_output returns empty list when none found."""
        results = await stub.get_unanimous_votes_for_output(uuid4())
        assert results == []
