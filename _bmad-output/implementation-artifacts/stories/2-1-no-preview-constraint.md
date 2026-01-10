# Story 2.1: No Preview Constraint (FR9)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **external observer**,
I want agent outputs recorded before any human sees them,
So that I can verify no unauthorized preview or modification occurred.

## Acceptance Criteria

### AC1: Immediate Output Commitment
**Given** an agent produces a deliberation output
**When** the output is generated
**Then** it is immediately committed to the event store with a content hash
**And** a `DeliberationOutputEvent` is created with timestamp

### AC2: Hash Verification on View
**Given** a human requests to view a deliberation output
**When** they access the output
**Then** the output hash in the event store matches the displayed content
**And** the view event is logged with viewer identity

### AC3: Pre-Commit Access Denial
**Given** an output that hasn't been committed to the event store
**When** a human attempts to view it
**Then** access is denied
**And** error message includes "FR9: Output must be recorded before viewing"

### AC4: No Preview Code Path
**Given** the No Preview enforcement
**When** I examine the code path
**Then** there is no code path where output can be viewed before store commit
**And** atomic commit-then-serve is enforced

## Tasks / Subtasks

- [x] Task 1: Define DeliberationOutputEvent (AC: 1)
  - [x] 1.1 Create `src/domain/events/deliberation_output.py` with event type
  - [x] 1.2 Define `DeliberationOutputPayload` with: `output_id`, `agent_id`, `content_hash`, `content_type`, `raw_content`
  - [x] 1.3 Register event type in event registry (if exists) or document in constants
  - [x] 1.4 Add unit tests for payload validation

- [x] Task 2: Create NoPreviewEnforcer Domain Service (AC: 3, 4)
  - [x] 2.1 Create `src/domain/services/no_preview_enforcer.py`
  - [x] 2.2 Implement `mark_committed()` and `is_committed()` methods
  - [x] 2.3 Implement `verify_committed(output_id: UUID) -> bool` method
  - [x] 2.4 Raise `FR9ViolationError` if uncommitted output is accessed
  - [x] 2.5 Add unit tests for enforcer logic (13 tests)

- [x] Task 3: Create OutputViewEvent for Audit Trail (AC: 2)
  - [x] 3.1 Create `src/domain/events/output_view.py` with event type
  - [x] 3.2 Define `OutputViewPayload` with: `output_id`, `viewer_id`, `viewer_type`, `viewed_at`
  - [x] 3.3 Add unit tests for view event creation (10 tests)

- [x] Task 4: Create DeliberationOutputPort (AC: 1, 2)
  - [x] 4.1 Create `src/application/ports/deliberation_output.py`
  - [x] 4.2 Define `DeliberationOutputPort` protocol with:
        - `store_output(output: DeliberationOutputPayload, event_sequence: int) -> StoredOutput`
        - `get_output(output_id: UUID) -> DeliberationOutputPayload | None`
        - `verify_hash(output_id: UUID, expected_hash: str) -> bool`
  - [x] 4.3 Add unit tests for port interface (8 tests)

- [x] Task 5: Create DeliberationOutputService Application Layer (AC: 1, 2, 3, 4)
  - [x] 5.1 Create `src/application/services/deliberation_output_service.py`
  - [x] 5.2 Inject `HaltChecker`, `NoPreviewEnforcer`, `DeliberationOutputPort`
  - [x] 5.3 Implement `commit_and_store(payload: DeliberationOutputPayload) -> CommittedOutput`:
        - Check halt state (HALT FIRST rule)
        - Store output via port
        - Mark as committed in enforcer
        - Return committed output reference
  - [x] 5.4 Implement `get_for_viewing(output_id: UUID, viewer_id: str) -> ViewableOutput | None`:
        - Check halt state (HALT FIRST rule)
        - Verify output is committed (FR9 enforcement)
        - Retrieve from storage
        - Verify hash matches (integrity check)
        - Return output only after all checks pass
  - [x] 5.5 Add unit tests for service (9 tests)

- [x] Task 6: Create Stub Infrastructure Implementation (AC: 1, 2)
  - [x] 6.1 Create `src/infrastructure/stubs/deliberation_output_stub.py`
  - [x] 6.2 Implement `DeliberationOutputStub` with in-memory storage for dev
  - [x] 6.3 Follow watermark pattern from `DevHSM` for dev mode indication
  - [x] 6.4 Add unit tests for stub implementation (8 tests)

- [x] Task 7: FR9 Compliance Verification Tests (AC: 4)
  - [x] 7.1 Create `tests/integration/test_no_preview_constraint.py`
  - [x] 7.2 Test: Cannot view output before commit (expect FR9ViolationError)
  - [x] 7.3 Test: Hash mismatch detected and rejected
  - [x] 7.4 Test: View event logged after successful retrieval
  - [x] 7.5 Test: Atomic failure if event write fails mid-commit (8 integration tests)

## Dev Notes

### Critical Architecture Context

**FR9: No Preview Constraint**
From the PRD, FR9 states: "Agent outputs are recorded before any human sees them." This is the foundational constitutional constraint for Epic 2. It ensures external observers can verify that no unauthorized preview or modification occurred between agent generation and human viewing.

**ADR-2: Context Bundles (Format + Integrity)**
The architecture mandates signed JSON context bundles with canonical serialization. While ADR-2 primarily covers input contexts to agents, the same principles apply to output: deterministic hashing, signature verification, and content-addressed references.

**Constitutional Truths Honored:**
- **CT-11:** Silent failure destroys legitimacy → If commit fails, output MUST NOT be viewable
- **CT-12:** Witnessing creates accountability → Both output commit and view access are witnessed events
- **CT-13:** Integrity outranks availability → Better to deny access than serve potentially modified content

### Previous Epic Intelligence (Epic 1 Patterns)

From Epic 1 implementation, the following patterns are established and MUST be followed:

**1. Event Creation Pattern:**
Use `Event.create_with_hash()` factory method from `src/domain/events/event.py`:
```python
event = Event.create_with_hash(
    sequence=next_seq,
    event_type="deliberation.output",
    payload={"output_id": str(output_id), ...},
    signature=signature,
    witness_id=witness_id,
    witness_signature=witness_signature,
    local_timestamp=datetime.now(timezone.utc),
    previous_content_hash=prev_hash,
    signing_key_id=key_id,
)
```

**2. Witness Attribution Pattern:**
All events require witness attribution (FR1). Use `WitnessService` from `src/application/services/witness_service.py`:
```python
witness = await witness_service.select_witness()
witness_sig = await witness_service.get_witness_signature(event_bytes)
```

**3. Atomic Event Writing:**
Use `EventWriterService` from `src/application/services/event_writer_service.py`:
```python
async with atomic_event_writer.write_atomically(event) as committed_event:
    # Event is committed atomically with witness
    ...
```

**4. Port/Adapter Pattern:**
- Ports in `src/application/ports/` define abstract interfaces
- Stubs in `src/infrastructure/stubs/` provide development implementations
- Follow the `EventStorePort` and `HaltChecker` patterns

**5. Error Domain Pattern:**
Create domain-specific errors in `src/domain/errors/`:
```python
class FR9ViolationError(ConstitutionalViolationError):
    """Raised when No Preview constraint (FR9) is violated."""
    pass
```

**6. Code Review Fixes from 1-10:**
- Use `tuple[...]` instead of `list[...]` in frozen dataclasses for true immutability
- Avoid mutable default arguments

### Hash Verification Pattern

For content hash verification, use the established pattern from `src/domain/events/hash_utils.py`:
```python
from src.domain.events.hash_utils import compute_content_hash

computed = compute_content_hash(output_content)
if computed != stored_hash:
    raise FR9ViolationError("Content hash mismatch - potential tampering detected")
```

### Atomic Commit-Then-Serve Implementation

The critical requirement is that NO code path exists where output can be viewed before store commit. This requires:

1. **Synchronous Event Write:** The `commit_and_store` method MUST complete event writing before returning
2. **No Caching:** Output content MUST NOT be cached or returned until event is confirmed committed
3. **Halt Check:** Always check halt state before operations (follow `HaltGuard` pattern)
4. **Failure Handling:** If commit fails, raise exception - never return partial results

```python
async def commit_and_store(self, agent_output: AgentOutput) -> CommittedOutput:
    # HALT CHECK FIRST (Golden Rule #1)
    await self._halt_checker.check_halted()

    # Generate content hash BEFORE any storage
    content_hash = compute_content_hash(agent_output.content)

    # Create event with hash
    event = self._create_deliberation_output_event(
        output=agent_output,
        content_hash=content_hash,
    )

    # Atomic write - this blocks until confirmed
    committed_event = await self._event_writer.write(event)

    # ONLY after confirmed commit, create output reference
    return CommittedOutput(
        output_id=agent_output.output_id,
        event_sequence=committed_event.sequence,
        content_hash=content_hash,
        committed_at=committed_event.authority_timestamp,
    )
```

### Project Structure Notes

**Files to Create:**
```
src/
├── domain/
│   ├── events/
│   │   ├── deliberation_output.py      # DeliberationOutputEvent, payload
│   │   └── output_view.py              # OutputViewEvent, payload
│   ├── errors/
│   │   └── no_preview.py               # FR9ViolationError
│   └── services/
│       └── no_preview_enforcer.py      # Domain logic for enforcement
├── application/
│   ├── ports/
│   │   └── deliberation_output.py      # Port interface
│   └── services/
│       └── deliberation_output_service.py  # Application service
└── infrastructure/
    └── stubs/
        └── deliberation_output_stub.py # Dev stub

tests/
├── unit/
│   ├── domain/
│   │   ├── test_deliberation_output_event.py
│   │   ├── test_output_view_event.py
│   │   └── test_no_preview_enforcer.py
│   └── application/
│       └── test_deliberation_output_service.py
└── integration/
    └── test_no_preview_constraint.py
```

**Alignment with Hexagonal Architecture:**
- Domain layer (`domain/`) has NO infrastructure imports
- Application layer (`application/`) orchestrates domain and uses ports
- Infrastructure layer (`infrastructure/`) implements adapters for ports
- Import boundary enforcement from Story 0-6 MUST be respected

### Testing Standards

Per `project-context.md`:
- ALL test files use `pytest.mark.asyncio`
- Use `async def test_*` for async tests
- Use `AsyncMock` not `Mock` for async functions
- Unit tests in `tests/unit/{module}/test_{name}.py`
- Integration tests in `tests/integration/test_{feature}_integration.py`
- 80% minimum coverage

### Library/Framework Requirements

**Required Dependencies (already installed in Epic 0):**
- `structlog` for logging (NO print statements, NO f-strings in logs)
- `pytest-asyncio` for async testing
- `pydantic` for data validation (if using Pydantic models)

**Do NOT add new dependencies without explicit approval.**

### Security Considerations

**No Silent Paths (CT-12):**
Every access to deliberation output must be logged as an event. The view event creates an audit trail that can be independently verified by external observers.

**Hash Integrity (FR9):**
- Content hash MUST be computed BEFORE any storage
- Hash algorithm version MUST be tracked (use `HASH_ALG_VERSION` from `hash_utils.py`)
- Any hash mismatch is a potential constitutional violation

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.1: No Preview Constraint]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-002]
- [Source: _bmad-output/project-context.md]
- [Source: src/domain/events/event.py] - Event entity pattern
- [Source: src/domain/events/hash_utils.py] - Hash computation utilities
- [Source: src/application/services/event_writer_service.py] - Writer service pattern
- [Source: src/application/ports/event_store.py] - Port pattern reference
- [Source: _bmad-output/implementation-artifacts/stories/1-10-replica-configuration-preparation.md] - Previous story learnings

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - All tests passed on first implementation round.

### Completion Notes List

1. **DeliberationOutputPayload Created:** Frozen dataclass with output_id, agent_id, content_hash, content_type, raw_content fields. Validates UUID, non-empty strings, and 64-char hash length.

2. **DELIBERATION_OUTPUT_EVENT_TYPE Constant:** Event type `deliberation.output` follows lowercase.dot.notation convention.

3. **FR9ViolationError Created:** Domain error extending ConstitutionalViolationError for No Preview constraint violations.

4. **NoPreviewEnforcer Domain Service:** Tracks committed outputs in memory, enforces FR9 with `verify_committed()` and `enforce_no_preview()` methods. Supports hash verification.

5. **OutputViewPayload Created:** Frozen dataclass for audit trail with output_id, viewer_id, viewer_type, viewed_at fields. Event type `output.view`.

6. **DeliberationOutputPort Interface:** Abstract protocol with `store_output()`, `get_output()`, `verify_hash()` methods. StoredOutput dataclass for return values.

7. **DeliberationOutputService:** Application service orchestrating FR9 compliance. `commit_and_store()` and `get_for_viewing()` methods implement atomic commit-then-serve pattern with HALT FIRST rule.

8. **DeliberationOutputStub:** In-memory stub implementation with DEV_MODE_WATERMARK for development/testing. Implements full port interface.

9. **65 Tests Total:** 9 DeliberationOutputPayload, 13 NoPreviewEnforcer, 10 OutputViewPayload, 8 Port, 9 Service, 8 Stub, 8 Integration tests. All pass.

### File List

**Created:**
- `src/domain/events/deliberation_output.py` - DeliberationOutputPayload, event type constant
- `src/domain/events/output_view.py` - OutputViewPayload, event type constant
- `src/domain/errors/no_preview.py` - FR9ViolationError
- `src/domain/services/__init__.py` - Domain services package init
- `src/domain/services/no_preview_enforcer.py` - NoPreviewEnforcer domain service
- `src/application/ports/deliberation_output.py` - StoredOutput, DeliberationOutputPort
- `src/application/services/deliberation_output_service.py` - CommittedOutput, ViewableOutput, DeliberationOutputService
- `src/infrastructure/stubs/deliberation_output_stub.py` - DeliberationOutputStub
- `tests/unit/domain/test_deliberation_output_event.py` - 9 tests
- `tests/unit/domain/test_no_preview_enforcer.py` - 13 tests
- `tests/unit/domain/test_output_view_event.py` - 10 tests
- `tests/unit/application/test_deliberation_output_port.py` - 8 tests
- `tests/unit/application/test_deliberation_output_service.py` - 9 tests
- `tests/unit/infrastructure/test_deliberation_output_stub.py` - 8 tests
- `tests/integration/test_no_preview_constraint.py` - 8 tests

**Modified:**
- None

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-06 | Story created with comprehensive context from Epic 2 analysis and Epic 1 learnings | SM Agent (Claude Opus 4.5) |
| 2026-01-06 | All 7 tasks completed: domain events, errors, services, ports, application service, stub, integration tests (65 tests total) | Dev Agent (Claude Opus 4.5) |
| 2026-01-06 | **Code Review APPROVED**: All ACs verified, all tasks confirmed complete, 65/65 tests pass. Fixed 4 linting issues (quoted type annotations, import sorting, unused import). | Code Review (Claude Opus 4.5) |
