"""Unit tests for JobSchedulerStub (Story 0.4, AC3).

Tests the in-memory stub implementation of JobSchedulerProtocol.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.models.scheduled_job import JobStatus, ScheduledJob
from src.infrastructure.stubs.job_scheduler_stub import JobSchedulerStub


class TestJobSchedulerStub:
    """Tests for JobSchedulerStub implementation."""

    @pytest.fixture
    def stub(self) -> JobSchedulerStub:
        """Create a fresh stub for each test."""
        return JobSchedulerStub()

    @pytest.mark.asyncio
    async def test_schedule_job(self, stub: JobSchedulerStub) -> None:
        """Test scheduling a new job."""
        run_at = datetime.now(timezone.utc) + timedelta(hours=1)

        job_id = await stub.schedule(
            job_type="referral_timeout",
            payload={"petition_id": "abc123"},
            run_at=run_at,
        )

        assert job_id is not None
        job = await stub.get_job(job_id)
        assert job is not None
        assert job.job_type == "referral_timeout"
        assert job.payload == {"petition_id": "abc123"}
        assert job.scheduled_for == run_at
        assert job.status == JobStatus.PENDING

    @pytest.mark.asyncio
    async def test_schedule_requires_timezone_aware(self, stub: JobSchedulerStub) -> None:
        """Test that schedule rejects naive datetime."""
        naive_datetime = datetime.now()  # No timezone

        with pytest.raises(ValueError, match="timezone-aware"):
            await stub.schedule(
                job_type="test",
                payload={},
                run_at=naive_datetime,
            )

    @pytest.mark.asyncio
    async def test_cancel_pending_job(self, stub: JobSchedulerStub) -> None:
        """Test cancelling a pending job."""
        run_at = datetime.now(timezone.utc) + timedelta(hours=1)
        job_id = await stub.schedule("test", {}, run_at)

        result = await stub.cancel(job_id)

        assert result is True
        assert await stub.get_job(job_id) is None
        assert job_id in stub.get_cancelled_jobs()

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(self, stub: JobSchedulerStub) -> None:
        """Test cancelling a nonexistent job returns False."""
        result = await stub.cancel(uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_processing_job_fails(self, stub: JobSchedulerStub) -> None:
        """Test that processing jobs cannot be cancelled."""
        # Schedule and claim a job
        run_at = datetime.now(timezone.utc) - timedelta(hours=1)  # Due now
        job_id = await stub.schedule("test", {}, run_at)
        await stub.claim_job(job_id)

        result = await stub.cancel(job_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_pending_jobs_due(self, stub: JobSchedulerStub) -> None:
        """Test getting pending jobs that are due."""
        # Schedule jobs - some due, some not
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        future = datetime.now(timezone.utc) + timedelta(hours=1)

        job1 = await stub.schedule("test1", {"order": 1}, past)
        job2 = await stub.schedule("test2", {"order": 2}, past)
        await stub.schedule("test3", {"order": 3}, future)  # Not due

        pending = await stub.get_pending_jobs()

        assert len(pending) == 2
        pending_ids = {j.id for j in pending}
        assert job1 in pending_ids
        assert job2 in pending_ids

    @pytest.mark.asyncio
    async def test_get_pending_jobs_limit(self, stub: JobSchedulerStub) -> None:
        """Test get_pending_jobs respects limit."""
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        for i in range(5):
            await stub.schedule(f"test{i}", {}, past)

        pending = await stub.get_pending_jobs(limit=2)

        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_claim_job_success(self, stub: JobSchedulerStub) -> None:
        """Test claiming a pending job."""
        run_at = datetime.now(timezone.utc) - timedelta(hours=1)
        job_id = await stub.schedule("test", {}, run_at)

        claimed = await stub.claim_job(job_id)

        assert claimed is not None
        assert claimed.id == job_id
        assert claimed.status == JobStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_claim_job_already_claimed(self, stub: JobSchedulerStub) -> None:
        """Test claiming an already-claimed job returns None."""
        run_at = datetime.now(timezone.utc) - timedelta(hours=1)
        job_id = await stub.schedule("test", {}, run_at)

        # First claim succeeds
        await stub.claim_job(job_id)

        # Second claim fails
        result = await stub.claim_job(job_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_mark_completed(self, stub: JobSchedulerStub) -> None:
        """Test marking a job as completed."""
        run_at = datetime.now(timezone.utc) - timedelta(hours=1)
        job_id = await stub.schedule("test", {}, run_at)
        await stub.claim_job(job_id)

        await stub.mark_completed(job_id)

        job = await stub.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.COMPLETED
        assert job_id in stub.get_completed_jobs()

    @pytest.mark.asyncio
    async def test_mark_completed_nonexistent(self, stub: JobSchedulerStub) -> None:
        """Test marking nonexistent job as completed raises KeyError."""
        with pytest.raises(KeyError):
            await stub.mark_completed(uuid4())

    @pytest.mark.asyncio
    async def test_mark_failed_retry(self, stub: JobSchedulerStub) -> None:
        """Test marking a job as failed schedules retry."""
        run_at = datetime.now(timezone.utc) - timedelta(hours=1)
        job_id = await stub.schedule("test", {}, run_at)
        await stub.claim_job(job_id)

        dlq_job = await stub.mark_failed(job_id, "Test failure")

        # Should not be in DLQ yet (retries remaining)
        assert dlq_job is None
        job = await stub.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.PENDING
        assert job.attempts == 1

    @pytest.mark.asyncio
    async def test_mark_failed_to_dlq(self, stub: JobSchedulerStub) -> None:
        """Test job moves to DLQ after max attempts."""
        run_at = datetime.now(timezone.utc) - timedelta(hours=1)
        job_id = await stub.schedule("test", {"key": "value"}, run_at)
        await stub.claim_job(job_id)

        # Fail max times
        for i in range(ScheduledJob.MAX_ATTEMPTS):
            job = await stub.get_job(job_id)
            if job and job.status == JobStatus.PENDING:
                await stub.claim_job(job_id)
            dlq_job = await stub.mark_failed(job_id, f"Failure {i + 1}")

        # Final failure should return DLQ job
        assert dlq_job is not None
        assert dlq_job.job_type == "test"
        assert dlq_job.payload == {"key": "value"}
        assert dlq_job.failure_reason == f"Failure {ScheduledJob.MAX_ATTEMPTS}"
        assert dlq_job.attempts == ScheduledJob.MAX_ATTEMPTS

        # Job should be removed from active jobs
        assert await stub.get_job(job_id) is None

    @pytest.mark.asyncio
    async def test_get_dlq_depth(self, stub: JobSchedulerStub) -> None:
        """Test getting DLQ depth."""
        assert await stub.get_dlq_depth() == 0

        # Add job to DLQ
        run_at = datetime.now(timezone.utc) - timedelta(hours=1)
        job_id = await stub.schedule("test", {}, run_at)
        await stub.claim_job(job_id)
        for _ in range(ScheduledJob.MAX_ATTEMPTS):
            job = await stub.get_job(job_id)
            if job and job.status == JobStatus.PENDING:
                await stub.claim_job(job_id)
            await stub.mark_failed(job_id, "Failure")

        assert await stub.get_dlq_depth() == 1

    @pytest.mark.asyncio
    async def test_get_dlq_jobs(self, stub: JobSchedulerStub) -> None:
        """Test getting jobs from DLQ."""
        # Add job to DLQ
        run_at = datetime.now(timezone.utc) - timedelta(hours=1)
        job_id = await stub.schedule("test", {}, run_at)
        await stub.claim_job(job_id)
        for _ in range(ScheduledJob.MAX_ATTEMPTS):
            job = await stub.get_job(job_id)
            if job and job.status == JobStatus.PENDING:
                await stub.claim_job(job_id)
            await stub.mark_failed(job_id, "Failure")

        dlq_jobs, total = await stub.get_dlq_jobs()

        assert total == 1
        assert len(dlq_jobs) == 1
        assert dlq_jobs[0].original_job_id == job_id

    @pytest.mark.asyncio
    async def test_clear(self, stub: JobSchedulerStub) -> None:
        """Test clearing all jobs."""
        run_at = datetime.now(timezone.utc)
        await stub.schedule("test1", {}, run_at)
        await stub.schedule("test2", {}, run_at)

        stub.clear()

        assert stub.get_scheduled_count() == 0
        assert await stub.get_dlq_depth() == 0
