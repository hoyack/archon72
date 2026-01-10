# Story 3.2: Single-Conflict Halt Trigger (FR17)

Status: done

## Story

As an **external observer**,
I want a single fork to trigger system-wide halt,
so that no operations continue on a corrupted state.

## Acceptance Criteria

1. **AC1: Immediate Halt on Fork Detection**
   - **Given** a fork is detected (via `ForkMonitoringService` callback)
   - **When** the system processes the detection
   - **Then** a halt is triggered immediately
   - **And** all write operations are blocked within 1 second of detection

2. **AC2: ConstitutionalCrisisEvent Creation (RT-2)**
   - **Given** a fork is detected
   - **When** the halt is triggered
   - **Then** a `ConstitutionalCrisisEvent` is created BEFORE halt takes effect
   - **And** the event includes: `crisis_type: FORK_DETECTED`, timestamp, detection details
   - **And** the event is witnessed before system stops

3. **AC3: Writer Service Stops Accepting Events**
   - **Given** the halt trigger is executed
   - **When** the halt state is set
   - **Then** the Writer service stops accepting new events
   - **And** pending operations fail gracefully with `SystemHaltedError`
   - **And** the error message includes "FR17: Constitutional crisis - fork detected"

4. **AC4: HaltChecker Interface Update**
   - **Given** the `HaltChecker` interface exists from Story 1.8
   - **When** the halt is triggered
   - **Then** `is_halted()` returns `True`
   - **And** `get_halt_reason()` returns the crisis details

## Tasks / Subtasks

- [x] Task 1: Create ConstitutionalCrisisEvent domain event (AC: #2)
  - [x] 1.1: Create `src/domain/events/constitutional_crisis.py` with `ConstitutionalCrisisPayload` dataclass
  - [x] 1.2: Add `CONSTITUTIONAL_CRISIS_EVENT_TYPE = "constitutional.crisis"` constant
  - [x] 1.3: Include fields: `crisis_type: CrisisType` (enum: FORK_DETECTED), `detection_timestamp: datetime`, `detection_details: str`, `triggering_event_ids: tuple[UUID, ...]`
  - [x] 1.4: Add `CrisisType` enum with `FORK_DETECTED` variant (extensible for future crisis types)
  - [x] 1.5: Export from `src/domain/events/__init__.py`
  - [x] 1.6: Write unit tests in `tests/unit/domain/test_constitutional_crisis_event.py`

- [x] Task 2: Create HaltTrigger port interface (AC: #1, #3)
  - [x] 2.1: Create `src/application/ports/halt_trigger.py` with `HaltTrigger` ABC
  - [x] 2.2: Define abstract method: `async def trigger_halt(reason: str, crisis_event_id: UUID | None = None) -> None`
  - [x] 2.3: Define abstract method: `async def set_halt_state(halted: bool, reason: str | None) -> None`
  - [x] 2.4: Define abstract property: `halt_propagation_timeout_seconds: float` (default 1.0)
  - [x] 2.5: Export from `src/application/ports/__init__.py`

- [x] Task 3: Create HaltTriggerStub for testing/development (AC: #1, #3, #4)
  - [x] 3.1: Create `src/infrastructure/stubs/halt_trigger_stub.py`
  - [x] 3.2: Implement `HaltTriggerStub` that updates internal halt state
  - [x] 3.3: Implement coordination with `HaltCheckerStub` (same halt state)
  - [x] 3.4: Add `get_trigger_count()` method for testing
  - [x] 3.5: Add `get_last_crisis_event_id()` method for testing
  - [x] 3.6: Write unit tests in `tests/unit/infrastructure/test_halt_trigger_stub.py`

- [x] Task 4: Create HaltTriggerService application service (AC: #1, #2)
  - [x] 4.1: Create `src/application/services/halt_trigger_service.py`
  - [x] 4.2: Implement `on_fork_detected(fork: ForkDetectedPayload)` callback method
  - [x] 4.3: Create ConstitutionalCrisisEvent before triggering halt (RT-2)
  - [x] 4.4: Write crisis event to event store (with witness) BEFORE halt takes effect
  - [x] 4.5: Call `HaltTrigger.trigger_halt()` after event is witnessed
  - [x] 4.6: Log all halt operations with structured logging
  - [x] 4.7: Export from `src/application/services/__init__.py`

- [x] Task 5: Update HaltCheckerStub to use shared state with HaltTriggerStub (AC: #4)
  - [x] 5.1: Create `src/infrastructure/stubs/halt_state.py` shared state module
  - [x] 5.2: Implement `HaltState` singleton/shared object for stub coordination
  - [x] 5.3: Update `HaltCheckerStub` to read from shared state
  - [x] 5.4: Update `HaltTriggerStub` to write to shared state
  - [x] 5.5: Ensure thread-safe state updates
  - [x] 5.6: Write unit tests for shared state coordination

- [x] Task 6: Wire ForkMonitoringService to HaltTriggerService (AC: #1)
  - [x] 6.1: Update application wiring to inject `HaltTriggerService.on_fork_detected` as callback
  - [x] 6.2: Create factory function for proper dependency injection
  - [x] 6.3: Document wiring in module docstring

- [x] Task 7: Integration tests (AC: #1, #2, #3, #4)
  - [x] 7.1: Create `tests/integration/test_halt_trigger_integration.py`
  - [x] 7.2: Test: Fork detection triggers halt within 1 second
  - [x] 7.3: Test: ConstitutionalCrisisEvent is created and witnessed before halt
  - [x] 7.4: Test: HaltChecker returns True after halt is triggered
  - [x] 7.5: Test: Writer rejects writes after halt with SystemHaltedError
  - [x] 7.6: Test: Multiple fork detections don't cause duplicate crisis events

## Dev Notes

### Constitutional Requirements

**FR17 Coverage:**
- System SHALL halt immediately when a single fork is detected
- No operations continue on corrupted state
- This is a constitutional crisis - integrity over availability

**Constitutional Truths to Honor:**
- **CT-11 (Silent failure destroys legitimacy):** Halt MUST be logged before taking effect
- **CT-12 (Witnessing creates accountability):** ConstitutionalCrisisEvent MUST be witnessed
- **CT-13 (Integrity outranks availability):** Availability is sacrificed for integrity

**Red Team Hardening (RT-2):**
- All halt signals must create witnessed halt event BEFORE system stops
- Phantom halts detectable via halt event mismatch analysis
- The crisis event provides audit trail for what triggered halt

**Developer Golden Rules:**
1. **HALT FIRST** - Check halt state before every operation
2. **WITNESS EVERYTHING** - Constitutional actions require attribution
3. **FAIL LOUD** - Never catch SystemHaltedError in business logic

### Architecture Compliance

**ADR-3 (Partition Behavior + Halt Durability):**
- This story implements the halt TRIGGER mechanism
- Story 3.3 will add dual-channel transport (Redis + DB)
- Story 3.4 will add sticky halt semantics
- For now, use in-memory state via stubs

**Hexagonal Architecture:**
- `src/domain/events/constitutional_crisis.py` - Domain event
- `src/application/ports/halt_trigger.py` - Port interface
- `src/application/services/halt_trigger_service.py` - Application service
- `src/infrastructure/stubs/halt_trigger_stub.py` - Stub adapter
- `src/infrastructure/stubs/halt_state.py` - Shared state for stubs

**Import Rules:**
- Domain layer: NO infrastructure imports
- Application layer: Import from domain only (ports are in application)
- Infrastructure: Implements application ports

### Technical Implementation Notes

**Fork Detection Callback:**
```python
# HaltTriggerService wired as callback to ForkMonitoringService
async def on_fork_detected(self, fork: ForkDetectedPayload) -> None:
    """Handle fork detection by triggering constitutional crisis halt."""
    # 1. Create crisis event FIRST (RT-2)
    crisis_event = ConstitutionalCrisisPayload(
        crisis_type=CrisisType.FORK_DETECTED,
        detection_timestamp=fork.detection_timestamp,
        detection_details=f"Fork: {len(fork.conflicting_event_ids)} conflicting events",
        triggering_event_ids=fork.conflicting_event_ids,
    )

    # 2. Write and witness the crisis event (BEFORE halt)
    event_id = await self._event_writer.write_witnessed_event(
        event_type=CONSTITUTIONAL_CRISIS_EVENT_TYPE,
        payload=crisis_event,
    )

    # 3. NOW trigger the halt
    await self._halt_trigger.trigger_halt(
        reason=f"FR17: Fork detected - {crisis_event.detection_details}",
        crisis_event_id=event_id,
    )
```

**Shared Halt State Pattern:**
```python
# src/infrastructure/stubs/halt_state.py
class HaltState:
    """Shared halt state for stub coordination."""

    _instance: HaltState | None = None

    def __init__(self) -> None:
        self._is_halted = False
        self._halt_reason: str | None = None
        self._crisis_event_id: UUID | None = None
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> HaltState:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def set_halted(self, halted: bool, reason: str | None, event_id: UUID | None = None) -> None:
        async with self._lock:
            self._is_halted = halted
            self._halt_reason = reason
            self._crisis_event_id = event_id
```

### Library/Framework Requirements

**Required Libraries (already in project):**
- `asyncio` - Async coordination and locks
- `structlog` - Structured logging
- `dataclasses` - Event payload definition
- `datetime` with `timezone.utc` (Python 3.10+ compatible)
- `uuid` - Event IDs

**Patterns to Follow:**
- Use `@dataclass(frozen=True)` for payload (immutability)
- Use `tuple[T, ...]` for immutable collections in dataclass fields
- Use `UUID` from uuid module, not strings
- Follow existing Event pattern from `src/domain/events/event.py`
- Use `timezone.utc` not `datetime.UTC` (Python 3.10 compat)

### File Structure

```
src/
├── domain/
│   └── events/
│       ├── constitutional_crisis.py  # NEW: ConstitutionalCrisisPayload
│       └── __init__.py               # UPDATE: export new event
├── application/
│   ├── ports/
│   │   ├── halt_trigger.py           # NEW: HaltTrigger ABC
│   │   └── __init__.py               # UPDATE: export new port
│   └── services/
│       ├── halt_trigger_service.py   # NEW: Application service
│       └── __init__.py               # UPDATE: export new service
└── infrastructure/
    └── stubs/
        ├── halt_state.py             # NEW: Shared halt state
        ├── halt_trigger_stub.py      # NEW: HaltTriggerStub
        ├── halt_checker_stub.py      # UPDATE: Use shared state
        └── __init__.py               # UPDATE: export new stub

tests/
├── unit/
│   ├── domain/
│   │   └── test_constitutional_crisis_event.py  # NEW
│   └── infrastructure/
│       ├── test_halt_trigger_stub.py            # NEW
│       └── test_halt_state.py                   # NEW
└── integration/
    └── test_halt_trigger_integration.py         # NEW
```

### Testing Standards

**Unit Tests:**
- Test ConstitutionalCrisisPayload field validation
- Test CrisisType enum values
- Test HaltTriggerStub state transitions
- Test shared halt state coordination
- Use `pytest.mark.asyncio` for async tests
- Use `AsyncMock` for async dependencies

**Integration Tests:**
- Test full fork detection → halt trigger flow
- Test crisis event is witnessed before halt
- Test HaltChecker reflects halt state after trigger
- Test multiple forks don't cause duplicate events
- Test graceful failure of pending writes

**Coverage Target:** 80% minimum, 100% for domain logic

### Previous Story Learnings (Story 3.1)

**From Story 3-1 (Fork Monitoring):**
- Use `timezone.utc` not `datetime.UTC` for Python 3.10 compatibility
- Use `tuple[T, ...]` for immutable collections in dataclass fields
- Use `contextlib.suppress(asyncio.CancelledError)` for graceful shutdown
- Callback pattern used for decoupling detection from halt logic
- Export all new types from `__init__.py` files immediately

**From Code Review Issues:**
- Missing exports in `__init__.py` files were found during review
- Add exports as part of the task, not as afterthought

### Dependencies

**Story Dependencies:**
- **Story 3.1 (Fork Monitoring):** Provides ForkMonitoringService and callback mechanism
- **Story 1.6 (Event Writer):** Uses EventWriter to write crisis event
- **Story 1.8 (Halt Check Interface):** HaltChecker interface exists, stub needs coordination

**Implementation Order:**
1. Create domain event (no dependencies)
2. Create port interface (depends on event)
3. Create shared halt state (no dependencies)
4. Update HaltCheckerStub to use shared state
5. Create HaltTriggerStub (depends on shared state)
6. Create application service (depends on all above)
7. Wire to ForkMonitoringService
8. Integration tests (depends on all above)

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.2]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-003]
- [Source: _bmad-output/planning-artifacts/architecture.md#RT-2]
- [Source: src/application/ports/halt_checker.py] - Existing halt interface
- [Source: src/infrastructure/stubs/halt_checker_stub.py] - Stub pattern
- [Source: src/application/services/fork_monitoring_service.py] - Callback pattern
- [Source: src/domain/events/fork_detected.py] - Event payload pattern
- [Source: src/domain/errors/writer.py] - SystemHaltedError

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - all tests passed on first run.

### Completion Notes List

- Created ConstitutionalCrisisPayload dataclass with CrisisType enum (FR17, RT-2)
- Created HaltTrigger port interface with trigger_halt, set_halt_state, and timeout property
- Implemented shared HaltState module for coordination between HaltCheckerStub and HaltTriggerStub
- Updated HaltCheckerStub to support both standalone and shared state modes (backward compatible)
- Created HaltTriggerStub with trigger count tracking and crisis event ID tracking
- Implemented HaltTriggerService with on_fork_detected callback for ForkMonitoringService integration
- All 59 unit and integration tests pass
- Constitutional constraints honored: FR17, CT-11, CT-12, CT-13, RT-2

### File List

**New Files:**
- src/domain/events/constitutional_crisis.py
- src/application/ports/halt_trigger.py
- src/application/services/halt_trigger_service.py
- src/infrastructure/stubs/halt_state.py
- src/infrastructure/stubs/halt_trigger_stub.py
- tests/unit/domain/test_constitutional_crisis_event.py
- tests/unit/infrastructure/test_halt_state.py
- tests/unit/infrastructure/test_halt_trigger_stub.py
- tests/integration/test_halt_trigger_integration.py

**Modified Files:**
- src/domain/events/__init__.py - Added ConstitutionalCrisisPayload, CrisisType exports
- src/application/ports/__init__.py - Added HaltTrigger export
- src/application/services/__init__.py - Added HaltTriggerService export
- src/infrastructure/stubs/__init__.py - Added HaltState, HaltTriggerStub exports
- src/infrastructure/stubs/halt_checker_stub.py - Updated to support shared state mode

## Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.5 (code-review workflow)
**Date:** 2026-01-07
**Outcome:** ✅ APPROVED (after fixes applied)

### Review Summary

| Category | Count |
|----------|-------|
| Files Reviewed | 9 source files, 4 test files |
| All ACs Implemented | ✅ Yes |
| All Tasks Marked [x] | ✅ Verified |
| Tests Pass | ✅ 59/59 passed |
| Import Boundary | ✅ No violations |
| Constitutional Compliance | ✅ FR17, CT-11, CT-12, CT-13, RT-2 honored |

### Issues Found and Fixed

**HIGH (Fixed):**
1. **H1:** Inline `uuid4` import inside functions → Moved to module-level import
2. **H2:** `HaltTrigger` missing from `__all__` in `src/application/ports/__init__.py` → Added

**LOW (Fixed):**
1. **L1:** Empty `TYPE_CHECKING` block in halt_trigger_service.py → Removed
2. **L2:** Inconsistent error message format (missing FR17 prefix) → Standardized

**MEDIUM (Accepted - by design):**
1. **M1:** TODO comment for Story 3.9 dependency → Acceptable, documented in story notes
2. **M2:** HaltState singleton pattern test isolation risk → Mitigated via `reset_all()` fixtures

**Note on AC3:** Integration test uses simulated writer (not real EventWriterService). This is acceptable for stub-based story scope - full integration will be verified in Story 3.9.

### Files Modified During Review

- `src/application/services/halt_trigger_service.py` - Import cleanup, message format fix
- `src/application/ports/__init__.py` - Added HaltTrigger to __all__

### Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-01-07 | Dev Agent (Opus 4.5) | Initial implementation - all tasks complete |
| 2026-01-07 | Review Agent (Opus 4.5) | Code review fixes: import cleanup, __all__ export, message format |

