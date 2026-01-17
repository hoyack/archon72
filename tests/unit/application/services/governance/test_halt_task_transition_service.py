"""Unit tests for HaltTaskTransitionService.

Story: consent-gov-4.3: Task State Transitions on Halt

Tests for task state transitions when system halt is triggered.
Covers all acceptance criteria and constitutional requirements.

Acceptance Criteria Tested:
- AC1: Pre-consent tasks transition to nullified (FR24)
- AC2: Post-consent tasks transition to quarantined (FR25)
- AC3: Completed tasks remain unchanged (FR26)
- AC4: State transitions are atomic (FR27, NFR-ATOMIC-01)
- AC5: In-flight tasks resolve deterministically (NFR-REL-03)
- AC6: All transitions emit events with halt correlation
- AC7: No partial transitions (all or nothing per task)
- AC8: Transition audit trail preserved
- AC9: Unit tests for each task state category
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.application.ports.governance.halt_task_transition_port import (
    ConcurrentModificationError,
    HaltTransitionResult,
    HaltTransitionType,
    TaskStateCategory,
    TaskTransitionRecord,
)
from src.application.services.governance.halt_task_transition_service import (
    HaltTaskTransitionService,
)
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.task.task_state import TaskStatus
from tests.helpers.fake_time_authority import FakeTimeAuthority


class FakeLedger:
    """Fake ledger for capturing emitted events."""

    def __init__(self, *, should_fail: bool = False) -> None:
        self.events: list[GovernanceEvent] = []
        self.should_fail = should_fail

    async def append_event(self, event: GovernanceEvent) -> Any:
        """Append event to ledger."""
        if self.should_fail:
            raise ConnectionError("Ledger unavailable")
        self.events.append(event)
        return event

    def get_events_by_type(self, event_type: str) -> list[GovernanceEvent]:
        """Get events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def get_last_event(self) -> GovernanceEvent | None:
        """Get the last event."""
        return self.events[-1] if self.events else None


class FakeTaskStatePort:
    """Fake task state port for testing."""

    def __init__(
        self,
        tasks: list[tuple[UUID, str]] | None = None,
        *,
        fail_on_transition: set[UUID] | None = None,
    ) -> None:
        # Active tasks: (task_id, status)
        self._tasks: dict[UUID, str] = {}
        if tasks:
            for task_id, status in tasks:
                self._tasks[task_id] = status

        # Set of task IDs that should fail on transition
        self._fail_on_transition = fail_on_transition or set()

        # Track transition calls
        self.transition_calls: list[dict] = []

    async def get_active_tasks(self) -> list[tuple[UUID, str]]:
        """Get all active (non-terminal) tasks."""
        return [(tid, status) for tid, status in self._tasks.items()]

    async def atomic_transition(
        self,
        task_id: UUID,
        from_status: str,
        to_status: str,
    ) -> None:
        """Atomically transition a single task."""
        self.transition_calls.append({
            "task_id": task_id,
            "from_status": from_status,
            "to_status": to_status,
        })

        if task_id in self._fail_on_transition:
            raise ConcurrentModificationError(
                task_id=task_id,
                expected_status=from_status,
                actual_status="concurrent_modified",
            )

        if task_id not in self._tasks:
            raise ConcurrentModificationError(
                task_id=task_id,
                expected_status=from_status,
                actual_status="not_found",
            )

        current = self._tasks[task_id]
        if current != from_status:
            raise ConcurrentModificationError(
                task_id=task_id,
                expected_status=from_status,
                actual_status=current,
            )

        self._tasks[task_id] = to_status

    def add_task(self, task_id: UUID, status: str) -> None:
        """Add a task for testing."""
        self._tasks[task_id] = status

    def get_task_status(self, task_id: UUID) -> str | None:
        """Get task status by ID."""
        return self._tasks.get(task_id)


@pytest.fixture
def fake_time() -> FakeTimeAuthority:
    """Provide fake time authority."""
    return FakeTimeAuthority(
        frozen_at=datetime(2026, 1, 17, 10, 0, 0, tzinfo=timezone.utc)
    )


@pytest.fixture
def fake_ledger() -> FakeLedger:
    """Provide fake ledger."""
    return FakeLedger()


@pytest.fixture
def fake_task_state() -> FakeTaskStatePort:
    """Provide fake task state port."""
    return FakeTaskStatePort()


@pytest.fixture
def service(
    fake_task_state: FakeTaskStatePort,
    fake_ledger: FakeLedger,
    fake_time: FakeTimeAuthority,
) -> HaltTaskTransitionService:
    """Create service instance."""
    return HaltTaskTransitionService(
        task_state_port=fake_task_state,
        ledger=fake_ledger,
        time_authority=fake_time,
    )


class TestHaltTaskTransitionServiceImport:
    """Tests for module imports."""

    def test_service_can_be_imported(self) -> None:
        """Service can be imported from governance services."""
        from src.application.services.governance.halt_task_transition_service import (
            HaltTaskTransitionService,
        )
        assert HaltTaskTransitionService is not None

    def test_port_can_be_imported(self) -> None:
        """Port can be imported from governance ports."""
        from src.application.ports.governance.halt_task_transition_port import (
            HaltTaskTransitionPort,
        )
        assert HaltTaskTransitionPort is not None


class TestHaltTaskTransitionServiceCreation:
    """Tests for service instantiation."""

    def test_service_creation(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """Service can be created with all dependencies."""
        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )
        assert service is not None


class TestPreConsentTaskNullification:
    """Tests for AC1: Pre-consent tasks transition to nullified (FR24)."""

    @pytest.mark.asyncio
    async def test_authorized_task_becomes_nullified(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """AUTHORIZED task transitions to NULLIFIED on halt (AC1)."""
        task_id = uuid4()
        fake_task_state.add_task(task_id, TaskStatus.AUTHORIZED.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        result = await service.transition_all_tasks_on_halt(halt_id)

        assert result.nullified_count == 1
        assert fake_task_state.get_task_status(task_id) == TaskStatus.NULLIFIED.value

    @pytest.mark.asyncio
    async def test_activated_task_becomes_nullified(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """ACTIVATED task transitions to NULLIFIED on halt (AC1)."""
        task_id = uuid4()
        fake_task_state.add_task(task_id, TaskStatus.ACTIVATED.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        result = await service.transition_all_tasks_on_halt(halt_id)

        assert result.nullified_count == 1
        assert fake_task_state.get_task_status(task_id) == TaskStatus.NULLIFIED.value

    @pytest.mark.asyncio
    async def test_routed_task_becomes_nullified(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """ROUTED task transitions to NULLIFIED on halt (AC1)."""
        task_id = uuid4()
        fake_task_state.add_task(task_id, TaskStatus.ROUTED.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        result = await service.transition_all_tasks_on_halt(halt_id)

        assert result.nullified_count == 1
        assert fake_task_state.get_task_status(task_id) == TaskStatus.NULLIFIED.value

    @pytest.mark.asyncio
    async def test_nullified_event_emitted(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """Pre-consent nullification emits executive.task.nullified_on_halt (AC6)."""
        task_id = uuid4()
        fake_task_state.add_task(task_id, TaskStatus.ROUTED.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        await service.transition_all_tasks_on_halt(halt_id)

        events = fake_ledger.get_events_by_type("executive.task.nullified_on_halt")
        assert len(events) == 1
        assert events[0].payload["task_id"] == str(task_id)
        assert events[0].payload["halt_correlation_id"] == str(halt_id)
        assert events[0].payload["reason"] == "system_halt_pre_consent"


class TestPostConsentTaskQuarantine:
    """Tests for AC2: Post-consent tasks transition to quarantined (FR25)."""

    @pytest.mark.asyncio
    async def test_accepted_task_becomes_quarantined(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """ACCEPTED task transitions to QUARANTINED on halt (AC2)."""
        task_id = uuid4()
        fake_task_state.add_task(task_id, TaskStatus.ACCEPTED.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        result = await service.transition_all_tasks_on_halt(halt_id)

        assert result.quarantined_count == 1
        assert fake_task_state.get_task_status(task_id) == TaskStatus.QUARANTINED.value

    @pytest.mark.asyncio
    async def test_in_progress_task_becomes_quarantined(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """IN_PROGRESS task transitions to QUARANTINED on halt (AC2)."""
        task_id = uuid4()
        fake_task_state.add_task(task_id, TaskStatus.IN_PROGRESS.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        result = await service.transition_all_tasks_on_halt(halt_id)

        assert result.quarantined_count == 1
        assert fake_task_state.get_task_status(task_id) == TaskStatus.QUARANTINED.value

    @pytest.mark.asyncio
    async def test_reported_task_becomes_quarantined(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """REPORTED task transitions to QUARANTINED on halt (AC2)."""
        task_id = uuid4()
        fake_task_state.add_task(task_id, TaskStatus.REPORTED.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        result = await service.transition_all_tasks_on_halt(halt_id)

        assert result.quarantined_count == 1
        assert fake_task_state.get_task_status(task_id) == TaskStatus.QUARANTINED.value

    @pytest.mark.asyncio
    async def test_aggregated_task_becomes_quarantined(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """AGGREGATED task transitions to QUARANTINED on halt (AC2)."""
        task_id = uuid4()
        fake_task_state.add_task(task_id, TaskStatus.AGGREGATED.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        result = await service.transition_all_tasks_on_halt(halt_id)

        assert result.quarantined_count == 1
        assert fake_task_state.get_task_status(task_id) == TaskStatus.QUARANTINED.value

    @pytest.mark.asyncio
    async def test_quarantined_event_emitted(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """Post-consent quarantine emits executive.task.quarantined_on_halt (AC6)."""
        task_id = uuid4()
        fake_task_state.add_task(task_id, TaskStatus.IN_PROGRESS.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        await service.transition_all_tasks_on_halt(halt_id)

        events = fake_ledger.get_events_by_type("executive.task.quarantined_on_halt")
        assert len(events) == 1
        assert events[0].payload["task_id"] == str(task_id)
        assert events[0].payload["halt_correlation_id"] == str(halt_id)
        assert events[0].payload["reason"] == "system_halt_post_consent"
        assert events[0].payload["work_preserved"] is True


class TestTerminalTaskPreservation:
    """Tests for AC3: Completed tasks remain unchanged (FR26)."""

    @pytest.mark.asyncio
    async def test_completed_task_unchanged(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """COMPLETED task remains COMPLETED on halt (AC3)."""
        task_id = uuid4()
        fake_task_state.add_task(task_id, TaskStatus.COMPLETED.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        result = await service.transition_all_tasks_on_halt(halt_id)

        assert result.preserved_count == 1
        assert fake_task_state.get_task_status(task_id) == TaskStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_declined_task_unchanged(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """DECLINED task remains DECLINED on halt (AC3)."""
        task_id = uuid4()
        fake_task_state.add_task(task_id, TaskStatus.DECLINED.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        result = await service.transition_all_tasks_on_halt(halt_id)

        assert result.preserved_count == 1
        assert fake_task_state.get_task_status(task_id) == TaskStatus.DECLINED.value

    @pytest.mark.asyncio
    async def test_quarantined_task_unchanged(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """Already QUARANTINED task remains QUARANTINED on halt (AC3)."""
        task_id = uuid4()
        fake_task_state.add_task(task_id, TaskStatus.QUARANTINED.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        result = await service.transition_all_tasks_on_halt(halt_id)

        assert result.preserved_count == 1
        assert fake_task_state.get_task_status(task_id) == TaskStatus.QUARANTINED.value

    @pytest.mark.asyncio
    async def test_nullified_task_unchanged(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """Already NULLIFIED task remains NULLIFIED on halt (AC3)."""
        task_id = uuid4()
        fake_task_state.add_task(task_id, TaskStatus.NULLIFIED.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        result = await service.transition_all_tasks_on_halt(halt_id)

        assert result.preserved_count == 1
        assert fake_task_state.get_task_status(task_id) == TaskStatus.NULLIFIED.value

    @pytest.mark.asyncio
    async def test_preserved_event_emitted(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """Terminal task preservation emits executive.task.preserved_on_halt (AC6)."""
        task_id = uuid4()
        fake_task_state.add_task(task_id, TaskStatus.COMPLETED.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        await service.transition_all_tasks_on_halt(halt_id)

        events = fake_ledger.get_events_by_type("executive.task.preserved_on_halt")
        assert len(events) == 1
        assert events[0].payload["task_id"] == str(task_id)
        assert events[0].payload["halt_correlation_id"] == str(halt_id)
        assert events[0].payload["reason"] == "terminal_state_unchanged"


class TestAtomicTransitions:
    """Tests for AC4: State transitions are atomic (FR27, NFR-ATOMIC-01)."""

    @pytest.mark.asyncio
    async def test_concurrent_modification_fails_gracefully(
        self,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """Concurrent modification results in FAILED transition type (AC4)."""
        task_id = uuid4()
        fake_task_state = FakeTaskStatePort(
            tasks=[(task_id, TaskStatus.ROUTED.value)],
            fail_on_transition={task_id},
        )

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        result = await service.transition_all_tasks_on_halt(halt_id)

        assert result.failed_count == 1
        assert task_id in result.failed_task_ids

    @pytest.mark.asyncio
    async def test_atomic_transition_called_with_correct_args(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """Atomic transition receives correct from_status and to_status (AC4)."""
        task_id = uuid4()
        fake_task_state.add_task(task_id, TaskStatus.ROUTED.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        await service.transition_all_tasks_on_halt(uuid4())

        assert len(fake_task_state.transition_calls) == 1
        call = fake_task_state.transition_calls[0]
        assert call["task_id"] == task_id
        assert call["from_status"] == TaskStatus.ROUTED.value
        assert call["to_status"] == TaskStatus.NULLIFIED.value


class TestInFlightTaskResolution:
    """Tests for AC5: In-flight tasks resolve deterministically (NFR-REL-03)."""

    @pytest.mark.asyncio
    async def test_in_flight_tasks_resolve_to_committed_state(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """In-flight tasks resolve based on committed state (AC5)."""
        # Task is in ROUTED state (pre-consent)
        task_id = uuid4()
        fake_task_state.add_task(task_id, TaskStatus.ROUTED.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        result = await service.transition_all_tasks_on_halt(halt_id)

        # Should be nullified based on pre-consent state
        assert result.nullified_count == 1
        assert fake_task_state.get_task_status(task_id) == TaskStatus.NULLIFIED.value


class TestEventCorrelation:
    """Tests for AC6: All transitions emit events with halt correlation."""

    @pytest.mark.asyncio
    async def test_all_events_have_halt_correlation_id(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """All emitted events include halt_correlation_id (AC6)."""
        # Add tasks of each type
        pre_consent_id = uuid4()
        post_consent_id = uuid4()
        terminal_id = uuid4()

        fake_task_state.add_task(pre_consent_id, TaskStatus.ROUTED.value)
        fake_task_state.add_task(post_consent_id, TaskStatus.IN_PROGRESS.value)
        fake_task_state.add_task(terminal_id, TaskStatus.COMPLETED.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        await service.transition_all_tasks_on_halt(halt_id)

        # Check all events have the correlation ID
        for event in fake_ledger.events:
            if "on_halt" in event.event_type:
                assert event.payload.get("halt_correlation_id") == str(halt_id)

    @pytest.mark.asyncio
    async def test_summary_event_emitted(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """Summary event emitted after all transitions (AC8)."""
        task_id = uuid4()
        fake_task_state.add_task(task_id, TaskStatus.ROUTED.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        await service.transition_all_tasks_on_halt(halt_id)

        summary_events = fake_ledger.get_events_by_type(
            "executive.task.halt_transitions_completed"
        )
        assert len(summary_events) == 1
        assert summary_events[0].payload["halt_correlation_id"] == str(halt_id)


class TestMixedTaskCategories:
    """Tests for mixed task states during halt."""

    @pytest.mark.asyncio
    async def test_all_categories_processed(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """All task categories are processed correctly (AC9)."""
        # Pre-consent tasks
        pre1 = uuid4()
        pre2 = uuid4()
        pre3 = uuid4()
        fake_task_state.add_task(pre1, TaskStatus.AUTHORIZED.value)
        fake_task_state.add_task(pre2, TaskStatus.ACTIVATED.value)
        fake_task_state.add_task(pre3, TaskStatus.ROUTED.value)

        # Post-consent tasks
        post1 = uuid4()
        post2 = uuid4()
        post3 = uuid4()
        post4 = uuid4()
        fake_task_state.add_task(post1, TaskStatus.ACCEPTED.value)
        fake_task_state.add_task(post2, TaskStatus.IN_PROGRESS.value)
        fake_task_state.add_task(post3, TaskStatus.REPORTED.value)
        fake_task_state.add_task(post4, TaskStatus.AGGREGATED.value)

        # Terminal tasks
        term1 = uuid4()
        term2 = uuid4()
        term3 = uuid4()
        term4 = uuid4()
        fake_task_state.add_task(term1, TaskStatus.COMPLETED.value)
        fake_task_state.add_task(term2, TaskStatus.DECLINED.value)
        fake_task_state.add_task(term3, TaskStatus.QUARANTINED.value)
        fake_task_state.add_task(term4, TaskStatus.NULLIFIED.value)

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        result = await service.transition_all_tasks_on_halt(halt_id)

        assert result.nullified_count == 3  # pre-consent
        assert result.quarantined_count == 4  # post-consent
        assert result.preserved_count == 4  # terminal
        assert result.failed_count == 0
        assert result.total_processed == 11
        assert result.is_complete_success


class TestHaltTransitionResult:
    """Tests for HaltTransitionResult dataclass."""

    def test_execution_ms_calculation(self, fake_time: FakeTimeAuthority) -> None:
        """execution_ms is calculated correctly."""
        triggered_at = fake_time.now()
        fake_time.advance(seconds=0.05)  # 50ms
        completed_at = fake_time.now()

        result = HaltTransitionResult(
            halt_correlation_id=uuid4(),
            triggered_at=triggered_at,
            completed_at=completed_at,
            nullified_count=0,
            quarantined_count=0,
            preserved_count=0,
            failed_count=0,
            total_processed=0,
        )

        assert 49.0 <= result.execution_ms <= 51.0

    def test_is_complete_success(self) -> None:
        """is_complete_success is True when failed_count is 0."""
        result = HaltTransitionResult(
            halt_correlation_id=uuid4(),
            triggered_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            nullified_count=5,
            quarantined_count=3,
            preserved_count=2,
            failed_count=0,
            total_processed=10,
        )

        assert result.is_complete_success

    def test_is_not_complete_success_with_failures(self) -> None:
        """is_complete_success is False when failed_count > 0."""
        result = HaltTransitionResult(
            halt_correlation_id=uuid4(),
            triggered_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            nullified_count=5,
            quarantined_count=3,
            preserved_count=2,
            failed_count=1,
            total_processed=11,
        )

        assert not result.is_complete_success

    def test_failed_task_ids_extraction(self) -> None:
        """failed_task_ids returns IDs of failed transitions."""
        task1 = uuid4()
        task2 = uuid4()
        task3 = uuid4()

        records = (
            TaskTransitionRecord(
                task_id=task1,
                previous_status="routed",
                new_status="routed",
                category=TaskStateCategory.PRE_CONSENT,
                transition_type=HaltTransitionType.FAILED,
                transitioned_at=datetime.now(timezone.utc),
                halt_correlation_id=uuid4(),
                error_message="concurrent modification",
            ),
            TaskTransitionRecord(
                task_id=task2,
                previous_status="routed",
                new_status="nullified",
                category=TaskStateCategory.PRE_CONSENT,
                transition_type=HaltTransitionType.NULLIFIED,
                transitioned_at=datetime.now(timezone.utc),
                halt_correlation_id=uuid4(),
            ),
            TaskTransitionRecord(
                task_id=task3,
                previous_status="in_progress",
                new_status="in_progress",
                category=TaskStateCategory.POST_CONSENT,
                transition_type=HaltTransitionType.FAILED,
                transitioned_at=datetime.now(timezone.utc),
                halt_correlation_id=uuid4(),
                error_message="another error",
            ),
        )

        result = HaltTransitionResult(
            halt_correlation_id=uuid4(),
            triggered_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            nullified_count=1,
            quarantined_count=0,
            preserved_count=0,
            failed_count=2,
            total_processed=3,
            transition_records=records,
        )

        failed_ids = result.failed_task_ids
        assert task1 in failed_ids
        assert task3 in failed_ids
        assert task2 not in failed_ids


class TestTaskTransitionRecord:
    """Tests for TaskTransitionRecord dataclass."""

    def test_is_success_for_nullified(self) -> None:
        """is_success is True for NULLIFIED transition."""
        record = TaskTransitionRecord(
            task_id=uuid4(),
            previous_status="routed",
            new_status="nullified",
            category=TaskStateCategory.PRE_CONSENT,
            transition_type=HaltTransitionType.NULLIFIED,
            transitioned_at=datetime.now(timezone.utc),
            halt_correlation_id=uuid4(),
        )

        assert record.is_success

    def test_is_success_for_quarantined(self) -> None:
        """is_success is True for QUARANTINED transition."""
        record = TaskTransitionRecord(
            task_id=uuid4(),
            previous_status="in_progress",
            new_status="quarantined",
            category=TaskStateCategory.POST_CONSENT,
            transition_type=HaltTransitionType.QUARANTINED,
            transitioned_at=datetime.now(timezone.utc),
            halt_correlation_id=uuid4(),
        )

        assert record.is_success

    def test_is_success_for_preserved(self) -> None:
        """is_success is True for PRESERVED transition."""
        record = TaskTransitionRecord(
            task_id=uuid4(),
            previous_status="completed",
            new_status="completed",
            category=TaskStateCategory.TERMINAL,
            transition_type=HaltTransitionType.PRESERVED,
            transitioned_at=datetime.now(timezone.utc),
            halt_correlation_id=uuid4(),
        )

        assert record.is_success

    def test_is_not_success_for_failed(self) -> None:
        """is_success is False for FAILED transition."""
        record = TaskTransitionRecord(
            task_id=uuid4(),
            previous_status="routed",
            new_status="routed",
            category=TaskStateCategory.PRE_CONSENT,
            transition_type=HaltTransitionType.FAILED,
            transitioned_at=datetime.now(timezone.utc),
            halt_correlation_id=uuid4(),
            error_message="concurrent modification",
        )

        assert not record.is_success


class TestConcurrentModificationError:
    """Tests for ConcurrentModificationError exception."""

    def test_error_message_format(self) -> None:
        """Error message includes task ID and status mismatch."""
        task_id = uuid4()
        error = ConcurrentModificationError(
            task_id=task_id,
            expected_status="routed",
            actual_status="accepted",
        )

        assert str(task_id) in str(error)
        assert "routed" in str(error)
        assert "accepted" in str(error)

    def test_error_attributes(self) -> None:
        """Error attributes are set correctly."""
        task_id = uuid4()
        error = ConcurrentModificationError(
            task_id=task_id,
            expected_status="routed",
            actual_status="accepted",
        )

        assert error.task_id == task_id
        assert error.expected_status == "routed"
        assert error.actual_status == "accepted"


class TestTaskStateCategory:
    """Tests for TaskStateCategory enum."""

    def test_all_categories_defined(self) -> None:
        """All task state categories are defined."""
        assert TaskStateCategory.PRE_CONSENT.value == "pre_consent"
        assert TaskStateCategory.POST_CONSENT.value == "post_consent"
        assert TaskStateCategory.TERMINAL.value == "terminal"


class TestHaltTransitionType:
    """Tests for HaltTransitionType enum."""

    def test_all_transition_types_defined(self) -> None:
        """All halt transition types are defined."""
        assert HaltTransitionType.NULLIFIED.value == "nullified"
        assert HaltTransitionType.QUARANTINED.value == "quarantined"
        assert HaltTransitionType.PRESERVED.value == "preserved"
        assert HaltTransitionType.FAILED.value == "failed"


class TestEmptyTaskList:
    """Tests for halt with no active tasks."""

    @pytest.mark.asyncio
    async def test_empty_task_list(
        self,
        fake_task_state: FakeTaskStatePort,
        fake_ledger: FakeLedger,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """Halt with no active tasks completes successfully."""
        # No tasks added

        service = HaltTaskTransitionService(
            task_state_port=fake_task_state,
            ledger=fake_ledger,
            time_authority=fake_time,
        )

        halt_id = uuid4()
        result = await service.transition_all_tasks_on_halt(halt_id)

        assert result.nullified_count == 0
        assert result.quarantined_count == 0
        assert result.preserved_count == 0
        assert result.failed_count == 0
        assert result.total_processed == 0
        assert result.is_complete_success

        # Summary event still emitted
        summary_events = fake_ledger.get_events_by_type(
            "executive.task.halt_transitions_completed"
        )
        assert len(summary_events) == 1
