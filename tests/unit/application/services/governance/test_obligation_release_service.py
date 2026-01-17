"""Unit tests for ObligationReleaseService.

Story: consent-gov-7.2: Obligation Release

Tests for:
- Releasing all obligations for a Cluster
- Pre-consent task nullification
- Post-consent task release with work preservation
- Pending request cancellation
- Event emission
- Structural absence of penalty methods (Golden Rule)

Constitutional Truths Tested:
- Golden Rule: No penalties exist
- FR44: All obligations released on exit
- CT-12: Knight observes releases (events emitted)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.domain.governance.exit.release_type import ReleaseType
from src.domain.governance.exit.obligation_release import ReleaseResult
from src.domain.governance.task.task_state import TaskStatus
from src.application.services.governance.obligation_release_service import (
    ObligationReleaseService,
    OBLIGATIONS_RELEASED_EVENT,
    TASK_NULLIFIED_ON_EXIT_EVENT,
    TASK_RELEASED_ON_EXIT_EVENT,
    PENDING_REQUESTS_CANCELLED_EVENT,
    RELEASE_CATEGORIES,
)


# =============================================================================
# Test Fixtures and Fakes
# =============================================================================


@dataclass
class FakeTask:
    """Fake task for testing."""

    task_id: UUID
    current_status: TaskStatus


class FakeTimeAuthority:
    """Fake time authority for testing."""

    def __init__(self) -> None:
        self._now = datetime.now(timezone.utc)

    def now(self) -> datetime:
        return self._now

    def set_time(self, time: datetime) -> None:
        self._now = time


class FakeEventEmitter:
    """Fake event emitter for testing."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict,
    ) -> None:
        self.events.append({
            "event_type": event_type,
            "actor": actor,
            "payload": payload,
        })

    def get_events_by_type(self, event_type: str) -> list[dict]:
        return [e for e in self.events if e["event_type"] == event_type]


class FakeTaskStatePort:
    """Fake task state port for testing."""

    def __init__(self) -> None:
        self.tasks: dict[UUID, FakeTask] = {}
        self.transitions: list[dict] = []

    def add_task(self, task: FakeTask) -> None:
        self.tasks[task.task_id] = task

    async def get_tasks_for_cluster(self, cluster_id: UUID) -> list[FakeTask]:
        return list(self.tasks.values())

    async def transition_task(
        self,
        task_id: UUID,
        to_status: TaskStatus,
        reason: str,
    ) -> None:
        self.transitions.append({
            "task_id": task_id,
            "to_status": to_status,
            "reason": reason,
        })
        if task_id in self.tasks:
            self.tasks[task_id] = FakeTask(
                task_id=task_id,
                current_status=to_status,
            )


class FakePendingRequestPort:
    """Fake pending request port for testing."""

    def __init__(self) -> None:
        self.pending_count = 0

    async def cancel_pending_for_cluster(self, cluster_id: UUID) -> int:
        count = self.pending_count
        self.pending_count = 0
        return count


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    return FakeTimeAuthority()


@pytest.fixture
def event_emitter() -> FakeEventEmitter:
    return FakeEventEmitter()


@pytest.fixture
def task_state_port() -> FakeTaskStatePort:
    return FakeTaskStatePort()


@pytest.fixture
def pending_request_port() -> FakePendingRequestPort:
    return FakePendingRequestPort()


@pytest.fixture
def service(
    task_state_port: FakeTaskStatePort,
    pending_request_port: FakePendingRequestPort,
    event_emitter: FakeEventEmitter,
    time_authority: FakeTimeAuthority,
) -> ObligationReleaseService:
    return ObligationReleaseService(
        task_state_port=task_state_port,
        pending_request_port=pending_request_port,
        event_emitter=event_emitter,
        time_authority=time_authority,
    )


# =============================================================================
# Test RELEASE_CATEGORIES Mapping
# =============================================================================


class TestReleaseCategories:
    """Unit tests for RELEASE_CATEGORIES mapping."""

    def test_pre_consent_states_map_to_nullified(self) -> None:
        """Pre-consent states map to NULLIFIED_ON_EXIT."""
        pre_consent_states = [
            TaskStatus.AUTHORIZED,
            TaskStatus.ACTIVATED,
            TaskStatus.ROUTED,
        ]
        for state in pre_consent_states:
            assert RELEASE_CATEGORIES[state] == ReleaseType.NULLIFIED_ON_EXIT

    def test_post_consent_states_map_to_released(self) -> None:
        """Post-consent states map to RELEASED_ON_EXIT."""
        post_consent_states = [
            TaskStatus.ACCEPTED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.REPORTED,
            TaskStatus.AGGREGATED,
        ]
        for state in post_consent_states:
            assert RELEASE_CATEGORIES[state] == ReleaseType.RELEASED_ON_EXIT

    def test_terminal_states_not_in_categories(self) -> None:
        """Terminal states are not in release categories."""
        terminal_states = [
            TaskStatus.COMPLETED,
            TaskStatus.DECLINED,
            TaskStatus.QUARANTINED,
            TaskStatus.NULLIFIED,
        ]
        for state in terminal_states:
            assert state not in RELEASE_CATEGORIES


# =============================================================================
# Test Pre-Consent Task Nullification (AC6)
# =============================================================================


class TestPreConsentNullification:
    """Tests for pre-consent task nullification (AC6)."""

    @pytest.mark.asyncio
    async def test_authorized_task_nullified(
        self,
        service: ObligationReleaseService,
        task_state_port: FakeTaskStatePort,
    ) -> None:
        """AUTHORIZED task is nullified on exit."""
        cluster_id = uuid4()
        task = FakeTask(task_id=uuid4(), current_status=TaskStatus.AUTHORIZED)
        task_state_port.add_task(task)

        result = await service.release_all(cluster_id)

        assert result.nullified_count == 1
        assert result.released_count == 0
        # Task should be transitioned to NULLIFIED
        assert task_state_port.tasks[task.task_id].current_status == TaskStatus.NULLIFIED

    @pytest.mark.asyncio
    async def test_activated_task_nullified(
        self,
        service: ObligationReleaseService,
        task_state_port: FakeTaskStatePort,
    ) -> None:
        """ACTIVATED task is nullified on exit."""
        cluster_id = uuid4()
        task = FakeTask(task_id=uuid4(), current_status=TaskStatus.ACTIVATED)
        task_state_port.add_task(task)

        result = await service.release_all(cluster_id)

        assert result.nullified_count == 1
        assert task_state_port.tasks[task.task_id].current_status == TaskStatus.NULLIFIED

    @pytest.mark.asyncio
    async def test_routed_task_nullified(
        self,
        service: ObligationReleaseService,
        task_state_port: FakeTaskStatePort,
    ) -> None:
        """ROUTED task is nullified on exit."""
        cluster_id = uuid4()
        task = FakeTask(task_id=uuid4(), current_status=TaskStatus.ROUTED)
        task_state_port.add_task(task)

        result = await service.release_all(cluster_id)

        assert result.nullified_count == 1
        assert task_state_port.tasks[task.task_id].current_status == TaskStatus.NULLIFIED

    @pytest.mark.asyncio
    async def test_nullified_event_emitted(
        self,
        service: ObligationReleaseService,
        task_state_port: FakeTaskStatePort,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """TASK_NULLIFIED_ON_EXIT event is emitted."""
        cluster_id = uuid4()
        task = FakeTask(task_id=uuid4(), current_status=TaskStatus.ROUTED)
        task_state_port.add_task(task)

        await service.release_all(cluster_id)

        events = event_emitter.get_events_by_type(TASK_NULLIFIED_ON_EXIT_EVENT)
        assert len(events) == 1
        assert events[0]["payload"]["task_id"] == str(task.task_id)
        assert events[0]["payload"]["previous_state"] == "routed"
        assert events[0]["payload"]["work_preserved"] is False


# =============================================================================
# Test Post-Consent Task Release with Work Preservation (AC7)
# =============================================================================


class TestPostConsentRelease:
    """Tests for post-consent task release (AC7)."""

    @pytest.mark.asyncio
    async def test_accepted_task_released(
        self,
        service: ObligationReleaseService,
        task_state_port: FakeTaskStatePort,
    ) -> None:
        """ACCEPTED task is released on exit."""
        cluster_id = uuid4()
        task = FakeTask(task_id=uuid4(), current_status=TaskStatus.ACCEPTED)
        task_state_port.add_task(task)

        result = await service.release_all(cluster_id)

        assert result.released_count == 1
        assert result.nullified_count == 0
        # Post-consent tasks go to QUARANTINED (work preserved)
        assert task_state_port.tasks[task.task_id].current_status == TaskStatus.QUARANTINED

    @pytest.mark.asyncio
    async def test_in_progress_task_released(
        self,
        service: ObligationReleaseService,
        task_state_port: FakeTaskStatePort,
    ) -> None:
        """IN_PROGRESS task is released on exit."""
        cluster_id = uuid4()
        task = FakeTask(task_id=uuid4(), current_status=TaskStatus.IN_PROGRESS)
        task_state_port.add_task(task)

        result = await service.release_all(cluster_id)

        assert result.released_count == 1
        assert task_state_port.tasks[task.task_id].current_status == TaskStatus.QUARANTINED

    @pytest.mark.asyncio
    async def test_reported_task_released(
        self,
        service: ObligationReleaseService,
        task_state_port: FakeTaskStatePort,
    ) -> None:
        """REPORTED task is released on exit."""
        cluster_id = uuid4()
        task = FakeTask(task_id=uuid4(), current_status=TaskStatus.REPORTED)
        task_state_port.add_task(task)

        result = await service.release_all(cluster_id)

        assert result.released_count == 1
        assert task_state_port.tasks[task.task_id].current_status == TaskStatus.QUARANTINED

    @pytest.mark.asyncio
    async def test_aggregated_task_released(
        self,
        service: ObligationReleaseService,
        task_state_port: FakeTaskStatePort,
    ) -> None:
        """AGGREGATED task is released on exit."""
        cluster_id = uuid4()
        task = FakeTask(task_id=uuid4(), current_status=TaskStatus.AGGREGATED)
        task_state_port.add_task(task)

        result = await service.release_all(cluster_id)

        assert result.released_count == 1
        assert task_state_port.tasks[task.task_id].current_status == TaskStatus.QUARANTINED

    @pytest.mark.asyncio
    async def test_released_event_emitted(
        self,
        service: ObligationReleaseService,
        task_state_port: FakeTaskStatePort,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """TASK_RELEASED_ON_EXIT event is emitted."""
        cluster_id = uuid4()
        task = FakeTask(task_id=uuid4(), current_status=TaskStatus.IN_PROGRESS)
        task_state_port.add_task(task)

        await service.release_all(cluster_id)

        events = event_emitter.get_events_by_type(TASK_RELEASED_ON_EXIT_EVENT)
        assert len(events) == 1
        assert events[0]["payload"]["task_id"] == str(task.task_id)
        assert events[0]["payload"]["previous_state"] == "in_progress"
        assert events[0]["payload"]["work_preserved"] is True


# =============================================================================
# Test Terminal State Handling (AC2)
# =============================================================================


class TestTerminalStateHandling:
    """Tests for terminal state handling."""

    @pytest.mark.asyncio
    async def test_completed_tasks_not_released(
        self,
        service: ObligationReleaseService,
        task_state_port: FakeTaskStatePort,
    ) -> None:
        """COMPLETED tasks are not released (already done)."""
        cluster_id = uuid4()
        task = FakeTask(task_id=uuid4(), current_status=TaskStatus.COMPLETED)
        task_state_port.add_task(task)

        result = await service.release_all(cluster_id)

        assert result.total_obligations == 0
        assert len(task_state_port.transitions) == 0

    @pytest.mark.asyncio
    async def test_declined_tasks_not_released(
        self,
        service: ObligationReleaseService,
        task_state_port: FakeTaskStatePort,
    ) -> None:
        """DECLINED tasks are not released (already done)."""
        cluster_id = uuid4()
        task = FakeTask(task_id=uuid4(), current_status=TaskStatus.DECLINED)
        task_state_port.add_task(task)

        result = await service.release_all(cluster_id)

        assert result.total_obligations == 0

    @pytest.mark.asyncio
    async def test_quarantined_tasks_not_released(
        self,
        service: ObligationReleaseService,
        task_state_port: FakeTaskStatePort,
    ) -> None:
        """QUARANTINED tasks are not released (already done)."""
        cluster_id = uuid4()
        task = FakeTask(task_id=uuid4(), current_status=TaskStatus.QUARANTINED)
        task_state_port.add_task(task)

        result = await service.release_all(cluster_id)

        assert result.total_obligations == 0


# =============================================================================
# Test Pending Request Cancellation (AC3)
# =============================================================================


class TestPendingRequestCancellation:
    """Tests for pending request cancellation (AC3)."""

    @pytest.mark.asyncio
    async def test_pending_requests_cancelled(
        self,
        service: ObligationReleaseService,
        pending_request_port: FakePendingRequestPort,
    ) -> None:
        """Pending requests are cancelled on exit."""
        cluster_id = uuid4()
        pending_request_port.pending_count = 5

        result = await service.release_all(cluster_id)

        assert result.pending_cancelled == 5

    @pytest.mark.asyncio
    async def test_pending_cancelled_event_emitted(
        self,
        service: ObligationReleaseService,
        pending_request_port: FakePendingRequestPort,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """PENDING_REQUESTS_CANCELLED event is emitted when requests cancelled."""
        cluster_id = uuid4()
        pending_request_port.pending_count = 3

        await service.release_all(cluster_id)

        events = event_emitter.get_events_by_type(PENDING_REQUESTS_CANCELLED_EVENT)
        assert len(events) == 1
        assert events[0]["payload"]["cancelled_count"] == 3

    @pytest.mark.asyncio
    async def test_no_event_when_no_pending(
        self,
        service: ObligationReleaseService,
        pending_request_port: FakePendingRequestPort,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """No event emitted when no pending requests."""
        cluster_id = uuid4()
        pending_request_port.pending_count = 0

        await service.release_all(cluster_id)

        events = event_emitter.get_events_by_type(PENDING_REQUESTS_CANCELLED_EVENT)
        assert len(events) == 0


# =============================================================================
# Test Event Emission (AC5)
# =============================================================================


class TestEventEmission:
    """Tests for event emission (AC5)."""

    @pytest.mark.asyncio
    async def test_obligations_released_event_emitted(
        self,
        service: ObligationReleaseService,
        task_state_port: FakeTaskStatePort,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """OBLIGATIONS_RELEASED event is emitted."""
        cluster_id = uuid4()
        task1 = FakeTask(task_id=uuid4(), current_status=TaskStatus.ROUTED)
        task2 = FakeTask(task_id=uuid4(), current_status=TaskStatus.IN_PROGRESS)
        task_state_port.add_task(task1)
        task_state_port.add_task(task2)

        await service.release_all(cluster_id)

        events = event_emitter.get_events_by_type(OBLIGATIONS_RELEASED_EVENT)
        assert len(events) == 1
        payload = events[0]["payload"]
        assert payload["cluster_id"] == str(cluster_id)
        assert payload["nullified_count"] == 1
        assert payload["released_count"] == 1
        assert payload["total_obligations"] == 2

    @pytest.mark.asyncio
    async def test_event_emitted_even_with_no_obligations(
        self,
        service: ObligationReleaseService,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """OBLIGATIONS_RELEASED event emitted even with no obligations."""
        cluster_id = uuid4()

        await service.release_all(cluster_id)

        events = event_emitter.get_events_by_type(OBLIGATIONS_RELEASED_EVENT)
        assert len(events) == 1
        assert events[0]["payload"]["total_obligations"] == 0


# =============================================================================
# Test Mixed Task States
# =============================================================================


class TestMixedTaskStates:
    """Tests for handling multiple tasks in different states."""

    @pytest.mark.asyncio
    async def test_handles_mixed_states(
        self,
        service: ObligationReleaseService,
        task_state_port: FakeTaskStatePort,
    ) -> None:
        """Handles tasks in mixed states correctly."""
        cluster_id = uuid4()

        # Pre-consent tasks (should be nullified)
        task1 = FakeTask(task_id=uuid4(), current_status=TaskStatus.AUTHORIZED)
        task2 = FakeTask(task_id=uuid4(), current_status=TaskStatus.ROUTED)

        # Post-consent tasks (should be released)
        task3 = FakeTask(task_id=uuid4(), current_status=TaskStatus.ACCEPTED)
        task4 = FakeTask(task_id=uuid4(), current_status=TaskStatus.IN_PROGRESS)

        # Terminal tasks (should be skipped)
        task5 = FakeTask(task_id=uuid4(), current_status=TaskStatus.COMPLETED)

        for task in [task1, task2, task3, task4, task5]:
            task_state_port.add_task(task)

        result = await service.release_all(cluster_id)

        assert result.nullified_count == 2
        assert result.released_count == 2
        assert result.total_obligations == 4


# =============================================================================
# Test Return Value (ReleaseResult)
# =============================================================================


class TestReleaseResultReturn:
    """Tests for ReleaseResult return value."""

    @pytest.mark.asyncio
    async def test_returns_release_result(
        self,
        service: ObligationReleaseService,
        task_state_port: FakeTaskStatePort,
        pending_request_port: FakePendingRequestPort,
    ) -> None:
        """Returns ReleaseResult with correct values."""
        cluster_id = uuid4()
        task1 = FakeTask(task_id=uuid4(), current_status=TaskStatus.ROUTED)
        task2 = FakeTask(task_id=uuid4(), current_status=TaskStatus.IN_PROGRESS)
        task_state_port.add_task(task1)
        task_state_port.add_task(task2)
        pending_request_port.pending_count = 3

        result = await service.release_all(cluster_id)

        assert isinstance(result, ReleaseResult)
        assert result.cluster_id == cluster_id
        assert result.nullified_count == 1
        assert result.released_count == 1
        assert result.pending_cancelled == 3
        assert result.total_obligations == 2

    @pytest.mark.asyncio
    async def test_result_has_released_at_timestamp(
        self,
        service: ObligationReleaseService,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """ReleaseResult has correct released_at timestamp."""
        cluster_id = uuid4()
        expected_time = datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc)
        time_authority.set_time(expected_time)

        result = await service.release_all(cluster_id)

        assert result.released_at == expected_time


# =============================================================================
# Test No Penalty Methods (AC4 - Golden Rule)
# =============================================================================


class TestNoPenaltyMethods:
    """Tests ensuring no penalty methods exist (AC4 - Golden Rule).

    Per Golden Rule: Refusal is penalty-free.
    These tests ensure structural absence of penalty mechanisms.
    """

    def test_no_apply_penalty_method(
        self,
        service: ObligationReleaseService,
    ) -> None:
        """No apply_penalty method exists."""
        assert not hasattr(service, "apply_penalty")

    def test_no_reduce_standing_method(
        self,
        service: ObligationReleaseService,
    ) -> None:
        """No reduce_standing method exists."""
        assert not hasattr(service, "reduce_standing")

    def test_no_mark_early_exit_method(
        self,
        service: ObligationReleaseService,
    ) -> None:
        """No mark_early_exit method exists."""
        assert not hasattr(service, "mark_early_exit")

    def test_no_penalize_method(
        self,
        service: ObligationReleaseService,
    ) -> None:
        """No penalize method exists."""
        assert not hasattr(service, "penalize")

    def test_no_decrease_reputation_method(
        self,
        service: ObligationReleaseService,
    ) -> None:
        """No decrease_reputation method exists."""
        assert not hasattr(service, "decrease_reputation")

    def test_no_record_abandonment_method(
        self,
        service: ObligationReleaseService,
    ) -> None:
        """No record_abandonment method exists."""
        assert not hasattr(service, "record_abandonment")

    def test_only_expected_public_methods_exist(
        self,
        service: ObligationReleaseService,
    ) -> None:
        """Only expected public methods exist (whitelist)."""
        public_methods = [
            name for name in dir(service)
            if not name.startswith("_") and callable(getattr(service, name))
        ]
        assert public_methods == ["release_all"]
