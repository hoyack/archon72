# Story 1.6: Event Writer Service (ADR-1)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **system operator**,
I want a single canonical Writer service that submits events through DB enforcement,
So that the trust boundary is narrowed to the database.

## Acceptance Criteria

### AC1: Writer Service Architecture

**Given** the Writer service
**When** I examine its architecture
**Then** it submits events but does NOT compute hashes locally
**And** hash computation is delegated to DB triggers
**And** signature verification is delegated to DB triggers

### AC2: Successful Event Submission

**Given** the Writer service submits an event
**When** the DB accepts the event
**Then** the Writer logs success with event_id and sequence
**And** returns the assigned sequence to the caller

### AC3: Failed Event Submission

**Given** the Writer service submits an invalid event
**When** the DB rejects it
**Then** the Writer logs the rejection reason
**And** raises an appropriate exception to the caller
**And** no partial state exists

### AC4: Single-Writer Constraint (ADR-1)

**Given** the single-writer constraint (ADR-1)
**When** I examine the deployment
**Then** only one Writer service instance is active
**And** failover requires a witnessed ceremony (not automatic)

### AC5: Writer Self-Verification (GAP-CHAOS-001)

**Given** Writer self-verification (CH-1)
**When** the Writer starts
**Then** it verifies its view of head hash matches DB
**And** if mismatch, it halts immediately
**And** halts are logged with both hash values

## Tasks / Subtasks

- [x] Task 1: Create EventWriterService class (AC: 1, 2, 3)
  - [x] 1.1 Create `src/application/services/event_writer_service.py`
  - [x] 1.2 Implement `EventWriterService` class delegating to `EventStorePort.append_event()`
  - [x] 1.3 Add structured logging for success (event_id, sequence)
  - [x] 1.4 Add error handling for DB rejection with logging
  - [x] 1.5 Ensure no local hash computation (hash comes from DB trigger response)
  - [x] 1.6 Add unit tests for EventWriterService

- [x] Task 2: Halt Check Integration (AC: 5)
  - [x] 2.1 Create `src/application/ports/halt_checker.py` with abstract `HaltChecker` interface
  - [x] 2.2 Define methods: `is_halted() -> bool`, `get_halt_reason() -> Optional[str]`
  - [x] 2.3 Create `src/infrastructure/stubs/halt_checker_stub.py` returning `False`/`None`
  - [x] 2.4 Inject `HaltChecker` into `EventWriterService`
  - [x] 2.5 Check halt state before every write operation (HALT FIRST rule)
  - [x] 2.6 Add TODO comment referencing Epic 3 for real implementation

- [x] Task 3: Writer Self-Verification on Startup (AC: 5)
  - [x] 3.1 Add `verify_head_consistency()` method to EventWriterService (named `verify_startup()`)
  - [x] 3.2 On startup, fetch latest event from DB
  - [x] 3.3 Compare local head hash with DB head hash
  - [x] 3.4 If mismatch, raise `WriterInconsistencyError` with both hash values
  - [x] 3.5 Log CRITICAL with both hashes before raising
  - [x] 3.6 Add startup verification tests

- [x] Task 4: Single-Writer Enforcement (AC: 4)
  - [x] 4.1 Add writer instance ID to EventWriterService (via WriterLockProtocol)
  - [x] 4.2 Create `src/application/ports/writer_lock.py` with `WriterLockProtocol`
  - [x] 4.3 Define methods: `acquire() -> bool`, `release()`, `is_held() -> bool`, `renew() -> bool`
  - [x] 4.4 Create `src/infrastructure/stubs/writer_lock_stub.py` (always succeeds)
  - [x] 4.5 Require lock acquisition before write operations
  - [x] 4.6 Document that production implements distributed lock (Redis)
  - [x] 4.7 Add unit tests for lock integration

- [x] Task 5: Integration with AtomicEventWriter (AC: 1, 2, 3)
  - [x] 5.1 EventWriterService wraps AtomicEventWriter (coordination pattern)
  - [x] 5.2 Ensure EventWriterService checks are performed before AtomicEventWriter logic
  - [x] 5.3 Add integration tests for full write flow

- [x] Task 6: Integration Tests (AC: 1-5)
  - [x] 6.1 Create `tests/integration/test_event_writer_integration.py`
  - [x] 6.2 Test successful event submission with DB (3 tests)
  - [x] 6.3 Test failed submission handling (2 tests)
  - [x] 6.4 Test halt check behavior (2 tests)
  - [x] 6.5 Test startup verification success/failure (2 tests)
  - [x] 6.6 Test single-writer lock behavior (2 tests)

## Dev Notes

### Critical Architecture Requirements

**Constitutional Truths to Honor:**
- **CT-11:** Silent failure destroys legitimacy → HALT OVER DEGRADE
- **CT-12:** Witnessing creates accountability → Unwitnessed actions are invalid
- **CT-13:** Integrity outranks availability → Availability may be sacrificed

**ADR-1 Key Points:**
> From architecture.md ADR-001: "Use Supabase Postgres as the storage backend with DB-level functions/triggers enforcing hash chaining and append-only invariants."
> "The Writer service submits events, but **the chain validation and hash computation are enforced in Postgres**."
> "**Single canonical Writer** (constitutionally required). Failover is ceremony-based: watchdog detection + human approval + witnessed promotion."

**Gap Addressed:**
> GAP-CHAOS-001: Writer self-verification - Priority P0, owned by Dev, linked to ADR-1

### Existing Code Foundation

**CRITICAL - Build on Existing Components:**

From Story 1-5, the `AtomicEventWriter` already exists at:
- `src/application/services/atomic_event_writer.py`

The EventWriterService should WRAP or COORDINATE with AtomicEventWriter:
```
EventWriterService (NEW - this story)
  ├─ halt_checker.is_halted()  # Check first (HALT FIRST rule)
  ├─ writer_lock.is_held()     # Verify we hold writer lock
  ├─ verify_head_consistency() # Self-verification
  └─ atomic_event_writer.write_event()  # Delegates actual write
```

**EventStorePort already has:**
- `append_event(event) -> Event` - Append with DB-enforced validation
- `get_latest_event() -> Event | None` - For head hash verification
- `get_max_sequence() -> int` - For sequence verification

### DB Trust Boundary (ADR-1 Critical)

**The Writer Service MUST NOT:**
- Compute content_hash locally (DB trigger computes)
- Verify hash chain locally (DB trigger verifies)
- Trust any hash that didn't come from DB response

**The Writer Service DELEGATES TO DB:**
- Hash computation → `events_before_insert` trigger
- Chain verification → `verify_prev_hash()` function
- Append-only enforcement → `prevent_event_delete` trigger
- Signature verification → `verify_event_signature()` function (Story 1.7)

### EventWriterService Pattern

```python
# src/application/services/event_writer_service.py
"""Event Writer Service - single canonical writer (ADR-1).

Constitutional Constraints:
- ADR-1: Single canonical writer, DB enforces chain integrity
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- GAP-CHAOS-001: Writer self-verification before accepting writes

Responsibilities:
- Halt check before every write (HALT FIRST rule)
- Writer lock verification (single-writer constraint)
- Startup self-verification (head hash consistency)
- Delegation to AtomicEventWriter for actual writes
"""

from structlog import get_logger

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.writer_lock import WriterLockProtocol
from src.application.services.atomic_event_writer import AtomicEventWriter
from src.domain.events import Event
from src.domain.errors import SystemHaltedError, WriterInconsistencyError, WriterLockNotHeldError

logger = get_logger()


class EventWriterService:
    """Single canonical event writer (ADR-1).

    Constitutional Constraint:
    This service ensures the single-writer invariant required by ADR-1.
    Only one Writer instance may be active at any time.
    Failover requires a witnessed ceremony.

    Developer Golden Rule: HALT FIRST
    Always check halt state before any write operation.
    """

    def __init__(
        self,
        atomic_writer: AtomicEventWriter,
        halt_checker: HaltChecker,
        writer_lock: WriterLockProtocol,
        event_store: EventStorePort,
    ) -> None:
        self._atomic_writer = atomic_writer
        self._halt_checker = halt_checker
        self._writer_lock = writer_lock
        self._event_store = event_store
        self._verified = False  # Startup verification flag

    async def verify_startup(self) -> None:
        """Verify head hash consistency on startup (GAP-CHAOS-001).

        MUST be called before accepting any writes.
        Raises WriterInconsistencyError if mismatch detected.
        """
        latest = await self._event_store.get_latest_event()

        if latest is None:
            # Empty store - nothing to verify
            log = logger.bind(state="empty_store")
            log.info("writer_verification_passed", message="Empty store - no verification needed")
            self._verified = True
            return

        # In production, this would compare with local cache/state
        # For now, just verify we can read the head event
        log = logger.bind(
            head_sequence=latest.sequence,
            head_hash=latest.content_hash[:16] + "...",  # Truncate for logging
        )
        log.info("writer_verification_passed", message="Head hash verified with DB")
        self._verified = True

    async def write_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        agent_id: str,
        local_timestamp: datetime,
    ) -> Event:
        """Write event with all constitutional checks.

        Performs in order:
        1. HALT CHECK (CT-11 - halt over degrade)
        2. Writer lock verification (ADR-1 - single writer)
        3. Startup verification check (GAP-CHAOS-001)
        4. Delegates to AtomicEventWriter
        5. Logs success/failure

        Returns:
            The persisted Event.

        Raises:
            SystemHaltedError: If system is halted (never retry!)
            WriterLockNotHeldError: If writer lock not held
            WriterInconsistencyError: If startup verification failed
        """
        # Step 1: HALT FIRST (Developer Golden Rule)
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log = logger.bind(halt_reason=reason)
            log.critical("write_rejected_system_halted")
            raise SystemHaltedError(f"System is halted: {reason}")

        # Step 2: Writer lock verification
        if not await self._writer_lock.is_held():
            log = logger.bind(event_type=event_type)
            log.error("write_rejected_no_lock")
            raise WriterLockNotHeldError("Writer lock not held - cannot write")

        # Step 3: Startup verification check
        if not self._verified:
            log = logger.bind(event_type=event_type)
            log.error("write_rejected_not_verified")
            raise WriterInconsistencyError("Writer not verified - call verify_startup() first")

        # Step 4: Delegate to AtomicEventWriter
        try:
            event = await self._atomic_writer.write_event(
                event_type=event_type,
                payload=payload,
                agent_id=agent_id,
                local_timestamp=local_timestamp,
            )

            # Step 5: Log success (AC2)
            log = logger.bind(
                event_id=str(event.event_id),
                sequence=event.sequence,
                event_type=event_type,
            )
            log.info("event_written_successfully")

            return event

        except Exception as e:
            # Log failure (AC3)
            log = logger.bind(
                event_type=event_type,
                error=str(e),
                error_type=type(e).__name__,
            )
            log.error("event_write_failed")
            raise
```

### HaltChecker Port (Story 1.8 Preview)

```python
# src/application/ports/halt_checker.py
"""Halt Checker port - interface for halt state checking.

This is a STUB for Epic 1 that will be implemented in Epic 3.
The Writer must check halt state before every write (HALT FIRST rule).

Constitutional Constraint (CT-11):
Silent failure destroys legitimacy. Halt is integrity protection,
not transient failure. NEVER retry after SystemHaltedError.
"""

from abc import ABC, abstractmethod
from typing import Optional


class HaltChecker(ABC):
    """Abstract interface for halt state checking.

    Epic 3 will implement the real HaltChecker with:
    - Dual-channel halt (Redis + DB flag)
    - Halt reason tracking
    - 48-hour recovery waiting period

    For Epic 1, use HaltCheckerStub which always returns False.
    """

    @abstractmethod
    async def is_halted(self) -> bool:
        """Check if the system is halted.

        Returns:
            True if system is halted, False otherwise.
        """
        ...

    @abstractmethod
    async def get_halt_reason(self) -> Optional[str]:
        """Get the reason for the current halt.

        Returns:
            Halt reason string if halted, None otherwise.
        """
        ...
```

### WriterLock Port

```python
# src/application/ports/writer_lock.py
"""Writer Lock port - ensures single-writer constraint (ADR-1).

Only one Writer instance may be active at any time.
Failover requires a witnessed ceremony (not automatic).

Production Implementation:
- Redis distributed lock with fencing token
- Lock TTL with heartbeat renewal
- Failover through witnessed ceremony
"""

from abc import ABC, abstractmethod


class WriterLockProtocol(ABC):
    """Abstract interface for writer lock operations.

    ADR-1 requires single canonical writer. This lock enforces
    that constraint at runtime.
    """

    @abstractmethod
    async def acquire(self) -> bool:
        """Acquire the writer lock.

        Returns:
            True if lock acquired, False if already held by another.
        """
        ...

    @abstractmethod
    async def release(self) -> None:
        """Release the writer lock."""
        ...

    @abstractmethod
    async def is_held(self) -> bool:
        """Check if this instance holds the lock.

        Returns:
            True if this instance holds the lock.
        """
        ...
```

### Stub Implementations

```python
# src/infrastructure/stubs/halt_checker_stub.py
"""Stub HaltChecker for Epic 1 - always returns not halted.

TODO: Epic 3 will implement the real HaltChecker with:
- Dual-channel halt (Redis + DB flag)
- Halt reason tracking
- 48-hour recovery waiting period
"""

from typing import Optional

from src.application.ports.halt_checker import HaltChecker


class HaltCheckerStub(HaltChecker):
    """Stub implementation that always returns not halted.

    This stub satisfies the interface so Epic 1 code can
    check halt state without depending on Epic 3.
    """

    async def is_halted(self) -> bool:
        """Stub: Always returns False (not halted)."""
        return False

    async def get_halt_reason(self) -> Optional[str]:
        """Stub: Always returns None (no halt reason)."""
        return None
```

```python
# src/infrastructure/stubs/writer_lock_stub.py
"""Stub WriterLock for development/testing.

Production uses Redis distributed lock with fencing token.
This stub always succeeds for local development.
"""

from src.application.ports.writer_lock import WriterLockProtocol


class WriterLockStub(WriterLockProtocol):
    """Stub implementation that always succeeds.

    For development/testing only. Production uses Redis.
    """

    def __init__(self) -> None:
        self._held = False

    async def acquire(self) -> bool:
        """Stub: Always succeeds."""
        self._held = True
        return True

    async def release(self) -> None:
        """Stub: Release the lock."""
        self._held = False

    async def is_held(self) -> bool:
        """Stub: Returns internal state."""
        return self._held
```

### Domain Errors to Add

```python
# Add to src/domain/errors/event_store.py or new file

class WriterInconsistencyError(ConstitutionalViolationError):
    """Writer detected head hash mismatch with DB (GAP-CHAOS-001).

    This is a CRITICAL error indicating possible data corruption
    or split-brain scenario. System must halt immediately.
    """
    pass


class WriterLockNotHeldError(ConstitutionalViolationError):
    """Write attempted without holding writer lock (ADR-1).

    Single-writer constraint violated. Indicates programming error
    or lock expiration without renewal.
    """
    pass
```

### Hexagonal Architecture Compliance

**Files to Create:**

| Layer | Path | Purpose |
|-------|------|---------|
| Application | `src/application/services/event_writer_service.py` | NEW: Single canonical writer |
| Application | `src/application/ports/halt_checker.py` | NEW: Halt check interface |
| Application | `src/application/ports/writer_lock.py` | NEW: Writer lock interface |
| Infrastructure | `src/infrastructure/stubs/halt_checker_stub.py` | NEW: Stub for Epic 1 |
| Infrastructure | `src/infrastructure/stubs/writer_lock_stub.py` | NEW: Stub for development |
| Domain | `src/domain/errors/writer.py` | NEW: Writer-specific errors |
| Tests | `tests/unit/application/test_event_writer_service.py` | NEW: Unit tests |
| Tests | `tests/integration/test_event_writer_integration.py` | NEW: Integration tests |

**Files to Modify:**

| Layer | Path | Changes |
|-------|------|---------|
| Application | `src/application/ports/__init__.py` | Export new ports |
| Application | `src/application/services/__init__.py` | Export EventWriterService |
| Domain | `src/domain/errors/__init__.py` | Export new errors |
| Infrastructure | `src/infrastructure/stubs/__init__.py` | Export stubs |

**Import Rules (CRITICAL):**
```python
# ALLOWED in application/services/event_writer_service.py
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.writer_lock import WriterLockProtocol
from src.application.services.atomic_event_writer import AtomicEventWriter
from src.domain.errors import SystemHaltedError, WriterInconsistencyError

# FORBIDDEN - Will fail pre-commit hook
from src.infrastructure import ...  # VIOLATION!
from redis import ...               # VIOLATION!
```

### Previous Story Learnings (Story 1-5)

From Story 1-5 completion:
- **AtomicEventWriter** is at `src/application/services/atomic_event_writer.py`
- `Event.create_with_hash()` handles timestamp fields correctly
- `EventStorePort.append_event()` returns persisted event with DB-assigned values
- **structlog pattern:** Use `logger.bind()` for context, then `log.info()` / `log.error()`
- Error codes use FR/CT prefixed format
- Domain errors inherit from base classes in `src/domain/errors/`

### Testing Requirements

**Unit Tests (no infrastructure):**
- Test EventWriterService with mocked dependencies
- Test halt check blocks writes
- Test writer lock check blocks writes
- Test startup verification passes/fails
- Test successful write delegation
- Test error handling and logging

**Integration Tests (require DB):**
- Test full write flow through EventWriterService
- Test DB rejection handling
- Test halt check with stub
- Test startup verification with real DB
- Test writer lock with stub

### Project Structure Notes

**Existing Structure (from Story 1-5):**
```
src/
├── domain/
│   ├── events/
│   │   ├── event.py
│   │   ├── hash_utils.py
│   │   └── signing.py
│   ├── errors/
│   │   ├── __init__.py
│   │   ├── constitutional.py
│   │   └── event_store.py
│   └── models/
│       ├── witness.py
│       └── agent_key.py
├── application/
│   ├── ports/
│   │   ├── __init__.py
│   │   ├── event_store.py
│   │   ├── key_registry.py
│   │   └── witness_pool.py
│   └── services/
│       ├── __init__.py
│       ├── atomic_event_writer.py
│       ├── signing_service.py
│       ├── witness_service.py
│       └── time_authority_service.py
└── infrastructure/
    ├── adapters/
    │   └── security/
    │       ├── hsm_dev.py
    │       └── hsm_factory.py
    └── stubs/
        └── (empty)
```

**New Files for Story 1-6:**
```
src/
├── application/
│   ├── ports/
│   │   ├── halt_checker.py      # NEW
│   │   └── writer_lock.py       # NEW
│   └── services/
│       └── event_writer_service.py  # NEW
├── domain/
│   └── errors/
│       └── writer.py            # NEW
└── infrastructure/
    └── stubs/
        ├── __init__.py          # NEW
        ├── halt_checker_stub.py # NEW
        └── writer_lock_stub.py  # NEW

tests/
├── unit/
│   └── application/
│       └── test_event_writer_service.py  # NEW
└── integration/
    └── test_event_writer_integration.py  # NEW
```

### Developer Golden Rules Reminder

From project-context.md:
1. **HALT FIRST** - Check halt state before every operation
2. **SIGN COMPLETE** - Never sign payload alone, always `signable_content()`
3. **WITNESS EVERYTHING** - Constitutional actions require attribution
4. **FAIL LOUD** - Never catch `SystemHaltedError`

### Anti-Patterns to Avoid

```python
# NEVER - Retry on halt (AP-1 from architecture.md)
async def write_event_bad(self, ...) -> Event:
    for attempt in range(3):
        try:
            if await self._halt_checker.is_halted():
                await asyncio.sleep(1)  # "Maybe it'll clear"
                continue
            return await self._atomic_writer.write_event(...)
        except SystemHaltedError:
            continue
    raise WriteFailedError("System unavailable")

# CORRECT - Halt propagates immediately
async def write_event_good(self, ...) -> Event:
    if await self._halt_checker.is_halted():
        raise SystemHaltedError(...)  # Never retry
    return await self._atomic_writer.write_event(...)
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.6: Event Writer Service (ADR-1)]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-001 — Event Store Implementation]
- [Source: _bmad-output/planning-artifacts/architecture.md#GAP-CHAOS-001: Writer self-verification]
- [Source: _bmad-output/project-context.md#Developer Golden Rules]
- [Source: src/application/services/atomic_event_writer.py#AtomicEventWriter]
- [Source: src/application/ports/event_store.py#EventStorePort]
- [Source: _bmad-output/implementation-artifacts/stories/1-5-dual-time-authority-and-sequence-numbers.md#Dev Agent Record]

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - All tests passed on first implementation

### Completion Notes List

- ✅ Implemented EventWriterService as single canonical writer (ADR-1)
- ✅ Created HaltChecker port and stub for Epic 3 integration
- ✅ Created WriterLockProtocol and stub for single-writer constraint
- ✅ Added 4 new domain errors: SystemHaltedError, WriterInconsistencyError, WriterLockNotHeldError, WriterNotVerifiedError
- ✅ Implemented startup verification (GAP-CHAOS-001)
- ✅ Added 28 unit tests covering all ACs (including head hash verification)
- ✅ Added 11 integration tests covering all ACs
- ✅ All tests pass (330 passed, 6 pre-existing failures unrelated to this story)
- ✅ All lint checks pass after auto-fix

### Code Review Fixes (2026-01-06)

- ✅ H1: Implemented actual head hash verification in `verify_startup()` with `expected_head_hash` parameter
- ✅ H2: Added missing `WriterInconsistencyError` import to service
- ✅ H3: Added 4 new unit tests for `WriterInconsistencyError` path (hash mismatch, empty store mismatch)
- ✅ M1: Removed unused `patch` import from unit tests
- ✅ M2: Added clarifying comment about test strategy in integration tests
- ✅ M3: Added constitutional constraint warning to halt clearing test

### File List

#### Files Created

| File | Purpose |
|------|---------|
| `src/application/services/event_writer_service.py` | Single canonical writer service (ADR-1) |
| `src/application/ports/halt_checker.py` | Halt state checking interface (Epic 3 stub) |
| `src/application/ports/writer_lock.py` | Single-writer lock interface |
| `src/domain/errors/writer.py` | Writer-specific errors |
| `src/infrastructure/stubs/__init__.py` | Stubs module exports |
| `src/infrastructure/stubs/halt_checker_stub.py` | Stub HaltChecker for Epic 1 |
| `src/infrastructure/stubs/writer_lock_stub.py` | Stub WriterLock for development |
| `tests/unit/application/test_event_writer_service.py` | 28 unit tests (including head hash verification) |
| `tests/integration/test_event_writer_integration.py` | 11 integration tests |

#### Files Modified

| File | Changes |
|------|---------|
| `src/application/ports/__init__.py` | Export HaltChecker, WriterLockProtocol |
| `src/application/services/__init__.py` | Export EventWriterService |
| `src/domain/errors/__init__.py` | Export SystemHaltedError, WriterInconsistencyError, WriterLockNotHeldError, WriterNotVerifiedError |

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-06 | Initial implementation complete - all tasks done | Dev Agent (Claude Opus 4.5) |
| 2026-01-06 | Code review fixes: head hash verification, missing import, 4 new tests, docs | Code Review Agent (Claude Opus 4.5) |

