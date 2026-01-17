# Story consent-gov-1.4: Write-Time Validation

Status: done

---

## Story

As a **governance system**,
I want **invalid events rejected at write-time**,
so that **the ledger never contains illegal transitions or invalid data, ensuring constitutional integrity**.

---

## Acceptance Criteria

1. **AC1:** Illegal state transitions rejected before append (with specific error)
2. **AC2:** Hash chain breaks rejected before append (with specific error)
3. **AC3:** Unknown event types rejected before append (with specific error)
4. **AC4:** Unknown actors rejected before append (with specific error)
5. **AC5:** Validation returns `WriteTimeValidationError` with specific failure reason (not generic failure)
6. **AC6:** State machine resolution completes in ≤10ms (NFR-PERF-05)
7. **AC7:** Hash chain verification completes in ≤50ms
8. **AC8:** Failed validation does NOT emit any event (ledger remains unchanged)
9. **AC9:** Unit tests for each rejection case with specific error verification
10. **AC10:** Integration test verifies ledger is unchanged after rejected append

---

## Tasks / Subtasks

- [x] **Task 1: Create validation service module structure** (AC: All)
  - [x] Create `src/application/services/governance/__init__.py`
  - [x] Create `src/application/services/governance/ledger_validation_service.py`
  - [x] Create `src/domain/governance/errors/validation_errors.py`

- [x] **Task 2: Implement WriteTimeValidationError hierarchy** (AC: 5)
  - [x] Define `WriteTimeValidationError` base exception
  - [x] Define `IllegalStateTransitionError` subclass
  - [x] Define `HashChainBreakError` subclass
  - [x] Define `UnknownEventTypeError` subclass
  - [x] Define `UnknownActorError` subclass
  - [x] Include detailed context in each error (event_id, expected, actual)

- [x] **Task 3: Implement event type validation** (AC: 3)
  - [x] Create `EventTypeValidator` class
  - [x] Validate against registered event types (from story 1-1)
  - [x] Return `UnknownEventTypeError` for invalid types
  - [x] Include suggested corrections in error message

- [x] **Task 4: Implement actor validation** (AC: 4)
  - [x] Create `ActorValidator` class
  - [x] Validate actor exists in actor registry (projection)
  - [x] Return `UnknownActorError` for invalid actors
  - [x] Include actor_id in error for debugging

- [x] **Task 5: Implement hash chain validation** (AC: 2, 7)
  - [x] Create `HashChainValidator` class
  - [x] Verify `prev_hash` matches latest event's hash
  - [x] Verify computed hash matches event's `hash` field
  - [x] Return `HashChainBreakError` with expected/actual hashes
  - [x] Performance target: ≤50ms

- [x] **Task 6: Implement state transition validation** (AC: 1, 6)
  - [x] Create `StateTransitionValidator` class
  - [x] Load current state from projection
  - [x] Validate transition against state machine rules
  - [x] Return `IllegalStateTransitionError` with current_state and attempted_state
  - [x] Performance target: ≤10ms

- [x] **Task 7: Implement LedgerValidationService orchestrator** (AC: All)
  - [x] Create `LedgerValidationService` class
  - [x] Orchestrate all validators in sequence
  - [x] Fail fast on first validation error
  - [x] Return specific error type (not generic)
  - [x] Ensure atomicity: no partial writes

- [x] **Task 8: Integrate with GovernanceLedgerPort** (AC: 8)
  - [x] Modify `append_event()` to call validation first
  - [x] Ensure failed validation leaves ledger unchanged
  - [x] Add validation bypass flag for replay scenarios (admin only)

- [x] **Task 9: Write comprehensive tests** (AC: 9, 10)
  - [x] Unit test: Illegal state transition rejected
  - [x] Unit test: Hash chain break rejected
  - [x] Unit test: Unknown event type rejected
  - [x] Unit test: Unknown actor rejected
  - [x] Unit test: Specific error types returned
  - [x] Unit test: Performance ≤10ms for state machine
  - [x] Integration test: Ledger unchanged after rejection

---

## Documentation Checklist

- [x] Architecture docs updated (write-time validation layer)
- [x] Inline comments added for validation logic
- [x] N/A - API docs (internal infrastructure)
- [x] N/A - README (internal component)

---

## Dev Notes

### Architecture Compliance (CRITICAL)

**From governance-architecture.md:**

This story implements the write-time prevention layer defined in the architecture document.

**Write-Time Prevention (Locked):**

| Check | Action | Rationale |
|-------|--------|-----------|
| Illegal state transition | Reject | State machine integrity |
| Hash chain break | Reject | Ledger integrity |
| Unknown event type | Reject | Schema integrity |
| Unknown actor | Reject | Actor registry integrity |

**Code Location:** `src/application/services/governance/ledger_validation_service.py`

**Principle (CRITICAL):**
> Write-time prevention is for ledger corruption. Policy violations are observer-time.

This means:
- **Write-time (this story):** Structural integrity (hash chain, schema, state machine)
- **Observer-time (story 6-2):** Policy violations (Golden Rules, legitimacy decay)

**Response by Damage Class (Locked):**

| Violation Type | Response | Rationale |
|----------------|----------|-----------|
| Illegal transition | Reject write | Ledger is sacred |
| Hash chain break | Reject write + alert | Existential threat |
| Golden Rule violation | Emit decay event | Legitimacy erosion (NOT this story) |

### Performance Requirements (CRITICAL)

**NFR-PERF-05:** State machine resolution ≤10ms

**Budget Allocation:**

| Validation | Budget | Implementation |
|------------|--------|----------------|
| Event type lookup | ≤1ms | In-memory frozenset |
| Actor lookup | ≤3ms | Cached projection |
| Hash chain verification | ≤50ms | Async hash computation |
| State machine resolution | ≤10ms | In-memory state machine |
| **Total (worst case)** | ≤64ms | Sequential validation |

**Optimization Strategies:**
- Event type registry in memory (frozenset)
- Actor registry cached with TTL
- State machine rules are pure functions
- Hash computation is CPU-bound (no I/O)

### Existing Patterns to Follow

**Reference:** `src/domain/errors/`

The existing error hierarchy demonstrates patterns:
- Domain-specific exception classes
- Contextual error messages
- Error codes for programmatic handling

**Reference:** `src/application/services/`

Existing service patterns:
- Constructor injection for dependencies
- Async methods for I/O operations
- Protocol-based port injection

### Dependency on Stories 1-1, 1-2, 1-3

This story depends on:
- `consent-gov-1-1-event-envelope-domain-model`: `GovernanceEvent`, event type validation
- `consent-gov-1-2-append-only-ledger-port-adapter`: `GovernanceLedgerPort.append_event()`
- `consent-gov-1-3-hash-chain-implementation`: Hash verification functions

**Import:**
```python
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.events.event_types import GOVERNANCE_EVENT_TYPES
from src.domain.governance.events.hash_chain import verify_event_hash, verify_chain_link
from src.application.ports.governance.ledger_port import GovernanceLedgerPort
```

### Source Tree Components

**New Files:**
```
src/application/services/governance/
├── __init__.py
└── ledger_validation_service.py    # LedgerValidationService

src/domain/governance/errors/
├── __init__.py
└── validation_errors.py            # WriteTimeValidationError hierarchy

src/application/services/governance/validators/
├── __init__.py
├── event_type_validator.py
├── actor_validator.py
├── hash_chain_validator.py
└── state_transition_validator.py
```

**Test Files:**
```
tests/unit/application/services/governance/
├── __init__.py
├── test_ledger_validation_service.py
└── validators/
    ├── test_event_type_validator.py
    ├── test_actor_validator.py
    ├── test_hash_chain_validator.py
    └── test_state_transition_validator.py

tests/integration/governance/
└── test_validation_integration.py
```

### Technical Requirements

**Error Hierarchy:**
```python
from dataclasses import dataclass
from uuid import UUID

class WriteTimeValidationError(Exception):
    """Base exception for write-time validation failures.

    All write-time validation errors inherit from this class.
    Each subclass provides specific context for debugging.
    """
    pass

@dataclass
class IllegalStateTransitionError(WriteTimeValidationError):
    """State machine transition is not allowed."""
    event_id: UUID
    aggregate_type: str
    aggregate_id: str
    current_state: str
    attempted_state: str
    allowed_states: list[str]

    def __str__(self) -> str:
        return (
            f"Illegal state transition for {self.aggregate_type}:{self.aggregate_id}: "
            f"cannot transition from '{self.current_state}' to '{self.attempted_state}'. "
            f"Allowed transitions: {self.allowed_states}"
        )

@dataclass
class HashChainBreakError(WriteTimeValidationError):
    """Hash chain integrity violation."""
    event_id: UUID
    expected_prev_hash: str
    actual_prev_hash: str

    def __str__(self) -> str:
        return (
            f"Hash chain break detected for event {self.event_id}: "
            f"expected prev_hash={self.expected_prev_hash[:16]}..., "
            f"actual prev_hash={self.actual_prev_hash[:16]}..."
        )

@dataclass
class UnknownEventTypeError(WriteTimeValidationError):
    """Event type is not registered in the governance vocabulary."""
    event_id: UUID
    event_type: str

    def __str__(self) -> str:
        return f"Unknown event type '{self.event_type}' for event {self.event_id}"

@dataclass
class UnknownActorError(WriteTimeValidationError):
    """Actor is not registered in the actor registry."""
    event_id: UUID
    actor_id: str

    def __str__(self) -> str:
        return f"Unknown actor '{self.actor_id}' for event {self.event_id}"
```

**Validation Service Pattern:**
```python
from typing import Protocol

class EventValidator(Protocol):
    """Protocol for event validators."""

    async def validate(self, event: GovernanceEvent) -> None:
        """Validate event. Raises WriteTimeValidationError on failure."""
        ...

class LedgerValidationService:
    """Orchestrates write-time validation for governance events.

    Validates events BEFORE they are appended to the ledger.
    Implements fail-fast: stops on first validation error.

    Constitutional Constraint:
    - Write-time validation is for structural integrity
    - Policy violations are detected at observer-time (Knight)
    """

    def __init__(
        self,
        event_type_validator: EventTypeValidator,
        actor_validator: ActorValidator,
        hash_chain_validator: HashChainValidator,
        state_transition_validator: StateTransitionValidator,
    ) -> None:
        self._validators = [
            event_type_validator,      # Fast: in-memory lookup
            actor_validator,           # Fast: cached projection
            hash_chain_validator,      # Medium: hash computation
            state_transition_validator, # Fast: state machine rules
        ]

    async def validate(self, event: GovernanceEvent) -> None:
        """Validate event for write-time constraints.

        Raises:
            WriteTimeValidationError: If any validation fails

        Note: Validates in sequence, fails fast on first error.
        """
        for validator in self._validators:
            await validator.validate(event)
```

**State Transition Validator:**
```python
class StateTransitionValidator:
    """Validates state machine transitions.

    Uses projections to get current state, then validates
    against state machine rules.
    """

    def __init__(
        self,
        task_state_projection: TaskStateProjectionPort,
        legitimacy_projection: LegitimacyProjectionPort,
        # ... other projections
    ) -> None:
        self._projections = {
            "task": task_state_projection,
            "legitimacy": legitimacy_projection,
        }

    async def validate(self, event: GovernanceEvent) -> None:
        """Validate state transition is allowed."""
        aggregate_type = self._extract_aggregate_type(event)
        if aggregate_type not in self._projections:
            return  # Not a state machine event

        projection = self._projections[aggregate_type]
        current_state = await projection.get_current_state(
            self._extract_aggregate_id(event)
        )

        new_state = self._extract_new_state(event)
        allowed = self._get_allowed_transitions(current_state)

        if new_state not in allowed:
            raise IllegalStateTransitionError(
                event_id=event.metadata.event_id,
                aggregate_type=aggregate_type,
                aggregate_id=self._extract_aggregate_id(event),
                current_state=current_state,
                attempted_state=new_state,
                allowed_states=allowed,
            )
```

**Python Patterns (CRITICAL):**
- Use `dataclass` for error types (rich context)
- Use `Protocol` for validator interface
- All validation methods are async (for projection access)
- Type hints on ALL functions (mypy --strict must pass)
- Fail fast: stop on first validation error

### Testing Standards

**Test File Location:** `tests/unit/application/services/governance/test_ledger_validation_service.py`

**Test Patterns:**
```python
import pytest
from uuid import uuid4
from datetime import datetime, timezone

class TestLedgerValidationService:
    @pytest.mark.asyncio
    async def test_illegal_state_transition_rejected(self, service, make_event):
        """Illegal state transition raises IllegalStateTransitionError."""
        event = make_event(event_type="executive.task.completed")  # Skip states

        with pytest.raises(IllegalStateTransitionError) as exc_info:
            await service.validate(event)

        assert exc_info.value.current_state == "authorized"
        assert exc_info.value.attempted_state == "completed"
        assert "activated" in exc_info.value.allowed_states

    @pytest.mark.asyncio
    async def test_hash_chain_break_rejected(self, service, make_event):
        """Hash chain break raises HashChainBreakError."""
        event = make_event(prev_hash="blake3:invalid")

        with pytest.raises(HashChainBreakError) as exc_info:
            await service.validate(event)

        assert exc_info.value.actual_prev_hash == "blake3:invalid"

    @pytest.mark.asyncio
    async def test_unknown_event_type_rejected(self, service, make_event):
        """Unknown event type raises UnknownEventTypeError."""
        event = make_event(event_type="fake.branch.action")

        with pytest.raises(UnknownEventTypeError) as exc_info:
            await service.validate(event)

        assert exc_info.value.event_type == "fake.branch.action"

    @pytest.mark.asyncio
    async def test_unknown_actor_rejected(self, service, make_event):
        """Unknown actor raises UnknownActorError."""
        event = make_event(actor_id="unknown-actor-id")

        with pytest.raises(UnknownActorError) as exc_info:
            await service.validate(event)

        assert exc_info.value.actor_id == "unknown-actor-id"

    @pytest.mark.asyncio
    async def test_valid_event_passes(self, service, valid_event):
        """Valid event passes all validations without raising."""
        await service.validate(valid_event)  # Should not raise

    @pytest.mark.asyncio
    async def test_state_machine_resolution_performance(self, service, valid_event):
        """State machine resolution completes in ≤10ms."""
        import time
        start = time.perf_counter()
        await service.validate(valid_event)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms <= 10, f"State machine took {elapsed_ms}ms, limit is 10ms"
```

**Integration Test:**
```python
@pytest.mark.asyncio
async def test_ledger_unchanged_after_rejection(ledger_adapter, invalid_event):
    """Rejected event does not modify ledger."""
    initial_sequence = await ledger_adapter.get_max_sequence()

    with pytest.raises(WriteTimeValidationError):
        await ledger_adapter.append_event(invalid_event)

    final_sequence = await ledger_adapter.get_max_sequence()
    assert final_sequence == initial_sequence
```

**Coverage Requirement:** 100% for validation service

### Library/Framework Requirements

| Library | Version | Purpose |
|---------|---------|---------|
| Python | 3.11+ | Async/await, dataclasses |
| pytest | latest | Unit testing |
| pytest-asyncio | latest | Async test support |

### Project Structure Notes

**Alignment:** Creates new `src/application/services/governance/` per architecture (Step 6).

**Import Rules (Hexagonal):**
- Service imports domain models and ports
- Service does NOT import adapters directly
- Validators are injected via constructor

### References

- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Write-Time Prevention (Locked)]
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Response by Damage Class (Locked)]
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Enforcement Layer Distribution (Locked)]
- [Source: _bmad-output/planning-artifacts/government-epics.md#GOV-1-4]
- [Source: _bmad-output/project-context.md#Critical Implementation Rules]
- [Source: consent-gov-1-1-event-envelope-domain-model.md] - Dependency
- [Source: consent-gov-1-2-append-only-ledger-port-adapter.md] - Dependency
- [Source: consent-gov-1-3-hash-chain-implementation.md] - Dependency

### FR/NFR Traceability

| Requirement | Description | Implementation |
|-------------|-------------|----------------|
| AD-12 | Write-time prevention | Validation before append |
| NFR-PERF-05 | State machine ≤10ms | In-memory state machine |
| NFR-CONST-09 | No mutation except state machine | Reject illegal transitions |
| NFR-ATOMIC-01 | Atomic operations | Validate before write |

### Story Dependencies

| Story | Dependency Type | What We Need |
|-------|-----------------|--------------|
| consent-gov-1-1 | Hard dependency | `GovernanceEvent`, event type registry |
| consent-gov-1-2 | Hard dependency | `GovernanceLedgerPort` for integration |
| consent-gov-1-3 | Hard dependency | Hash verification functions |

### Design Decision: Validation vs Append Atomicity

**Decision:** Validation happens BEFORE append, not inside transaction.

**Rationale:**
- Validation may require async projection lookups
- Failed validation should not start a transaction
- Ledger append is single INSERT (already atomic)
- Separation allows validation caching/optimization

**Implementation:**
```python
# In PostgresGovernanceLedgerAdapter
async def append_event(self, event: GovernanceEvent) -> GovernanceEvent:
    # Validation first (can fail without touching DB)
    await self._validation_service.validate(event)

    # Only append if validation passed
    async with self._session_factory() as session:
        # Single INSERT, inherently atomic
        ...
```

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Session continuation from previous context after compaction

### Completion Notes List

- **All 9 tasks completed successfully**
- **92 tests passing** (unit tests for validators, orchestrator, error types, and integration tests)
- **All 10 acceptance criteria satisfied:**
  - AC1: IllegalStateTransitionError raised for illegal state transitions
  - AC2: HashChainBreakError raised for hash chain breaks
  - AC3: UnknownEventTypeError raised for unknown event types
  - AC4: UnknownActorError raised for unknown actors
  - AC5: Specific WriteTimeValidationError subclasses with detailed context
  - AC6: State machine resolution ≤10ms (verified in performance tests)
  - AC7: Hash chain verification ≤50ms (verified in performance tests)
  - AC8: Failed validation leaves ledger unchanged (verified in integration tests)
  - AC9: Comprehensive unit tests for each rejection case
  - AC10: Integration test confirms ledger unchanged after rejection

### Implementation Summary

- **WriteTimeValidationError Hierarchy:** Base exception with 4 specific subclasses (IllegalStateTransitionError, HashChainBreakError, UnknownEventTypeError, UnknownActorError), each with rich context
- **Validators:** EventTypeValidator, ActorValidator, HashChainValidator, StateTransitionValidator - all with async validate() methods and skip_validation bypass flags
- **LedgerValidationService:** Orchestrator that runs validators in performance order (fast to slow), implements fail-fast behavior
- **ValidatedGovernanceLedgerAdapter:** Decorator that wraps base adapter, validates before append, passes through read operations
- **State Machines:** Task lifecycle (pending → authorized → activated → accepted → completed) and Legitimacy bands (full ↔ provisional ↔ suspended)
- **NoOpValidationService:** Bypass validation for replay scenarios

### File List

**Source Files:**
- `src/domain/governance/errors/__init__.py`
- `src/domain/governance/errors/validation_errors.py`
- `src/application/services/governance/__init__.py`
- `src/application/services/governance/ledger_validation_service.py`
- `src/application/services/governance/validators/__init__.py`
- `src/application/services/governance/validators/event_type_validator.py`
- `src/application/services/governance/validators/actor_validator.py`
- `src/application/services/governance/validators/hash_chain_validator.py`
- `src/application/services/governance/validators/state_transition_validator.py`
- `src/infrastructure/adapters/governance/validated_ledger_adapter.py`

**Test Files:**
- `tests/unit/domain/governance/errors/__init__.py`
- `tests/unit/domain/governance/errors/test_validation_errors.py`
- `tests/unit/application/services/governance/__init__.py`
- `tests/unit/application/services/governance/test_ledger_validation_service.py`
- `tests/unit/application/services/governance/validators/__init__.py`
- `tests/unit/application/services/governance/validators/test_event_type_validator.py`
- `tests/unit/application/services/governance/validators/test_actor_validator.py`
- `tests/unit/application/services/governance/validators/test_hash_chain_validator.py`
- `tests/unit/application/services/governance/validators/test_state_transition_validator.py`
- `tests/integration/governance/__init__.py`
- `tests/integration/governance/test_validation_integration.py`

