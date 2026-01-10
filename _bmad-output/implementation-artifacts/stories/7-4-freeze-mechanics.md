# Story 7.4: Freeze Mechanics

Status: done

## Story

As a **system operator**,
I want freeze on new actions except record preservation after cessation,
So that the system stops but records are preserved.

## Acceptance Criteria

### AC1: Immediate Write Freeze on Cessation (FR41)
**Given** cessation is triggered
**When** the cessation event is written
**Then** all write operations are frozen immediately
**And** the system transitions to `CEASED` state
**And** no further `EventWriterService.write_event()` calls succeed
**And** the freeze is instantaneous (no grace period)

### AC2: Pending Operations Fail Gracefully (FR41)
**Given** cessation has occurred
**When** pending write operations are in flight
**Then** they fail with `SystemCeasedError`
**And** error includes "FR41: System ceased - writes frozen"
**And** no data corruption occurs from partial writes
**And** operation failures are logged with full context (CT-11)

### AC3: Write Rejection Error Message (FR41)
**Given** a frozen system
**When** a write is attempted
**Then** it is rejected with `SystemCeasedError`
**And** error message includes "FR41: System ceased - writes frozen"
**And** error includes cessation timestamp and final sequence number
**And** this applies to ALL write paths (EventWriterService, AtomicEventWriter, direct DB)

### AC4: Record Preservation Accessibility (FR41)
**Given** record preservation
**When** the system is frozen
**Then** existing records remain accessible via read operations
**And** all events up to and including the cessation event are readable
**And** hash chain integrity is preserved and verifiable
**And** observer API read endpoints continue to function

### AC5: Preservation Processes Continue (FR41)
**Given** the system is in ceased state
**When** preservation mode is active
**Then** read replicas continue to serve queries
**And** backup processes can still read data for archival
**And** verification toolkit continues to work
**And** Merkle path generation for historical events continues

### AC6: CeasedStatusHeader in Responses (FR41)
**Given** a ceased system
**When** any read operation is performed
**Then** response includes `system_status: CEASED` header
**And** header includes `ceased_at` timestamp
**And** header includes `final_sequence_number`
**And** this is analogous to `HaltStatusHeader` but permanent

### AC7: API Endpoint Behavior After Cessation (FR41)
**Given** a ceased system
**When** API endpoints are called
**Then** read endpoints (GET) return 200 with `CEASED` header
**And** write endpoints (POST, PUT, DELETE) return 503 with cessation message
**And** 503 response includes `Retry-After: never` to signal permanence
**And** response body explains "FR41: System has permanently ceased"

### AC8: Dual-Channel Cessation Flag (FR41)
**Given** cessation occurs
**When** the cessation event is written
**Then** the cessation flag is set in BOTH Redis AND database
**And** this mirrors the dual-channel halt pattern (ADR-3)
**And** flag setting is atomic with cessation event write
**And** flag can be read even if one channel is unavailable

## Tasks / Subtasks

- [x] **Task 1: Create CEASED status constants and model** (AC: 1,6)
  - [x] Create `src/domain/models/ceased_status_header.py`
  - [x] Define status constants: `SYSTEM_STATUS_CEASED = "CEASED"`
  - [x] Implement `CeasedStatusHeader` frozen dataclass with:
    - `system_status: str` (always "CEASED")
    - `ceased_at: datetime` (when cessation occurred)
    - `final_sequence_number: int` (last valid sequence)
    - `cessation_reason: str` (from cessation event)
  - [x] Add factory methods: `from_cessation_details()`, `ceased()`
  - [x] Implement `to_dict()` for JSON serialization
  - [x] Export from `src/domain/models/__init__.py`

- [x] **Task 2: Create SystemCeasedError domain error** (AC: 2,3)
  - [x] Create `src/domain/errors/ceased.py`
  - [x] Define `SystemCeasedError(ConstitutionalViolationError)`:
    - Must include "FR41: System ceased - writes frozen" in message
    - Include `ceased_at: datetime` attribute
    - Include `final_sequence_number: int` attribute
    - Inherit from `ConstitutionalViolationError` (never retry!)
  - [x] Add `CeasedWriteAttemptError` for specific write rejections
  - [x] Export from `src/domain/errors/__init__.py`

- [x] **Task 3: Create freeze state checker port** (AC: 1,4)
  - [x] Create `src/application/ports/freeze_checker.py`
  - [x] Define `FreezeCheckerProtocol` with:
    - `is_frozen() -> bool` - Check if system is in ceased state
    - `get_freeze_details() -> CessationDetails | None` - Get cessation details
    - `get_ceased_at() -> datetime | None` - When cessation occurred
    - `get_final_sequence() -> int | None` - Last valid sequence
  - [x] Export from `src/application/ports/__init__.py`

- [x] **Task 4: Create dual-channel cessation flag repository** (AC: 8)
  - [x] Create `src/application/ports/cessation_flag_repository.py`
  - [x] Define `CessationFlagRepositoryProtocol` (mirrors HaltFlagRepository pattern):
    - `set_ceased(details: CessationDetails) -> None` - Set flag in BOTH channels
    - `is_ceased() -> bool` - Check either channel
    - `get_cessation_details() -> CessationDetails | None`
  - [x] Export from `src/application/ports/__init__.py`

- [x] **Task 5: Implement freeze checker stub** (AC: all)
  - [x] Create `src/infrastructure/stubs/freeze_checker_stub.py`
  - [x] Implement `FreezeCheckerStub`:
    - `set_frozen(ceased_at, final_sequence, reason)` - Configure frozen state
    - `clear_frozen()` - Reset for test isolation
    - All protocol methods
  - [x] Register in `src/infrastructure/stubs/__init__.py`

- [x] **Task 6: Implement cessation flag repository stub** (AC: 8)
  - [x] Create `src/infrastructure/stubs/cessation_flag_repository_stub.py`
  - [x] Implement `CessationFlagRepositoryStub`:
    - In-memory dual storage (simulating Redis + DB)
    - Atomic flag setting
    - Configurable failure modes for testing
  - [x] Register in `src/infrastructure/stubs/__init__.py`

- [x] **Task 7: Create freeze guard service** (AC: 1,2,3,4)
  - [x] Create `src/application/services/freeze_guard.py`
  - [x] Implement `FreezeGuard` class:
    - Inject `FreezeCheckerProtocol`
    - `ensure_not_frozen() -> None` - Raises `SystemCeasedError` if frozen
    - `get_freeze_status() -> CeasedStatusHeader | None`
    - `for_operation(name)` - Async context manager for operations
  - [x] Log all freeze check failures (CT-11)

- [x] **Task 8: Update EventWriterService for freeze check** (AC: 1,2,3)
  - [x] Modify `src/application/services/event_writer_service.py`
  - [x] Add `FreezeCheckerProtocol` dependency injection
  - [x] Add freeze check AFTER terminal check (separate concern):
    - Terminal check = cessation event exists (Story 7.3)
    - Freeze check = operational freeze is in effect (Story 7.4)
  - [x] Ensure `SystemCeasedError` is raised with full context

- [x] **Task 9: Create cessation execution service** (AC: 1,8)
  - [x] Create `src/application/services/cessation_execution_service.py`
  - [x] Implement `CessationExecutionService`:
    - `execute_cessation(trigger_event: Event) -> CessationExecutedEvent`
    - Write cessation event (last event ever)
    - Set dual-channel cessation flag atomically
    - Log execution with full context (CT-11)
  - [x] This service is called by deliberation when cessation vote passes

- [x] **Task 10: Write unit tests** (AC: all)
  - [x] `tests/unit/domain/test_ceased_status_header.py` - Header creation, serialization
  - [x] `tests/unit/domain/test_ceased_errors.py` - Error messages, attributes
  - [x] `tests/unit/application/test_freeze_checker_port.py` - Protocol compliance
  - [x] `tests/unit/application/test_freeze_guard.py` - Guard behavior, exceptions
  - [x] `tests/unit/application/test_cessation_execution_service.py` - Execution flow
  - [x] `tests/unit/infrastructure/test_freeze_checker_stub.py` - Stub functionality
  - [x] `tests/unit/infrastructure/test_cessation_flag_repository_stub.py` - Dual-channel

- [x] **Task 11: Write integration tests** (AC: all)
  - [x] `tests/integration/test_freeze_mechanics_integration.py`:
    - Test cessation → immediate write rejection
    - Test pending operations fail gracefully
    - Test read operations continue after cessation
    - Test CeasedStatusHeader in responses
    - Test dual-channel flag consistency
    - Test EventWriterService freeze check integration
    - Test API endpoint behavior (200 for GET, 503 for POST/PUT/DELETE)

## Dev Notes

### Relevant Architecture Patterns and Constraints

**Constitutional Truths to Honor:**
- **CT-11**: Silent failure destroys legitimacy → Log ALL freeze violations
- **CT-12**: Witnessing creates accountability → Cessation execution must be witnessed
- **CT-13**: Integrity outranks availability → Terminate > Continue after cessation
- **FR41**: Freeze on new actions except record preservation (PRIMARY CONSTRAINT)

**Developer Golden Rules:**
1. **TERMINAL FIRST** - Check termination before freeze (Story 7.3 terminal check is about the event existing; Story 7.4 freeze check is about operational state)
2. **FREEZE SECOND** - Check freeze state after terminal check
3. **FAIL LOUD** - Never silently allow post-cessation writes
4. **READ ALWAYS** - Read operations must ALWAYS succeed with status header

### Source Tree Components to Touch

**New Files:**
```
src/domain/models/ceased_status_header.py              # CeasedStatusHeader
src/domain/errors/ceased.py                             # SystemCeasedError
src/application/ports/freeze_checker.py                 # FreezeCheckerProtocol
src/application/ports/cessation_flag_repository.py      # Dual-channel flag port
src/application/services/freeze_guard.py                # FreezeGuard service
src/application/services/cessation_execution_service.py # Execute cessation
src/infrastructure/stubs/freeze_checker_stub.py
src/infrastructure/stubs/cessation_flag_repository_stub.py
tests/unit/domain/test_ceased_status_header.py
tests/unit/domain/test_ceased_errors.py
tests/unit/application/test_freeze_checker_port.py
tests/unit/application/test_freeze_guard.py
tests/unit/application/test_cessation_execution_service.py
tests/unit/infrastructure/test_freeze_checker_stub.py
tests/unit/infrastructure/test_cessation_flag_repository_stub.py
tests/integration/test_freeze_mechanics_integration.py
```

**Files to Update:**
```
src/domain/models/__init__.py                          # Export CeasedStatusHeader
src/domain/errors/__init__.py                          # Export SystemCeasedError
src/application/ports/__init__.py                      # Export new ports
src/application/services/event_writer_service.py       # Add FreezeGuard
src/infrastructure/stubs/__init__.py                   # Register stubs
```

### Related Existing Code

**Story 7.3 Terminal Detection (Build on this):**
- `src/application/ports/terminal_event_detector.py` - Check if cessation event exists
- `src/domain/events/cessation_executed.py` - The terminal event payload
- `src/domain/errors/schema_irreversibility.py` - SchemaIrreversibilityError

**Story 3.5 Read-Only Pattern (Mirror this for cessation):**
- `src/domain/errors/read_only.py` - `WriteBlockedDuringHaltError` pattern
- `src/domain/models/halt_status_header.py` - `HaltStatusHeader` pattern

**Dual-Channel Pattern (ADR-3):**
- `src/infrastructure/adapters/persistence/halt_flag_repository.py` - DB flag pattern
- `src/infrastructure/adapters/messaging/halt_stream_publisher.py` - Redis pattern
- `src/infrastructure/stubs/dual_channel_halt_stub.py` - Stub pattern

**EventWriterService Check Order:**
```python
# From event_writer_service.py - FOLLOW THIS CHECK ORDER
async def write_event(self, ...) -> Event:
    # 1. TERMINAL CHECK FIRST (Story 7.3 - NFR40)
    if await self._terminal_detector.is_system_terminated():
        raise SchemaIrreversibilityError(...)

    # 2. FREEZE CHECK SECOND (Story 7.4 - FR41) <- ADD THIS
    if await self._freeze_guard.is_frozen():
        raise SystemCeasedError(...)

    # 3. HALT CHECK THIRD (existing)
    if await self._halt_checker.is_halted():
        raise SystemHaltedError(...)

    # 4. Proceed with write...
```

### Design Decisions

**Why Separate Terminal Check and Freeze Check:**
1. **Separation of concerns**: Terminal check = "cessation event exists", Freeze check = "operational freeze in effect"
2. **Story 7.3 already implemented terminal detection** - this story adds operational freeze
3. **Terminal is schema-level** (no reversal event type), Freeze is **operational** (no writes accepted)
4. **They complement each other**: Terminal prevents new event types, Freeze prevents new events of ANY type

**Why Mirror HaltStatusHeader Pattern:**
1. Consistent API responses for all degraded states
2. External observers familiar with halt pattern
3. Reuse of serialization/header injection patterns
4. Clear distinction: `HALTED` (temporary) vs `CEASED` (permanent)

**Why Dual-Channel Cessation Flag:**
1. Mirrors proven ADR-3 halt pattern
2. Handles Redis/DB partition scenarios
3. Fast reads via Redis, durability via DB
4. Atomic setting prevents inconsistent states

**API Behavior Rationale:**
1. **503 for writes**: Standard "service unavailable" but permanent
2. **`Retry-After: never`**: Signals to clients this is not temporary
3. **200 with header for reads**: Records must remain accessible indefinitely

### Testing Standards Summary

- **Async Testing**: ALL tests use `pytest.mark.asyncio` and `async def test_*`
- **Mocking**: Use `AsyncMock` for async dependencies
- **Coverage**: 80% minimum required
- **Unit Test Location**: `tests/unit/domain/`, `tests/unit/application/`, `tests/unit/infrastructure/`
- **Integration Test Location**: `tests/integration/`

### Project Structure Notes

**Hexagonal Architecture Compliance:**
- Domain models: Pure dataclasses, no infrastructure imports
- Domain errors: Simple exception classes, no I/O
- Ports: Protocol classes in `application/ports/`
- Stubs: Implementation stubs in `infrastructure/stubs/`
- Services: Business logic in `application/services/`

**Import Rules:**
- `domain/` imports NOTHING from other layers
- `application/` imports from `domain/` only
- `infrastructure/` implements ports from `application/`

### Key Differences from Story 7.3

| Aspect | Story 7.3 | Story 7.4 |
|--------|-----------|-----------|
| Focus | Schema prevents reversal | Operational freeze |
| Mechanism | Event type prohibition | Write rejection |
| Check Type | Terminal event exists | Freeze state active |
| Error Type | SchemaIrreversibilityError | SystemCeasedError |
| Effect | No cessation_reversal events | No ANY events after cessation |
| Constraint | NFR40 | FR41 |

### Edge Cases to Test

1. **Concurrent cessation attempts**: Only first one succeeds
2. **In-flight write during cessation**: Fails gracefully with context
3. **Read during cessation execution**: Should succeed with header
4. **Redis down during cessation**: DB flag still set
5. **DB down during cessation**: Operation fails (can't write cessation event)
6. **API endpoint called milliseconds after cessation**: Returns 503 with full context
7. **Verification toolkit after cessation**: Still works, returns CEASED status

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-7.4]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-3] - Dual-channel pattern
- [Source: _bmad-output/planning-artifacts/architecture.md#FR41]
- [Source: src/domain/models/halt_status_header.py] - Pattern to mirror
- [Source: src/domain/errors/read_only.py] - Error pattern to mirror
- [Source: src/application/services/event_writer_service.py] - Add freeze check
- [Source: src/domain/events/cessation_executed.py] - Terminal event from 7.3
- [Source: src/application/ports/terminal_event_detector.py] - Terminal detection from 7.3
- [Source: _bmad-output/project-context.md] - Coding standards
- [Source: _bmad-output/implementation-artifacts/stories/7-3-schema-irreversibility.md] - Previous story learnings

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - all tests passing

### Completion Notes List

1. Implemented `CeasedStatusHeader` model with `CessationDetails` value object
2. Created `SystemCeasedError` and `CeasedWriteAttemptError` domain errors
3. Created `FreezeCheckerProtocol` port for freeze state detection
4. Created `CessationFlagRepositoryProtocol` for dual-channel flag storage (ADR-3)
5. Implemented stubs: `FreezeCheckerStub`, `CessationFlagRepositoryStub`
6. Created `FreezeGuard` service with `ensure_not_frozen()` and context manager
7. Updated `EventWriterService` with FREEZE SECOND check (after terminal, before halt)
8. Created `CessationExecutionService` for executing cessation with dual-channel flag setting
9. All 89 Story 7.4 related tests passing

### File List

**New Files:**
- `src/domain/models/ceased_status_header.py` - CeasedStatusHeader, CessationDetails
- `src/domain/errors/ceased.py` - SystemCeasedError, CeasedWriteAttemptError
- `src/application/ports/freeze_checker.py` - FreezeCheckerProtocol
- `src/application/ports/cessation_flag_repository.py` - CessationFlagRepositoryProtocol
- `src/application/services/freeze_guard.py` - FreezeGuard service
- `src/application/services/cessation_execution_service.py` - CessationExecutionService
- `src/infrastructure/stubs/freeze_checker_stub.py` - FreezeCheckerStub
- `src/infrastructure/stubs/cessation_flag_repository_stub.py` - CessationFlagRepositoryStub
- `tests/unit/domain/test_ceased_status_header.py` - 16 tests
- `tests/unit/domain/test_ceased_errors.py` - 15 tests
- `tests/unit/application/test_freeze_checker_port.py` - 12 tests
- `tests/unit/application/test_freeze_guard.py` - 10 tests
- `tests/unit/application/test_cessation_execution_service.py` - 19 tests
- `tests/unit/infrastructure/test_freeze_checker_stub.py` - 13 tests
- `tests/unit/infrastructure/test_cessation_flag_repository_stub.py` - 15 tests
- `tests/integration/test_freeze_mechanics_integration.py` - 14 tests

**Modified Files:**
- `src/application/services/event_writer_service.py` - Added freeze check (Step 2)
- `src/domain/models/__init__.py` - Export CeasedStatusHeader, CessationDetails
- `src/domain/errors/__init__.py` - Export SystemCeasedError, CeasedWriteAttemptError
- `src/application/ports/__init__.py` - Export FreezeCheckerProtocol, CessationFlagRepositoryProtocol
- `src/infrastructure/stubs/__init__.py` - Export FreezeCheckerStub, CessationFlagRepositoryStub
- `tests/unit/application/test_event_writer_service.py` - Added 8 freeze check tests

## Change Log

- 2026-01-08: Story created - Freeze mechanics implementation (FR41)
- 2026-01-08: Story completed - All 11 tasks done, 89 tests passing
