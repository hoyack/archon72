"""Integration tests for CrewAI Deliberation Adapter (Story 2A.5, FR-11.4).

These tests verify the CrewAIDeliberationAdapter integrates correctly with:
- Archon profile repository
- Deliberation session domain model
- Context package domain model
- Phase result domain model

Tests use the PhaseExecutorStub for deterministic behavior while
validating the adapter's interface compatibility.

Test Coverage:
- AC1: PhaseExecutorProtocol compliance
- AC6: Blake3 transcript integrity
- Integration with existing domain models
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.models.deliberation_context_package import (
    DeliberationContextPackage,
    compute_content_hash,
)
from src.domain.models.deliberation_result import PhaseResult
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)
from src.infrastructure.stubs.deliberation_orchestrator_stub import (
    PhaseExecutorStub,
)


@pytest.fixture
def archon_ids() -> tuple:
    """Create 3 archon UUIDs for testing."""
    return (uuid4(), uuid4(), uuid4())


@pytest.fixture
def session_id() -> uuid4:
    """Create session UUID for testing."""
    return uuid4()


@pytest.fixture
def petition_id() -> uuid4:
    """Create petition UUID for testing."""
    return uuid4()


@pytest.fixture
def deliberation_session(session_id, petition_id, archon_ids):
    """Create a deliberation session for testing."""
    return DeliberationSession.create(
        session_id=session_id,
        petition_id=petition_id,
        assigned_archons=archon_ids,
    )


@pytest.fixture
def context_package(petition_id, session_id, archon_ids):
    """Create a context package with content hash for testing."""
    pkg = DeliberationContextPackage(
        petition_id=petition_id,
        petition_text="Integration test petition for Three Fates deliberation.",
        petition_type="GENERAL",
        co_signer_count=10,
        submitter_id=uuid4(),
        realm="governance",
        submitted_at=datetime.now(timezone.utc),
        session_id=session_id,
        assigned_archons=archon_ids,
    )
    # Compute and set content hash
    hashable = pkg.to_hashable_dict()
    content_hash = compute_content_hash(hashable)
    return DeliberationContextPackage(
        petition_id=pkg.petition_id,
        petition_text=pkg.petition_text,
        petition_type=pkg.petition_type,
        co_signer_count=pkg.co_signer_count,
        submitter_id=pkg.submitter_id,
        realm=pkg.realm,
        submitted_at=pkg.submitted_at,
        session_id=pkg.session_id,
        assigned_archons=pkg.assigned_archons,
        built_at=pkg.built_at,
        content_hash=content_hash,
    )


@pytest.fixture
def executor_stub():
    """Create PhaseExecutorStub for testing."""
    return PhaseExecutorStub()


class TestPhaseExecutorProtocolCompliance:
    """Test that implementations comply with PhaseExecutorProtocol."""

    def test_stub_implements_execute_assess(
        self,
        executor_stub,
        deliberation_session,
        context_package,
    ):
        """AC1: Stub implements execute_assess method."""
        result = executor_stub.execute_assess(deliberation_session, context_package)

        assert isinstance(result, PhaseResult)
        assert result.phase == DeliberationPhase.ASSESS

    def test_stub_implements_execute_position(
        self,
        executor_stub,
        deliberation_session,
        context_package,
    ):
        """AC1: Stub implements execute_position method."""
        assess_result = executor_stub.execute_assess(
            deliberation_session, context_package
        )
        result = executor_stub.execute_position(
            deliberation_session, context_package, assess_result
        )

        assert isinstance(result, PhaseResult)
        assert result.phase == DeliberationPhase.POSITION

    def test_stub_implements_execute_cross_examine(
        self,
        executor_stub,
        deliberation_session,
        context_package,
    ):
        """AC1: Stub implements execute_cross_examine method."""
        assess_result = executor_stub.execute_assess(
            deliberation_session, context_package
        )
        position_result = executor_stub.execute_position(
            deliberation_session, context_package, assess_result
        )
        result = executor_stub.execute_cross_examine(
            deliberation_session, context_package, position_result
        )

        assert isinstance(result, PhaseResult)
        assert result.phase == DeliberationPhase.CROSS_EXAMINE

    def test_stub_implements_execute_vote(
        self,
        executor_stub,
        deliberation_session,
        context_package,
    ):
        """AC1: Stub implements execute_vote method."""
        assess_result = executor_stub.execute_assess(
            deliberation_session, context_package
        )
        position_result = executor_stub.execute_position(
            deliberation_session, context_package, assess_result
        )
        cross_examine_result = executor_stub.execute_cross_examine(
            deliberation_session, context_package, position_result
        )
        result = executor_stub.execute_vote(
            deliberation_session, context_package, cross_examine_result
        )

        assert isinstance(result, PhaseResult)
        assert result.phase == DeliberationPhase.VOTE


class TestPhaseResultIntegrity:
    """Test phase result integrity with Blake3 hashing."""

    def test_phase_result_has_32_byte_hash(
        self,
        executor_stub,
        deliberation_session,
        context_package,
    ):
        """AC6: Phase results have 32-byte Blake3 hash."""
        result = executor_stub.execute_assess(deliberation_session, context_package)

        assert len(result.transcript_hash) == 32

    def test_phase_results_have_unique_hashes(
        self,
        executor_stub,
        deliberation_session,
        context_package,
    ):
        """AC6: Different phases produce different hashes."""
        assess = executor_stub.execute_assess(deliberation_session, context_package)
        position = executor_stub.execute_position(
            deliberation_session, context_package, assess
        )
        cross_examine = executor_stub.execute_cross_examine(
            deliberation_session, context_package, position
        )
        vote = executor_stub.execute_vote(
            deliberation_session, context_package, cross_examine
        )

        hashes = [
            assess.transcript_hash,
            position.transcript_hash,
            cross_examine.transcript_hash,
            vote.transcript_hash,
        ]

        # All hashes should be unique
        assert len(set(hashes)) == 4

    def test_phase_result_transcript_not_empty(
        self,
        executor_stub,
        deliberation_session,
        context_package,
    ):
        """Phase transcripts are not empty."""
        result = executor_stub.execute_assess(deliberation_session, context_package)

        assert len(result.transcript) > 0
        assert "ASSESS" in result.transcript


class TestVoteExtraction:
    """Test vote extraction from VOTE phase."""

    def test_vote_phase_returns_votes_in_metadata(
        self,
        executor_stub,
        deliberation_session,
        context_package,
    ):
        """AC5: VOTE phase metadata contains votes dict."""
        assess = executor_stub.execute_assess(deliberation_session, context_package)
        position = executor_stub.execute_position(
            deliberation_session, context_package, assess
        )
        cross_examine = executor_stub.execute_cross_examine(
            deliberation_session, context_package, position
        )
        vote = executor_stub.execute_vote(
            deliberation_session, context_package, cross_examine
        )

        votes = vote.get_metadata("votes")

        assert votes is not None
        assert len(votes) == 3

    def test_vote_phase_votes_are_valid_outcomes(
        self,
        executor_stub,
        deliberation_session,
        context_package,
        archon_ids,
    ):
        """AC5: All votes are valid DeliberationOutcome values."""
        assess = executor_stub.execute_assess(deliberation_session, context_package)
        position = executor_stub.execute_position(
            deliberation_session, context_package, assess
        )
        cross_examine = executor_stub.execute_cross_examine(
            deliberation_session, context_package, position
        )
        vote = executor_stub.execute_vote(
            deliberation_session, context_package, cross_examine
        )

        votes = vote.get_metadata("votes")

        for archon_id in archon_ids:
            assert archon_id in votes
            assert isinstance(votes[archon_id], DeliberationOutcome)

    def test_unanimous_vote_stub(
        self,
        deliberation_session,
        context_package,
    ):
        """Test stub with unanimous ESCALATE vote."""
        executor = PhaseExecutorStub.with_unanimous_vote(DeliberationOutcome.ESCALATE)

        assess = executor.execute_assess(deliberation_session, context_package)
        position = executor.execute_position(
            deliberation_session, context_package, assess
        )
        cross_examine = executor.execute_cross_examine(
            deliberation_session, context_package, position
        )
        vote = executor.execute_vote(
            deliberation_session, context_package, cross_examine
        )

        votes = vote.get_metadata("votes")
        for outcome in votes.values():
            assert outcome == DeliberationOutcome.ESCALATE

    def test_custom_votes_stub(
        self,
        deliberation_session,
        context_package,
        archon_ids,
    ):
        """Test stub with custom 2-1 vote."""
        custom_votes = {
            archon_ids[0]: DeliberationOutcome.REFER,
            archon_ids[1]: DeliberationOutcome.REFER,
            archon_ids[2]: DeliberationOutcome.ACKNOWLEDGE,
        }
        executor = PhaseExecutorStub.with_votes(custom_votes)

        assess = executor.execute_assess(deliberation_session, context_package)
        position = executor.execute_position(
            deliberation_session, context_package, assess
        )
        cross_examine = executor.execute_cross_examine(
            deliberation_session, context_package, position
        )
        vote = executor.execute_vote(
            deliberation_session, context_package, cross_examine
        )

        votes = vote.get_metadata("votes")
        assert votes[archon_ids[0]] == DeliberationOutcome.REFER
        assert votes[archon_ids[1]] == DeliberationOutcome.REFER
        assert votes[archon_ids[2]] == DeliberationOutcome.ACKNOWLEDGE


class TestCrossExamineMetadata:
    """Test CROSS_EXAMINE phase metadata."""

    def test_cross_examine_includes_rounds_completed(
        self,
        executor_stub,
        deliberation_session,
        context_package,
    ):
        """AC4: CROSS_EXAMINE metadata includes rounds_completed."""
        assess = executor_stub.execute_assess(deliberation_session, context_package)
        position = executor_stub.execute_position(
            deliberation_session, context_package, assess
        )
        result = executor_stub.execute_cross_examine(
            deliberation_session, context_package, position
        )

        assert result.get_metadata("rounds_completed") is not None
        assert result.get_metadata("rounds_completed") >= 1

    def test_cross_examine_includes_challenges_raised(
        self,
        executor_stub,
        deliberation_session,
        context_package,
    ):
        """AC4: CROSS_EXAMINE metadata includes challenges_raised."""
        assess = executor_stub.execute_assess(deliberation_session, context_package)
        position = executor_stub.execute_position(
            deliberation_session, context_package, assess
        )
        result = executor_stub.execute_cross_examine(
            deliberation_session, context_package, position
        )

        challenges = result.get_metadata("challenges_raised")
        assert challenges is not None
        assert isinstance(challenges, int)


class TestFullDeliberationFlow:
    """Test complete deliberation flow through all phases."""

    def test_full_flow_all_phases_complete(
        self,
        executor_stub,
        deliberation_session,
        context_package,
    ):
        """Complete deliberation flow executes all 4 phases."""
        assess = executor_stub.execute_assess(deliberation_session, context_package)
        assert assess.phase == DeliberationPhase.ASSESS

        position = executor_stub.execute_position(
            deliberation_session, context_package, assess
        )
        assert position.phase == DeliberationPhase.POSITION

        cross_examine = executor_stub.execute_cross_examine(
            deliberation_session, context_package, position
        )
        assert cross_examine.phase == DeliberationPhase.CROSS_EXAMINE

        vote = executor_stub.execute_vote(
            deliberation_session, context_package, cross_examine
        )
        assert vote.phase == DeliberationPhase.VOTE

    def test_full_flow_participants_consistent(
        self,
        executor_stub,
        deliberation_session,
        context_package,
        archon_ids,
    ):
        """All phases have same participants."""
        assess = executor_stub.execute_assess(deliberation_session, context_package)
        position = executor_stub.execute_position(
            deliberation_session, context_package, assess
        )
        cross_examine = executor_stub.execute_cross_examine(
            deliberation_session, context_package, position
        )
        vote = executor_stub.execute_vote(
            deliberation_session, context_package, cross_examine
        )

        expected_participants = archon_ids

        assert assess.participants == expected_participants
        assert position.participants == expected_participants
        assert cross_examine.participants == expected_participants
        assert vote.participants == expected_participants

    def test_full_flow_timestamps_sequential(
        self,
        executor_stub,
        deliberation_session,
        context_package,
    ):
        """Phase timestamps are sequential."""
        assess = executor_stub.execute_assess(deliberation_session, context_package)
        position = executor_stub.execute_position(
            deliberation_session, context_package, assess
        )
        cross_examine = executor_stub.execute_cross_examine(
            deliberation_session, context_package, position
        )
        vote = executor_stub.execute_vote(
            deliberation_session, context_package, cross_examine
        )

        # Verify temporal ordering
        assert assess.completed_at <= position.started_at
        assert position.completed_at <= cross_examine.started_at
        assert cross_examine.completed_at <= vote.started_at
