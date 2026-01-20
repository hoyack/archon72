"""Unit tests for JobWorkerService (Story 0.4, AC5).

Tests the job worker service with stub implementations.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.application.services.job_queue.job_worker_service import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    JobHandler,
    JobWorkerService,
)
from src.domain.models.scheduled_job import JobStatus, ScheduledJob
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.job_scheduler_stub import JobSchedulerStub


class MockJobHandler(JobHandler):
    """Mock job handler for testing."""

    def __init__(self, should_fail: bool = False) -> None:
        self.executed_jobs: list[ScheduledJob] = []
        self.should_fail = should_fail

    async def execute(self, job: ScheduledJob) -> None:
        self.executed_jobs.append(job)
        if self.should_fail:
            raise RuntimeError("Handler intentionally failed")


class TestJobWorkerService:
    """Tests for JobWorkerService."""

    @pytest.fixture
    def scheduler(self) -> JobSchedulerStub:
        """Create a fresh scheduler stub."""
        return JobSchedulerStub()

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create a fresh halt checker stub."""
        return HaltCheckerStub()

    @pytest.fixture
    def worker(
        self,
        scheduler: JobSchedulerStub,
        halt_checker: HaltCheckerStub,
    ) -> JobWorkerService:
        """Create a job worker service."""
        return JobWorkerService(
            scheduler=scheduler,
            halt_checker=halt_checker,
            poll_interval=1,  # Fast for testing
        )

    def test_default_poll_interval(self) -> None:
        """Test default poll interval is 10 seconds (NFR-7.5)."""
        assert DEFAULT_POLL_INTERVAL_SECONDS == 10

    def test_register_handler(self, worker: JobWorkerService) -> None:
        """Test registering a job handler."""
        handler = MockJobHandler()

        worker.register_handler("test_job", handler)

        # Verify handler is registered (we'll test execution separately)
        assert "test_job" in worker._handlers

    @pytest.mark.asyncio
    async def test_process_single_job_success(
        self,
        scheduler: JobSchedulerStub,
        worker: JobWorkerService,
    ) -> None:
        """Test processing a single job successfully."""
        handler = MockJobHandler()
        worker.register_handler("test_job", handler)

        # Schedule a job
        run_at = datetime.now(timezone.utc) - timedelta(hours=1)
        job_id = await scheduler.schedule("test_job", {"key": "value"}, run_at)

        # Process it
        result = await worker.process_single_job(job_id)

        assert result is True
        assert len(handler.executed_jobs) == 1
        assert handler.executed_jobs[0].id == job_id

        # Job should be completed
        job = await scheduler.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_process_single_job_handler_fails(
        self,
        scheduler: JobSchedulerStub,
        worker: JobWorkerService,
    ) -> None:
        """Test processing a job when handler fails."""
        handler = MockJobHandler(should_fail=True)
        worker.register_handler("test_job", handler)

        # Schedule a job
        run_at = datetime.now(timezone.utc) - timedelta(hours=1)
        job_id = await scheduler.schedule("test_job", {}, run_at)

        # Process it - should handle failure gracefully
        result = await worker.process_single_job(job_id)

        assert result is True  # Job was found and processed
        # Job should be marked for retry
        job = await scheduler.get_job(job_id)
        assert job is not None
        assert job.attempts == 1

    @pytest.mark.asyncio
    async def test_process_single_job_no_handler(
        self,
        scheduler: JobSchedulerStub,
        worker: JobWorkerService,
    ) -> None:
        """Test processing a job with no registered handler."""
        # Schedule a job with unregistered type
        run_at = datetime.now(timezone.utc) - timedelta(hours=1)
        job_id = await scheduler.schedule("unknown_type", {}, run_at)

        # Process it
        result = await worker.process_single_job(job_id)

        assert result is True  # Job was found
        # Job should be failed due to no handler
        job = await scheduler.get_job(job_id)
        assert job is not None
        assert job.attempts == 1

    @pytest.mark.asyncio
    async def test_process_single_job_not_found(
        self,
        worker: JobWorkerService,
    ) -> None:
        """Test processing a nonexistent job."""
        from uuid import uuid4

        result = await worker.process_single_job(uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_poll_cycle_halted(
        self,
        scheduler: JobSchedulerStub,
        halt_checker: HaltCheckerStub,
        worker: JobWorkerService,
    ) -> None:
        """Test that poll cycle is skipped when system is halted."""
        handler = MockJobHandler()
        worker.register_handler("test_job", handler)

        # Schedule a job
        run_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await scheduler.schedule("test_job", {}, run_at)

        # Set system as halted
        halt_checker.set_halted(True, "Test halt")

        # Run a poll cycle
        await worker._poll_cycle()

        # Handler should not have been called
        assert len(handler.executed_jobs) == 0

    @pytest.mark.asyncio
    async def test_poll_cycle_processes_due_jobs(
        self,
        scheduler: JobSchedulerStub,
        worker: JobWorkerService,
    ) -> None:
        """Test that poll cycle processes due jobs."""
        handler = MockJobHandler()
        worker.register_handler("test_job", handler)

        # Schedule multiple jobs - some due, some not
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        future = datetime.now(timezone.utc) + timedelta(hours=1)

        job1 = await scheduler.schedule("test_job", {"order": 1}, past)
        job2 = await scheduler.schedule("test_job", {"order": 2}, past)
        await scheduler.schedule("test_job", {"order": 3}, future)  # Not due

        # Run a poll cycle
        await worker._poll_cycle()

        # Only due jobs should be processed
        assert len(handler.executed_jobs) == 2
        executed_ids = {j.id for j in handler.executed_jobs}
        assert job1 in executed_ids
        assert job2 in executed_ids

    @pytest.mark.asyncio
    async def test_heartbeat_emitted(self, worker: JobWorkerService) -> None:
        """Test that heartbeat is emitted during poll (NFR-7.5)."""
        assert worker.get_last_heartbeat() is None

        # Run a poll cycle
        await worker._poll_cycle()

        heartbeat = worker.get_last_heartbeat()
        assert heartbeat is not None
        # Should be recent
        assert (datetime.now(timezone.utc) - heartbeat).total_seconds() < 5

    @pytest.mark.asyncio
    async def test_is_running(self, worker: JobWorkerService) -> None:
        """Test is_running status."""
        assert worker.is_running() is False

        # We can't easily test start() without it running forever,
        # but we can test the flag
        worker._running = True
        assert worker.is_running() is True


class TestJobWorkerServiceDLQ:
    """Tests for DLQ behavior in JobWorkerService."""

    @pytest.fixture
    def scheduler(self) -> JobSchedulerStub:
        return JobSchedulerStub()

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        return HaltCheckerStub()

    @pytest.fixture
    def worker(
        self,
        scheduler: JobSchedulerStub,
        halt_checker: HaltCheckerStub,
    ) -> JobWorkerService:
        return JobWorkerService(
            scheduler=scheduler,
            halt_checker=halt_checker,
            poll_interval=1,
        )

    @pytest.mark.asyncio
    async def test_job_moved_to_dlq_after_max_retries(
        self,
        scheduler: JobSchedulerStub,
        worker: JobWorkerService,
    ) -> None:
        """Test that jobs move to DLQ after max retries (HC-6)."""
        handler = MockJobHandler(should_fail=True)
        worker.register_handler("test_job", handler)

        # Schedule a job
        run_at = datetime.now(timezone.utc) - timedelta(hours=1)
        job_id = await scheduler.schedule("test_job", {}, run_at)

        # Process until DLQ (3 attempts)
        for _ in range(ScheduledJob.MAX_ATTEMPTS):
            await worker.process_single_job(job_id)

        # Job should be in DLQ
        assert await scheduler.get_dlq_depth() == 1
        assert await scheduler.get_job(job_id) is None
