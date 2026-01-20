"""Unit tests for DeliberationTimeoutService (Story 2B.2, AC-8).

Tests timeout scheduling, cancellation, and firing behavior.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.services.deliberation_timeout_service import (
    DELIBERATION_TIMEOUT_JOB_TYPE,
    DeliberationTimeoutService,
)
from src.config.deliberation_config import (
    DEFAULT_DELIBERATION_CONFIG,
    DeliberationConfig,
)
from src.domain.errors.deliberation import (
    SessionAlreadyCompleteError,
    SessionNotFoundError,
)
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)
from src.infrastructure.stubs.job_scheduler_stub import JobSchedulerStub


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


class TestDeliberationTimeoutServiceSchedule:
    """Tests for timeout scheduling."""

    @pytest.mark.asyncio
    async def test_schedule_timeout_creates_job(self) -> None:
        """Should schedule a job in the job queue."""
        scheduler = JobSchedulerStub()
        service = DeliberationTimeoutService(scheduler)
        session = _create_test_session()

        updated_session = await service.schedule_timeout(session)

        # Verify job was scheduled
        assert scheduler.get_scheduled_count() == 1
        jobs = scheduler.get_all_jobs()
        assert len(jobs) == 1
        assert jobs[0].job_type == DELIBERATION_TIMEOUT_JOB_TYPE

    @pytest.mark.asyncio
    async def test_schedule_timeout_sets_session_fields(self) -> None:
        """Should set timeout_job_id and timeout_at on session."""
        scheduler = JobSchedulerStub()
        service = DeliberationTimeoutService(scheduler)
        session = _create_test_session()

        updated_session = await service.schedule_timeout(session)

        assert updated_session.has_timeout_scheduled
        assert updated_session.timeout_job_id is not None
        assert updated_session.timeout_at is not None

    @pytest.mark.asyncio
    async def test_schedule_timeout_uses_configured_duration(self) -> None:
        """Should use configured timeout duration."""
        scheduler = JobSchedulerStub()
        config = DeliberationConfig(timeout_seconds=120)  # 2 minutes
        service = DeliberationTimeoutService(scheduler, config=config)
        session = _create_test_session()

        updated_session = await service.schedule_timeout(session)

        # Timeout should be approximately 2 minutes from now
        expected_timeout = _utc_now() + timedelta(seconds=120)
        if updated_session.timeout_at is not None:
            delta = abs((updated_session.timeout_at - expected_timeout).total_seconds())
            assert delta < 2  # Within 2 seconds tolerance

    @pytest.mark.asyncio
    async def test_schedule_timeout_includes_payload(self) -> None:
        """Should include session_id and petition_id in job payload."""
        scheduler = JobSchedulerStub()
        service = DeliberationTimeoutService(scheduler)
        session = _create_test_session()

        await service.schedule_timeout(session)

        jobs = scheduler.get_all_jobs()
        payload = jobs[0].payload
        assert payload["session_id"] == str(session.session_id)
        assert payload["petition_id"] == str(session.petition_id)
        assert payload["timeout_seconds"] == DEFAULT_DELIBERATION_CONFIG.timeout_seconds

    @pytest.mark.asyncio
    async def test_schedule_timeout_rejects_complete_session(self) -> None:
        """Should reject scheduling on completed session."""
        scheduler = JobSchedulerStub()
        service = DeliberationTimeoutService(scheduler)
        session = _create_test_session(phase=DeliberationPhase.COMPLETE)

        with pytest.raises(SessionAlreadyCompleteError):
            await service.schedule_timeout(session)

    @pytest.mark.asyncio
    async def test_schedule_timeout_rejects_already_scheduled(self) -> None:
        """Should reject if timeout already scheduled."""
        scheduler = JobSchedulerStub()
        service = DeliberationTimeoutService(scheduler)
        session = _create_test_session()

        # Schedule first time
        updated_session = await service.schedule_timeout(session)

        # Try to schedule again
        with pytest.raises(ValueError) as exc_info:
            await service.schedule_timeout(updated_session)

        assert "already scheduled" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_schedule_timeout_registers_session(self) -> None:
        """Should register session for later lookup."""
        scheduler = JobSchedulerStub()
        service = DeliberationTimeoutService(scheduler)
        session = _create_test_session()

        await service.schedule_timeout(session)

        retrieved = service.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id


class TestDeliberationTimeoutServiceCancel:
    """Tests for timeout cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_timeout_removes_job(self) -> None:
        """Should cancel the scheduled job."""
        scheduler = JobSchedulerStub()
        service = DeliberationTimeoutService(scheduler)
        session = _create_test_session()

        scheduled_session = await service.schedule_timeout(session)
        assert scheduler.get_scheduled_count() == 1

        await service.cancel_timeout(scheduled_session)

        # Job should be cancelled
        assert scheduler.get_scheduled_count() == 0
        assert scheduled_session.timeout_job_id in scheduler.get_cancelled_jobs()

    @pytest.mark.asyncio
    async def test_cancel_timeout_clears_session_fields(self) -> None:
        """Should clear timeout tracking fields on session."""
        scheduler = JobSchedulerStub()
        service = DeliberationTimeoutService(scheduler)
        session = _create_test_session()

        scheduled_session = await service.schedule_timeout(session)
        cancelled_session = await service.cancel_timeout(scheduled_session)

        assert not cancelled_session.has_timeout_scheduled
        assert cancelled_session.timeout_job_id is None
        assert cancelled_session.timeout_at is None

    @pytest.mark.asyncio
    async def test_cancel_timeout_returns_unchanged_if_not_scheduled(self) -> None:
        """Should return session unchanged if no timeout scheduled."""
        scheduler = JobSchedulerStub()
        service = DeliberationTimeoutService(scheduler)
        session = _create_test_session()

        # No timeout scheduled
        cancelled_session = await service.cancel_timeout(session)

        assert cancelled_session.session_id == session.session_id
        assert not cancelled_session.has_timeout_scheduled


class TestDeliberationTimeoutServiceHandle:
    """Tests for timeout handling (firing)."""

    @pytest.mark.asyncio
    async def test_handle_timeout_marks_session_timed_out(self) -> None:
        """Should mark session as timed out."""
        scheduler = JobSchedulerStub()
        service = DeliberationTimeoutService(scheduler)
        session = _create_test_session()

        # Register and schedule
        scheduled_session = await service.schedule_timeout(session)

        # Handle timeout
        updated_session, event = await service.handle_timeout(session.session_id)

        assert updated_session.is_timed_out
        assert updated_session.timed_out is True

    @pytest.mark.asyncio
    async def test_handle_timeout_sets_escalate_outcome(self) -> None:
        """Should set outcome to ESCALATE per HC-7."""
        scheduler = JobSchedulerStub()
        service = DeliberationTimeoutService(scheduler)
        session = _create_test_session()

        await service.schedule_timeout(session)
        updated_session, event = await service.handle_timeout(session.session_id)

        assert updated_session.outcome == DeliberationOutcome.ESCALATE

    @pytest.mark.asyncio
    async def test_handle_timeout_returns_event(self) -> None:
        """Should return DeliberationTimeoutEvent."""
        scheduler = JobSchedulerStub()
        service = DeliberationTimeoutService(scheduler)
        session = _create_test_session()

        await service.schedule_timeout(session)
        updated_session, event = await service.handle_timeout(session.session_id)

        assert event.session_id == session.session_id
        assert event.petition_id == session.petition_id
        assert event.phase_at_timeout == session.phase
        assert event.configured_timeout_seconds == DEFAULT_DELIBERATION_CONFIG.timeout_seconds

    @pytest.mark.asyncio
    async def test_handle_timeout_raises_for_unknown_session(self) -> None:
        """Should raise SessionNotFoundError for unknown session."""
        scheduler = JobSchedulerStub()
        service = DeliberationTimeoutService(scheduler)

        unknown_id = uuid4()
        with pytest.raises(SessionNotFoundError):
            await service.handle_timeout(unknown_id)

    @pytest.mark.asyncio
    async def test_handle_timeout_raises_for_complete_session(self) -> None:
        """Should raise SessionAlreadyCompleteError for completed session."""
        scheduler = JobSchedulerStub()
        service = DeliberationTimeoutService(scheduler)

        # Create and register a completed session
        session = _create_test_session(phase=DeliberationPhase.COMPLETE)
        service.register_session(session)

        with pytest.raises(SessionAlreadyCompleteError):
            await service.handle_timeout(session.session_id)


class TestDeliberationTimeoutServiceStatus:
    """Tests for timeout status queries."""

    @pytest.mark.asyncio
    async def test_get_timeout_status_when_scheduled(self) -> None:
        """Should return (True, remaining_seconds) when scheduled."""
        scheduler = JobSchedulerStub()
        config = DeliberationConfig(timeout_seconds=300)
        service = DeliberationTimeoutService(scheduler, config=config)
        session = _create_test_session()

        await service.schedule_timeout(session)

        is_scheduled, remaining = await service.get_timeout_status(session.session_id)

        assert is_scheduled is True
        assert remaining is not None
        assert 280 <= remaining <= 300  # Should be close to 300 seconds

    @pytest.mark.asyncio
    async def test_get_timeout_status_when_not_scheduled(self) -> None:
        """Should return (False, None) when not scheduled."""
        scheduler = JobSchedulerStub()
        service = DeliberationTimeoutService(scheduler)
        session = _create_test_session()
        service.register_session(session)

        is_scheduled, remaining = await service.get_timeout_status(session.session_id)

        assert is_scheduled is False
        assert remaining is None

    @pytest.mark.asyncio
    async def test_get_timeout_status_for_unknown_session(self) -> None:
        """Should return (False, None) for unknown session."""
        scheduler = JobSchedulerStub()
        service = DeliberationTimeoutService(scheduler)

        is_scheduled, remaining = await service.get_timeout_status(uuid4())

        assert is_scheduled is False
        assert remaining is None

    def test_timeout_seconds_property(self) -> None:
        """Should expose configured timeout duration."""
        scheduler = JobSchedulerStub()
        config = DeliberationConfig(timeout_seconds=180)
        service = DeliberationTimeoutService(scheduler, config=config)

        assert service.timeout_seconds == 180
