"""Unit tests for DeliberationSession domain model (Story 2A.1).

Tests cover:
- FR-11.1: System SHALL assign exactly 3 Marquis-rank Archons
- FR-11.4: Deliberation SHALL follow structured protocol
- AT-6: Deliberation is collective judgment (2-of-3 consensus)
- CT-12: Frozen dataclass ensures immutability
- NFR-10.3: Consensus determinism - 100% reproducible
- NFR-10.4: Witness completeness - transcript integrity
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.errors.deliberation import (
    ConsensusNotReachedError,
    InvalidArchonAssignmentError,
    InvalidPhaseTransitionError,
    SessionAlreadyCompleteError,
)
from src.domain.models.deliberation_session import (
    CONSENSUS_THRESHOLD,
    PHASE_TRANSITION_MATRIX,
    REQUIRED_ARCHON_COUNT,
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_session_id():
    """Generate a sample session ID."""
    return uuid4()


@pytest.fixture
def sample_petition_id():
    """Generate a sample petition ID."""
    return uuid4()


@pytest.fixture
def sample_archons():
    """Generate 3 unique archon UUIDs."""
    return (uuid4(), uuid4(), uuid4())


@pytest.fixture
def sample_session(sample_session_id, sample_petition_id, sample_archons):
    """Create a sample deliberation session in ASSESS phase."""
    return DeliberationSession.create(
        session_id=sample_session_id,
        petition_id=sample_petition_id,
        assigned_archons=sample_archons,
    )


@pytest.fixture
def sample_transcript_hash():
    """Generate a sample 32-byte Blake3 hash."""
    return b"\x00" * 32


# =============================================================================
# DeliberationPhase Tests
# =============================================================================


class TestDeliberationPhase:
    """Tests for DeliberationPhase enum."""

    def test_phase_values(self):
        """Test all phase enum values exist."""
        assert DeliberationPhase.ASSESS.value == "ASSESS"
        assert DeliberationPhase.POSITION.value == "POSITION"
        assert DeliberationPhase.CROSS_EXAMINE.value == "CROSS_EXAMINE"
        assert DeliberationPhase.VOTE.value == "VOTE"
        assert DeliberationPhase.COMPLETE.value == "COMPLETE"

    def test_phase_count(self):
        """Test exactly 5 phases exist."""
        assert len(DeliberationPhase) == 5

    def test_is_terminal_complete(self):
        """Test COMPLETE is terminal phase."""
        assert DeliberationPhase.COMPLETE.is_terminal() is True

    def test_is_terminal_non_complete(self):
        """Test non-COMPLETE phases are not terminal."""
        assert DeliberationPhase.ASSESS.is_terminal() is False
        assert DeliberationPhase.POSITION.is_terminal() is False
        assert DeliberationPhase.CROSS_EXAMINE.is_terminal() is False
        assert DeliberationPhase.VOTE.is_terminal() is False

    def test_next_phase_assess(self):
        """Test ASSESS -> POSITION transition."""
        assert DeliberationPhase.ASSESS.next_phase() == DeliberationPhase.POSITION

    def test_next_phase_position(self):
        """Test POSITION -> CROSS_EXAMINE transition."""
        assert DeliberationPhase.POSITION.next_phase() == DeliberationPhase.CROSS_EXAMINE

    def test_next_phase_cross_examine(self):
        """Test CROSS_EXAMINE -> VOTE transition."""
        assert DeliberationPhase.CROSS_EXAMINE.next_phase() == DeliberationPhase.VOTE

    def test_next_phase_vote(self):
        """Test VOTE -> COMPLETE transition."""
        assert DeliberationPhase.VOTE.next_phase() == DeliberationPhase.COMPLETE

    def test_next_phase_complete_is_none(self):
        """Test COMPLETE has no next phase (terminal)."""
        assert DeliberationPhase.COMPLETE.next_phase() is None


class TestPhaseTransitionMatrix:
    """Tests for phase transition matrix (FR-11.4)."""

    def test_matrix_covers_all_phases(self):
        """Test matrix has entry for every phase."""
        for phase in DeliberationPhase:
            assert phase in PHASE_TRANSITION_MATRIX

    def test_matrix_valid_transitions(self):
        """Test matrix defines valid transitions."""
        assert PHASE_TRANSITION_MATRIX[DeliberationPhase.ASSESS] == DeliberationPhase.POSITION
        assert PHASE_TRANSITION_MATRIX[DeliberationPhase.POSITION] == DeliberationPhase.CROSS_EXAMINE
        assert PHASE_TRANSITION_MATRIX[DeliberationPhase.CROSS_EXAMINE] == DeliberationPhase.VOTE
        assert PHASE_TRANSITION_MATRIX[DeliberationPhase.VOTE] == DeliberationPhase.COMPLETE
        assert PHASE_TRANSITION_MATRIX[DeliberationPhase.COMPLETE] is None


# =============================================================================
# DeliberationOutcome Tests
# =============================================================================


class TestDeliberationOutcome:
    """Tests for DeliberationOutcome enum (Three Fates)."""

    def test_outcome_values(self):
        """Test all outcome enum values exist."""
        assert DeliberationOutcome.ACKNOWLEDGE.value == "ACKNOWLEDGE"
        assert DeliberationOutcome.REFER.value == "REFER"
        assert DeliberationOutcome.ESCALATE.value == "ESCALATE"

    def test_outcome_count(self):
        """Test exactly 3 outcomes exist (Three Fates)."""
        assert len(DeliberationOutcome) == 3


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Tests for domain constants."""

    def test_consensus_threshold(self):
        """Test consensus threshold is 2 (2-of-3 supermajority)."""
        assert CONSENSUS_THRESHOLD == 2

    def test_required_archon_count(self):
        """Test required archon count is 3 (FR-11.1)."""
        assert REQUIRED_ARCHON_COUNT == 3


# =============================================================================
# DeliberationSession Creation Tests
# =============================================================================


class TestDeliberationSessionCreation:
    """Tests for DeliberationSession creation (FR-11.1)."""

    def test_create_valid_session(self, sample_session_id, sample_petition_id, sample_archons):
        """Test creating a valid session with 3 archons."""
        session = DeliberationSession.create(
            session_id=sample_session_id,
            petition_id=sample_petition_id,
            assigned_archons=sample_archons,
        )

        assert session.session_id == sample_session_id
        assert session.petition_id == sample_petition_id
        assert session.assigned_archons == sample_archons
        assert session.phase == DeliberationPhase.ASSESS
        assert session.phase_transcripts == {}
        assert session.votes == {}
        assert session.outcome is None
        assert session.dissent_archon_id is None
        assert session.completed_at is None
        assert session.version == 1

    def test_create_sets_created_at(self, sample_session_id, sample_petition_id, sample_archons):
        """Test that created_at is set automatically."""
        before = datetime.now(timezone.utc)
        session = DeliberationSession.create(
            session_id=sample_session_id,
            petition_id=sample_petition_id,
            assigned_archons=sample_archons,
        )
        after = datetime.now(timezone.utc)

        assert before <= session.created_at <= after

    def test_create_fails_with_two_archons(self, sample_session_id, sample_petition_id):
        """Test creation fails with fewer than 3 archons."""
        archons = (uuid4(), uuid4())

        with pytest.raises(InvalidArchonAssignmentError) as exc_info:
            DeliberationSession.create(
                session_id=sample_session_id,
                petition_id=sample_petition_id,
                assigned_archons=archons,  # type: ignore
            )

        assert "Exactly 3 archons required" in str(exc_info.value)
        assert exc_info.value.archon_count == 2

    def test_create_fails_with_four_archons(self, sample_session_id, sample_petition_id):
        """Test creation fails with more than 3 archons."""
        archons = (uuid4(), uuid4(), uuid4(), uuid4())

        with pytest.raises(InvalidArchonAssignmentError) as exc_info:
            DeliberationSession.create(
                session_id=sample_session_id,
                petition_id=sample_petition_id,
                assigned_archons=archons,  # type: ignore
            )

        assert "Exactly 3 archons required" in str(exc_info.value)
        assert exc_info.value.archon_count == 4

    def test_create_fails_with_duplicate_archons(self, sample_session_id, sample_petition_id):
        """Test creation fails with duplicate archon IDs."""
        archon1 = uuid4()
        archon2 = uuid4()
        archons = (archon1, archon2, archon1)  # Duplicate

        with pytest.raises(InvalidArchonAssignmentError) as exc_info:
            DeliberationSession.create(
                session_id=sample_session_id,
                petition_id=sample_petition_id,
                assigned_archons=archons,
            )

        assert "Duplicate archon IDs" in str(exc_info.value)


class TestDeliberationSessionImmutability:
    """Tests for frozen dataclass immutability (CT-12)."""

    def test_session_is_frozen(self, sample_session):
        """Test that session attributes cannot be modified."""
        with pytest.raises(AttributeError):
            sample_session.phase = DeliberationPhase.POSITION  # type: ignore

    def test_session_id_immutable(self, sample_session):
        """Test session_id cannot be modified."""
        with pytest.raises(AttributeError):
            sample_session.session_id = uuid4()  # type: ignore

    def test_votes_dict_is_same_reference(self, sample_session):
        """Test that votes dict is the same reference (frozen doesn't deep copy).

        Note: frozen dataclasses don't prevent mutation of mutable field contents.
        The immutability guarantee is that the attribute reference cannot be changed,
        not that the dict contents cannot be modified. Domain methods return new
        sessions with copied dicts to maintain immutability semantics.
        """
        original_votes = sample_session.votes
        # Same reference returned
        assert sample_session.votes is original_votes


# =============================================================================
# Phase Transition Tests (FR-11.4)
# =============================================================================


class TestPhaseTransitions:
    """Tests for phase transitions (FR-11.4)."""

    def test_valid_transition_assess_to_position(self, sample_session):
        """Test valid ASSESS -> POSITION transition."""
        new_session = sample_session.with_phase(DeliberationPhase.POSITION)

        assert new_session.phase == DeliberationPhase.POSITION
        assert new_session.version == sample_session.version + 1

    def test_valid_transition_position_to_cross_examine(self, sample_session):
        """Test valid POSITION -> CROSS_EXAMINE transition."""
        session = sample_session.with_phase(DeliberationPhase.POSITION)
        new_session = session.with_phase(DeliberationPhase.CROSS_EXAMINE)

        assert new_session.phase == DeliberationPhase.CROSS_EXAMINE

    def test_valid_transition_cross_examine_to_vote(self, sample_session):
        """Test valid CROSS_EXAMINE -> VOTE transition."""
        session = sample_session.with_phase(DeliberationPhase.POSITION)
        session = session.with_phase(DeliberationPhase.CROSS_EXAMINE)
        new_session = session.with_phase(DeliberationPhase.VOTE)

        assert new_session.phase == DeliberationPhase.VOTE

    def test_valid_full_phase_sequence(self, sample_session):
        """Test complete phase sequence progression."""
        session = sample_session
        assert session.phase == DeliberationPhase.ASSESS

        session = session.with_phase(DeliberationPhase.POSITION)
        assert session.phase == DeliberationPhase.POSITION

        session = session.with_phase(DeliberationPhase.CROSS_EXAMINE)
        assert session.phase == DeliberationPhase.CROSS_EXAMINE

        session = session.with_phase(DeliberationPhase.VOTE)
        assert session.phase == DeliberationPhase.VOTE

        # To transition to COMPLETE, we need votes and outcome
        # This is handled by with_outcome()

    def test_invalid_skip_phase(self, sample_session):
        """Test that skipping phases raises error."""
        with pytest.raises(InvalidPhaseTransitionError) as exc_info:
            sample_session.with_phase(DeliberationPhase.VOTE)  # Skip to VOTE

        assert exc_info.value.from_phase == DeliberationPhase.ASSESS
        assert exc_info.value.to_phase == DeliberationPhase.VOTE
        assert exc_info.value.expected_phase == DeliberationPhase.POSITION

    def test_invalid_backward_transition(self, sample_session):
        """Test that backward transitions raise error."""
        session = sample_session.with_phase(DeliberationPhase.POSITION)

        with pytest.raises(InvalidPhaseTransitionError):
            session.with_phase(DeliberationPhase.ASSESS)  # Go backward

    def test_invalid_same_phase_transition(self, sample_session):
        """Test that transitioning to same phase raises error."""
        with pytest.raises(InvalidPhaseTransitionError):
            sample_session.with_phase(DeliberationPhase.ASSESS)

    def test_transition_preserves_other_fields(self, sample_session, sample_transcript_hash):
        """Test that phase transition preserves other session data."""
        session_with_transcript = sample_session.with_transcript(
            DeliberationPhase.ASSESS, sample_transcript_hash
        )
        new_session = session_with_transcript.with_phase(DeliberationPhase.POSITION)

        assert new_session.session_id == sample_session.session_id
        assert new_session.petition_id == sample_session.petition_id
        assert new_session.assigned_archons == sample_session.assigned_archons
        assert new_session.phase_transcripts == {DeliberationPhase.ASSESS: sample_transcript_hash}
        assert new_session.created_at == sample_session.created_at


# =============================================================================
# Transcript Tests (NFR-10.4)
# =============================================================================


class TestTranscripts:
    """Tests for phase transcripts (NFR-10.4)."""

    def test_add_transcript(self, sample_session, sample_transcript_hash):
        """Test adding a transcript hash."""
        new_session = sample_session.with_transcript(
            DeliberationPhase.ASSESS, sample_transcript_hash
        )

        assert new_session.has_transcript(DeliberationPhase.ASSESS)
        assert new_session.phase_transcripts[DeliberationPhase.ASSESS] == sample_transcript_hash
        assert new_session.version == sample_session.version + 1

    def test_add_multiple_transcripts(self, sample_session, sample_transcript_hash):
        """Test adding transcripts for multiple phases."""
        session = sample_session.with_transcript(DeliberationPhase.ASSESS, sample_transcript_hash)
        session = session.with_phase(DeliberationPhase.POSITION)

        position_hash = b"\x01" * 32
        session = session.with_transcript(DeliberationPhase.POSITION, position_hash)

        assert session.has_transcript(DeliberationPhase.ASSESS)
        assert session.has_transcript(DeliberationPhase.POSITION)
        assert not session.has_transcript(DeliberationPhase.CROSS_EXAMINE)

    def test_transcript_wrong_length_raises_error(self, sample_session):
        """Test that transcript hash must be 32 bytes."""
        with pytest.raises(ValueError) as exc_info:
            sample_session.with_transcript(DeliberationPhase.ASSESS, b"\x00" * 31)

        assert "32 bytes" in str(exc_info.value)

    def test_transcript_empty_raises_error(self, sample_session):
        """Test that empty transcript hash raises error."""
        with pytest.raises(ValueError):
            sample_session.with_transcript(DeliberationPhase.ASSESS, b"")

    def test_has_transcript_returns_false_when_missing(self, sample_session):
        """Test has_transcript returns False for missing transcripts."""
        assert not sample_session.has_transcript(DeliberationPhase.ASSESS)
        assert not sample_session.has_transcript(DeliberationPhase.POSITION)


# =============================================================================
# Voting Tests (AT-6)
# =============================================================================


class TestVoting:
    """Tests for voting system (AT-6: collective judgment)."""

    def test_record_votes(self, sample_session):
        """Test recording votes from all 3 archons."""
        archon1, archon2, archon3 = sample_session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.ACKNOWLEDGE,
            archon3: DeliberationOutcome.REFER,
        }

        new_session = sample_session.with_votes(votes)

        assert new_session.votes == votes
        assert new_session.version == sample_session.version + 1

    def test_votes_fail_with_non_assigned_archon(self, sample_session):
        """Test that non-assigned archon cannot vote."""
        archon1, archon2, _ = sample_session.assigned_archons
        rogue_archon = uuid4()
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.ACKNOWLEDGE,
            rogue_archon: DeliberationOutcome.REFER,  # Not assigned
        }

        with pytest.raises(InvalidArchonAssignmentError) as exc_info:
            sample_session.with_votes(votes)

        assert "not assigned to this session" in str(exc_info.value)

    def test_votes_fail_with_too_few_votes(self, sample_session):
        """Test that fewer than 3 votes raises error."""
        archon1, archon2, _ = sample_session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.ACKNOWLEDGE,
        }

        with pytest.raises(ValueError) as exc_info:
            sample_session.with_votes(votes)

        assert "Exactly 3 votes required" in str(exc_info.value)

    def test_get_archon_vote(self, sample_session):
        """Test retrieving an archon's vote."""
        archon1, archon2, archon3 = sample_session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.ESCALATE,
        }

        session = sample_session.with_votes(votes)

        assert session.get_archon_vote(archon1) == DeliberationOutcome.ACKNOWLEDGE
        assert session.get_archon_vote(archon2) == DeliberationOutcome.REFER
        assert session.get_archon_vote(archon3) == DeliberationOutcome.ESCALATE

    def test_get_archon_vote_returns_none_if_not_voted(self, sample_session):
        """Test that get_archon_vote returns None before voting."""
        archon1, _, _ = sample_session.assigned_archons
        assert sample_session.get_archon_vote(archon1) is None


# =============================================================================
# Consensus Resolution Tests (AT-6)
# =============================================================================


class TestConsensusResolution:
    """Tests for consensus resolution (AT-6: 2-of-3 supermajority)."""

    def test_unanimous_acknowledge(self, sample_session):
        """Test unanimous ACKNOWLEDGE outcome (3-0)."""
        archon1, archon2, archon3 = sample_session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.ACKNOWLEDGE,
            archon3: DeliberationOutcome.ACKNOWLEDGE,
        }

        session = sample_session.with_votes(votes)
        resolved = session.with_outcome()

        assert resolved.outcome == DeliberationOutcome.ACKNOWLEDGE
        assert resolved.phase == DeliberationPhase.COMPLETE
        assert resolved.dissent_archon_id is None  # Unanimous
        assert resolved.completed_at is not None

    def test_majority_acknowledge_one_dissent(self, sample_session):
        """Test 2-1 ACKNOWLEDGE outcome with dissenter."""
        archon1, archon2, archon3 = sample_session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.ACKNOWLEDGE,
            archon3: DeliberationOutcome.REFER,  # Dissenter
        }

        session = sample_session.with_votes(votes)
        resolved = session.with_outcome()

        assert resolved.outcome == DeliberationOutcome.ACKNOWLEDGE
        assert resolved.dissent_archon_id == archon3

    def test_majority_refer(self, sample_session):
        """Test 2-1 REFER outcome."""
        archon1, archon2, archon3 = sample_session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.REFER,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.ESCALATE,
        }

        session = sample_session.with_votes(votes)
        resolved = session.with_outcome()

        assert resolved.outcome == DeliberationOutcome.REFER
        assert resolved.dissent_archon_id == archon3

    def test_majority_escalate(self, sample_session):
        """Test 2-1 ESCALATE outcome."""
        archon1, archon2, archon3 = sample_session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.ESCALATE,
            archon3: DeliberationOutcome.ESCALATE,
        }

        session = sample_session.with_votes(votes)
        resolved = session.with_outcome()

        assert resolved.outcome == DeliberationOutcome.ESCALATE
        assert resolved.dissent_archon_id == archon1

    def test_unanimous_no_dissenter(self, sample_session):
        """Test unanimous vote has no dissenter."""
        archon1, archon2, archon3 = sample_session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.REFER,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.REFER,
        }

        session = sample_session.with_votes(votes)
        resolved = session.with_outcome()

        assert resolved.outcome == DeliberationOutcome.REFER
        assert resolved.dissent_archon_id is None

    def test_outcome_fails_without_votes(self, sample_session):
        """Test that resolving outcome without votes raises error."""
        with pytest.raises(ConsensusNotReachedError) as exc_info:
            sample_session.with_outcome()

        assert exc_info.value.votes_received == 0
        assert exc_info.value.votes_required == 3

    def test_outcome_increments_version(self, sample_session):
        """Test that resolving outcome increments version."""
        archon1, archon2, archon3 = sample_session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.ACKNOWLEDGE,
            archon3: DeliberationOutcome.ACKNOWLEDGE,
        }

        session = sample_session.with_votes(votes)
        resolved = session.with_outcome()

        assert resolved.version == session.version + 1


# =============================================================================
# Completed Session Tests (AC-6)
# =============================================================================


class TestCompletedSession:
    """Tests for completed session immutability (AC-6)."""

    @pytest.fixture
    def completed_session(self, sample_session):
        """Create a completed session."""
        archon1, archon2, archon3 = sample_session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.ACKNOWLEDGE,
            archon3: DeliberationOutcome.ACKNOWLEDGE,
        }
        session = sample_session.with_votes(votes)
        return session.with_outcome()

    def test_completed_session_cannot_change_phase(self, completed_session):
        """Test that completed session cannot change phase."""
        with pytest.raises(SessionAlreadyCompleteError) as exc_info:
            completed_session.with_phase(DeliberationPhase.VOTE)

        assert str(completed_session.session_id) in str(exc_info.value)
        assert "immutable" in str(exc_info.value)

    def test_completed_session_cannot_add_transcript(self, completed_session, sample_transcript_hash):
        """Test that completed session cannot add transcript."""
        with pytest.raises(SessionAlreadyCompleteError):
            completed_session.with_transcript(DeliberationPhase.VOTE, sample_transcript_hash)

    def test_completed_session_cannot_add_votes(self, completed_session):
        """Test that completed session cannot modify votes."""
        archon1, archon2, archon3 = completed_session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.REFER,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.REFER,
        }

        with pytest.raises(SessionAlreadyCompleteError):
            completed_session.with_votes(votes)

    def test_completed_session_cannot_resolve_again(self, completed_session):
        """Test that completed session cannot resolve outcome again."""
        with pytest.raises(SessionAlreadyCompleteError):
            completed_session.with_outcome()

    def test_completed_session_has_completed_at(self, completed_session):
        """Test that completed session has completed_at timestamp."""
        assert completed_session.completed_at is not None
        assert isinstance(completed_session.completed_at, datetime)


# =============================================================================
# Archon Assignment Tests
# =============================================================================


class TestArchonAssignment:
    """Tests for archon assignment checks."""

    def test_is_archon_assigned_true(self, sample_session):
        """Test is_archon_assigned returns True for assigned archon."""
        archon1 = sample_session.assigned_archons[0]
        assert sample_session.is_archon_assigned(archon1) is True

    def test_is_archon_assigned_false(self, sample_session):
        """Test is_archon_assigned returns False for non-assigned archon."""
        other_archon = uuid4()
        assert sample_session.is_archon_assigned(other_archon) is False

    def test_all_assigned_archons_are_assigned(self, sample_session):
        """Test all 3 assigned archons return True."""
        for archon_id in sample_session.assigned_archons:
            assert sample_session.is_archon_assigned(archon_id) is True


# =============================================================================
# Edge Cases and Error Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_session_equality(self, sample_session_id, sample_petition_id, sample_archons):
        """Test that sessions with same data are equal."""
        session1 = DeliberationSession.create(
            session_id=sample_session_id,
            petition_id=sample_petition_id,
            assigned_archons=sample_archons,
        )
        # Create with same data - note created_at will differ
        # so we need to manually construct with same created_at
        session2 = DeliberationSession(
            session_id=session1.session_id,
            petition_id=session1.petition_id,
            assigned_archons=session1.assigned_archons,
            phase=session1.phase,
            phase_transcripts=dict(session1.phase_transcripts),
            votes=dict(session1.votes),
            outcome=session1.outcome,
            dissent_archon_id=session1.dissent_archon_id,
            created_at=session1.created_at,
            completed_at=session1.completed_at,
            version=session1.version,
        )

        assert session1 == session2

    def test_session_not_hashable_due_to_mutable_fields(self, sample_session_id, sample_petition_id, sample_archons):
        """Test that sessions cannot be used in sets (dict fields aren't hashable).

        Note: Even though the dataclass is frozen, it contains dict fields which
        are not hashable. This is expected Python behavior. Use session_id for
        set membership or dictionary keys instead.
        """
        session = DeliberationSession.create(
            session_id=sample_session_id,
            petition_id=sample_petition_id,
            assigned_archons=sample_archons,
        )

        with pytest.raises(TypeError):
            {session}  # Should raise unhashable type error

    def test_version_starts_at_one(self, sample_session):
        """Test that version starts at 1."""
        assert sample_session.version == 1

    def test_version_increments_with_each_mutation(self, sample_session, sample_transcript_hash):
        """Test that version increments with each mutation."""
        assert sample_session.version == 1

        session = sample_session.with_transcript(DeliberationPhase.ASSESS, sample_transcript_hash)
        assert session.version == 2

        session = session.with_phase(DeliberationPhase.POSITION)
        assert session.version == 3

    def test_invalid_outcome_without_consensus(self, sample_session_id, sample_petition_id, sample_archons):
        """Test that creating session with mismatched outcome/votes raises error."""
        archon1, archon2, archon3 = sample_archons
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.ACKNOWLEDGE,
            archon3: DeliberationOutcome.REFER,
        }

        # Try to create session with REFER outcome when votes show ACKNOWLEDGE majority
        with pytest.raises(ConsensusNotReachedError):
            DeliberationSession(
                session_id=sample_session_id,
                petition_id=sample_petition_id,
                assigned_archons=sample_archons,
                phase=DeliberationPhase.COMPLETE,
                votes=votes,
                outcome=DeliberationOutcome.REFER,  # Wrong! Should be ACKNOWLEDGE
                completed_at=datetime.now(timezone.utc),
            )

    def test_outcome_without_all_votes_raises_error(self, sample_session_id, sample_petition_id, sample_archons):
        """Test that setting outcome without 3 votes raises error."""
        archon1, archon2, _ = sample_archons
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.ACKNOWLEDGE,
        }

        with pytest.raises(ConsensusNotReachedError):
            DeliberationSession(
                session_id=sample_session_id,
                petition_id=sample_petition_id,
                assigned_archons=sample_archons,
                phase=DeliberationPhase.COMPLETE,
                votes=votes,
                outcome=DeliberationOutcome.ACKNOWLEDGE,
                completed_at=datetime.now(timezone.utc),
            )
