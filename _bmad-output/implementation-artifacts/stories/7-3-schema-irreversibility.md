# Story 7.3: Schema Irreversibility

Status: done

## Story

As a **developer**,
I want no "cessation_reversal" event type in schema,
So that cessation is architecturally irreversible.

## Acceptance Criteria

### AC1: No Reversal Event Type in Schema (FR40)
**Given** the event schema
**When** I examine event types
**Then** there is no `cessation_reversal` or equivalent type
**And** schema documentation confirms this is intentional
**And** the `EventType` registry explicitly documents this prohibition

### AC2: Schema Migration Validation (NFR40)
**Given** an attempt to add a reversal event type
**When** schema migration is attempted
**Then** it is blocked by schema validation
**And** error includes "NFR40: Cessation reversal prohibited by schema"
**And** CI/CD pipeline rejects the migration

### AC3: Terminal Event Marker (FR40)
**Given** the cessation event type
**When** it is written
**Then** it is marked as terminal (`is_terminal: true`)
**And** subsequent event writes are blocked by `EventWriterService`
**And** `SchemaIrreversibilityError` is raised for post-cessation writes

### AC4: Event Type Registry Validation (NFR40)
**Given** the `PAYLOAD_REGISTRY` from architecture
**When** it is validated at import time
**Then** no event type contains "reversal", "undo", "revert", or "restore" for cessation
**And** `EventTypeProhibitedError` is raised if violation detected
**And** this validation runs on every application startup

### AC5: Documentation of Intentional Prohibition
**Given** the event schema documentation
**When** I examine it
**Then** it explicitly states "NFR40: Cessation reversal is architecturally prohibited"
**And** the rationale is documented ("cessation is final by design")
**And** this appears in code comments AND architecture docs

### AC6: Event Witnessing (CT-12)
**Given** any schema irreversibility validation event
**When** a validation fails
**Then** the failure MUST be logged with full context
**And** `signable_content()` includes validation details

### AC7: Halt State Interaction (CT-11)
**Given** system is in halted state
**When** a cessation event is evaluated for terminality
**Then** the terminal check still applies
**And** post-halt cessation events are equally irreversible

## Tasks / Subtasks

- [x] **Task 1: Create CESSATION_EXECUTED event type** (AC: 1,3,5)
  - [x] Create `src/domain/events/cessation_executed.py`
  - [x] Define `CESSATION_EXECUTED_EVENT_TYPE = "cessation.executed"`
  - [x] Implement `CessationExecutedEventPayload` frozen dataclass with:
    - `cessation_id`: UUID
    - `execution_timestamp`: datetime
    - `is_terminal`: bool (always True)
    - `final_sequence_number`: int
    - `final_hash`: str (SHA-256 of last event)
    - `reason`: str (from agenda placement)
    - `triggering_event_id`: UUID (reference to agenda placement)
  - [x] Implement `signable_content()` for CT-12 witnessing
  - [x] Add `to_dict()` for event storage
  - [x] Export from `src/domain/events/__init__.py`

- [x] **Task 2: Create schema irreversibility domain errors** (AC: 2,3,4)
  - [x] Create `src/domain/errors/schema_irreversibility.py`
  - [x] Define errors:
    - `SchemaIrreversibilityError(ConstitutionalViolationError)` - Post-cessation write attempt
    - `EventTypeProhibitedError(ConstitutionalViolationError)` - Forbidden event type detected
    - `TerminalEventViolationError(ConstitutionalViolationError)` - Write after terminal event
    - `CessationReversalAttemptError(ConstitutionalViolationError)` - Reversal attempt detected
  - [x] All errors include "NFR40" reference in message
  - [x] Export from `src/domain/errors/__init__.py`

- [x] **Task 3: Create terminal event detection port** (AC: 3)
  - [x] Create `src/application/ports/terminal_event_detector.py`
  - [x] Define `TerminalEventDetectorProtocol`:
    - `is_system_terminated() -> bool` - Check if cessation has executed
    - `get_terminal_event() -> Optional[Event]` - Get cessation event if exists
    - `get_termination_timestamp() -> Optional[datetime]` - When cessation occurred
  - [x] Export from `src/application/ports/__init__.py`

- [x] **Task 4: Create event type validator** (AC: 2,4)
  - [x] Create `src/domain/services/event_type_validator.py`
  - [x] Define `PROHIBITED_EVENT_TYPE_PATTERNS` (18 patterns)
  - [x] Implement `validate_event_type(event_type: str) -> bool`
  - [x] Raise `EventTypeProhibitedError` if pattern matches
  - [x] Include "NFR40: Cessation reversal prohibited by schema" in error

- [x] **Task 5: Update EventWriterService for terminal check** (AC: 3,6,7)
  - [x] Modify `src/application/services/event_writer_service.py`
  - [x] Inject `TerminalEventDetector` dependency
  - [x] Add terminal check BEFORE halt check
  - [x] Log all rejections with full context

- [x] **Task 6: Create import-time validation** (AC: 4)
  - [x] Add `_validate_no_prohibited_event_types()` to `src/domain/events/__init__.py`
  - [x] Ensure this runs on every application startup
  - [x] Test that importing with a prohibited type fails fast

- [x] **Task 7: Create stub implementations** (AC: all)
  - [x] Create `src/infrastructure/stubs/terminal_event_detector_stub.py`
  - [x] Implement configurable stub for testing:
    - `set_terminated(terminal_event: Event)` - Simulate cessation
    - `clear_termination()` - Reset for test isolation
    - `set_terminated_simple()` - Minimal test helper
  - [x] Register stub in `src/infrastructure/stubs/__init__.py`

- [x] **Task 8: Add schema documentation** (AC: 1,5)
  - [x] Update docstring in `src/domain/events/__init__.py` with NFR40 compliance section
  - [x] Add inline comments on relevant validation code

- [x] **Task 9: Write unit tests** (AC: all)
  - [x] `tests/unit/domain/test_cessation_executed_event.py` - 29 tests
  - [x] `tests/unit/domain/test_event_type_validator.py` - 35 tests
  - [x] `tests/unit/domain/test_schema_irreversibility_errors.py` - 22 tests
  - [x] `tests/unit/application/test_event_writer_service.py` - Added TestEventWriterServiceTerminalDetection (6 tests)
  - [x] `tests/unit/infrastructure/test_terminal_event_detector_stub.py` - 18 tests

- [x] **Task 10: Write integration tests** (AC: all)
  - [x] `tests/integration/test_schema_irreversibility_integration.py` - 16 tests
    - Test end-to-end cessation → write rejection
    - Test import-time validation catches violations
    - Test terminal event detection
    - Test halt + termination interaction (terminal first)

## Dev Notes

### Relevant Architecture Patterns and Constraints

**Constitutional Truths to Honor:**
- **CT-11**: Silent failure destroys legitimacy → Log ALL irreversibility violations
- **CT-12**: Witnessing creates accountability → All validation events must be logged
- **CT-13**: Integrity outranks availability → Terminate > Continue with invalid state
- **NFR40**: No cessation reversal event type in schema (PRIMARY CONSTRAINT)

**Developer Golden Rules:**
1. **TERMINAL FIRST** - Check termination BEFORE halt state
2. **WITNESS EVERYTHING** - All rejections must be logged with context
3. **FAIL LOUD** - Never silently allow post-cessation writes
4. **IMPORT-TIME VALIDATION** - Catch violations at startup, not runtime

### Source Tree Components to Touch

**New Files:**
```
src/domain/events/cessation_executed.py               # CessationExecutedEventPayload
src/domain/errors/schema_irreversibility.py           # Irreversibility errors
src/domain/services/event_type_validator.py           # Prohibited pattern validator
src/application/ports/terminal_event_detector.py      # Terminal detection port
src/infrastructure/stubs/terminal_event_detector_stub.py
tests/unit/domain/test_cessation_executed_event.py
tests/unit/domain/test_event_type_validator.py
tests/unit/domain/test_schema_irreversibility_errors.py
tests/unit/application/test_terminal_event_detection.py
tests/unit/infrastructure/test_terminal_event_detector_stub.py
tests/integration/test_schema_irreversibility_integration.py
```

**Files to Update:**
```
src/domain/events/__init__.py                         # Export new event, add NFR40 docs
src/domain/errors/__init__.py                         # Export new errors
src/application/ports/__init__.py                     # Export new port
src/application/services/event_writer_service.py      # Add terminal check
src/infrastructure/stubs/__init__.py                  # Register stub
```

### Related Existing Code

**Cessation Events (Story 6.3, 7.1):**
- `src/domain/events/cessation.py` - CessationConsiderationEventPayload, CessationDecision
- `src/domain/events/cessation_agenda.py` - CessationAgendaPlacementEventPayload
- `src/application/services/cessation_consideration_service.py` - Service pattern

**Event Writing Pattern:**
```python
# From event_writer_service.py - FOLLOW THIS PATTERN for terminal check
async def write_event(self, ...) -> Event:
    # 1. TERMINAL CHECK FIRST (new, before halt)
    if await self._terminal_detector.is_system_terminated():
        raise SchemaIrreversibilityError("NFR40: Post-cessation write rejected")

    # 2. HALT CHECK SECOND (existing)
    if await self._halt_checker.is_halted():
        raise SystemHaltedError("CT-11: System is halted")

    # 3. Proceed with event write
    ...
```

**Registry Validation Pattern (from architecture.md):**
```python
# WR-2: Registry Exhaustiveness Guard - FOLLOW THIS PATTERN
def _validate_payload_registry() -> None:
    """Import-time validation ensures all event types have registered payloads."""
    defined = set(EventType)
    registered = set(PAYLOAD_REGISTRY.keys())

    missing = defined - registered
    if missing:
        raise ConfigurationError(
            f"Missing payloads for event types: {missing}"
        )
```

**Import-Time Validation Pattern:**
```python
# Add this pattern to events/__init__.py
def _validate_no_prohibited_event_types() -> None:
    """NFR40: Ensure no cessation reversal event types exist."""
    from src.domain.services.event_type_validator import (
        validate_event_type,
        PROHIBITED_EVENT_TYPE_PATTERNS,
    )

    for name in dir():
        if name.endswith("_EVENT_TYPE"):
            event_type_value = globals().get(name)
            if event_type_value:
                validate_event_type(event_type_value)

# Called at module load
_validate_no_prohibited_event_types()
```

### Design Decisions

**Why Terminal Check Before Halt Check:**
1. Cessation is permanent; halt is temporary
2. A halted system can be unhalted; a ceased system cannot
3. Terminal state supersedes all other states
4. This ordering prevents any edge case where halt could mask cessation

**Why Import-Time Validation:**
1. Catch violations before any code runs
2. CI/CD fails fast on prohibited patterns
3. Prevents accidental addition of reversal types
4. Self-documenting constraint enforcement

**Why Regex Patterns (not exact match):**
1. Catches variations: "cessation_reversal", "cessation.reversal", "cessationReversal"
2. Prevents typosquatting: "cesation_reversal"
3. Blocks synonyms: "undo", "revert", "restore", "rollback"
4. Extensible for future prohibitions

### Testing Standards Summary

- **Async Testing**: ALL tests use `pytest.mark.asyncio` and `async def test_*`
- **Mocking**: Use `AsyncMock` for async dependencies
- **Coverage**: 80% minimum required
- **Import Tests**: Test that module import fails with prohibited types
- **Unit Test Location**: `tests/unit/domain/` and `tests/unit/application/`
- **Integration Test Location**: `tests/integration/`

### Project Structure Notes

**Hexagonal Architecture Compliance:**
- Domain events: Pure dataclasses, no infrastructure imports
- Domain services: Pure validation logic, no I/O
- Ports: Protocol classes in `application/ports/`
- Stubs: Implementation stubs in `infrastructure/stubs/`
- Service updates: Business logic in `application/services/`

**Import Rules:**
- `domain/` imports NOTHING from other layers
- `domain/services/` contains pure validation (no async, no I/O)
- `application/` imports from `domain/` only
- `infrastructure/` implements ports from `application/`

### Key Differences from Story 7.1/7.2

| Aspect | Story 7.1/7.2 | Story 7.3 |
|--------|---------------|-----------|
| Focus | Agenda placement triggers | Schema enforcement |
| Mechanism | Event creation | Event type prohibition |
| Validation | Runtime business logic | Import-time + runtime |
| Primary Constraint | FR37-FR39 | NFR40, FR40 |
| Effect | Create events | Block events |

### Edge Cases to Test

1. **Module reload**: Does validation re-run?
2. **Partial match**: "cessation_reversal_attempt" - should block
3. **Case variations**: "CESSATION_REVERSAL" - should block
4. **Timestamp edge**: Event written at exact cessation moment
5. **Concurrent cessation**: Two cessation attempts simultaneously
6. **Restart after cessation**: Terminal state persists

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-7.3]
- [Source: _bmad-output/planning-artifacts/architecture.md#WR-2]
- [Source: _bmad-output/planning-artifacts/architecture.md#Payload-Type-Registry]
- [Source: src/domain/events/cessation.py] - Existing cessation events
- [Source: src/domain/events/cessation_agenda.py] - Agenda placement event
- [Source: src/application/services/event_writer_service.py] - Event writer to modify
- [Source: _bmad-output/project-context.md] - Coding standards
- [Source: _bmad-output/implementation-artifacts/stories/7-1-automatic-agenda-placement.md] - Previous story
- [Source: _bmad-output/implementation-artifacts/stories/7-2-external-observer-petition.md] - Previous story

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

1. **Tasks 1-4 were pre-implemented**: The session started with `CessationExecutedEventPayload`, schema irreversibility errors, terminal event detector port, and event type validator already created (140 tests passing).

2. **Task 5 - EventWriterService Update**: Added `TerminalEventDetectorProtocol` dependency with terminal check BEFORE halt check (TERMINAL FIRST rule). The check order is: Terminal → Halt → Lock → Verification → Write.

3. **Task 6 - Import-Time Validation**: Added `_validate_no_prohibited_event_types()` function to `src/domain/events/__init__.py` that runs on import and validates all `*_EVENT_TYPE` constants against prohibited patterns.

4. **Task 7 - Stub Implementation**: Created `TerminalEventDetectorStub` with `set_terminated()`, `clear_termination()`, and `set_terminated_simple()` methods for testing.

5. **Task 8 - Documentation**: Added NFR40 compliance documentation to `src/domain/events/__init__.py` module docstring explaining prohibited patterns and validation.

6. **Task 9 - Unit Tests**: Added `TestEventWriterServiceTerminalDetection` class to `test_event_writer_service.py` (6 tests) and created `test_terminal_event_detector_stub.py` (18 tests).

7. **Task 10 - Integration Tests**: Created `test_schema_irreversibility_integration.py` with 16 tests covering all acceptance criteria.

8. **Total Tests**: 200 tests pass for Story 7.3 components.

### File List

**New Files Created:**
- `src/infrastructure/stubs/terminal_event_detector_stub.py`
- `tests/unit/infrastructure/test_terminal_event_detector_stub.py`
- `tests/integration/test_schema_irreversibility_integration.py`

**Files Modified:**
- `src/application/services/event_writer_service.py` - Added terminal detector dependency and TERMINAL FIRST check
- `src/domain/events/__init__.py` - Added NFR40 documentation and import-time validation
- `src/infrastructure/stubs/__init__.py` - Exported `TerminalEventDetectorStub`
- `tests/unit/application/test_event_writer_service.py` - Added `TestEventWriterServiceTerminalDetection` class

**Pre-existing Files (Tasks 1-4):**
- `src/domain/events/cessation_executed.py`
- `src/domain/errors/schema_irreversibility.py`
- `src/application/ports/terminal_event_detector.py`
- `src/domain/services/event_type_validator.py`
- `tests/unit/domain/test_cessation_executed_event.py`
- `tests/unit/domain/test_event_type_validator.py`
- `tests/unit/domain/test_schema_irreversibility_errors.py`

## Change Log

- 2026-01-08: Story created - Schema irreversibility enforcement (FR40, NFR40)
- 2026-01-08: Story completed - All 10 tasks finished, 200 tests passing
