"""Integration tests for consensus resolver (Story 2A.6, FR-11.5, FR-11.6).

Tests the ConsensusResolverService integration with DeliberationSession
and validates the complete consensus resolution flow.

Constitutional Constraints Verified:
- AT-6: Deliberation is collective judgment, not unilateral decision
- NFR-10.3: Consensus determinism - 100% reproducible
- CT-12: Witnessing creates accountability (via to_dict serialization)
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
    CONSENSUS_THRESHOLD,
    REQUIRED_ARCHON_COUNT,
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)
from src.infrastructure.stubs.consensus_resolver_stub import (
    ConsensusResolverOperation,
    ConsensusResolverStub,
)


class TestConsensusResolverIntegration:
    """Integration tests for ConsensusResolverService with DeliberationSession."""

    def test_full_deliberation_flow_unanimous_acknowledge(self) -> None:
        """Test full flow: session -> votes -> unanimous consensus (FR-11.5, FR-11.6)."""
        # Create session
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )
        archons = session.assigned_archons

        # Simulate all archons voting ACKNOWLEDGE
        votes = {
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.ACKNOWLEDGE,
            archons[2]: DeliberationOutcome.ACKNOWLEDGE,
        }

        # Resolve consensus
        service = ConsensusResolverService()
        result = service.resolve_consensus(session, votes)

        # Verify unanimous result
        assert result.status == ConsensusStatus.UNANIMOUS
        assert result.winning_outcome == DeliberationOutcome.ACKNOWLEDGE.value
        assert result.is_unanimous is True
        assert result.has_dissent is False

        # Verify session can be updated with outcome
        session_with_votes = session.with_votes(votes)
        session_complete = session_with_votes.with_outcome()

        assert session_complete.outcome == DeliberationOutcome.ACKNOWLEDGE
        assert session_complete.phase == DeliberationPhase.COMPLETE
        assert session_complete.dissent_archon_id is None

    def test_full_deliberation_flow_split_refer(self) -> None:
        """Test full flow: session -> votes -> 2-1 split consensus for REFER."""
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )
        archons = session.assigned_archons

        # 2 vote REFER, 1 votes ACKNOWLEDGE
        votes = {
            archons[0]: DeliberationOutcome.REFER,
            archons[1]: DeliberationOutcome.REFER,
            archons[2]: DeliberationOutcome.ACKNOWLEDGE,
        }

        service = ConsensusResolverService()
        result = service.resolve_consensus(session, votes)

        # Verify split result
        assert result.status == ConsensusStatus.ACHIEVED
        assert result.winning_outcome == DeliberationOutcome.REFER.value
        assert result.has_dissent is True
        assert result.dissent_archon_id == archons[2]

        # Verify session can be updated
        session_with_votes = session.with_votes(votes)
        session_complete = session_with_votes.with_outcome()

        assert session_complete.outcome == DeliberationOutcome.REFER
        assert session_complete.dissent_archon_id == archons[2]

    def test_full_deliberation_flow_split_escalate(self) -> None:
        """Test full flow: session -> votes -> 2-1 split consensus for ESCALATE."""
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )
        archons = session.assigned_archons

        # 2 vote ESCALATE, 1 votes REFER
        votes = {
            archons[0]: DeliberationOutcome.ESCALATE,
            archons[1]: DeliberationOutcome.REFER,  # Dissenter
            archons[2]: DeliberationOutcome.ESCALATE,
        }

        service = ConsensusResolverService()
        result = service.resolve_consensus(session, votes)

        assert result.status == ConsensusStatus.ACHIEVED
        assert result.winning_outcome == DeliberationOutcome.ESCALATE.value
        assert result.dissent_archon_id == archons[1]

    def test_consensus_result_serialization_for_witness(self) -> None:
        """Test that consensus result serializes properly for witness record (CT-12)."""
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )
        archons = session.assigned_archons

        votes = {
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.ACKNOWLEDGE,
            archons[2]: DeliberationOutcome.REFER,
        }

        service = ConsensusResolverService()
        result = service.resolve_consensus(session, votes)

        # Serialize for witness record
        data = result.to_dict()

        # Verify all required fields for witness record
        assert "session_id" in data
        assert "petition_id" in data
        assert "status" in data
        assert "winning_outcome" in data
        assert "vote_distribution" in data
        assert "majority_archon_ids" in data
        assert "dissent_archon_id" in data
        assert "algorithm_version" in data
        assert "resolved_at" in data
        assert "schema_version" in data

        # Verify schema_version for event serialization (D2)
        assert data["schema_version"] == 1

    def test_validation_matches_session_constraints(self) -> None:
        """Test that validation enforces session's archon constraints."""
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )
        archons = session.assigned_archons

        # Try to include an archon not in the session
        rogue_archon = uuid4()
        votes = {
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.ACKNOWLEDGE,
            rogue_archon: DeliberationOutcome.ACKNOWLEDGE,
        }

        service = ConsensusResolverService()
        validation = service.validate_votes(session, votes)

        assert validation.is_valid is False
        assert validation.status == VoteValidationStatus.UNAUTHORIZED_VOTER
        assert rogue_archon in validation.unauthorized_archon_ids


class TestConsensusResolverStubIntegration:
    """Integration tests for ConsensusResolverStub."""

    def test_stub_default_mode_works_like_service(self) -> None:
        """Test that stub in default mode produces correct results."""
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )
        archons = session.assigned_archons

        votes = {
            archons[0]: DeliberationOutcome.REFER,
            archons[1]: DeliberationOutcome.REFER,
            archons[2]: DeliberationOutcome.REFER,
        }

        stub = ConsensusResolverStub()
        result = stub.resolve_consensus(session, votes)

        assert result.status == ConsensusStatus.UNANIMOUS
        assert result.winning_outcome == "REFER"

        # Verify call was recorded
        assert len(stub.calls) == 1
        assert stub.calls[0].operation == ConsensusResolverOperation.RESOLVE_CONSENSUS

    def test_stub_force_unanimous_mode(self) -> None:
        """Test stub in force_unanimous mode."""
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )
        archons = session.assigned_archons

        # Votes that would normally produce split
        votes = {
            archons[0]: DeliberationOutcome.REFER,
            archons[1]: DeliberationOutcome.REFER,
            archons[2]: DeliberationOutcome.ACKNOWLEDGE,
        }

        stub = ConsensusResolverStub.force_unanimous(
            outcome=DeliberationOutcome.ESCALATE
        )
        result = stub.resolve_consensus(session, votes)

        # Stub overrides to unanimous ESCALATE
        assert result.status == ConsensusStatus.UNANIMOUS
        assert result.winning_outcome == "ESCALATE"

    def test_stub_force_split_mode(self) -> None:
        """Test stub in force_split mode."""
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )
        archons = session.assigned_archons

        # Votes that would normally be unanimous
        votes = {
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.ACKNOWLEDGE,
            archons[2]: DeliberationOutcome.ACKNOWLEDGE,
        }

        stub = ConsensusResolverStub.force_split(
            outcome=DeliberationOutcome.REFER,
            dissenter_index=0,
        )
        result = stub.resolve_consensus(session, votes)

        # Stub overrides to 2-1 split
        assert result.status == ConsensusStatus.ACHIEVED
        assert result.winning_outcome == "REFER"
        assert result.dissent_archon_id == archons[0]

    def test_stub_force_no_consensus_mode(self) -> None:
        """Test stub in force_no_consensus mode."""
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )
        archons = session.assigned_archons

        votes = {
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.ACKNOWLEDGE,
            archons[2]: DeliberationOutcome.ACKNOWLEDGE,
        }

        stub = ConsensusResolverStub.force_no_consensus()

        with pytest.raises(ConsensusNotReachedError):
            stub.resolve_consensus(session, votes)

    def test_stub_tracks_all_operations(self) -> None:
        """Test that stub tracks all operations for verification."""
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )
        archons = session.assigned_archons

        votes = {
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.ACKNOWLEDGE,
            archons[2]: DeliberationOutcome.ACKNOWLEDGE,
        }

        stub = ConsensusResolverStub()

        # Call multiple operations
        stub.validate_votes(session, votes)
        stub.resolve_consensus(session, votes)
        stub.can_reach_consensus(votes)

        assert len(stub.calls) == 3
        assert stub.calls[0].operation == ConsensusResolverOperation.VALIDATE_VOTES
        assert stub.calls[1].operation == ConsensusResolverOperation.RESOLVE_CONSENSUS
        assert stub.calls[2].operation == ConsensusResolverOperation.CAN_REACH_CONSENSUS


class TestConsensusConstants:
    """Tests verifying consensus constants match session constraints."""

    def test_supermajority_threshold_matches_session(self) -> None:
        """Test that SUPERMAJORITY_THRESHOLD matches session's CONSENSUS_THRESHOLD."""
        from src.domain.models.consensus_result import SUPERMAJORITY_THRESHOLD

        assert SUPERMAJORITY_THRESHOLD == CONSENSUS_THRESHOLD == 2

    def test_required_vote_count_matches_session(self) -> None:
        """Test that REQUIRED_VOTE_COUNT matches session's REQUIRED_ARCHON_COUNT."""
        from src.domain.models.consensus_result import REQUIRED_VOTE_COUNT

        assert REQUIRED_VOTE_COUNT == REQUIRED_ARCHON_COUNT == 3
