"""Unit tests for deliberation result domain models (Story 2A.4, FR-11.4).

Tests PhaseResult and DeliberationResult frozen dataclasses for correctness,
immutability, and invariant enforcement.

Constitutional Constraints:
- FR-11.4: Structured protocol execution
- FR-11.5: Supermajority consensus (2-of-3)
- AT-6: Collective judgment via consensus
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.models.deliberation_result import (
    DeliberationResult,
    PhaseResult,
)
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
)


def _make_hash(content: str) -> bytes:
    """Create a 32-byte hash for testing."""
    return hashlib.sha256(content.encode()).digest()


def _make_timestamp(offset_seconds: int = 0) -> datetime:
    """Create a UTC timestamp with optional offset."""
    base = datetime(2026, 1, 19, 12, 0, 0, tzinfo=timezone.utc)
    return base + timedelta(seconds=offset_seconds)


class TestPhaseResult:
    """Tests for PhaseResult frozen dataclass."""

    def test_create_valid_phase_result(self) -> None:
        """PhaseResult can be created with valid parameters."""
        archon1 = uuid4()
        archon2 = uuid4()
        archon3 = uuid4()

        result = PhaseResult(
            phase=DeliberationPhase.ASSESS,
            transcript="Test transcript content",
            transcript_hash=_make_hash("Test transcript content"),
            participants=(archon1, archon2, archon3),
            started_at=_make_timestamp(0),
            completed_at=_make_timestamp(100),
            phase_metadata={"assessments_completed": 3},
        )

        assert result.phase == DeliberationPhase.ASSESS
        assert result.transcript == "Test transcript content"
        assert len(result.transcript_hash) == 32
        assert len(result.participants) == 3
        assert result.phase_metadata["assessments_completed"] == 3

    def test_phase_result_is_frozen(self) -> None:
        """PhaseResult is immutable (frozen dataclass)."""
        result = PhaseResult(
            phase=DeliberationPhase.ASSESS,
            transcript="Test",
            transcript_hash=_make_hash("Test"),
            participants=(uuid4(),),
            started_at=_make_timestamp(0),
            completed_at=_make_timestamp(100),
        )

        with pytest.raises(AttributeError):
            result.phase = DeliberationPhase.VOTE  # type: ignore[misc]

    def test_phase_result_duration_ms(self) -> None:
        """duration_ms returns correct millisecond duration."""
        result = PhaseResult(
            phase=DeliberationPhase.ASSESS,
            transcript="Test",
            transcript_hash=_make_hash("Test"),
            participants=(uuid4(),),
            started_at=_make_timestamp(0),
            completed_at=_make_timestamp(5),  # 5 seconds
        )

        assert result.duration_ms == 5000

    def test_invalid_transcript_hash_length_raises(self) -> None:
        """Creating PhaseResult with wrong hash length raises ValueError."""
        with pytest.raises(ValueError, match="must be 32 bytes"):
            PhaseResult(
                phase=DeliberationPhase.ASSESS,
                transcript="Test",
                transcript_hash=b"short",  # Not 32 bytes
                participants=(uuid4(),),
                started_at=_make_timestamp(0),
                completed_at=_make_timestamp(100),
            )

    def test_completed_before_started_raises(self) -> None:
        """Creating PhaseResult with completed_at before started_at raises ValueError."""
        with pytest.raises(ValueError, match="cannot be before"):
            PhaseResult(
                phase=DeliberationPhase.ASSESS,
                transcript="Test",
                transcript_hash=_make_hash("Test"),
                participants=(uuid4(),),
                started_at=_make_timestamp(100),
                completed_at=_make_timestamp(0),  # Before started
            )

    def test_empty_participants_raises(self) -> None:
        """Creating PhaseResult with no participants raises ValueError."""
        with pytest.raises(ValueError, match="At least one participant"):
            PhaseResult(
                phase=DeliberationPhase.ASSESS,
                transcript="Test",
                transcript_hash=_make_hash("Test"),
                participants=(),  # Empty
                started_at=_make_timestamp(0),
                completed_at=_make_timestamp(100),
            )

    def test_duplicate_participants_raises(self) -> None:
        """Creating PhaseResult with duplicate participants raises ValueError."""
        archon = uuid4()
        with pytest.raises(ValueError, match="Duplicate participant"):
            PhaseResult(
                phase=DeliberationPhase.ASSESS,
                transcript="Test",
                transcript_hash=_make_hash("Test"),
                participants=(archon, archon),  # Duplicate
                started_at=_make_timestamp(0),
                completed_at=_make_timestamp(100),
            )

    def test_get_metadata_returns_value(self) -> None:
        """get_metadata returns metadata value by key."""
        result = PhaseResult(
            phase=DeliberationPhase.ASSESS,
            transcript="Test",
            transcript_hash=_make_hash("Test"),
            participants=(uuid4(),),
            started_at=_make_timestamp(0),
            completed_at=_make_timestamp(100),
            phase_metadata={"key": "value"},
        )

        assert result.get_metadata("key") == "value"
        assert result.get_metadata("missing", "default") == "default"


class TestDeliberationResult:
    """Tests for DeliberationResult frozen dataclass."""

    def _make_phase_results(
        self, archons: tuple[uuid4, uuid4, uuid4]
    ) -> tuple[PhaseResult, ...]:
        """Create a valid tuple of 4 phase results."""
        phases = [
            DeliberationPhase.ASSESS,
            DeliberationPhase.POSITION,
            DeliberationPhase.CROSS_EXAMINE,
            DeliberationPhase.VOTE,
        ]
        results = []
        for i, phase in enumerate(phases):
            results.append(
                PhaseResult(
                    phase=phase,
                    transcript=f"Transcript for {phase.value}",
                    transcript_hash=_make_hash(f"Transcript for {phase.value}"),
                    participants=archons,
                    started_at=_make_timestamp(i * 100),
                    completed_at=_make_timestamp((i + 1) * 100),
                )
            )
        return tuple(results)

    def test_create_valid_deliberation_result_unanimous(self) -> None:
        """DeliberationResult can be created with unanimous 3-0 vote."""
        session_id = uuid4()
        petition_id = uuid4()
        archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
        archons = (archon1, archon2, archon3)

        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.ACKNOWLEDGE,
            archon3: DeliberationOutcome.ACKNOWLEDGE,
        }

        result = DeliberationResult(
            session_id=session_id,
            petition_id=petition_id,
            outcome=DeliberationOutcome.ACKNOWLEDGE,
            votes=votes,
            dissent_archon_id=None,  # Unanimous
            phase_results=self._make_phase_results(archons),
            started_at=_make_timestamp(0),
            completed_at=_make_timestamp(400),
        )

        assert result.outcome == DeliberationOutcome.ACKNOWLEDGE
        assert result.is_unanimous is True
        assert result.dissent_archon_id is None
        assert len(result.phase_results) == 4

    def test_create_valid_deliberation_result_with_dissent(self) -> None:
        """DeliberationResult can be created with 2-1 vote."""
        session_id = uuid4()
        petition_id = uuid4()
        archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
        archons = (archon1, archon2, archon3)

        votes = {
            archon1: DeliberationOutcome.REFER,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.ACKNOWLEDGE,  # Dissent
        }

        result = DeliberationResult(
            session_id=session_id,
            petition_id=petition_id,
            outcome=DeliberationOutcome.REFER,
            votes=votes,
            dissent_archon_id=archon3,
            phase_results=self._make_phase_results(archons),
            started_at=_make_timestamp(0),
            completed_at=_make_timestamp(400),
        )

        assert result.outcome == DeliberationOutcome.REFER
        assert result.is_unanimous is False
        assert result.dissent_archon_id == archon3

    def test_deliberation_result_is_frozen(self) -> None:
        """DeliberationResult is immutable (frozen dataclass)."""
        archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
        archons = (archon1, archon2, archon3)

        result = DeliberationResult(
            session_id=uuid4(),
            petition_id=uuid4(),
            outcome=DeliberationOutcome.ACKNOWLEDGE,
            votes={a: DeliberationOutcome.ACKNOWLEDGE for a in archons},
            dissent_archon_id=None,
            phase_results=self._make_phase_results(archons),
            started_at=_make_timestamp(0),
            completed_at=_make_timestamp(400),
        )

        with pytest.raises(AttributeError):
            result.outcome = DeliberationOutcome.REFER  # type: ignore[misc]

    def test_total_duration_ms(self) -> None:
        """total_duration_ms returns correct millisecond duration."""
        archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
        archons = (archon1, archon2, archon3)

        result = DeliberationResult(
            session_id=uuid4(),
            petition_id=uuid4(),
            outcome=DeliberationOutcome.ACKNOWLEDGE,
            votes={a: DeliberationOutcome.ACKNOWLEDGE for a in archons},
            dissent_archon_id=None,
            phase_results=self._make_phase_results(archons),
            started_at=_make_timestamp(0),
            completed_at=_make_timestamp(10),  # 10 seconds
        )

        assert result.total_duration_ms == 10000

    def test_wrong_vote_count_raises(self) -> None:
        """Creating with fewer than 3 votes raises ValueError."""
        archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
        archons = (archon1, archon2, archon3)

        with pytest.raises(ValueError, match="Exactly 3 votes required"):
            DeliberationResult(
                session_id=uuid4(),
                petition_id=uuid4(),
                outcome=DeliberationOutcome.ACKNOWLEDGE,
                votes={archon1: DeliberationOutcome.ACKNOWLEDGE},  # Only 1 vote
                dissent_archon_id=None,
                phase_results=self._make_phase_results(archons),
                started_at=_make_timestamp(0),
                completed_at=_make_timestamp(400),
            )

    def test_outcome_without_consensus_raises(self) -> None:
        """Creating with outcome that has < 2 votes raises ValueError."""
        archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
        archons = (archon1, archon2, archon3)

        # All different votes - no consensus for any outcome
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.ESCALATE,
        }

        with pytest.raises(ValueError, match="does not have 2-of-3 consensus"):
            DeliberationResult(
                session_id=uuid4(),
                petition_id=uuid4(),
                outcome=DeliberationOutcome.ACKNOWLEDGE,  # Only 1 vote
                votes=votes,
                dissent_archon_id=archon2,  # Would need to pick one
                phase_results=self._make_phase_results(archons),
                started_at=_make_timestamp(0),
                completed_at=_make_timestamp(400),
            )

    def test_unanimous_with_dissent_id_raises(self) -> None:
        """Creating unanimous vote with dissent_archon_id raises ValueError."""
        archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
        archons = (archon1, archon2, archon3)

        votes = {a: DeliberationOutcome.ACKNOWLEDGE for a in archons}

        with pytest.raises(ValueError, match="must be None for unanimous"):
            DeliberationResult(
                session_id=uuid4(),
                petition_id=uuid4(),
                outcome=DeliberationOutcome.ACKNOWLEDGE,
                votes=votes,
                dissent_archon_id=archon3,  # Shouldn't have dissent for unanimous
                phase_results=self._make_phase_results(archons),
                started_at=_make_timestamp(0),
                completed_at=_make_timestamp(400),
            )

    def test_non_unanimous_without_dissent_id_raises(self) -> None:
        """Creating 2-1 vote without dissent_archon_id raises ValueError."""
        archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
        archons = (archon1, archon2, archon3)

        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.ACKNOWLEDGE,
            archon3: DeliberationOutcome.REFER,  # Dissent
        }

        with pytest.raises(ValueError, match="required for 2-1 vote"):
            DeliberationResult(
                session_id=uuid4(),
                petition_id=uuid4(),
                outcome=DeliberationOutcome.ACKNOWLEDGE,
                votes=votes,
                dissent_archon_id=None,  # Missing dissent id
                phase_results=self._make_phase_results(archons),
                started_at=_make_timestamp(0),
                completed_at=_make_timestamp(400),
            )

    def test_wrong_dissent_archon_raises(self) -> None:
        """Creating with dissent_archon_id that voted for outcome raises ValueError."""
        archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
        archons = (archon1, archon2, archon3)

        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.ACKNOWLEDGE,
            archon3: DeliberationOutcome.REFER,
        }

        with pytest.raises(ValueError, match="voted for outcome"):
            DeliberationResult(
                session_id=uuid4(),
                petition_id=uuid4(),
                outcome=DeliberationOutcome.ACKNOWLEDGE,
                votes=votes,
                dissent_archon_id=archon1,  # archon1 voted for outcome, not dissent
                phase_results=self._make_phase_results(archons),
                started_at=_make_timestamp(0),
                completed_at=_make_timestamp(400),
            )

    def test_wrong_phase_count_raises(self) -> None:
        """Creating with too few phase results raises ValueError."""
        archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
        archons = (archon1, archon2, archon3)

        # Only 2 phase results
        partial_results = self._make_phase_results(archons)[:2]

        with pytest.raises(
            ValueError,
            match="Phase results must include ASSESS, POSITION, and at least one",
        ):
            DeliberationResult(
                session_id=uuid4(),
                petition_id=uuid4(),
                outcome=DeliberationOutcome.ACKNOWLEDGE,
                votes={a: DeliberationOutcome.ACKNOWLEDGE for a in archons},
                dissent_archon_id=None,
                phase_results=partial_results,
                started_at=_make_timestamp(0),
                completed_at=_make_timestamp(400),
            )

    def test_wrong_phase_order_raises(self) -> None:
        """Creating with phases out of order raises ValueError."""
        archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
        archons = (archon1, archon2, archon3)

        # Phases in wrong order
        wrong_order_results = (
            PhaseResult(
                phase=DeliberationPhase.VOTE,  # Should be ASSESS
                transcript="Test",
                transcript_hash=_make_hash("Test"),
                participants=archons,
                started_at=_make_timestamp(0),
                completed_at=_make_timestamp(100),
            ),
            PhaseResult(
                phase=DeliberationPhase.POSITION,
                transcript="Test",
                transcript_hash=_make_hash("Test2"),
                participants=archons,
                started_at=_make_timestamp(100),
                completed_at=_make_timestamp(200),
            ),
            PhaseResult(
                phase=DeliberationPhase.CROSS_EXAMINE,
                transcript="Test",
                transcript_hash=_make_hash("Test3"),
                participants=archons,
                started_at=_make_timestamp(200),
                completed_at=_make_timestamp(300),
            ),
            PhaseResult(
                phase=DeliberationPhase.ASSESS,  # Should be VOTE
                transcript="Test",
                transcript_hash=_make_hash("Test4"),
                participants=archons,
                started_at=_make_timestamp(300),
                completed_at=_make_timestamp(400),
            ),
        )

        with pytest.raises(ValueError, match="should be ASSESS"):
            DeliberationResult(
                session_id=uuid4(),
                petition_id=uuid4(),
                outcome=DeliberationOutcome.ACKNOWLEDGE,
                votes={a: DeliberationOutcome.ACKNOWLEDGE for a in archons},
                dissent_archon_id=None,
                phase_results=wrong_order_results,
                started_at=_make_timestamp(0),
                completed_at=_make_timestamp(400),
            )

    def test_get_phase_result_returns_correct_phase(self) -> None:
        """get_phase_result returns the result for specified phase."""
        archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
        archons = (archon1, archon2, archon3)

        result = DeliberationResult(
            session_id=uuid4(),
            petition_id=uuid4(),
            outcome=DeliberationOutcome.ACKNOWLEDGE,
            votes={a: DeliberationOutcome.ACKNOWLEDGE for a in archons},
            dissent_archon_id=None,
            phase_results=self._make_phase_results(archons),
            started_at=_make_timestamp(0),
            completed_at=_make_timestamp(400),
        )

        assess = result.get_phase_result(DeliberationPhase.ASSESS)
        assert assess is not None
        assert assess.phase == DeliberationPhase.ASSESS

        vote = result.get_phase_result(DeliberationPhase.VOTE)
        assert vote is not None
        assert vote.phase == DeliberationPhase.VOTE

    def test_get_archon_vote_returns_correct_vote(self) -> None:
        """get_archon_vote returns the archon's vote."""
        archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
        archons = (archon1, archon2, archon3)

        votes = {
            archon1: DeliberationOutcome.REFER,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.ACKNOWLEDGE,
        }

        result = DeliberationResult(
            session_id=uuid4(),
            petition_id=uuid4(),
            outcome=DeliberationOutcome.REFER,
            votes=votes,
            dissent_archon_id=archon3,
            phase_results=self._make_phase_results(archons),
            started_at=_make_timestamp(0),
            completed_at=_make_timestamp(400),
        )

        assert result.get_archon_vote(archon1) == DeliberationOutcome.REFER
        assert result.get_archon_vote(archon3) == DeliberationOutcome.ACKNOWLEDGE
        assert result.get_archon_vote(uuid4()) is None  # Unknown archon

    def test_majority_archons_returns_winning_voters(self) -> None:
        """majority_archons returns archons who voted for outcome."""
        archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
        archons = (archon1, archon2, archon3)

        votes = {
            archon1: DeliberationOutcome.ESCALATE,
            archon2: DeliberationOutcome.ESCALATE,
            archon3: DeliberationOutcome.ACKNOWLEDGE,
        }

        result = DeliberationResult(
            session_id=uuid4(),
            petition_id=uuid4(),
            outcome=DeliberationOutcome.ESCALATE,
            votes=votes,
            dissent_archon_id=archon3,
            phase_results=self._make_phase_results(archons),
            started_at=_make_timestamp(0),
            completed_at=_make_timestamp(400),
        )

        majority = result.majority_archons
        assert len(majority) == 2
        assert archon1 in majority
        assert archon2 in majority
        assert archon3 not in majority
