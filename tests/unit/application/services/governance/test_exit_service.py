"""Unit tests for exit service.

Story: consent-gov-7.1: Exit Request Processing

Tests for:
- Exit initiation and completion (AC1, AC2)
- ≤2 round-trips (AC3)
- Exit from any state (AC4)
- Event emission (AC5, AC6)
- No barriers (AC7, AC8)
- Exit from each task state (AC9)
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from src.application.services.governance.exit_service import (
    ExitService,
    EXIT_INITIATED_EVENT,
    EXIT_COMPLETED_EVENT,
)
from src.domain.governance.exit.exit_request import ExitRequest
from src.domain.governance.exit.exit_result import ExitResult
from src.domain.governance.exit.exit_status import ExitStatus
from src.domain.governance.exit.errors import AlreadyExitedError
from src.domain.governance.task.task_state import TaskStatus


# =============================================================================
# Test Fixtures
# =============================================================================


class FakeTimeAuthority:
    """Fake time authority for testing."""

    def __init__(self, start_time: datetime | None = None):
        self._current_time = start_time or datetime.now(timezone.utc)
        self._call_count = 0

    def now(self) -> datetime:
        """Get current time, advancing slightly each call."""
        self._call_count += 1
        # Advance 50ms each call to simulate real time passing
        result = self._current_time + timedelta(milliseconds=50 * (self._call_count - 1))
        return result

    def set_time(self, time: datetime) -> None:
        """Set the current time."""
        self._current_time = time
        self._call_count = 0


class FakeEventEmitter:
    """Fake event emitter for testing."""

    def __init__(self):
        self.events: list[dict] = []

    async def emit(self, event_type: str, actor: str, payload: dict) -> None:
        """Record emitted event."""
        self.events.append({
            "event_type": event_type,
            "actor": actor,
            "payload": payload,
        })

    def get_events(self, event_type: str) -> list[dict]:
        """Get events of specific type."""
        return [e for e in self.events if e["event_type"] == event_type]

    def get_last_event(self, event_type: str) -> dict | None:
        """Get most recent event of specific type."""
        events = self.get_events(event_type)
        return events[-1] if events else None

    def clear(self) -> None:
        """Clear all events."""
        self.events = []


class FakeExitPort:
    """Fake exit port for testing."""

    def __init__(self):
        self._requests: dict[UUID, ExitRequest] = {}
        self._results: dict[UUID, ExitResult] = {}
        self._exited_clusters: set[UUID] = set()
        self._active_tasks: dict[UUID, list[UUID]] = {}
        self._task_states: dict[UUID, TaskStatus] = {}

    async def record_exit_request(self, request: ExitRequest) -> None:
        """Record exit request."""
        self._requests[request.request_id] = request

    async def record_exit_result(self, result: ExitResult) -> None:
        """Record exit result."""
        self._results[result.request_id] = result
        if result.status == ExitStatus.COMPLETED:
            self._exited_clusters.add(result.cluster_id)

    async def get_exit_request(self, request_id: UUID) -> ExitRequest | None:
        """Get exit request."""
        return self._requests.get(request_id)

    async def get_exit_result(self, request_id: UUID) -> ExitResult | None:
        """Get exit result."""
        return self._results.get(request_id)

    async def has_cluster_exited(self, cluster_id: UUID) -> bool:
        """Check if cluster exited."""
        return cluster_id in self._exited_clusters

    async def get_cluster_active_tasks(self, cluster_id: UUID) -> list[UUID]:
        """Get active tasks."""
        return self._active_tasks.get(cluster_id, [])

    # Test helpers
    def set_active_tasks(self, cluster_id: UUID, task_ids: list[UUID]) -> None:
        """Set active tasks for cluster."""
        self._active_tasks[cluster_id] = task_ids

    def mark_as_exited(self, cluster_id: UUID) -> None:
        """Mark cluster as already exited."""
        self._exited_clusters.add(cluster_id)

    def add_task_in_state(self, cluster_id: UUID, task_id: UUID, state: TaskStatus) -> None:
        """Add a task in specific state."""
        if cluster_id not in self._active_tasks:
            self._active_tasks[cluster_id] = []
        self._active_tasks[cluster_id].append(task_id)
        self._task_states[task_id] = state


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    """Create fake time authority."""
    return FakeTimeAuthority()


@pytest.fixture
def event_emitter() -> FakeEventEmitter:
    """Create fake event emitter."""
    return FakeEventEmitter()


@pytest.fixture
def exit_port() -> FakeExitPort:
    """Create fake exit port."""
    return FakeExitPort()


@pytest.fixture
def exit_service(exit_port, event_emitter, time_authority) -> ExitService:
    """Create exit service with fakes."""
    return ExitService(
        exit_port=exit_port,
        event_emitter=event_emitter,
        time_authority=time_authority,
    )


@pytest.fixture
def cluster_id() -> UUID:
    """Generate cluster ID."""
    return uuid4()


# =============================================================================
# Basic Exit Tests (AC1, AC2)
# =============================================================================


class TestExitInitiation:
    """Tests for exit initiation (AC1, AC2)."""

    @pytest.mark.asyncio
    async def test_can_initiate_exit(self, exit_service, cluster_id):
        """Cluster can initiate exit request (AC1)."""
        result = await exit_service.initiate_exit(cluster_id)

        assert result is not None
        assert result.cluster_id == cluster_id

    @pytest.mark.asyncio
    async def test_system_processes_exit(self, exit_service, cluster_id):
        """System processes exit request (AC2)."""
        result = await exit_service.initiate_exit(cluster_id)

        assert result.status == ExitStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_exit_returns_result(self, exit_service, cluster_id):
        """Exit returns ExitResult."""
        result = await exit_service.initiate_exit(cluster_id)

        assert isinstance(result, ExitResult)
        assert result.request_id is not None
        assert result.initiated_at is not None
        assert result.completed_at is not None


# =============================================================================
# Round-Trip Tests (AC3)
# =============================================================================


class TestRoundTrips:
    """Tests for ≤2 round-trips (AC3, NFR-EXIT-01)."""

    @pytest.mark.asyncio
    async def test_exit_completes_in_two_round_trips(self, exit_service, cluster_id):
        """Exit completes in ≤2 message round-trips (AC3)."""
        result = await exit_service.initiate_exit(cluster_id)

        assert result.round_trips <= 2

    @pytest.mark.asyncio
    async def test_exit_uses_exactly_two_round_trips(self, exit_service, cluster_id):
        """Exit uses exactly 2 round-trips (request + confirmation)."""
        result = await exit_service.initiate_exit(cluster_id)

        assert result.round_trips == 2

    @pytest.mark.asyncio
    async def test_single_method_call_for_exit(self, exit_service, cluster_id):
        """Exit requires only single method call (no multi-step)."""
        # If exit worked, it was a single call
        result = await exit_service.initiate_exit(cluster_id)

        assert result.is_complete


# =============================================================================
# Exit From Any State Tests (AC4, AC8, AC9)
# =============================================================================


class TestExitFromAnyState:
    """Tests for exit from any task state (AC4, AC8, AC9)."""

    @pytest.mark.asyncio
    async def test_exit_from_authorized_state(self, exit_service, exit_port, cluster_id):
        """Can exit while having AUTHORIZED tasks (AC9)."""
        task_id = uuid4()
        exit_port.add_task_in_state(cluster_id, task_id, TaskStatus.AUTHORIZED)

        result = await exit_service.initiate_exit(cluster_id)

        assert result.status == ExitStatus.COMPLETED
        assert result.tasks_affected >= 1

    @pytest.mark.asyncio
    async def test_exit_from_activated_state(self, exit_service, exit_port, cluster_id):
        """Can exit while having ACTIVATED tasks (AC9)."""
        task_id = uuid4()
        exit_port.add_task_in_state(cluster_id, task_id, TaskStatus.ACTIVATED)

        result = await exit_service.initiate_exit(cluster_id)

        assert result.status == ExitStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_exit_from_routed_state(self, exit_service, exit_port, cluster_id):
        """Can exit while having ROUTED tasks (AC9)."""
        task_id = uuid4()
        exit_port.add_task_in_state(cluster_id, task_id, TaskStatus.ROUTED)

        result = await exit_service.initiate_exit(cluster_id)

        assert result.status == ExitStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_exit_from_accepted_state(self, exit_service, exit_port, cluster_id):
        """Can exit while having ACCEPTED tasks (AC9)."""
        task_id = uuid4()
        exit_port.add_task_in_state(cluster_id, task_id, TaskStatus.ACCEPTED)

        result = await exit_service.initiate_exit(cluster_id)

        assert result.status == ExitStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_exit_from_in_progress_state(self, exit_service, exit_port, cluster_id):
        """Can exit while having IN_PROGRESS tasks (AC9)."""
        task_id = uuid4()
        exit_port.add_task_in_state(cluster_id, task_id, TaskStatus.IN_PROGRESS)

        result = await exit_service.initiate_exit(cluster_id)

        assert result.status == ExitStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_exit_from_reported_state(self, exit_service, exit_port, cluster_id):
        """Can exit while having REPORTED tasks (AC9)."""
        task_id = uuid4()
        exit_port.add_task_in_state(cluster_id, task_id, TaskStatus.REPORTED)

        result = await exit_service.initiate_exit(cluster_id)

        assert result.status == ExitStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_exit_from_aggregated_state(self, exit_service, exit_port, cluster_id):
        """Can exit while having AGGREGATED tasks (AC9)."""
        task_id = uuid4()
        exit_port.add_task_in_state(cluster_id, task_id, TaskStatus.AGGREGATED)

        result = await exit_service.initiate_exit(cluster_id)

        assert result.status == ExitStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_exit_with_no_active_tasks(self, exit_service, cluster_id):
        """Can exit with no active tasks (AC4)."""
        # No tasks set up
        result = await exit_service.initiate_exit(cluster_id)

        assert result.status == ExitStatus.COMPLETED
        assert result.tasks_affected == 0

    @pytest.mark.asyncio
    async def test_exit_regardless_of_task_status(self, exit_service, exit_port, cluster_id):
        """Exit works regardless of current task status (AC8)."""
        # Add tasks in multiple states
        exit_port.add_task_in_state(cluster_id, uuid4(), TaskStatus.AUTHORIZED)
        exit_port.add_task_in_state(cluster_id, uuid4(), TaskStatus.IN_PROGRESS)
        exit_port.add_task_in_state(cluster_id, uuid4(), TaskStatus.REPORTED)

        result = await exit_service.initiate_exit(cluster_id)

        assert result.status == ExitStatus.COMPLETED
        assert result.tasks_affected == 3

    @pytest.mark.asyncio
    @pytest.mark.parametrize("task_state", [
        TaskStatus.AUTHORIZED,
        TaskStatus.ACTIVATED,
        TaskStatus.ROUTED,
        TaskStatus.ACCEPTED,
        TaskStatus.IN_PROGRESS,
        TaskStatus.REPORTED,
        TaskStatus.AGGREGATED,
    ])
    async def test_exit_available_from_state_parametrized(
        self,
        exit_port,
        event_emitter,
        time_authority,
        task_state,
    ):
        """Exit is available from any non-terminal task state (AC9 parametrized)."""
        cluster_id = uuid4()
        service = ExitService(exit_port, event_emitter, time_authority)
        exit_port.add_task_in_state(cluster_id, uuid4(), task_state)

        result = await service.initiate_exit(cluster_id)

        assert result.status == ExitStatus.COMPLETED


# =============================================================================
# Event Emission Tests (AC5, AC6)
# =============================================================================


class TestEventEmission:
    """Tests for event emission (AC5, AC6)."""

    @pytest.mark.asyncio
    async def test_initiated_event_emitted(self, exit_service, event_emitter, cluster_id):
        """Event custodial.exit.initiated emitted at start (AC5)."""
        await exit_service.initiate_exit(cluster_id)

        event = event_emitter.get_last_event(EXIT_INITIATED_EVENT)

        assert event is not None
        assert event["event_type"] == EXIT_INITIATED_EVENT
        assert event["actor"] == str(cluster_id)

    @pytest.mark.asyncio
    async def test_initiated_event_payload(self, exit_service, event_emitter, cluster_id):
        """Initiated event has correct payload (AC5)."""
        await exit_service.initiate_exit(cluster_id)

        event = event_emitter.get_last_event(EXIT_INITIATED_EVENT)
        payload = event["payload"]

        assert "request_id" in payload
        assert "cluster_id" in payload
        assert "initiated_at" in payload
        assert "active_tasks" in payload
        assert payload["cluster_id"] == str(cluster_id)

    @pytest.mark.asyncio
    async def test_completed_event_emitted(self, exit_service, event_emitter, cluster_id):
        """Event custodial.exit.completed emitted on completion (AC6)."""
        await exit_service.initiate_exit(cluster_id)

        event = event_emitter.get_last_event(EXIT_COMPLETED_EVENT)

        assert event is not None
        assert event["event_type"] == EXIT_COMPLETED_EVENT
        assert event["actor"] == "system"

    @pytest.mark.asyncio
    async def test_completed_event_payload(self, exit_service, event_emitter, cluster_id):
        """Completed event has correct payload (AC6)."""
        await exit_service.initiate_exit(cluster_id)

        event = event_emitter.get_last_event(EXIT_COMPLETED_EVENT)
        payload = event["payload"]

        assert "request_id" in payload
        assert "cluster_id" in payload
        assert "initiated_at" in payload
        assert "completed_at" in payload
        assert "tasks_affected" in payload
        assert "duration_ms" in payload

    @pytest.mark.asyncio
    async def test_both_events_emitted_in_order(self, exit_service, event_emitter, cluster_id):
        """Both initiated and completed events emitted in order."""
        await exit_service.initiate_exit(cluster_id)

        initiated_events = event_emitter.get_events(EXIT_INITIATED_EVENT)
        completed_events = event_emitter.get_events(EXIT_COMPLETED_EVENT)

        assert len(initiated_events) == 1
        assert len(completed_events) == 1

        # Verify order in overall event list
        event_types = [e["event_type"] for e in event_emitter.events]
        assert event_types.index(EXIT_INITIATED_EVENT) < event_types.index(EXIT_COMPLETED_EVENT)


# =============================================================================
# No Barriers Tests (AC7)
# =============================================================================


class TestNoBarriers:
    """Tests ensuring no exit barriers exist (AC7)."""

    def test_no_confirmation_method(self, exit_service):
        """Exit service has no confirmation method (AC7)."""
        assert not hasattr(exit_service, "confirm_exit")
        assert not hasattr(exit_service, "verify_exit")
        assert not hasattr(exit_service, "approve_exit")

    def test_no_waiting_period_method(self, exit_service):
        """Exit service has no waiting period method (AC7)."""
        assert not hasattr(exit_service, "waiting_period")
        assert not hasattr(exit_service, "wait_for_exit")
        assert not hasattr(exit_service, "delay_exit")

    def test_no_penalty_warning_method(self, exit_service):
        """Exit service has no penalty warning method (AC7)."""
        assert not hasattr(exit_service, "exit_penalties")
        assert not hasattr(exit_service, "warn_exit")
        assert not hasattr(exit_service, "show_warning")

    def test_no_reason_required_method(self, exit_service):
        """Exit service has no reason required method (AC7)."""
        assert not hasattr(exit_service, "require_reason")
        assert not hasattr(exit_service, "set_reason")
        assert not hasattr(exit_service, "get_reason")

    def test_no_are_you_sure_method(self, exit_service):
        """Exit service has no 'are you sure' method (AC7)."""
        assert not hasattr(exit_service, "are_you_sure")
        assert not hasattr(exit_service, "confirm_decision")

    @pytest.mark.asyncio
    async def test_exit_is_immediate(self, exit_service, cluster_id):
        """Exit processes immediately with no intermediate waiting (AC7)."""
        result = await exit_service.initiate_exit(cluster_id)

        # Completed in single call
        assert result.is_complete
        # No pending status
        assert result.status != ExitStatus.PROCESSING


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_already_exited_raises_error(self, exit_service, exit_port, cluster_id):
        """Cannot exit twice - raises AlreadyExitedError."""
        exit_port.mark_as_exited(cluster_id)

        with pytest.raises(AlreadyExitedError):
            await exit_service.initiate_exit(cluster_id)

    @pytest.mark.asyncio
    async def test_already_exited_error_message(self, exit_service, exit_port, cluster_id):
        """AlreadyExitedError contains cluster ID."""
        exit_port.mark_as_exited(cluster_id)

        with pytest.raises(AlreadyExitedError) as exc_info:
            await exit_service.initiate_exit(cluster_id)

        assert str(cluster_id) in str(exc_info.value)


# =============================================================================
# Data Recording Tests
# =============================================================================


class TestDataRecording:
    """Tests for data recording."""

    @pytest.mark.asyncio
    async def test_exit_request_recorded(self, exit_service, exit_port, cluster_id):
        """Exit request is recorded to port."""
        result = await exit_service.initiate_exit(cluster_id)

        recorded_request = await exit_port.get_exit_request(result.request_id)

        assert recorded_request is not None
        assert recorded_request.cluster_id == cluster_id

    @pytest.mark.asyncio
    async def test_exit_result_recorded(self, exit_service, exit_port, cluster_id):
        """Exit result is recorded to port."""
        result = await exit_service.initiate_exit(cluster_id)

        recorded_result = await exit_port.get_exit_result(result.request_id)

        assert recorded_result is not None
        assert recorded_result.status == ExitStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_cluster_marked_as_exited(self, exit_service, exit_port, cluster_id):
        """Cluster is marked as exited after completion."""
        await exit_service.initiate_exit(cluster_id)

        assert await exit_port.has_cluster_exited(cluster_id) is True


# =============================================================================
# Exit Status Query Tests
# =============================================================================


class TestExitStatusQuery:
    """Tests for exit status querying."""

    @pytest.mark.asyncio
    async def test_get_exit_status_none_before_exit(self, exit_service, cluster_id):
        """get_exit_status returns None before exit."""
        status = await exit_service.get_exit_status(cluster_id)

        assert status is None

    @pytest.mark.asyncio
    async def test_get_exit_status_completed_after_exit(self, exit_service, cluster_id):
        """get_exit_status returns COMPLETED after exit."""
        await exit_service.initiate_exit(cluster_id)

        status = await exit_service.get_exit_status(cluster_id)

        assert status == ExitStatus.COMPLETED
