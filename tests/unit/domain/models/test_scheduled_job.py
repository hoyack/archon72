"""Unit tests for ScheduledJob and DeadLetterJob domain models (Story 0.4, AC2).

Tests the domain model invariants and behavior for the job queue infrastructure.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.models.scheduled_job import (
    DeadLetterJob,
    JobStatus,
    ScheduledJob,
)


class TestScheduledJob:
    """Tests for ScheduledJob domain model."""

    def _make_job(
        self,
        job_id: UUID | None = None,
        job_type: str = "test_job",
        payload: dict | None = None,
        scheduled_for: datetime | None = None,
        status: JobStatus = JobStatus.PENDING,
        attempts: int = 0,
    ) -> ScheduledJob:
        """Factory for creating test jobs."""
        return ScheduledJob(
            id=job_id or uuid4(),
            job_type=job_type,
            payload=payload or {"key": "value"},
            scheduled_for=scheduled_for or datetime.now(timezone.utc),
            status=status,
            attempts=attempts,
        )

    def test_create_scheduled_job(self) -> None:
        """Test creating a valid ScheduledJob."""
        job_id = uuid4()
        scheduled_for = datetime.now(timezone.utc)

        job = ScheduledJob(
            id=job_id,
            job_type="referral_timeout",
            payload={"petition_id": "abc123"},
            scheduled_for=scheduled_for,
        )

        assert job.id == job_id
        assert job.job_type == "referral_timeout"
        assert job.payload == {"petition_id": "abc123"}
        assert job.scheduled_for == scheduled_for
        assert job.status == JobStatus.PENDING
        assert job.attempts == 0
        assert job.last_attempt_at is None

    def test_job_type_required(self) -> None:
        """Test that job_type cannot be empty."""
        with pytest.raises(ValueError, match="job_type cannot be empty"):
            ScheduledJob(
                id=uuid4(),
                job_type="",
                payload={},
                scheduled_for=datetime.now(timezone.utc),
            )

    def test_attempts_cannot_be_negative(self) -> None:
        """Test that attempts cannot be negative."""
        with pytest.raises(ValueError, match="attempts cannot be negative"):
            ScheduledJob(
                id=uuid4(),
                job_type="test",
                payload={},
                scheduled_for=datetime.now(timezone.utc),
                attempts=-1,
            )

    def test_scheduled_for_must_be_timezone_aware(self) -> None:
        """Test that scheduled_for must be timezone-aware."""
        with pytest.raises(ValueError, match="scheduled_for must be timezone-aware"):
            ScheduledJob(
                id=uuid4(),
                job_type="test",
                payload={},
                scheduled_for=datetime.now(),  # naive datetime
            )

    def test_with_status(self) -> None:
        """Test status transition creates new instance."""
        job = self._make_job(status=JobStatus.PENDING)

        processing_job = job.with_status(JobStatus.PROCESSING)

        # Original unchanged (frozen)
        assert job.status == JobStatus.PENDING
        # New instance has new status
        assert processing_job.status == JobStatus.PROCESSING
        # Other fields preserved
        assert processing_job.id == job.id
        assert processing_job.job_type == job.job_type

    def test_with_attempt(self) -> None:
        """Test incrementing attempts creates new instance."""
        job = self._make_job(attempts=0)

        job_with_attempt = job.with_attempt()

        assert job.attempts == 0  # Original unchanged
        assert job_with_attempt.attempts == 1
        assert job_with_attempt.last_attempt_at is not None

    def test_is_due_pending_past(self) -> None:
        """Test is_due returns True for pending job in the past."""
        past_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
        job = self._make_job(scheduled_for=past_time, status=JobStatus.PENDING)

        assert job.is_due() is True

    def test_is_due_processing_not_due(self) -> None:
        """Test is_due returns False for processing job."""
        past_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
        job = self._make_job(scheduled_for=past_time, status=JobStatus.PROCESSING)

        assert job.is_due() is False

    def test_should_move_to_dlq_max_attempts(self) -> None:
        """Test should_move_to_dlq when max attempts reached."""
        job = self._make_job(
            attempts=ScheduledJob.MAX_ATTEMPTS,
            status=JobStatus.FAILED,
        )

        assert job.should_move_to_dlq() is True

    def test_should_move_to_dlq_under_max_attempts(self) -> None:
        """Test should_move_to_dlq when under max attempts."""
        job = self._make_job(
            attempts=ScheduledJob.MAX_ATTEMPTS - 1,
            status=JobStatus.FAILED,
        )

        assert job.should_move_to_dlq() is False

    def test_to_dict_serialization(self) -> None:
        """Test to_dict serializes properly (D2: Never use asdict)."""
        job_id = uuid4()
        scheduled_for = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        job = ScheduledJob(
            id=job_id,
            job_type="test",
            payload={"key": "value"},
            scheduled_for=scheduled_for,
            status=JobStatus.PENDING,
        )

        result = job.to_dict()

        assert result["id"] == str(job_id)
        assert result["job_type"] == "test"
        assert result["payload"] == {"key": "value"}
        assert result["scheduled_for"] == scheduled_for.isoformat()
        assert result["status"] == "pending"


class TestDeadLetterJob:
    """Tests for DeadLetterJob domain model."""

    def test_create_dead_letter_job(self) -> None:
        """Test creating a valid DeadLetterJob."""
        dlq_id = uuid4()
        original_id = uuid4()

        dlq_job = DeadLetterJob(
            id=dlq_id,
            original_job_id=original_id,
            job_type="referral_timeout",
            payload={"petition_id": "abc123"},
            failure_reason="Connection timeout",
            attempts=3,
        )

        assert dlq_job.id == dlq_id
        assert dlq_job.original_job_id == original_id
        assert dlq_job.job_type == "referral_timeout"
        assert dlq_job.failure_reason == "Connection timeout"
        assert dlq_job.attempts == 3

    def test_job_type_required(self) -> None:
        """Test that job_type cannot be empty."""
        with pytest.raises(ValueError, match="job_type cannot be empty"):
            DeadLetterJob(
                id=uuid4(),
                original_job_id=uuid4(),
                job_type="",
                payload={},
                failure_reason="test",
            )

    def test_failure_reason_required(self) -> None:
        """Test that failure_reason cannot be empty."""
        with pytest.raises(ValueError, match="failure_reason cannot be empty"):
            DeadLetterJob(
                id=uuid4(),
                original_job_id=uuid4(),
                job_type="test",
                payload={},
                failure_reason="",
            )

    def test_from_failed_job(self) -> None:
        """Test creating DeadLetterJob from failed ScheduledJob."""
        failed_job = ScheduledJob(
            id=uuid4(),
            job_type="referral_timeout",
            payload={"petition_id": "abc123"},
            scheduled_for=datetime.now(timezone.utc),
            status=JobStatus.FAILED,
            attempts=3,
        )

        dlq_id = uuid4()
        dlq_job = DeadLetterJob.from_failed_job(
            dlq_id,
            failed_job,
            "Max retries exceeded",
        )

        assert dlq_job.id == dlq_id
        assert dlq_job.original_job_id == failed_job.id
        assert dlq_job.job_type == failed_job.job_type
        assert dlq_job.payload == failed_job.payload
        assert dlq_job.failure_reason == "Max retries exceeded"
        assert dlq_job.attempts == failed_job.attempts

    def test_to_dict_serialization(self) -> None:
        """Test to_dict serializes properly (D2: Never use asdict)."""
        dlq_id = uuid4()
        original_id = uuid4()

        dlq_job = DeadLetterJob(
            id=dlq_id,
            original_job_id=original_id,
            job_type="test",
            payload={"key": "value"},
            failure_reason="Test failure",
            attempts=3,
        )

        result = dlq_job.to_dict()

        assert result["id"] == str(dlq_id)
        assert result["original_job_id"] == str(original_id)
        assert result["job_type"] == "test"
        assert result["payload"] == {"key": "value"}
        assert result["failure_reason"] == "Test failure"
        assert result["attempts"] == 3


class TestJobStatus:
    """Tests for JobStatus enum."""

    def test_status_values(self) -> None:
        """Test JobStatus enum values match database enum."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.PROCESSING.value == "processing"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
