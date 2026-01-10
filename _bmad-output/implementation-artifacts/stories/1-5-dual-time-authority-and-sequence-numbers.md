# Story 1.5: Dual Time Authority & Sequence Numbers (FR6-FR7)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **external observer**,
I want events to have dual timestamps and sequence numbers,
So that I can order events deterministically regardless of clock drift.

## Acceptance Criteria

### AC1: Dual Timestamps on Event Creation

**Given** an event is created
**When** it is inserted
**Then** `local_timestamp` is set by the writer service to its local clock
**And** `authority_timestamp` is set by the DB to `now()`
**And** `sequence` is assigned by a BIGSERIAL (monotonically increasing)

### AC2: Unique Sequential Numbers

**Given** the sequence column
**When** two events are inserted concurrently
**Then** each receives a unique, sequential number
**And** no gaps exist in the sequence (except documented ceremonies)

### AC3: Sequence as Authoritative Order

**Given** an external observer
**When** they need to order events
**Then** they use `sequence` as the authoritative order
**And** timestamps are for informational/debugging purposes only

### AC4: Clock Drift Warning

**Given** a scenario where local_timestamp and authority_timestamp differ significantly (>5 seconds)
**When** the event is inserted
**Then** a warning is logged for clock drift investigation
**And** the event is still accepted (sequence is authoritative)

## Tasks / Subtasks

- [x] Task 1: Clock Drift Detection Service (AC: 4)
  - [x] 1.1 Create `src/application/services/time_authority_service.py`
  - [x] 1.2 Implement `TimeAuthorityService` with clock drift detection
  - [x] 1.3 Add configurable drift threshold (default 5 seconds)
  - [x] 1.4 Integrate with structlog for drift warnings
  - [x] 1.5 Add unit tests for drift detection (14 tests)

- [x] Task 2: Sequence Number Validation (AC: 2, 3)
  - [x] 2.1 Create helper `validate_sequence_continuity()` in event store
  - [x] 2.2 Add method to EventStoreProtocol: `get_max_sequence() -> int`
  - [x] 2.3 Implement sequence gap detection (for observer verification)
  - [x] 2.4 Add unit tests for sequence validation (16 tests)

- [x] Task 3: DB Migration for Clock Drift Logging (AC: 4)
  - [x] 3.1 Create `migrations/005_clock_drift_monitoring.sql`
  - [x] 3.2 Create function `log_clock_drift()` as AFTER INSERT trigger
  - [x] 3.3 Trigger logs to `clock_drift_warnings` table when drift > threshold
  - [x] 3.4 Include event_id, local_timestamp, authority_timestamp, drift_seconds

- [x] Task 4: Update AtomicEventWriter for Dual Timestamps (AC: 1)
  - [x] 4.1 Modify `AtomicEventWriter.write_event()` to capture local_timestamp
  - [x] 4.2 Document that authority_timestamp is set by DB (DEFAULT NOW())
  - [x] 4.3 Add TimeAuthorityService integration for post-write drift check
  - [x] 4.4 Add unit tests for dual timestamp handling (5 new tests)

- [x] Task 5: Observer Query Helpers (AC: 3)
  - [x] 5.1 Add `get_events_by_sequence_range(start, end)` to EventStoreProtocol
  - [x] 5.2 Add `verify_sequence_continuity(start, end)` helper
  - [x] 5.3 Document that sequence is authoritative, timestamps informational
  - [x] 5.4 Add unit tests for observer query methods (covered in Task 2)

- [x] Task 6: Integration Tests (AC: 1-4)
  - [x] 6.1 Create `tests/integration/test_time_authority_integration.py`
  - [x] 6.2 Test dual timestamps on event insertion (2 tests)
  - [x] 6.3 Test sequence uniqueness with concurrent inserts (2 tests)
  - [x] 6.4 Test clock drift warning when drift > threshold (2 tests)
  - [x] 6.5 Test sequence gap detection (3 tests)
  - [x] 6.6 Test observer queries by sequence range (2 tests)

## Dev Notes

### Critical Architecture Requirements

**Constitutional Truths to Honor:**
- **CT-11:** Silent failure destroys legitimacy → HALT OVER DEGRADE
- **CT-12:** Witnessing creates accountability → Events must be verifiable
- **CT-13:** Integrity outranks availability → Sequence gaps are constitutional events

**FR Requirements:**
- **FR6:** Events must have dual timestamps (local + authority)
- **FR7:** Sequence numbers must be monotonically increasing and unique

**From Architecture:**
> From architecture.md: "Dual Time Authority" allows external observers to verify event ordering
> independent of clock synchronization issues. Sequence is the authoritative order.

### Schema Already Supports Story

**CRITICAL:** The schema already has the necessary columns from Story 1.1:

```sql
-- From migrations/001_create_events_table.sql
sequence BIGSERIAL UNIQUE NOT NULL,  -- ✅ Auto-incrementing, unique
local_timestamp TIMESTAMPTZ NOT NULL,  -- ✅ Set by writer
authority_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()  -- ✅ Set by DB
```

**This story adds:**
1. Clock drift detection/warning service
2. Sequence validation helpers for observers
3. Documentation that sequence is authoritative

### Clock Drift Detection Pattern

```python
# src/application/services/time_authority_service.py
from datetime import datetime, timedelta, timezone
from structlog import get_logger

logger = get_logger()

DRIFT_THRESHOLD_SECONDS = 5  # Configurable


class TimeAuthorityService:
    """Service for time authority and clock drift detection (FR6-FR7).

    Constitutional Constraint (CT-12):
    Events must be verifiable - clock drift doesn't invalidate events
    but must be logged for investigation.
    """

    def __init__(self, drift_threshold_seconds: float = DRIFT_THRESHOLD_SECONDS) -> None:
        self._threshold = timedelta(seconds=drift_threshold_seconds)

    def check_drift(
        self,
        local_timestamp: datetime,
        authority_timestamp: datetime,
        event_id: str,
    ) -> None:
        """Check for clock drift and log warning if threshold exceeded.

        Args:
            local_timestamp: Timestamp from event source.
            authority_timestamp: Timestamp from time authority (DB).
            event_id: Event ID for logging context.

        Note:
            This does NOT reject the event - sequence is authoritative.
            Clock drift is informational only (AC4).
        """
        drift = abs(authority_timestamp - local_timestamp)

        if drift > self._threshold:
            log = logger.bind(
                event_id=event_id,
                local_timestamp=local_timestamp.isoformat(),
                authority_timestamp=authority_timestamp.isoformat(),
                drift_seconds=drift.total_seconds(),
            )
            log.warning(
                "clock_drift_detected",
                message="FR6: Clock drift exceeds threshold - investigate time sync",
            )
```

### Sequence Gap Detection for Observers

```python
# Add to src/application/ports/event_store.py

class EventStoreProtocol(ABC):
    """Protocol for event store operations."""

    @abstractmethod
    async def get_max_sequence(self) -> int:
        """Get the current maximum sequence number.

        Returns:
            The highest sequence number in the store, or 0 if empty.
        """
        ...

    @abstractmethod
    async def get_events_by_sequence_range(
        self,
        start: int,
        end: int,
    ) -> list[Event]:
        """Get events within a sequence range (inclusive).

        Args:
            start: Start of sequence range (inclusive).
            end: End of sequence range (inclusive).

        Returns:
            List of events ordered by sequence.
        """
        ...

    @abstractmethod
    async def verify_sequence_continuity(
        self,
        start: int,
        end: int,
    ) -> tuple[bool, list[int]]:
        """Verify no gaps exist in sequence range.

        Args:
            start: Start of range to verify.
            end: End of range to verify.

        Returns:
            Tuple of (is_continuous, missing_sequences).
            If continuous, missing_sequences is empty.

        Note:
            Gaps may be valid for documented ceremonies.
            Caller must interpret gaps in context.
        """
        ...
```

### Clock Drift Logging Migration

```sql
-- migrations/005_clock_drift_monitoring.sql
-- Story: 1.5 Dual Time Authority & Sequence Numbers (FR6-FR7)
--
-- Constitutional Constraints:
--   FR6: Events have dual timestamps
--   FR7: Sequence is authoritative ordering

-- Clock drift warning table for monitoring
CREATE TABLE IF NOT EXISTS clock_drift_warnings (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID NOT NULL REFERENCES events(event_id),
    local_timestamp TIMESTAMPTZ NOT NULL,
    authority_timestamp TIMESTAMPTZ NOT NULL,
    drift_seconds NUMERIC(10, 3) NOT NULL,
    logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clock_drift_event_id ON clock_drift_warnings (event_id);
CREATE INDEX IF NOT EXISTS idx_clock_drift_logged_at ON clock_drift_warnings (logged_at);

-- Function to log clock drift on insert
CREATE OR REPLACE FUNCTION log_clock_drift()
RETURNS TRIGGER AS $$
DECLARE
    drift_seconds NUMERIC;
    drift_threshold NUMERIC := 5.0;  -- 5 seconds default
BEGIN
    -- Calculate drift in seconds
    drift_seconds := EXTRACT(EPOCH FROM (NEW.authority_timestamp - NEW.local_timestamp));
    drift_seconds := ABS(drift_seconds);

    -- Log if drift exceeds threshold
    IF drift_seconds > drift_threshold THEN
        INSERT INTO clock_drift_warnings (
            event_id,
            local_timestamp,
            authority_timestamp,
            drift_seconds
        ) VALUES (
            NEW.event_id,
            NEW.local_timestamp,
            NEW.authority_timestamp,
            drift_seconds
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER log_clock_drift_on_insert
    AFTER INSERT ON events
    FOR EACH ROW
    EXECUTE FUNCTION log_clock_drift();

COMMENT ON TABLE clock_drift_warnings IS 'FR6: Clock drift warnings for time sync investigation';
COMMENT ON FUNCTION log_clock_drift() IS 'FR6: Logs clock drift when threshold exceeded';
```

### Integration with AtomicEventWriter

The `AtomicEventWriter` from Story 1-4 already accepts `local_timestamp`. The story adds:

1. **Post-write drift check** - After successful write, check for drift and log warning
2. **No rejection** - Event is accepted regardless of drift (sequence is authoritative)

```python
# Modification to atomic_event_writer.py

class AtomicEventWriter:
    def __init__(
        self,
        signing_service: SigningService,
        witness_service: WitnessService,
        event_store: EventStoreProtocol,
        time_authority: TimeAuthorityService | None = None,  # NEW
    ) -> None:
        self._signing_service = signing_service
        self._witness_service = witness_service
        self._event_store = event_store
        self._time_authority = time_authority  # Optional for drift checking

    @ensure_atomicity
    async def write_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        agent_id: str,
        local_timestamp: datetime,  # Required - caller provides
        previous_content_hash: str | None = None,
    ) -> Event:
        # ... existing logic ...

        # After successful write, check for drift (if time authority configured)
        if self._time_authority and event.authority_timestamp:
            self._time_authority.check_drift(
                local_timestamp=event.local_timestamp,
                authority_timestamp=event.authority_timestamp,
                event_id=str(event.event_id),
            )

        return event
```

### Hexagonal Architecture Compliance

**Files to Create/Modify:**

| Layer | Path | Purpose |
|-------|------|---------|
| Application | `src/application/services/time_authority_service.py` | NEW: Clock drift detection |
| Application | `src/application/ports/event_store.py` | MODIFY: Add observer query methods |
| Infrastructure | `migrations/005_clock_drift_monitoring.sql` | NEW: Clock drift table + trigger |
| Tests | `tests/unit/application/test_time_authority_service.py` | NEW: Unit tests |
| Tests | `tests/integration/test_time_authority_integration.py` | NEW: Integration tests |

**Import Rules (CRITICAL):**
```python
# ALLOWED in application/services/time_authority_service.py
from datetime import datetime, timedelta, timezone
from structlog import get_logger

# FORBIDDEN - Will fail pre-commit hook
from src.infrastructure import ...  # VIOLATION!
from supabase import ...            # VIOLATION!
```

### Previous Story Learnings (Story 1-4)

From Story 1-4 completion:
- **AtomicEventWriter** is at `src/application/services/atomic_event_writer.py` - extend with TimeAuthorityService
- **ensure_atomicity** decorator from Epic 0 works correctly
- **Event.create_with_hash()** handles timestamp fields correctly
- **structlog pattern:** Use `logger.bind()` for context, then `log.warning()` for structured output
- Error codes use FR-prefixed format: "FR6: Clock drift exceeds threshold"

### Testing Requirements

**Unit Tests (no infrastructure):**
- Test TimeAuthorityService drift detection with mock timestamps
- Test drift threshold configuration
- Test logging output format
- Test sequence validation helpers

**Integration Tests (require DB):**
- Test dual timestamps on actual event insertion
- Test sequence uniqueness with concurrent inserts
- Test clock_drift_warnings table populated on drift
- Test sequence gap detection
- Test observer query methods

### Project Structure Notes

**Existing Structure (from Story 1-4):**
```
src/
├── domain/
│   ├── events/
│   │   ├── event.py          # Has local_timestamp, authority_timestamp
│   │   └── hash_utils.py
│   └── models/
│       └── witness.py
├── application/
│   ├── ports/
│   │   ├── event_store.py    # MODIFY: Add observer methods
│   │   └── witness_pool.py
│   └── services/
│       ├── atomic_event_writer.py  # MODIFY: Add TimeAuthorityService
│       ├── signing_service.py
│       └── witness_service.py
└── infrastructure/
    └── adapters/
        └── persistence/
            └── witness_pool.py

migrations/
├── 001_create_events_table.sql   # Has sequence, timestamps
├── 002_hash_chain_verification.sql
├── 003_key_registry.sql
└── 004_witness_validation.sql
```

**New Files for Story 1-5:**
```
src/
└── application/
    └── services/
        └── time_authority_service.py  # NEW

migrations/
└── 005_clock_drift_monitoring.sql     # NEW

tests/
├── unit/
│   └── application/
│       └── test_time_authority_service.py  # NEW
└── integration/
    └── test_time_authority_integration.py  # NEW
```

### Developer Golden Rules Reminder

From project-context.md:
1. **HALT FIRST** - Check halt state before every operation
2. **SIGN COMPLETE** - Never sign payload alone, always `signable_content()`
3. **WITNESS EVERYTHING** - Constitutional actions require attribution
4. **FAIL LOUD** - Never catch `SystemHaltedError`

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.5: Dual Time Authority & Sequence Numbers]
- [Source: _bmad-output/planning-artifacts/architecture.md#FR6-FR7: Dual Time Authority]
- [Source: _bmad-output/project-context.md#Technology Stack & Versions]
- [Source: migrations/001_create_events_table.sql#sequence, timestamps columns]
- [Source: src/domain/events/event.py#local_timestamp, authority_timestamp fields]
- [Source: src/application/services/atomic_event_writer.py#AtomicEventWriter]

---

## Dev Agent Record

### Implementation Summary

**Completed:** 2026-01-06
**Agent:** Claude Opus 4.5

### Files Created
| File | Purpose |
|------|---------|
| `src/application/services/time_authority_service.py` | TimeAuthorityService with clock drift detection (FR6, AC4) |
| `migrations/005_clock_drift_monitoring.sql` | Clock drift warnings table and AFTER INSERT trigger |
| `tests/unit/application/test_time_authority_service.py` | 14 unit tests for drift detection |
| `tests/unit/application/test_event_store_port.py` | 16 unit tests for sequence validation |
| `tests/integration/test_time_authority_integration.py` | 11 integration tests for all ACs |

### Files Modified
| File | Changes |
|------|---------|
| `src/application/ports/event_store.py` | Added `validate_sequence_continuity()` helper, `get_max_sequence()`, `get_events_by_sequence_range()`, `verify_sequence_continuity()` methods |
| `src/application/ports/__init__.py` | Exported `validate_sequence_continuity` |
| `src/application/services/atomic_event_writer.py` | Added optional `time_authority` parameter and post-write drift check |
| `src/application/services/__init__.py` | Exported `TimeAuthorityService` |
| `tests/unit/application/test_atomic_event_writer.py` | Added 5 tests for TimeAuthorityService integration |

### Test Coverage
| Test Suite | Count | Status |
|------------|-------|--------|
| TimeAuthorityService unit tests | 14 | ✅ Pass |
| Sequence validation unit tests | 16 | ✅ Pass |
| AtomicEventWriter time authority tests | 5 | ✅ Pass |
| Integration tests | 11 | ✅ Pass |
| **Total Story 1.5 tests** | **46** | ✅ **All Pass** |

### Acceptance Criteria Verification
- ✅ **AC1:** Dual timestamps on event creation - authority_timestamp set by DB DEFAULT NOW(), local_timestamp passed in
- ✅ **AC2:** Unique sequential numbers - BIGSERIAL with UNIQUE constraint, validate_sequence_continuity() helper
- ✅ **AC3:** Sequence as authoritative order - Observer query methods added, documentation in docstrings
- ✅ **AC4:** Clock drift warning - TimeAuthorityService logs when drift > 5s, event still accepted

### Constitutional Compliance
- **FR6:** Events have dual timestamps (local_timestamp, authority_timestamp)
- **FR7:** Sequence numbers are monotonically increasing and unique
- **CT-11:** Errors are logged loudly (structlog warnings with context)
- **CT-12:** Drift logged for investigation (witnessing accountability)

### Notes
- Clock drift does NOT reject events (sequence is authoritative per AC3/AC4)
- TimeAuthorityService is optional dependency for AtomicEventWriter
- Migration creates both table and trigger for DB-level drift logging
- All tests pass with existing codebase (no regressions)
- [Source: _bmad-output/implementation-artifacts/stories/1-4-witness-attribution-atomic.md#Dev Agent Record]

---

## Senior Developer Review (AI)

**Review Date:** 2026-01-06
**Reviewer:** Claude Opus 4.5 (Adversarial Code Review)

### Review Summary

| Category | Count | Status |
|----------|-------|--------|
| Critical/High | 3 | ✅ Fixed |
| Medium | 4 | ✅ Fixed/Acknowledged |
| Low | 3 | ⏭️ Deferred |

### Issues Found & Resolution

#### Fixed Issues

1. **[H1] Empty File List** - Populated complete file list below
2. **[H3] Status not updated** - Changed from "ready-for-dev" to "done"
3. **[L1] Duplicate Dev Agent Record** - Removed duplicate section, consolidated

#### Acknowledged Issues (Expected Behavior)

4. **[M2] TimeAuthorityService export** - Verified already exported in `__init__.py`
5. **[M3] EventStorePort abstract methods** - Port definition only, implementations in future stories
6. **[M4] Integration tests require Docker** - Expected, marked with `@pytest.mark.integration`

#### Deferred Issues (Low Priority)

7. **[L2] Missing sig_alg_version documentation** - Minor doc gap
8. **[L3] No validation for negative threshold** - Edge case, not critical

### Verified Test Counts

| Test Suite | Claimed | Actual | Status |
|------------|---------|--------|--------|
| TimeAuthorityService unit | 14 | 14 | ✅ |
| Sequence validation unit | 16 | 16 | ✅ |
| AtomicEventWriter time authority | 5 | 5 | ✅ |
| Integration tests | 11 | 11 | ✅ |
| **Total** | **46** | **46** | ✅ |

### Acceptance Criteria Verification

- ✅ **AC1:** Dual timestamps verified - `local_timestamp` set by writer, `authority_timestamp` by DB DEFAULT NOW()
- ✅ **AC2:** Unique sequential numbers - BIGSERIAL UNIQUE constraint, `validate_sequence_continuity()` helper
- ✅ **AC3:** Sequence as authoritative - Observer query methods added, documented in docstrings
- ✅ **AC4:** Clock drift warning - `TimeAuthorityService.check_drift()` logs when drift > 5s

### Review Outcome

**APPROVED** - All acceptance criteria implemented, all critical issues fixed.

---

## File List

### Files Created
| File | Purpose |
|------|---------|
| `src/application/services/time_authority_service.py` | TimeAuthorityService with clock drift detection (FR6, AC4) |
| `migrations/005_clock_drift_monitoring.sql` | Clock drift warnings table and AFTER INSERT trigger |
| `tests/unit/application/test_time_authority_service.py` | 14 unit tests for drift detection |
| `tests/unit/application/test_event_store_port.py` | 16 unit tests for sequence validation |
| `tests/integration/test_time_authority_integration.py` | 11 integration tests for all ACs |

### Files Modified
| File | Changes |
|------|---------|
| `src/application/ports/event_store.py` | Added `validate_sequence_continuity()` helper, `get_max_sequence()`, `get_events_by_sequence_range()`, `verify_sequence_continuity()` methods to port |
| `src/application/ports/__init__.py` | Exported `validate_sequence_continuity` |
| `src/application/services/atomic_event_writer.py` | Added optional `time_authority` parameter and post-write drift check |
| `src/application/services/__init__.py` | Exported `TimeAuthorityService` |
| `tests/unit/application/test_atomic_event_writer.py` | Added 5 tests for TimeAuthorityService integration |

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-06 | Initial implementation complete | Dev Agent (Claude Opus 4.5) |
| 2026-01-06 | Code review: Fixed status, added file list, consolidated Dev Agent Record | Code Review (Claude Opus 4.5) |

