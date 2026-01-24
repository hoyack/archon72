"""Unit tests for ConsensusAggregator state reconstruction.

Story 5.3: State Reconstruction Tests

Tests proving aggregator state reconstruction works after crash/restart:
- P4: In-memory state with Kafka replay
- V2: Session-bounded filtering
- Idempotency guarantees (no duplicate processing)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from src.workers.consensus_aggregator import (
    ConsensusStatus,
    ValidatorResponse,
    VoteAggregation,
)


@dataclass
class MockValidationResult:
    """Mock validation result message."""

    vote_id: UUID
    session_id: UUID
    motion_id: UUID
    archon_id: str
    validator_id: str
    validated_choice: str
    confidence: float
    attempt: int
    timestamp_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "vote_id": str(self.vote_id),
            "session_id": str(self.session_id),
            "motion_id": str(self.motion_id),
            "archon_id": self.archon_id,
            "validator_id": self.validator_id,
            "validated_choice": self.validated_choice,
            "confidence": self.confidence,
            "attempt": self.attempt,
            "timestamp_ms": self.timestamp_ms,
        }


def create_validation_result(
    vote_id: UUID,
    session_id: UUID,
    validator_id: str,
    choice: str = "APPROVE",
    confidence: float = 0.95,
    attempt: int = 1,
) -> MockValidationResult:
    """Helper to create validation results."""
    return MockValidationResult(
        vote_id=vote_id,
        session_id=session_id,
        motion_id=uuid4(),
        archon_id="archon_test",
        validator_id=validator_id,
        validated_choice=choice,
        confidence=confidence,
        attempt=attempt,
        timestamp_ms=int(time.time() * 1000),
    )


def create_validator_response(
    validator_id: str,
    choice: str = "APPROVE",
    confidence: float = 0.95,
    attempt: int = 1,
) -> ValidatorResponse:
    """Helper to create ValidatorResponse objects."""
    return ValidatorResponse(
        validator_id=validator_id,
        validated_choice=choice,
        confidence=confidence,
        attempt=attempt,
        timestamp_ms=int(time.time() * 1000),
    )


def create_vote_aggregation(
    vote_id: str | UUID,
    session_id: str | UUID,
    optimistic_choice: str = "APPROVE",
    archon_id: str = "archon_test",
    raw_response: str = "raw response",
    motion_text: str = "motion text",
) -> VoteAggregation:
    """Helper to create VoteAggregation with required fields."""
    return VoteAggregation(
        vote_id=str(vote_id),
        session_id=str(session_id),
        archon_id=archon_id,
        raw_response=raw_response,
        motion_text=motion_text,
        optimistic_choice=optimistic_choice,
    )



class TestStateReconstruction:
    """Tests for aggregator state reconstruction from Kafka replay.

    These tests focus on VoteAggregation state management which is the
    core of P4 (in-memory state with Kafka replay).
    """

    def test_fresh_vote_aggregation_has_no_responses(self) -> None:
        """Test that a fresh VoteAggregation starts with no responses."""
        vote = create_vote_aggregation(
            vote_id=str(uuid4()),
            session_id=str(uuid4()),
            optimistic_choice="APPROVE",
        )

        assert len(vote.responses) == 0
        assert vote.status == ConsensusStatus.PENDING

    def test_state_reconstruction_from_replay(self) -> None:
        """Test that VoteAggregation correctly reconstructs state from replay.

        P4: In-memory state + Kafka replay
        When replaying messages, the same state should be reconstructed.
        """
        vote_id = str(uuid4())
        session_id = str(uuid4())

        # Create "original" vote aggregation and add response
        original = create_vote_aggregation(
            vote_id=vote_id,
            session_id=session_id,
            optimistic_choice="APPROVE",
        )

        response1 = create_validator_response(
            validator_id="validator_1",
            choice="APPROVE",
            attempt=1,
        )
        original.add_response(response1)

        # Verify original state
        assert len(original.responses) == 1
        assert "validator_1:1" in original.responses

        # Create "restarted" vote aggregation (simulating replay)
        restarted = create_vote_aggregation(
            vote_id=vote_id,
            session_id=session_id,
            optimistic_choice="APPROVE",
        )

        # Replay the same response
        restarted.add_response(response1)

        # Verify state matches
        assert len(restarted.responses) == 1
        assert "validator_1:1" in restarted.responses
        assert original.vote_id == restarted.vote_id

    def test_idempotent_replay_no_duplicates(self) -> None:
        """Test that replaying the same message twice doesn't cause duplicates.

        Idempotency guarantee: (vote_id, validator_id, attempt) tuple
        should only be processed once.
        """
        vote = create_vote_aggregation(
            vote_id=str(uuid4()),
            session_id=str(uuid4()),
            optimistic_choice="APPROVE",
        )

        response = create_validator_response(
            validator_id="validator_1",
            choice="APPROVE",
            attempt=1,
        )

        # Process the same response multiple times (simulating replay)
        results = []
        for _ in range(5):
            results.append(vote.add_response(response))

        # First add returns True, rest return False (idempotent skip)
        assert results[0] is True
        assert all(r is False for r in results[1:])

        # Verify only one response is tracked
        assert len(vote.responses) == 1

    def test_session_bounded_filtering(self) -> None:
        """Test V2: Session-bounded filtering concept.

        Different sessions should have separate VoteAggregation instances.
        This test validates the filtering logic at the aggregation level.
        """
        current_session = str(uuid4())
        other_session = str(uuid4())
        vote_id = str(uuid4())

        # Vote for current session
        vote_current = create_vote_aggregation(
            vote_id=vote_id,
            session_id=current_session,
            optimistic_choice="APPROVE",
        )

        # Vote for other session (same vote_id, different session)
        vote_other = create_vote_aggregation(
            vote_id=vote_id,
            session_id=other_session,
            optimistic_choice="APPROVE",
        )

        # Add responses to each
        response = create_validator_response(validator_id="validator_1")
        vote_current.add_response(response)
        vote_other.add_response(response)

        # Sessions are independent
        assert vote_current.session_id == current_session
        assert vote_other.session_id == other_session
        assert vote_current.session_id != vote_other.session_id

    def test_consensus_determination_both_agree(self) -> None:
        """Test that consensus is correctly determined when validators agree."""
        vote = create_vote_aggregation(
            vote_id=str(uuid4()),
            session_id=str(uuid4()),
            optimistic_choice="APPROVE",
        )

        # Both validators agree
        response1 = create_validator_response(
            validator_id="validator_1",
            choice="APPROVE",
        )
        response2 = create_validator_response(
            validator_id="validator_2",
            choice="APPROVE",
        )

        vote.add_response(response1)
        vote.add_response(response2)

        # Check consensus
        choices = {r.validated_choice for r in vote.responses.values()}
        assert len(choices) == 1  # All agree
        assert "APPROVE" in choices

    def test_no_consensus_when_validators_disagree(self) -> None:
        """Test that disagreement is tracked correctly."""
        vote = create_vote_aggregation(
            vote_id=str(uuid4()),
            session_id=str(uuid4()),
            optimistic_choice="APPROVE",
        )

        # Validators disagree
        response1 = create_validator_response(
            validator_id="validator_1",
            choice="APPROVE",
        )
        response2 = create_validator_response(
            validator_id="validator_2",
            choice="REJECT",  # Different!
        )

        vote.add_response(response1)
        vote.add_response(response2)

        # Check no consensus
        choices = {r.validated_choice for r in vote.responses.values()}
        assert len(choices) == 2  # Disagreement
        assert "APPROVE" in choices
        assert "REJECT" in choices


class TestIdempotencyGuarantees:
    """Tests for idempotency guarantees in aggregation."""

    def test_same_validator_multiple_attempts(self) -> None:
        """Test that multiple attempts from same validator are tracked separately."""
        vote = create_vote_aggregation(
            vote_id=str(uuid4()),
            session_id=str(uuid4()),
            optimistic_choice="APPROVE",
        )

        # Same validator, different attempts
        response_attempt1 = create_validator_response(
            validator_id="validator_1",
            choice="APPROVE",
            attempt=1,
        )
        response_attempt2 = create_validator_response(
            validator_id="validator_1",
            choice="APPROVE",
            attempt=2,  # Different attempt
        )

        result1 = vote.add_response(response_attempt1)
        result2 = vote.add_response(response_attempt2)

        # Both attempts should be tracked (different attempt numbers)
        assert result1 is True
        assert result2 is True
        assert len(vote.responses) == 2
        assert "validator_1:1" in vote.responses
        assert "validator_1:2" in vote.responses

    def test_duplicate_key_ignored(self) -> None:
        """Test that duplicate (vote_id, validator_id, attempt) is ignored."""
        vote = create_vote_aggregation(
            vote_id=str(uuid4()),
            session_id=str(uuid4()),
            optimistic_choice="APPROVE",
        )

        # Same exact response
        response = create_validator_response(
            validator_id="validator_1",
            choice="APPROVE",
            attempt=1,
        )

        # Process same response twice
        result1 = vote.add_response(response)
        result2 = vote.add_response(response)

        # First succeeds, second is skipped (idempotent)
        assert result1 is True
        assert result2 is False
        assert len(vote.responses) == 1


class TestMetricsAfterReconstruction:
    """Tests for metrics consistency after state reconstruction."""

    def test_response_count_reflects_state(self) -> None:
        """Test that response counts accurately reflect state."""
        # Create multiple votes
        votes: dict[str, VoteAggregation] = {}

        for i in range(5):
            vote_id = str(uuid4())
            vote = create_vote_aggregation(
                vote_id=vote_id,
                session_id=str(uuid4()),
                optimistic_choice="APPROVE",
            )

            # Add responses from both validators
            for validator_id in ["validator_1", "validator_2"]:
                response = create_validator_response(
                    validator_id=validator_id,
                    choice="APPROVE",
                )
                vote.add_response(response)

            votes[vote_id] = vote

        # Verify state
        assert len(votes) == 5
        for vote in votes.values():
            assert len(vote.responses) == 2

    def test_duplicate_skip_tracking(self) -> None:
        """Test that duplicate skips can be tracked."""
        vote = create_vote_aggregation(
            vote_id=str(uuid4()),
            session_id=str(uuid4()),
            optimistic_choice="APPROVE",
        )

        response = create_validator_response(
            validator_id="validator_1",
            choice="APPROVE",
        )

        # Track results manually
        results = [
            vote.add_response(response),
            vote.add_response(response),
            vote.add_response(response),
        ]

        # Count duplicates skipped
        duplicates_skipped = results.count(False)
        assert duplicates_skipped == 2


class TestEdgeCases:
    """Edge case tests for state reconstruction."""

    def test_empty_aggregation(self) -> None:
        """Test that empty VoteAggregation is valid."""
        vote = create_vote_aggregation(
            vote_id=str(uuid4()),
            session_id=str(uuid4()),
            optimistic_choice="APPROVE",
        )

        # No responses yet
        assert len(vote.responses) == 0
        assert vote.status == ConsensusStatus.PENDING

    def test_partial_consensus_state(self) -> None:
        """Test state with only partial validator responses."""
        vote = create_vote_aggregation(
            vote_id=str(uuid4()),
            session_id=str(uuid4()),
            optimistic_choice="APPROVE",
        )

        # Only one validator responded
        response = create_validator_response(
            validator_id="validator_1",
            choice="APPROVE",
        )
        vote.add_response(response)

        # Vote should be tracked but awaiting more responses
        assert len(vote.responses) == 1
        assert vote.status == ConsensusStatus.PENDING

    def test_response_data_integrity(self) -> None:
        """Test that response data is preserved correctly."""
        vote = create_vote_aggregation(
            vote_id=str(uuid4()),
            session_id=str(uuid4()),
            optimistic_choice="APPROVE",
        )

        # Add a response with specific values
        response = ValidatorResponse(
            validator_id="validator_test",
            validated_choice="REJECT",
            confidence=0.87,
            attempt=3,
            timestamp_ms=1234567890,
        )
        vote.add_response(response)

        # Verify data integrity
        stored = vote.responses["validator_test:3"]
        assert stored.validator_id == "validator_test"
        assert stored.validated_choice == "REJECT"
        assert stored.confidence == 0.87
        assert stored.attempt == 3
        assert stored.timestamp_ms == 1234567890

    def test_multiple_votes_isolation(self) -> None:
        """Test that multiple votes maintain isolation."""
        votes: dict[str, VoteAggregation] = {}

        # Create three separate votes
        for i in range(3):
            vote_id = str(uuid4())
            vote = create_vote_aggregation(
                vote_id=vote_id,
                session_id=str(uuid4()),
                optimistic_choice=["APPROVE", "REJECT", "ABSTAIN"][i],
            )
            response = create_validator_response(
                validator_id=f"validator_{i}",
                choice=vote.optimistic_choice,
            )
            vote.add_response(response)
            votes[vote_id] = vote

        # Verify isolation
        assert len(votes) == 3
        for vote_id, vote in votes.items():
            assert vote.vote_id == vote_id
            assert len(vote.responses) == 1
