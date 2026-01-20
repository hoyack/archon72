"""Unit tests for DeliberationTimeoutStub (Story 2B.2, AC-8).

Tests the stub implementation of DeliberationTimeoutProtocol.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.config.deliberation_config import DeliberationConfig
from src.domain.errors.deliberation import (
    SessionAlreadyCompleteError,
    SessionNotFoundError,
)
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)
from src.infrastructure.stubs.deliberation_timeout_stub import DeliberationTimeoutStub


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


def _create_test_session(
    phase: DeliberationPhase = DeliberationPhase.ASSESS,
) -> DeliberationSession:
    """Create a test session with default archons."""
    return DeliberationSession(
        session_id=uuid4(),
        petition_id=uuid4(),
        assigned_archons=(uuid4(), uuid4(), uuid4()),
        phase=phase,
        created_at=_utc_now(),
    )


class TestDeliberationTimeoutStubSchedule:
    """Tests for stub timeout scheduling."""

    @pytest.mark.asyncio
    async def test_schedule_timeout_sets_fields(self) -> None:
        """Should set timeout tracking fields on session."""
        stub = DeliberationTimeoutStub()
        session = _create_test_session()

        updated_session = await stub.schedule_timeout(session)

        assert updated_session.has_timeout_scheduled
        assert updated_session.timeout_job_id is not None
        assert updated_session.timeout_at is not None

    @pytest.mark.asyncio
    async def test_schedule_timeout_tracks_in_dict(self) -> None:
        """Should track timeout in internal dictionary."""
        stub = DeliberationTimeoutStub()
        session = _create_test_session()

        await stub.schedule_timeout(session)

        timeouts = stub.get_scheduled_timeouts()
        assert session.session_id in timeouts

    @pytest.mark.asyncio
    async def test_schedule_timeout_uses_config(self) -> None:
        """Should use provided configuration."""
        config = DeliberationConfig(timeout_seconds=120)
        stub = DeliberationTimeoutStub(config=config)
        session = _create_test_session()

        await stub.schedule_timeout(session)

        assert stub.timeout_seconds == 120

    @pytest.mark.asyncio
    async def test_schedule_timeout_rejects_complete(self) -> None:
        """Should reject scheduling on completed session."""
        stub = DeliberationTimeoutStub()
        session = _create_test_session(phase=DeliberationPhase.COMPLETE)

        with pytest.raises(SessionAlreadyCompleteError):
            await stub.schedule_timeout(session)

    @pytest.mark.asyncio
    async def test_schedule_timeout_rejects_already_scheduled(self) -> None:
        """Should reject if already scheduled."""
        stub = DeliberationTimeoutStub()
        session = _create_test_session()

        updated_session = await stub.schedule_timeout(session)

        with pytest.raises(ValueError):
            await stub.schedule_timeout(updated_session)


class TestDeliberationTimeoutStubCancel:
    """Tests for stub timeout cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_timeout_clears_fields(self) -> None:
        """Should clear timeout tracking fields."""
        stub = DeliberationTimeoutStub()
        session = _create_test_session()

        scheduled = await stub.schedule_timeout(session)
        cancelled = await stub.cancel_timeout(scheduled)

        assert not cancelled.has_timeout_scheduled
        assert cancelled.timeout_job_id is None
        assert cancelled.timeout_at is None

    @pytest.mark.asyncio
    async def test_cancel_timeout_removes_from_dict(self) -> None:
        """Should remove from internal tracking."""
        stub = DeliberationTimeoutStub()
        session = _create_test_session()

        scheduled = await stub.schedule_timeout(session)
        await stub.cancel_timeout(scheduled)

        timeouts = stub.get_scheduled_timeouts()
        assert session.session_id not in timeouts

    @pytest.mark.asyncio
    async def test_cancel_timeout_tracks_cancellation(self) -> None:
        """Should track cancelled timeouts."""
        stub = DeliberationTimeoutStub()
        session = _create_test_session()

        scheduled = await stub.schedule_timeout(session)
        await stub.cancel_timeout(scheduled)

        cancelled = stub.get_cancelled_timeouts()
        assert session.session_id in cancelled

    @pytest.mark.asyncio
    async def test_cancel_timeout_noop_if_not_scheduled(self) -> None:
        """Should return unchanged if no timeout scheduled."""
        stub = DeliberationTimeoutStub()
        session = _create_test_session()

        result = await stub.cancel_timeout(session)

        assert result.session_id == session.session_id
        assert not result.has_timeout_scheduled


class TestDeliberationTimeoutStubHandle:
    """Tests for stub timeout handling."""

    @pytest.mark.asyncio
    async def test_handle_timeout_marks_timed_out(self) -> None:
        """Should mark session as timed out."""
        stub = DeliberationTimeoutStub()
        session = _create_test_session()
        stub.register_session(session)

        updated_session, event = await stub.handle_timeout(session.session_id)

        assert updated_session.is_timed_out
        assert updated_session.timed_out is True

    @pytest.mark.asyncio
    async def test_handle_timeout_sets_escalate(self) -> None:
        """Should set outcome to ESCALATE."""
        stub = DeliberationTimeoutStub()
        session = _create_test_session()
        stub.register_session(session)

        updated_session, event = await stub.handle_timeout(session.session_id)

        assert updated_session.outcome == DeliberationOutcome.ESCALATE

    @pytest.mark.asyncio
    async def test_handle_timeout_returns_event(self) -> None:
        """Should return timeout event."""
        stub = DeliberationTimeoutStub()
        session = _create_test_session()
        stub.register_session(session)

        updated_session, event = await stub.handle_timeout(session.session_id)

        assert event.session_id == session.session_id
        assert event.petition_id == session.petition_id
        assert event.phase_at_timeout == session.phase

    @pytest.mark.asyncio
    async def test_handle_timeout_tracks_fired(self) -> None:
        """Should track fired timeouts."""
        stub = DeliberationTimeoutStub()
        session = _create_test_session()
        stub.register_session(session)

        await stub.handle_timeout(session.session_id)

        fired = stub.get_fired_timeouts()
        assert session.session_id in fired

    @pytest.mark.asyncio
    async def test_handle_timeout_emits_event(self) -> None:
        """Should record emitted event."""
        stub = DeliberationTimeoutStub()
        session = _create_test_session()
        stub.register_session(session)

        await stub.handle_timeout(session.session_id)

        events = stub.get_emitted_events()
        assert len(events) == 1
        assert events[0].session_id == session.session_id

    @pytest.mark.asyncio
    async def test_handle_timeout_raises_for_unknown(self) -> None:
        """Should raise SessionNotFoundError for unknown session."""
        stub = DeliberationTimeoutStub()

        with pytest.raises(SessionNotFoundError):
            await stub.handle_timeout(uuid4())

    @pytest.mark.asyncio
    async def test_handle_timeout_raises_for_complete(self) -> None:
        """Should raise for completed session."""
        stub = DeliberationTimeoutStub()
        session = _create_test_session(phase=DeliberationPhase.COMPLETE)
        stub.register_session(session)

        with pytest.raises(SessionAlreadyCompleteError):
            await stub.handle_timeout(session.session_id)


class TestDeliberationTimeoutStubStatus:
    """Tests for stub status queries."""

    @pytest.mark.asyncio
    async def test_get_timeout_status_when_scheduled(self) -> None:
        """Should return True with remaining time."""
        stub = DeliberationTimeoutStub()
        session = _create_test_session()

        await stub.schedule_timeout(session)

        is_scheduled, remaining = await stub.get_timeout_status(session.session_id)

        assert is_scheduled is True
        assert remaining is not None
        assert remaining > 0

    @pytest.mark.asyncio
    async def test_get_timeout_status_when_not_scheduled(self) -> None:
        """Should return False, None."""
        stub = DeliberationTimeoutStub()
        session = _create_test_session()
        stub.register_session(session)

        is_scheduled, remaining = await stub.get_timeout_status(session.session_id)

        assert is_scheduled is False
        assert remaining is None

    @pytest.mark.asyncio
    async def test_get_timeout_status_for_unknown(self) -> None:
        """Should return False, None for unknown session."""
        stub = DeliberationTimeoutStub()

        is_scheduled, remaining = await stub.get_timeout_status(uuid4())

        assert is_scheduled is False
        assert remaining is None


class TestDeliberationTimeoutStubHelpers:
    """Tests for stub test helper methods."""

    def test_clear_resets_all(self) -> None:
        """clear() should reset all state."""
        stub = DeliberationTimeoutStub()
        session = _create_test_session()
        stub.register_session(session)

        stub.clear()

        assert stub.get_session(session.session_id) is None
        assert len(stub.get_scheduled_timeouts()) == 0
        assert len(stub.get_fired_timeouts()) == 0
        assert len(stub.get_cancelled_timeouts()) == 0
        assert len(stub.get_emitted_events()) == 0

    @pytest.mark.asyncio
    async def test_simulate_timeout_fire(self) -> None:
        """simulate_timeout_fire should backdate timeout."""
        stub = DeliberationTimeoutStub()
        session = _create_test_session()

        scheduled = await stub.schedule_timeout(session)
        stub.simulate_timeout_fire(session.session_id)

        updated = stub.get_session(session.session_id)
        assert updated is not None
        if updated.timeout_at is not None:
            assert updated.timeout_at < _utc_now()

    def test_timeout_seconds_property(self) -> None:
        """Should expose configured timeout."""
        config = DeliberationConfig(timeout_seconds=180)
        stub = DeliberationTimeoutStub(config=config)

        assert stub.timeout_seconds == 180
