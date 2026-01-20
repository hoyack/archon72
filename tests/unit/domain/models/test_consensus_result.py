"""Unit tests for ConsensusResult domain model (Story 2A.6, FR-11.5, FR-11.6).

Tests the ConsensusResult and VoteValidationResult domain models for
the supermajority consensus resolution system.

Constitutional Constraints Verified:
- AT-6: Deliberation is collective judgment, not unilateral decision
- NFR-10.3: Consensus determinism - 100% reproducible
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.models.consensus_result import (
    CONSENSUS_ALGORITHM_VERSION,
    REQUIRED_VOTE_COUNT,
    SUPERMAJORITY_THRESHOLD,
    ConsensusResult,
    ConsensusStatus,
    VoteValidationResult,
    VoteValidationStatus,
)


# Test constants
ARCHON_1 = uuid4()
ARCHON_2 = uuid4()
ARCHON_3 = uuid4()
SESSION_ID = uuid4()
PETITION_ID = uuid4()


class TestVoteValidationResult:
    """Tests for VoteValidationResult domain model."""

    def test_valid_factory_method(self) -> None:
        """Test VoteValidationResult.valid() factory method."""
        result = VoteValidationResult.valid()

        assert result.is_valid is True
        assert result.status == VoteValidationStatus.VALID
        assert result.missing_archon_ids == ()
        assert result.unauthorized_archon_ids == ()
        assert result.error_message is None
        assert isinstance(result.validated_at, datetime)

    def test_missing_votes_factory_method(self) -> None:
        """Test VoteValidationResult.missing_votes() factory method."""
        missing = (ARCHON_1, ARCHON_2)
        result = VoteValidationResult.missing_votes(missing)

        assert result.is_valid is False
        assert result.status == VoteValidationStatus.MISSING_VOTES
        assert result.missing_archon_ids == missing
        assert result.unauthorized_archon_ids == ()
        assert "2 archon(s)" in result.error_message

    def test_unauthorized_voter_factory_method(self) -> None:
        """Test VoteValidationResult.unauthorized_voter() factory method."""
        unauthorized = (ARCHON_3,)
        result = VoteValidationResult.unauthorized_voter(unauthorized)

        assert result.is_valid is False
        assert result.status == VoteValidationStatus.UNAUTHORIZED_VOTER
        assert result.missing_archon_ids == ()
        assert result.unauthorized_archon_ids == unauthorized
        assert "1 archon(s)" in result.error_message

    def test_invalid_outcome_factory_method(self) -> None:
        """Test VoteValidationResult.invalid_outcome() factory method."""
        result = VoteValidationResult.invalid_outcome("Invalid outcome type")

        assert result.is_valid is False
        assert result.status == VoteValidationStatus.INVALID_OUTCOME
        assert result.error_message == "Invalid outcome type"

    def test_immutability(self) -> None:
        """Test that VoteValidationResult is immutable (frozen dataclass)."""
        result = VoteValidationResult.valid()

        with pytest.raises(AttributeError):
            result.is_valid = False  # type: ignore


class TestConsensusResult:
    """Tests for ConsensusResult domain model."""

    def test_unanimous_consensus_creation(self) -> None:
        """Test creating a unanimous consensus result (3-0 vote)."""
        result = ConsensusResult(
            session_id=SESSION_ID,
            petition_id=PETITION_ID,
            status=ConsensusStatus.UNANIMOUS,
            winning_outcome="ACKNOWLEDGE",
            vote_distribution={"ACKNOWLEDGE": 3},
            majority_archon_ids=(ARCHON_1, ARCHON_2, ARCHON_3),
            dissent_archon_id=None,
        )

        assert result.is_consensus_reached is True
        assert result.is_unanimous is True
        assert result.has_dissent is False
        assert result.algorithm_version == CONSENSUS_ALGORITHM_VERSION

    def test_achieved_consensus_with_dissent(self) -> None:
        """Test creating a 2-1 split consensus result (FR-11.6)."""
        result = ConsensusResult(
            session_id=SESSION_ID,
            petition_id=PETITION_ID,
            status=ConsensusStatus.ACHIEVED,
            winning_outcome="REFER",
            vote_distribution={"REFER": 2, "ACKNOWLEDGE": 1},
            majority_archon_ids=(ARCHON_1, ARCHON_2),
            dissent_archon_id=ARCHON_3,
        )

        assert result.is_consensus_reached is True
        assert result.is_unanimous is False
        assert result.has_dissent is True
        assert result.dissent_archon_id == ARCHON_3

    def test_not_reached_status(self) -> None:
        """Test ConsensusStatus.NOT_REACHED (edge case)."""
        result = ConsensusResult(
            session_id=SESSION_ID,
            petition_id=PETITION_ID,
            status=ConsensusStatus.NOT_REACHED,
            winning_outcome=None,
            vote_distribution={"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1},
            majority_archon_ids=(),
            dissent_archon_id=None,
        )

        assert result.is_consensus_reached is False
        assert result.is_unanimous is False
        assert result.winning_outcome is None

    def test_invalid_status(self) -> None:
        """Test ConsensusStatus.INVALID."""
        result = ConsensusResult(
            session_id=SESSION_ID,
            petition_id=PETITION_ID,
            status=ConsensusStatus.INVALID,
            winning_outcome=None,
            vote_distribution={},
            majority_archon_ids=(),
            dissent_archon_id=None,
        )

        assert result.is_consensus_reached is False
        assert result.status == ConsensusStatus.INVALID

    def test_validation_unanimous_without_winning_outcome_raises(self) -> None:
        """Test that UNANIMOUS status without winning_outcome raises ValueError."""
        with pytest.raises(ValueError, match="must have a winning_outcome"):
            ConsensusResult(
                session_id=SESSION_ID,
                petition_id=PETITION_ID,
                status=ConsensusStatus.UNANIMOUS,
                winning_outcome=None,  # Invalid: must have outcome
                vote_distribution={"ACKNOWLEDGE": 3},
                majority_archon_ids=(ARCHON_1, ARCHON_2, ARCHON_3),
            )

    def test_validation_achieved_without_winning_outcome_raises(self) -> None:
        """Test that ACHIEVED status without winning_outcome raises ValueError."""
        with pytest.raises(ValueError, match="must have a winning_outcome"):
            ConsensusResult(
                session_id=SESSION_ID,
                petition_id=PETITION_ID,
                status=ConsensusStatus.ACHIEVED,
                winning_outcome=None,  # Invalid: must have outcome
                vote_distribution={"REFER": 2, "ACKNOWLEDGE": 1},
                majority_archon_ids=(ARCHON_1, ARCHON_2),
                dissent_archon_id=ARCHON_3,
            )

    def test_validation_unanimous_with_dissenter_raises(self) -> None:
        """Test that UNANIMOUS status with dissent_archon_id raises ValueError."""
        with pytest.raises(ValueError, match="cannot have dissent_archon_id"):
            ConsensusResult(
                session_id=SESSION_ID,
                petition_id=PETITION_ID,
                status=ConsensusStatus.UNANIMOUS,
                winning_outcome="ACKNOWLEDGE",
                vote_distribution={"ACKNOWLEDGE": 3},
                majority_archon_ids=(ARCHON_1, ARCHON_2, ARCHON_3),
                dissent_archon_id=ARCHON_1,  # Invalid: unanimous can't have dissent
            )

    def test_validation_split_without_dissenter_raises(self) -> None:
        """Test that 2-1 split without dissent_archon_id raises ValueError."""
        with pytest.raises(ValueError, match="must identify dissent_archon_id"):
            ConsensusResult(
                session_id=SESSION_ID,
                petition_id=PETITION_ID,
                status=ConsensusStatus.ACHIEVED,
                winning_outcome="REFER",
                vote_distribution={"REFER": 2, "ACKNOWLEDGE": 1},
                majority_archon_ids=(ARCHON_1, ARCHON_2),  # Only 2 = split
                dissent_archon_id=None,  # Invalid: split must identify dissenter
            )

    def test_validation_insufficient_majority_raises(self) -> None:
        """Test that ACHIEVED with < 2 majority archons raises ValueError."""
        with pytest.raises(ValueError, match="at least 2 majority archons"):
            ConsensusResult(
                session_id=SESSION_ID,
                petition_id=PETITION_ID,
                status=ConsensusStatus.ACHIEVED,
                winning_outcome="REFER",
                vote_distribution={"REFER": 1},
                majority_archon_ids=(ARCHON_1,),  # Invalid: need at least 2
            )

    def test_to_dict_serialization(self) -> None:
        """Test ConsensusResult.to_dict() serialization."""
        result = ConsensusResult(
            session_id=SESSION_ID,
            petition_id=PETITION_ID,
            status=ConsensusStatus.ACHIEVED,
            winning_outcome="ESCALATE",
            vote_distribution={"ESCALATE": 2, "REFER": 1},
            majority_archon_ids=(ARCHON_1, ARCHON_2),
            dissent_archon_id=ARCHON_3,
        )

        data = result.to_dict()

        assert data["session_id"] == str(SESSION_ID)
        assert data["petition_id"] == str(PETITION_ID)
        assert data["status"] == "ACHIEVED"
        assert data["winning_outcome"] == "ESCALATE"
        assert data["vote_distribution"] == {"ESCALATE": 2, "REFER": 1}
        assert len(data["majority_archon_ids"]) == 2
        assert data["dissent_archon_id"] == str(ARCHON_3)
        assert data["algorithm_version"] == CONSENSUS_ALGORITHM_VERSION
        assert data["schema_version"] == 1
        assert "resolved_at" in data

    def test_to_dict_with_none_dissenter(self) -> None:
        """Test to_dict() with None dissent_archon_id (unanimous)."""
        result = ConsensusResult(
            session_id=SESSION_ID,
            petition_id=PETITION_ID,
            status=ConsensusStatus.UNANIMOUS,
            winning_outcome="ACKNOWLEDGE",
            vote_distribution={"ACKNOWLEDGE": 3},
            majority_archon_ids=(ARCHON_1, ARCHON_2, ARCHON_3),
            dissent_archon_id=None,
        )

        data = result.to_dict()
        assert data["dissent_archon_id"] is None

    def test_immutability(self) -> None:
        """Test that ConsensusResult is immutable (frozen dataclass)."""
        result = ConsensusResult(
            session_id=SESSION_ID,
            petition_id=PETITION_ID,
            status=ConsensusStatus.UNANIMOUS,
            winning_outcome="ACKNOWLEDGE",
            vote_distribution={"ACKNOWLEDGE": 3},
            majority_archon_ids=(ARCHON_1, ARCHON_2, ARCHON_3),
        )

        with pytest.raises(AttributeError):
            result.status = ConsensusStatus.INVALID  # type: ignore


class TestConsensusConstants:
    """Tests for consensus-related constants."""

    def test_supermajority_threshold_is_two(self) -> None:
        """Test that supermajority threshold is 2 (for 2-of-3)."""
        assert SUPERMAJORITY_THRESHOLD == 2

    def test_required_vote_count_is_three(self) -> None:
        """Test that required vote count is 3 (FR-11.1)."""
        assert REQUIRED_VOTE_COUNT == 3

    def test_algorithm_version_exists(self) -> None:
        """Test that algorithm version is defined (NFR-10.3 determinism)."""
        assert CONSENSUS_ALGORITHM_VERSION >= 1
