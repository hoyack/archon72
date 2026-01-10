"""Unit tests for UnanimousVotePayload domain type (Story 2.4, FR12).

Tests the UnanimousVotePayload frozen dataclass and VoteOutcome enum
for tracking unanimous vote events in the governance system.

Test categories:
- VoteOutcome enum validation
- UnanimousVotePayload creation and validation
- Unanimity constraint enforcement
- Serialization to dict
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.collective_output import VoteCounts
from src.domain.events.unanimous_vote import (
    UNANIMOUS_VOTE_EVENT_TYPE,
    UnanimousVotePayload,
    VoteOutcome,
)


class TestVoteOutcome:
    """Tests for VoteOutcome enum."""

    def test_yes_unanimous_value(self) -> None:
        """VoteOutcome.YES_UNANIMOUS has correct string value."""
        assert VoteOutcome.YES_UNANIMOUS.value == "yes_unanimous"

    def test_no_unanimous_value(self) -> None:
        """VoteOutcome.NO_UNANIMOUS has correct string value."""
        assert VoteOutcome.NO_UNANIMOUS.value == "no_unanimous"

    def test_abstain_unanimous_value(self) -> None:
        """VoteOutcome.ABSTAIN_UNANIMOUS has correct string value."""
        assert VoteOutcome.ABSTAIN_UNANIMOUS.value == "abstain_unanimous"

    def test_enum_has_exactly_three_members(self) -> None:
        """VoteOutcome has exactly three members."""
        assert len(VoteOutcome) == 3


class TestUnanimousVoteEventType:
    """Tests for event type constant."""

    def test_event_type_follows_convention(self) -> None:
        """Event type follows lowercase.dot.notation convention."""
        assert UNANIMOUS_VOTE_EVENT_TYPE == "vote.unanimous"


class TestUnanimousVotePayload:
    """Tests for UnanimousVotePayload dataclass."""

    def test_valid_yes_unanimous_payload(self) -> None:
        """Valid YES_UNANIMOUS payload is created successfully."""
        vote_id = uuid4()
        output_id = uuid4()
        recorded_at = datetime.now(timezone.utc)

        payload = UnanimousVotePayload(
            vote_id=vote_id,
            output_id=output_id,
            vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
            outcome=VoteOutcome.YES_UNANIMOUS,
            voter_count=72,
            recorded_at=recorded_at,
        )

        assert payload.vote_id == vote_id
        assert payload.output_id == output_id
        assert payload.vote_counts.yes_count == 72
        assert payload.outcome == VoteOutcome.YES_UNANIMOUS
        assert payload.voter_count == 72
        assert payload.recorded_at == recorded_at

    def test_valid_no_unanimous_payload(self) -> None:
        """Valid NO_UNANIMOUS payload is created successfully."""
        payload = UnanimousVotePayload(
            vote_id=uuid4(),
            output_id=uuid4(),
            vote_counts=VoteCounts(yes_count=0, no_count=72, abstain_count=0),
            outcome=VoteOutcome.NO_UNANIMOUS,
            voter_count=72,
            recorded_at=datetime.now(timezone.utc),
        )

        assert payload.outcome == VoteOutcome.NO_UNANIMOUS
        assert payload.vote_counts.no_count == 72

    def test_valid_abstain_unanimous_payload(self) -> None:
        """Valid ABSTAIN_UNANIMOUS payload is created successfully."""
        payload = UnanimousVotePayload(
            vote_id=uuid4(),
            output_id=uuid4(),
            vote_counts=VoteCounts(yes_count=0, no_count=0, abstain_count=72),
            outcome=VoteOutcome.ABSTAIN_UNANIMOUS,
            voter_count=72,
            recorded_at=datetime.now(timezone.utc),
        )

        assert payload.outcome == VoteOutcome.ABSTAIN_UNANIMOUS
        assert payload.vote_counts.abstain_count == 72

    def test_payload_is_frozen(self) -> None:
        """UnanimousVotePayload is immutable (frozen dataclass)."""
        payload = UnanimousVotePayload(
            vote_id=uuid4(),
            output_id=uuid4(),
            vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
            outcome=VoteOutcome.YES_UNANIMOUS,
            voter_count=72,
            recorded_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            payload.voter_count = 100  # type: ignore[misc]

    def test_rejects_non_unanimous_vote_counts_for_yes(self) -> None:
        """Rejects YES_UNANIMOUS when vote is not actually unanimous."""
        with pytest.raises(ValueError, match="not unanimous"):
            UnanimousVotePayload(
                vote_id=uuid4(),
                output_id=uuid4(),
                vote_counts=VoteCounts(yes_count=70, no_count=2, abstain_count=0),
                outcome=VoteOutcome.YES_UNANIMOUS,
                voter_count=72,
                recorded_at=datetime.now(timezone.utc),
            )

    def test_rejects_mismatched_outcome_and_counts(self) -> None:
        """Rejects when outcome doesn't match the actual unanimous direction."""
        with pytest.raises(ValueError, match="outcome.*mismatch"):
            UnanimousVotePayload(
                vote_id=uuid4(),
                output_id=uuid4(),
                vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
                outcome=VoteOutcome.NO_UNANIMOUS,  # Wrong outcome
                voter_count=72,
                recorded_at=datetime.now(timezone.utc),
            )

    def test_rejects_voter_count_not_matching_total(self) -> None:
        """Rejects when voter_count doesn't match vote_counts.total."""
        with pytest.raises(ValueError, match="voter_count.*must equal"):
            UnanimousVotePayload(
                vote_id=uuid4(),
                output_id=uuid4(),
                vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
                outcome=VoteOutcome.YES_UNANIMOUS,
                voter_count=50,  # Doesn't match total
                recorded_at=datetime.now(timezone.utc),
            )

    def test_rejects_non_uuid_vote_id(self) -> None:
        """Rejects non-UUID vote_id."""
        with pytest.raises(TypeError, match="vote_id must be UUID"):
            UnanimousVotePayload(
                vote_id="not-a-uuid",  # type: ignore[arg-type]
                output_id=uuid4(),
                vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
                outcome=VoteOutcome.YES_UNANIMOUS,
                voter_count=72,
                recorded_at=datetime.now(timezone.utc),
            )

    def test_rejects_non_uuid_output_id(self) -> None:
        """Rejects non-UUID output_id."""
        with pytest.raises(TypeError, match="output_id must be UUID"):
            UnanimousVotePayload(
                vote_id=uuid4(),
                output_id="not-a-uuid",  # type: ignore[arg-type]
                vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
                outcome=VoteOutcome.YES_UNANIMOUS,
                voter_count=72,
                recorded_at=datetime.now(timezone.utc),
            )

    def test_to_dict_serialization(self) -> None:
        """to_dict() produces correct dictionary structure."""
        vote_id = uuid4()
        output_id = uuid4()
        recorded_at = datetime.now(timezone.utc)

        payload = UnanimousVotePayload(
            vote_id=vote_id,
            output_id=output_id,
            vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
            outcome=VoteOutcome.YES_UNANIMOUS,
            voter_count=72,
            recorded_at=recorded_at,
        )

        result = payload.to_dict()

        assert result["vote_id"] == str(vote_id)
        assert result["output_id"] == str(output_id)
        assert result["vote_counts"]["yes_count"] == 72
        assert result["vote_counts"]["no_count"] == 0
        assert result["vote_counts"]["abstain_count"] == 0
        assert result["outcome"] == "yes_unanimous"
        assert result["voter_count"] == 72
        assert result["recorded_at"] == recorded_at.isoformat()

    def test_small_unanimous_vote_accepted(self) -> None:
        """Unanimous vote with small voter count is accepted."""
        payload = UnanimousVotePayload(
            vote_id=uuid4(),
            output_id=uuid4(),
            vote_counts=VoteCounts(yes_count=2, no_count=0, abstain_count=0),
            outcome=VoteOutcome.YES_UNANIMOUS,
            voter_count=2,
            recorded_at=datetime.now(timezone.utc),
        )

        assert payload.voter_count == 2
        assert payload.vote_counts.total == 2
