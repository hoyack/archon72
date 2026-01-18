"""Unit tests for TaskResultService.

Story: consent-gov-2.4: Task Result Submission

Tests the TaskResultService for:
- submit_result() transitions IN_PROGRESS → REPORTED (AC3)
- submit_problem_report() keeps IN_PROGRESS (AC4)
- Event emission on result submission (AC5)
- Event emission on problem report (AC6)
- Result validation against task spec (AC7)
- Problem report captures category and description (AC8)
- Unauthorized Cluster submission rejected (AC9)
- Submission from wrong state rejected

References:
- FR6: Cluster can submit task result report
- FR7: Cluster can submit problem report for in-progress task
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.application.ports.governance.task_result_port import (
    InvalidResultStateError,
    ProblemCategory,
    UnauthorizedResultError,
)
from src.domain.governance.task.task_state import TaskState, TaskStatus


class MockTaskStatePort:
    """Mock implementation of TaskStatePort for testing."""

    def __init__(self) -> None:
        self._tasks: dict[UUID, TaskState] = {}

    def add_task(self, task: TaskState) -> None:
        """Add a task to the mock store."""
        self._tasks[task.task_id] = task

    async def get_task(self, task_id: UUID) -> TaskState:
        """Get a task by ID."""
        if task_id not in self._tasks:
            from src.application.ports.governance.task_activation_port import (
                TaskNotFoundError,
            )

            raise TaskNotFoundError(task_id)
        return self._tasks[task_id]

    async def save_task(self, task: TaskState) -> None:
        """Save a task."""
        self._tasks[task.task_id] = task


class MockLedgerPort:
    """Mock implementation of GovernanceLedgerPort for testing."""

    def __init__(self) -> None:
        self.events: list[Any] = []

    async def append_event(self, event: Any) -> None:
        """Record an appended event."""
        self.events.append(event)

    async def read_events(
        self,
        event_type_pattern: str | None = None,
        payload_filter: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[Any]:
        """Read events (returns empty for mock)."""
        return []


class MockTwoPhaseEmitter:
    """Mock implementation of TwoPhaseEventEmitterPort for testing."""

    def __init__(self) -> None:
        self.intents: list[dict[str, Any]] = []
        self.commits: list[dict[str, Any]] = []
        self.failures: list[dict[str, Any]] = []
        self._next_correlation_id = uuid4()

    async def emit_intent(
        self,
        operation_type: str,
        actor_id: str,
        target_entity_id: str,
        intent_payload: dict[str, Any],
    ) -> UUID:
        """Emit an intent event."""
        correlation_id = self._next_correlation_id
        self._next_correlation_id = uuid4()
        self.intents.append(
            {
                "correlation_id": correlation_id,
                "operation_type": operation_type,
                "actor_id": actor_id,
                "target_entity_id": target_entity_id,
                "intent_payload": intent_payload,
            }
        )
        return correlation_id

    async def emit_commit(
        self,
        correlation_id: UUID,
        result_payload: dict[str, Any],
    ) -> None:
        """Emit a commit event."""
        self.commits.append(
            {
                "correlation_id": correlation_id,
                "result_payload": result_payload,
            }
        )

    async def emit_failure(
        self,
        correlation_id: UUID,
        failure_reason: str,
        failure_details: dict[str, Any],
    ) -> None:
        """Emit a failure event."""
        self.failures.append(
            {
                "correlation_id": correlation_id,
                "failure_reason": failure_reason,
                "failure_details": failure_details,
            }
        )


class MockTimeAuthority:
    """Mock implementation of TimeAuthorityProtocol for testing."""

    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime.now(timezone.utc)

    def now(self) -> datetime:
        """Return the current time."""
        return self._now

    def set_now(self, now: datetime) -> None:
        """Set the current time."""
        self._now = now


@pytest.fixture
def task_state_port() -> MockTaskStatePort:
    """Create a mock TaskStatePort."""
    return MockTaskStatePort()


@pytest.fixture
def ledger_port() -> MockLedgerPort:
    """Create a mock GovernanceLedgerPort."""
    return MockLedgerPort()


@pytest.fixture
def two_phase_emitter() -> MockTwoPhaseEmitter:
    """Create a mock TwoPhaseEventEmitterPort."""
    return MockTwoPhaseEmitter()


@pytest.fixture
def time_authority() -> MockTimeAuthority:
    """Create a mock TimeAuthorityProtocol."""
    return MockTimeAuthority()


@pytest.fixture
def in_progress_task() -> TaskState:
    """Create an IN_PROGRESS task for testing."""
    task_id = uuid4()
    now = datetime.now(timezone.utc)
    cluster_id = "cluster-1"

    # Create task in AUTHORIZED state
    task = TaskState.create(
        task_id=task_id,
        earl_id="earl-1",
        created_at=now - timedelta(hours=1),
    )
    # Transition through states to IN_PROGRESS
    task = task.with_cluster(cluster_id)
    task = task.transition(TaskStatus.ACTIVATED, now - timedelta(minutes=50), "system")
    task = task.transition(TaskStatus.ROUTED, now - timedelta(minutes=40), "system")
    task = task.transition(TaskStatus.ACCEPTED, now - timedelta(minutes=30), cluster_id)
    task = task.transition(
        TaskStatus.IN_PROGRESS, now - timedelta(minutes=20), cluster_id
    )

    return task


@pytest.fixture
def result_service(
    task_state_port: MockTaskStatePort,
    ledger_port: MockLedgerPort,
    two_phase_emitter: MockTwoPhaseEmitter,
    time_authority: MockTimeAuthority,
) -> TaskResultService:
    """Create a TaskResultService for testing."""
    from src.application.services.governance.task_result_service import (
        TaskResultService,
    )

    return TaskResultService(
        task_state_port=task_state_port,
        ledger_port=ledger_port,
        two_phase_emitter=two_phase_emitter,
        time_authority=time_authority,
    )


class TestTaskResultServiceExists:
    """Tests that TaskResultService can be imported and instantiated."""

    def test_task_result_service_can_be_imported(self) -> None:
        """Verify TaskResultService can be imported."""
        from src.application.services.governance.task_result_service import (
            TaskResultService,
        )

        assert TaskResultService is not None

    def test_task_result_service_implements_port(
        self,
        result_service: TaskResultService,
    ) -> None:
        """Verify TaskResultService implements TaskResultPort."""
        from src.application.ports.governance.task_result_port import TaskResultPort

        assert isinstance(result_service, TaskResultPort)


class TestSubmitResult:
    """Tests for submit_result() method."""

    @pytest.mark.asyncio
    async def test_submit_result_transitions_to_reported(
        self,
        result_service: TaskResultService,
        task_state_port: MockTaskStatePort,
        in_progress_task: TaskState,
    ) -> None:
        """Result submission transitions task to REPORTED (AC3)."""
        task_state_port.add_task(in_progress_task)

        result = await result_service.submit_result(
            task_id=in_progress_task.task_id,
            cluster_id=in_progress_task.cluster_id,
            output={"completion": "done"},
        )

        assert result.success is True
        assert result.new_status == "reported"

        # Verify task transitioned
        updated_task = await task_state_port.get_task(in_progress_task.task_id)
        assert updated_task.current_status == TaskStatus.REPORTED

    @pytest.mark.asyncio
    async def test_submit_result_emits_event(
        self,
        result_service: TaskResultService,
        task_state_port: MockTaskStatePort,
        ledger_port: MockLedgerPort,
        in_progress_task: TaskState,
    ) -> None:
        """Result submission emits executive.task.reported event (AC5)."""
        task_state_port.add_task(in_progress_task)

        await result_service.submit_result(
            task_id=in_progress_task.task_id,
            cluster_id=in_progress_task.cluster_id,
            output={"completion": "done"},
        )

        # Verify event was emitted
        assert len(ledger_port.events) == 1
        event = ledger_port.events[0]
        assert event.event_type == "executive.task.reported"
        assert event.payload["task_id"] == str(in_progress_task.task_id)

    @pytest.mark.asyncio
    async def test_submit_result_includes_structured_output(
        self,
        result_service: TaskResultService,
        task_state_port: MockTaskStatePort,
        in_progress_task: TaskState,
    ) -> None:
        """Result includes structured output (AC7)."""
        task_state_port.add_task(in_progress_task)

        output = {
            "status": "complete",
            "artifacts": ["file1.txt", "file2.txt"],
            "metrics": {"count": 42},
        }

        result = await result_service.submit_result(
            task_id=in_progress_task.task_id,
            cluster_id=in_progress_task.cluster_id,
            output=output,
        )

        assert result.result.output == output

    @pytest.mark.asyncio
    async def test_submit_result_unauthorized_cluster_rejected(
        self,
        result_service: TaskResultService,
        task_state_port: MockTaskStatePort,
        in_progress_task: TaskState,
    ) -> None:
        """Only assigned Cluster can submit results (AC9)."""
        task_state_port.add_task(in_progress_task)

        with pytest.raises(UnauthorizedResultError):
            await result_service.submit_result(
                task_id=in_progress_task.task_id,
                cluster_id="wrong-cluster",  # Not the assigned cluster
                output={"completion": "done"},
            )

    @pytest.mark.asyncio
    async def test_submit_result_wrong_state_rejected(
        self,
        result_service: TaskResultService,
        task_state_port: MockTaskStatePort,
    ) -> None:
        """Cannot submit result if task not IN_PROGRESS."""
        # Create task in ACCEPTED state (not IN_PROGRESS)
        task = TaskState.create(
            task_id=uuid4(),
            earl_id="earl-1",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        task = task.with_cluster("cluster-1")
        now = datetime.now(timezone.utc)
        task = task.transition(
            TaskStatus.ACTIVATED, now - timedelta(minutes=50), "system"
        )
        task = task.transition(TaskStatus.ROUTED, now - timedelta(minutes=40), "system")
        task = task.transition(
            TaskStatus.ACCEPTED, now - timedelta(minutes=30), "cluster-1"
        )
        # Not transitioned to IN_PROGRESS

        task_state_port.add_task(task)

        with pytest.raises(InvalidResultStateError):
            await result_service.submit_result(
                task_id=task.task_id,
                cluster_id="cluster-1",
                output={"completion": "done"},
            )

    @pytest.mark.asyncio
    async def test_submit_result_uses_two_phase_emission(
        self,
        result_service: TaskResultService,
        task_state_port: MockTaskStatePort,
        two_phase_emitter: MockTwoPhaseEmitter,
        in_progress_task: TaskState,
    ) -> None:
        """Result submission uses two-phase event emission."""
        task_state_port.add_task(in_progress_task)

        await result_service.submit_result(
            task_id=in_progress_task.task_id,
            cluster_id=in_progress_task.cluster_id,
            output={"completion": "done"},
        )

        # Verify two-phase emission occurred
        assert len(two_phase_emitter.intents) == 1
        assert two_phase_emitter.intents[0]["operation_type"] == "task.result"
        assert len(two_phase_emitter.commits) == 1


class TestSubmitProblemReport:
    """Tests for submit_problem_report() method."""

    @pytest.mark.asyncio
    async def test_submit_problem_report_keeps_in_progress(
        self,
        result_service: TaskResultService,
        task_state_port: MockTaskStatePort,
        in_progress_task: TaskState,
    ) -> None:
        """Problem report does NOT change task state (AC4)."""
        task_state_port.add_task(in_progress_task)

        result = await result_service.submit_problem_report(
            task_id=in_progress_task.task_id,
            cluster_id=in_progress_task.cluster_id,
            category=ProblemCategory.BLOCKED,
            description="External API unavailable",
        )

        assert result.success is True
        # Verify task state is UNCHANGED
        assert result.new_status == "in_progress"

        updated_task = await task_state_port.get_task(in_progress_task.task_id)
        assert updated_task.current_status == TaskStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_submit_problem_report_emits_event(
        self,
        result_service: TaskResultService,
        task_state_port: MockTaskStatePort,
        ledger_port: MockLedgerPort,
        in_progress_task: TaskState,
    ) -> None:
        """Problem report emits executive.task.problem_reported event (AC6)."""
        task_state_port.add_task(in_progress_task)

        await result_service.submit_problem_report(
            task_id=in_progress_task.task_id,
            cluster_id=in_progress_task.cluster_id,
            category=ProblemCategory.UNCLEAR_SPEC,
            description="Task requirements are ambiguous",
        )

        # Verify event was emitted
        assert len(ledger_port.events) == 1
        event = ledger_port.events[0]
        assert event.event_type == "executive.task.problem_reported"
        assert event.payload["category"] == "unclear_spec"
        assert event.payload["description"] == "Task requirements are ambiguous"

    @pytest.mark.asyncio
    async def test_submit_problem_report_captures_category(
        self,
        result_service: TaskResultService,
        task_state_port: MockTaskStatePort,
        in_progress_task: TaskState,
    ) -> None:
        """Problem report captures category (AC8)."""
        task_state_port.add_task(in_progress_task)

        result = await result_service.submit_problem_report(
            task_id=in_progress_task.task_id,
            cluster_id=in_progress_task.cluster_id,
            category=ProblemCategory.RESOURCE_UNAVAILABLE,
            description="Database connection failed",
        )

        # Result should be a ProblemReportValue with correct category
        from src.application.ports.governance.task_result_port import ProblemReportValue

        assert isinstance(result.result, ProblemReportValue)
        assert result.result.category == ProblemCategory.RESOURCE_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_submit_problem_report_captures_description(
        self,
        result_service: TaskResultService,
        task_state_port: MockTaskStatePort,
        in_progress_task: TaskState,
    ) -> None:
        """Problem report captures description (AC8)."""
        task_state_port.add_task(in_progress_task)
        description = "Database connection failed with timeout error after 30 seconds"

        result = await result_service.submit_problem_report(
            task_id=in_progress_task.task_id,
            cluster_id=in_progress_task.cluster_id,
            category=ProblemCategory.TECHNICAL_ISSUE,
            description=description,
        )

        from src.application.ports.governance.task_result_port import ProblemReportValue

        assert isinstance(result.result, ProblemReportValue)
        assert result.result.description == description

    @pytest.mark.asyncio
    async def test_submit_problem_report_unauthorized_cluster_rejected(
        self,
        result_service: TaskResultService,
        task_state_port: MockTaskStatePort,
        in_progress_task: TaskState,
    ) -> None:
        """Only assigned Cluster can submit problem reports (AC9)."""
        task_state_port.add_task(in_progress_task)

        with pytest.raises(UnauthorizedResultError):
            await result_service.submit_problem_report(
                task_id=in_progress_task.task_id,
                cluster_id="wrong-cluster",
                category=ProblemCategory.BLOCKED,
                description="Some issue",
            )

    @pytest.mark.asyncio
    async def test_submit_problem_report_wrong_state_rejected(
        self,
        result_service: TaskResultService,
        task_state_port: MockTaskStatePort,
    ) -> None:
        """Cannot submit problem report if task not IN_PROGRESS."""
        # Create task in ACCEPTED state
        task = TaskState.create(
            task_id=uuid4(),
            earl_id="earl-1",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        task = task.with_cluster("cluster-1")
        now = datetime.now(timezone.utc)
        task = task.transition(
            TaskStatus.ACTIVATED, now - timedelta(minutes=50), "system"
        )
        task = task.transition(TaskStatus.ROUTED, now - timedelta(minutes=40), "system")
        task = task.transition(
            TaskStatus.ACCEPTED, now - timedelta(minutes=30), "cluster-1"
        )

        task_state_port.add_task(task)

        with pytest.raises(InvalidResultStateError):
            await result_service.submit_problem_report(
                task_id=task.task_id,
                cluster_id="cluster-1",
                category=ProblemCategory.BLOCKED,
                description="Some issue",
            )

    @pytest.mark.asyncio
    async def test_submit_problem_report_uses_two_phase_emission(
        self,
        result_service: TaskResultService,
        task_state_port: MockTaskStatePort,
        two_phase_emitter: MockTwoPhaseEmitter,
        in_progress_task: TaskState,
    ) -> None:
        """Problem report uses two-phase event emission."""
        task_state_port.add_task(in_progress_task)

        await result_service.submit_problem_report(
            task_id=in_progress_task.task_id,
            cluster_id=in_progress_task.cluster_id,
            category=ProblemCategory.OTHER,
            description="Miscellaneous issue",
        )

        # Verify two-phase emission occurred
        assert len(two_phase_emitter.intents) == 1
        assert two_phase_emitter.intents[0]["operation_type"] == "task.problem_report"
        assert len(two_phase_emitter.commits) == 1
