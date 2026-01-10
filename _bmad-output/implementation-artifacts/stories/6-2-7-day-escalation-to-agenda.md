# Story 6.2: 7-Day Escalation to Agenda (FR31)

Status: done

## Story

As a **system operator**,
I want unacknowledged breaches to escalate to Conclave agenda after 7 days,
So that breaches cannot be ignored.

## Acceptance Criteria

### AC1: Automatic Escalation After 7 Days (FR31)
**Given** a breach event exists
**When** 7 days pass without acknowledgment
**Then** it is automatically added to Conclave agenda
**And** an `EscalationEvent` is created with breach reference

### AC2: Acknowledgment Stops Escalation
**Given** a breach is acknowledged within 7 days
**When** acknowledgment is recorded
**Then** escalation timer is stopped
**And** a `BreachAcknowledgedEvent` is created

### AC3: Pending Escalation Query
**Given** the escalation system
**When** I query pending escalations
**Then** I see all breaches approaching 7-day deadline
**And** time remaining is displayed

## Tasks / Subtasks

- [x] Task 1: Create Escalation Domain Events (AC: #1, #2)
  - [x] 1.1 Create `src/domain/events/escalation.py`:
    - `EscalationEventPayload` dataclass with: `escalation_id`, `breach_id`, `breach_type`, `escalation_timestamp`, `days_since_breach`, `agenda_placement_reason`
    - `BreachAcknowledgedEventPayload` dataclass with: `acknowledgment_id`, `breach_id`, `acknowledged_by`, `acknowledgment_timestamp`, `response_choice` (enum: CORRECTIVE, DISMISS, DEFER, ACCEPT)
    - Event type constants: `ESCALATION_EVENT_TYPE = "breach.escalated"`, `BREACH_ACKNOWLEDGED_EVENT_TYPE = "breach.acknowledged"`
    - `signable_content()` methods for witnessing (CT-12)
  - [x] 1.2 Export from `src/domain/events/__init__.py`

- [x] Task 2: Create Escalation Domain Errors (AC: #1, #2)
  - [x] 2.1 Create `src/domain/errors/escalation.py`:
    - `EscalationError(ConstitutionalViolationError)` - base for escalation errors
    - `BreachNotFoundError(EscalationError)` - breach does not exist
    - `BreachAlreadyAcknowledgedError(EscalationError)` - breach already acknowledged
    - `BreachAlreadyEscalatedError(EscalationError)` - breach already escalated
    - `InvalidAcknowledgmentError(EscalationError)` - invalid acknowledgment attempt
    - `EscalationTimerNotStartedError(EscalationError)` - timer not yet started
  - [x] 2.2 Export from `src/domain/errors/__init__.py`

- [x] Task 3: Create Escalation Ports (AC: #1, #2, #3)
  - [x] 3.1 Create `src/application/ports/escalation.py`:
    - `EscalationProtocol` with methods:
      - `async def escalate_breach(breach_id: UUID) -> EscalationEventPayload`
      - `async def acknowledge_breach(breach_id: UUID, acknowledged_by: str, response_choice: ResponseChoice) -> BreachAcknowledgedEventPayload`
      - `async def get_pending_escalations() -> list[PendingEscalation]` (includes breach info + time remaining)
      - `async def is_breach_acknowledged(breach_id: UUID) -> bool`
      - `async def is_breach_escalated(breach_id: UUID) -> bool`
  - [x] 3.2 Create `src/application/ports/escalation_repository.py`:
    - `EscalationRepositoryProtocol` with methods:
      - `async def save_escalation(escalation: EscalationEventPayload) -> None`
      - `async def save_acknowledgment(ack: BreachAcknowledgedEventPayload) -> None`
      - `async def get_acknowledgment_for_breach(breach_id: UUID) -> Optional[BreachAcknowledgedEventPayload]`
      - `async def get_escalation_for_breach(breach_id: UUID) -> Optional[EscalationEventPayload]`
      - `async def list_escalations() -> list[EscalationEventPayload]`
      - `async def list_acknowledgments() -> list[BreachAcknowledgedEventPayload]`
  - [x] 3.3 Create `PendingEscalation` dataclass in `src/domain/models/pending_escalation.py`:
    - `breach_id`, `breach_type`, `detection_timestamp`, `days_remaining`, `hours_remaining`
    - `from_breach()` factory method for calculating time remaining
    - `is_overdue`, `is_urgent`, `urgency_level` properties
  - [x] 3.4 Export from `src/application/ports/__init__.py` and `src/domain/models/__init__.py`

- [x] Task 4: Create Escalation Service (AC: #1, #2, #3)
  - [x] 4.1 Create `src/application/services/escalation_service.py`
  - [x] 4.2 Implement `EscalationService`:
    - Inject: `BreachRepositoryProtocol`, `EscalationRepositoryProtocol`, `EventWriterService`, `HaltChecker`
    - HALT CHECK FIRST at every operation boundary (CT-11)
  - [x] 4.3 Implement `check_and_escalate_breaches() -> list[EscalationEventPayload]`:
    - HALT CHECK FIRST (CT-11)
    - Query all breaches from `BreachRepositoryProtocol`
    - Filter to unacknowledged breaches older than 7 days
    - For each, check if already escalated via `EscalationRepositoryProtocol`
    - Create `EscalationEventPayload` for new escalations
    - Write `EscalationEvent` via EventWriterService (CT-12 witnessing)
    - Save to escalation repository
    - Log escalation with FR31 reference
    - Return list of new escalations
  - [x] 4.4 Implement `acknowledge_breach(breach_id: UUID, acknowledged_by: str, response_choice: ResponseChoice) -> BreachAcknowledgedEventPayload`:
    - HALT CHECK FIRST (CT-11)
    - Validate breach exists via `BreachRepositoryProtocol.get_by_id()`
    - Check not already acknowledged
    - Create `BreachAcknowledgedEventPayload`
    - Write `BreachAcknowledgedEvent` via EventWriterService (CT-12)
    - Save to escalation repository
    - Log acknowledgment
    - Return payload
  - [x] 4.5 Implement `get_pending_escalations() -> list[PendingEscalation]`:
    - HALT CHECK FIRST (CT-11)
    - Query all breaches
    - Filter to unacknowledged and not-yet-escalated
    - Calculate time remaining (7 days - age)
    - Sort by urgency (least time remaining first)
    - Return `PendingEscalation` list
  - [x] 4.6 Implement `get_breach_status(breach_id: UUID) -> dict`:
    - HALT CHECK FIRST (CT-11)
    - Return: `is_acknowledged`, `is_escalated`, `acknowledgment_details`, `escalation_details`
  - [x] 4.7 Export from `src/application/services/__init__.py`

- [x] Task 5: Create Escalation Repository Stub (AC: #3)
  - [x] 5.1 Create `src/infrastructure/stubs/escalation_repository_stub.py`
  - [x] 5.2 Implement `EscalationRepositoryStub`:
    - In-memory storage with `dict[UUID, EscalationEventPayload]` and `dict[UUID, BreachAcknowledgedEventPayload]`
    - Implement all protocol methods
    - `clear()` for test cleanup
    - Duplicate prevention with `BreachAlreadyEscalatedError` and `BreachAlreadyAcknowledgedError`
  - [x] 5.3 Export from `src/infrastructure/stubs/__init__.py`

- [x] Task 6: Write Unit Tests (AC: #1, #2, #3)
  - [x] 6.1 Create `tests/unit/domain/test_escalation_events.py`:
    - Test `EscalationEventPayload` creation with required fields (28 tests)
    - Test `BreachAcknowledgedEventPayload` creation
    - Test `ResponseChoice` enum values
    - Test `signable_content()` determinism
    - Test payload immutability (frozen dataclass)
  - [x] 6.2 Create `tests/unit/domain/test_escalation_errors.py`:
    - Test all escalation error types (26 tests)
    - Test error inheritance hierarchy
  - [x] 6.3 Create `tests/unit/domain/test_pending_escalation.py`:
    - Test `PendingEscalation` dataclass (20 tests)
    - Test time remaining calculations
    - Test `from_breach()` factory method
    - Test `is_overdue`, `is_urgent`, `urgency_level` properties
  - [x] 6.4 Create `tests/unit/application/test_escalation_service.py`:
    - Test `check_and_escalate_breaches()` finds breaches > 7 days old (31 tests)
    - Test `check_and_escalate_breaches()` skips acknowledged breaches
    - Test `check_and_escalate_breaches()` skips already escalated breaches
    - Test `acknowledge_breach()` stops escalation timer
    - Test `acknowledge_breach()` creates witnessed event (CT-12)
    - Test `acknowledge_breach()` fails for nonexistent breach
    - Test `acknowledge_breach()` fails for already acknowledged
    - Test `get_pending_escalations()` returns sorted by urgency
    - Test `get_pending_escalations()` calculates time remaining correctly
    - Test HALT CHECK on all operations
  - [x] 6.5 Create `tests/unit/infrastructure/test_escalation_repository_stub.py`:
    - Test all repository methods (15 tests)
    - Test breach-to-escalation lookup
    - Test breach-to-acknowledgment lookup
    - Test duplicate prevention

- [x] Task 7: Write Integration Tests (AC: #1, #2, #3)
  - [x] 7.1 Create `tests/integration/test_escalation_integration.py`:
    - Test: `test_fr31_breach_escalates_after_7_days` (AC1) (24 tests)
    - Test: `test_escalation_event_is_witnessed` (AC1, CT-12)
    - Test: `test_escalation_includes_breach_reference` (AC1)
    - Test: `test_acknowledgment_stops_escalation` (AC2)
    - Test: `test_acknowledgment_event_is_witnessed` (AC2, CT-12)
    - Test: `test_acknowledgment_event_includes_response_choice` (AC2)
    - Test: `test_pending_escalations_query` (AC3)
    - Test: `test_pending_escalations_sorted_by_urgency` (AC3)
    - Test: `test_time_remaining_calculation` (AC3)
    - Test: `test_halt_check_prevents_escalation_during_halt`
    - Test: `test_halt_check_prevents_acknowledgment_during_halt`
    - Test: `test_multiple_breaches_escalate_independently`
    - Test: `test_acknowledged_breach_not_in_pending`
    - Test: `test_escalated_breach_not_in_pending`

## Dev Notes

### Constitutional Constraints (CRITICAL)

- **FR31**: Unacknowledged breaches after 7 days SHALL escalate to Conclave agenda
- **CT-11**: Silent failure destroys legitimacy -> HALT CHECK FIRST at every operation
- **CT-12**: Witnessing creates accountability -> All events MUST be witnessed
- **CT-13**: Integrity outranks availability -> Availability may be sacrificed for integrity

### Epic 6 Context

Story 6.2 builds on Story 6.1 (Breach Declaration Events) to implement the escalation mechanism. The flow:

```
Breach Declared (Story 6.1)
     |
     v
+---------------------------------------------+
| EscalationService                           | <- Story 6.2 (THIS STORY)
| - check_and_escalate_breaches() [periodic]  |
| - acknowledge_breach()                       |
| - get_pending_escalations()                  |
+---------------------------------------------+
     |
     v
+---------------------------------------------+
| EventWriterService                          |
| - Write EscalationEvent / AcknowledgedEvent |
| - Events are witnessed (CT-12)              |
+---------------------------------------------+
```

### Key Dependencies from Story 6.1

- `BreachEventPayload` from `src/domain/events/breach.py`
- `BreachRepositoryProtocol` from `src/application/ports/breach_repository.py`
- `BreachDeclarationService` from `src/application/services/breach_declaration_service.py`

Use `BreachRepositoryProtocol.list_all()` and `filter_by_date_range()` to find breaches needing escalation.

### ResponseChoice Enum Design

```python
class ResponseChoice(str, Enum):
    """Acknowledgment response choices for breaches (FR31).

    Acknowledgment requires attributed response choice, not template confirmation.
    """
    CORRECTIVE = "corrective"      # Taking corrective action
    DISMISS = "dismiss"            # Dismissing as false positive
    DEFER = "defer"                # Deferring to future session
    ACCEPT = "accept"              # Accepting breach as known limitation
```

### 7-Day Calculation

- Use `datetime.now(timezone.utc)` for current time
- Calculate age: `age = now - breach.detection_timestamp`
- Escalate if `age.days >= 7` AND not acknowledged AND not already escalated
- Time remaining: `timedelta(days=7) - age`

### EscalationEventPayload Design

```python
@dataclass(frozen=True)
class EscalationEventPayload:
    """Payload for breach escalation to Conclave agenda (FR31)."""
    escalation_id: UUID
    breach_id: UUID
    breach_type: BreachType  # From original breach
    escalation_timestamp: datetime
    days_since_breach: int  # For auditability
    agenda_placement_reason: str  # "7-day unacknowledged breach per FR31"

    def signable_content(self) -> bytes:
        """Return deterministic bytes for signing (CT-12)."""
        content = {
            "escalation_id": str(self.escalation_id),
            "breach_id": str(self.breach_id),
            "breach_type": self.breach_type.value,
            "escalation_timestamp": self.escalation_timestamp.isoformat(),
            "days_since_breach": self.days_since_breach,
            "agenda_placement_reason": self.agenda_placement_reason,
        }
        return json.dumps(content, sort_keys=True).encode("utf-8")
```

### Periodic Escalation Check

The `check_and_escalate_breaches()` method is designed to be called periodically (e.g., every hour or daily). It is idempotent - calling it multiple times will not create duplicate escalations.

**Integration Point**: A background worker or scheduled task should call this method. For MVP, manual invocation is acceptable with documentation for future automation (see Story 8.x operational monitoring).

### Alert Severity for Escalations

Per architecture alert levels:
- Escalation creation: **MEDIUM** - Alert on-call, 15 min response
- Breach acknowledgment: **INFO** - No alert, log only

### Import Rules (Hexagonal Architecture)

- `domain/events/escalation.py` imports from `domain/events/breach.py` (for BreachType)
- `domain/errors/escalation.py` inherits from `ConstitutionalViolationError`
- `application/ports/escalation*.py` imports from `domain/events/`, `domain/errors/`, `typing`
- `application/services/escalation_service.py` imports from `application/ports/`, `domain/`
- NEVER import from `infrastructure/` in `domain/` or `application/`

### Testing Standards

- ALL tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Unit tests mock the protocol interfaces
- Integration tests use stub implementations
- FR31 tests MUST verify:
  - Breaches escalate after exactly 7 days (not before)
  - Acknowledgment stops escalation timer
  - Escalation events are witnessed (CT-12)
  - Pending escalations query returns correct time remaining

### Learnings from Story 6.1

- Use `MappingProxyType[str, Any]` for immutable dict fields (AC2 compliance)
- Match service method names exactly to protocol (e.g., `get_breach_by_id` not `get_breach`)
- Remove unused imports to pass linting
- 100 tests passed in Story 6.1 - maintain similar coverage ratio

### Files to Create

```
src/domain/events/escalation.py                        # Escalation event payloads
src/domain/errors/escalation.py                        # Escalation errors
src/domain/models/pending_escalation.py                # PendingEscalation model
src/application/ports/escalation.py                    # Escalation protocol
src/application/ports/escalation_repository.py         # Repository protocol
src/application/services/escalation_service.py         # Main service
src/infrastructure/stubs/escalation_repository_stub.py # Repository stub
tests/unit/domain/test_escalation_events.py            # Event tests
tests/unit/domain/test_escalation_errors.py            # Error tests
tests/unit/domain/test_pending_escalation.py           # Model tests
tests/unit/application/test_escalation_service.py      # Service tests
tests/unit/infrastructure/test_escalation_repository_stub.py # Stub tests
tests/integration/test_escalation_integration.py       # Integration tests
```

### Files to Modify

```
src/domain/events/__init__.py                          # Export new events
src/domain/errors/__init__.py                          # Export new errors
src/domain/models/__init__.py                          # Export new model
src/application/ports/__init__.py                      # Export new ports
src/application/services/__init__.py                   # Export new service
src/infrastructure/stubs/__init__.py                   # Export new stub
```

### Project Structure Notes

- Events follow existing `BreachEventPayload` pattern from Story 6.1
- Errors inherit from `ConstitutionalViolationError` with FR31 reference
- Service follows HALT CHECK FIRST pattern throughout
- Repository stub follows in-memory dict pattern from `BreachRepositoryStub`

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-6.2] - Story definition
- [Source: _bmad-output/planning-artifacts/prd.md#FR31] - 7-day escalation requirement
- [Source: _bmad-output/planning-artifacts/architecture.md#CT-11] - Halt over degrade
- [Source: _bmad-output/planning-artifacts/architecture.md#CT-12] - Witnessing accountability
- [Source: _bmad-output/implementation-artifacts/stories/6-1-breach-declaration-events.md] - Previous story patterns
- [Source: src/domain/events/breach.py] - BreachEventPayload pattern
- [Source: src/application/ports/breach_repository.py] - Repository protocol pattern
- [Source: src/application/services/breach_declaration_service.py] - Service pattern
- [Source: _bmad-output/project-context.md] - Project implementation rules

## Code Review Action Items

### 🔴 HIGH PRIORITY (Must Fix Before Merge)

- [x] **HIGH-1**: Fix type mismatch in `write_event()` payload parameter ✅ FIXED
  - File: `src/application/services/escalation_service.py:223, :382`
  - Problem: `payload.signable_content()` returns `bytes`, but `EventWriterService.write_event()` expects `dict[str, Any]`
  - Fix: Changed to use `payload.to_dict()` method

- [x] **HIGH-2**: Add missing `local_timestamp` argument to `write_event()` calls ✅ FIXED
  - File: `src/application/services/escalation_service.py:223, :382`
  - Problem: Missing required `local_timestamp: datetime` parameter
  - Fix: Added `local_timestamp=escalation_timestamp` and `local_timestamp=acknowledgment_timestamp`

- [x] **HIGH-3**: Add type parameters to `dict` return type annotation ✅ FIXED
  - File: `src/application/ports/escalation.py:131`
  - File: `src/application/services/escalation_service.py:514`
  - Problem: `Optional[dict]` should be `Optional[dict[str, Any]]`
  - Fix: Added type parameters and `Any` import

### 🟡 MEDIUM PRIORITY (Should Fix)

- [x] **MEDIUM-1**: Add `to_dict()` method to escalation payloads for consistency ✅ FIXED
  - File: `src/domain/events/escalation.py`
  - Problem: Other payloads (keeper, ceremony) use `to_dict()` pattern
  - Fix: Added `to_dict() -> dict[str, Any]` method to both payloads

- [ ] **MEDIUM-2**: Consider extracting HALT CHECK pattern to helper method (DEFERRED)
  - File: `src/application/services/escalation_service.py`
  - Problem: HALT CHECK pattern repeated 6 times verbatim
  - Note: Code works correctly; refactoring is optional improvement

- [ ] **MEDIUM-3**: Integration tests mock EventWriterService (NOTED)
  - File: `tests/integration/test_escalation_integration.py`
  - Note: Mocks prevented catching HIGH-1/HIGH-2 type errors at test time
  - Recommendation: Consider using real EventWriterService with stub dependencies in future

### Review Summary

| Severity | Count | Status |
|----------|-------|--------|
| 🔴 HIGH | 3 | ✅ All Fixed |
| 🟡 MEDIUM | 3 | 1 Fixed, 2 Deferred |
| 🟢 LOW | 0 | N/A |

**Reviewed by:** Code Review Workflow (Claude Opus 4.5)
**Review Date:** 2026-01-08
**Tests Verified:** 144/144 passing
**Fixes Applied:** 2026-01-08 - All HIGH priority items resolved

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 144 escalation tests passing (28 event + 26 error + 20 model + 31 service + 15 stub + 24 integration)

### Completion Notes List

- Implemented FR31 (7-day escalation) with full constitutional compliance
- HALT CHECK FIRST (CT-11) at every operation boundary
- Witnessed events (CT-12) via EventWriterService
- PendingEscalation model with urgency levels (OVERDUE, URGENT, WARNING, PENDING)
- ResponseChoice enum (CORRECTIVE, DISMISS, DEFER, ACCEPT)
- EscalationRepositoryStub with duplicate prevention

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-07 | Story created with comprehensive FR31 context, builds on Story 6.1 foundation | Create-Story Workflow (Opus 4.5) |
| 2026-01-07 | Story implementation complete - all 7 tasks done, 144 tests passing | Dev-Story Workflow (Opus 4.5) |

### File List

#### Created Files

- `src/domain/events/escalation.py` - Escalation event payloads
- `src/domain/errors/escalation.py` - Escalation errors
- `src/domain/models/pending_escalation.py` - PendingEscalation model
- `src/application/ports/escalation.py` - Escalation protocol
- `src/application/ports/escalation_repository.py` - Repository protocol
- `src/application/services/escalation_service.py` - Main service
- `src/infrastructure/stubs/escalation_repository_stub.py` - Repository stub
- `tests/unit/domain/test_escalation_events.py` - 28 tests
- `tests/unit/domain/test_escalation_errors.py` - 26 tests
- `tests/unit/domain/test_pending_escalation.py` - 20 tests
- `tests/unit/application/test_escalation_service.py` - 31 tests
- `tests/unit/infrastructure/test_escalation_repository_stub.py` - 15 tests
- `tests/integration/test_escalation_integration.py` - 24 tests

#### Modified Files

- `src/domain/events/__init__.py` - Added escalation event exports
- `src/domain/errors/__init__.py` - Added escalation error exports
- `src/domain/models/__init__.py` - Added PendingEscalation export
- `src/application/ports/__init__.py` - Added escalation port exports
- `src/application/services/__init__.py` - Added EscalationService export
- `src/infrastructure/stubs/__init__.py` - Added EscalationRepositoryStub export
