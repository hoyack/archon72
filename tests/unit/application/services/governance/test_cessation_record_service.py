"""Unit tests for CessationRecordService.

Story: consent-gov-8.2: Cessation Record Creation

Tests for the service that creates immutable Cessation Records
when the governance system ceases.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.application.services.governance.cessation_record_service import (
    CessationRecordService,
)
from src.domain.governance.cessation import (
    CessationRecord,
    CessationRecordAlreadyExistsError,
    CessationRecordCreationError,
    CessationTrigger,
    InterruptedWork,
    SystemSnapshot,
)


class FakeCessationRecordPort:
    """Fake implementation of CessationRecordPort for testing."""

    def __init__(self) -> None:
        self.record: CessationRecord | None = None
        self.fail_on_create: bool = False
        self.create_called: bool = False

    async def create_record_atomic(self, record: CessationRecord) -> None:
        """Create cessation record atomically."""
        self.create_called = True
        if self.fail_on_create:
            raise RuntimeError("Simulated creation failure")
        if self.record is not None:
            raise CessationRecordAlreadyExistsError(
                existing_record_id=self.record.record_id,
            )
        self.record = record

    async def get_record(self) -> CessationRecord | None:
        """Get cessation record if exists."""
        return self.record


class FakeLedgerPort:
    """Fake implementation for ledger operations."""

    def __init__(
        self,
        final_hash: str = "sha256:test123",
        final_seq: int = 12345,
    ) -> None:
        self.final_hash = final_hash
        self.final_seq = final_seq

    async def get_final_state(self) -> tuple[str, int]:
        """Get final ledger hash and sequence."""
        return self.final_hash, self.final_seq


class FakeInProgressWorkPort:
    """Fake implementation for in-progress work queries."""

    def __init__(self) -> None:
        self.in_progress_work: list[dict] = []
        self.labeled_work: list[InterruptedWork] = []

    async def get_in_progress(self) -> list[dict]:
        """Get all in-progress work items."""
        return self.in_progress_work

    async def label_interrupted(
        self,
        work_id: UUID,
        cessation_record_id: UUID,
        interrupted_at: datetime,
        previous_state: str,
        work_type: str,
    ) -> InterruptedWork:
        """Label work as interrupted by cessation."""
        work = InterruptedWork(
            work_id=work_id,
            work_type=work_type,
            previous_state=previous_state,
            interrupted_at=interrupted_at,
            cessation_record_id=cessation_record_id,
        )
        self.labeled_work.append(work)
        return work

    async def count_active(self) -> int:
        """Count active tasks."""
        return sum(1 for w in self.in_progress_work if w.get("type") == "task")

    async def count_in_progress(self) -> int:
        """Count in-progress executions."""
        return len(self.in_progress_work)


class FakeMotionPort:
    """Fake implementation for motion queries."""

    def __init__(self, pending_count: int = 0) -> None:
        self.pending_count = pending_count

    async def count_pending(self) -> int:
        """Count pending motions."""
        return self.pending_count


class FakeEventEmitter:
    """Fake implementation for event emission."""

    def __init__(self) -> None:
        self.events: list[dict] = []
        self.intents: list[dict] = []
        self.commits: list[dict] = []
        self.failures: list[dict] = []
        self._correlation_counter: int = 0

    async def emit_intent(
        self,
        operation_type: str,
        actor_id: str,
        target_entity_id: str,
        intent_payload: dict,
    ) -> str:
        """Emit intent event and return correlation ID."""
        self._correlation_counter += 1
        correlation_id = f"corr-{self._correlation_counter}"
        self.intents.append(
            {
                "correlation_id": correlation_id,
                "operation_type": operation_type,
                "actor_id": actor_id,
                "target_entity_id": target_entity_id,
                "payload": intent_payload,
            }
        )
        return correlation_id

    async def emit_commit(
        self,
        correlation_id: str,
        outcome_payload: dict,
    ) -> None:
        """Emit commit event."""
        self.commits.append(
            {
                "correlation_id": correlation_id,
                "payload": outcome_payload,
            }
        )

    async def emit_failure(
        self,
        correlation_id: str,
        failure_reason: str,
        failure_details: dict,
    ) -> None:
        """Emit failure event."""
        self.failures.append(
            {
                "correlation_id": correlation_id,
                "reason": failure_reason,
                "details": failure_details,
            }
        )


class FakeTimeAuthority:
    """Fake implementation of TimeAuthority."""

    def __init__(self, fixed_time: datetime | None = None) -> None:
        self._fixed_time = fixed_time or datetime.now(timezone.utc)

    def utcnow(self) -> datetime:
        """Return fixed time."""
        return self._fixed_time


class FakeLegitimacyPort:
    """Fake implementation for legitimacy queries."""

    def __init__(self, band: str = "BASELINE") -> None:
        self.band = band

    async def get_current_band(self) -> str:
        """Get current legitimacy band."""
        return self.band


class FakeComponentStatusPort:
    """Fake implementation for component status queries."""

    def __init__(self, statuses: dict[str, str] | None = None) -> None:
        self.statuses = statuses or {"default": "healthy"}

    async def get_all_statuses(self) -> dict[str, str]:
        """Get all component statuses."""
        return self.statuses


@pytest.fixture
def cessation_trigger() -> CessationTrigger:
    """Create a test cessation trigger."""
    return CessationTrigger(
        trigger_id=uuid4(),
        operator_id=uuid4(),
        triggered_at=datetime.now(timezone.utc),
        reason="Test cessation",
    )


@pytest.fixture
def record_port() -> FakeCessationRecordPort:
    """Create a fake record port."""
    return FakeCessationRecordPort()


@pytest.fixture
def ledger_port() -> FakeLedgerPort:
    """Create a fake ledger port."""
    return FakeLedgerPort()


@pytest.fixture
def work_port() -> FakeInProgressWorkPort:
    """Create a fake work port."""
    return FakeInProgressWorkPort()


@pytest.fixture
def motion_port() -> FakeMotionPort:
    """Create a fake motion port."""
    return FakeMotionPort()


@pytest.fixture
def event_emitter() -> FakeEventEmitter:
    """Create a fake event emitter."""
    return FakeEventEmitter()


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    """Create a fake time authority."""
    return FakeTimeAuthority()


@pytest.fixture
def legitimacy_port() -> FakeLegitimacyPort:
    """Create a fake legitimacy port."""
    return FakeLegitimacyPort()


@pytest.fixture
def component_status_port() -> FakeComponentStatusPort:
    """Create a fake component status port."""
    return FakeComponentStatusPort()


@pytest.fixture
def record_service(
    record_port: FakeCessationRecordPort,
    ledger_port: FakeLedgerPort,
    work_port: FakeInProgressWorkPort,
    motion_port: FakeMotionPort,
    event_emitter: FakeEventEmitter,
    time_authority: FakeTimeAuthority,
    legitimacy_port: FakeLegitimacyPort,
    component_status_port: FakeComponentStatusPort,
) -> CessationRecordService:
    """Create the cessation record service with fakes."""
    return CessationRecordService(
        cessation_record_port=record_port,
        ledger_port=ledger_port,
        work_port=work_port,
        motion_port=motion_port,
        event_emitter=event_emitter,
        time_authority=time_authority,
        legitimacy_port=legitimacy_port,
        component_status_port=component_status_port,
    )


class TestCessationRecordCreation:
    """Tests for cessation record creation (AC1, AC6)."""

    async def test_record_created_successfully(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
        record_port: FakeCessationRecordPort,
    ) -> None:
        """Cessation record is created successfully (AC1)."""
        record = await record_service.create_record(trigger=cessation_trigger)

        assert record is not None
        assert record.trigger_id == cessation_trigger.trigger_id
        assert record.operator_id == cessation_trigger.operator_id
        assert record.reason == cessation_trigger.reason
        assert record_port.create_called

    async def test_record_contains_trigger_reference(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
    ) -> None:
        """Record contains reference to the cessation trigger."""
        record = await record_service.create_record(trigger=cessation_trigger)

        assert record.trigger_id == cessation_trigger.trigger_id

    async def test_record_contains_system_snapshot(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
    ) -> None:
        """Record contains complete system snapshot (AC6)."""
        record = await record_service.create_record(trigger=cessation_trigger)

        assert record.system_snapshot is not None
        assert isinstance(record.system_snapshot, SystemSnapshot)
        assert record.system_snapshot.captured_at is not None


class TestAtomicCreation:
    """Tests for atomic record creation (AC2)."""

    async def test_creation_is_atomic_on_success(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
        record_port: FakeCessationRecordPort,
    ) -> None:
        """Record creation completes atomically on success (AC2)."""
        record = await record_service.create_record(trigger=cessation_trigger)

        assert record is not None
        assert record_port.record == record

    async def test_creation_fails_atomically(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
        record_port: FakeCessationRecordPort,
    ) -> None:
        """Record creation fails atomically on error (AC2)."""
        record_port.fail_on_create = True

        with pytest.raises(CessationRecordCreationError):
            await record_service.create_record(trigger=cessation_trigger)

        # Verify nothing was created
        assert record_port.record is None

    async def test_cannot_create_second_record(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
    ) -> None:
        """Cannot create second cessation record."""
        await record_service.create_record(trigger=cessation_trigger)

        with pytest.raises(CessationRecordAlreadyExistsError):
            await record_service.create_record(trigger=cessation_trigger)


class TestRecordPreservation:
    """Tests for record preservation (AC3)."""

    async def test_final_ledger_hash_captured(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
        ledger_port: FakeLedgerPort,
    ) -> None:
        """Final ledger hash is captured in record (AC3)."""
        ledger_port.final_hash = "sha256:final_hash_value"
        ledger_port.final_seq = 99999

        record = await record_service.create_record(trigger=cessation_trigger)

        assert record.final_ledger_hash == "sha256:final_hash_value"
        assert record.final_sequence_number == 99999

    async def test_all_events_preserved(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
    ) -> None:
        """All events are preserved in the final ledger state (AC3)."""
        record = await record_service.create_record(trigger=cessation_trigger)

        # The final hash is proof that all events are preserved
        assert record.final_ledger_hash is not None
        assert record.final_sequence_number > 0


class TestInterruptedWorkLabeling:
    """Tests for interrupted work labeling (AC4)."""

    async def test_in_progress_work_labeled(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
        work_port: FakeInProgressWorkPort,
    ) -> None:
        """In-progress work is labeled as interrupted (AC4)."""
        work_id = uuid4()
        work_port.in_progress_work = [
            {"id": work_id, "type": "task", "state": "in_progress"},
        ]

        record = await record_service.create_record(trigger=cessation_trigger)

        assert len(work_port.labeled_work) == 1
        assert work_port.labeled_work[0].work_id == work_id
        assert work_id in record.interrupted_work_ids

    async def test_multiple_work_items_labeled(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
        work_port: FakeInProgressWorkPort,
    ) -> None:
        """Multiple in-progress work items are all labeled."""
        work_ids = [uuid4(), uuid4(), uuid4()]
        work_port.in_progress_work = [
            {"id": work_ids[0], "type": "task", "state": "in_progress"},
            {"id": work_ids[1], "type": "motion", "state": "pending"},
            {"id": work_ids[2], "type": "execution", "state": "running"},
        ]

        record = await record_service.create_record(trigger=cessation_trigger)

        assert len(work_port.labeled_work) == 3
        assert len(record.interrupted_work_ids) == 3

    async def test_interrupted_work_has_cessation_record_reference(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
        work_port: FakeInProgressWorkPort,
    ) -> None:
        """Interrupted work has cessation_record_id reference."""
        work_id = uuid4()
        work_port.in_progress_work = [
            {"id": work_id, "type": "task", "state": "in_progress"},
        ]

        record = await record_service.create_record(trigger=cessation_trigger)

        labeled = work_port.labeled_work[0]
        assert labeled.cessation_record_id == record.record_id


class TestEventEmission:
    """Tests for event emission (AC5)."""

    async def test_record_created_event_emitted(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Event constitutional.cessation.record_created is emitted (AC5)."""
        await record_service.create_record(trigger=cessation_trigger)

        # Check for intent event
        assert len(event_emitter.intents) == 1
        intent = event_emitter.intents[0]
        assert intent["operation_type"] == "constitutional.cessation.record_created"

        # Check for commit event
        assert len(event_emitter.commits) == 1

    async def test_failure_event_emitted_on_error(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
        record_port: FakeCessationRecordPort,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Failure event is emitted when creation fails."""
        record_port.fail_on_create = True

        with pytest.raises(CessationRecordCreationError):
            await record_service.create_record(trigger=cessation_trigger)

        # Check for failure event
        assert len(event_emitter.failures) == 1

    async def test_event_contains_record_details(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Emitted event contains record details."""
        await record_service.create_record(trigger=cessation_trigger)

        intent = event_emitter.intents[0]
        assert intent["payload"]["trigger_id"] == str(cessation_trigger.trigger_id)
        assert intent["payload"]["operator_id"] == str(cessation_trigger.operator_id)


class TestSystemSnapshot:
    """Tests for system snapshot capture (AC6)."""

    async def test_snapshot_captures_active_tasks(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
        work_port: FakeInProgressWorkPort,
    ) -> None:
        """Snapshot captures active tasks count (AC6)."""
        work_port.in_progress_work = [
            {"id": uuid4(), "type": "task", "state": "in_progress"},
            {"id": uuid4(), "type": "task", "state": "in_progress"},
        ]

        record = await record_service.create_record(trigger=cessation_trigger)

        assert record.system_snapshot.active_tasks == 2

    async def test_snapshot_captures_pending_motions(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
        motion_port: FakeMotionPort,
    ) -> None:
        """Snapshot captures pending motions count (AC6)."""
        motion_port.pending_count = 5

        record = await record_service.create_record(trigger=cessation_trigger)

        assert record.system_snapshot.pending_motions == 5

    async def test_snapshot_captures_legitimacy_band(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
        legitimacy_port: FakeLegitimacyPort,
    ) -> None:
        """Snapshot captures legitimacy band (AC6)."""
        legitimacy_port.band = "ELEVATED"

        record = await record_service.create_record(trigger=cessation_trigger)

        assert record.system_snapshot.legitimacy_band == "ELEVATED"

    async def test_snapshot_captures_component_statuses(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
        component_status_port: FakeComponentStatusPort,
    ) -> None:
        """Snapshot captures component statuses (AC6)."""
        component_status_port.statuses = {
            "king_service": "healthy",
            "president_service": "degraded",
        }

        record = await record_service.create_record(trigger=cessation_trigger)

        assert record.system_snapshot.component_statuses["king_service"] == "healthy"
        assert (
            record.system_snapshot.component_statuses["president_service"] == "degraded"
        )


class TestRecordImmutability:
    """Tests for record immutability (AC7)."""

    def test_no_update_method(
        self,
        record_service: CessationRecordService,
    ) -> None:
        """No update method exists (AC7)."""
        assert not hasattr(record_service, "update_record")
        assert not hasattr(record_service, "modify_record")

    def test_no_delete_method(
        self,
        record_service: CessationRecordService,
    ) -> None:
        """No delete method exists (AC7)."""
        assert not hasattr(record_service, "delete_record")
        assert not hasattr(record_service, "remove_record")


class TestGetRecord:
    """Tests for retrieving the cessation record."""

    async def test_get_record_returns_none_before_creation(
        self,
        record_service: CessationRecordService,
    ) -> None:
        """get_record returns None before creation."""
        record = await record_service.get_record()

        assert record is None

    async def test_get_record_returns_record_after_creation(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
    ) -> None:
        """get_record returns record after creation."""
        created = await record_service.create_record(trigger=cessation_trigger)
        retrieved = await record_service.get_record()

        assert retrieved is not None
        assert retrieved.record_id == created.record_id
