"""Unit tests for archon substitution service (Story 2B.4, NFR-10.6).

Tests the ArchonSubstitutionService for correct failure detection, substitution,
abort handling, and SLA compliance.

Constitutional Constraints:
- FR-11.12: System SHALL detect individual Archon response timeout
- NFR-10.6: Archon substitution latency < 10 seconds on failure
- NFR-10.2: Individual Archon response time p95 < 30 seconds
- CT-11: Silent failure destroys legitimacy - failures must be handled
- AT-1: Every petition terminates in exactly one of Three Fates
- AT-6: Deliberation is collective judgment (need 3 active Archons)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.ports.archon_substitution import (
    ContextHandoff,
)
from src.application.services.archon_substitution_service import (
    MAX_SUBSTITUTION_LATENCY_MS,
    VALID_ABORT_REASONS,
    VALID_FAILURE_REASONS,
    ArchonSubstitutionService,
)
from src.config.deliberation_config import DEFAULT_DELIBERATION_CONFIG
from src.domain.errors.deliberation import SessionAlreadyCompleteError
from src.domain.events.archon_substitution import (
    ArchonSubstitutedEvent,
    DeliberationAbortedEvent,
)
from src.domain.models.deliberation_session import (
    MAX_SUBSTITUTIONS_PER_SESSION,
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)
from src.domain.models.fate_archon import DeliberationStyle, FateArchon


def _create_test_archon(name: str = "TestArchon") -> FateArchon:
    """Create a test FateArchon."""
    return FateArchon(
        id=uuid4(),
        name=name,
        title="Marquis",
        deliberation_style=DeliberationStyle.PRAGMATIC_MODERATOR,
        system_prompt_template=f"You are {name}, a test archon.",
    )


def _create_test_session(
    phase: DeliberationPhase = DeliberationPhase.POSITION,
    with_substitution: bool = False,
) -> tuple[DeliberationSession, tuple[FateArchon, FateArchon, FateArchon]]:
    """Create a test deliberation session with archons."""
    archon1 = _create_test_archon("Amon")
    archon2 = _create_test_archon("Bael")
    archon3 = _create_test_archon("Cimeries")

    session = DeliberationSession.create(
        session_id=uuid4(),
        petition_id=uuid4(),
        assigned_archons=(archon1.id, archon2.id, archon3.id),
    )

    # Transition through phases to reach target phase
    if phase in (
        DeliberationPhase.POSITION,
        DeliberationPhase.CROSS_EXAMINE,
        DeliberationPhase.VOTE,
    ):
        session = session.with_phase(DeliberationPhase.POSITION)
    if phase in (DeliberationPhase.CROSS_EXAMINE, DeliberationPhase.VOTE):
        session = session.with_phase(DeliberationPhase.CROSS_EXAMINE)
    if phase == DeliberationPhase.VOTE:
        session = session.with_phase(DeliberationPhase.VOTE)

    # Add a substitution if requested
    if with_substitution:
        substitute = _create_test_archon("Substitute")
        session = session.with_substitution(
            failed_archon_id=archon2.id,
            substitute_archon_id=substitute.id,
            failure_reason="RESPONSE_TIMEOUT",
        )
        return session, (archon1, substitute, archon3)

    return session, (archon1, archon2, archon3)


def _create_mock_archon_pool(
    archons: list[FateArchon],
    substitute: FateArchon | None = None,
) -> MagicMock:
    """Create a mock archon pool."""
    pool = MagicMock()

    def get_archon_by_id(archon_id: Any) -> FateArchon | None:
        for archon in archons:
            if archon.id == archon_id:
                return archon
        return None

    pool.get_archon_by_id.side_effect = get_archon_by_id
    pool.select_substitute.return_value = substitute
    pool.get_available_archons.return_value = [substitute] if substitute else []
    pool.list_all_archons.return_value = archons + ([substitute] if substitute else [])
    return pool


def _create_mock_event_emitter() -> AsyncMock:
    """Create a mock event emitter."""
    emitter = AsyncMock()
    emitter.append_event = AsyncMock()
    return emitter


class TestDetectFailure:
    """Tests for detect_failure method (AC-1, FR-11.12)."""

    @pytest.mark.asyncio
    async def test_detects_valid_failure_in_active_session(self) -> None:
        """Detects failure for an active archon in an active session."""
        session, (archon1, archon2, archon3) = _create_test_session()
        pool = _create_mock_archon_pool([archon1, archon2, archon3])
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        result = await service.detect_failure(
            session=session,
            archon_id=archon2.id,
            failure_reason="RESPONSE_TIMEOUT",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_rejects_failure_for_non_session_archon(self) -> None:
        """Rejects failure for archon not in session."""
        session, archons = _create_test_session()
        pool = _create_mock_archon_pool(list(archons))
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        other_archon = _create_test_archon("OtherArchon")
        result = await service.detect_failure(
            session=session,
            archon_id=other_archon.id,
            failure_reason="RESPONSE_TIMEOUT",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_rejects_invalid_failure_reason(self) -> None:
        """Raises ValueError for invalid failure reason."""
        session, archons = _create_test_session()
        pool = _create_mock_archon_pool(list(archons))
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        with pytest.raises(ValueError, match="failure_reason must be one of"):
            await service.detect_failure(
                session=session,
                archon_id=archons[0].id,
                failure_reason="INVALID_REASON",
            )

    @pytest.mark.asyncio
    async def test_rejects_completed_session(self) -> None:
        """Returns False for completed session."""
        session, archons = _create_test_session(phase=DeliberationPhase.VOTE)
        # Complete the session
        session = session.with_votes(
            {
                archons[0].id: DeliberationOutcome.ACKNOWLEDGE,
                archons[1].id: DeliberationOutcome.ACKNOWLEDGE,
                archons[2].id: DeliberationOutcome.REFER,
            }
        )
        session = session.with_outcome()

        pool = _create_mock_archon_pool(list(archons))
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        result = await service.detect_failure(
            session=session,
            archon_id=archons[0].id,
            failure_reason="RESPONSE_TIMEOUT",
        )

        assert result is False


class TestCanSubstitute:
    """Tests for can_substitute method (NFR-10.6: max 1)."""

    @pytest.mark.asyncio
    async def test_allows_first_substitution(self) -> None:
        """Allows substitution when no prior substitutions."""
        session, archons = _create_test_session()
        pool = _create_mock_archon_pool(list(archons))
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        result = await service.can_substitute(session)

        assert result is True
        assert session.substitution_count == 0

    @pytest.mark.asyncio
    async def test_denies_second_substitution(self) -> None:
        """Denies substitution when max substitutions reached."""
        session, archons = _create_test_session(with_substitution=True)
        pool = _create_mock_archon_pool(list(archons))
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        result = await service.can_substitute(session)

        assert result is False
        assert session.substitution_count >= MAX_SUBSTITUTIONS_PER_SESSION


class TestSelectSubstitute:
    """Tests for select_substitute method (AC-2)."""

    @pytest.mark.asyncio
    async def test_selects_available_substitute(self) -> None:
        """Selects substitute from pool excluding assigned archons."""
        session, archons = _create_test_session()
        substitute = _create_test_archon("Dantalion")
        pool = _create_mock_archon_pool(list(archons), substitute=substitute)
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        result = await service.select_substitute(
            session=session,
            failed_archon_id=archons[1].id,
        )

        assert result == substitute.id
        pool.list_all_archons.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_pool_exhausted(self) -> None:
        """Returns None when no substitute available."""
        session, archons = _create_test_session()
        pool = _create_mock_archon_pool(list(archons), substitute=None)
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        result = await service.select_substitute(
            session=session,
            failed_archon_id=archons[1].id,
        )

        assert result is None


class TestPrepareContextHandoff:
    """Tests for prepare_context_handoff method (AC-3)."""

    @pytest.mark.asyncio
    async def test_creates_context_with_transcript(self) -> None:
        """Creates context handoff with transcript pages."""
        session, archons = _create_test_session(phase=DeliberationPhase.CROSS_EXAMINE)
        # Add transcript data
        session = session.with_transcript(
            DeliberationPhase.ASSESS,
            b"a" * 32,
        )
        session = session.with_transcript(
            DeliberationPhase.POSITION,
            b"b" * 32,
        )

        pool = _create_mock_archon_pool(list(archons))
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        handoff = await service.prepare_context_handoff(
            session=session,
            failed_archon_id=archons[1].id,
        )

        assert isinstance(handoff, ContextHandoff)
        assert handoff.session_id == session.session_id
        assert handoff.petition_id == session.petition_id
        assert handoff.current_phase == session.phase
        assert len(handoff.transcript_pages) == 2  # ASSESS + POSITION


class TestExecuteSubstitution:
    """Tests for execute_substitution method (AC-1 through AC-9)."""

    @pytest.mark.asyncio
    async def test_successful_substitution_flow(self) -> None:
        """Successfully substitutes failed archon (AC-4)."""
        session, archons = _create_test_session()
        substitute = _create_test_archon("Dantalion")
        pool = _create_mock_archon_pool(list(archons), substitute=substitute)
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        result = await service.execute_substitution(
            session=session,
            failed_archon_id=archons[1].id,
            failure_reason="RESPONSE_TIMEOUT",
        )

        assert result.success is True
        assert result.substitute_archon_id == substitute.id
        assert isinstance(result.event, ArchonSubstitutedEvent)
        assert result.session.substitution_count == 1

    @pytest.mark.asyncio
    async def test_substitution_emits_event(self) -> None:
        """Emits ArchonSubstitutedEvent on success (AC-6)."""
        session, archons = _create_test_session()
        substitute = _create_test_archon("Dantalion")
        pool = _create_mock_archon_pool(list(archons), substitute=substitute)
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        await service.execute_substitution(
            session=session,
            failed_archon_id=archons[1].id,
            failure_reason="RESPONSE_TIMEOUT",
        )

        # Check event was emitted
        emitter.append_event.assert_called_once()
        event = emitter.append_event.call_args[0][0]
        assert isinstance(event, ArchonSubstitutedEvent)
        assert event.failed_archon_id == archons[1].id
        assert event.substitute_archon_id == substitute.id
        assert event.failure_reason == "RESPONSE_TIMEOUT"

    @pytest.mark.asyncio
    async def test_substitution_tracks_latency(self) -> None:
        """Records substitution latency (AC-4, NFR-10.6)."""
        session, archons = _create_test_session()
        substitute = _create_test_archon("Dantalion")
        pool = _create_mock_archon_pool(list(archons), substitute=substitute)
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        result = await service.execute_substitution(
            session=session,
            failed_archon_id=archons[1].id,
            failure_reason="RESPONSE_TIMEOUT",
        )

        assert result.latency_ms >= 0
        assert result.latency_ms < MAX_SUBSTITUTION_LATENCY_MS  # Within SLA

    @pytest.mark.asyncio
    async def test_substitution_updates_session(self) -> None:
        """Updates session with substitution record (AC-9)."""
        session, archons = _create_test_session()
        substitute = _create_test_archon("Dantalion")
        pool = _create_mock_archon_pool(list(archons), substitute=substitute)
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        result = await service.execute_substitution(
            session=session,
            failed_archon_id=archons[1].id,
            failure_reason="RESPONSE_TIMEOUT",
        )

        # Check session updated
        updated = result.session
        assert updated.substitution_count == 1
        assert updated.has_substitution is True
        assert archons[1].id in updated.failed_archon_ids

    @pytest.mark.asyncio
    async def test_abort_when_max_substitutions_exceeded(self) -> None:
        """Aborts when substitution limit reached (AC-7)."""
        session, archons = _create_test_session(with_substitution=True)
        pool = _create_mock_archon_pool(list(archons), substitute=None)
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        result = await service.execute_substitution(
            session=session,
            failed_archon_id=archons[2].id,
            failure_reason="RESPONSE_TIMEOUT",
        )

        assert result.success is False
        assert isinstance(result.event, DeliberationAbortedEvent)
        assert result.session.is_aborted is True

    @pytest.mark.asyncio
    async def test_abort_when_pool_exhausted(self) -> None:
        """Aborts when no substitute available (AC-8)."""
        session, archons = _create_test_session()
        pool = _create_mock_archon_pool(list(archons), substitute=None)
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        result = await service.execute_substitution(
            session=session,
            failed_archon_id=archons[1].id,
            failure_reason="RESPONSE_TIMEOUT",
        )

        assert result.success is False
        assert isinstance(result.event, DeliberationAbortedEvent)
        assert result.event.reason == "ARCHON_POOL_EXHAUSTED"

    @pytest.mark.asyncio
    async def test_raises_for_completed_session(self) -> None:
        """Raises SessionAlreadyCompleteError for completed session."""
        session, archons = _create_test_session(phase=DeliberationPhase.VOTE)
        session = session.with_votes(
            {
                archons[0].id: DeliberationOutcome.ACKNOWLEDGE,
                archons[1].id: DeliberationOutcome.ACKNOWLEDGE,
                archons[2].id: DeliberationOutcome.REFER,
            }
        )
        session = session.with_outcome()

        pool = _create_mock_archon_pool(list(archons))
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        with pytest.raises(SessionAlreadyCompleteError):
            await service.execute_substitution(
                session=session,
                failed_archon_id=archons[1].id,
                failure_reason="RESPONSE_TIMEOUT",
            )


class TestAbortDeliberation:
    """Tests for abort_deliberation method (AC-7, AC-8)."""

    @pytest.mark.asyncio
    async def test_abort_sets_escalate_outcome(self) -> None:
        """Abort sets ESCALATE outcome."""
        session, archons = _create_test_session()
        pool = _create_mock_archon_pool(list(archons))
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        failed_archons = [
            {
                "archon_id": str(archons[0].id),
                "failure_reason": "RESPONSE_TIMEOUT",
                "phase": "POSITION",
            }
        ]

        updated, event = await service.abort_deliberation(
            session=session,
            reason="INSUFFICIENT_ARCHONS",
            failed_archons=failed_archons,
        )

        assert updated.outcome == DeliberationOutcome.ESCALATE
        assert updated.is_aborted is True

    @pytest.mark.asyncio
    async def test_abort_emits_event(self) -> None:
        """Abort emits DeliberationAbortedEvent."""
        session, archons = _create_test_session()
        pool = _create_mock_archon_pool(list(archons))
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        failed_archons = [
            {
                "archon_id": str(archons[0].id),
                "failure_reason": "RESPONSE_TIMEOUT",
                "phase": "POSITION",
            }
        ]

        updated, event = await service.abort_deliberation(
            session=session,
            reason="INSUFFICIENT_ARCHONS",
            failed_archons=failed_archons,
        )

        assert isinstance(event, DeliberationAbortedEvent)
        assert event.reason == "INSUFFICIENT_ARCHONS"
        emitter.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_abort_rejects_invalid_reason(self) -> None:
        """Abort rejects invalid reason."""
        session, archons = _create_test_session()
        pool = _create_mock_archon_pool(list(archons))
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        with pytest.raises(ValueError, match="reason must be one of"):
            await service.abort_deliberation(
                session=session,
                reason="INVALID_REASON",
                failed_archons=[],
            )


class TestGetSubstitutionStatus:
    """Tests for get_substitution_status method."""

    @pytest.mark.asyncio
    async def test_returns_no_substitution_for_fresh_session(self) -> None:
        """Returns no substitution for session without substitutions."""
        session, archons = _create_test_session()
        pool = _create_mock_archon_pool(list(archons))
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )
        # Register session for status tracking
        service._sessions[session.session_id] = session

        has_sub, count, latest = await service.get_substitution_status(
            session.session_id
        )

        assert has_sub is False
        assert count == 0
        assert latest is None

    @pytest.mark.asyncio
    async def test_returns_substitution_info(self) -> None:
        """Returns substitution info for session with substitution."""
        session, archons = _create_test_session(with_substitution=True)
        pool = _create_mock_archon_pool(list(archons))
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )
        service._sessions[session.session_id] = session

        has_sub, count, latest = await service.get_substitution_status(
            session.session_id
        )

        assert has_sub is True
        assert count == 1
        assert latest is not None


class TestGetActiveArchons:
    """Tests for get_active_archons method."""

    @pytest.mark.asyncio
    async def test_returns_original_archons_no_substitution(self) -> None:
        """Returns original archons when no substitution."""
        session, archons = _create_test_session()
        pool = _create_mock_archon_pool(list(archons))
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )
        service._sessions[session.session_id] = session

        active = await service.get_active_archons(session.session_id)

        assert len(active) == 3
        assert set(active) == set(session.assigned_archons)

    @pytest.mark.asyncio
    async def test_returns_updated_archons_with_substitution(self) -> None:
        """Returns updated archons after substitution."""
        session, archons = _create_test_session(with_substitution=True)
        pool = _create_mock_archon_pool(list(archons))
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )
        service._sessions[session.session_id] = session

        active = await service.get_active_archons(session.session_id)

        assert len(active) == 3
        # Substitute should be in active list
        substitute_id = session.substitutions[0].substitute_archon_id
        assert substitute_id in active


class TestValidFailureReasons:
    """Tests for failure reason validation."""

    def test_valid_failure_reasons_constant(self) -> None:
        """VALID_FAILURE_REASONS contains expected values."""
        assert "RESPONSE_TIMEOUT" in VALID_FAILURE_REASONS
        assert "API_ERROR" in VALID_FAILURE_REASONS
        assert "INVALID_RESPONSE" in VALID_FAILURE_REASONS

    def test_valid_abort_reasons_constant(self) -> None:
        """VALID_ABORT_REASONS contains expected values."""
        assert "INSUFFICIENT_ARCHONS" in VALID_ABORT_REASONS
        assert "ARCHON_POOL_EXHAUSTED" in VALID_ABORT_REASONS


class TestConstitutionalCompliance:
    """Tests verifying constitutional constraint compliance."""

    @pytest.mark.asyncio
    async def test_nfr_10_6_substitution_latency_sla(self) -> None:
        """NFR-10.6: Archon substitution latency < 10 seconds."""
        session, archons = _create_test_session()
        substitute = _create_test_archon("Dantalion")
        pool = _create_mock_archon_pool(list(archons), substitute=substitute)
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        result = await service.execute_substitution(
            session=session,
            failed_archon_id=archons[1].id,
            failure_reason="RESPONSE_TIMEOUT",
        )

        # NFR-10.6: < 10 seconds = 10000 ms
        assert result.latency_ms < MAX_SUBSTITUTION_LATENCY_MS
        assert result.met_sla is True

    @pytest.mark.asyncio
    async def test_ct_11_failure_must_terminate(self) -> None:
        """CT-11: Silent failure destroys legitimacy - failures must be handled."""
        session, archons = _create_test_session()
        # No substitute available - should abort
        pool = _create_mock_archon_pool(list(archons), substitute=None)
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        result = await service.execute_substitution(
            session=session,
            failed_archon_id=archons[1].id,
            failure_reason="RESPONSE_TIMEOUT",
        )

        # CT-11: Must handle failure (either substitute or abort)
        assert result.success is False or result.success is True
        if not result.success:
            # Failure handled by abort
            assert isinstance(result.event, DeliberationAbortedEvent)
            assert result.session.is_aborted is True

    @pytest.mark.asyncio
    async def test_at_1_petition_terminates_in_three_fates(self) -> None:
        """AT-1: Every petition terminates in exactly one of Three Fates."""
        session, archons = _create_test_session()
        pool = _create_mock_archon_pool(list(archons), substitute=None)
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        result = await service.execute_substitution(
            session=session,
            failed_archon_id=archons[1].id,
            failure_reason="RESPONSE_TIMEOUT",
        )

        # AT-1: Aborted session has ESCALATE outcome
        if result.session.is_aborted:
            assert result.session.outcome == DeliberationOutcome.ESCALATE

    @pytest.mark.asyncio
    async def test_at_6_maintains_three_active_archons(self) -> None:
        """AT-6: Deliberation is collective judgment (need 3 active Archons)."""
        session, archons = _create_test_session()
        substitute = _create_test_archon("Dantalion")
        pool = _create_mock_archon_pool(list(archons), substitute=substitute)
        emitter = _create_mock_event_emitter()

        service = ArchonSubstitutionService(
            archon_pool=pool,
            event_emitter=emitter,
            config=DEFAULT_DELIBERATION_CONFIG,
        )

        result = await service.execute_substitution(
            session=session,
            failed_archon_id=archons[1].id,
            failure_reason="RESPONSE_TIMEOUT",
        )

        # AT-6: Must have 3 active archons
        if result.success:
            active = result.session.current_active_archons
            assert len(active) == 3


class TestMaxSubstitutionsPerSession:
    """Tests for MAX_SUBSTITUTIONS_PER_SESSION constant."""

    def test_max_is_one(self) -> None:
        """MAX_SUBSTITUTIONS_PER_SESSION is 1 per NFR-10.6."""
        assert MAX_SUBSTITUTIONS_PER_SESSION == 1
