"""Unit tests for deliberation orchestrator service (Story 2A.4, FR-11.4).

Tests the DeliberationOrchestratorService for correct phase sequence execution,
session state management, and consensus resolution.

Constitutional Constraints:
- FR-11.4: Deliberation SHALL follow structured protocol
- FR-11.5: System SHALL require supermajority consensus (2-of-3)
- AT-6: Deliberation is collective judgment
- NFR-10.3: Consensus determinism - 100% reproducible
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.services.deliberation_orchestrator_service import (
    DeliberationOrchestratorService,
)
from src.domain.errors.deliberation import PetitionSessionMismatchError
from src.domain.models.deliberation_context_package import (
    CONTEXT_PACKAGE_SCHEMA_VERSION,
    DeliberationContextPackage,
)
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)
from src.infrastructure.stubs.deliberation_orchestrator_stub import (
    PhaseExecutorStub,
)


def _create_test_session(
    petition_id: uuid4 | None = None,
) -> DeliberationSession:
    """Create a test deliberation session."""
    archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
    return DeliberationSession.create(
        session_id=uuid4(),
        petition_id=petition_id or uuid4(),
        assigned_archons=(archon1, archon2, archon3),
    )


def _create_test_package(
    petition_id: uuid4,
    session_id: uuid4,
    archons: tuple[uuid4, uuid4, uuid4],
) -> DeliberationContextPackage:
    """Create a test context package."""
    return DeliberationContextPackage(
        petition_id=petition_id,
        petition_text="Test petition about constitutional matters",
        petition_type="GENERAL",
        co_signer_count=5,
        submitter_id=uuid4(),
        realm="test-realm",
        submitted_at=datetime.now(timezone.utc),
        session_id=session_id,
        assigned_archons=archons,
        similar_petitions=tuple(),
        ruling_3_deferred=True,
        schema_version=CONTEXT_PACKAGE_SCHEMA_VERSION,
        built_at=datetime.now(timezone.utc),
        content_hash="a" * 64,
    )


class TestDeliberationOrchestratorService:
    """Tests for DeliberationOrchestratorService."""

    def test_orchestrate_happy_path_unanimous(self) -> None:
        """Orchestrate executes all 4 phases and resolves unanimous outcome."""
        session = _create_test_session()
        package = _create_test_package(
            petition_id=session.petition_id,
            session_id=session.session_id,
            archons=session.assigned_archons,
        )

        executor = PhaseExecutorStub()
        orchestrator = DeliberationOrchestratorService(executor)

        result = orchestrator.orchestrate(session, package)

        # Verify outcome
        assert result.outcome == DeliberationOutcome.ACKNOWLEDGE
        assert result.is_unanimous is True
        assert result.dissent_archon_id is None

        # Verify all 4 phases executed
        assert len(result.phase_results) == 4
        assert result.phase_results[0].phase == DeliberationPhase.ASSESS
        assert result.phase_results[1].phase == DeliberationPhase.POSITION
        assert result.phase_results[2].phase == DeliberationPhase.CROSS_EXAMINE
        assert result.phase_results[3].phase == DeliberationPhase.VOTE

        # Verify session IDs match
        assert result.session_id == session.session_id
        assert result.petition_id == session.petition_id

    def test_orchestrate_with_dissent(self) -> None:
        """Orchestrate handles 2-1 vote with dissent correctly."""
        session = _create_test_session()
        package = _create_test_package(
            petition_id=session.petition_id,
            session_id=session.session_id,
            archons=session.assigned_archons,
        )

        archon1, archon2, archon3 = session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.REFER,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.ACKNOWLEDGE,  # Dissent
        }

        executor = PhaseExecutorStub.with_votes(votes)
        orchestrator = DeliberationOrchestratorService(executor)

        result = orchestrator.orchestrate(session, package)

        assert result.outcome == DeliberationOutcome.REFER
        assert result.is_unanimous is False
        assert result.dissent_archon_id == archon3

    def test_orchestrate_escalate_outcome(self) -> None:
        """Orchestrate can produce ESCALATE outcome."""
        session = _create_test_session()
        package = _create_test_package(
            petition_id=session.petition_id,
            session_id=session.session_id,
            archons=session.assigned_archons,
        )

        executor = PhaseExecutorStub.with_unanimous_vote(DeliberationOutcome.ESCALATE)
        orchestrator = DeliberationOrchestratorService(executor)

        result = orchestrator.orchestrate(session, package)

        assert result.outcome == DeliberationOutcome.ESCALATE
        assert result.is_unanimous is True

    def test_orchestrate_all_phases_have_transcripts(self) -> None:
        """All phase results include non-empty transcripts."""
        session = _create_test_session()
        package = _create_test_package(
            petition_id=session.petition_id,
            session_id=session.session_id,
            archons=session.assigned_archons,
        )

        executor = PhaseExecutorStub()
        orchestrator = DeliberationOrchestratorService(executor)

        result = orchestrator.orchestrate(session, package)

        for phase_result in result.phase_results:
            assert phase_result.transcript != ""
            assert len(phase_result.transcript_hash) == 32  # Valid hash

    def test_orchestrate_all_phases_have_participants(self) -> None:
        """All phase results include the 3 assigned archons."""
        session = _create_test_session()
        package = _create_test_package(
            petition_id=session.petition_id,
            session_id=session.session_id,
            archons=session.assigned_archons,
        )

        executor = PhaseExecutorStub()
        orchestrator = DeliberationOrchestratorService(executor)

        result = orchestrator.orchestrate(session, package)

        for phase_result in result.phase_results:
            assert len(phase_result.participants) == 3
            assert set(phase_result.participants) == set(session.assigned_archons)

    def test_orchestrate_mismatch_petition_id_raises(self) -> None:
        """Orchestrate raises if package.petition_id != session.petition_id."""
        session = _create_test_session()
        # Create package with different petition_id
        package = _create_test_package(
            petition_id=uuid4(),  # Different petition_id
            session_id=session.session_id,
            archons=session.assigned_archons,
        )

        executor = PhaseExecutorStub()
        orchestrator = DeliberationOrchestratorService(executor)

        with pytest.raises(PetitionSessionMismatchError):
            orchestrator.orchestrate(session, package)

    def test_orchestrate_records_timestamps(self) -> None:
        """Orchestrate records valid start and completion timestamps."""
        session = _create_test_session()
        package = _create_test_package(
            petition_id=session.petition_id,
            session_id=session.session_id,
            archons=session.assigned_archons,
        )

        executor = PhaseExecutorStub()
        orchestrator = DeliberationOrchestratorService(executor)

        result = orchestrator.orchestrate(session, package)

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at
        assert result.total_duration_ms >= 0

    def test_orchestrate_votes_extracted_correctly(self) -> None:
        """Orchestrate correctly extracts votes from vote phase metadata."""
        session = _create_test_session()
        package = _create_test_package(
            petition_id=session.petition_id,
            session_id=session.session_id,
            archons=session.assigned_archons,
        )

        archon1, archon2, archon3 = session.assigned_archons
        expected_votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.REFER,
        }

        executor = PhaseExecutorStub.with_votes(expected_votes)
        orchestrator = DeliberationOrchestratorService(executor)

        result = orchestrator.orchestrate(session, package)

        # Verify votes match
        assert result.votes == expected_votes
        assert result.get_archon_vote(archon1) == DeliberationOutcome.ACKNOWLEDGE
        assert result.get_archon_vote(archon2) == DeliberationOutcome.REFER

    def test_orchestrate_phase_metadata_preserved(self) -> None:
        """Phase-specific metadata is preserved in results."""
        session = _create_test_session()
        package = _create_test_package(
            petition_id=session.petition_id,
            session_id=session.session_id,
            archons=session.assigned_archons,
        )

        executor = PhaseExecutorStub()
        orchestrator = DeliberationOrchestratorService(executor)

        result = orchestrator.orchestrate(session, package)

        # Check ASSESS metadata
        assess = result.get_phase_result(DeliberationPhase.ASSESS)
        assert assess is not None
        assert "assessments_completed" in assess.phase_metadata

        # Check CROSS_EXAMINE metadata
        cross_examine = result.get_phase_result(DeliberationPhase.CROSS_EXAMINE)
        assert cross_examine is not None
        assert "challenges_raised" in cross_examine.phase_metadata
        assert "rounds_completed" in cross_examine.phase_metadata

        # Check VOTE metadata
        vote = result.get_phase_result(DeliberationPhase.VOTE)
        assert vote is not None
        assert "votes" in vote.phase_metadata

    def test_orchestrate_deterministic_with_same_inputs(self) -> None:
        """Same inputs produce same outcome (NFR-10.3 determinism)."""
        session = _create_test_session()
        package = _create_test_package(
            petition_id=session.petition_id,
            session_id=session.session_id,
            archons=session.assigned_archons,
        )

        # Same votes for both runs
        archon1, archon2, archon3 = session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.ESCALATE,
            archon2: DeliberationOutcome.ESCALATE,
            archon3: DeliberationOutcome.REFER,
        }

        executor1 = PhaseExecutorStub.with_votes(votes)
        orchestrator1 = DeliberationOrchestratorService(executor1)
        result1 = orchestrator1.orchestrate(session, package)

        executor2 = PhaseExecutorStub.with_votes(votes)
        orchestrator2 = DeliberationOrchestratorService(executor2)
        result2 = orchestrator2.orchestrate(session, package)

        # Outcomes must match
        assert result1.outcome == result2.outcome
        assert result1.is_unanimous == result2.is_unanimous
        assert result1.dissent_archon_id == result2.dissent_archon_id
        assert result1.votes == result2.votes


class TestPhaseSequenceEnforcement:
    """Tests verifying strict phase sequence (FR-11.4)."""

    def test_phases_execute_in_correct_order(self) -> None:
        """Phases execute in ASSESS -> POSITION -> CROSS_EXAMINE -> VOTE order."""
        session = _create_test_session()
        package = _create_test_package(
            petition_id=session.petition_id,
            session_id=session.session_id,
            archons=session.assigned_archons,
        )

        executor = PhaseExecutorStub()
        orchestrator = DeliberationOrchestratorService(executor)

        result = orchestrator.orchestrate(session, package)

        # Verify strict order
        expected_order = [
            DeliberationPhase.ASSESS,
            DeliberationPhase.POSITION,
            DeliberationPhase.CROSS_EXAMINE,
            DeliberationPhase.VOTE,
        ]

        for i, (expected, actual) in enumerate(
            zip(expected_order, result.phase_results, strict=True)
        ):
            assert actual.phase == expected, (
                f"Phase {i} should be {expected.value}, got {actual.phase.value}"
            )

    def test_all_four_phases_complete(self) -> None:
        """All 4 required phases complete during orchestration."""
        session = _create_test_session()
        package = _create_test_package(
            petition_id=session.petition_id,
            session_id=session.session_id,
            archons=session.assigned_archons,
        )

        executor = PhaseExecutorStub()
        orchestrator = DeliberationOrchestratorService(executor)

        result = orchestrator.orchestrate(session, package)

        # Must have exactly 4 phases
        assert len(result.phase_results) == 4

        # All phases represented
        phases = {pr.phase for pr in result.phase_results}
        assert phases == {
            DeliberationPhase.ASSESS,
            DeliberationPhase.POSITION,
            DeliberationPhase.CROSS_EXAMINE,
            DeliberationPhase.VOTE,
        }


class TestConsensusResolution:
    """Tests for supermajority consensus resolution (FR-11.5, AT-6)."""

    def test_2_acknowledge_resolves_to_acknowledge(self) -> None:
        """2-of-3 ACKNOWLEDGE votes resolve to ACKNOWLEDGE outcome."""
        session = _create_test_session()
        package = _create_test_package(
            petition_id=session.petition_id,
            session_id=session.session_id,
            archons=session.assigned_archons,
        )

        archon1, archon2, archon3 = session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.ACKNOWLEDGE,
            archon3: DeliberationOutcome.ESCALATE,
        }

        executor = PhaseExecutorStub.with_votes(votes)
        orchestrator = DeliberationOrchestratorService(executor)
        result = orchestrator.orchestrate(session, package)

        assert result.outcome == DeliberationOutcome.ACKNOWLEDGE

    def test_2_refer_resolves_to_refer(self) -> None:
        """2-of-3 REFER votes resolve to REFER outcome."""
        session = _create_test_session()
        package = _create_test_package(
            petition_id=session.petition_id,
            session_id=session.session_id,
            archons=session.assigned_archons,
        )

        archon1, archon2, archon3 = session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.REFER,
            archon2: DeliberationOutcome.ACKNOWLEDGE,
            archon3: DeliberationOutcome.REFER,
        }

        executor = PhaseExecutorStub.with_votes(votes)
        orchestrator = DeliberationOrchestratorService(executor)
        result = orchestrator.orchestrate(session, package)

        assert result.outcome == DeliberationOutcome.REFER

    def test_2_escalate_resolves_to_escalate(self) -> None:
        """2-of-3 ESCALATE votes resolve to ESCALATE outcome."""
        session = _create_test_session()
        package = _create_test_package(
            petition_id=session.petition_id,
            session_id=session.session_id,
            archons=session.assigned_archons,
        )

        archon1, archon2, archon3 = session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.ESCALATE,
            archon2: DeliberationOutcome.ESCALATE,
            archon3: DeliberationOutcome.REFER,
        }

        executor = PhaseExecutorStub.with_votes(votes)
        orchestrator = DeliberationOrchestratorService(executor)
        result = orchestrator.orchestrate(session, package)

        assert result.outcome == DeliberationOutcome.ESCALATE

    def test_3_0_vote_is_unanimous(self) -> None:
        """3-of-3 same votes are marked as unanimous."""
        session = _create_test_session()
        package = _create_test_package(
            petition_id=session.petition_id,
            session_id=session.session_id,
            archons=session.assigned_archons,
        )

        archon1, archon2, archon3 = session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.REFER,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.REFER,
        }

        executor = PhaseExecutorStub.with_votes(votes)
        orchestrator = DeliberationOrchestratorService(executor)
        result = orchestrator.orchestrate(session, package)

        assert result.outcome == DeliberationOutcome.REFER
        assert result.is_unanimous is True
        assert result.dissent_archon_id is None

    def test_2_1_vote_identifies_dissenter(self) -> None:
        """2-of-3 vote correctly identifies dissenting archon."""
        session = _create_test_session()
        package = _create_test_package(
            petition_id=session.petition_id,
            session_id=session.session_id,
            archons=session.assigned_archons,
        )

        archon1, archon2, archon3 = session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.ACKNOWLEDGE,
            archon3: DeliberationOutcome.ESCALATE,  # Dissenter
        }

        executor = PhaseExecutorStub.with_votes(votes)
        orchestrator = DeliberationOrchestratorService(executor)
        result = orchestrator.orchestrate(session, package)

        assert result.outcome == DeliberationOutcome.ACKNOWLEDGE
        assert result.is_unanimous is False
        assert result.dissent_archon_id == archon3
