# Story 9.5: Audit Results as Events (FR108)

Status: done

## Story

As an **external observer**,
I want audit results logged as events,
So that audit history is part of the constitutional record.

## Acceptance Criteria

### AC1: Audit Completed Events Logged
**Given** an audit completes (quarterly or ad-hoc)
**When** results are finalized
**Then** an `AuditCompletedEvent` is created
**And** it includes: audit_type, scope, findings_count, status

### AC2: Audit History Queryable
**Given** audit history
**When** I query events
**Then** all audit events are returned
**And** trends can be analyzed

### AC3: HALT CHECK FIRST Compliance (CT-11)
**Given** any audit event service operation
**When** invoked
**Then** halt state is checked first
**And** if halted, operation fails with SystemHaltedError

### AC4: All Audit Events Witnessed (CT-12)
**Given** audit event generation
**When** any audit event is created
**Then** it is signed and witnessed
**And** forms part of the constitutional record

### AC5: Event Types Cover All Audit Scenarios
**Given** the audit event system
**When** any audit-related action occurs
**Then** an appropriate event type is emitted
**And** event types include: started, completed (clean/violations/failed), violation_flagged

## Tasks / Subtasks

- [x] **Task 1: Extend Audit Event Query Service** (AC: 2)
  - [x] Create `src/application/services/audit_event_query_service.py`
    - [x] `AuditEventQueryService` class
    - [x] Constructor: `event_query: EventQueryProtocol`, `halt_checker: HaltChecker`
    - [x] `async def get_audit_events(self, limit: int = 100) -> list[AuditEvent]`
      - [x] HALT CHECK FIRST (CT-11)
      - [x] Query event store for `audit.*` event types
      - [x] Return in chronological order (oldest first)
    - [x] `async def get_audit_events_by_type(self, event_type: str, limit: int = 100) -> list[AuditEvent]`
      - [x] HALT CHECK FIRST (CT-11)
      - [x] Filter by specific event type
    - [x] `async def get_audit_events_by_quarter(self, quarter: str) -> list[AuditEvent]`
      - [x] HALT CHECK FIRST (CT-11)
      - [x] Filter by quarter field in payload
    - [x] `async def get_audit_trend(self, quarters: int = 4) -> AuditTrend`
      - [x] HALT CHECK FIRST (CT-11)
      - [x] Aggregate violation counts over specified quarters
      - [x] Return trend data for analysis
  - [x] Update `src/application/services/__init__.py` with exports

- [x] **Task 2: Create Audit Event Domain Models** (AC: 1, 2, 5)
  - [x] Create `src/domain/models/audit_event.py`
    - [x] `AuditEventType` enum: STARTED, COMPLETED, VIOLATION_FLAGGED
    - [x] `AuditEvent` frozen dataclass:
      - [x] `event_id: str` - From event store
      - [x] `event_type: str` - Original event type string
      - [x] `audit_id: str` - Audit identifier
      - [x] `quarter: str | None` - Quarter if applicable
      - [x] `timestamp: datetime` - When event occurred
      - [x] `payload: dict[str, object]` - Full event payload
    - [x] `AuditTrend` frozen dataclass:
      - [x] `quarters: tuple[str, ...]` - Quarters analyzed
      - [x] `total_audits: int` - Total audits in period
      - [x] `total_violations: int` - Total violations found
      - [x] `clean_audits: int` - Audits with no violations
      - [x] `violation_audits: int` - Audits with violations
      - [x] `failed_audits: int` - Failed audits
      - [x] `average_violations_per_audit: float` - For trending
      - [x] `quarter_breakdown: tuple[QuarterStats, ...]` - Per-quarter data
    - [x] `QuarterStats` frozen dataclass:
      - [x] `quarter: str`
      - [x] `audits: int`
      - [x] `violations: int`
      - [x] `status: Literal["clean", "violations_found", "failed", "not_run"]`
  - [x] Update `src/domain/models/__init__.py` with exports

- [x] **Task 3: Create Event Store Query Port Extension** (AC: 2)
  - [x] Create `src/application/ports/event_query.py`
    - [x] `EventQueryProtocol(Protocol)`:
      - [x] `async def query_events_by_type_prefix(self, type_prefix: str, limit: int = 100) -> list[dict[str, object]]`
        - [x] Query events where type starts with prefix (e.g., "audit.")
      - [x] `async def query_events_by_type(self, event_type: str, limit: int = 100) -> list[dict[str, object]]`
        - [x] Query exact event type match
      - [x] `async def query_events_with_payload_filter(self, event_type: str, payload_filter: dict[str, object], limit: int = 100) -> list[dict[str, object]]`
        - [x] Query events with specific payload values (e.g., quarter="2026-Q1")
    - [x] Docstrings with FR108 reference
  - [x] Update `src/application/ports/__init__.py` with exports

- [x] **Task 4: Implement Event Query Stub** (AC: 2)
  - [x] Create `src/infrastructure/stubs/event_query_stub.py`
    - [x] `EventQueryStub` implementing `EventQueryProtocol`
    - [x] In-memory event storage with filtering
    - [x] Configuration methods:
      - [x] `add_event(event: dict[str, object])` - Add test event
      - [x] `clear()` - Clear all events
      - [x] `get_all_events() -> list[dict[str, object]]` - Get all stored events
      - [x] `configure_audit_events(...)` - Add complete audit event sequence
  - [x] Update `src/infrastructure/stubs/__init__.py` with exports

- [x] **Task 5: Create Audit Event Errors** (AC: 3)
  - [x] Create `src/domain/errors/audit_event.py`
    - [x] `AuditEventQueryError(ConstitutionalViolationError)` - Base error
    - [x] `AuditEventNotFoundError(AuditEventQueryError)` - Event not found
    - [x] `AuditTrendCalculationError(AuditEventQueryError)` - Trend calculation failed
    - [x] `InsufficientAuditDataError(AuditEventQueryError)` - Not enough data for trend
    - [x] `AuditQueryTimeoutError(AuditEventQueryError)` - Query timeout
  - [x] Update `src/domain/errors/__init__.py` with exports

- [x] **Task 6: Write Unit Tests** (AC: 1, 2, 3, 4, 5)
  - [x] Create `tests/unit/domain/test_audit_event_models.py`
    - [x] Test AuditEvent dataclass (8 tests)
    - [x] Test AuditTrend dataclass (8 tests)
    - [x] Test QuarterStats dataclass (4 tests)
    - [x] Test AuditEventType enum (4 tests)
    - [x] Test constants (4 tests)
  - [x] Create `tests/unit/application/test_audit_event_query_service.py`
    - [x] Test HALT CHECK FIRST pattern (4 tests)
    - [x] Test get_audit_events (5 tests)
    - [x] Test get_audit_events_by_type (4 tests)
    - [x] Test get_audit_events_by_quarter (4 tests)
    - [x] Test get_audit_trend calculation (8 tests)
    - [x] Test edge cases (empty results, missing data) (5 tests)
  - [x] Total: 58 unit tests passing

- [x] **Task 7: Write Integration Tests** (AC: 1, 2, 3, 4, 5)
  - [x] Create `tests/integration/test_audit_results_as_events_integration.py`
    - [x] Test audit event flow end-to-end (7 tests)
    - [x] Test HALT CHECK FIRST pattern (7 tests)
    - [x] Test trend analysis edge cases (4 tests)
    - [x] Test query by event type (3 tests)
    - [x] Test system agent identification (1 test)
    - [x] Test event prefix filtering (1 test)
  - [x] Total: 23 integration tests passing

## Dev Notes

### Relationship to Previous Stories

**Story 9-3 (Quarterly Material Audit)** already creates audit events:
- `AuditStartedEventPayload` - When audit begins
- `AuditCompletedEventPayload` - When audit completes (clean/violations/failed)
- `ViolationFlaggedEventPayload` - For each violation found

**Story 9-5 (This Story)** adds:
- **Query capability** to retrieve audit events from the event store
- **Trend analysis** to analyze audit history over time
- **Event models** for working with audit events in application code

### CRITICAL: Builds on Existing Audit Events

The audit events are already being WRITTEN by `QuarterlyAuditService` (Story 9-3).
This story enables READING and ANALYZING those events.

```
Story 9-3: WRITE audit events via EventWriterService
Story 9-5: READ audit events via EventQueryProtocol (NEW)
```

### Architecture Pattern: Query Service

```
AuditEventQueryService (new)
    └── EventQueryProtocol (new - query events from store)
    └── HaltChecker (existing)
```

The query service transforms raw event store data into domain-specific `AuditEvent` models for use by external observers and trend analysis.

### Relevant FR and CT References

**FR108 (Audit Results as Events):**
From `_bmad-output/planning-artifacts/epics.md#Story-9.5`:

> Audit results logged as events.
> Audit history is part of the constitutional record.
> AuditCompletedEvent includes: audit_type, scope, findings_count, status.
> Trends can be analyzed.

**CT-11 (Silent Failure Destroys Legitimacy):**
- HALT CHECK FIRST on every query method
- Query failures are logged and reported

**CT-12 (Witnessing Creates Accountability):**
- Audit events are already witnessed when written (Story 9-3)
- Query service reads witnessed events from constitutional record

### Event Type Mapping

| Event Type String | Meaning | Source Story |
|-------------------|---------|--------------|
| `audit.started` | Quarterly audit began | 9-3 |
| `audit.completed` | Audit finished (status in payload) | 9-3 |
| `audit.violation.flagged` | Material violation detected | 9-3 |

### Source Tree Components to Touch

**Files to Create:**
```
src/domain/models/audit_event.py
src/domain/errors/audit_event.py
src/application/ports/event_query.py
src/application/services/audit_event_query_service.py
src/infrastructure/stubs/event_query_stub.py
tests/unit/domain/test_audit_event_models.py
tests/unit/application/test_audit_event_query_service.py
tests/integration/test_audit_results_as_events_integration.py
```

**Files to Modify:**
```
src/domain/models/__init__.py          # Export AuditEvent, AuditTrend, QuarterStats
src/domain/errors/__init__.py          # Export AuditEventQueryError and subclasses
src/application/ports/__init__.py      # Export EventQueryProtocol
src/application/services/__init__.py   # Export AuditEventQueryService
src/infrastructure/stubs/__init__.py   # Export EventQueryStub
```

### Testing Standards Summary

**Coverage Requirements:**
- Minimum 80% coverage
- 100% coverage for trend calculation (critical for compliance)
- All query methods tested with empty results

**Async Testing:**
- ALL test files use `pytest.mark.asyncio`
- Use `AsyncMock` for async port methods
- Mock `HaltChecker` and `EventQueryProtocol` in unit tests

**Key Test Scenarios:**
1. Query returns all audit events in order
2. Filter by event type works correctly
3. Filter by quarter works correctly
4. Trend calculation handles missing quarters
5. HALT CHECK FIRST prevents operations when halted
6. Empty event store returns empty results (not error)
7. Trend with single quarter still works

### Previous Story Intelligence (Story 9-4)

**Learnings from Story 9-4:**
1. Service pattern: Constructor injection with ports
2. HALT CHECK FIRST at start of every public method
3. Event payloads are frozen dataclasses with `to_dict()` and `signable_content()`
4. Errors inherit from `ConstitutionalViolationError`
5. Stubs provide test control methods (configuration for test scenarios)

**Existing Infrastructure to Reuse:**
- `EventWriterService` (Story 1-6) - already writes audit events
- `HaltChecker` (Story 3-2) - for CT-11 compliance
- `AuditStartedEventPayload`, `AuditCompletedEventPayload`, `ViolationFlaggedEventPayload` (Story 9-3)

### Git Intelligence (Recent Commits)

```
686a37a feat(story-7.6): Implement cessation as final recorded event (FR24)
cdeb269 feat(story-3.6): Implement 48-hour recovery waiting period (FR21)
```

**Commit pattern for this story:**
```
feat(story-9.5): Implement audit results as events (FR108)
```

### Critical Implementation Notes

**AuditEvent Domain Model:**
```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal

class AuditEventType(str, Enum):
    """Types of audit events (FR108)."""
    STARTED = "audit.started"
    COMPLETED = "audit.completed"
    VIOLATION_FLAGGED = "audit.violation.flagged"

@dataclass(frozen=True)
class AuditEvent:
    """Audit event from constitutional record (FR108)."""
    event_id: str
    event_type: str
    audit_id: str
    quarter: str | None
    timestamp: datetime
    payload: dict[str, object]

    @property
    def is_started(self) -> bool:
        return self.event_type == AuditEventType.STARTED.value

    @property
    def is_completed(self) -> bool:
        return self.event_type == AuditEventType.COMPLETED.value

    @property
    def completion_status(self) -> str | None:
        """Get completion status from payload if this is a completed event."""
        if self.is_completed and "status" in self.payload:
            return str(self.payload["status"])
        return None
```

**Query Service Pattern:**
```python
async def get_audit_events(self, limit: int = 100) -> list[AuditEvent]:
    """Query all audit events per FR108.

    HALT CHECK FIRST (CT-11).

    Args:
        limit: Maximum events to return.

    Returns:
        List of AuditEvent objects.

    Raises:
        SystemHaltedError: If system is halted.
    """
    # HALT CHECK FIRST (Golden Rule #1)
    await self._check_halt()

    # Query events with audit prefix
    raw_events = await self._event_query.query_events_by_type_prefix(
        type_prefix="audit.",
        limit=limit,
    )

    # Transform to domain objects
    return [self._to_audit_event(event) for event in raw_events]
```

**Trend Calculation:**
```python
async def get_audit_trend(self, quarters: int = 4) -> AuditTrend:
    """Calculate audit trend over quarters per FR108.

    HALT CHECK FIRST (CT-11).

    Args:
        quarters: Number of quarters to analyze.

    Returns:
        AuditTrend with aggregated statistics.

    Raises:
        SystemHaltedError: If system is halted.
        InsufficientAuditDataError: If no audit data available.
    """
    await self._check_halt()

    # Get recent completed events
    completed_events = await self._event_query.query_events_by_type(
        event_type=AuditEventType.COMPLETED.value,
        limit=quarters * 10,  # Buffer for multiple audits per quarter
    )

    if not completed_events:
        raise InsufficientAuditDataError("No audit data available for trend analysis")

    # Aggregate by quarter
    quarter_data: dict[str, QuarterStats] = {}
    for event in completed_events:
        payload = event.get("payload", {})
        quarter = payload.get("quarter", "unknown")
        status = payload.get("status", "unknown")
        violations = payload.get("violations_found", 0)

        # Update or create quarter stats
        # ... aggregation logic

    return AuditTrend(
        quarters=tuple(sorted(quarter_data.keys())),
        total_audits=len(completed_events),
        # ... rest of stats
    )
```

### Dependencies

**Required Ports (inject via constructor):**
- `EventQueryProtocol` - New for this story (query events)
- `HaltChecker` - For CT-11 halt check (existing)

**Existing Infrastructure to Reuse:**
- Event types from `src/domain/events/audit.py` (Story 9-3)
- `HaltChecker` from Story 3-2
- Event store (writes already happening from Story 9-3)

### Project Structure Notes

- Alignment with unified project structure (paths, modules, naming)
- New files follow existing patterns in `src/domain/models/`, `src/application/services/`, etc.
- No conflicts detected
- Query capability complements existing write capability from 9-3

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-9.5] - Story definition
- [Source: _bmad-output/implementation-artifacts/stories/9-3-quarterly-material-audit.md] - Audit service
- [Source: _bmad-output/implementation-artifacts/stories/9-4-user-content-prohibition.md] - Previous story
- [Source: src/domain/events/audit.py] - Existing audit event payloads
- [Source: src/application/services/quarterly_audit_service.py] - Where events are written
- [Source: _bmad-output/project-context.md] - Project conventions

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 81 tests passing (27 domain model + 31 service + 23 integration)

### Completion Notes List

- FR108 implementation complete with full CT-11 (HALT CHECK FIRST) compliance
- Event query service provides read-only access to audit history
- Trend analysis calculates aggregate statistics across quarters
- All public methods enforce halt state check before execution

### File List

**Created:**
- `src/domain/models/audit_event.py` - AuditEvent, AuditTrend, QuarterStats domain models with validation
- `src/domain/errors/audit_event.py` - AuditEventNotFoundError, InsufficientAuditDataError, AuditTrendCalculationError, AuditQueryTimeoutError
- `src/application/ports/event_query.py` - EventQueryProtocol port interface for querying events
- `src/application/services/audit_event_query_service.py` - AuditEventQueryService with CT-11 compliance
- `src/infrastructure/stubs/event_query_stub.py` - EventQueryStub for testing
- `tests/unit/domain/test_audit_event_models.py` - 27 unit tests for domain models
- `tests/unit/application/test_audit_event_query_service.py` - 31 unit tests for service
- `tests/integration/test_audit_results_as_events_integration.py` - 23 integration tests

**Modified:**
- `src/domain/models/__init__.py` - Added AuditEvent, AuditTrend, QuarterStats exports
- `src/domain/errors/__init__.py` - Added audit event error exports
- `src/application/ports/__init__.py` - Added EventQueryProtocol export
- `src/application/services/__init__.py` - Added AuditEventQueryService export
- `src/infrastructure/stubs/__init__.py` - Added EventQueryStub export

