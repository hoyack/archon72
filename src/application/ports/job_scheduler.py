"""Job scheduler port for deadline monitoring (Story 0.4, AC2).

This module defines the abstract interface for job scheduling operations
in the Three Fates petition system.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → All operations must be logged
- CT-12: Witnessing creates accountability → All job executions are auditable
- HP-1: Job queue for reliable deadline execution
- HC-6: Dead-letter alerting for failed jobs
- NFR-7.5: Timeout job monitoring with heartbeat on scheduler

Developer Golden Rules:
1. HALT CHECK FIRST - Service layer checks halt, not scheduler
2. WITNESS EVERYTHING - Scheduler stores, service witnesses
3. FAIL LOUD - Scheduler raises on errors
4. READS DURING HALT - Scheduler reads work during halt (CT-13)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from src.domain.models.scheduled_job import DeadLetterJob, ScheduledJob


class JobSchedulerProtocol(Protocol):
    """Protocol for job scheduling operations (Story 0.4, AC2).

    Defines the contract for job scheduling persistence. Implementations
    may use Supabase, in-memory storage, or other backends.

    Constitutional Constraints:
    - AC2: Support schedule, cancel, get_pending_jobs, mark_completed, mark_failed
    - HP-1: Reliable deadline execution
    - HC-6: Dead-letter queue for failed jobs

    Methods:
        schedule: Schedule a new job for future execution
        cancel: Cancel a scheduled job
        get_pending_jobs: Get jobs due for execution
        mark_completed: Mark a job as successfully completed
        mark_failed: Mark a job as failed (with retry/DLQ logic)
        get_dlq_depth: Get count of jobs in dead letter queue
        get_dlq_jobs: Get jobs from dead letter queue
    """

    async def schedule(
        self,
        job_type: str,
        payload: dict[str, Any],
        run_at: datetime,
    ) -> UUID:
        """Schedule a new job for future execution.

        Constitutional Constraint (HP-1): Reliable deadline execution.

        Args:
            job_type: Type of job (referral_timeout, deliberation_timeout, etc.)
            payload: Job-specific data (petition_id, deadline details, etc.)
            run_at: Timestamp when job should be executed (UTC, timezone-aware)

        Returns:
            UUID of the newly scheduled job

        Raises:
            ValueError: If run_at is not timezone-aware
        """
        ...

    async def cancel(self, job_id: UUID) -> bool:
        """Cancel a scheduled job.

        Only jobs with status PENDING can be cancelled.

        Args:
            job_id: UUID of the job to cancel

        Returns:
            True if job was cancelled, False if job was not found or not cancellable
        """
        ...

    async def get_pending_jobs(self, limit: int = 10) -> list[ScheduledJob]:
        """Get jobs due for execution.

        Uses SELECT FOR UPDATE SKIP LOCKED to prevent double-processing
        by multiple workers.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of ScheduledJob instances due for execution
        """
        ...

    async def claim_job(self, job_id: UUID) -> ScheduledJob | None:
        """Claim a job for processing.

        Sets job status to PROCESSING. Uses optimistic locking.

        Args:
            job_id: UUID of the job to claim

        Returns:
            The claimed ScheduledJob if successful, None if already claimed
        """
        ...

    async def mark_completed(self, job_id: UUID) -> None:
        """Mark a job as successfully completed.

        Sets job status to COMPLETED.

        Args:
            job_id: UUID of the job to mark completed

        Raises:
            KeyError: If job doesn't exist
        """
        ...

    async def mark_failed(
        self,
        job_id: UUID,
        reason: str,
    ) -> DeadLetterJob | None:
        """Mark a job as failed.

        Increments attempt counter. If max attempts reached,
        moves job to dead letter queue and returns DeadLetterJob.

        Constitutional Constraint (HC-6): Dead-letter alerting.

        Args:
            job_id: UUID of the failed job
            reason: Why the job failed

        Returns:
            DeadLetterJob if job was moved to DLQ, None if retry scheduled

        Raises:
            KeyError: If job doesn't exist
        """
        ...

    async def get_dlq_depth(self) -> int:
        """Get count of jobs in dead letter queue.

        Constitutional Constraint (HC-6): Alerting when depth > 0.

        Returns:
            Number of jobs in the dead letter queue
        """
        ...

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
        ...

    async def get_job(self, job_id: UUID) -> ScheduledJob | None:
        """Get a job by ID.

        Args:
            job_id: UUID of the job

        Returns:
            The ScheduledJob if found, None otherwise
        """
        ...
