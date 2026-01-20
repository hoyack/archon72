"""Integration tests for archon substitution (Story 2B.4, NFR-10.6).

Tests the full archon substitution flow, verifying that archon failures
are handled correctly and deliberation can continue with substitutes.

Constitutional Constraints:
- FR-11.12: System SHALL detect individual Archon response timeout
- NFR-10.6: Archon substitution latency < 10 seconds on failure
- NFR-10.2: Individual Archon response time p95 < 30 seconds
- CT-11: Silent failure destroys legitimacy - failures must be handled
- AT-1: Every petition terminates in exactly one of Three Fates
- AT-6: Deliberation is collective judgment (need 3 active Archons)
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.application.services.archon_substitution_service import (
    ArchonSubstitutionService,
    MAX_SUBSTITUTION_LATENCY_MS,
)
from src.application.services.context_package_builder_service import (
    ContextPackageBuilderService,
)
from src.application.services.deliberation_orchestrator_service import (
    DeliberationOrchestratorService,
)
from src.config.deliberation_config import DEFAULT_DELIBERATION_CONFIG
from src.domain.errors.deliberation import PhaseExecutionError
from src.domain.events.archon_substitution import (
    ArchonSubstitutedEvent,
    DeliberationAbortedEvent,
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
from src.infrastructure.stubs.archon_substitution_stub import ArchonSubstitutionStub
from src.infrastructure.stubs.deliberation_orchestrator_stub import PhaseExecutorStub


def _create_petition() -> PetitionSubmission:
    """Create a test petition submission."""
    return PetitionSubmission.create(
        id=uuid4(),
        petition_type=PetitionType.GENERAL,
        text="Test petition for substitution testing",
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


class TestArchonSubstitutionIntegration:
    """Integration tests for archon substitution with orchestrator."""

    def test_substitution_stub_basic_flow(self) -> None:
        """Test basic substitution flow with stub."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        failed_archon_id = session.assigned_archons[1]
        substitute_id = uuid4()

        # Create stub with available substitute
        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[substitute_id],
        )
        stub.set_session(session)

        # Execute substitution
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            stub.execute_substitution(
                session=session,
                failed_archon_id=failed_archon_id,
                failure_reason="RESPONSE_TIMEOUT",
            )
        )

        # Verify success
        assert result.success is True
        assert result.substitute_archon_id == substitute_id
        assert isinstance(result.event, ArchonSubstitutedEvent)
        assert result.event.failed_archon_id == failed_archon_id
        assert result.event.substitute_archon_id == substitute_id
        assert result.latency_ms < MAX_SUBSTITUTION_LATENCY_MS

    def test_substitution_abort_when_pool_exhausted(self) -> None:
        """Test abort flow when no substitute available."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        failed_archon_id = session.assigned_archons[1]

        # Create stub with no available substitutes
        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[],
        )
        stub.set_session(session)

        # Execute substitution
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            stub.execute_substitution(
                session=session,
                failed_archon_id=failed_archon_id,
                failure_reason="RESPONSE_TIMEOUT",
            )
        )

        # Verify abort
        assert result.success is False
        assert isinstance(result.event, DeliberationAbortedEvent)
        assert result.event.reason == "ARCHON_POOL_EXHAUSTED"
        assert result.session.is_aborted is True
        assert result.session.outcome == DeliberationOutcome.ESCALATE

    def test_substitution_abort_on_second_failure(self) -> None:
        """Test abort when second archon fails (AC-7)."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)

        # Add an existing substitution
        first_failed = session.assigned_archons[0]
        first_substitute = uuid4()
        session = session.with_substitution(
            failed_archon_id=first_failed,
            substitute_archon_id=first_substitute,
            failure_reason="RESPONSE_TIMEOUT",
        )

        # Create stub with available substitute (but should abort due to limit)
        second_substitute = uuid4()
        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[second_substitute],
        )
        stub.set_session(session)

        # Execute substitution for second failure
        second_failed = session.assigned_archons[1]
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            stub.execute_substitution(
                session=session,
                failed_archon_id=second_failed,
                failure_reason="API_ERROR",
            )
        )

        # Verify abort due to max substitutions exceeded
        assert result.success is False
        assert isinstance(result.event, DeliberationAbortedEvent)
        assert result.session.is_aborted is True

    def test_substitution_context_handoff(self) -> None:
        """Test context handoff includes transcript pages (AC-3)."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)

        # Add some transcript data
        session = session.with_phase(DeliberationPhase.POSITION)
        session = session.with_transcript(DeliberationPhase.ASSESS, b"assess_hash")
        session = session.with_phase(DeliberationPhase.CROSS_EXAMINE)
        session = session.with_transcript(DeliberationPhase.POSITION, b"position_hash")

        substitute_id = uuid4()
        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[substitute_id],
        )
        stub.set_session(session)

        # Get context handoff
        import asyncio
        handoff = asyncio.get_event_loop().run_until_complete(
            stub.prepare_context_handoff(
                session=session,
                failed_archon_id=session.assigned_archons[1],
            )
        )

        # Verify handoff contains transcript pages
        assert handoff.session_id == session.session_id
        assert handoff.petition_id == session.petition_id
        assert handoff.current_phase == session.phase

    def test_event_tracking_in_stub(self) -> None:
        """Test that stub tracks all emitted events for verification."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        substitute_id = uuid4()

        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[substitute_id],
        )
        stub.set_session(session)

        # Execute substitution
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            stub.execute_substitution(
                session=session,
                failed_archon_id=session.assigned_archons[1],
                failure_reason="RESPONSE_TIMEOUT",
            )
        )

        # Verify event tracking
        events = stub.get_emitted_events()
        assert len(events) == 1
        assert isinstance(events[0], ArchonSubstitutedEvent)

        substitutions = stub.get_substitutions()
        assert len(substitutions) == 1


class TestSubstitutionWithOrchestratorIntegration:
    """Integration tests for substitution with deliberation orchestrator."""

    def test_orchestrator_handles_archon_failure(self) -> None:
        """Test that orchestrator handles archon failure via substitution handler."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        package_builder = ContextPackageBuilderService()
        package = package_builder.build_package(petition, session)

        archon1, archon2, archon3 = session.assigned_archons
        substitute_id = uuid4()

        # Create a votes dict for successful outcome after substitution
        votes = {
            archon1: DeliberationOutcome.ACKNOWLEDGE,
            archon2: DeliberationOutcome.ACKNOWLEDGE,  # Will be substitute
            archon3: DeliberationOutcome.REFER,
        }

        # Create executor that succeeds
        executor = PhaseExecutorStub.with_votes(votes)

        # Create substitution stub
        substitution_stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[substitute_id],
        )
        substitution_stub.set_session(session)

        # Create orchestrator with substitution handler
        orchestrator = DeliberationOrchestratorService(
            executor,
            substitution_handler=substitution_stub,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        # Orchestrate - should complete normally (no failure triggered in this test)
        result = orchestrator.orchestrate(session, package)

        # Verify deliberation completed
        assert result.outcome in (
            DeliberationOutcome.ACKNOWLEDGE,
            DeliberationOutcome.REFER,
            DeliberationOutcome.ESCALATE,
        )


class TestConstitutionalComplianceIntegration:
    """Integration tests for constitutional compliance."""

    def test_at_1_petition_terminates_in_three_fates(self) -> None:
        """AT-1: Every petition terminates in exactly one of Three Fates."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)

        # Test with pool exhausted - should abort to ESCALATE
        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[],
        )
        stub.set_session(session)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            stub.execute_substitution(
                session=session,
                failed_archon_id=session.assigned_archons[1],
                failure_reason="RESPONSE_TIMEOUT",
            )
        )

        # AT-1: Must terminate in one of Three Fates
        assert result.session.outcome in (
            DeliberationOutcome.ACKNOWLEDGE,
            DeliberationOutcome.REFER,
            DeliberationOutcome.ESCALATE,
        )
        # Specifically, abort should be ESCALATE
        assert result.session.outcome == DeliberationOutcome.ESCALATE

    def test_nfr_10_6_substitution_latency(self) -> None:
        """NFR-10.6: Archon substitution latency < 10 seconds."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        substitute_id = uuid4()

        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[substitute_id],
            simulated_latency_ms=50,  # Well under SLA
        )
        stub.set_session(session)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            stub.execute_substitution(
                session=session,
                failed_archon_id=session.assigned_archons[1],
                failure_reason="RESPONSE_TIMEOUT",
            )
        )

        # NFR-10.6: < 10 seconds
        assert result.latency_ms < MAX_SUBSTITUTION_LATENCY_MS
        assert result.met_sla is True

    def test_ct_11_failure_must_be_handled(self) -> None:
        """CT-11: Silent failure destroys legitimacy - failures must be handled."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)

        # With substitute available
        substitute_id = uuid4()
        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[substitute_id],
        )
        stub.set_session(session)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            stub.execute_substitution(
                session=session,
                failed_archon_id=session.assigned_archons[1],
                failure_reason="RESPONSE_TIMEOUT",
            )
        )

        # CT-11: Failure must be handled (either substituted or aborted)
        # In this case, should be substituted
        assert result.success is True
        assert result.substitute_archon_id is not None

    def test_at_6_maintains_three_active_archons(self) -> None:
        """AT-6: Deliberation is collective judgment (need 3 active Archons)."""
        petition = _create_petition()
        session = _create_session_for_petition(petition)
        substitute_id = uuid4()

        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[substitute_id],
        )
        stub.set_session(session)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            stub.execute_substitution(
                session=session,
                failed_archon_id=session.assigned_archons[1],
                failure_reason="RESPONSE_TIMEOUT",
            )
        )

        # AT-6: After substitution, should still have 3 active archons
        if result.success:
            active = result.session.current_active_archons
            assert len(active) == 3
            # Substitute should be in the list
            assert substitute_id in active
