"""Tests for TaskActivationService.

Story: consent-gov-2.2: Task Activation Request

Tests the task activation service:
- Successful activation with routing
- Filter rejection handling
- Filter blocking handling
- Earl task visibility
- Two-phase event emission
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.ports.governance.task_activation_port import (
    UnauthorizedAccessError,
)
from src.application.services.governance.task_activation_service import (
    TaskActivationService,
)
from src.domain.governance.filter import (
    FilteredContent,
    FilterResult,
    FilterVersion,
    RejectionReason,
    Transformation,
    ViolationType,
)
from src.domain.governance.task.task_activation_request import (
    FilterOutcome,
    RoutingStatus,
)
from src.domain.governance.task.task_state import TaskState, TaskStatus


def _make_filter_version() -> FilterVersion:
    """Create a test filter version."""
    return FilterVersion(major=1, minor=0, patch=0, rules_hash="test_hash_123")


def _make_filtered_content(content: str) -> FilteredContent:
    """Create a test filtered content."""
    return FilteredContent._create(
        content=content,
        original_content=content,
        filter_version=_make_filter_version(),
        filtered_at=datetime.now(timezone.utc),
    )


def _make_accepted_result(content: str, transformations: tuple[Transformation, ...] = ()) -> FilterResult:
    """Create an ACCEPTED filter result."""
    return FilterResult.accepted(
        content=_make_filtered_content(content),
        version=_make_filter_version(),
        timestamp=datetime.now(timezone.utc),
        transformations=transformations,
    )


def _make_rejected_result(reason: RejectionReason, guidance: str | None = None) -> FilterResult:
    """Create a REJECTED filter result."""
    return FilterResult.rejected(
        reason=reason,
        version=_make_filter_version(),
        timestamp=datetime.now(timezone.utc),
        guidance=guidance,
    )


def _make_blocked_result(violation: ViolationType, details: str | None = None) -> FilterResult:
    """Create a BLOCKED filter result."""
    return FilterResult.blocked(
        violation=violation,
        version=_make_filter_version(),
        timestamp=datetime.now(timezone.utc),
        details=details,
    )


@pytest.fixture
def mock_task_state_port():
    """Create mock task state port."""
    port = AsyncMock()
    return port


@pytest.fixture
def mock_coercion_filter():
    """Create mock coercion filter port."""
    return AsyncMock()


@pytest.fixture
def mock_participant_message_port():
    """Create mock participant message port."""
    return AsyncMock()


@pytest.fixture
def mock_ledger_port():
    """Create mock ledger port."""
    return AsyncMock()


@pytest.fixture
def mock_two_phase_emitter():
    """Create mock two-phase emitter."""
    emitter = AsyncMock()
    emitter.emit_intent.return_value = uuid4()
    return emitter


@pytest.fixture
def task_activation_service(
    mock_task_state_port,
    mock_coercion_filter,
    mock_participant_message_port,
    mock_ledger_port,
    mock_two_phase_emitter,
):
    """Create TaskActivationService with mocked dependencies."""
    return TaskActivationService(
        task_state_port=mock_task_state_port,
        coercion_filter=mock_coercion_filter,
        participant_message_port=mock_participant_message_port,
        ledger_port=mock_ledger_port,
        two_phase_emitter=mock_two_phase_emitter,
    )


class TestCreateActivation:
    """Tests for create_activation method."""

    @pytest.mark.asyncio
    async def test_successful_activation_routes_to_cluster(
        self,
        task_activation_service,
        mock_task_state_port,
        mock_coercion_filter,
        mock_participant_message_port,
    ):
        """Accepted content is routed to Cluster."""
        # Setup task state
        task_id = uuid4()
        task = TaskState.create(task_id=task_id, earl_id="earl-agares", created_at=datetime.utcnow())
        mock_task_state_port.create_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        # Setup filter to accept
        mock_coercion_filter.filter_content.return_value = _make_accepted_result(
            "Test task description"
        )

        # Execute
        result = await task_activation_service.create_activation(
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            description="Test task description",
            requirements=["Req 1"],
            expected_outcomes=["Outcome 1"],
        )

        # Assert
        assert result.success is True
        assert result.routing_status == RoutingStatus.ROUTED
        assert result.filter_outcome == FilterOutcome.ACCEPTED
        mock_participant_message_port.send_to_participant.assert_called_once()

    @pytest.mark.asyncio
    async def test_transformed_content_is_routed(
        self,
        task_activation_service,
        mock_task_state_port,
        mock_coercion_filter,
        mock_participant_message_port,
    ):
        """Transformed content is also routed to Cluster."""
        # Setup
        task_id = uuid4()
        task = TaskState.create(task_id=task_id, earl_id="earl-agares", created_at=datetime.utcnow())
        mock_task_state_port.create_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        # Create a transformation record to indicate content was modified
        transformation = Transformation(
            pattern_matched=r"(?i)URGENT!?",
            original_text="URGENT:",
            replacement_text="",
            rule_id="urgency-1",
            position=0,
        )
        mock_coercion_filter.filter_content.return_value = _make_accepted_result(
            "Modified task description",
            transformations=(transformation,),
        )

        # Execute
        result = await task_activation_service.create_activation(
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            description="URGENT: Test task",
            requirements=[],
            expected_outcomes=[],
        )

        # Assert
        assert result.success is True
        assert result.routing_status == RoutingStatus.ROUTED
        # Note: With new API, ACCEPTED with transformations still returns ACCEPTED
        assert result.filter_outcome == FilterOutcome.ACCEPTED
        mock_participant_message_port.send_to_participant.assert_called_once()

    @pytest.mark.asyncio
    async def test_rejected_content_not_routed(
        self,
        task_activation_service,
        mock_task_state_port,
        mock_coercion_filter,
        mock_participant_message_port,
    ):
        """Rejected content returns to Earl for rewrite."""
        # Setup
        task_id = uuid4()
        task = TaskState.create(task_id=task_id, earl_id="earl-agares", created_at=datetime.utcnow())
        mock_task_state_port.create_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        mock_coercion_filter.filter_content.return_value = _make_rejected_result(
            reason=RejectionReason.URGENCY_PRESSURE,
            guidance="Contains urgency language",
        )

        # Execute
        result = await task_activation_service.create_activation(
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            description="URGENT: Do this NOW!",
            requirements=[],
            expected_outcomes=[],
        )

        # Assert
        assert result.success is False
        assert result.routing_status == RoutingStatus.PENDING_REWRITE
        assert result.filter_outcome == FilterOutcome.REJECTED
        assert result.rejection_reason == "Contains urgency language"
        mock_participant_message_port.send_to_participant.assert_not_called()

    @pytest.mark.asyncio
    async def test_blocked_content_not_routed(
        self,
        task_activation_service,
        mock_task_state_port,
        mock_coercion_filter,
        mock_participant_message_port,
    ):
        """Blocked content logs violation, does not route."""
        # Setup
        task_id = uuid4()
        task = TaskState.create(task_id=task_id, earl_id="earl-agares", created_at=datetime.utcnow())
        mock_task_state_port.create_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        mock_coercion_filter.filter_content.return_value = _make_blocked_result(
            violation=ViolationType.EXPLICIT_THREAT,
            details="coercion.threat, coercion.intimidation",
        )

        # Execute
        result = await task_activation_service.create_activation(
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            description="Do this or else!",
            requirements=[],
            expected_outcomes=[],
        )

        # Assert
        assert result.success is False
        assert result.routing_status == RoutingStatus.BLOCKED
        assert result.filter_outcome == FilterOutcome.BLOCKED
        mock_participant_message_port.send_to_participant.assert_not_called()

    @pytest.mark.asyncio
    async def test_custom_ttl_used(
        self,
        task_activation_service,
        mock_task_state_port,
        mock_coercion_filter,
    ):
        """Custom TTL should be passed to task creation."""
        # Setup
        task = TaskState.create(task_id=uuid4(), earl_id="earl-agares", created_at=datetime.utcnow())
        mock_task_state_port.create_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        mock_coercion_filter.filter_content.return_value = _make_accepted_result("Test")

        custom_ttl = timedelta(hours=48)

        # Execute
        await task_activation_service.create_activation(
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            description="Test task",
            requirements=[],
            expected_outcomes=[],
            ttl=custom_ttl,
        )

        # Assert
        mock_task_state_port.create_task.assert_called_once_with(
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            ttl=custom_ttl,
        )

    @pytest.mark.asyncio
    async def test_default_ttl_is_72_hours(
        self,
        task_activation_service,
        mock_task_state_port,
        mock_coercion_filter,
    ):
        """Default TTL should be 72 hours per NFR-CONSENT-01."""
        # Setup
        task = TaskState.create(task_id=uuid4(), earl_id="earl-agares", created_at=datetime.utcnow())
        mock_task_state_port.create_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        mock_coercion_filter.filter_content.return_value = _make_accepted_result("Test")

        # Execute
        await task_activation_service.create_activation(
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            description="Test task",
            requirements=[],
            expected_outcomes=[],
        )

        # Assert
        mock_task_state_port.create_task.assert_called_once_with(
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            ttl=timedelta(hours=72),
        )

    @pytest.mark.asyncio
    async def test_two_phase_emission_on_success(
        self,
        task_activation_service,
        mock_task_state_port,
        mock_coercion_filter,
        mock_two_phase_emitter,
    ):
        """Two-phase emission should emit intent and commit."""
        # Setup
        task = TaskState.create(task_id=uuid4(), earl_id="earl-agares", created_at=datetime.utcnow())
        mock_task_state_port.create_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        mock_coercion_filter.filter_content.return_value = _make_accepted_result("Test")

        # Execute
        await task_activation_service.create_activation(
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            description="Test task",
            requirements=[],
            expected_outcomes=[],
        )

        # Assert - intent should be emitted
        mock_two_phase_emitter.emit_intent.assert_called_once()
        call_kwargs = mock_two_phase_emitter.emit_intent.call_args.kwargs
        assert call_kwargs["operation_type"] == "task.activate"
        assert call_kwargs["actor_id"] == "earl-agares"

        # Assert - commit should be emitted
        mock_two_phase_emitter.emit_commit.assert_called_once()


class TestGetTaskState:
    """Tests for get_task_state method."""

    @pytest.mark.asyncio
    async def test_get_task_state_for_owner(
        self,
        task_activation_service,
        mock_task_state_port,
    ):
        """Earl can get state of their own task."""
        task_id = uuid4()
        task = TaskState.create(task_id=task_id, earl_id="earl-agares", created_at=datetime.utcnow())
        mock_task_state_port.get_task.return_value = task

        view = await task_activation_service.get_task_state(
            task_id=task_id,
            earl_id="earl-agares",
        )

        assert view.task_id == task_id
        assert view.current_status == "authorized"
        assert view.is_pre_consent is True

    @pytest.mark.asyncio
    async def test_get_task_state_unauthorized(
        self,
        task_activation_service,
        mock_task_state_port,
    ):
        """Non-owner Earl cannot get task state."""
        task_id = uuid4()
        task = TaskState.create(task_id=task_id, earl_id="earl-agares", created_at=datetime.utcnow())
        mock_task_state_port.get_task.return_value = task

        with pytest.raises(UnauthorizedAccessError) as exc_info:
            await task_activation_service.get_task_state(
                task_id=task_id,
                earl_id="earl-other",  # Different Earl
            )

        assert "earl-other" in str(exc_info.value)
        assert "does not own" in str(exc_info.value)


class TestGetTaskHistory:
    """Tests for get_task_history method."""

    @pytest.mark.asyncio
    async def test_get_task_history_for_owner(
        self,
        task_activation_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Earl can get history of their own task."""
        task_id = uuid4()
        task = TaskState.create(task_id=task_id, earl_id="earl-agares", created_at=datetime.utcnow())
        mock_task_state_port.get_task.return_value = task

        # Mock ledger events
        mock_event = MagicMock()
        mock_event.event_id = uuid4()
        mock_event.event_type = "executive.task.activated"
        mock_event.timestamp = datetime.utcnow()
        mock_event.actor_id = "earl-agares"
        mock_event.payload = {"task_id": str(task_id)}
        mock_ledger_port.read_events.return_value = [mock_event]

        history = await task_activation_service.get_task_history(
            task_id=task_id,
            earl_id="earl-agares",
        )

        assert len(history) == 1
        assert history[0]["event_type"] == "executive.task.activated"

    @pytest.mark.asyncio
    async def test_get_task_history_unauthorized(
        self,
        task_activation_service,
        mock_task_state_port,
    ):
        """Non-owner Earl cannot get task history."""
        task_id = uuid4()
        task = TaskState.create(task_id=task_id, earl_id="earl-agares", created_at=datetime.utcnow())
        mock_task_state_port.get_task.return_value = task

        with pytest.raises(UnauthorizedAccessError):
            await task_activation_service.get_task_history(
                task_id=task_id,
                earl_id="earl-other",
            )


class TestRouteToCluster:
    """Tests for route_to_cluster method."""

    @pytest.mark.asyncio
    async def test_route_activated_task(
        self,
        task_activation_service,
        mock_task_state_port,
    ):
        """Can route a task in ACTIVATED state."""
        task_id = uuid4()
        task = TaskState.create(task_id=task_id, earl_id="earl-agares", created_at=datetime.utcnow())
        # Transition to ACTIVATED
        activated_task = task.transition(
            new_status=TaskStatus.ACTIVATED,
            transition_time=datetime.utcnow(),
            actor_id="earl-agares",
        )
        mock_task_state_port.get_task.return_value = activated_task
        mock_task_state_port.save_task.return_value = None

        result = await task_activation_service.route_to_cluster(
            task_id=task_id,
            cluster_id="cluster-alpha",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_route_non_activated_task_raises_error(
        self,
        task_activation_service,
        mock_task_state_port,
    ):
        """Cannot route a task not in ACTIVATED state."""
        task_id = uuid4()
        task = TaskState.create(task_id=task_id, earl_id="earl-agares", created_at=datetime.utcnow())
        # Task is in AUTHORIZED state (not ACTIVATED)
        mock_task_state_port.get_task.return_value = task

        with pytest.raises(ValueError, match="not in ACTIVATED state"):
            await task_activation_service.route_to_cluster(
                task_id=task_id,
                cluster_id="cluster-alpha",
            )


class TestFilterIntegration:
    """Tests for Coercion Filter integration."""

    @pytest.mark.asyncio
    async def test_filter_receives_correct_content(
        self,
        task_activation_service,
        mock_task_state_port,
        mock_coercion_filter,
    ):
        """Filter receives combined description, requirements, and expected_outcomes."""
        # Setup
        task = TaskState.create(task_id=uuid4(), earl_id="earl-agares", created_at=datetime.utcnow())
        mock_task_state_port.create_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        mock_coercion_filter.filter_content.return_value = _make_accepted_result("Test")

        # Execute
        await task_activation_service.create_activation(
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            description="Complete the report",
            requirements=["Access to data", "Deadline: Friday"],
            expected_outcomes=["PDF report", "Summary email"],
        )

        # Assert filter received correct content using new API
        mock_coercion_filter.filter_content.assert_called_once()
        call_kwargs = mock_coercion_filter.filter_content.call_args.kwargs
        # New API passes content as combined string with message_type
        assert "Complete the report" in call_kwargs["content"]
        assert "Access to data" in call_kwargs["content"]
        assert "PDF report" in call_kwargs["content"]

    @pytest.mark.asyncio
    async def test_filtered_content_sent_to_participant(
        self,
        task_activation_service,
        mock_task_state_port,
        mock_coercion_filter,
        mock_participant_message_port,
    ):
        """FilteredContent (not raw) is sent to participant."""
        # Setup
        task = TaskState.create(task_id=uuid4(), earl_id="earl-agares", created_at=datetime.utcnow())
        mock_task_state_port.create_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        mock_coercion_filter.filter_content.return_value = _make_accepted_result(
            "Filtered task description"
        )

        # Execute
        await task_activation_service.create_activation(
            earl_id="earl-agares",
            cluster_id="cluster-alpha",
            description="Original description",
            requirements=[],
            expected_outcomes=[],
        )

        # Assert content was sent (now uses TaskFilteredContent adapter)
        mock_participant_message_port.send_to_participant.assert_called_once()
        call_kwargs = mock_participant_message_port.send_to_participant.call_args.kwargs
        assert call_kwargs["content"].content == "Filtered task description"
        assert call_kwargs["participant_id"] == "cluster-alpha"
        assert call_kwargs["message_type"] == "task_activation"
