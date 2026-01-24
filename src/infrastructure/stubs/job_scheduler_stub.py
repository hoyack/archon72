"""Job scheduler stub implementation (Story 0.4, AC3).

This module provides an in-memory stub implementation of
JobSchedulerProtocol for development and testing purposes.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → All operations logged
- CT-12: Witnessing creates accountability → All job executions tracked
- HP-1: Job queue for reliable deadline execution
- HC-6: Dead-letter alerting for failed jobs
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from src.application.ports.job_scheduler import JobSchedulerProtocol
from src.domain.models.scheduled_job import (
    DeadLetterJob,
    JobStatus,
    ScheduledJob,
)


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class JobSchedulerStub(JobSchedulerProtocol):
    """In-memory stub implementation of JobSchedulerProtocol.

    This stub stores scheduled jobs in memory for development and testing.
    It is NOT suitable for production use.

    Constitutional Compliance:
    - HP-1: Reliable deadline execution (simulated)
    - HC-6: Dead-letter queue for failed jobs (in-memory)

    Attributes:
        _jobs: Dictionary mapping job.id to ScheduledJob
        _dlq: Dictionary mapping dlq entry id to DeadLetterJob
        _scheduled_jobs: List of job IDs in scheduled order (for tracking)
        _cancelled_jobs: Set of cancelled job IDs (for testing)
        _completed_jobs: Set of completed job IDs (for testing)
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._jobs: dict[UUID, ScheduledJob] = {}
        self._dlq: dict[UUID, DeadLetterJob] = {}
        self._scheduled_jobs: list[UUID] = []
        self._cancelled_jobs: set[UUID] = set()
        self._completed_jobs: set[UUID] = set()

    async def schedule(
        self,
        job_type: str,
        payload: dict[str, Any],
        run_at: datetime | None = None,
        scheduled_for: datetime | None = None,
    ) -> UUID:
        """Schedule a new job for future execution.

        Args:
            job_type: Type of job (referral_timeout, deliberation_timeout, etc.)
            payload: Job-specific data (petition_id, deadline details, etc.)
            run_at: Timestamp when job should be executed (UTC, timezone-aware)
            scheduled_for: Alias for run_at (legacy/test callers)

        Returns:
            UUID of the newly scheduled job

        Raises:
            ValueError: If run_at is not timezone-aware
        """
        effective_run_at = run_at if run_at is not None else scheduled_for
        if effective_run_at is None:
            raise ValueError("run_at or scheduled_for must be provided")
        if effective_run_at.tzinfo is None:
            raise ValueError("run_at must be timezone-aware (UTC)")

        job_id = uuid4()
        job = ScheduledJob(
            id=job_id,
            job_type=job_type,
            payload=payload,
            scheduled_for=effective_run_at,
            created_at=_utc_now(),
            attempts=0,
            last_attempt_at=None,
            status=JobStatus.PENDING,
        )
        self._jobs[job_id] = job
        self._scheduled_jobs.append(job_id)
        return job_id

    async def cancel(self, job_id: UUID) -> bool:
        """Cancel a scheduled job.

        Only jobs with status PENDING can be cancelled.

        Args:
            job_id: UUID of the job to cancel

        Returns:
            True if job was cancelled, False if job was not found or not cancellable
        """
        job = self._jobs.get(job_id)
        if job is None:
            return False
        if job.status != JobStatus.PENDING:
            return False

        del self._jobs[job_id]
        self._cancelled_jobs.add(job_id)
        if job_id in self._scheduled_jobs:
            self._scheduled_jobs.remove(job_id)
        return True

    async def get_pending_jobs(self, limit: int = 10) -> list[ScheduledJob]:
        """Get jobs due for execution.

        Returns pending jobs where scheduled_for <= now, ordered by scheduled_for.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of ScheduledJob instances due for execution
        """
        now = _utc_now()
        pending = [
            job
            for job in self._jobs.values()
            if job.status == JobStatus.PENDING and job.scheduled_for <= now
        ]
        # Sort by scheduled_for ascending (oldest first)
        pending.sort(key=lambda j: j.scheduled_for)
        return pending[:limit]

    async def claim_job(self, job_id: UUID) -> ScheduledJob | None:
        """Claim a job for processing.

        Sets job status to PROCESSING.

        Args:
            job_id: UUID of the job to claim

        Returns:
            The claimed ScheduledJob if successful, None if already claimed
        """
        job = self._jobs.get(job_id)
        if job is None:
            return None
        if job.status != JobStatus.PENDING:
            return None

        claimed_job = job.with_status(JobStatus.PROCESSING)
        self._jobs[job_id] = claimed_job
        return claimed_job

    async def mark_completed(self, job_id: UUID) -> None:
        """Mark a job as successfully completed.

        Sets job status to COMPLETED.

        Args:
            job_id: UUID of the job to mark completed

        Raises:
            KeyError: If job doesn't exist
        """
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job not found: {job_id}")

        completed_job = job.with_status(JobStatus.COMPLETED)
        self._jobs[job_id] = completed_job
        self._completed_jobs.add(job_id)

    async def mark_failed(
        self,
        job_id: UUID,
        reason: str,
    ) -> DeadLetterJob | None:
        """Mark a job as failed.

        Increments attempt counter. If max attempts reached,
        moves job to dead letter queue and returns DeadLetterJob.

        Args:
            job_id: UUID of the failed job
            reason: Why the job failed

        Returns:
            DeadLetterJob if job was moved to DLQ, None if retry scheduled

        Raises:
            KeyError: If job doesn't exist
        """
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job not found: {job_id}")

        # Increment attempts
        job_with_attempt = job.with_attempt()
        failed_job = job_with_attempt.with_status(JobStatus.FAILED)
        self._jobs[job_id] = failed_job

        # Check if should move to DLQ
        if failed_job.should_move_to_dlq():
            # Create DLQ entry
            dlq_id = uuid4()
            dlq_job = DeadLetterJob.from_failed_job(dlq_id, failed_job, reason)
            self._dlq[dlq_id] = dlq_job

            # Remove from active jobs
            del self._jobs[job_id]
            if job_id in self._scheduled_jobs:
                self._scheduled_jobs.remove(job_id)

            return dlq_job

        # Schedule retry - set status back to pending
        retry_job = failed_job.with_status(JobStatus.PENDING)
        self._jobs[job_id] = retry_job
        return None

    async def get_dlq_depth(self) -> int:
        """Get count of jobs in dead letter queue.

        Returns:
            Number of jobs in the dead letter queue
        """
        return len(self._dlq)

    async def get_dlq_jobs(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[DeadLetterJob], int]:
        """Get jobs from dead letter queue.

        Args:
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip

        Returns:
            Tuple of (list of DeadLetterJob, total count)
        """
        dlq_list = list(self._dlq.values())
        # Sort by failed_at descending (newest first)
        dlq_list.sort(key=lambda j: j.failed_at, reverse=True)
        total = len(dlq_list)
        return dlq_list[offset : offset + limit], total

    async def get_job(self, job_id: UUID) -> ScheduledJob | None:
        """Get a job by ID.

        Args:
            job_id: UUID of the job

        Returns:
            The ScheduledJob if found, None otherwise
        """
        return self._jobs.get(job_id)

    # Testing helper methods

    def clear(self) -> None:
        """Clear all jobs and DLQ entries (for testing)."""
        self._jobs.clear()
        self._dlq.clear()
        self._scheduled_jobs.clear()
        self._cancelled_jobs.clear()
        self._completed_jobs.clear()

    def get_scheduled_count(self) -> int:
        """Get count of scheduled jobs (for testing)."""
        return len(self._jobs)

    def get_cancelled_jobs(self) -> set[UUID]:
        """Get set of cancelled job IDs (for testing)."""
        return self._cancelled_jobs.copy()

    def get_completed_jobs(self) -> set[UUID]:
        """Get set of completed job IDs (for testing)."""
        return self._completed_jobs.copy()

    def get_all_jobs(self) -> list[ScheduledJob]:
        """Get all jobs (for testing)."""
        return list(self._jobs.values())

    def add_dlq_job(self, dlq_job: DeadLetterJob) -> None:
        """Add a job directly to DLQ (for testing).

        This is a test helper to populate the DLQ without going through
        the normal mark_failed flow.

        Args:
            dlq_job: The DeadLetterJob to add to DLQ
        """
        self._dlq[dlq_job.id] = dlq_job
