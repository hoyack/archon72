"""Unit tests for exit domain models.

Story: consent-gov-7.1: Exit Request Processing

Tests for:
- ExitStatus enum behavior
- ExitRequest domain model
- ExitResult domain model
- Validation and immutability guarantees
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.governance.exit.errors import (
    AlreadyExitedError,
    ExitBarrierError,
    ExitNotFoundError,
)
from src.domain.governance.exit.exit_request import ExitRequest
from src.domain.governance.exit.exit_result import MAX_ROUND_TRIPS, ExitResult
from src.domain.governance.exit.exit_status import ExitStatus

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


@pytest.fixture
def request_id():
    """Generate a request ID."""
    return uuid4()


@pytest.fixture
def cluster_id():
    """Generate a cluster ID."""
    return uuid4()


@pytest.fixture
def task_ids():
    """Generate task IDs."""
    return tuple(uuid4() for _ in range(3))


@pytest.fixture
def exit_request(request_id, cluster_id, task_ids, now) -> ExitRequest:
    """Create a valid exit request."""
    return ExitRequest(
        request_id=request_id,
        cluster_id=cluster_id,
        requested_at=now,
        tasks_at_request=task_ids,
    )


@pytest.fixture
def exit_result(request_id, cluster_id, now) -> ExitResult:
    """Create a valid exit result."""
    completed_at = now + timedelta(milliseconds=100)
    return ExitResult(
        request_id=request_id,
        cluster_id=cluster_id,
        status=ExitStatus.COMPLETED,
        initiated_at=now,
        completed_at=completed_at,
        tasks_affected=3,
        obligations_released=3,
        round_trips=2,
    )


# =============================================================================
# ExitStatus Tests
# =============================================================================


class TestExitStatus:
    """Tests for ExitStatus enum."""

    def test_has_three_statuses(self):
        """ExitStatus should have exactly 3 values."""
        assert len(ExitStatus) == 3

    def test_initiated_status(self):
        """INITIATED status exists and has correct value."""
        assert ExitStatus.INITIATED.value == "initiated"

    def test_processing_status(self):
        """PROCESSING status exists and has correct value."""
        assert ExitStatus.PROCESSING.value == "processing"

    def test_completed_status(self):
        """COMPLETED status exists and has correct value."""
        assert ExitStatus.COMPLETED.value == "completed"

    def test_only_completed_is_terminal(self):
        """Only COMPLETED is terminal."""
        assert not ExitStatus.INITIATED.is_terminal
        assert not ExitStatus.PROCESSING.is_terminal
        assert ExitStatus.COMPLETED.is_terminal

    def test_no_interaction_allowed_at_any_status(self):
        """No interaction allowed at any exit status.

        Per NFR-EXIT-01: Once exit is initiated, no further interaction
        is allowed. This prevents barriers.
        """
        for status in ExitStatus:
            assert not status.allows_interaction

    def test_no_pending_review_status_exists(self):
        """No PENDING_REVIEW status exists (would allow blocking)."""
        status_values = [s.value for s in ExitStatus]
        assert "pending_review" not in status_values
        assert "awaiting_approval" not in status_values
        assert "cancelled" not in status_values
        assert "rejected" not in status_values


# =============================================================================
# ExitRequest Tests
# =============================================================================


class TestExitRequest:
    """Tests for ExitRequest domain model."""

    def test_create_valid_request(self, exit_request):
        """Can create a valid exit request."""
        assert exit_request.request_id is not None
        assert exit_request.cluster_id is not None
        assert exit_request.requested_at is not None
        assert len(exit_request.tasks_at_request) == 3

    def test_request_is_immutable(self, exit_request):
        """ExitRequest is frozen (immutable)."""
        with pytest.raises(AttributeError):
            exit_request.cluster_id = uuid4()

    def test_tasks_at_request_is_tuple(self, exit_request):
        """tasks_at_request is a tuple (immutable)."""
        assert isinstance(exit_request.tasks_at_request, tuple)

    def test_active_task_count(self, exit_request):
        """active_task_count property works."""
        assert exit_request.active_task_count == 3

    def test_has_active_tasks_true(self, exit_request):
        """has_active_tasks is True when tasks exist."""
        assert exit_request.has_active_tasks is True

    def test_has_active_tasks_false_when_empty(self, request_id, cluster_id, now):
        """has_active_tasks is False when no tasks."""
        request = ExitRequest(
            request_id=request_id,
            cluster_id=cluster_id,
            requested_at=now,
            tasks_at_request=(),  # Empty tuple
        )
        assert request.has_active_tasks is False

    def test_no_reason_field(self):
        """ExitRequest has no 'reason' field (unconditional right)."""
        assert not hasattr(ExitRequest, "reason")

    def test_invalid_request_id_type(self, cluster_id, now, task_ids):
        """request_id must be UUID."""
        with pytest.raises(ValueError, match="request_id must be UUID"):
            ExitRequest(
                request_id="not-a-uuid",
                cluster_id=cluster_id,
                requested_at=now,
                tasks_at_request=task_ids,
            )

    def test_invalid_cluster_id_type(self, request_id, now, task_ids):
        """cluster_id must be UUID."""
        with pytest.raises(ValueError, match="cluster_id must be UUID"):
            ExitRequest(
                request_id=request_id,
                cluster_id="not-a-uuid",
                requested_at=now,
                tasks_at_request=task_ids,
            )

    def test_invalid_requested_at_type(self, request_id, cluster_id, task_ids):
        """requested_at must be datetime."""
        with pytest.raises(ValueError, match="requested_at must be datetime"):
            ExitRequest(
                request_id=request_id,
                cluster_id=cluster_id,
                requested_at="not-a-datetime",
                tasks_at_request=task_ids,
            )

    def test_invalid_tasks_at_request_type(self, request_id, cluster_id, now):
        """tasks_at_request must be tuple."""
        with pytest.raises(ValueError, match="tasks_at_request must be tuple"):
            ExitRequest(
                request_id=request_id,
                cluster_id=cluster_id,
                requested_at=now,
                tasks_at_request=[uuid4(), uuid4()],  # List, not tuple
            )

    def test_invalid_task_id_in_tuple(self, request_id, cluster_id, now):
        """All task IDs must be UUIDs."""
        with pytest.raises(ValueError, match="must be UUID"):
            ExitRequest(
                request_id=request_id,
                cluster_id=cluster_id,
                requested_at=now,
                tasks_at_request=(uuid4(), "not-a-uuid"),
            )


# =============================================================================
# ExitResult Tests
# =============================================================================


class TestExitResult:
    """Tests for ExitResult domain model."""

    def test_create_valid_result(self, exit_result):
        """Can create a valid exit result."""
        assert exit_result.request_id is not None
        assert exit_result.status == ExitStatus.COMPLETED
        assert exit_result.round_trips == 2

    def test_result_is_immutable(self, exit_result):
        """ExitResult is frozen (immutable)."""
        with pytest.raises(AttributeError):
            exit_result.status = ExitStatus.INITIATED

    def test_is_complete_true(self, exit_result):
        """is_complete is True when status is COMPLETED."""
        assert exit_result.is_complete is True

    def test_is_complete_false(self, request_id, cluster_id, now):
        """is_complete is False when status is not COMPLETED."""
        result = ExitResult(
            request_id=request_id,
            cluster_id=cluster_id,
            status=ExitStatus.PROCESSING,
            initiated_at=now,
            completed_at=None,
            tasks_affected=0,
            obligations_released=0,
            round_trips=1,
        )
        assert result.is_complete is False

    def test_duration_ms_calculated(self, exit_result):
        """duration_ms is calculated correctly."""
        assert exit_result.duration_ms == 100.0

    def test_duration_ms_none_when_not_complete(self, request_id, cluster_id, now):
        """duration_ms is None when not complete."""
        result = ExitResult(
            request_id=request_id,
            cluster_id=cluster_id,
            status=ExitStatus.PROCESSING,
            initiated_at=now,
            completed_at=None,
            tasks_affected=0,
            obligations_released=0,
            round_trips=1,
        )
        assert result.duration_ms is None

    def test_max_round_trips_is_two(self):
        """MAX_ROUND_TRIPS constant is 2 per NFR-EXIT-01."""
        assert MAX_ROUND_TRIPS == 2

    def test_round_trips_at_limit(self, request_id, cluster_id, now):
        """Result with exactly 2 round-trips is valid."""
        completed_at = now + timedelta(milliseconds=100)
        result = ExitResult(
            request_id=request_id,
            cluster_id=cluster_id,
            status=ExitStatus.COMPLETED,
            initiated_at=now,
            completed_at=completed_at,
            tasks_affected=0,
            obligations_released=0,
            round_trips=2,
        )
        assert result.round_trips == 2

    def test_round_trips_exceeds_limit_raises(self, request_id, cluster_id, now):
        """Result with >2 round-trips raises error (NFR-EXIT-01 violation).

        Per NFR-EXIT-01: Exit completes in ≤2 message round-trips.
        """
        completed_at = now + timedelta(milliseconds=100)
        with pytest.raises(ValueError, match="NFR-EXIT-01 VIOLATION"):
            ExitResult(
                request_id=request_id,
                cluster_id=cluster_id,
                status=ExitStatus.COMPLETED,
                initiated_at=now,
                completed_at=completed_at,
                tasks_affected=0,
                obligations_released=0,
                round_trips=3,  # Exceeds limit
            )

    def test_completed_at_before_initiated_raises(self, request_id, cluster_id, now):
        """completed_at cannot be before initiated_at."""
        with pytest.raises(ValueError, match="cannot be before initiated_at"):
            ExitResult(
                request_id=request_id,
                cluster_id=cluster_id,
                status=ExitStatus.COMPLETED,
                initiated_at=now,
                completed_at=now - timedelta(hours=1),
                tasks_affected=0,
                obligations_released=0,
                round_trips=2,
            )

    def test_negative_tasks_affected_raises(self, request_id, cluster_id, now):
        """tasks_affected must be non-negative."""
        with pytest.raises(ValueError, match="non-negative"):
            ExitResult(
                request_id=request_id,
                cluster_id=cluster_id,
                status=ExitStatus.COMPLETED,
                initiated_at=now,
                completed_at=now + timedelta(milliseconds=100),
                tasks_affected=-1,
                obligations_released=0,
                round_trips=2,
            )


# =============================================================================
# Error Tests
# =============================================================================


class TestExitErrors:
    """Tests for exit-related errors."""

    def test_exit_barrier_error_message(self):
        """ExitBarrierError includes barrier description."""
        error = ExitBarrierError("Confirmation prompts")
        assert "NFR-EXIT-01 VIOLATION" in str(error)
        assert "Confirmation prompts" in str(error)

    def test_already_exited_error_message(self):
        """AlreadyExitedError includes cluster ID."""
        error = AlreadyExitedError("cluster-123")
        assert "cluster-123" in str(error)
        assert "already exited" in str(error)

    def test_exit_not_found_error_message(self):
        """ExitNotFoundError includes request ID."""
        error = ExitNotFoundError("request-456")
        assert "request-456" in str(error)


# =============================================================================
# No Barrier Design Tests
# =============================================================================


class TestNoBarrierDesign:
    """Tests verifying no barrier mechanisms exist in models."""

    def test_exit_request_has_no_confirmation_field(self):
        """ExitRequest has no confirmation-related fields."""
        assert not hasattr(ExitRequest, "confirmed")
        assert not hasattr(ExitRequest, "confirmation_required")
        assert not hasattr(ExitRequest, "waiting_period")

    def test_exit_result_has_no_approval_field(self):
        """ExitResult has no approval-related fields."""
        assert not hasattr(ExitResult, "approved")
        assert not hasattr(ExitResult, "approved_by")
        assert not hasattr(ExitResult, "rejection_reason")

    def test_exit_status_has_no_pending_approval(self):
        """ExitStatus has no states that imply waiting for approval."""
        status_names = [s.name for s in ExitStatus]
        assert "PENDING_APPROVAL" not in status_names
        assert "AWAITING_REVIEW" not in status_names
        assert "ON_HOLD" not in status_names
