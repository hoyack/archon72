"""Unit tests for ConsensusResolverService (Story 2A.6, FR-11.5, FR-11.6).

Tests the 2-of-3 supermajority consensus resolution algorithm.

Constitutional Constraints Verified:
- AT-6: Deliberation is collective judgment, not unilateral decision
- NFR-10.3: Consensus determinism - 100% reproducible
"""

from uuid import uuid4

import pytest

from src.application.services.consensus_resolver_service import ConsensusResolverService
from src.domain.errors.deliberation import ConsensusNotReachedError
from src.domain.models.consensus_result import (
    CONSENSUS_ALGORITHM_VERSION,
    ConsensusStatus,
    VoteValidationStatus,
)
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationSession,
)


# Test fixtures
def make_session() -> DeliberationSession:
    """Create a test deliberation session with 3 archons."""
    return DeliberationSession.create(
        session_id=uuid4(),
        petition_id=uuid4(),
        assigned_archons=(uuid4(), uuid4(), uuid4()),
    )


class TestValidateVotes:
    """Tests for ConsensusResolverService.validate_votes()."""

    def test_valid_votes_all_assigned_archons(self) -> None:
        """Test validation passes when all assigned archons vote (AC-1)."""
        service = ConsensusResolverService()
        session = make_session()
        archons = session.assigned_archons

        votes = {
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.ACKNOWLEDGE,
            archons[2]: DeliberationOutcome.REFER,
        }

        result = service.validate_votes(session, votes)

        assert result.is_valid is True
        assert result.status == VoteValidationStatus.VALID

    def test_missing_votes_detected(self) -> None:
        """Test validation detects missing votes (AC-2)."""
        service = ConsensusResolverService()
        session = make_session()
        archons = session.assigned_archons

        # Only 2 of 3 archons vote
        votes = {
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.REFER,
        }

        result = service.validate_votes(session, votes)

        assert result.is_valid is False
        assert result.status == VoteValidationStatus.MISSING_VOTES
        assert archons[2] in result.missing_archon_ids
        assert len(result.missing_archon_ids) == 1

    def test_unauthorized_voter_detected(self) -> None:
        """Test validation detects unauthorized voters (AC-3)."""
        service = ConsensusResolverService()
        session = make_session()
        archons = session.assigned_archons

        unauthorized_archon = uuid4()  # Not in session

        # Include unauthorized archon
        votes = {
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.REFER,
            unauthorized_archon: DeliberationOutcome.ESCALATE,
        }

        result = service.validate_votes(session, votes)

        assert result.is_valid is False
        assert result.status == VoteValidationStatus.UNAUTHORIZED_VOTER
        assert unauthorized_archon in result.unauthorized_archon_ids

    def test_empty_votes_returns_missing(self) -> None:
        """Test validation with no votes returns missing all archons."""
        service = ConsensusResolverService()
        session = make_session()

        result = service.validate_votes(session, {})

        assert result.is_valid is False
        assert result.status == VoteValidationStatus.MISSING_VOTES
        assert len(result.missing_archon_ids) == 3


class TestResolveConsensus:
    """Tests for ConsensusResolverService.resolve_consensus()."""

    def test_unanimous_3_0_vote_acknowledge(self) -> None:
        """Test unanimous vote returns UNANIMOUS status (AC-4)."""
        service = ConsensusResolverService()
        session = make_session()
        archons = session.assigned_archons

        votes = {
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.ACKNOWLEDGE,
            archons[2]: DeliberationOutcome.ACKNOWLEDGE,
        }

        result = service.resolve_consensus(session, votes)

        assert result.status == ConsensusStatus.UNANIMOUS
        assert result.winning_outcome == "ACKNOWLEDGE"
        assert result.is_unanimous is True
        assert result.has_dissent is False
        assert result.dissent_archon_id is None
        assert len(result.majority_archon_ids) == 3
        assert result.vote_distribution == {"ACKNOWLEDGE": 3}

    def test_unanimous_3_0_vote_refer(self) -> None:
        """Test unanimous vote for REFER."""
        service = ConsensusResolverService()
        session = make_session()
        archons = session.assigned_archons

        votes = {
            archons[0]: DeliberationOutcome.REFER,
            archons[1]: DeliberationOutcome.REFER,
            archons[2]: DeliberationOutcome.REFER,
        }

        result = service.resolve_consensus(session, votes)

        assert result.status == ConsensusStatus.UNANIMOUS
        assert result.winning_outcome == "REFER"

    def test_unanimous_3_0_vote_escalate(self) -> None:
        """Test unanimous vote for ESCALATE."""
        service = ConsensusResolverService()
        session = make_session()
        archons = session.assigned_archons

        votes = {
            archons[0]: DeliberationOutcome.ESCALATE,
            archons[1]: DeliberationOutcome.ESCALATE,
            archons[2]: DeliberationOutcome.ESCALATE,
        }

        result = service.resolve_consensus(session, votes)

        assert result.status == ConsensusStatus.UNANIMOUS
        assert result.winning_outcome == "ESCALATE"

    def test_split_2_1_vote_identifies_dissenter(self) -> None:
        """Test 2-1 split identifies the dissenting archon (AC-5, FR-11.6)."""
        service = ConsensusResolverService()
        session = make_session()
        archons = session.assigned_archons

        # archons[0] and archons[1] vote REFER, archons[2] dissents
        votes = {
            archons[0]: DeliberationOutcome.REFER,
            archons[1]: DeliberationOutcome.REFER,
            archons[2]: DeliberationOutcome.ACKNOWLEDGE,  # Dissenter
        }

        result = service.resolve_consensus(session, votes)

        assert result.status == ConsensusStatus.ACHIEVED
        assert result.winning_outcome == "REFER"
        assert result.is_consensus_reached is True
        assert result.has_dissent is True
        assert result.dissent_archon_id == archons[2]
        assert len(result.majority_archon_ids) == 2
        assert archons[0] in result.majority_archon_ids
        assert archons[1] in result.majority_archon_ids
        assert result.vote_distribution == {"REFER": 2, "ACKNOWLEDGE": 1}

    def test_split_first_archon_dissents(self) -> None:
        """Test 2-1 split where first archon dissents."""
        service = ConsensusResolverService()
        session = make_session()
        archons = session.assigned_archons

        votes = {
            archons[0]: DeliberationOutcome.ESCALATE,  # Dissenter
            archons[1]: DeliberationOutcome.ACKNOWLEDGE,
            archons[2]: DeliberationOutcome.ACKNOWLEDGE,
        }

        result = service.resolve_consensus(session, votes)

        assert result.status == ConsensusStatus.ACHIEVED
        assert result.winning_outcome == "ACKNOWLEDGE"
        assert result.dissent_archon_id == archons[0]

    def test_split_second_archon_dissents(self) -> None:
        """Test 2-1 split where second archon dissents."""
        service = ConsensusResolverService()
        session = make_session()
        archons = session.assigned_archons

        votes = {
            archons[0]: DeliberationOutcome.REFER,
            archons[1]: DeliberationOutcome.ESCALATE,  # Dissenter
            archons[2]: DeliberationOutcome.REFER,
        }

        result = service.resolve_consensus(session, votes)

        assert result.status == ConsensusStatus.ACHIEVED
        assert result.winning_outcome == "REFER"
        assert result.dissent_archon_id == archons[1]

    def test_invalid_votes_raises_value_error(self) -> None:
        """Test that invalid votes raise ValueError (AC-6)."""
        service = ConsensusResolverService()
        session = make_session()
        archons = session.assigned_archons

        # Only 2 votes - missing one
        votes = {
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.REFER,
        }

        with pytest.raises(ValueError, match="Vote validation failed"):
            service.resolve_consensus(session, votes)

    def test_all_different_votes_raises_consensus_not_reached(self) -> None:
        """Test that all different votes raises ConsensusNotReachedError (edge case)."""
        service = ConsensusResolverService()
        session = make_session()
        archons = session.assigned_archons

        # All 3 archons vote differently - no 2-of-3 majority possible
        votes = {
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.REFER,
            archons[2]: DeliberationOutcome.ESCALATE,
        }

        with pytest.raises(ConsensusNotReachedError) as exc_info:
            service.resolve_consensus(session, votes)

        assert exc_info.value.votes_received == 3
        assert "2-of-3 supermajority" in str(exc_info.value)

    def test_algorithm_version_included_in_result(self) -> None:
        """Test that algorithm version is included for determinism (NFR-10.3)."""
        service = ConsensusResolverService()
        session = make_session()
        archons = session.assigned_archons

        votes = {
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.ACKNOWLEDGE,
            archons[2]: DeliberationOutcome.ACKNOWLEDGE,
        }

        result = service.resolve_consensus(session, votes)

        assert result.algorithm_version == CONSENSUS_ALGORITHM_VERSION

    def test_session_and_petition_ids_preserved(self) -> None:
        """Test that session and petition IDs are correctly preserved."""
        service = ConsensusResolverService()
        session = make_session()
        archons = session.assigned_archons

        votes = {
            archons[0]: DeliberationOutcome.REFER,
            archons[1]: DeliberationOutcome.REFER,
            archons[2]: DeliberationOutcome.REFER,
        }

        result = service.resolve_consensus(session, votes)

        assert result.session_id == session.session_id
        assert result.petition_id == session.petition_id


class TestCanReachConsensus:
    """Tests for ConsensusResolverService.can_reach_consensus()."""

    def test_unanimous_votes_can_reach_consensus(self) -> None:
        """Test that unanimous votes can reach consensus."""
        service = ConsensusResolverService()
        archons = [uuid4() for _ in range(3)]

        votes = {
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.ACKNOWLEDGE,
            archons[2]: DeliberationOutcome.ACKNOWLEDGE,
        }

        assert service.can_reach_consensus(votes) is True

    def test_split_2_1_can_reach_consensus(self) -> None:
        """Test that 2-1 split can reach consensus."""
        service = ConsensusResolverService()
        archons = [uuid4() for _ in range(3)]

        votes = {
            archons[0]: DeliberationOutcome.REFER,
            archons[1]: DeliberationOutcome.REFER,
            archons[2]: DeliberationOutcome.ACKNOWLEDGE,
        }

        assert service.can_reach_consensus(votes) is True

    def test_all_different_cannot_reach_consensus(self) -> None:
        """Test that all different votes cannot reach consensus."""
        service = ConsensusResolverService()
        archons = [uuid4() for _ in range(3)]

        votes = {
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.REFER,
            archons[2]: DeliberationOutcome.ESCALATE,
        }

        assert service.can_reach_consensus(votes) is False

    def test_insufficient_votes_cannot_reach_consensus(self) -> None:
        """Test that fewer than 3 votes cannot reach consensus."""
        service = ConsensusResolverService()
        archons = [uuid4() for _ in range(2)]

        votes = {
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.ACKNOWLEDGE,
        }

        assert service.can_reach_consensus(votes) is False

    def test_too_many_votes_cannot_reach_consensus(self) -> None:
        """Test that more than 3 votes cannot reach consensus."""
        service = ConsensusResolverService()
        archons = [uuid4() for _ in range(4)]

        votes = {
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.ACKNOWLEDGE,
            archons[2]: DeliberationOutcome.ACKNOWLEDGE,
            archons[3]: DeliberationOutcome.ACKNOWLEDGE,
        }

        assert service.can_reach_consensus(votes) is False


class TestDeterminism:
    """Tests for consensus resolution determinism (NFR-10.3)."""

    def test_same_inputs_produce_same_output(self) -> None:
        """Test that identical inputs always produce identical outputs."""
        service = ConsensusResolverService()
        session = make_session()
        archons = session.assigned_archons

        votes = {
            archons[0]: DeliberationOutcome.ESCALATE,
            archons[1]: DeliberationOutcome.ESCALATE,
            archons[2]: DeliberationOutcome.REFER,
        }

        # Run multiple times
        results = [service.resolve_consensus(session, votes) for _ in range(10)]

        # All results should be identical (except timestamp)
        for result in results:
            assert result.status == results[0].status
            assert result.winning_outcome == results[0].winning_outcome
            assert result.vote_distribution == results[0].vote_distribution
            assert result.majority_archon_ids == results[0].majority_archon_ids
            assert result.dissent_archon_id == results[0].dissent_archon_id
            assert result.algorithm_version == results[0].algorithm_version

    def test_vote_order_does_not_affect_outcome(self) -> None:
        """Test that different vote orderings produce same outcome."""
        service = ConsensusResolverService()
        session = make_session()
        archons = session.assigned_archons

        # Same votes in different orderings
        votes_order_1 = {
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.REFER,
            archons[2]: DeliberationOutcome.ACKNOWLEDGE,
        }

        votes_order_2 = {
            archons[2]: DeliberationOutcome.ACKNOWLEDGE,
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.REFER,
        }

        result_1 = service.resolve_consensus(session, votes_order_1)
        result_2 = service.resolve_consensus(session, votes_order_2)

        assert result_1.winning_outcome == result_2.winning_outcome
        assert result_1.status == result_2.status
        assert set(result_1.majority_archon_ids) == set(result_2.majority_archon_ids)
