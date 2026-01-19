# Story 1.7: Fate Event Emission (Transactional)

Status: complete

---

## Story

As a **governance system**,
I want **fate events emitted in the same transaction as state updates**,
So that **fate assignment and witnessing are atomic, ensuring 100% of fate transitions are witnessed (NFR-3.3, HC-1)**.

---

## Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-2.5 | System SHALL emit fate event in same transaction as state update | P0 |
| NFR-3.3 | Event witnessing: 100% fate events persisted | CRITICAL |
| HC-1 | Fate transition requires witness event | P0 |
| CT-12 | Witnessing creates accountability | Constitutional |

---

## Acceptance Criteria

1. **AC1:** `petition.acknowledged` event emitted atomically with ACKNOWLEDGED state transition (FR-2.5)
2. **AC2:** `petition.referred` event emitted atomically with REFERRED state transition (FR-2.5)
3. **AC3:** `petition.escalated` event emitted atomically with ESCALATED state transition (FR-2.5)
4. **AC4:** If event emission fails, state change is rolled back (transactional integrity)
5. **AC5:** Event contains: petition_id, previous_state, new_state, actor_id, timestamp, reason (per story definition)
6. **AC6:** Fate events are persisted via GovernanceLedger (CT-12)
7. **AC7:** 100% of fate events are witnessed (NFR-3.3)
8. **AC8:** Unit tests cover all three fate event types
9. **AC9:** Unit tests verify transactional rollback on event emission failure
10. **AC10:** Integration tests verify events appear in ledger after fate assignment

---

## Tasks / Subtasks

- [x] **Task 1: Define Fate Event Payloads** (AC: 1, 2, 3, 5)
  - [x] Add `PETITION_ACKNOWLEDGED_EVENT_TYPE` constant to `src/domain/events/petition.py`
  - [x] Add `PETITION_REFERRED_EVENT_TYPE` constant
  - [x] Add `PETITION_ESCALATED_EVENT_TYPE` constant
  - [x] Define `PetitionFateEventPayload` dataclass with fields: petition_id, previous_state, new_state, actor_id, timestamp, reason
  - [x] Include `signable_content()` and `to_dict()` methods per pattern
  - [x] Include `schema_version` in payload (D2 - CRITICAL)

- [x] **Task 2: Extend PetitionEventEmitter Port** (AC: 6, 7)
  - [x] Add `emit_fate_event()` method signature to `PetitionEventEmitterPort`
  - [x] Method signature: `async def emit_fate_event(petition_id, previous_state, new_state, actor_id, reason) -> None`
  - [x] Method MUST raise on failure (no graceful degradation for fate events)

- [x] **Task 3: Implement Transactional Fate Event Emission** (AC: 1, 2, 3, 4, 6, 7)
  - [x] Implement `emit_fate_event()` in `PetitionEventEmitter` service
  - [x] CRITICAL: Method raises exception on failure (HC-1 - cannot silently fail)
  - [x] Map fate state to appropriate event type
  - [x] Create `GovernanceEvent` envelope with proper trace_id
  - [x] Persist to ledger via `append_event()`

- [x] **Task 4: Create Transactional Fate Assignment Service** (AC: 4)
  - [x] Create `assign_fate_transactional()` method in repository or service
  - [x] Pattern: Begin transaction → CAS state update → emit event → commit OR rollback
  - [x] If event emission fails, rollback state change
  - [x] Return updated petition on success

- [x] **Task 5: Update Stub for Testing** (AC: 8, 9)
  - [x] Extend `PetitionEventEmitterStub` with `emit_fate_event()` method
  - [x] Add `emitted_fate_events` list for tracking emitted events
  - [x] Add `fate_should_fail` flag for testing rollback behavior

- [x] **Task 6: Write Unit Tests** (AC: 8, 9)
  - [x] Test `PetitionFateEventPayload` structure and serialization
  - [x] Test `signable_content()` produces correct canonical bytes
  - [x] Test `to_dict()` includes `schema_version`
  - [x] Test emit_fate_event for ACKNOWLEDGED state
  - [x] Test emit_fate_event for REFERRED state
  - [x] Test emit_fate_event for ESCALATED state
  - [x] Test transactional rollback when event emission fails
  - [x] Test event emission failure raises exception (not returns False)

- [x] **Task 7: Write Integration Tests** (AC: 10)
  - [x] Test full fate assignment flow emits event to ledger
  - [x] Verify event content in ledger matches fate assignment
  - [x] Test concurrent fate assignments (combine with Story 1.6 CAS)
  - [x] Verify exactly one event per successful fate assignment

---

## Documentation Checklist

- [x] Inline comments explaining constitutional constraints (HC-1, CT-12, NFR-3.3)
- [x] N/A - Architecture docs (follows existing event pattern)
- [x] N/A - API docs (internal service)
- [x] N/A - README (internal component)

---

## Dev Notes

### Architecture Compliance (CRITICAL)

**From petition-system-epics.md (Story 1.7):**

> FR-2.5: System SHALL emit fate event in same transaction as state update [P0]

**Constitutional Constraints:**
- **HC-1:** Fate transition requires witness event - NO fate transition is valid without witnessed event
- **CT-12:** Witnessing creates accountability - Events MUST be persisted to GovernanceLedger
- **NFR-3.3:** Event witnessing: 100% fate events persisted [CRITICAL]

**CRITICAL DIFFERENCE from Story 1.2:**

| Story 1.2 (petition.received) | Story 1.7 (fate events) |
|------------------------------|-------------------------|
| Event emission is **optional** | Event emission is **mandatory** |
| Failure returns `False` | Failure **raises exception** |
| Petition persists without event | State change **rolled back** on failure |
| Eventual consistency acceptable | **Transactional atomicity required** |

### Event Types

**Three Fate Event Types:**
```python
PETITION_ACKNOWLEDGED_EVENT_TYPE: str = "petition.acknowledged"
PETITION_REFERRED_EVENT_TYPE: str = "petition.referred"
PETITION_ESCALATED_EVENT_TYPE: str = "petition.escalated"
```

### Event Payload Structure

**Payload Structure:**
```python
@dataclass(frozen=True)
class PetitionFateEventPayload:
    petition_id: UUID
    previous_state: str  # "RECEIVED" or "DELIBERATING"
    new_state: str       # "ACKNOWLEDGED", "REFERRED", or "ESCALATED"
    actor_id: str        # Agent or system identifier
    timestamp: datetime  # Fate assignment time (UTC)
    reason: str | None   # Optional reason code/rationale
    schema_version: int  # D2 - REQUIRED

    def signable_content(self) -> bytes: ...
    def to_dict(self) -> dict[str, Any]: ...
```

### Transactional Pattern (CRITICAL)

**Pattern for Atomic Fate Assignment:**
```python
async def assign_fate_transactional(
    self,
    submission_id: UUID,
    expected_state: PetitionState,
    new_state: PetitionState,
    actor_id: str,
    reason: str | None = None,
) -> PetitionSubmission:
    """Atomic fate assignment with witnessed event (FR-2.5, HC-1).

    This method ensures fate assignment and event emission are atomic.
    If event emission fails, the state change is rolled back.

    Raises:
        ConcurrentModificationError: If CAS fails
        EventEmissionError: If event cannot be witnessed
        PetitionAlreadyFatedError: If already in terminal state
    """
    # Step 1: Perform CAS state update (Story 1.6)
    updated_petition = await self._repo.assign_fate_cas(
        submission_id, expected_state, new_state
    )

    # Step 2: Emit fate event (MUST succeed or rollback)
    try:
        await self._event_emitter.emit_fate_event(
            petition_id=updated_petition.id,
            previous_state=expected_state,
            new_state=new_state,
            actor_id=actor_id,
            reason=reason,
        )
    except Exception as e:
        # CRITICAL: Rollback state change
        await self._repo.rollback_fate(submission_id, expected_state)
        raise EventEmissionError(
            f"Failed to witness fate event for {submission_id}"
        ) from e

    return updated_petition
```

### Implementation Notes

**NEVER DO THIS (from Story 1.2 pattern):**
```python
# WRONG - Graceful degradation is NOT allowed for fate events
try:
    await self._ledger.append_event(event)
    return True
except Exception as e:
    logger.error("Failed to emit fate event", ...)
    return False  # WRONG - must raise!
```

**CORRECT Pattern:**
```python
# CORRECT - Fail loud for fate events (HC-1)
await self._ledger.append_event(event)
# If append_event fails, exception propagates - this is correct!
# Caller handles rollback.
```

### Source Tree Components

**Modified Files:**
```
src/domain/events/petition.py                          # Add fate event types and payload
src/application/ports/petition_event_emitter.py        # Add emit_fate_event() signature
src/application/services/petition_event_emitter.py    # Implement emit_fate_event()
```

**New Files:**
```
(May need) src/domain/errors/event_emission.py         # EventEmissionError
```

**Test Files:**
```
tests/unit/domain/test_petition_events.py              # Extend with fate event tests
tests/unit/application/services/test_petition_event_emitter.py  # Extend with fate tests
tests/integration/test_fate_event_emission.py          # New integration tests
```

### FR/NFR Traceability

| Requirement | Description | Implementation |
|-------------|-------------|----------------|
| FR-2.5 | Emit fate event in same transaction as state update | Transactional pattern with rollback |
| NFR-3.3 | 100% fate events persisted | emit_fate_event raises on failure |
| HC-1 | Fate transition requires witness event | No graceful degradation |
| CT-12 | Witnessing creates accountability | Event persisted to GovernanceLedger |

### Story Dependencies

| Story | Dependency Type | What We Need |
|-------|-----------------|--------------|
| petition-1-6 | Hard dependency | `assign_fate_cas()` method for CAS |
| petition-1-2 | Pattern reference | PetitionEventEmitter service, event patterns |
| petition-1-5 | Hard dependency | State machine, terminal state detection |

### Previous Story Intelligence (petition-1-6)

**Key Learnings:**
- ConcurrentModificationError inherits from ConstitutionalViolationError
- Stub uses asyncio.Lock for simulating database row-level locking
- Triple-layer validation in assign_fate_cas(): terminal check, CAS check, transition check
- Error order matters: PetitionAlreadyFatedError before ConcurrentModificationError

**Files from 1-6 to Reference:**
- `src/domain/errors/concurrent_modification.py` - Error pattern
- `src/infrastructure/stubs/petition_submission_repository_stub.py` - CAS implementation
- `tests/unit/infrastructure/stubs/test_petition_submission_repository_stub.py` - CAS test patterns

### Previous Story Intelligence (petition-1-2)

**Key Learnings:**
- PetitionReceivedEventPayload pattern for event structure
- GovernanceEvent.create() for envelope creation
- PETITION_SYSTEM_AGENT_ID for event attribution
- CURRENT_SCHEMA_VERSION for D2 compliance
- Event emitter uses TimeAuthorityProtocol for timestamps (HARDENING-1)

**Files from 1-2 to Reference:**
- `src/domain/events/petition.py` - Event payload pattern
- `src/application/services/petition_event_emitter.py` - Emitter service pattern
- `src/infrastructure/stubs/petition_event_emitter_stub.py` - Stub pattern

### Project Context Reference

**Read:** `_bmad-output/project-context.md`

**Key Rules:**
- schema_version REQUIRED in all event payloads (D2)
- Use to_dict() not asdict() for events
- Never retry constitutional operations (D12)
- Blake3 for content hashing
- Fail loud - never catch bare Exception unless re-raising

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- All 7 tasks completed successfully
- All acceptance criteria met (AC1-AC10)
- Implementation follows constitutional constraints (FR-2.5, HC-1, NFR-3.3, CT-12)
- Transactional pattern implemented with proper rollback on event emission failure
- Unit tests cover all three fate event types and error handling
- Integration tests verify atomic state+event commitment and rollback behavior

### File List

**Modified Files:**
- `src/domain/events/petition.py` - Added fate event type constants and PetitionFateEventPayload dataclass
- `src/application/ports/petition_event_emitter.py` - Added emit_fate_event() method signature
- `src/application/services/petition_event_emitter.py` - Implemented emit_fate_event() with fail-loud pattern
- `src/application/services/petition_submission_service.py` - Added assign_fate_transactional() method
- `src/infrastructure/stubs/petition_event_emitter_stub.py` - Extended with fate event support
- `src/infrastructure/stubs/__init__.py` - Added EmittedFateEvent export
- `src/domain/errors/__init__.py` - Added FateEventEmissionError export
- `tests/unit/domain/test_petition_events.py` - Added fate event payload tests
- `tests/unit/application/services/test_petition_event_emitter.py` - Added fate event emission tests

**New Files:**
- `src/domain/errors/event_emission.py` - FateEventEmissionError exception
- `tests/unit/domain/errors/test_event_emission.py` - Error tests
- `tests/unit/application/services/test_petition_submission_service.py` - Service tests
- `tests/integration/test_fate_event_transactional.py` - Integration tests

