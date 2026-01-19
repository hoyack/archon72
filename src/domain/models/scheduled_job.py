"""Scheduled job domain models for deadline monitoring (Story 0.4, AC1-2).

This module defines the domain models for the job queue infrastructure
supporting referral timeouts and deliberation timeouts in the
Three Fates petition system.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → All job failures logged and alerted
- CT-12: Witnessing creates accountability → Job execution is auditable
- HP-1: Job queue for reliable deadline execution
- HC-6: Dead-letter alerting for failed jobs
- NFR-7.5: Timeout job monitoring with heartbeat on scheduler
- FM-7.1: Persistent job queue prevents "timeout never fires" failure mode
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID


class JobStatus(Enum):
    """Status of a scheduled job (AC1).

    Status transitions:
    PENDING -> PROCESSING -> COMPLETED
                         -> FAILED (after 3 retries -> DLQ)

    Statuses:
        PENDING: Job scheduled, waiting for execution time
        PROCESSING: Job claimed by worker, execution in progress
        COMPLETED: Job successfully executed
        FAILED: Job failed (will be retried or moved to DLQ)
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, eq=True)
class ScheduledJob:
    """A scheduled job for deadline monitoring (AC1, AC2).

    Constitutional Constraints:
    - CT-12: Frozen dataclass ensures immutability
    - HP-1: Supports reliable deadline execution
    - FM-7.1: Persistent job queue prevents timeout failures

    Job Types (defined in later stories):
    - referral_timeout: Knight referral deadline (FR-4.5, Story Epic 4)
    - deliberation_timeout: Three Fates deliberation deadline (NFR-10.2, Story Epic 2B)
    - escalation_check: Periodic co-signer count check (Story Epic 5)

    Attributes:
        id: UUIDv7 unique identifier for the job
        job_type: Type of job (referral_timeout, deliberation_timeout, etc.)
        payload: Job-specific data (petition_id, deadline details, etc.)
        scheduled_for: Timestamp when job should be executed
        created_at: Timestamp when job was scheduled
        attempts: Number of execution attempts (max 3 before DLQ)
        last_attempt_at: Timestamp of last execution attempt
        status: Current job status
    """

    id: UUID
    job_type: str
    payload: dict[str, Any]
    scheduled_for: datetime
    created_at: datetime = field(default_factory=_utc_now)
    attempts: int = field(default=0)
    last_attempt_at: datetime | None = field(default=None)
    status: JobStatus = field(default=JobStatus.PENDING)

    MAX_ATTEMPTS: int = 3

    def __post_init__(self) -> None:
        """Validate scheduled job fields."""
        if not self.job_type:
            raise ValueError("job_type cannot be empty")
        if self.attempts < 0:
            raise ValueError("attempts cannot be negative")
        # Ensure scheduled_for is timezone-aware
        if self.scheduled_for.tzinfo is None:
            raise ValueError("scheduled_for must be timezone-aware (UTC)")

    def with_status(self, new_status: JobStatus) -> ScheduledJob:
        """Create new job with updated status.

        Since ScheduledJob is frozen, returns new instance.

        Args:
            new_status: The new status to transition to.

        Returns:
            New ScheduledJob with updated status.
        """
        return ScheduledJob(
            id=self.id,
            job_type=self.job_type,
            payload=self.payload,
            scheduled_for=self.scheduled_for,
            created_at=self.created_at,
            attempts=self.attempts,
            last_attempt_at=self.last_attempt_at,
            status=new_status,
        )

    def with_attempt(self) -> ScheduledJob:
        """Create new job with incremented attempt count.

        Updates attempts counter and last_attempt_at timestamp.

        Returns:
            New ScheduledJob with incremented attempts.
        """
        return ScheduledJob(
            id=self.id,
            job_type=self.job_type,
            payload=self.payload,
            scheduled_for=self.scheduled_for,
            created_at=self.created_at,
            attempts=self.attempts + 1,
            last_attempt_at=_utc_now(),
            status=self.status,
        )

    def is_due(self) -> bool:
        """Check if job is due for execution.

        Returns:
            True if scheduled_for <= now and status is PENDING.
        """
        return self.status == JobStatus.PENDING and self.scheduled_for <= _utc_now()

    def should_move_to_dlq(self) -> bool:
        """Check if job should be moved to dead letter queue.

        Returns:
            True if attempts >= MAX_ATTEMPTS and status is FAILED.
        """
        return self.status == JobStatus.FAILED and self.attempts >= self.MAX_ATTEMPTS

    def to_dict(self) -> dict[str, Any]:
        """Serialize job to dictionary for event payloads.

        Constitutional Constraint (D2): Never use asdict() for events.
        Uses explicit serialization to handle UUID and datetime properly.

        Returns:
            Dictionary representation of the job.
        """
        return {
            "id": str(self.id),
            "job_type": self.job_type,
            "payload": self.payload,
            "scheduled_for": self.scheduled_for.isoformat(),
            "created_at": self.created_at.isoformat(),
            "attempts": self.attempts,
            "last_attempt_at": (
                self.last_attempt_at.isoformat() if self.last_attempt_at else None
            ),
            "status": self.status.value,
        }


@dataclass(frozen=True, eq=True)
class DeadLetterJob:
    """A failed job in the dead letter queue (AC1, HC-6).

    Constitutional Constraints:
    - CT-11: Silent failure destroys legitimacy → DLQ enables alerting
    - HC-6: Dead-letter alerting for failed jobs

    Attributes:
        id: UUIDv7 unique identifier for the DLQ entry
        original_job_id: Reference to the original scheduled_jobs.id
        job_type: Copied job type for independent querying
        payload: Copied payload for debugging and retry analysis
        failure_reason: Detailed reason for job failure
        failed_at: Timestamp when job was moved to DLQ
        attempts: Total execution attempts before failure
    """

    id: UUID
    original_job_id: UUID
    job_type: str
    payload: dict[str, Any]
    failure_reason: str
    failed_at: datetime = field(default_factory=_utc_now)
    attempts: int = field(default=0)

    def __post_init__(self) -> None:
        """Validate dead letter job fields."""
        if not self.job_type:
            raise ValueError("job_type cannot be empty")
        if not self.failure_reason:
            raise ValueError("failure_reason cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        """Serialize dead letter job to dictionary for event payloads.

        Constitutional Constraint (D2): Never use asdict() for events.

        Returns:
            Dictionary representation of the dead letter job.
        """
        return {
            "id": str(self.id),
            "original_job_id": str(self.original_job_id),
            "job_type": self.job_type,
            "payload": self.payload,
            "failure_reason": self.failure_reason,
            "failed_at": self.failed_at.isoformat(),
            "attempts": self.attempts,
        }

    @classmethod
    def from_failed_job(
        cls,
        dlq_id: UUID,
        job: ScheduledJob,
        failure_reason: str,
    ) -> DeadLetterJob:
        """Create a DeadLetterJob from a failed ScheduledJob.

        Factory method for creating DLQ entries from failed jobs.

        Args:
            dlq_id: UUID for the new DLQ entry
            job: The failed ScheduledJob
            failure_reason: Why the job ultimately failed

        Returns:
            New DeadLetterJob instance
        """
        return cls(
            id=dlq_id,
            original_job_id=job.id,
            job_type=job.job_type,
            payload=job.payload,
            failure_reason=failure_reason,
            failed_at=_utc_now(),
            attempts=job.attempts,
        )
