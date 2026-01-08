# Story 7.6: Cessation as Final Recorded Event

Status: done

## Story

As an **external observer**,
I want cessation to be the final recorded event,
so that the system doesn't silently disappear.

## Acceptance Criteria

### AC1: CessationEvent as Final Event (FR43)
**Given** cessation is triggered
**When** it executes via `CessationExecutionService.execute_cessation()`
**Then** a `CessationEvent` (type: `cessation.executed`) is the final event in the store
**And** no events can be written after it
**And** the event is persisted BEFORE the freeze flag is set

### AC2: CessationEvent Content (FR43)
**Given** the cessation event
**When** I examine its payload
**Then** it includes:
  - `trigger_reason`: Human-readable reason for cessation
  - `trigger_source`: Reference to triggering event (FR37/FR38/FR39)
  - `final_sequence`: The sequence number OF this cessation event
  - `final_hash`: The hash of the event BEFORE cessation (prev_hash)
  - `is_terminal`: Always `true` (NFR40)
  - `cessation_id`: Unique UUID for this cessation
  - `execution_timestamp`: UTC timestamp of cessation
**And** the event is witnessed (CT-12)

### AC3: DB-Level Write Rejection After Cessation (FR43, NFR40)
**Given** the final event constraint
**When** any write is attempted after cessation event exists
**Then** the DB trigger rejects it with error
**And** error references cessation event sequence
**And** application layer receives `SchemaIrreversibilityError`

### AC4: prev_hash Cannot Reference Cessation Event (FR43)
**Given** the cessation event has `is_terminal: true`
**When** any new event attempts to set `prev_hash` to cessation's `content_hash`
**Then** the DB trigger rejects the write
**And** error indicates "Cannot append after terminal event"
**And** this is enforced at DB level (not just application)

### AC5: Atomic Cessation Sequence (FR43, FR41)
**Given** cessation is triggered
**When** `CessationExecutionService.execute_cessation()` runs
**Then** the sequence is:
  1. Write cessation event (BECOMES final event)
  2. Set dual-channel freeze flag (ADR-3)
  3. System enters read-only mode (FR41, FR42)
**And** if step 1 fails, no freeze flag is set (atomic)
**And** if step 2 fails, system logs CRITICAL and requires human intervention

### AC6: Terminal Event Detection (NFR40)
**Given** the `TerminalEventDetectorProtocol`
**When** `is_system_terminated()` is called after cessation
**Then** it returns `True`
**And** `get_terminal_event()` returns the cessation event
**And** this check is performed BEFORE halt check in EventWriterService

### AC7: Integration with EventWriterService (FR43)
**Given** the EventWriterService with terminal detection
**When** any write is attempted after cessation
**Then** `SchemaIrreversibilityError` is raised
**And** error message includes cessation sequence number
**And** this happens BEFORE checking halt or freeze state

## Tasks / Subtasks

- [x] **Task 1: Create/Update DB trigger for terminal event enforcement** (AC: 3,4)
  - [x] Create migration `008_terminal_event_trigger.sql`
  - [x] Created `enforce_terminal_event_constraint()` trigger function
  - [x] Add check: If any event with `payload->>'is_terminal' = 'true'` exists, reject insert
  - [x] Add check: If `prev_hash` matches a terminal event's `content_hash`, reject insert
  - [x] Return clear error message: "NFR40: Cannot write after terminal cessation event"
  - [x] Created `get_terminal_event()` and `is_system_terminated()` DB functions
  - [x] Created partial index `idx_events_terminal` for fast terminal event lookup

- [x] **Task 2: Update TerminalEventDetectorStub to real implementation** (AC: 6)
  - [x] Create `src/infrastructure/adapters/persistence/terminal_event_detector.py`
  - [x] Implemented `TerminalEventDetector` with event store query
  - [x] Implemented `InMemoryTerminalEventDetector` for testing
  - [x] Cache result after first `True` (terminal state is permanent)
  - [x] Added exports to `src/infrastructure/adapters/persistence/__init__.py`

- [x] **Task 3: Update CessationExecutionService for final event semantics** (AC: 1,2,5)
  - [x] Reviewed `src/application/services/cessation_execution_service.py`
  - [x] Verified cessation event is written BEFORE freeze flag
  - [x] Added explicit logging: "FR43: Cessation event is now the FINAL event"
  - [x] Verified `final_sequence` in payload IS the cessation event's own sequence
  - [x] Added CRITICAL log if freeze flag set fails after event write (AC5 compliance)

- [x] **Task 4: Update CessationExecutedEventPayload for trigger_source** (AC: 2)
  - [x] Updated `src/domain/events/cessation_executed.py`
  - [x] Added `trigger_source` alias property for `triggering_event_id`
  - [x] Added `trigger_reason` alias property for `reason` field
  - [x] Added `final_sequence` alias property for `final_sequence_number`
  - [x] Updated `to_dict()` to include all FR43 AC2 aliases
  - [x] Verified `signable_content()` includes all required fields

- [x] **Task 5: Integration with EventWriterService** (AC: 7)
  - [x] Verified `EventWriterService` checks terminal state FIRST (lines 313-327)
  - [x] Verified error message includes cessation sequence number
  - [x] Raises `SchemaIrreversibilityError` with NFR40 reference

- [x] **Task 6: Write unit tests** (AC: all) - **50 tests passed**
  - [x] `tests/unit/domain/test_cessation_final_event.py` (22 tests):
    - [x] TestFR43RequiredFields (7 tests) - All payload fields
    - [x] TestIsTerminalAlwaysTrue (4 tests) - NFR40 enforcement
    - [x] TestSignableContentDeterministic (5 tests) - CT-12 witnessing
    - [x] TestToDictAliases (4 tests) - FR43 AC2 aliases
    - [x] TestEventTypeConstant (2 tests)
  - [x] `tests/unit/application/test_terminal_event_detection.py` (18 tests):
    - [x] TestTerminalEventDetectorBeforeCessation (4 tests)
    - [x] TestTerminalEventDetectorAfterCessation (3 tests)
    - [x] TestTerminalEventDetectorCaching (3 tests) - NFR40 caching
    - [x] TestInMemoryTerminalEventDetector (5 tests)
    - [x] TestTerminalEventDetectorWithPayloadFieldQuery (1 test)
    - [x] TestTerminalEventDetectorTimestampExtraction (2 tests)
  - [x] `tests/unit/application/test_cessation_execution_final_event.py` (10 tests):
    - [x] TestEventWrittenBeforeFreezeFlag (2 tests)
    - [x] TestFinalSequenceIsCessationEventSequence (1 test)
    - [x] TestFreezeFlagFailureHandling (2 tests)
    - [x] TestEmptyEventStoreHandling (1 test)
    - [x] TestCessationEventPayload (3 tests)
    - [x] TestReturnValue (1 test)

- [x] **Task 7: Write integration tests** (AC: all) - **14 tests passed**
  - [x] `tests/integration/test_cessation_final_event_integration.py`:
    - [x] TestCessationIsLastEvent (2 tests) - FR43 cessation is final event
    - [x] TestCessationEventContent (4 tests) - trigger_reason, trigger_source, final_sequence, is_terminal
    - [x] TestWriteAfterCessation (1 test) - SchemaIrreversibilityError
    - [x] TestTerminalEventDetection (2 tests) - InMemoryTerminalEventDetector
    - [x] TestFreezeFlag (1 test) - Freeze flag set after cessation
    - [x] TestAtomicBehavior (1 test) - Empty store handling
    - [x] TestCessationEventWitnessed (1 test) - CT-12 witnessing
    - [x] TestCessationDetailsContent (2 tests) - Event ID and final sequence

## Dev Notes

### Relevant Architecture Patterns and Constraints

**Constitutional Constraints:**
- **FR43**: Cessation as final recorded event (not silent disappearance)
- **NFR40**: Cessation reversal is architecturally prohibited
- **CT-11**: Silent failure destroys legitimacy -> Cessation MUST be logged
- **CT-12**: Witnessing creates accountability -> Cessation event MUST be witnessed
- **CT-13**: Integrity outranks availability -> Permanent termination

**Developer Golden Rules:**
1. **TERMINAL EVENT** - `is_terminal: true` marks end of event stream
2. **EVENT BEFORE FLAG** - Cessation event written BEFORE freeze flag set
3. **DB ENFORCEMENT** - Terminal constraint enforced at DB level, not just app
4. **WITNESS EVERYTHING** - Cessation event must be witnessed (CT-12)
5. **NO REVERSAL** - No event type can undo cessation (NFR40)

### Source Tree Components to Touch

**Files to Modify:**
```
src/domain/events/cessation_executed.py        # Verify field naming for FR43
src/application/services/cessation_execution_service.py  # Add FR43 logging
migrations/YYYYMMDD_terminal_event_trigger.sql  # NEW: DB-level enforcement
```

**Files to Create:**
```
src/infrastructure/adapters/persistence/terminal_event_detector.py  # Real impl
tests/unit/domain/test_cessation_final_event.py
tests/unit/application/test_terminal_event_detection.py
tests/unit/application/test_cessation_execution_final_event.py
tests/integration/test_cessation_final_event_integration.py
```

### Related Existing Code (MUST Review)

**Story 7.3 Schema Irreversibility (Build on this):**
- `src/domain/events/cessation_executed.py` - `CessationExecutedEventPayload`
  - Already has `is_terminal: true` enforcement
  - Already has `signable_content()` for witnessing
  - Has `final_sequence_number`, `final_hash`, `reason`, `triggering_event_id`
- `src/domain/errors/schema_irreversibility.py` - Error types
  - `SchemaIrreversibilityError` - For post-cessation write attempts
  - `TerminalEventViolationError` - For terminal event detection
- `src/application/ports/terminal_event_detector.py` - Protocol
  - Already defines `is_system_terminated()`, `get_terminal_event()`
- `src/infrastructure/stubs/terminal_event_detector_stub.py` - Stub (needs real impl)

**Story 7.4 Freeze Mechanics (Complements this):**
- `src/application/services/cessation_execution_service.py` - Execution flow
  - Already writes event THEN sets freeze flag
  - Needs verification that `final_sequence` is correct
- `src/application/services/freeze_guard.py` - Freeze enforcement
- `src/domain/models/ceased_status_header.py` - Cessation details

**Story 7.5 Read-Only Access (Regression test):**
- Ensure reads still work after cessation event
- CeasedResponseMiddleware should still function

**EventWriterService (Already integrated):**
- `src/application/services/event_writer_service.py`
- Lines 313-327: Terminal check already implemented
- Checks terminal BEFORE halt BEFORE freeze (correct order)

### Design Decisions

**Why DB-Level Enforcement (not just app):**
1. Defense in depth - app layer can be bypassed
2. Consistent with hash chain enforcement (also DB trigger)
3. Prevents edge cases where app restarts without state
4. Immutable constraint - can't be disabled by config

**Why Event Before Freeze Flag:**
1. Event is the source of truth (witnessed, hashed)
2. If event write fails, system shouldn't freeze
3. If freeze fails, event still exists as proof
4. Observers can verify cessation happened even if flag state is inconsistent

**Why final_sequence Is Cessation Event's Own Sequence:**
1. Clear semantic: "This is the last sequence number"
2. Verifiable: Query events WHERE sequence > final_sequence returns empty
3. Matches FR43 requirement: cessation IS the final event

**Difference from Story 7.4 Freeze Mechanics:**
| Aspect | Story 7.4 (Freeze) | Story 7.6 (Final Event) |
|--------|-------------------|-------------------------|
| Focus | Operational freeze | Event store termination |
| Enforcement | Application layer | DB trigger |
| What it does | Blocks new writes | Prevents ANY append |
| prev_hash | Not checked | MUST NOT ref terminal |
| Error type | SystemCeasedError | SchemaIrreversibilityError |

### Testing Standards Summary

- **Async Testing**: ALL tests use `pytest.mark.asyncio` and `async def test_*`
- **Mocking**: Use `AsyncMock` for async dependencies
- **Coverage**: 80% minimum required
- **Unit Test Location**: `tests/unit/domain/`, `tests/unit/application/`
- **Integration Test Location**: `tests/integration/`

### Project Structure Notes

**Hexagonal Architecture Compliance:**
- Domain models: Pure dataclasses, no infrastructure imports
- Ports: Protocol classes in `application/ports/`
- Real adapters: In `infrastructure/adapters/` (not stubs)
- Migrations: In `migrations/` directory

**Import Rules:**
- `domain/` imports NOTHING from other layers
- `application/` imports from `domain/` only
- `infrastructure/` implements ports from `application/`
- `api/` depends on `application/` services

### Edge Cases to Test

1. **Concurrent cessation attempts**: Only one should succeed
2. **Write during cessation execution**: Should fail with clear error
3. **Cessation on empty store**: Should fail (nothing to cease)
4. **Network failure after event write**: Freeze flag may not be set, human intervention needed
5. **DB restart after cessation**: Terminal state must persist
6. **Observer query during cessation**: Should return all events including cessation
7. **prev_hash collision**: Ensure can't craft hash that bypasses check

### Previous Story Intelligence (7.5)

**Learnings from Story 7.5:**
1. **Middleware pattern works well** - CeasedResponseMiddleware was clean
2. **Test coverage goal: 50+** - Achieved 53 tests (37 unit + 16 integration)
3. **Freeze checker integration** - ObserverService already has freeze_checker
4. **FR42 compliance** - Reads always work, writes return 503

**Files created in 7.5 to build on:**
- `src/api/middleware/ceased_response.py` - Cessation header injection
- `src/api/dependencies/cessation.py` - `require_not_ceased` dependency

**Key patterns established:**
- Response headers include cessation info
- 503 with `Retry-After: never` for write rejection
- All JSON responses include `cessation_info` when ceased

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-7.6]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-12] - Crisis Response
- [Source: _bmad-output/planning-artifacts/architecture.md#NFR40] - Cessation reversal prohibited
- [Source: src/domain/events/cessation_executed.py] - CessationExecutedEventPayload
- [Source: src/domain/errors/schema_irreversibility.py] - Error types
- [Source: src/application/ports/terminal_event_detector.py] - Protocol to implement
- [Source: src/application/services/cessation_execution_service.py] - Execution flow
- [Source: src/application/services/event_writer_service.py:313-327] - Terminal check
- [Source: _bmad-output/implementation-artifacts/stories/7-5-read-only-access-after-cessation.md] - Previous story

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Unit tests: 50 passed in 0.60s
- Integration tests: 14 passed in 0.48s
- Total test coverage: 64 tests

### Completion Notes List

1. Created DB trigger migration (008_terminal_event_trigger.sql) with:
   - `enforce_terminal_event_constraint()` function
   - `get_terminal_event()` helper function
   - `is_system_terminated()` helper function
   - Partial index `idx_events_terminal` for fast lookup

2. Implemented real TerminalEventDetector:
   - Queries event store for `is_terminal: true` events
   - Caches result after first True (terminal state is permanent)
   - Includes InMemoryTerminalEventDetector for testing

3. Updated CessationExecutedEventPayload with FR43 AC2 aliases:
   - `trigger_reason` -> alias for `reason`
   - `trigger_source` -> alias for `triggering_event_id`
   - `final_sequence` -> alias for `final_sequence_number`
   - All aliases included in `to_dict()` output

4. Updated CessationExecutionService with FR43 logging:
   - "FR43: Cessation event is now the FINAL event"
   - CRITICAL log if freeze flag fails after event write

5. All acceptance criteria satisfied:
   - AC1: CessationEvent as final event
   - AC2: All payload fields present with aliases
   - AC3: DB-level write rejection
   - AC4: prev_hash cannot reference terminal event
   - AC5: Atomic cessation sequence
   - AC6: Terminal event detection
   - AC7: EventWriterService integration

### File List

**Created:**
- `migrations/008_terminal_event_trigger.sql` - DB trigger for terminal event enforcement
- `src/infrastructure/adapters/persistence/terminal_event_detector.py` - Real implementation
- `tests/unit/domain/test_cessation_final_event.py` - 22 unit tests
- `tests/unit/application/test_terminal_event_detection.py` - 18 unit tests
- `tests/unit/application/test_cessation_execution_final_event.py` - 10 unit tests
- `tests/integration/test_cessation_final_event_integration.py` - 14 integration tests

**Modified:**
- `src/infrastructure/adapters/persistence/__init__.py` - Added exports
- `src/domain/events/cessation_executed.py` - Added FR43 AC2 aliases
- `src/application/services/cessation_execution_service.py` - Added FR43 logging

## Change Log

- 2026-01-08: Story created via create-story workflow
- 2026-01-08: Implementation completed - 64 tests passing (50 unit + 14 integration)
