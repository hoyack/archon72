"""Unit tests for archon substitution stub (Story 2B.4).

Tests the ArchonSubstitutionStub in-memory implementation for correct
substitution and abort behavior.

Constitutional Constraints:
- NFR-10.6: Archon substitution latency < 10 seconds on failure
- CT-11: Silent failure destroys legitimacy - failures must be handled
- AT-1: Every petition terminates in exactly one of Three Fates
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.config.deliberation_config import DEFAULT_DELIBERATION_CONFIG
from src.domain.events.archon_substitution import (
    ArchonSubstitutedEvent,
    DeliberationAbortedEvent,
)
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)
from src.infrastructure.stubs.archon_substitution_stub import ArchonSubstitutionStub


def _create_test_session(
    phase: DeliberationPhase = DeliberationPhase.POSITION,
    with_substitution: bool = False,
) -> DeliberationSession:
    """Create a test deliberation session."""
    archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
    session = DeliberationSession.create(
        session_id=uuid4(),
        petition_id=uuid4(),
        assigned_archons=(archon1, archon2, archon3),
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
        substitute_id = uuid4()
        session = session.with_substitution(
            failed_archon_id=archon2,
            substitute_archon_id=substitute_id,
            failure_reason="RESPONSE_TIMEOUT",
        )

    return session


class TestArchonSubstitutionStubBasics:
    """Basic tests for ArchonSubstitutionStub."""

    def test_stub_initializes_with_defaults(self) -> None:
        """Stub initializes with default configuration."""
        stub = ArchonSubstitutionStub(config=DEFAULT_DELIBERATION_CONFIG)

        assert stub._available_substitutes == []
        assert stub._simulated_latency_ms == 100

    def test_stub_accepts_custom_substitutes(self) -> None:
        """Stub accepts custom available substitutes."""
        substitute_id = uuid4()
        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[substitute_id],
        )

        assert substitute_id in stub._available_substitutes

    def test_stub_accepts_custom_latency(self) -> None:
        """Stub accepts custom simulated latency."""
        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            simulated_latency_ms=500,
        )

        assert stub._simulated_latency_ms == 500


class TestStubSessionManagement:
    """Tests for session management in stub."""

    def test_set_session_stores_session(self) -> None:
        """set_session stores session for retrieval."""
        stub = ArchonSubstitutionStub(config=DEFAULT_DELIBERATION_CONFIG)
        session = _create_test_session()

        stub.set_session(session)

        assert stub._sessions[session.session_id] == session

    def test_clear_resets_all_state(self) -> None:
        """clear method resets all state."""
        stub = ArchonSubstitutionStub(config=DEFAULT_DELIBERATION_CONFIG)
        session = _create_test_session()
        stub.set_session(session)
        stub._emitted_events.append("event")

        stub.clear()

        assert len(stub._sessions) == 0
        assert len(stub._emitted_events) == 0


class TestStubDetectFailure:
    """Tests for detect_failure method."""

    @pytest.mark.asyncio
    async def test_detect_failure_returns_true_for_valid_failure(self) -> None:
        """detect_failure returns True for valid failure in active session."""
        stub = ArchonSubstitutionStub(config=DEFAULT_DELIBERATION_CONFIG)
        session = _create_test_session()
        stub.set_session(session)

        result = await stub.detect_failure(
            session=session,
            archon_id=session.assigned_archons[1],
            failure_reason="RESPONSE_TIMEOUT",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_detect_failure_returns_false_for_unknown_archon(self) -> None:
        """detect_failure returns False for archon not in session."""
        stub = ArchonSubstitutionStub(config=DEFAULT_DELIBERATION_CONFIG)
        session = _create_test_session()
        stub.set_session(session)

        result = await stub.detect_failure(
            session=session,
            archon_id=uuid4(),  # Not in session
            failure_reason="RESPONSE_TIMEOUT",
        )

        assert result is False


class TestStubCanSubstitute:
    """Tests for can_substitute method."""

    @pytest.mark.asyncio
    async def test_can_substitute_returns_true_for_fresh_session(self) -> None:
        """can_substitute returns True for session without substitutions."""
        stub = ArchonSubstitutionStub(config=DEFAULT_DELIBERATION_CONFIG)
        session = _create_test_session()
        stub.set_session(session)

        result = await stub.can_substitute(session)

        assert result is True

    @pytest.mark.asyncio
    async def test_can_substitute_returns_false_after_substitution(self) -> None:
        """can_substitute returns False after max substitutions."""
        stub = ArchonSubstitutionStub(config=DEFAULT_DELIBERATION_CONFIG)
        session = _create_test_session(with_substitution=True)
        stub.set_session(session)

        result = await stub.can_substitute(session)

        assert result is False


class TestStubSelectSubstitute:
    """Tests for select_substitute method."""

    @pytest.mark.asyncio
    async def test_select_substitute_returns_available(self) -> None:
        """select_substitute returns available substitute ID."""
        substitute_id = uuid4()
        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[substitute_id],
        )
        session = _create_test_session()
        stub.set_session(session)

        result = await stub.select_substitute(
            session=session,
            failed_archon_id=session.assigned_archons[1],
        )

        assert result == substitute_id

    @pytest.mark.asyncio
    async def test_select_substitute_returns_none_when_exhausted(self) -> None:
        """select_substitute returns None when pool exhausted."""
        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[],
        )
        session = _create_test_session()
        stub.set_session(session)

        result = await stub.select_substitute(
            session=session,
            failed_archon_id=session.assigned_archons[1],
        )

        assert result is None


class TestStubExecuteSubstitution:
    """Tests for execute_substitution method."""

    @pytest.mark.asyncio
    async def test_successful_substitution(self) -> None:
        """execute_substitution returns success with substitute."""
        substitute_id = uuid4()
        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[substitute_id],
        )
        session = _create_test_session()
        stub.set_session(session)

        result = await stub.execute_substitution(
            session=session,
            failed_archon_id=session.assigned_archons[1],
            failure_reason="RESPONSE_TIMEOUT",
        )

        assert result.success is True
        assert result.substitute_archon_id == substitute_id
        assert isinstance(result.event, ArchonSubstitutedEvent)

    @pytest.mark.asyncio
    async def test_abort_when_no_substitute(self) -> None:
        """execute_substitution returns abort when no substitute available."""
        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[],
        )
        session = _create_test_session()
        stub.set_session(session)

        result = await stub.execute_substitution(
            session=session,
            failed_archon_id=session.assigned_archons[1],
            failure_reason="RESPONSE_TIMEOUT",
        )

        assert result.success is False
        assert isinstance(result.event, DeliberationAbortedEvent)

    @pytest.mark.asyncio
    async def test_uses_simulated_latency(self) -> None:
        """execute_substitution uses configured latency."""
        substitute_id = uuid4()
        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[substitute_id],
            simulated_latency_ms=200,
        )
        session = _create_test_session()
        stub.set_session(session)

        result = await stub.execute_substitution(
            session=session,
            failed_archon_id=session.assigned_archons[1],
            failure_reason="RESPONSE_TIMEOUT",
        )

        assert result.latency_ms == 200


class TestStubAbortDeliberation:
    """Tests for abort_deliberation method."""

    @pytest.mark.asyncio
    async def test_abort_sets_escalate_outcome(self) -> None:
        """abort_deliberation sets ESCALATE outcome."""
        stub = ArchonSubstitutionStub(config=DEFAULT_DELIBERATION_CONFIG)
        session = _create_test_session()
        stub.set_session(session)

        updated, event = await stub.abort_deliberation(
            session=session,
            reason="INSUFFICIENT_ARCHONS",
            failed_archons=[],
        )

        assert updated.outcome == DeliberationOutcome.ESCALATE
        assert updated.is_aborted is True

    @pytest.mark.asyncio
    async def test_abort_emits_event(self) -> None:
        """abort_deliberation emits DeliberationAbortedEvent."""
        stub = ArchonSubstitutionStub(config=DEFAULT_DELIBERATION_CONFIG)
        session = _create_test_session()
        stub.set_session(session)

        updated, event = await stub.abort_deliberation(
            session=session,
            reason="ARCHON_POOL_EXHAUSTED",
            failed_archons=[],
        )

        assert isinstance(event, DeliberationAbortedEvent)
        assert event.reason == "ARCHON_POOL_EXHAUSTED"


class TestStubEventTracking:
    """Tests for event tracking in stub."""

    @pytest.mark.asyncio
    async def test_get_emitted_events_returns_all_events(self) -> None:
        """get_emitted_events returns all emitted events."""
        substitute_id = uuid4()
        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[substitute_id],
        )
        session = _create_test_session()
        stub.set_session(session)

        await stub.execute_substitution(
            session=session,
            failed_archon_id=session.assigned_archons[1],
            failure_reason="RESPONSE_TIMEOUT",
        )

        events = stub.get_emitted_events()
        assert len(events) == 1
        assert isinstance(events[0], ArchonSubstitutedEvent)

    @pytest.mark.asyncio
    async def test_get_substitutions_returns_substitutions(self) -> None:
        """get_substitutions returns recorded substitutions."""
        substitute_id = uuid4()
        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[substitute_id],
        )
        session = _create_test_session()
        stub.set_session(session)

        await stub.execute_substitution(
            session=session,
            failed_archon_id=session.assigned_archons[1],
            failure_reason="RESPONSE_TIMEOUT",
        )

        substitutions = stub.get_substitutions()
        assert len(substitutions) == 1

    @pytest.mark.asyncio
    async def test_get_aborts_returns_aborts(self) -> None:
        """get_aborts returns recorded aborts."""
        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[],
        )
        session = _create_test_session()
        stub.set_session(session)

        await stub.execute_substitution(
            session=session,
            failed_archon_id=session.assigned_archons[1],
            failure_reason="RESPONSE_TIMEOUT",
        )

        aborts = stub.get_aborts()
        assert len(aborts) == 1


class TestStubConstitutionalCompliance:
    """Tests for constitutional compliance in stub."""

    @pytest.mark.asyncio
    async def test_stub_enforces_max_one_substitution(self) -> None:
        """Stub enforces max 1 substitution per session."""
        substitute_id = uuid4()
        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[substitute_id, uuid4()],
        )
        session = _create_test_session(with_substitution=True)
        stub.set_session(session)

        result = await stub.execute_substitution(
            session=session,
            failed_archon_id=session.assigned_archons[0],
            failure_reason="RESPONSE_TIMEOUT",
        )

        # Second substitution should fail
        assert result.success is False
        assert isinstance(result.event, DeliberationAbortedEvent)

    @pytest.mark.asyncio
    async def test_stub_returns_escalate_on_abort(self) -> None:
        """Stub returns ESCALATE outcome on abort (AT-1)."""
        stub = ArchonSubstitutionStub(
            config=DEFAULT_DELIBERATION_CONFIG,
            available_substitutes=[],
        )
        session = _create_test_session()
        stub.set_session(session)

        result = await stub.execute_substitution(
            session=session,
            failed_archon_id=session.assigned_archons[1],
            failure_reason="RESPONSE_TIMEOUT",
        )

        assert result.session.outcome == DeliberationOutcome.ESCALATE
