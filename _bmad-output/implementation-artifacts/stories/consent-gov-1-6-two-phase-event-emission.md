# Story consent-gov-1.6: Two-Phase Event Emission

Status: done

---

## Story

As a **governance system**,
I want **events emitted in two phases (intent → commit/failure)**,
So that **observers see both attempts and outcomes, making witness suppression impossible and enabling gap detection**.

---

## Acceptance Criteria

1. **AC1:** `intent_emitted` event published BEFORE operation begins
2. **AC2:** `commit_confirmed` event published on successful operation completion
3. **AC3:** `failure_recorded` event published on operation failure
4. **AC4:** Intent and outcome events linked by `correlation_id` (UUID)
5. **AC5:** No orphaned intents allowed - every intent MUST resolve to commit or failure
6. **AC6:** Orphan detection mechanism identifies unresolved intents after timeout
7. **AC7:** Hash chain gap detection triggers constitutional violation event when intent exists without outcome
8. **AC8:** Knight can observe `intent_emitted` immediately upon action initiation
9. **AC9:** `TwoPhaseEventEmitter` service encapsulates the two-phase pattern
10. **AC10:** Unit tests for both success and failure paths, plus orphan detection

---

## Tasks / Subtasks

- [ ] **Task 1: Define two-phase event types** (AC: 1, 2, 3)
  - [ ] Create `src/domain/governance/events/two_phase_events.py`
  - [ ] Define `IntentEmittedEvent` domain model
  - [ ] Define `CommitConfirmedEvent` domain model
  - [ ] Define `FailureRecordedEvent` domain model
  - [ ] Register event types in event registry

- [ ] **Task 2: Implement correlation ID linking** (AC: 4)
  - [ ] Add `correlation_id` field to two-phase events
  - [ ] Add `intent_event_id` reference in outcome events
  - [ ] Implement correlation ID generation (UUID)
  - [ ] Add validation ensuring outcome references valid intent

- [ ] **Task 3: Create TwoPhaseEventEmitter service** (AC: 1, 2, 3, 9)
  - [ ] Create `src/application/services/governance/two_phase_event_emitter.py`
  - [ ] Implement `emit_intent()` method
  - [ ] Implement `emit_commit()` method
  - [ ] Implement `emit_failure()` method
  - [ ] Implement context manager for automatic failure on exception

- [ ] **Task 4: Implement orphan prevention** (AC: 5, 6)
  - [ ] Create `OrphanIntentDetector` class
  - [ ] Define orphan timeout threshold (configurable, default 5 minutes)
  - [ ] Implement periodic orphan scan
  - [ ] Auto-emit `failure_recorded` for orphaned intents with reason

- [ ] **Task 5: Implement gap detection integration** (AC: 7, 8)
  - [ ] Integrate with hash chain verification (story 1-3)
  - [ ] Define `ledger.integrity.orphaned_intent_detected` event type
  - [ ] Emit constitutional violation event on gap detection
  - [ ] Ensure Knight can query intent-outcome pairs

- [ ] **Task 6: Create two-phase execution wrapper** (AC: 5, 9)
  - [ ] Create `TwoPhaseExecution` context manager
  - [ ] Handle success path (emit commit on `__exit__` with no exception)
  - [ ] Handle failure path (emit failure on `__exit__` with exception)
  - [ ] Ensure intent is ALWAYS emitted before operation starts

- [ ] **Task 7: Write comprehensive unit tests** (AC: 10)
  - [ ] Test intent emission before operation
  - [ ] Test commit emission on success
  - [ ] Test failure emission on exception
  - [ ] Test correlation ID linking
  - [ ] Test orphan detection
  - [ ] Test hash chain gap detection
  - [ ] Test context manager behavior

- [ ] **Task 8: Create integration tests** (AC: 8)
  - [ ] Test Knight can observe intent immediately
  - [ ] Test full two-phase lifecycle end-to-end
  - [ ] Test concurrent two-phase operations

---

## Documentation Checklist

- [ ] Architecture docs updated (two-phase emission pattern)
- [ ] Inline comments explaining Knight observability guarantees
- [ ] N/A - API docs (internal service)
- [ ] N/A - README (internal component)

---

## Dev Notes

### Architecture Compliance (CRITICAL)

**From governance-architecture.md:**

This story implements Foundation 5: Two-Phase Event Emission for Knight Observability.

**Event Lifecycle (Locked):**
```
Action initiated → intent_emitted → Action executes → commit_confirmed OR failure_recorded
```

**Knight Observes:**
- `intent_emitted` — immediately upon action initiation
- `commit_confirmed` OR `failure_recorded` — outcome

**Gap Detection:**
- If Knight misses an event, gap is detectable via hash chain discontinuity
- Hash chain gap triggers constitutional violation event

**Why Two-Phase Emission:**

| Risk | Mitigation |
|------|------------|
| Witness suppression | Events emitted BEFORE state commit; hash chain detects gaps |
| Silent failures | Failure always recorded; no silent drops |
| Action without record | Intent emitted first; action cannot proceed without record |

**Golden Rule Enforcement:**
> "Witness statements cannot be suppressed"

This is enforced by:
1. Events emitted BEFORE state commit
2. Hash chain detects gaps (missing intent OR missing outcome)
3. Orphan detection auto-resolves abandoned intents

### Two-Phase Event Types

**Intent Emitted Event:**
```python
@dataclass(frozen=True)
class IntentEmittedEvent:
    """Published BEFORE operation begins."""
    correlation_id: UUID  # Links intent to outcome
    operation_type: str   # e.g., "task.accept", "panel.convene"
    actor_id: str
    target_entity_id: str
    intent_payload: dict  # Operation-specific intent data
```

**Event Type:** `{branch}.intent.emitted`
- Example: `executive.intent.emitted`, `judicial.intent.emitted`

**Commit Confirmed Event:**
```python
@dataclass(frozen=True)
class CommitConfirmedEvent:
    """Published on successful operation completion."""
    correlation_id: UUID  # Links to intent
    intent_event_id: UUID  # Reference to IntentEmittedEvent
    operation_type: str
    result_payload: dict  # Operation-specific result data
```

**Event Type:** `{branch}.commit.confirmed`

**Failure Recorded Event:**
```python
@dataclass(frozen=True)
class FailureRecordedEvent:
    """Published on operation failure."""
    correlation_id: UUID  # Links to intent
    intent_event_id: UUID  # Reference to IntentEmittedEvent
    operation_type: str
    failure_reason: str
    failure_details: dict  # Error information
    was_orphan: bool = False  # True if auto-resolved orphan
```

**Event Type:** `{branch}.failure.recorded`

### TwoPhaseEventEmitter Service

**Service Interface:**
```python
from typing import Protocol
from uuid import UUID

class TwoPhaseEventEmitterPort(Protocol):
    """Two-phase event emission for Knight observability.

    Constitutional Guarantee:
    - Intent is ALWAYS emitted before operation begins
    - Outcome (commit/failure) is ALWAYS emitted after operation
    - No orphaned intents - auto-resolved after timeout
    """

    async def emit_intent(
        self,
        operation_type: str,
        actor_id: str,
        target_entity_id: str,
        intent_payload: dict,
    ) -> UUID:
        """Emit intent event. Returns correlation_id."""
        ...

    async def emit_commit(
        self,
        correlation_id: UUID,
        result_payload: dict,
    ) -> None:
        """Emit commit event for successful operation."""
        ...

    async def emit_failure(
        self,
        correlation_id: UUID,
        failure_reason: str,
        failure_details: dict,
    ) -> None:
        """Emit failure event for failed operation."""
        ...
```

### TwoPhaseExecution Context Manager

**Usage Pattern:**
```python
async with TwoPhaseExecution(
    emitter=two_phase_emitter,
    operation_type="task.accept",
    actor_id=actor_id,
    target_entity_id=task_id,
    intent_payload={"earl_id": earl_id},
) as execution:
    # Intent already emitted at this point
    # Knight can observe intent immediately

    result = await perform_task_acceptance(task_id)
    execution.set_result({"new_state": result.state})

# Commit emitted automatically on successful exit
# Failure emitted automatically on exception
```

**Implementation:**
```python
class TwoPhaseExecution:
    """Context manager for two-phase event emission.

    Guarantees:
    - Intent emitted on __aenter__
    - Commit emitted on successful __aexit__
    - Failure emitted on exception in __aexit__
    """

    def __init__(
        self,
        emitter: TwoPhaseEventEmitterPort,
        operation_type: str,
        actor_id: str,
        target_entity_id: str,
        intent_payload: dict,
    ) -> None:
        self._emitter = emitter
        self._operation_type = operation_type
        self._actor_id = actor_id
        self._target_entity_id = target_entity_id
        self._intent_payload = intent_payload
        self._correlation_id: UUID | None = None
        self._result_payload: dict = {}

    async def __aenter__(self) -> "TwoPhaseExecution":
        self._correlation_id = await self._emitter.emit_intent(
            operation_type=self._operation_type,
            actor_id=self._actor_id,
            target_entity_id=self._target_entity_id,
            intent_payload=self._intent_payload,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is None:
            await self._emitter.emit_commit(
                correlation_id=self._correlation_id,
                result_payload=self._result_payload,
            )
        else:
            await self._emitter.emit_failure(
                correlation_id=self._correlation_id,
                failure_reason=str(exc_val),
                failure_details={"exception_type": exc_type.__name__},
            )
        return False  # Don't suppress exceptions

    def set_result(self, result_payload: dict) -> None:
        self._result_payload = result_payload

    @property
    def correlation_id(self) -> UUID:
        return self._correlation_id
```

### Orphan Intent Detection

**Orphan Definition:**
An intent is orphaned if:
1. `intent_emitted` exists in ledger
2. No corresponding `commit_confirmed` or `failure_recorded` exists
3. Time since intent > orphan_timeout (default: 5 minutes)

**Orphan Resolution:**
```python
class OrphanIntentDetector:
    """Detects and auto-resolves orphaned intents.

    Constitutional Guarantee:
    - No intent remains unresolved indefinitely
    - Orphan resolution is logged with explicit reason
    """

    def __init__(
        self,
        ledger_port: GovernanceLedgerPort,
        emitter: TwoPhaseEventEmitterPort,
        orphan_timeout: timedelta = timedelta(minutes=5),
    ) -> None:
        self._ledger = ledger_port
        self._emitter = emitter
        self._timeout = orphan_timeout

    async def scan_and_resolve_orphans(self) -> list[UUID]:
        """Scan for orphaned intents and auto-resolve them."""
        orphaned = await self._find_orphaned_intents()
        for correlation_id in orphaned:
            await self._emitter.emit_failure(
                correlation_id=correlation_id,
                failure_reason="ORPHAN_TIMEOUT",
                failure_details={
                    "timeout_seconds": self._timeout.total_seconds(),
                    "auto_resolved": True,
                },
            )
        return orphaned
```

### Hash Chain Gap Detection

**Gap Scenarios:**
1. Intent without outcome → Orphan (handled by OrphanIntentDetector)
2. Outcome without intent → Constitutional violation (impossible if using TwoPhaseExecution)
3. Missing events in sequence → Hash chain break (handled by story 1-3)

**Integration with Story 1-3:**
```python
# When verifying hash chain, also verify two-phase completeness
async def verify_two_phase_completeness(
    ledger: GovernanceLedgerPort,
    time_authority: TimeAuthority,
    orphan_timeout: timedelta,
) -> list[TwoPhaseViolation]:
    """Verify all intents have corresponding outcomes."""
    violations = []
    intents = await ledger.read_events(event_type_pattern="*.intent.emitted")

    for intent in intents:
        correlation_id = intent.payload["correlation_id"]
        outcome = await find_outcome_for_intent(ledger, correlation_id)

        if outcome is None:
            age = time_authority.now() - intent.metadata.timestamp
            if age > orphan_timeout:
                violations.append(TwoPhaseViolation(
                    intent_event_id=intent.metadata.event_id,
                    correlation_id=correlation_id,
                    violation_type="ORPHANED_INTENT",
                ))

    return violations
```

### Existing Patterns to Follow

**Reference:** `src/domain/governance/events/event_envelope.py` (from story 1-1)

The existing `GovernanceEvent` class provides the envelope pattern for two-phase events.

**Reference:** `src/application/services/governance/ledger_validation_service.py` (from story 1-4)

The validation service pattern demonstrates how to integrate verification.

### Dependency on Story 1-1, 1-2, 1-3

This story depends on:
- `consent-gov-1-1-event-envelope-domain-model`: `GovernanceEvent`, `EventMetadata`
- `consent-gov-1-2-append-only-ledger-port-adapter`: `GovernanceLedgerPort.append_event()`
- `consent-gov-1-3-hash-chain-implementation`: Hash chain verification, `compute_event_hash()`

**Import:**
```python
from src.domain.governance.events.event_envelope import GovernanceEvent, EventMetadata
from src.application.ports.governance.ledger_port import GovernanceLedgerPort
from src.domain.governance.events.hash_chain import compute_event_hash
```

### Source Tree Components

**New Files:**
```
src/domain/governance/events/
└── two_phase_events.py                   # IntentEmitted, CommitConfirmed, FailureRecorded

src/application/ports/governance/
└── two_phase_emitter_port.py             # TwoPhaseEventEmitterPort protocol

src/application/services/governance/
├── two_phase_event_emitter.py            # TwoPhaseEventEmitter service
├── two_phase_execution.py                # TwoPhaseExecution context manager
└── orphan_intent_detector.py             # OrphanIntentDetector service
```

**Test Files:**
```
tests/unit/domain/governance/events/
└── test_two_phase_events.py

tests/unit/application/services/governance/
├── test_two_phase_event_emitter.py
├── test_two_phase_execution.py
└── test_orphan_intent_detector.py

tests/integration/governance/
└── test_two_phase_lifecycle.py
```

### Technical Requirements

**Python Patterns (CRITICAL):**
- Use `asynccontextmanager` or `__aenter__`/`__aexit__` for context manager
- All I/O operations MUST be async
- Type hints on ALL functions (mypy --strict must pass)
- Frozen dataclasses for event models
- Import from `src.domain.errors.constitutional import ConstitutionalViolationError`

**Event Type Naming:**
- Intent: `{branch}.intent.emitted`
- Commit: `{branch}.commit.confirmed`
- Failure: `{branch}.failure.recorded`

**Correlation ID Format:**
- UUID v4, generated at intent emission time
- Stored in both intent and outcome events
- Indexed for efficient lookup

### Testing Standards

**Unit Test Patterns:**
```python
import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

class TestTwoPhaseExecution:
    @pytest.mark.asyncio
    async def test_successful_execution_emits_commit(self):
        """Successful operation emits intent then commit."""
        emitter = AsyncMock()
        emitter.emit_intent.return_value = uuid4()

        async with TwoPhaseExecution(
            emitter=emitter,
            operation_type="task.accept",
            actor_id="actor-1",
            target_entity_id="task-1",
            intent_payload={},
        ) as execution:
            execution.set_result({"status": "accepted"})

        emitter.emit_intent.assert_called_once()
        emitter.emit_commit.assert_called_once()
        emitter.emit_failure.assert_not_called()

    @pytest.mark.asyncio
    async def test_failed_execution_emits_failure(self):
        """Exception during operation emits intent then failure."""
        emitter = AsyncMock()
        emitter.emit_intent.return_value = uuid4()

        with pytest.raises(ValueError):
            async with TwoPhaseExecution(
                emitter=emitter,
                operation_type="task.accept",
                actor_id="actor-1",
                target_entity_id="task-1",
                intent_payload={},
            ):
                raise ValueError("Operation failed")

        emitter.emit_intent.assert_called_once()
        emitter.emit_failure.assert_called_once()
        emitter.emit_commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_intent_emitted_before_operation(self):
        """Intent is emitted before context body executes."""
        emitter = AsyncMock()
        emitter.emit_intent.return_value = uuid4()
        call_order = []

        async with TwoPhaseExecution(
            emitter=emitter,
            operation_type="task.accept",
            actor_id="actor-1",
            target_entity_id="task-1",
            intent_payload={},
        ):
            # This runs AFTER intent is emitted
            assert emitter.emit_intent.called
            call_order.append("body")

        call_order.append("commit")
        assert call_order == ["body", "commit"]
```

**Coverage Requirement:** 100% for two-phase emission components

### Library/Framework Requirements

| Library | Version | Purpose |
|---------|---------|---------|
| Python | 3.11+ | Async context managers |
| pytest | latest | Unit testing |
| pytest-asyncio | latest | Async test support |

### Project Structure Notes

**Alignment:** Creates new two-phase emission components in `src/application/services/governance/` per architecture (Step 6).

**Import Rules (Hexagonal):**
- Domain events import nothing from other layers
- Service imports ports and domain models
- Port imports domain models only
- No circular dependencies

### References

- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Foundation 5: Two-Phase Event Emission]
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Golden Rules → Architecture Enforcement]
- [Source: _bmad-output/planning-artifacts/government-epics.md#GOV-1-6]
- [Source: _bmad-output/project-context.md#Critical Implementation Rules]
- [Source: consent-gov-1-1-event-envelope-domain-model.md] - Dependency
- [Source: consent-gov-1-2-append-only-ledger-port-adapter.md] - Dependency
- [Source: consent-gov-1-3-hash-chain-implementation.md] - Dependency

### FR/NFR Traceability

| Requirement | Description | Implementation |
|-------------|-------------|----------------|
| AD-3 | Two-phase event emission | Intent → commit/failure pattern |
| NFR-CONST-07 | Witness statements cannot be suppressed | Events emitted before state commit |
| NFR-OBS-01 | Events observable within ≤1 second | Intent published immediately |
| NFR-AUDIT-01 | All branch actions logged | Two-phase captures attempt + outcome |

### Story Dependencies

| Story | Dependency Type | What We Need |
|-------|-----------------|--------------|
| consent-gov-1-1 | Hard dependency | `GovernanceEvent`, `EventMetadata` types |
| consent-gov-1-2 | Hard dependency | `GovernanceLedgerPort.append_event()` |
| consent-gov-1-3 | Soft dependency | Hash chain verification for gap detection |

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - No debug issues encountered

### Completion Notes List

1. **All 8 tasks completed successfully** - Two-phase event emission pattern fully implemented
2. **107 tests passing** (95 unit tests + 12 integration tests)
3. **Architecture compliance verified** - All components follow hexagonal architecture (ports/adapters)
4. **Constitutional guarantees enforced**:
   - Intent ALWAYS emitted before operation begins
   - Outcome (commit/failure) ALWAYS emitted after operation
   - No orphaned intents - auto-resolved after timeout
   - Knight can observe intent_emitted immediately

### Key Implementation Decisions

1. **TimeAuthorityProtocol injection** - All timestamp access via injected protocol (HARDENING-1)
2. **In-memory pending intent tracking** - TwoPhaseEventEmitter tracks pending intents for orphan detection
3. **Correlation ID as trace_id** - Uses correlation_id as trace_id for request tracing
4. **Configurable orphan timeout** - Default 5 minutes, configurable per detector instance

### File List

**Domain Models:**
- `src/domain/governance/events/two_phase_events.py` - IntentEmittedEvent, CommitConfirmedEvent, FailureRecordedEvent
- `src/domain/governance/events/event_types.py` - Added 28 new event types for two-phase emission

**Ports:**
- `src/application/ports/governance/two_phase_emitter_port.py` - TwoPhaseEventEmitterPort protocol

**Services:**
- `src/application/services/governance/two_phase_event_emitter.py` - TwoPhaseEventEmitter service
- `src/application/services/governance/orphan_intent_detector.py` - OrphanIntentDetector service
- `src/application/services/governance/two_phase_gap_detector.py` - TwoPhaseGapDetector service
- `src/application/services/governance/two_phase_execution.py` - TwoPhaseExecution context manager

**Unit Tests:**
- `tests/unit/domain/governance/events/test_two_phase_events.py` - 25 tests
- `tests/unit/application/services/governance/test_two_phase_event_emitter.py` - 20 tests
- `tests/unit/application/services/governance/test_orphan_intent_detector.py` - 16 tests
- `tests/unit/application/services/governance/test_two_phase_gap_detector.py` - 17 tests
- `tests/unit/application/services/governance/test_two_phase_execution.py` - 17 tests

**Integration Tests:**
- `tests/integration/governance/test_two_phase_lifecycle.py` - 12 tests

