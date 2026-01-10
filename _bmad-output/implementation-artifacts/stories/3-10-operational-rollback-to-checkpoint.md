# Story 3.10: Operational Rollback to Checkpoint (FR111-FR113, FR143)

## Story

**As a** system operator,
**I want** the ability to rollback to a checkpoint anchor during recovery,
**So that** I can restore to a known-good state.

## Status

Status: done

## Context

### Business Context
During a constitutional crisis (fork detection, halt), operators need the ability to rollback the event store to a known-good checkpoint. This is NOT about undoing constitutional history - it's about restoring infrastructure state to a checkpoint anchor. The rollback is itself a constitutional event that must be witnessed and recorded.

Key distinction per FR143 and FR104:
- **Infrastructure rollback**: Restores state to checkpoint (this story)
- **Fork recovery**: Constitutional process with 48-hour wait (Story 3.6)

Checkpoints are periodic anchors (FR137 - minimum weekly) that provide trusted points for:
1. Observer verification (light verification via Merkle paths)
2. Operational recovery (this story)
3. Audit/compliance snapshots

### Technical Context
- **ADR-3**: Partition Behavior + Halt Durability governs rollback during recovery
- **ADR-8**: Genesis Anchor + RFC 3161 checkpointing for timestamp authority
- **Story 3.6**: RecoveryCoordinator exists for 48-hour recovery waiting period
- **Epic 4 (Story 4.6)**: Will add Merkle paths and weekly checkpoint creation
- **This story focuses on**: Query, select, and execute rollback to checkpoints

### Dependencies
- **Story 1.1**: Event store schema with sequence numbers
- **Story 3.5**: Read-only access during halt
- **Story 3.6**: RecoveryCoordinator for recovery orchestration
- **Epic 4 will depend on this**: Checkpoint query API

### Constitutional Constraints
- **FR111**: Detect partitions within 2 minutes - rollback needs fencing
- **FR112**: Single-writer lease/fencing token - rollback must respect this
- **FR113**: Conflicting heads = halt + fork recovery - rollback is NOT fork resolution
- **FR143**: Rollback to checkpoint for infrastructure recovery; logged; does not undo canonical events
- **CT-11**: Silent failure destroys legitimacy - rollback MUST be witnessed
- **CT-13**: Integrity outranks availability - safety over speed

### Architecture Decision
Per ADR-3 and FR143:
1. Checkpoints are trusted anchors with: checkpoint_id, event_sequence, timestamp, anchor_hash
2. Rollback marks events after checkpoint as "orphaned" (NOT deleted - PREVENT_DELETE)
3. HEAD pointer moves to checkpoint sequence
4. RollbackTargetSelectedEvent records Keeper selection
5. RollbackCompletedEvent records successful rollback
6. All events remain queryable with `include_orphaned=true` flag

## Acceptance Criteria

### AC1: Query available checkpoints
**Given** checkpoint anchors exist
**When** I query available checkpoints
**Then** I receive a list with: checkpoint_id, event_sequence, timestamp, anchor_hash

### AC2: Record rollback target selection
**Given** a recovery is in progress
**When** Keepers select a checkpoint for rollback
**Then** the selection is recorded
**And** a `RollbackTargetSelectedEvent` is created

### AC3: Execute rollback
**Given** a rollback is executed
**When** the process completes
**Then** the event store HEAD points to the checkpoint
**And** all events after the checkpoint are marked as "orphaned" (not deleted, but excluded)
**And** a `RollbackCompletedEvent` is created

## Tasks

### Task 1: Create Checkpoint domain model
Create immutable domain model representing a checkpoint anchor.

**Files:**
- `src/domain/models/checkpoint.py` (new)
- `tests/unit/domain/test_checkpoint.py` (new)

**Test Cases (RED):**
- `test_checkpoint_creation_with_required_fields`
- `test_checkpoint_immutable`
- `test_checkpoint_id_is_uuid`
- `test_checkpoint_event_sequence_positive`
- `test_checkpoint_anchor_hash_format`
- `test_checkpoint_equality`
- `test_checkpoint_signable_content`

**Implementation (GREEN):**
```python
@dataclass(frozen=True, eq=True)
class Checkpoint:
    """Checkpoint anchor for recovery and verification.

    Checkpoints are periodic anchors (FR137) that provide trusted
    points for operational recovery and observer verification.

    Per FR143: Rollback to checkpoint restores infrastructure state,
    not constitutional history.
    """
    checkpoint_id: UUID
    event_sequence: int  # Sequence number at checkpoint
    timestamp: datetime
    anchor_hash: str  # Hash at this point in chain
    anchor_type: str  # "genesis" | "periodic" | "manual"
    creator_id: str  # Service/operator that created checkpoint

    def signable_content(self) -> bytes:
        """Return canonical bytes for signing."""
        ...
```

### Task 2: Create CheckpointRepository port
Port interface for querying and storing checkpoints.

**Files:**
- `src/application/ports/checkpoint_repository.py` (new)
- `tests/unit/application/test_checkpoint_repository_port.py` (new)

**Test Cases (RED):**
- `test_port_is_abstract`
- `test_get_all_checkpoints_method_signature`
- `test_get_checkpoint_by_id_method_signature`
- `test_get_latest_checkpoint_method_signature`
- `test_get_checkpoints_after_sequence_method_signature`
- `test_create_checkpoint_method_signature`
- `test_port_is_runtime_checkable`

**Implementation (GREEN):**
```python
@runtime_checkable
class CheckpointRepository(Protocol):
    """Repository for checkpoint anchors (FR137, FR143)."""

    async def get_all_checkpoints(self) -> list[Checkpoint]:
        """Get all available checkpoints ordered by sequence."""
        ...

    async def get_checkpoint_by_id(
        self, checkpoint_id: UUID
    ) -> Checkpoint | None:
        """Get specific checkpoint by ID."""
        ...

    async def get_latest_checkpoint(self) -> Checkpoint | None:
        """Get most recent checkpoint."""
        ...

    async def get_checkpoints_after_sequence(
        self, sequence: int
    ) -> list[Checkpoint]:
        """Get checkpoints after given sequence (for rollback options)."""
        ...

    async def create_checkpoint(
        self,
        event_sequence: int,
        anchor_hash: str,
        anchor_type: str,
        creator_id: str,
    ) -> Checkpoint:
        """Create a new checkpoint anchor."""
        ...
```

### Task 3: Create CheckpointRepositoryStub
Test stub for checkpoint repository.

**Files:**
- `src/infrastructure/stubs/checkpoint_repository_stub.py` (new)
- `tests/unit/infrastructure/test_checkpoint_repository_stub.py` (new)

**Test Cases (RED):**
- `test_stub_implements_protocol`
- `test_get_all_returns_all_checkpoints`
- `test_get_all_returns_empty_when_none`
- `test_get_by_id_returns_checkpoint`
- `test_get_by_id_returns_none_when_not_found`
- `test_get_latest_returns_most_recent`
- `test_get_latest_returns_none_when_empty`
- `test_get_after_sequence_filters_correctly`
- `test_create_checkpoint_stores_and_returns`
- `test_seed_checkpoints_for_testing`
- `test_reset_clears_all`

**Implementation (GREEN):**
```python
class CheckpointRepositoryStub(CheckpointRepository):
    """In-memory stub for testing."""

    def __init__(self) -> None:
        self._checkpoints: dict[UUID, Checkpoint] = {}

    def seed_checkpoints(self, checkpoints: list[Checkpoint]) -> None:
        """Seed test data."""
        for cp in checkpoints:
            self._checkpoints[cp.checkpoint_id] = cp

    async def get_all_checkpoints(self) -> list[Checkpoint]:
        return sorted(
            self._checkpoints.values(),
            key=lambda c: c.event_sequence,
        )
    # ... other methods
```

### Task 4: Create RollbackTargetSelectedEvent payload
Event payload for when Keepers select rollback target.

**Files:**
- `src/domain/events/rollback_target_selected.py` (new)
- `tests/unit/domain/test_rollback_target_selected_event.py` (new)

**Test Cases (RED):**
- `test_event_type_constant`
- `test_payload_creation`
- `test_payload_immutable`
- `test_payload_signable_content`
- `test_payload_includes_checkpoint_details`
- `test_payload_includes_selecting_keepers`
- `test_payload_includes_reason`

**Implementation (GREEN):**
```python
ROLLBACK_TARGET_SELECTED_EVENT_TYPE = "rollback_target_selected"

@dataclass(frozen=True, eq=True)
class RollbackTargetSelectedPayload:
    """Payload for RollbackTargetSelectedEvent (AC2).

    Records Keepers selecting a checkpoint for rollback.
    """
    target_checkpoint_id: UUID
    target_event_sequence: int
    target_anchor_hash: str
    selecting_keepers: tuple[str, ...]
    selection_reason: str
    selection_timestamp: datetime

    def signable_content(self) -> bytes:
        """Return canonical bytes for signing."""
        ...
```

### Task 5: Create RollbackCompletedEvent payload
Event payload for successful rollback completion.

**Files:**
- `src/domain/events/rollback_completed.py` (new)
- `tests/unit/domain/test_rollback_completed_event.py` (new)

**Test Cases (RED):**
- `test_event_type_constant`
- `test_payload_creation`
- `test_payload_immutable`
- `test_payload_signable_content`
- `test_payload_includes_checkpoint_details`
- `test_payload_includes_orphaned_event_count`
- `test_payload_includes_new_head_sequence`
- `test_payload_includes_ceremony_id`

**Implementation (GREEN):**
```python
ROLLBACK_COMPLETED_EVENT_TYPE = "rollback_completed"

@dataclass(frozen=True, eq=True)
class RollbackCompletedPayload:
    """Payload for RollbackCompletedEvent (AC3).

    Records successful rollback to checkpoint.
    """
    target_checkpoint_id: UUID
    previous_head_sequence: int
    new_head_sequence: int  # = target checkpoint sequence
    orphaned_event_count: int
    orphaned_sequence_range: tuple[int, int]  # (start, end) exclusive
    rollback_timestamp: datetime
    ceremony_id: UUID
    approving_keepers: tuple[str, ...]

    def signable_content(self) -> bytes:
        """Return canonical bytes for signing."""
        ...
```

### Task 6: Create rollback domain errors
Error types for rollback operations.

**Files:**
- `src/domain/errors/rollback.py` (new)
- `tests/unit/domain/test_rollback_errors.py` (new)

**Test Cases (RED):**
- `test_checkpoint_not_found_error`
- `test_rollback_not_permitted_error`
- `test_invalid_rollback_target_error`
- `test_rollback_already_in_progress_error`
- `test_no_events_to_orphan_error`
- `test_errors_are_value_errors`

**Implementation (GREEN):**
```python
class CheckpointNotFoundError(ValueError):
    """Requested checkpoint does not exist."""
    pass

class RollbackNotPermittedError(ValueError):
    """Rollback not allowed in current state (e.g., not halted)."""
    pass

class InvalidRollbackTargetError(ValueError):
    """Selected checkpoint is not valid for rollback."""
    pass

class RollbackAlreadyInProgressError(ValueError):
    """A rollback is already in progress."""
    pass
```

### Task 7: Create RollbackCoordinator port
Port interface for rollback operations.

**Files:**
- `src/application/ports/rollback_coordinator.py` (new)
- `tests/unit/application/test_rollback_coordinator_port.py` (new)

**Test Cases (RED):**
- `test_port_is_abstract`
- `test_query_checkpoints_method_signature`
- `test_select_rollback_target_method_signature`
- `test_execute_rollback_method_signature`
- `test_get_rollback_status_method_signature`
- `test_port_is_runtime_checkable`

**Implementation (GREEN):**
```python
@runtime_checkable
class RollbackCoordinator(Protocol):
    """Port for coordinating rollback operations (FR143)."""

    async def query_checkpoints(self) -> list[Checkpoint]:
        """Query available checkpoints for rollback (AC1)."""
        ...

    async def select_rollback_target(
        self,
        checkpoint_id: UUID,
        selecting_keepers: tuple[str, ...],
        reason: str,
    ) -> RollbackTargetSelectedPayload:
        """Record Keeper selection of rollback target (AC2)."""
        ...

    async def execute_rollback(
        self,
        ceremony_evidence: CeremonyEvidence,
    ) -> RollbackCompletedPayload:
        """Execute rollback to selected checkpoint (AC3)."""
        ...

    async def get_rollback_status(self) -> dict[str, Any]:
        """Get current rollback operation status."""
        ...
```

### Task 8: Create RollbackCoordinatorService
Application service implementing rollback coordination.

**Files:**
- `src/application/services/rollback_coordinator_service.py` (new)
- `tests/unit/application/test_rollback_coordinator_service.py` (new)

**Test Cases (RED):**
- `test_query_checkpoints_returns_all_available`
- `test_query_checkpoints_empty_when_none`
- `test_select_target_requires_halt`
- `test_select_target_creates_event_payload`
- `test_select_target_validates_checkpoint_exists`
- `test_select_target_rejects_invalid_checkpoint`
- `test_execute_rollback_requires_halt`
- `test_execute_rollback_requires_target_selected`
- `test_execute_rollback_orphans_events`
- `test_execute_rollback_moves_head`
- `test_execute_rollback_creates_event_payload`
- `test_execute_rollback_validates_ceremony`
- `test_get_status_returns_state`

**Implementation (GREEN):**
```python
class RollbackCoordinatorService:
    """Coordinates rollback to checkpoint (FR143, AC1-AC3).

    Constitutional Constraints:
    - FR143: Rollback for infrastructure recovery, logged, no event deletion
    - CT-11: Rollback must be witnessed
    - CT-13: Integrity over availability
    - PREVENT_DELETE: Events marked orphaned, not deleted
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        checkpoint_repository: CheckpointRepository,
        event_store: EventStorePort,
        witnessed_event_writer: WitnessedEventWriter,
    ) -> None:
        self._halt_checker = halt_checker
        self._checkpoint_repo = checkpoint_repository
        self._event_store = event_store
        self._event_writer = witnessed_event_writer
        self._selected_target: Checkpoint | None = None

    async def query_checkpoints(self) -> list[Checkpoint]:
        """Query available checkpoints (AC1)."""
        return await self._checkpoint_repo.get_all_checkpoints()

    async def select_rollback_target(
        self,
        checkpoint_id: UUID,
        selecting_keepers: tuple[str, ...],
        reason: str,
    ) -> RollbackTargetSelectedPayload:
        """Select checkpoint for rollback (AC2)."""
        # Validate halt state
        if not await self._halt_checker.is_halted():
            raise RollbackNotPermittedError("System must be halted")

        # Validate checkpoint exists
        checkpoint = await self._checkpoint_repo.get_checkpoint_by_id(checkpoint_id)
        if not checkpoint:
            raise CheckpointNotFoundError(f"Checkpoint {checkpoint_id} not found")

        self._selected_target = checkpoint

        return RollbackTargetSelectedPayload(
            target_checkpoint_id=checkpoint.checkpoint_id,
            target_event_sequence=checkpoint.event_sequence,
            target_anchor_hash=checkpoint.anchor_hash,
            selecting_keepers=selecting_keepers,
            selection_reason=reason,
            selection_timestamp=datetime.now(timezone.utc),
        )

    async def execute_rollback(
        self,
        ceremony_evidence: CeremonyEvidence,
    ) -> RollbackCompletedPayload:
        """Execute rollback (AC3)."""
        # ... implementation
```

### Task 9: Create EventStorePort extension for orphaning
Extend event store port with orphan marking capability.

**Files:**
- `src/application/ports/event_store.py` (modify)
- `tests/unit/application/test_event_store_port.py` (extend)

**Test Cases (RED):**
- `test_mark_events_orphaned_method_signature`
- `test_get_head_sequence_method_signature`
- `test_set_head_sequence_method_signature`
- `test_query_with_include_orphaned_flag`

**Implementation (GREEN):**
```python
# Add to EventStorePort Protocol:
async def mark_events_orphaned(
    self,
    start_sequence: int,
    end_sequence: int,
) -> int:
    """Mark events in range as orphaned (not deleted).

    Per PREVENT_DELETE: Events are never deleted, only marked.
    Returns count of events marked.
    """
    ...

async def get_head_sequence(self) -> int:
    """Get current HEAD sequence number."""
    ...

async def set_head_sequence(self, sequence: int) -> None:
    """Set HEAD to specific sequence (for rollback)."""
    ...
```

### Task 10: Integration tests for rollback flow
End-to-end tests for the complete rollback flow.

**Files:**
- `tests/integration/test_rollback_integration.py` (new)

**Test Cases:**
- `test_query_checkpoints_returns_all_anchors`
- `test_select_target_creates_witnessed_event`
- `test_execute_rollback_orphans_events`
- `test_execute_rollback_moves_head`
- `test_execute_rollback_creates_witnessed_event`
- `test_rollback_requires_halt_state`
- `test_rollback_requires_ceremony_evidence`
- `test_orphaned_events_excluded_by_default`
- `test_orphaned_events_queryable_with_flag`
- `test_rollback_does_not_delete_events`
- `test_constitutional_compliance_fr143`
- `test_constitutional_compliance_prevent_delete`

### Task 11: Update __init__.py exports
Update all package __init__.py files.

**Files:**
- `src/domain/models/__init__.py` (modify)
- `src/domain/events/__init__.py` (modify)
- `src/domain/errors/__init__.py` (modify)
- `src/application/ports/__init__.py` (modify)
- `src/application/services/__init__.py` (modify)
- `src/infrastructure/stubs/__init__.py` (modify)

## Technical Notes

### Implementation Order
1. Tasks 1-3: Checkpoint domain model and repository (foundation)
2. Tasks 4-6: Event payloads and errors
3. Tasks 7-8: RollbackCoordinator port and service
4. Task 9: EventStorePort extension
5. Tasks 10-11: Integration tests and exports

### Testing Strategy
- Unit tests for each component in isolation
- Integration tests for full rollback flow with stubs
- All tests follow red-green-refactor TDD cycle
- Verify PREVENT_DELETE constraint: events orphaned, not deleted

### Constitutional Compliance Matrix
| Requirement | Implementation |
|-------------|----------------|
| FR111 | Partition detection before rollback |
| FR112 | Validate writer lease/fencing |
| FR113 | Halt + fork recovery for conflicts |
| FR143 | Rollback logged as constitutional event |
| CT-11 | RollbackCompletedEvent is witnessed |
| CT-13 | Halt required before rollback |
| PREVENT_DELETE | Events marked orphaned, never deleted |

### Key Design Decisions
1. **Orphaned vs Deleted**: Events after checkpoint are marked `is_orphaned=true`, never deleted (PREVENT_DELETE primitive)
2. **HEAD movement**: HEAD pointer moves to checkpoint sequence; orphaned events remain queryable
3. **Two-phase**: Selection event → Execution event (audit trail)
4. **Ceremony required**: Keeper ceremony evidence validates authorization

### Patterns from Story 3.6 to Follow
- Use `HaltChecker` port for halt validation
- Use `CeremonyEvidence` for Keeper authorization
- Follow `RecoveryCoordinator` service structure
- Use `RecoveryWaitingPeriod` as model pattern

## Dev Notes

### Project Structure Notes
- Domain models: `src/domain/models/checkpoint.py`
- Events: `src/domain/events/rollback_*.py`
- Errors: `src/domain/errors/rollback.py`
- Ports: `src/application/ports/checkpoint_repository.py`, `rollback_coordinator.py`
- Services: `src/application/services/rollback_coordinator_service.py`
- Stubs: `src/infrastructure/stubs/checkpoint_repository_stub.py`

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.10]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-3]
- [Source: _bmad-output/planning-artifacts/prd.md#FR143]
- [Source: _bmad-output/planning-artifacts/prd.md#FR111-FR113]
- [Source: src/domain/models/recovery_waiting_period.py - pattern reference]
- [Source: src/application/services/recovery_coordinator.py - service pattern]

## Dev Agent Record

### Agent Model Used
Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References
- All 106 tests passing for Story 3.10 implementation

### Completion Notes List
- [x] Task 1: Checkpoint domain model created with immutability, signable_content, and anchor types
- [x] Task 2: CheckpointRepository port created as runtime_checkable Protocol
- [x] Task 3: CheckpointRepositoryStub implemented with seed/reset test helpers
- [x] Task 4: RollbackTargetSelectedPayload created for AC2 (Keeper selection recording)
- [x] Task 5: RollbackCompletedPayload created for AC3 (rollback completion event)
- [x] Task 6: Rollback domain errors created (CheckpointNotFoundError, RollbackNotPermittedError, InvalidRollbackTargetError, RollbackAlreadyInProgressError)
- [x] Task 7: RollbackCoordinator port created with query_checkpoints, select_rollback_target, execute_rollback, get_rollback_status
- [x] Task 8: RollbackCoordinatorService created with halt validation and ceremony evidence
- [x] Task 9: EventStorePort extended with mark_events_orphaned, get_head_sequence, set_head_sequence, get_events_by_sequence_range_with_orphaned
- [x] Task 10: Integration tests created for complete rollback flow
- [x] Task 11: All __init__.py exports updated

### File List
**Created:**
- `src/domain/models/checkpoint.py`
- `src/domain/events/rollback_target_selected.py`
- `src/domain/events/rollback_completed.py`
- `src/domain/errors/rollback.py`
- `src/application/ports/checkpoint_repository.py`
- `src/application/ports/rollback_coordinator.py`
- `src/application/services/rollback_coordinator_service.py`
- `src/infrastructure/stubs/checkpoint_repository_stub.py`
- `tests/unit/domain/test_checkpoint.py`
- `tests/unit/domain/test_rollback_target_selected_event.py`
- `tests/unit/domain/test_rollback_completed_event.py`
- `tests/unit/domain/test_rollback_errors.py`
- `tests/unit/application/test_checkpoint_repository_port.py`
- `tests/unit/application/test_rollback_coordinator_port.py`
- `tests/unit/application/test_rollback_coordinator_service.py`
- `tests/unit/infrastructure/test_checkpoint_repository_stub.py`
- `tests/integration/test_rollback_integration.py`

**Modified:**
- `src/application/ports/event_store.py` (added orphaning methods)
- `src/domain/models/__init__.py` (added Checkpoint export)
- `src/domain/events/__init__.py` (added rollback event exports)
- `src/domain/errors/__init__.py` (added rollback error exports)
- `src/application/ports/__init__.py` (added CheckpointRepository, RollbackCoordinator)
- `src/application/services/__init__.py` (added RollbackCoordinatorService)
- `src/infrastructure/stubs/__init__.py` (added CheckpointRepositoryStub)
- `tests/unit/application/test_event_store_port.py` (added orphaning tests)
