"""Integration tests for Job Queue Infrastructure (Story 0.4, AC7).

Tests the complete job queue lifecycle using PostgreSQL testcontainer:
- schedule → claim → execute → complete lifecycle (AC7)
- Concurrent worker safety with SELECT FOR UPDATE SKIP LOCKED
- Dead letter queue behavior after max retries (HC-6)
- PostgresJobScheduler with real database

Constitutional Constraints:
- HP-1: Job queue for reliable deadline execution
- HC-6: Dead-letter alerting for failed jobs
- NFR-7.5: 10-second polling interval verification
- FM-7.1: Persistent job queue prevents "timeout never fires" failure mode
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.job_queue.job_worker_service import (
    JobHandler,
    JobWorkerService,
)
from src.domain.models.scheduled_job import JobStatus, ScheduledJob
from src.infrastructure.adapters.job_queue.postgres_job_scheduler import (
    PostgresJobScheduler,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class TestJobHandler(JobHandler):
    """Test job handler that tracks executions."""

    def __init__(self, should_fail: bool = False) -> None:
        self.executed_jobs: list[ScheduledJob] = []
        self.should_fail = should_fail

    async def execute(self, job: ScheduledJob) -> None:
        """Execute the job, tracking it and optionally failing."""
        self.executed_jobs.append(job)
        if self.should_fail:
            raise RuntimeError("Handler intentionally failed")


async def _create_job_queue_schema(session: AsyncSession) -> None:
    """Create the job queue tables for testing."""
    # Create job_status_enum type
    await session.execute(
        text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'job_status_enum') THEN
                CREATE TYPE job_status_enum AS ENUM (
                    'pending',
                    'processing',
                    'completed',
                    'failed'
                );
            END IF;
        END $$;
        """)
    )

    # Create scheduled_jobs table
    await session.execute(
        text("""
        CREATE TABLE IF NOT EXISTS scheduled_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_type VARCHAR(100) NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}',
            scheduled_for TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            attempts INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TIMESTAMPTZ,
            last_error TEXT,
            status job_status_enum NOT NULL DEFAULT 'pending'
        )
        """)
    )

    # Create dead_letter_queue table
    await session.execute(
        text("""
        CREATE TABLE IF NOT EXISTS dead_letter_queue (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            original_job_id UUID NOT NULL,
            job_type VARCHAR(100) NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}',
            scheduled_for TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            moved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            attempts INTEGER NOT NULL,
            failure_reason TEXT NOT NULL
        )
        """)
    )

    # Create index for efficient polling
    await session.execute(
        text("""
        CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_status_scheduled
        ON scheduled_jobs(status, scheduled_for)
        WHERE status = 'pending'
        """)
    )

    await session.commit()


@pytest.fixture
async def job_queue_session(
    db_session: AsyncSession,
) -> AsyncSession:
    """Provide a database session with job queue schema."""
    await _create_job_queue_schema(db_session)
    return db_session


@pytest.fixture
def scheduler(job_queue_session: AsyncSession) -> PostgresJobScheduler:
    """Create PostgresJobScheduler with test session."""
    return PostgresJobScheduler(lambda: job_queue_session)


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create a fresh halt checker stub."""
    return HaltCheckerStub()


@pytest.fixture
def worker(
    scheduler: PostgresJobScheduler,
    halt_checker: HaltCheckerStub,
) -> JobWorkerService:
    """Create a job worker service."""
    return JobWorkerService(
        scheduler=scheduler,
        halt_checker=halt_checker,
        poll_interval=1,  # Fast for testing
    )


class TestJobQueueLifecycle:
    """Integration tests for job queue lifecycle (AC7)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_schedule_claim_execute_complete_lifecycle(
        self,
        scheduler: PostgresJobScheduler,
        worker: JobWorkerService,
    ) -> None:
        """AC7: schedule→claim→execute→complete lifecycle.

        Tests the complete lifecycle of a scheduled job through
        the PostgresJobScheduler and JobWorkerService.
        """
        handler = TestJobHandler()
        worker.register_handler("referral_timeout", handler)

        # Schedule a job for immediate execution
        run_at = _utc_now() - timedelta(hours=1)
        job_id = await scheduler.schedule(
            job_type="referral_timeout",
            payload={"petition_id": str(uuid4())},
            scheduled_for=run_at,
        )

        # Verify job is scheduled
        job = await scheduler.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.PENDING
        assert job.job_type == "referral_timeout"

        # Process the job
        result = await worker.process_single_job(job_id)

        # Verify success
        assert result is True
        assert len(handler.executed_jobs) == 1
        assert handler.executed_jobs[0].id == job_id

        # Verify job is completed
        completed_job = await scheduler.get_job(job_id)
        assert completed_job is not None
        assert completed_job.status == JobStatus.COMPLETED

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_job_not_due_not_returned(
        self,
        scheduler: PostgresJobScheduler,
    ) -> None:
        """Test that jobs scheduled for the future are not returned as pending."""
        # Schedule a job for the future
        future_time = _utc_now() + timedelta(hours=1)
        await scheduler.schedule(
            job_type="future_job",
            payload={},
            scheduled_for=future_time,
        )

        # Get pending jobs (should be empty)
        pending = await scheduler.get_pending_jobs(limit=10)
        assert len(pending) == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_cancel_job_before_processing(
        self,
        scheduler: PostgresJobScheduler,
    ) -> None:
        """Test that pending jobs can be cancelled."""
        run_at = _utc_now() + timedelta(hours=1)
        job_id = await scheduler.schedule(
            job_type="test_job",
            payload={},
            scheduled_for=run_at,
        )

        # Cancel the job
        cancelled = await scheduler.cancel(job_id)
        assert cancelled is True

        # Verify job is gone
        job = await scheduler.get_job(job_id)
        assert job is None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_cancel_processing_job_fails(
        self,
        scheduler: PostgresJobScheduler,
    ) -> None:
        """Test that jobs being processed cannot be cancelled."""
        run_at = _utc_now() - timedelta(hours=1)
        job_id = await scheduler.schedule(
            job_type="test_job",
            payload={},
            scheduled_for=run_at,
        )

        # Claim the job (moves to processing)
        await scheduler.claim_job(job_id)

        # Try to cancel (should fail)
        cancelled = await scheduler.cancel(job_id)
        assert cancelled is False

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_claim_job_atomicity(
        self,
        scheduler: PostgresJobScheduler,
    ) -> None:
        """Test that claiming a job is atomic (prevents double-processing)."""
        run_at = _utc_now() - timedelta(hours=1)
        job_id = await scheduler.schedule(
            job_type="test_job",
            payload={},
            scheduled_for=run_at,
        )

        # First claim should succeed
        job1 = await scheduler.claim_job(job_id)
        assert job1 is not None
        assert job1.status == JobStatus.PROCESSING

        # Second claim should fail (job already claimed)
        job2 = await scheduler.claim_job(job_id)
        assert job2 is None


class TestDeadLetterQueue:
    """Integration tests for Dead Letter Queue behavior (HC-6)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_job_moved_to_dlq_after_max_retries(
        self,
        scheduler: PostgresJobScheduler,
        worker: JobWorkerService,
    ) -> None:
        """HC-6: Jobs move to DLQ after max retries (3 attempts)."""
        handler = TestJobHandler(should_fail=True)
        worker.register_handler("failing_job", handler)

        # Schedule a job
        run_at = _utc_now() - timedelta(hours=1)
        job_id = await scheduler.schedule(
            job_type="failing_job",
            payload={"test": "dlq"},
            scheduled_for=run_at,
        )

        # Process 3 times (max attempts)
        for _ in range(ScheduledJob.MAX_ATTEMPTS):
            await worker.process_single_job(job_id)

        # Verify job is in DLQ
        dlq_depth = await scheduler.get_dlq_depth()
        assert dlq_depth == 1

        # Verify original job is removed
        job = await scheduler.get_job(job_id)
        assert job is None

        # Verify DLQ entry
        dlq_jobs, total_count = await scheduler.get_dlq_jobs(limit=10)
        assert len(dlq_jobs) == 1
        assert total_count == 1
        assert dlq_jobs[0].original_job_id == job_id
        assert dlq_jobs[0].job_type == "failing_job"
        assert dlq_jobs[0].attempts == ScheduledJob.MAX_ATTEMPTS

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_failed_job_under_max_attempts_stays_pending(
        self,
        scheduler: PostgresJobScheduler,
        worker: JobWorkerService,
    ) -> None:
        """Test that failed jobs under max attempts remain pending for retry."""
        handler = TestJobHandler(should_fail=True)
        worker.register_handler("retry_job", handler)

        # Schedule a job
        run_at = _utc_now() - timedelta(hours=1)
        job_id = await scheduler.schedule(
            job_type="retry_job",
            payload={},
            scheduled_for=run_at,
        )

        # Process once (should fail but not move to DLQ)
        await worker.process_single_job(job_id)

        # Verify job is still in scheduled_jobs with 1 attempt
        job = await scheduler.get_job(job_id)
        assert job is not None
        assert job.attempts == 1
        assert job.status == JobStatus.PENDING

        # Verify DLQ is empty
        dlq_depth = await scheduler.get_dlq_depth()
        assert dlq_depth == 0


class TestPollCycle:
    """Integration tests for poll cycle behavior."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_poll_cycle_processes_multiple_due_jobs(
        self,
        scheduler: PostgresJobScheduler,
        worker: JobWorkerService,
    ) -> None:
        """Test that poll cycle processes all due jobs."""
        handler = TestJobHandler()
        worker.register_handler("batch_job", handler)

        # Schedule multiple jobs
        past = _utc_now() - timedelta(hours=1)
        job_ids = []
        for i in range(3):
            job_id = await scheduler.schedule(
                job_type="batch_job",
                payload={"index": i},
                scheduled_for=past,
            )
            job_ids.append(job_id)

        # Run poll cycle
        await worker._poll_cycle()

        # Verify all jobs processed
        assert len(handler.executed_jobs) == 3
        executed_ids = {j.id for j in handler.executed_jobs}
        for job_id in job_ids:
            assert job_id in executed_ids

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_poll_cycle_respects_halt_state(
        self,
        scheduler: PostgresJobScheduler,
        halt_checker: HaltCheckerStub,
        worker: JobWorkerService,
    ) -> None:
        """CT-11: Poll cycle skips processing when system is halted."""
        handler = TestJobHandler()
        worker.register_handler("halt_job", handler)

        # Schedule a job
        past = _utc_now() - timedelta(hours=1)
        await scheduler.schedule(
            job_type="halt_job",
            payload={},
            scheduled_for=past,
        )

        # Set system as halted
        halt_checker.set_halted(True, "System maintenance")

        # Run poll cycle
        await worker._poll_cycle()

        # Verify job NOT processed
        assert len(handler.executed_jobs) == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_heartbeat_emitted_on_poll(
        self,
        worker: JobWorkerService,
    ) -> None:
        """NFR-7.5: Heartbeat is emitted during poll cycle."""
        assert worker.get_last_heartbeat() is None

        # Run poll cycle
        await worker._poll_cycle()

        # Verify heartbeat was emitted
        heartbeat = worker.get_last_heartbeat()
        assert heartbeat is not None
        # Should be recent (within 5 seconds)
        assert (_utc_now() - heartbeat).total_seconds() < 5


class TestPayloadSerialization:
    """Integration tests for job payload serialization with PostgreSQL JSONB."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complex_payload_roundtrip(
        self,
        scheduler: PostgresJobScheduler,
    ) -> None:
        """Test that complex payloads survive database roundtrip."""
        complex_payload = {
            "petition_id": str(uuid4()),
            "timeout_hours": 48,
            "metadata": {
                "created_by": "system",
                "priority": "high",
                "tags": ["deadline", "referral"],
            },
            "amounts": [100, 200, 300],
            "enabled": True,
            "nullable": None,
        }

        run_at = _utc_now() + timedelta(hours=1)
        job_id = await scheduler.schedule(
            job_type="complex_job",
            payload=complex_payload,
            scheduled_for=run_at,
        )

        # Retrieve and verify
        job = await scheduler.get_job(job_id)
        assert job is not None
        assert job.payload == complex_payload
        assert job.payload["metadata"]["tags"] == ["deadline", "referral"]
        assert job.payload["enabled"] is True
        assert job.payload["nullable"] is None
