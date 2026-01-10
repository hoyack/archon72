# Story 3.9: Witnessed Halt Event Before Stop (RT-2)

## Story

**As an** external observer,
**I want** a halt signal to create a witnessed event BEFORE the system stops,
**So that** the halt itself is part of the auditable record.

## Status

Status: done

## Context

### Business Context
Constitutional crises (fork detection, sequence gaps) require immediate system halt.
For external accountability, the halt itself must be recorded in the event store with
proper witnessing BEFORE the system stops accepting writes. This creates an auditable
record of every halt event.

### Technical Context
- **HaltTriggerService** already creates `ConstitutionalCrisisPayload` and logs it
- The payload has `signable_content()` for witnessing (CT-12 compliance)
- Currently, the event is logged but NOT written to the event store
- Story 3.9 completes the RT-2 requirement by actually persisting the witnessed event

### Dependencies
- Story 1.6 (Event Writer Service) - For writing witnessed events
- Story 3.2 (HaltTriggerService) - Service that orchestrates halt
- Story 3.3 (Dual Channel Halt) - Transport for halt propagation

### Constitutional Constraints
- **RT-2**: All halt signals must create witnessed halt event BEFORE system stops
- **CT-11**: Silent failure destroys legitimacy - halt MUST be logged
- **CT-12**: Witnessing creates accountability - crisis event MUST be witnessed
- **CT-13**: Integrity outranks availability - halt proceeds even if write fails

### Architecture Decision
Per ADR-3 and RT-2:
1. Create ConstitutionalCrisisEvent payload (already done in HaltTriggerService)
2. **NEW**: Write the event to event store with witnessing
3. Trigger halt via dual-channel transport (already done)
4. If event store write fails: halt proceeds anyway (safety over auditability)
5. Recovery mechanism logs unwitnessed halts for later reconciliation

## Acceptance Criteria

### AC1: Halt event written BEFORE halt
**Given** a halt is triggered (fork detection, sequence gap, or manual crisis)
**When** the halt process begins
**Then** a `ConstitutionalCrisisEvent` is written to the event store FIRST
**And** the event is witnessed (has witness_id, witness_signature)
**And** only THEN does the system stop accepting writes

### AC2: Halt event contains required fields
**Given** the halt event
**When** I examine it
**Then** it includes:
  - `crisis_type`: Type of crisis (FORK_DETECTED, SEQUENCE_GAP_DETECTED, etc.)
  - `detection_timestamp`: When the crisis was detected
  - `detection_details`: Human-readable description
  - `triggering_event_ids`: UUIDs of events that triggered the crisis
  - `detecting_service_id`: ID of the detecting service
**And** `witness_signature` is present (CT-12)

### AC3: Safety over auditability
**Given** a scenario where halt event write fails
**When** the system cannot write the halt event (DB unavailable, etc.)
**Then** halt proceeds anyway (CT-13: integrity over availability)
**And** an `UnwitnessedHaltRecord` is created for recovery
**And** the unwitnessed halt is logged at CRITICAL level

### AC4: Recovery mechanism
**Given** an unwitnessed halt occurred
**When** the system recovers
**Then** the `UnwitnessedHaltRecord` can be retrieved
**And** it contains all the crisis payload fields
**And** it can be reconciled into the event store later (manual ceremony)

## Tasks

### Task 1: Create UnwitnessedHaltRecord domain model ✅
Create a domain model to track halts that couldn't be written to the event store.

**Files:**
- `src/domain/models/unwitnessed_halt.py` (new)
- `tests/unit/domain/test_unwitnessed_halt.py` (new)

**Test Cases (RED):**
- `test_unwitnessed_halt_record_creation`
- `test_unwitnessed_halt_record_immutable`
- `test_unwitnessed_halt_record_contains_crisis_payload`
- `test_unwitnessed_halt_record_contains_failure_reason`
- `test_unwitnessed_halt_record_contains_fallback_timestamp`
- `test_unwitnessed_halt_record_signable_content`
- `test_unwitnessed_halt_record_equality`

**Implementation (GREEN):**
```python
@dataclass(frozen=True, eq=True)
class UnwitnessedHaltRecord:
    """Record of halt that couldn't be witnessed.

    When event store write fails during halt, we still proceed
    with halt (CT-13: integrity over availability) but create
    this record for later reconciliation.
    """
    halt_id: UUID
    crisis_payload: ConstitutionalCrisisPayload
    failure_reason: str
    fallback_timestamp: datetime
    detecting_service_id: str

    def signable_content(self) -> bytes:
        """Return canonical bytes for later witnessing."""
        ...
```

### Task 2: Create UnwitnessedHaltRepository port ✅
Port interface for storing/retrieving unwitnessed halt records.

**Files:**
- `src/application/ports/unwitnessed_halt_repository.py` (new)
- `tests/unit/application/test_unwitnessed_halt_repository_port.py` (new)

**Test Cases (RED):**
- `test_port_is_abstract`
- `test_save_method_signature`
- `test_get_all_method_signature`
- `test_get_by_id_method_signature`
- `test_port_is_runtime_checkable`

**Implementation (GREEN):**
```python
@runtime_checkable
class UnwitnessedHaltRepository(Protocol):
    """Repository for unwitnessed halt records."""

    async def save(self, record: UnwitnessedHaltRecord) -> None:
        """Save an unwitnessed halt record."""
        ...

    async def get_all(self) -> list[UnwitnessedHaltRecord]:
        """Get all unwitnessed halt records."""
        ...

    async def get_by_id(self, halt_id: UUID) -> UnwitnessedHaltRecord | None:
        """Get a specific record by halt ID."""
        ...
```

### Task 3: Create UnwitnessedHaltRepositoryStub ✅
Test stub for the repository.

**Files:**
- `src/infrastructure/stubs/unwitnessed_halt_repository_stub.py` (new)
- `tests/unit/infrastructure/test_unwitnessed_halt_repository_stub.py` (new)

**Test Cases (RED):**
- `test_stub_implements_protocol`
- `test_save_stores_record`
- `test_get_all_returns_all_records`
- `test_get_all_returns_empty_when_none`
- `test_get_by_id_returns_record`
- `test_get_by_id_returns_none_when_not_found`
- `test_reset_clears_records`

**Implementation (GREEN):**
```python
class UnwitnessedHaltRepositoryStub(UnwitnessedHaltRepository):
    """In-memory stub for testing."""

    def __init__(self) -> None:
        self._records: dict[UUID, UnwitnessedHaltRecord] = {}

    async def save(self, record: UnwitnessedHaltRecord) -> None:
        self._records[record.halt_id] = record

    # ... other methods
```

### Task 4: Create WitnessedHaltWriter port ✅
Port interface for writing witnessed halt events.

**Files:**
- `src/application/ports/witnessed_halt_writer.py` (new)
- `tests/unit/application/test_witnessed_halt_writer_port.py` (new)

**Test Cases (RED):**
- `test_port_is_abstract`
- `test_write_halt_event_method_signature`
- `test_returns_event_on_success`
- `test_port_is_runtime_checkable`

**Implementation (GREEN):**
```python
@runtime_checkable
class WitnessedHaltWriter(Protocol):
    """Port for writing witnessed halt events.

    This is a specialized writer that can write halt events
    even when the system is about to halt.
    """

    async def write_halt_event(
        self,
        crisis_payload: ConstitutionalCrisisPayload,
    ) -> Event | None:
        """Write a witnessed halt event.

        Returns Event if successful, None if write failed.
        Never raises - failure is handled by caller.
        """
        ...
```

### Task 5: Create WitnessedHaltWriterStub ✅
Test stub that simulates success/failure.

**Files:**
- `src/infrastructure/stubs/witnessed_halt_writer_stub.py` (new)
- `tests/unit/infrastructure/test_witnessed_halt_writer_stub.py` (new)

**Test Cases (RED):**
- `test_stub_implements_protocol`
- `test_write_returns_event_on_success`
- `test_write_returns_none_when_configured_to_fail`
- `test_set_fail_next_configures_failure`
- `test_get_written_events_returns_history`
- `test_reset_clears_state`

**Implementation (GREEN):**
```python
class WitnessedHaltWriterStub(WitnessedHaltWriter):
    """Test stub for witnessed halt writer."""

    def __init__(self) -> None:
        self._fail_next = False
        self._written_events: list[Event] = []

    def set_fail_next(self) -> None:
        """Configure next write to fail."""
        self._fail_next = True

    async def write_halt_event(
        self,
        crisis_payload: ConstitutionalCrisisPayload,
    ) -> Event | None:
        if self._fail_next:
            self._fail_next = False
            return None
        # Create mock event
        ...
```

### Task 6: Extend HaltTriggerService with witnessed halt ✅
Modify HaltTriggerService to write witnessed event before halt.

**Files:**
- `src/application/services/halt_trigger_service.py` (modify)
- `tests/unit/application/test_halt_trigger_service.py` (extend)

**Test Cases (RED):**
- `test_halt_writes_witnessed_event_before_triggering_halt`
- `test_halt_proceeds_when_event_write_fails`
- `test_unwitnessed_halt_record_created_on_failure`
- `test_crisis_event_id_matches_written_event`
- `test_halt_not_triggered_twice_even_with_retry`

**Implementation (GREEN):**
```python
def __init__(
    self,
    *,
    dual_channel_halt: DualChannelHaltTransport | None = None,
    halt_trigger: HaltTrigger | None = None,
    witnessed_halt_writer: WitnessedHaltWriter | None = None,
    unwitnessed_halt_repository: UnwitnessedHaltRepository | None = None,
    service_id: str,
) -> None:
    # ... existing init
    self._witnessed_halt_writer = witnessed_halt_writer
    self._unwitnessed_halt_repository = unwitnessed_halt_repository

async def on_fork_detected(self, fork: ForkDetectedPayload) -> None:
    # ... existing crisis payload creation

    # NEW: Write witnessed event BEFORE halt (RT-2)
    crisis_event = await self._write_witnessed_halt_event(crisis_payload)

    if crisis_event is not None:
        self._crisis_event_id = crisis_event.event_id
    else:
        # Event write failed - create unwitnessed record (AC3)
        await self._create_unwitnessed_halt_record(
            crisis_payload,
            "Event store write failed"
        )
        self._crisis_event_id = uuid4()  # Generate placeholder ID

    # Trigger halt (proceeds regardless of write success)
    await self._write_halt(halt_reason, self._crisis_event_id)
```

### Task 7: Integration tests for witnessed halt flow ✅
End-to-end tests for the full witnessed halt flow.

**Files:**
- `tests/integration/test_witnessed_halt_integration.py` (new)

**Test Cases:**
- `test_fork_creates_witnessed_halt_event_then_halts`
- `test_sequence_gap_creates_witnessed_halt_event_then_halts`
- `test_halt_event_contains_all_required_fields`
- `test_halt_event_is_witnessed`
- `test_halt_proceeds_when_event_store_unavailable`
- `test_unwitnessed_halt_record_created_on_failure`
- `test_halt_event_sequence_is_last_before_halt`
- `test_constitutional_compliance_rt2`
- `test_constitutional_compliance_ct12`

### Task 8: Update __init__.py exports ✅
Update all package __init__.py files.

**Files:**
- `src/domain/models/__init__.py` (modify)
- `src/application/ports/__init__.py` (modify)
- `src/infrastructure/stubs/__init__.py` (modify)

## Technical Notes

### Implementation Order
1. Task 1-3: Domain model and repository (foundation)
2. Task 4-5: Writer port and stub
3. Task 6: Service integration (main feature)
4. Task 7-8: Integration tests and exports

### Testing Strategy
- Unit tests for each component in isolation
- Integration tests for full flow with stubs
- All tests follow red-green-refactor TDD cycle

### Constitutional Compliance Matrix
| Requirement | Implementation |
|-------------|----------------|
| RT-2 | Event written BEFORE halt trigger |
| CT-11 | CRITICAL logging on failure |
| CT-12 | Witness signature on event |
| CT-13 | Halt proceeds even if write fails |

## References

- Epic 3: Halt & Fork Detection
- ADR-3: Partition Behavior + Halt Durability
- Story 3.2: Single Conflict Halt Trigger
- Story 1.6: Event Writer Service
