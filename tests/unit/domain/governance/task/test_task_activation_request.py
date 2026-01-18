"""Tests for TaskActivationRequest domain models.

Story: consent-gov-2.2: Task Activation Request

Tests the domain models for task activation:
- TaskActivationRequest
- TaskActivationResult
- FilteredContent
- TaskStateView
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.domain.governance.task.task_activation_request import (
    FilteredContent,
    FilterOutcome,
    RoutingStatus,
    TaskActivationRequest,
    TaskActivationResult,
    TaskStateView,
)


class TestFilteredContent:
    """Tests for FilteredContent wrapper."""

    def test_filtered_content_is_frozen(self):
        """FilteredContent should be immutable."""
        content = FilteredContent(
            content="Test content",
            filter_decision_id=uuid4(),
            original_hash="blake3:abc123",
        )
        with pytest.raises(AttributeError):
            content.content = "Modified"  # type: ignore

    def test_filtered_content_with_transformation(self):
        """FilteredContent can indicate transformation was applied."""
        content = FilteredContent(
            content="Modified content",
            filter_decision_id=uuid4(),
            original_hash="blake3:abc123",
            transformation_applied=True,
        )
        assert content.transformation_applied is True

    def test_filtered_content_default_no_transformation(self):
        """FilteredContent defaults to no transformation."""
        content = FilteredContent(
            content="Original content",
            filter_decision_id=uuid4(),
            original_hash="blake3:abc123",
        )
        assert content.transformation_applied is False


class TestFilterOutcome:
    """Tests for FilterOutcome enum."""

    def test_all_outcomes_defined(self):
        """All filter outcomes are defined."""
        assert FilterOutcome.ACCEPTED.value == "accepted"
        assert FilterOutcome.TRANSFORMED.value == "transformed"
        assert FilterOutcome.REJECTED.value == "rejected"
        assert FilterOutcome.BLOCKED.value == "blocked"

    def test_outcomes_are_strings(self):
        """Filter outcomes are string enums."""
        assert isinstance(FilterOutcome.ACCEPTED, str)


class TestRoutingStatus:
    """Tests for RoutingStatus enum."""

    def test_all_statuses_defined(self):
        """All routing statuses are defined."""
        assert RoutingStatus.ROUTED.value == "routed"
        assert RoutingStatus.PENDING_REWRITE.value == "pending_rewrite"
        assert RoutingStatus.BLOCKED.value == "blocked"
        assert RoutingStatus.PENDING_FILTER.value == "pending_filter"


class TestTaskActivationRequest:
    """Tests for TaskActivationRequest domain model."""

    def test_create_valid_request(self):
        """Valid request should create successfully."""
        request_id = uuid4()
        task_id = uuid4()
        request = TaskActivationRequest(
            request_id=request_id,
            task_id=task_id,
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            description="Complete the quarterly report",
            requirements=["Access to data", "Formatting guidelines"],
            expected_outcomes=["Completed report PDF"],
        )
        assert request.request_id == request_id
        assert request.task_id == task_id
        assert request.earl_id == "earl-agares"
        assert request.cluster_id == "cluster-alpha"
        assert request.description == "Complete the quarterly report"
        assert len(request.requirements) == 2
        assert len(request.expected_outcomes) == 1

    def test_default_ttl_is_72_hours(self):
        """Default TTL should be 72 hours per NFR-CONSENT-01."""
        request = TaskActivationRequest(
            request_id=uuid4(),
            task_id=uuid4(),
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            description="Test task",
        )
        assert request.ttl == timedelta(hours=72)

    def test_custom_ttl_allowed(self):
        """Custom TTL should be accepted."""
        custom_ttl = timedelta(hours=48)
        request = TaskActivationRequest(
            request_id=uuid4(),
            task_id=uuid4(),
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            description="Test task",
            ttl=custom_ttl,
        )
        assert request.ttl == custom_ttl

    def test_request_is_frozen(self):
        """Request should be immutable."""
        request = TaskActivationRequest(
            request_id=uuid4(),
            task_id=uuid4(),
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            description="Test task",
        )
        with pytest.raises(AttributeError):
            request.description = "Modified"  # type: ignore

    def test_empty_description_raises_error(self):
        """Empty description should raise ValueError."""
        with pytest.raises(ValueError, match="description must be non-empty"):
            TaskActivationRequest(
                request_id=uuid4(),
                task_id=uuid4(),
                earl_id="earl-agares",
                cluster_id="cluster-alpha",
                description="",
            )

    def test_whitespace_description_raises_error(self):
        """Whitespace-only description should raise ValueError."""
        with pytest.raises(ValueError, match="description must be non-empty"):
            TaskActivationRequest(
                request_id=uuid4(),
                task_id=uuid4(),
                earl_id="earl-agares",
                cluster_id="cluster-alpha",
                description="   ",
            )

    def test_empty_earl_id_raises_error(self):
        """Empty earl_id should raise ValueError."""
        with pytest.raises(ValueError, match="earl_id must be non-empty"):
            TaskActivationRequest(
                request_id=uuid4(),
                task_id=uuid4(),
                earl_id="",
                cluster_id="cluster-alpha",
                description="Test task",
            )

    def test_empty_cluster_id_raises_error(self):
        """Empty cluster_id should raise ValueError."""
        with pytest.raises(ValueError, match="cluster_id must be non-empty"):
            TaskActivationRequest(
                request_id=uuid4(),
                task_id=uuid4(),
                earl_id="earl-agares",
                cluster_id="",
                description="Test task",
            )

    def test_negative_ttl_raises_error(self):
        """Negative TTL should raise ValueError."""
        with pytest.raises(ValueError, match="ttl must be positive"):
            TaskActivationRequest(
                request_id=uuid4(),
                task_id=uuid4(),
                earl_id="earl-agares",
                cluster_id="cluster-alpha",
                description="Test task",
                ttl=timedelta(hours=-1),
            )

    def test_zero_ttl_raises_error(self):
        """Zero TTL should raise ValueError."""
        with pytest.raises(ValueError, match="ttl must be positive"):
            TaskActivationRequest(
                request_id=uuid4(),
                task_id=uuid4(),
                earl_id="earl-agares",
                cluster_id="cluster-alpha",
                description="Test task",
                ttl=timedelta(seconds=0),
            )

    def test_is_filtered_false_initially(self):
        """New request should not be filtered."""
        request = TaskActivationRequest(
            request_id=uuid4(),
            task_id=uuid4(),
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            description="Test task",
        )
        assert request.is_filtered is False
        assert request.filter_outcome is None

    def test_is_routable_when_accepted(self):
        """Request should be routable when filter accepted."""
        # Note: Since frozen, we can't modify - but we test the logic
        # by understanding the is_routable property
        request = TaskActivationRequest(
            request_id=uuid4(),
            task_id=uuid4(),
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            description="Test task",
            filter_outcome=FilterOutcome.ACCEPTED,
        )
        assert request.is_routable is True

    def test_is_routable_when_transformed(self):
        """Request should be routable when filter transformed."""
        request = TaskActivationRequest(
            request_id=uuid4(),
            task_id=uuid4(),
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            description="Test task",
            filter_outcome=FilterOutcome.TRANSFORMED,
        )
        assert request.is_routable is True

    def test_not_routable_when_rejected(self):
        """Request should not be routable when filter rejected."""
        request = TaskActivationRequest(
            request_id=uuid4(),
            task_id=uuid4(),
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            description="Test task",
            filter_outcome=FilterOutcome.REJECTED,
        )
        assert request.is_routable is False

    def test_not_routable_when_blocked(self):
        """Request should not be routable when filter blocked."""
        request = TaskActivationRequest(
            request_id=uuid4(),
            task_id=uuid4(),
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            description="Test task",
            filter_outcome=FilterOutcome.BLOCKED,
        )
        assert request.is_routable is False


class TestTaskActivationResult:
    """Tests for TaskActivationResult domain model."""

    def test_successful_result(self):
        """Successful result should have correct attributes."""
        from src.domain.governance.task.task_state import TaskState

        task_state = TaskState.create(
            task_id=uuid4(),
            earl_id="earl-agares",
            created_at=datetime.utcnow(),
        )
        result = TaskActivationResult(
            success=True,
            task_state=task_state,
            filter_outcome=FilterOutcome.ACCEPTED,
            filter_decision_id=uuid4(),
            routing_status=RoutingStatus.ROUTED,
            message="Task activation routed to Cluster",
        )
        assert result.success is True
        assert result.routing_status == RoutingStatus.ROUTED

    def test_rejected_result(self):
        """Rejected result should include rejection reason."""
        from src.domain.governance.task.task_state import TaskState

        task_state = TaskState.create(
            task_id=uuid4(),
            earl_id="earl-agares",
            created_at=datetime.utcnow(),
        )
        result = TaskActivationResult(
            success=False,
            task_state=task_state,
            filter_outcome=FilterOutcome.REJECTED,
            filter_decision_id=uuid4(),
            routing_status=RoutingStatus.PENDING_REWRITE,
            message="Content rejected by filter. Please revise.",
            rejection_reason="Contains urgency language",
        )
        assert result.success is False
        assert result.routing_status == RoutingStatus.PENDING_REWRITE
        assert result.rejection_reason == "Contains urgency language"

    def test_result_is_frozen(self):
        """Result should be immutable."""
        from src.domain.governance.task.task_state import TaskState

        task_state = TaskState.create(
            task_id=uuid4(),
            earl_id="earl-agares",
            created_at=datetime.utcnow(),
        )
        result = TaskActivationResult(
            success=True,
            task_state=task_state,
            filter_outcome=FilterOutcome.ACCEPTED,
            filter_decision_id=uuid4(),
            routing_status=RoutingStatus.ROUTED,
            message="Test",
        )
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore


class TestTaskStateView:
    """Tests for TaskStateView domain model."""

    def test_create_task_state_view(self):
        """TaskStateView should contain expected fields."""
        now = datetime.utcnow()
        view = TaskStateView(
            task_id=uuid4(),
            current_status="activated",
            cluster_id="cluster-alpha",
            created_at=now,
            state_entered_at=now,
            ttl=timedelta(hours=72),
            ttl_remaining=timedelta(hours=48),
            is_pre_consent=True,
            is_post_consent=False,
            is_terminal=False,
        )
        assert view.current_status == "activated"
        assert view.is_pre_consent is True
        assert view.ttl_remaining == timedelta(hours=48)

    def test_view_is_frozen(self):
        """View should be immutable."""
        now = datetime.utcnow()
        view = TaskStateView(
            task_id=uuid4(),
            current_status="activated",
            cluster_id=None,
            created_at=now,
            state_entered_at=now,
            ttl=timedelta(hours=72),
            ttl_remaining=timedelta(hours=48),
            is_pre_consent=True,
            is_post_consent=False,
            is_terminal=False,
        )
        with pytest.raises(AttributeError):
            view.current_status = "routed"  # type: ignore
