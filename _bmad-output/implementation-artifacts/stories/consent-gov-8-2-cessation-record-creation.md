# Story consent-gov-8.2: Cessation Record Creation

Status: ready-for-dev

---

## Story

As a **governance system**,
I want **an immutable Cessation Record created on cessation**,
So that **the shutdown is formally documented**.

---

## Acceptance Criteria

1. **AC1:** Immutable Cessation Record created (FR48)
2. **AC2:** Creation is atomic (NFR-REL-05)
3. **AC3:** All records preserved (FR51)
4. **AC4:** In-progress work labeled `interrupted_by_cessation` (FR52)
5. **AC5:** Event `constitutional.cessation.record_created` emitted
6. **AC6:** Cessation Record contains complete system snapshot
7. **AC7:** Record is append-only (no modification after creation)
8. **AC8:** Unit tests for record creation

---

## Tasks / Subtasks

- [ ] **Task 1: Create CessationRecord domain model** (AC: 1, 7)
  - [ ] Create `src/domain/governance/cessation/cessation_record.py`
  - [ ] Include trigger reference, created_at
  - [ ] Include final ledger hash
  - [ ] Include system snapshot
  - [ ] Immutable value object

- [ ] **Task 2: Create CessationRecordService** (AC: 1, 2, 5)
  - [ ] Create `src/application/services/governance/cessation_record_service.py`
  - [ ] Create record atomically
  - [ ] Emit `constitutional.cessation.record_created`
  - [ ] Coordinate with snapshot collection

- [ ] **Task 3: Create CessationRecordPort interface** (AC: 1, 7)
  - [ ] Create port for record operations
  - [ ] Define `create_record()` method (atomic)
  - [ ] Define `get_record()` method
  - [ ] NO modify/delete methods (immutable)

- [ ] **Task 4: Implement atomic creation** (AC: 2)
  - [ ] Transaction wraps entire creation
  - [ ] Partial creation fails entirely
  - [ ] All-or-nothing semantics
  - [ ] No partial cessation state

- [ ] **Task 5: Implement record preservation** (AC: 3)
  - [ ] Final ledger hash captured
  - [ ] All events preserved
  - [ ] Hash chain integrity verified
  - [ ] No data loss

- [ ] **Task 6: Implement interrupted work labeling** (AC: 4)
  - [ ] Query all in-progress work
  - [ ] Label each with `interrupted_by_cessation`
  - [ ] Include cessation_record_id reference
  - [ ] Emit events for each labeled item

- [ ] **Task 7: Implement system snapshot** (AC: 6)
  - [ ] Capture active tasks count
  - [ ] Capture pending motions count
  - [ ] Capture legitimacy band state
  - [ ] Capture component statuses

- [ ] **Task 8: Write comprehensive unit tests** (AC: 8)
  - [ ] Test record created successfully
  - [ ] Test atomic creation (partial fails)
  - [ ] Test records preserved
  - [ ] Test interrupted work labeled
  - [ ] Test event emitted

---

## Documentation Checklist

- [ ] Architecture docs updated (cessation record structure)
- [ ] Operations runbook for record verification
- [ ] Inline comments explaining atomicity
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Cessation Record Purpose:**
```
The Cessation Record is the final historical document:
  - Proves cessation happened properly
  - Contains complete system state at cessation
  - Immutable once created
  - Cannot be modified, only created once

Contents:
  - Trigger reference (who, when, why)
  - Final ledger hash (proof of state)
  - System snapshot (counts, statuses)
  - Interrupted work list (with labels)
  - Timestamp (exact cessation moment)
```

**Why Atomic Creation?**
```
NFR-REL-05: Cessation Record creation is atomic

Partial cessation is dangerous:
  - System half-stopped is worse than running or stopped
  - Data could be corrupted
  - Recovery impossible
  - Trust destroyed

Atomic guarantees:
  - Either complete record created OR
  - Nothing changed (can retry)
  - No in-between state
  - Clean final state
```

**Interrupted Work Labeling:**
```
FR52: In-progress work labeled `interrupted_by_cessation`

Why label?
  - Distinguishes from normal completion
  - Explains why work didn't finish
  - Audit trail for human participants
  - No silent abandonment

Label includes:
  - cessation_record_id: Links to cessation
  - interrupted_at: When interruption occurred
  - previous_state: What state it was in
  - Any partial results preserved
```

### Domain Models

```python
@dataclass(frozen=True)
class SystemSnapshot:
    """Snapshot of system state at cessation."""
    active_tasks: int
    pending_motions: int
    in_progress_executions: int
    legitimacy_band: str
    component_statuses: dict[str, str]
    captured_at: datetime


@dataclass(frozen=True)
class InterruptedWork:
    """Record of work interrupted by cessation."""
    work_id: UUID
    work_type: str  # "task", "motion", "execution"
    previous_state: str
    interrupted_at: datetime
    cessation_record_id: UUID


@dataclass(frozen=True)
class CessationRecord:
    """Immutable record of system cessation.

    Created atomically. Cannot be modified after creation.
    This is the final historical document for this system instance.
    """
    record_id: UUID
    trigger_id: UUID
    operator_id: UUID
    created_at: datetime
    final_ledger_hash: str
    final_sequence_number: int
    system_snapshot: SystemSnapshot
    interrupted_work_ids: list[UUID]
    reason: str

    # Explicitly NOT included (immutable):
    # - modified_at: datetime
    # - updated_by: UUID
    # - cancelled: bool


class CessationRecordCreationError(ValueError):
    """Raised when cessation record creation fails."""
    pass


class CessationRecordAlreadyExistsError(ValueError):
    """Raised when attempting to create second cessation record."""
    pass
```

### Service Implementation Sketch

```python
class CessationRecordService:
    """Creates immutable Cessation Record.

    Creation is ATOMIC (NFR-REL-05).
    NO modify/delete methods exist.
    """

    def __init__(
        self,
        cessation_record_port: CessationRecordPort,
        ledger_port: LedgerPort,
        task_state_port: TaskStatePort,
        motion_port: MotionPort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ):
        self._records = cessation_record_port
        self._ledger = ledger_port
        self._tasks = task_state_port
        self._motions = motion_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def create_record(
        self,
        trigger: CessationTrigger,
    ) -> CessationRecord:
        """Create immutable Cessation Record.

        This operation is ATOMIC:
          - Either complete record is created
          - Or nothing is changed (fails entirely)

        Args:
            trigger: The cessation trigger that initiated this

        Returns:
            CessationRecord (immutable)

        Raises:
            CessationRecordCreationError: If creation fails
            CessationRecordAlreadyExistsError: If record already exists
        """
        now = self._time.now()

        # Check no existing record
        existing = await self._records.get_record()
        if existing is not None:
            raise CessationRecordAlreadyExistsError(
                f"Cessation record already exists: {existing.record_id}"
            )

        # Collect system snapshot
        snapshot = await self._collect_snapshot(now)

        # Get final ledger state
        final_hash, final_seq = await self._ledger.get_final_state()

        # Label interrupted work
        interrupted_ids = await self._label_interrupted_work(
            record_id=record_id := uuid4(),
            timestamp=now,
        )

        # Create record
        record = CessationRecord(
            record_id=record_id,
            trigger_id=trigger.trigger_id,
            operator_id=trigger.operator_id,
            created_at=now,
            final_ledger_hash=final_hash,
            final_sequence_number=final_seq,
            system_snapshot=snapshot,
            interrupted_work_ids=interrupted_ids,
            reason=trigger.reason,
        )

        # Atomic creation
        try:
            await self._records.create_record_atomic(record)
        except Exception as e:
            raise CessationRecordCreationError(
                f"Failed to create cessation record: {e}"
            ) from e

        # Emit created event
        await self._event_emitter.emit(
            event_type="constitutional.cessation.record_created",
            actor="system",
            payload={
                "record_id": str(record.record_id),
                "trigger_id": str(trigger.trigger_id),
                "operator_id": str(trigger.operator_id),
                "created_at": now.isoformat(),
                "final_ledger_hash": final_hash,
                "final_sequence_number": final_seq,
                "interrupted_work_count": len(interrupted_ids),
            },
        )

        return record

    async def _collect_snapshot(
        self,
        timestamp: datetime,
    ) -> SystemSnapshot:
        """Collect system state snapshot."""
        return SystemSnapshot(
            active_tasks=await self._tasks.count_active(),
            pending_motions=await self._motions.count_pending(),
            in_progress_executions=await self._tasks.count_in_progress(),
            legitimacy_band=await self._get_legitimacy_band(),
            component_statuses=await self._get_component_statuses(),
            captured_at=timestamp,
        )

    async def _label_interrupted_work(
        self,
        record_id: UUID,
        timestamp: datetime,
    ) -> list[UUID]:
        """Label all in-progress work as interrupted."""
        interrupted_ids = []

        # Get all in-progress work
        in_progress = await self._tasks.get_in_progress()

        for work in in_progress:
            await self._tasks.label_interrupted(
                work_id=work.id,
                cessation_record_id=record_id,
                interrupted_at=timestamp,
            )
            interrupted_ids.append(work.id)

            await self._event_emitter.emit(
                event_type="executive.work.interrupted_by_cessation",
                actor="system",
                payload={
                    "work_id": str(work.id),
                    "previous_state": work.status.value,
                    "cessation_record_id": str(record_id),
                    "interrupted_at": timestamp.isoformat(),
                },
            )

        return interrupted_ids

    # These methods intentionally do not exist:
    # async def update_record(self, ...): ...
    # async def delete_record(self, ...): ...
    # async def modify_record(self, ...): ...


class CessationRecordPort(Protocol):
    """Port for cessation record operations.

    NO modify/delete methods (immutable record).
    """

    async def create_record_atomic(
        self,
        record: CessationRecord,
    ) -> None:
        """Create cessation record atomically.

        All-or-nothing: either complete or fails entirely.
        """
        ...

    async def get_record(self) -> CessationRecord | None:
        """Get cessation record if exists."""
        ...

    # Intentionally NOT defined:
    # - update_record()
    # - delete_record()
    # - modify_record()
```

### Event Patterns

```python
# Cessation record created
{
    "event_type": "constitutional.cessation.record_created",
    "actor": "system",
    "payload": {
        "record_id": "uuid",
        "trigger_id": "uuid",
        "operator_id": "uuid",
        "created_at": "2026-01-16T00:00:00Z",
        "final_ledger_hash": "sha256:abc123...",
        "final_sequence_number": 12345,
        "interrupted_work_count": 3
    }
}

# Work interrupted by cessation
{
    "event_type": "executive.work.interrupted_by_cessation",
    "actor": "system",
    "payload": {
        "work_id": "uuid",
        "previous_state": "in_progress",
        "cessation_record_id": "uuid",
        "interrupted_at": "2026-01-16T00:00:00Z"
    }
}
```

### Test Patterns

```python
class TestCessationRecordService:
    """Unit tests for cessation record service."""

    async def test_record_created_successfully(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
    ):
        """Cessation record is created successfully."""
        record = await record_service.create_record(
            trigger=cessation_trigger,
        )

        assert record.trigger_id == cessation_trigger.trigger_id
        assert record.final_ledger_hash is not None

    async def test_creation_is_atomic(
        self,
        record_service: CessationRecordService,
        failing_port: FakeCessationRecordPort,
        cessation_trigger: CessationTrigger,
    ):
        """Record creation fails atomically on error."""
        failing_port.fail_on_create = True

        with pytest.raises(CessationRecordCreationError):
            await record_service.create_record(
                trigger=cessation_trigger,
            )

        # Verify nothing was created
        record = await failing_port.get_record()
        assert record is None

    async def test_records_preserved(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
    ):
        """Final ledger hash is captured in record."""
        record = await record_service.create_record(
            trigger=cessation_trigger,
        )

        assert record.final_ledger_hash is not None
        assert record.final_sequence_number > 0

    async def test_interrupted_work_labeled(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
        task_with_in_progress_work,
        task_state_port: FakeTaskStatePort,
    ):
        """In-progress work is labeled as interrupted."""
        record = await record_service.create_record(
            trigger=cessation_trigger,
        )

        # Check work was labeled
        work = await task_state_port.get_work(
            task_with_in_progress_work.id
        )
        assert work.label == "interrupted_by_cessation"
        assert work.cessation_record_id == record.record_id

    async def test_record_created_event_emitted(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
        event_capture: EventCapture,
    ):
        """Created event is emitted."""
        await record_service.create_record(
            trigger=cessation_trigger,
        )

        event = event_capture.get_last("constitutional.cessation.record_created")
        assert event is not None

    async def test_cannot_create_second_record(
        self,
        record_service: CessationRecordService,
        cessation_trigger: CessationTrigger,
    ):
        """Cannot create second cessation record."""
        await record_service.create_record(
            trigger=cessation_trigger,
        )

        with pytest.raises(CessationRecordAlreadyExistsError):
            await record_service.create_record(
                trigger=cessation_trigger,
            )


class TestCessationRecordImmutability:
    """Tests ensuring cessation record is immutable."""

    def test_no_update_method(
        self,
        record_service: CessationRecordService,
    ):
        """No update method exists."""
        assert not hasattr(record_service, "update_record")
        assert not hasattr(record_service, "modify_record")

    def test_no_delete_method(
        self,
        record_service: CessationRecordService,
    ):
        """No delete method exists."""
        assert not hasattr(record_service, "delete_record")
        assert not hasattr(record_service, "remove_record")

    def test_record_is_frozen(self):
        """CessationRecord is frozen dataclass."""
        assert CessationRecord.__dataclass_fields__
        # Frozen dataclass cannot be modified after creation
```

### Dependencies

- **Depends on:** consent-gov-8-1 (cessation trigger)
- **Enables:** consent-gov-8-3 (reconstitution validation)

### References

- FR48: System can create immutable Cessation Record on cessation
- FR51: System can preserve all records on cessation
- FR52: System can label in-progress work as `interrupted_by_cessation`
- NFR-REL-05: Cessation Record creation is atomic; partial cessation is impossible
