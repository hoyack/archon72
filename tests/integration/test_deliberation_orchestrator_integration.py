"""Integration tests for deliberation orchestrator (Story 2A.4, FR-11.4).

Tests the full deliberation orchestration flow with stub executor,
verifying phase execution, transcript recording, and outcome resolution.

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

from src.application.services.context_package_builder_service import (
    ContextPackageBuilderService,
)
from src.application.services.deliberation_orchestrator_service import (
    DeliberationOrchestratorService,
)
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)
from src.domain.models.petition_submission import (
    PetitionSubmission,
    PetitionType,
)
from src.infrastructure.stubs.deliberation_orchestrator_stub import (
    DeliberationOrchestratorStub,
    PhaseExecutorStub,
)


def _create_petition() -> PetitionSubmission:
    """Create a test petition submission."""
    return PetitionSubmission.create(
        id=uuid4(),
        petition_type=PetitionType.GENERAL,
        text="Test petition requesting system improvement",
        submitter_id=uuid4(),
        realm="test-realm",
    )


def _create_session_for_petition(petition: PetitionSubmission) -> DeliberationSession:
    """Create a deliberation session for a petition."""
    archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
    return DeliberationSession.create(
        session_id=uuid4(),
        petition_id=petition.id,
        assigned_archons=(archon1, archon2, archon3),
    )


class TestDeliberationOrchestratorIntegration:
    """Integration tests for full orchestration flow."""

    def test_full_orchestration_with_context_builder(self) -> None:
        """Full integration test with context package builder and orchestrator."""
        # Create petition
        petition = _create_petition()

        # Create session
        session = _create_session_for_petition(petition)

        # Build context package
        package_builder = ContextPackageBuilderService()
        package = package_builder.build_package(petition, session)

        # Verify package-session relationship
        assert package.petition_id == session.petition_id
        assert package.session_id == session.session_id

        # Orchestrate deliberation
        executor = PhaseExecutorStub()
        orchestrator = DeliberationOrchestratorService(executor)
        result = orchestrator.orchestrate(session, package)

        # Verify outcome
        assert result.outcome == DeliberationOutcome.ACKNOWLEDGE
        assert result.session_id == session.session_id
        assert result.petition_id == petition.id

        # Verify all phases completed
        assert len(result.phase_results) == 4
        assert all(
            pr.phase == expected
            for pr, expected in zip(
                result.phase_results,
                [
                    DeliberationPhase.ASSESS,
                    DeliberationPhase.POSITION,
                    DeliberationPhase.CROSS_EXAMINE,
                    DeliberationPhase.VOTE,
                ],
            )
        )

    def test_stub_orchestrator_convenience_methods(self) -> None:
        """Test DeliberationOrchestratorStub convenience factory methods."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        package_builder = ContextPackageBuilderService()
        package = package_builder.build_package(petition, session)

        # Test default stub
        orchestrator_default = DeliberationOrchestratorStub.default()
        result_default = orchestrator_default.orchestrate(session, package)
        assert result_default.outcome == DeliberationOutcome.ACKNOWLEDGE
        assert result_default.is_unanimous

        # Test with unanimous vote
        orchestrator_escalate = DeliberationOrchestratorStub.with_unanimous_vote(
            DeliberationOutcome.ESCALATE
        )
        result_escalate = orchestrator_escalate.orchestrate(session, package)
        assert result_escalate.outcome == DeliberationOutcome.ESCALATE
        assert result_escalate.is_unanimous

    def test_stub_orchestrator_custom_votes(self) -> None:
        """Test DeliberationOrchestratorStub with custom votes."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        package_builder = ContextPackageBuilderService()
        package = package_builder.build_package(petition, session)

        archon1, archon2, archon3 = session.assigned_archons
        custom_votes = {
            archon1: DeliberationOutcome.REFER,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.ESCALATE,
        }

        orchestrator = DeliberationOrchestratorStub.with_votes(custom_votes)
        result = orchestrator.orchestrate(session, package)

        assert result.outcome == DeliberationOutcome.REFER
        assert not result.is_unanimous
        assert result.dissent_archon_id == archon3

    def test_transcript_hash_integrity(self) -> None:
        """Verify transcript hashes are recorded for witness verification."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        package_builder = ContextPackageBuilderService()
        package = package_builder.build_package(petition, session)

        orchestrator = DeliberationOrchestratorStub.default()
        result = orchestrator.orchestrate(session, package)

        # Each phase should have valid 32-byte hash (Blake3/SHA-256)
        for phase_result in result.phase_results:
            assert len(phase_result.transcript_hash) == 32
            assert phase_result.transcript != ""

    def test_phase_metadata_captured(self) -> None:
        """Verify phase-specific metadata is captured for reporting."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        package_builder = ContextPackageBuilderService()
        package = package_builder.build_package(petition, session)

        orchestrator = DeliberationOrchestratorStub.default()
        result = orchestrator.orchestrate(session, package)

        # ASSESS metadata
        assess = result.get_phase_result(DeliberationPhase.ASSESS)
        assert assess is not None
        assert "assessments_completed" in assess.phase_metadata

        # POSITION metadata
        position = result.get_phase_result(DeliberationPhase.POSITION)
        assert position is not None
        assert "positions_converged" in position.phase_metadata

        # CROSS_EXAMINE metadata
        cross_examine = result.get_phase_result(DeliberationPhase.CROSS_EXAMINE)
        assert cross_examine is not None
        assert "challenges_raised" in cross_examine.phase_metadata
        assert "rounds_completed" in cross_examine.phase_metadata

        # VOTE metadata
        vote = result.get_phase_result(DeliberationPhase.VOTE)
        assert vote is not None
        assert "votes" in vote.phase_metadata
        assert "vote_counts" in vote.phase_metadata

    def test_all_petition_types_can_deliberate(self) -> None:
        """Verify all petition types can go through deliberation."""
        for petition_type in PetitionType:
            petition = PetitionSubmission.create(
                id=uuid4(),
                petition_type=petition_type,
                text=f"Test petition of type {petition_type.value}",
                submitter_id=uuid4(),
                realm="test-realm",
            )
            session = _create_session_for_petition(petition)
            package_builder = ContextPackageBuilderService()
            package = package_builder.build_package(petition, session)

            orchestrator = DeliberationOrchestratorStub.default()
            result = orchestrator.orchestrate(session, package)

            assert result.outcome is not None
            assert result.petition_id == petition.id


class TestDeliberationDeterminism:
    """Tests for NFR-10.3 consensus determinism."""

    def test_same_inputs_same_outcome(self) -> None:
        """Same inputs always produce same outcome (determinism)."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        package_builder = ContextPackageBuilderService()
        package = package_builder.build_package(petition, session)

        archon1, archon2, archon3 = session.assigned_archons
        fixed_votes = {
            archon1: DeliberationOutcome.ESCALATE,
            archon2: DeliberationOutcome.ACKNOWLEDGE,
            archon3: DeliberationOutcome.ESCALATE,
        }

        # Run 3 times with same inputs
        results = []
        for _ in range(3):
            orchestrator = DeliberationOrchestratorStub.with_votes(fixed_votes)
            result = orchestrator.orchestrate(session, package)
            results.append(result)

        # All outcomes must be identical
        assert all(r.outcome == DeliberationOutcome.ESCALATE for r in results)
        assert all(r.dissent_archon_id == archon2 for r in results)
        assert all(r.is_unanimous is False for r in results)

    def test_vote_order_independent(self) -> None:
        """Outcome is independent of vote processing order."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        package_builder = ContextPackageBuilderService()
        package = package_builder.build_package(petition, session)

        archon1, archon2, archon3 = session.assigned_archons

        # Same votes, different dict construction order
        votes1 = {
            archon1: DeliberationOutcome.REFER,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.ACKNOWLEDGE,
        }
        votes2 = {
            archon3: DeliberationOutcome.ACKNOWLEDGE,
            archon1: DeliberationOutcome.REFER,
            archon2: DeliberationOutcome.REFER,
        }

        orchestrator1 = DeliberationOrchestratorStub.with_votes(votes1)
        result1 = orchestrator1.orchestrate(session, package)

        orchestrator2 = DeliberationOrchestratorStub.with_votes(votes2)
        result2 = orchestrator2.orchestrate(session, package)

        # Outcomes must match regardless of dict order
        assert result1.outcome == result2.outcome == DeliberationOutcome.REFER
        assert result1.dissent_archon_id == result2.dissent_archon_id == archon3
