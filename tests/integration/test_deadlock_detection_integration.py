"""Integration tests for deadlock detection (Story 2B.3, FR-11.10).

Tests the full deadlock detection and auto-ESCALATE flow, verifying
that 1-1-1 vote splits are handled correctly across multiple rounds.

Constitutional Constraints:
- FR-11.10: System SHALL auto-ESCALATE after 3 rounds without supermajority
- CT-11: Silent failure destroys legitimacy - deadlock MUST terminate
- CT-14: Silence is expensive - every petition terminates in witnessed fate
- AT-1: Every petition terminates in exactly one of Three Fates
- AT-6: Deliberation is collective judgment - deadlock is collective conclusion
- NFR-10.3: Consensus determinism - 100% reproducible
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.application.services.context_package_builder_service import (
    ContextPackageBuilderService,
)
from src.application.services.deadlock_handler_service import (
    DeadlockHandlerService,
)
from src.application.services.deliberation_orchestrator_service import (
    DeliberationOrchestratorService,
)
from src.config.deliberation_config import (
    SINGLE_ROUND_DELIBERATION_CONFIG,
    DeliberationConfig,
)
from src.domain.events.deadlock import (
    CrossExamineRoundTriggeredEvent,
    DeadlockDetectedEvent,
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
from src.infrastructure.stubs.deadlock_handler_stub import (
    DeadlockHandlerStub,
)
from src.infrastructure.stubs.deliberation_orchestrator_stub import (
    PhaseExecutorStub,
)


def _create_petition() -> PetitionSubmission:
    """Create a test petition submission."""
    return PetitionSubmission.create(
        id=uuid4(),
        petition_type=PetitionType.GENERAL,
        text="Test petition for deadlock testing",
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


class TestDeadlockDetectionIntegration:
    """Integration tests for deadlock detection with full orchestration."""

    def test_full_deadlock_flow_three_rounds(self) -> None:
        """Full integration test: 3 rounds of 1-1-1 splits leading to deadlock."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        package_builder = ContextPackageBuilderService()
        package = package_builder.build_package(petition, session)

        archon1, archon2, archon3 = session.assigned_archons
        # Create 1-1-1 vote split (all different outcomes)
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.ESCALATE,
        }

        config = DeliberationConfig(timeout_seconds=300, max_rounds=3)
        executor = PhaseExecutorStub.with_votes(votes)
        deadlock_handler = DeadlockHandlerStub(config=config)
        orchestrator = DeliberationOrchestratorService(
            executor,
            deadlock_handler=deadlock_handler,
            config=config,
        )

        result = orchestrator.orchestrate(session, package)

        # FR-11.10: Must auto-ESCALATE after 3 rounds
        assert result.outcome == DeliberationOutcome.ESCALATE

        # Verify events emitted
        events = deadlock_handler.get_emitted_events()
        assert len(events) == 3  # 2 round triggers + 1 deadlock

        # First two are round triggers
        assert isinstance(events[0], CrossExamineRoundTriggeredEvent)
        assert events[0].round_number == 2
        assert isinstance(events[1], CrossExamineRoundTriggeredEvent)
        assert events[1].round_number == 3

        # Last one is deadlock
        assert isinstance(events[2], DeadlockDetectedEvent)
        assert events[2].reason == "DEADLOCK_MAX_ROUNDS_EXCEEDED"

    def test_single_round_immediate_deadlock(self) -> None:
        """Integration test: Single round config causes immediate deadlock."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        package_builder = ContextPackageBuilderService()
        package = package_builder.build_package(petition, session)

        archon1, archon2, archon3 = session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.ESCALATE,
        }

        config = SINGLE_ROUND_DELIBERATION_CONFIG
        executor = PhaseExecutorStub.with_votes(votes)
        deadlock_handler = DeadlockHandlerStub(config=config)
        orchestrator = DeliberationOrchestratorService(
            executor,
            deadlock_handler=deadlock_handler,
            config=config,
        )

        result = orchestrator.orchestrate(session, package)

        # Immediate deadlock on first 1-1-1
        assert result.outcome == DeliberationOutcome.ESCALATE

        # Should only have deadlock event (no round triggers)
        events = deadlock_handler.get_emitted_events()
        assert len(events) == 1
        assert isinstance(events[0], DeadlockDetectedEvent)

    def test_consensus_reached_no_deadlock(self) -> None:
        """Integration test: 2-1 vote reaches consensus without deadlock."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        package_builder = ContextPackageBuilderService()
        package = package_builder.build_package(petition, session)

        archon1, archon2, archon3 = session.assigned_archons
        # 2-1 vote (not deadlock pattern)
        votes = {
            archon1: DeliberationOutcome.REFER,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.ACKNOWLEDGE,
        }

        executor = PhaseExecutorStub.with_votes(votes)
        deadlock_handler = DeadlockHandlerStub()
        orchestrator = DeliberationOrchestratorService(
            executor,
            deadlock_handler=deadlock_handler,
        )

        result = orchestrator.orchestrate(session, package)

        # 2-1 reaches consensus normally
        assert result.outcome == DeliberationOutcome.REFER
        assert result.dissent_archon_id == archon3

        # No deadlock events should be emitted
        events = deadlock_handler.get_emitted_events()
        assert len(events) == 0


class TestDeadlockConstitutionalCompliance:
    """Integration tests verifying constitutional compliance."""

    def test_fr_11_10_auto_escalate_mandatory(self) -> None:
        """FR-11.10: System SHALL auto-ESCALATE after 3 rounds without supermajority."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        package_builder = ContextPackageBuilderService()
        package = package_builder.build_package(petition, session)

        archon1, archon2, archon3 = session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.ESCALATE,
        }

        config = DeliberationConfig(timeout_seconds=300, max_rounds=3)
        executor = PhaseExecutorStub.with_votes(votes)
        deadlock_handler = DeadlockHandlerStub(config=config)
        orchestrator = DeliberationOrchestratorService(
            executor,
            deadlock_handler=deadlock_handler,
            config=config,
        )

        result = orchestrator.orchestrate(session, package)

        # FR-11.10: ESCALATE is mandatory after deadlock
        assert result.outcome == DeliberationOutcome.ESCALATE

    def test_ct_11_deadlock_must_terminate(self) -> None:
        """CT-11: Silent failure destroys legitimacy - deadlock MUST terminate."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        package_builder = ContextPackageBuilderService()
        package = package_builder.build_package(petition, session)

        archon1, archon2, archon3 = session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.ESCALATE,
        }

        executor = PhaseExecutorStub.with_votes(votes)
        deadlock_handler = DeadlockHandlerStub()
        orchestrator = DeliberationOrchestratorService(
            executor,
            deadlock_handler=deadlock_handler,
        )

        result = orchestrator.orchestrate(session, package)

        # CT-11: Session must have a valid outcome (no silent failure)
        assert result.outcome is not None
        assert result.outcome in (
            DeliberationOutcome.ACKNOWLEDGE,
            DeliberationOutcome.REFER,
            DeliberationOutcome.ESCALATE,
        )

    def test_at_1_petition_terminates_in_three_fates(self) -> None:
        """AT-1: Every petition terminates in exactly one of Three Fates."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        package_builder = ContextPackageBuilderService()
        package = package_builder.build_package(petition, session)

        archon1, archon2, archon3 = session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.ESCALATE,
        }

        executor = PhaseExecutorStub.with_votes(votes)
        deadlock_handler = DeadlockHandlerStub()
        orchestrator = DeliberationOrchestratorService(
            executor,
            deadlock_handler=deadlock_handler,
        )

        result = orchestrator.orchestrate(session, package)

        # AT-1: Outcome must be one of Three Fates
        assert result.outcome in (
            DeliberationOutcome.ACKNOWLEDGE,
            DeliberationOutcome.REFER,
            DeliberationOutcome.ESCALATE,
        )

    def test_nfr_10_3_deterministic_deadlock(self) -> None:
        """NFR-10.3: Consensus determinism - deadlock is reproducible."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        package_builder = ContextPackageBuilderService()
        package = package_builder.build_package(petition, session)

        archon1, archon2, archon3 = session.assigned_archons
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.REFER,
            archon3: DeliberationOutcome.ESCALATE,
        }

        # Run twice with same inputs
        config = DeliberationConfig(timeout_seconds=300, max_rounds=3)

        executor1 = PhaseExecutorStub.with_votes(votes)
        handler1 = DeadlockHandlerStub(config=config)
        orch1 = DeliberationOrchestratorService(
            executor1, deadlock_handler=handler1, config=config
        )
        result1 = orch1.orchestrate(session, package)

        executor2 = PhaseExecutorStub.with_votes(votes)
        handler2 = DeadlockHandlerStub(config=config)
        orch2 = DeliberationOrchestratorService(
            executor2, deadlock_handler=handler2, config=config
        )
        result2 = orch2.orchestrate(session, package)

        # NFR-10.3: Same inputs produce same outcome
        assert result1.outcome == result2.outcome


@pytest.mark.asyncio
class TestDeadlockServiceDirectIntegration:
    """Integration tests for DeadlockHandlerService directly."""

    async def test_service_round_progression(self) -> None:
        """Test service handles round progression correctly."""
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )
        session = (
            session.with_phase(DeliberationPhase.POSITION)
            .with_phase(DeliberationPhase.CROSS_EXAMINE)
            .with_phase(DeliberationPhase.VOTE)
        )

        service = DeadlockHandlerService()
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        # Round 1 -> 2
        updated1, event1 = await service.handle_no_consensus(
            session, vote_distribution, max_rounds=3
        )
        assert isinstance(event1, CrossExamineRoundTriggeredEvent)
        assert updated1.round_count == 2

        # Round 2 -> 3
        updated1_vote = updated1.with_phase(DeliberationPhase.VOTE)
        updated2, event2 = await service.handle_no_consensus(
            updated1_vote, vote_distribution, max_rounds=3
        )
        assert isinstance(event2, CrossExamineRoundTriggeredEvent)
        assert updated2.round_count == 3

        # Round 3 -> deadlock
        updated2_vote = updated2.with_phase(DeliberationPhase.VOTE)
        updated3, event3 = await service.handle_no_consensus(
            updated2_vote, vote_distribution, max_rounds=3
        )
        assert isinstance(event3, DeadlockDetectedEvent)
        assert updated3.is_deadlocked is True
        assert updated3.outcome == DeliberationOutcome.ESCALATE

    async def test_service_vote_history_accumulation(self) -> None:
        """Test service accumulates vote history correctly."""
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )
        session = (
            session.with_phase(DeliberationPhase.POSITION)
            .with_phase(DeliberationPhase.CROSS_EXAMINE)
            .with_phase(DeliberationPhase.VOTE)
        )

        service = DeadlockHandlerService()
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        # Round 1
        updated, _ = await service.handle_no_consensus(
            session, vote_distribution, max_rounds=3
        )
        assert len(updated.votes_by_round) == 1

        # Round 2
        updated_vote = updated.with_phase(DeliberationPhase.VOTE)
        updated, _ = await service.handle_no_consensus(
            updated_vote, vote_distribution, max_rounds=3
        )
        assert len(updated.votes_by_round) == 2

        # Round 3 (deadlock)
        updated_vote = updated.with_phase(DeliberationPhase.VOTE)
        updated, event = await service.handle_no_consensus(
            updated_vote, vote_distribution, max_rounds=3
        )

        # Deadlock event should have all 3 rounds of votes
        assert isinstance(event, DeadlockDetectedEvent)
        assert len(event.votes_by_round) == 3
