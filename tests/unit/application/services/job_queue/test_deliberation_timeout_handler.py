"""Unit tests for DeliberationTimeoutHandler (Story 2B.2, AC-6, AC-8).

Tests the job handler that processes deliberation timeout jobs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.services.deliberation_timeout_service import (
    DELIBERATION_TIMEOUT_JOB_TYPE,
    DeliberationTimeoutService,
)
from src.application.services.job_queue.deliberation_timeout_handler import (
    DeliberationTimeoutHandler,
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
from src.domain.models.scheduled_job import JobStatus, ScheduledJob
from src.infrastructure.stubs.job_scheduler_stub import JobSchedulerStub


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


def _create_test_session(
    session_id: uuid4 | None = None,
    phase: DeliberationPhase = DeliberationPhase.ASSESS,
) -> DeliberationSession:
    """Create a test session with default archons."""
    return DeliberationSession(
        session_id=session_id or uuid4(),
        petition_id=uuid4(),
        assigned_archons=(uuid4(), uuid4(), uuid4()),
        phase=phase,
        created_at=_utc_now(),
    )


def _create_test_job(
    session_id: str,
    petition_id: str = "test-petition",
) -> ScheduledJob:
    """Create a test scheduled job for timeout."""
    return ScheduledJob(
        id=uuid4(),
        job_type=DELIBERATION_TIMEOUT_JOB_TYPE,
        payload={
            "session_id": session_id,
            "petition_id": petition_id,
            "timeout_seconds": 300,
        },
        scheduled_for=_utc_now(),
        created_at=_utc_now(),
        attempts=0,
        last_attempt_at=None,
        status=JobStatus.PROCESSING,
    )


class TestDeliberationTimeoutHandler:
    """Tests for DeliberationTimeoutHandler execution."""

    @pytest.mark.asyncio
    async def test_execute_triggers_timeout_handling(self) -> None:
        """Should delegate to timeout service handle_timeout."""
        scheduler = JobSchedulerStub()
        timeout_service = DeliberationTimeoutService(scheduler)
        handler = DeliberationTimeoutHandler(timeout_service)

        session = _create_test_session()
        timeout_service.register_session(session)

        job = _create_test_job(
            session_id=str(session.session_id),
            petition_id=str(session.petition_id),
        )

        await handler.execute(job)

        # Session should be marked as timed out
        updated_session = timeout_service.get_session(session.session_id)
        assert updated_session is not None
        assert updated_session.is_timed_out
        assert updated_session.outcome == DeliberationOutcome.ESCALATE

    @pytest.mark.asyncio
    async def test_execute_raises_for_missing_session_id(self) -> None:
        """Should raise ValueError if payload missing session_id."""
        scheduler = JobSchedulerStub()
        timeout_service = DeliberationTimeoutService(scheduler)
        handler = DeliberationTimeoutHandler(timeout_service)

        job = ScheduledJob(
            id=uuid4(),
            job_type=DELIBERATION_TIMEOUT_JOB_TYPE,
            payload={"petition_id": "test"},  # Missing session_id
            scheduled_for=_utc_now(),
            created_at=_utc_now(),
            attempts=0,
            last_attempt_at=None,
            status=JobStatus.PROCESSING,
        )

        with pytest.raises(ValueError) as exc_info:
            await handler.execute(job)

        assert "session_id" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_raises_for_invalid_session_id(self) -> None:
        """Should raise ValueError if session_id is invalid UUID."""
        scheduler = JobSchedulerStub()
        timeout_service = DeliberationTimeoutService(scheduler)
        handler = DeliberationTimeoutHandler(timeout_service)

        job = ScheduledJob(
            id=uuid4(),
            job_type=DELIBERATION_TIMEOUT_JOB_TYPE,
            payload={
                "session_id": "not-a-uuid",
                "petition_id": "test",
            },
            scheduled_for=_utc_now(),
            created_at=_utc_now(),
            attempts=0,
            last_attempt_at=None,
            status=JobStatus.PROCESSING,
        )

        with pytest.raises(ValueError) as exc_info:
            await handler.execute(job)

        assert "Invalid session_id" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_raises_for_unknown_session(self) -> None:
        """Should raise SessionNotFoundError for unknown session."""
        scheduler = JobSchedulerStub()
        timeout_service = DeliberationTimeoutService(scheduler)
        handler = DeliberationTimeoutHandler(timeout_service)

        unknown_session_id = uuid4()
        job = _create_test_job(session_id=str(unknown_session_id))

        with pytest.raises(SessionNotFoundError):
            await handler.execute(job)

    @pytest.mark.asyncio
    async def test_execute_raises_for_complete_session(self) -> None:
        """Should raise SessionAlreadyCompleteError for completed session."""
        scheduler = JobSchedulerStub()
        timeout_service = DeliberationTimeoutService(scheduler)
        handler = DeliberationTimeoutHandler(timeout_service)

        session = _create_test_session(phase=DeliberationPhase.COMPLETE)
        timeout_service.register_session(session)

        job = _create_test_job(session_id=str(session.session_id))

        with pytest.raises(SessionAlreadyCompleteError):
            await handler.execute(job)

    def test_handler_job_type_constant(self) -> None:
        """Handler should have correct job_type."""
        scheduler = JobSchedulerStub()
        timeout_service = DeliberationTimeoutService(scheduler)
        handler = DeliberationTimeoutHandler(timeout_service)

        assert handler.job_type == DELIBERATION_TIMEOUT_JOB_TYPE
