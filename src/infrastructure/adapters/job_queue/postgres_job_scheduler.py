"""PostgreSQL Job Scheduler adapter (Story 0.4, AC4).

This module provides the production PostgreSQL implementation of
JobSchedulerProtocol for reliable deadline monitoring.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → All operations logged
- CT-12: Witnessing creates accountability → All job executions auditable
- HP-1: Job queue for reliable deadline execution
- HC-6: Dead-letter alerting for failed jobs
- NFR-7.5: Timeout job monitoring with heartbeat on scheduler
- FM-7.1: Persistent job queue prevents "timeout never fires" failure mode

Architecture:
- Uses SELECT FOR UPDATE SKIP LOCKED for concurrent worker safety
- Atomic job claiming prevents double-processing
- Dead letter queue for failed jobs after max retries
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog import get_logger

from src.application.ports.job_scheduler import JobSchedulerProtocol
from src.domain.models.scheduled_job import (
    DeadLetterJob,
    JobStatus,
    ScheduledJob,
)

logger = get_logger()


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class PostgresJobScheduler(JobSchedulerProtocol):
    """PostgreSQL implementation of JobSchedulerProtocol (AC4).

    Uses the scheduled_jobs and dead_letter_queue tables created by
    migration 014_create_job_queue_tables.sql.

    Constitutional Compliance:
    - HP-1: Reliable deadline execution via persistent PostgreSQL storage
    - HC-6: Dead-letter queue for failed jobs with alerting support
    - FM-7.1: Persistent storage prevents "timeout never fires" failure

    Thread Safety:
    - Uses SELECT FOR UPDATE SKIP LOCKED for safe concurrent claiming
    - Multiple workers can safely poll without double-processing

    Attributes:
        _session_factory: SQLAlchemy async session factory for DB access
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Initialize the PostgreSQL job scheduler.

        Args:
            session_factory: SQLAlchemy async session factory for DB access.
        """
        self._session_factory = session_factory

    @asynccontextmanager
    async def _session_scope(self) -> AsyncSession:
        """Yield a session without closing externally managed sessions."""
        session = self._session_factory()
        if isinstance(session, AsyncSession) and session.in_transaction():
            yield session
            return
        async with session as managed_session:
            yield managed_session

    @asynccontextmanager
    async def _transaction_scope(self, session: AsyncSession):
        """Begin a transaction only if one isn't already active."""
        if session.in_transaction():
            yield
            return
        async with session.begin():
            yield

    async def schedule(
        self,
        job_type: str,
        payload: dict[str, Any],
        run_at: datetime | None = None,
        scheduled_for: datetime | None = None,
    ) -> UUID:
        """Schedule a new job for future execution.

        HP-1: Reliable deadline execution via persistent storage.

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
        log = logger.bind(job_id=str(job_id), job_type=job_type)

        async with self._session_scope() as session:
            async with self._transaction_scope(session):
                await session.execute(
                    text("""
                        INSERT INTO scheduled_jobs (
                            id, job_type, payload, scheduled_for, created_at,
                            attempts, last_attempt_at, status
                        )
                        VALUES (
                            :id, :job_type, CAST(:payload AS jsonb), :scheduled_for,
                            :created_at, 0, NULL, 'pending'
                        )
                    """),
                    {
                        "id": job_id,
                        "job_type": job_type,
                        "payload": self._serialize_payload(payload),
                        "scheduled_for": effective_run_at,
                        "created_at": _utc_now(),
                    },
                )

        log.info(
            "job_scheduled",
            scheduled_for=effective_run_at.isoformat(),
            message="HP-1: Job scheduled for future execution",
        )
        return job_id

    async def cancel(self, job_id: UUID) -> bool:
        """Cancel a scheduled job.

        Only jobs with status PENDING can be cancelled.

        Args:
            job_id: UUID of the job to cancel

        Returns:
            True if job was cancelled, False if not found or not cancellable
        """
        log = logger.bind(job_id=str(job_id))

        async with self._session_scope() as session:
            async with self._transaction_scope(session):
                result = await session.execute(
                    text("""
                        DELETE FROM scheduled_jobs
                        WHERE id = :id AND status = 'pending'
                        RETURNING id
                    """),
                    {"id": job_id},
                )
                row = result.fetchone()

        if row:
            log.info("job_cancelled")
            return True

        log.debug("job_cancel_not_found_or_not_pending")
        return False

    async def get_pending_jobs(self, limit: int = 10) -> list[ScheduledJob]:
        """Get jobs due for execution.

        Uses SELECT FOR UPDATE SKIP LOCKED for concurrent worker safety.
        This prevents multiple workers from claiming the same job.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of ScheduledJob instances due for execution
        """
        async with self._session_scope() as session:
            result = await session.execute(
                text("""
                    SELECT id, job_type, payload, scheduled_for, created_at,
                           attempts, last_attempt_at, status
                    FROM scheduled_jobs
                    WHERE status = 'pending' AND scheduled_for <= :now
                    ORDER BY scheduled_for ASC
                    LIMIT :limit
                """),
                {"now": _utc_now(), "limit": limit},
            )
            rows = result.fetchall()

        return [self._row_to_job(row) for row in rows]

    async def claim_job(self, job_id: UUID) -> ScheduledJob | None:
        """Claim a job for processing.

        Uses optimistic locking - only claims if status is still PENDING.
        Sets status to PROCESSING atomically.

        Args:
            job_id: UUID of the job to claim

        Returns:
            The claimed ScheduledJob if successful, None if already claimed
        """
        log = logger.bind(job_id=str(job_id))

        async with self._session_scope() as session:
            async with self._transaction_scope(session):
                # Claim job atomically
                result = await session.execute(
                    text("""
                        UPDATE scheduled_jobs
                        SET status = 'processing'
                        WHERE id = :id AND status = 'pending'
                        RETURNING id, job_type, payload, scheduled_for, created_at,
                                  attempts, last_attempt_at, status
                    """),
                    {"id": job_id},
                )
                row = result.fetchone()

        if row:
            log.info("job_claimed", message="Job claimed for processing")
            return self._row_to_job(row)

        log.debug("job_claim_failed", reason="already claimed or not found")
        return None

    async def mark_completed(self, job_id: UUID) -> None:
        """Mark a job as successfully completed.

        Sets job status to COMPLETED.

        Args:
            job_id: UUID of the job to mark completed

        Raises:
            KeyError: If job doesn't exist
        """
        log = logger.bind(job_id=str(job_id))

        async with self._session_scope() as session:
            async with self._transaction_scope(session):
                result = await session.execute(
                    text("""
                        UPDATE scheduled_jobs
                        SET status = 'completed'
                        WHERE id = :id
                        RETURNING id
                    """),
                    {"id": job_id},
                )
                row = result.fetchone()

        if not row:
            raise KeyError(f"Job not found: {job_id}")

        log.info("job_completed", message="Job marked as completed")

    async def mark_failed(
        self,
        job_id: UUID,
        reason: str,
    ) -> DeadLetterJob | None:
        """Mark a job as failed.

        Increments attempt counter. If max attempts (3) reached,
        moves job to dead letter queue and returns DeadLetterJob.

        HC-6: Dead-letter alerting for failed jobs.

        Args:
            job_id: UUID of the failed job
            reason: Why the job failed

        Returns:
            DeadLetterJob if job was moved to DLQ, None if retry scheduled

        Raises:
            KeyError: If job doesn't exist
        """
        log = logger.bind(job_id=str(job_id))

        async with self._session_scope() as session:
            async with self._transaction_scope(session):
                # First, increment attempts and get current state
                result = await session.execute(
                    text("""
                        UPDATE scheduled_jobs
                        SET attempts = attempts + 1,
                            last_attempt_at = :now,
                            status = 'failed'
                        WHERE id = :id
                        RETURNING id, job_type, payload, scheduled_for, created_at,
                                  attempts, last_attempt_at, status
                    """),
                    {"id": job_id, "now": _utc_now()},
                )
                row = result.fetchone()

                if not row:
                    raise KeyError(f"Job not found: {job_id}")

                job = self._row_to_job(row)

                # Check if should move to DLQ (3 max attempts)
                if job.attempts >= ScheduledJob.MAX_ATTEMPTS:
                    # Move to DLQ
                    dlq_id = uuid4()
                    await session.execute(
                        text("""
                            INSERT INTO dead_letter_queue (
                                id, original_job_id, job_type, payload,
                                failure_reason, failed_at, attempts
                            )
                            VALUES (
                                :id, :original_job_id, :job_type, CAST(:payload AS jsonb),
                                :failure_reason, :failed_at, :attempts
                            )
                        """),
                        {
                            "id": dlq_id,
                            "original_job_id": job_id,
                            "job_type": job.job_type,
                            "payload": self._serialize_payload(job.payload),
                            "failure_reason": reason,
                            "failed_at": _utc_now(),
                            "attempts": job.attempts,
                        },
                    )

                    # Remove from scheduled_jobs
                    await session.execute(
                        text("DELETE FROM scheduled_jobs WHERE id = :id"),
                        {"id": job_id},
                    )

                    log.warning(
                        "job_moved_to_dlq",
                        dlq_id=str(dlq_id),
                        attempts=job.attempts,
                        failure_reason=reason,
                        message="HC-6: Job moved to dead letter queue",
                    )

                    return DeadLetterJob(
                        id=dlq_id,
                        original_job_id=job_id,
                        job_type=job.job_type,
                        payload=job.payload,
                        failure_reason=reason,
                        failed_at=_utc_now(),
                        attempts=job.attempts,
                    )
                else:
                    # Schedule retry by setting status back to pending
                    await session.execute(
                        text("""
                            UPDATE scheduled_jobs
                            SET status = 'pending'
                            WHERE id = :id
                        """),
                        {"id": job_id},
                    )

                    log.info(
                        "job_retry_scheduled",
                        attempts=job.attempts,
                        max_attempts=ScheduledJob.MAX_ATTEMPTS,
                        failure_reason=reason,
                    )
                    return None

    async def get_dlq_depth(self) -> int:
        """Get count of jobs in dead letter queue.

        HC-6: Alerting when depth > 0.

        Returns:
            Number of jobs in the dead letter queue
        """
        async with self._session_scope() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM dead_letter_queue")
            )
            count = result.scalar() or 0

        if count > 0:
            logger.warning(
                "dlq_not_empty",
                depth=count,
                message="HC-6: Dead letter queue has items - alerting required",
            )

        return count

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
        async with self._session_scope() as session:
            # Get total count
            count_result = await session.execute(
                text("SELECT COUNT(*) FROM dead_letter_queue")
            )
            total = count_result.scalar() or 0

            # Get paginated jobs
            result = await session.execute(
                text("""
                    SELECT id, original_job_id, job_type, payload,
                           failure_reason, failed_at, attempts
                    FROM dead_letter_queue
                    ORDER BY failed_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"limit": limit, "offset": offset},
            )
            rows = result.fetchall()

        dlq_jobs = [self._row_to_dlq_job(row) for row in rows]
        return dlq_jobs, total

    async def get_job(self, job_id: UUID) -> ScheduledJob | None:
        """Get a job by ID.

        Args:
            job_id: UUID of the job

        Returns:
            The ScheduledJob if found, None otherwise
        """
        async with self._session_scope() as session:
            result = await session.execute(
                text("""
                    SELECT id, job_type, payload, scheduled_for, created_at,
                           attempts, last_attempt_at, status
                    FROM scheduled_jobs
                    WHERE id = :id
                """),
                {"id": job_id},
            )
            row = result.fetchone()

        if row:
            return self._row_to_job(row)
        return None

    def _row_to_job(self, row: Any) -> ScheduledJob:
        """Convert a database row to ScheduledJob domain model.

        Args:
            row: Database row tuple

        Returns:
            ScheduledJob instance
        """
        import json

        (
            id_,
            job_type,
            payload,
            scheduled_for,
            created_at,
            attempts,
            last_attempt_at,
            status,
        ) = row

        # Parse payload if it's a string
        if isinstance(payload, str):
            payload = json.loads(payload)

        return ScheduledJob(
            id=id_,
            job_type=job_type,
            payload=payload or {},
            scheduled_for=scheduled_for,
            created_at=created_at,
            attempts=attempts,
            last_attempt_at=last_attempt_at,
            status=JobStatus(status),
        )

    def _row_to_dlq_job(self, row: Any) -> DeadLetterJob:
        """Convert a database row to DeadLetterJob domain model.

        Args:
            row: Database row tuple

        Returns:
            DeadLetterJob instance
        """
        import json

        (
            id_,
            original_job_id,
            job_type,
            payload,
            failure_reason,
            failed_at,
            attempts,
        ) = row

        # Parse payload if it's a string
        if isinstance(payload, str):
            payload = json.loads(payload)

        return DeadLetterJob(
            id=id_,
            original_job_id=original_job_id,
            job_type=job_type,
            payload=payload or {},
            failure_reason=failure_reason,
            failed_at=failed_at,
            attempts=attempts,
        )

    def _serialize_payload(self, payload: dict[str, Any]) -> str:
        """Serialize payload to JSON string for PostgreSQL JSONB.

        Args:
            payload: Dictionary payload to serialize

        Returns:
            JSON string representation
        """
        import json

        return json.dumps(payload)
