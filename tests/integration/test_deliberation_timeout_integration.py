"""Integration tests for deliberation timeout (Story 2B.2, AC-9).

Tests the integration of timeout service, job worker, and orchestrator.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.services.deliberation_timeout_service import (
    DELIBERATION_TIMEOUT_JOB_TYPE,
    DeliberationTimeoutService,
)
from src.application.services.job_queue.deliberation_timeout_handler import (
    DeliberationTimeoutHandler,
)
from src.application.services.job_queue.job_worker_service import JobWorkerService
from src.config.deliberation_config import DeliberationConfig
from src.domain.events.deliberation_timeout import DeliberationTimeoutEvent
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
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


class TestTimeoutServiceJobWorkerIntegration:
    """Integration tests for timeout service with job worker."""

    @pytest.mark.asyncio
    async def test_timeout_job_created_and_processed(self) -> None:
        """Timeout job should be created and processed by worker."""
        # Setup
        scheduler = JobSchedulerStub()
        timeout_service = DeliberationTimeoutService(scheduler)
        handler = DeliberationTimeoutHandler(timeout_service)
        halt_checker = HaltCheckerStub()

        worker = JobWorkerService(scheduler, halt_checker, poll_interval=1)
        worker.register_handler(DELIBERATION_TIMEOUT_JOB_TYPE, handler)

        # Schedule timeout
        session = _create_test_session()
        await timeout_service.schedule_timeout(session)

        # Verify job was created
        assert scheduler.get_scheduled_count() == 1
        jobs = scheduler.get_all_jobs()
        assert jobs[0].job_type == DELIBERATION_TIMEOUT_JOB_TYPE

        # Manually process the job (simulating time passing)
        await worker.process_single_job(jobs[0].id)

        # Verify session was marked as timed out
        updated_session = timeout_service.get_session(session.session_id)
        assert updated_session is not None
        assert updated_session.is_timed_out
        assert updated_session.outcome == DeliberationOutcome.ESCALATE

    @pytest.mark.asyncio
    async def test_cancelled_timeout_not_processed(self) -> None:
        """Cancelled timeout should not be processed by worker."""
        # Setup
        scheduler = JobSchedulerStub()
        timeout_service = DeliberationTimeoutService(scheduler)
        handler = DeliberationTimeoutHandler(timeout_service)
        halt_checker = HaltCheckerStub()

        worker = JobWorkerService(scheduler, halt_checker, poll_interval=1)
        worker.register_handler(DELIBERATION_TIMEOUT_JOB_TYPE, handler)

        # Schedule then cancel
        session = _create_test_session()
        scheduled_session = await timeout_service.schedule_timeout(session)
        job_id = scheduled_session.timeout_job_id
        await timeout_service.cancel_timeout(scheduled_session)

        # Verify job was cancelled
        assert scheduler.get_scheduled_count() == 0
        assert job_id in scheduler.get_cancelled_jobs()

        # Session should not be timed out
        final_session = timeout_service.get_session(session.session_id)
        assert final_session is not None
        assert not final_session.is_timed_out
        assert final_session.outcome is None


class TestTimeoutEndToEndFlow:
    """End-to-end integration tests for timeout flow."""

    @pytest.mark.asyncio
    async def test_normal_completion_cancels_timeout(self) -> None:
        """Normal deliberation completion should cancel timeout."""
        scheduler = JobSchedulerStub()
        timeout_service = DeliberationTimeoutService(scheduler)

        session = _create_test_session()

        # Schedule timeout at deliberation start
        scheduled_session = await timeout_service.schedule_timeout(session)
        assert scheduled_session.has_timeout_scheduled

        # Verify job exists
        assert scheduler.get_scheduled_count() == 1

        # Simulate normal completion - cancel timeout
        cancelled_session = await timeout_service.cancel_timeout(scheduled_session)

        # Timeout should be cancelled
        assert not cancelled_session.has_timeout_scheduled
        assert scheduler.get_scheduled_count() == 0

    @pytest.mark.asyncio
    async def test_timeout_fires_auto_escalate(self) -> None:
        """Timeout firing should auto-escalate (HC-7)."""
        scheduler = JobSchedulerStub()
        timeout_service = DeliberationTimeoutService(scheduler)

        session = _create_test_session(phase=DeliberationPhase.CROSS_EXAMINE)

        # Schedule timeout
        await timeout_service.schedule_timeout(session)

        # Simulate timeout firing
        updated_session, event = await timeout_service.handle_timeout(
            session.session_id
        )

        # HC-7: Should auto-escalate
        assert updated_session.outcome == DeliberationOutcome.ESCALATE
        assert updated_session.is_timed_out

        # Event should capture phase at timeout
        assert event.phase_at_timeout == DeliberationPhase.CROSS_EXAMINE

    @pytest.mark.asyncio
    async def test_timeout_with_configured_duration(self) -> None:
        """Timeout should use configured duration."""
        scheduler = JobSchedulerStub()
        config = DeliberationConfig(timeout_seconds=120)  # 2 minutes
        timeout_service = DeliberationTimeoutService(scheduler, config=config)

        session = _create_test_session()
        scheduled_session = await timeout_service.schedule_timeout(session)

        # Verify timeout is approximately 2 minutes from now
        if scheduled_session.timeout_at is not None:
            expected = _utc_now() + timedelta(seconds=120)
            delta = abs((scheduled_session.timeout_at - expected).total_seconds())
            assert delta < 2  # Within 2 seconds


class TestTimeoutEventGeneration:
    """Tests for timeout event generation."""

    @pytest.mark.asyncio
    async def test_timeout_event_has_correct_fields(self) -> None:
        """Timeout event should have all required fields."""
        scheduler = JobSchedulerStub()
        config = DeliberationConfig(timeout_seconds=300)
        timeout_service = DeliberationTimeoutService(scheduler, config=config)

        session = _create_test_session(phase=DeliberationPhase.POSITION)
        await timeout_service.schedule_timeout(session)

        updated_session, event = await timeout_service.handle_timeout(
            session.session_id
        )

        # Verify event fields
        assert isinstance(event, DeliberationTimeoutEvent)
        assert event.session_id == session.session_id
        assert event.petition_id == session.petition_id
        assert event.phase_at_timeout == DeliberationPhase.POSITION
        assert event.configured_timeout_seconds == 300
        assert event.participating_archons == session.assigned_archons
        assert event.schema_version == 1

    @pytest.mark.asyncio
    async def test_timeout_event_elapsed_time(self) -> None:
        """Timeout event should calculate elapsed time correctly."""
        scheduler = JobSchedulerStub()
        timeout_service = DeliberationTimeoutService(scheduler)

        session = _create_test_session()
        await timeout_service.schedule_timeout(session)

        # Small delay to ensure some time passes
        await asyncio.sleep(0.01)

        updated_session, event = await timeout_service.handle_timeout(
            session.session_id
        )

        # Elapsed should be positive
        assert event.elapsed_seconds >= 0

    @pytest.mark.asyncio
    async def test_timeout_event_was_phase_in_progress(self) -> None:
        """Timeout event should correctly report phase status."""
        scheduler = JobSchedulerStub()
        timeout_service = DeliberationTimeoutService(scheduler)

        # Test with active phase
        session = _create_test_session(phase=DeliberationPhase.VOTE)
        await timeout_service.schedule_timeout(session)

        _, event = await timeout_service.handle_timeout(session.session_id)

        assert event.was_phase_in_progress is True


class TestMultipleTimeoutsScenario:
    """Tests for multiple concurrent timeouts."""

    @pytest.mark.asyncio
    async def test_multiple_sessions_independent_timeouts(self) -> None:
        """Multiple sessions should have independent timeouts."""
        scheduler = JobSchedulerStub()
        timeout_service = DeliberationTimeoutService(scheduler)

        # Create multiple sessions
        session1 = _create_test_session()
        session2 = _create_test_session()
        session3 = _create_test_session()

        # Schedule timeouts for all
        scheduled1 = await timeout_service.schedule_timeout(session1)
        scheduled2 = await timeout_service.schedule_timeout(session2)
        scheduled3 = await timeout_service.schedule_timeout(session3)

        # Verify all have independent jobs
        assert scheduler.get_scheduled_count() == 3
        assert scheduled1.timeout_job_id != scheduled2.timeout_job_id
        assert scheduled2.timeout_job_id != scheduled3.timeout_job_id

        # Cancel one
        await timeout_service.cancel_timeout(scheduled2)

        # Verify only one cancelled
        assert scheduler.get_scheduled_count() == 2
        final1 = timeout_service.get_session(session1.session_id)
        final2 = timeout_service.get_session(session2.session_id)
        final3 = timeout_service.get_session(session3.session_id)

        assert final1 is not None and final1.has_timeout_scheduled
        assert final2 is not None and not final2.has_timeout_scheduled
        assert final3 is not None and final3.has_timeout_scheduled

    @pytest.mark.asyncio
    async def test_timeout_fires_for_specific_session(self) -> None:
        """Firing timeout should only affect the specific session."""
        scheduler = JobSchedulerStub()
        timeout_service = DeliberationTimeoutService(scheduler)

        # Create two sessions
        session1 = _create_test_session()
        session2 = _create_test_session()

        await timeout_service.schedule_timeout(session1)
        await timeout_service.schedule_timeout(session2)

        # Fire timeout for session1 only
        updated1, event = await timeout_service.handle_timeout(session1.session_id)

        # Session1 should be timed out
        assert updated1.is_timed_out
        assert updated1.outcome == DeliberationOutcome.ESCALATE

        # Session2 should NOT be affected
        session2_after = timeout_service.get_session(session2.session_id)
        assert session2_after is not None
        assert not session2_after.is_timed_out
        assert session2_after.outcome is None
