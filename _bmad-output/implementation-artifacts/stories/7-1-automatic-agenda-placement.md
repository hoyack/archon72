# Story 7.1: Automatic Agenda Placement

Status: review

## Story

As a **system operator**,
I want automatic agenda placement at 3 consecutive integrity failures in 30 days,
So that cessation is considered when integrity is compromised.

## Acceptance Criteria

### AC1: Consecutive Failure Trigger (FR37)
**Given** integrity failure tracking
**When** 3 consecutive failures occur in 30 days
**Then** cessation is automatically placed on Conclave agenda
**And** a `CessationAgendaPlacementEvent` is created with:
  - `trigger_type`: "consecutive_failures"
  - `failure_count`: 3
  - `window_days`: 30
  - `consecutive`: true
  - `failure_event_ids`: references to the 3 triggering events
  - `agenda_placement_reason`: "FR37: 3 consecutive integrity failures in 30 days"

### AC2: RT-4 Rolling Window Alternative Trigger
**Given** the RT-4 alternative trigger for timing attack prevention
**When** 5 non-consecutive failures occur in any 90-day rolling window
**Then** cessation is automatically placed on agenda
**And** a `CessationAgendaPlacementEvent` is created with:
  - `trigger_type`: "rolling_window"
  - `failure_count`: 5
  - `window_days`: 90
  - `consecutive`: false
  - `failure_event_ids`: references to the 5 triggering events
  - `agenda_placement_reason`: "RT-4: 5 integrity failures in 90-day rolling window"
**And** this prevents "wait and reset" timing attacks

### AC3: Anti-Success Alert Sustained Trigger (FR38)
**Given** anti-success alert sustained 90 days
**When** the 90-day threshold is reached
**Then** cessation is placed on agenda
**And** event includes:
  - `trigger_type`: "anti_success_sustained"
  - `sustained_days`: 90
  - `alert_history`: list of alert events during the period
  - `first_alert_date`: when the sustained period began
  - `agenda_placement_reason`: "FR38: Anti-success alert sustained 90 days"

### AC4: Idempotent Trigger
**Given** cessation already on agenda for the same trigger
**When** the trigger condition is evaluated again
**Then** no duplicate agenda placement is created
**And** the original `CessationAgendaPlacementEvent` ID is returned

### AC5: Event Witnessing (CT-12)
**Given** any cessation agenda placement trigger
**When** the event is created
**Then** the event MUST be witnessed via EventWriterService
**And** `signable_content()` includes all trigger details

### AC6: Halt State Check (CT-11)
**Given** system is in halted state
**When** an agenda placement trigger is evaluated
**Then** `SystemHaltedError` is raised
**And** no agenda placement event is created

## Tasks / Subtasks

- [x] **Task 1: Create CessationAgendaPlacementEvent domain event** (AC: 1,2,3,5)
  - [x] Create `src/domain/events/cessation_agenda.py`
  - [x] Define `AgendaTriggerType` enum (consecutive_failures, rolling_window, anti_success_sustained)
  - [x] Implement `CessationAgendaPlacementEventPayload` frozen dataclass
  - [x] Implement `signable_content()` for CT-12 witnessing
  - [x] Add `to_dict()` for event storage
  - [x] Export from `src/domain/events/__init__.py`

- [x] **Task 2: Create IntegrityFailureRepository port** (AC: 1,2)
  - [x] Create `src/application/ports/integrity_failure_repository.py`
  - [x] Define methods: `count_consecutive_in_window()`, `count_in_rolling_window()`, `get_failures_in_window()`
  - [x] Support filtering by date range and consecutive flag
  - [x] Export from `src/application/ports/__init__.py`

- [x] **Task 3: Create AntiSuccessAlertRepository port** (AC: 3)
  - [x] Create `src/application/ports/anti_success_alert_repository.py`
  - [x] Define methods: `get_sustained_alert_duration()`, `get_alerts_in_window()`
  - [x] Track sustained alert start date
  - [x] Export from `src/application/ports/__init__.py`

- [x] **Task 4: Create CessationAgendaRepository port** (AC: 4)
  - [x] Create `src/application/ports/cessation_agenda_repository.py`
  - [x] Define methods: `save_agenda_placement()`, `get_active_placement()`, `get_placement_by_trigger()`
  - [x] Support idempotent check by trigger type
  - [x] Export from `src/application/ports/__init__.py`

- [x] **Task 5: Implement AutomaticAgendaPlacementService** (AC: 1,2,3,4,5,6)
  - [x] Create `src/application/services/automatic_agenda_placement_service.py`
  - [x] Inject: `IntegrityFailureRepository`, `AntiSuccessAlertRepository`, `CessationAgendaRepository`, `EventWriterService`, `HaltChecker`
  - [x] Implement `check_consecutive_failures()` - 3 consecutive in 30 days
  - [x] Implement `check_rolling_window_failures()` - 5 in 90 days (RT-4)
  - [x] Implement `check_anti_success_sustained()` - 90 days sustained
  - [x] Implement `evaluate_all_triggers()` - runs all checks
  - [x] HALT CHECK FIRST pattern in all methods
  - [x] Write witnessed events via EventWriterService
  - [x] Export from `src/application/services/__init__.py`

- [x] **Task 6: Create stub implementations** (AC: all)
  - [x] Create `src/infrastructure/stubs/integrity_failure_repository_stub.py`
  - [x] Create `src/infrastructure/stubs/anti_success_alert_repository_stub.py`
  - [x] Create `src/infrastructure/stubs/cessation_agenda_repository_stub.py`
  - [x] Register stubs in `src/infrastructure/stubs/__init__.py`

- [x] **Task 7: Write unit tests** (AC: all)
  - [x] Create `tests/unit/domain/test_cessation_agenda_event.py`
  - [x] Create `tests/unit/application/test_automatic_agenda_placement_service.py`
  - [x] Test consecutive failure detection (exact boundary: 2 vs 3)
  - [x] Test rolling window detection (exact boundary: 4 vs 5)
  - [x] Test anti-success sustained detection (exact boundary: 89 vs 90 days)
  - [x] Test idempotency (no duplicate placements)
  - [x] Test halt state rejection
  - [x] Test signable_content() determinism

- [x] **Task 8: Write integration tests** (AC: all)
  - [x] Create `tests/integration/test_automatic_agenda_placement_integration.py`
  - [x] Test end-to-end consecutive failure → agenda placement
  - [x] Test end-to-end rolling window → agenda placement
  - [x] Test end-to-end anti-success → agenda placement
  - [x] Test timing attack prevention (RT-4 scenario)

## Dev Notes

### Relevant Architecture Patterns and Constraints

**Constitutional Truths to Honor:**
- **CT-11**: Silent failure destroys legitimacy → HALT CHECK FIRST, raise `SystemHaltedError`
- **CT-12**: Witnessing creates accountability → All events MUST be witnessed via EventWriterService
- **CT-13**: Integrity outranks availability → Availability may be sacrificed

**Developer Golden Rules:**
1. **HALT FIRST** - Check halt state before every operation
2. **WITNESS EVERYTHING** - Constitutional actions require attribution
3. **FAIL LOUD** - Never silently swallow errors

### Source Tree Components to Touch

**New Files:**
```
src/domain/events/cessation_agenda.py          # CessationAgendaPlacementEventPayload
src/application/ports/integrity_failure_repository.py
src/application/ports/anti_success_alert_repository.py
src/application/ports/cessation_agenda_repository.py
src/application/services/automatic_agenda_placement_service.py
src/infrastructure/stubs/integrity_failure_repository_stub.py
src/infrastructure/stubs/anti_success_alert_repository_stub.py
src/infrastructure/stubs/cessation_agenda_repository_stub.py
tests/unit/domain/test_cessation_agenda_event.py
tests/unit/application/test_automatic_agenda_placement_service.py
tests/integration/test_automatic_agenda_placement_integration.py
```

**Files to Update:**
```
src/domain/events/__init__.py                  # Export new event
src/application/ports/__init__.py              # Export new ports
src/application/services/__init__.py           # Export new service
src/infrastructure/stubs/__init__.py           # Register stubs
```

### Related Existing Code

**Breach Infrastructure (Epic 6):**
- `src/domain/events/breach.py` - BreachType, BreachEventPayload pattern
- `src/domain/events/escalation.py` - EscalationEventPayload pattern
- `src/domain/events/cessation.py` - CessationConsiderationEventPayload (similar trigger pattern)
- `src/application/ports/breach_repository.py` - Repository pattern reference
- `src/application/services/cessation_consideration_service.py` - Similar service pattern

**Anti-Success Alert (Epic 5):**
- `src/domain/events/anti_success_alert.py` - AntiSuccessAlertPayload, AlertType
- Event type: `override.anti_success_alert`

**Halt Check Pattern:**
```python
# From cessation_consideration_service.py - FOLLOW THIS PATTERN
if await self._halt_checker.is_halted():
    reason = await self._halt_checker.get_halt_reason()
    log.critical("operation_rejected_system_halted", halt_reason=reason)
    raise SystemHaltedError(f"CT-11: System is halted: {reason}")
```

**Event Writing Pattern:**
```python
# From cessation_consideration_service.py - FOLLOW THIS PATTERN
await self._event_writer.write_event(
    event_type=CESSATION_CONSIDERATION_EVENT_TYPE,
    payload=payload.to_dict(),
    agent_id=CESSATION_SYSTEM_AGENT_ID,
    local_timestamp=trigger_timestamp,
)
```

### Testing Standards Summary

- **Async Testing**: ALL tests use `pytest.mark.asyncio` and `async def test_*`
- **Mocking**: Use `AsyncMock` for async dependencies
- **Coverage**: 80% minimum required
- **Boundary Tests**: Test exact thresholds (2 vs 3, 4 vs 5, 89 vs 90)
- **Unit Test Location**: `tests/unit/domain/` and `tests/unit/application/`
- **Integration Test Location**: `tests/integration/`

### Project Structure Notes

**Hexagonal Architecture Compliance:**
- Domain events: Pure dataclasses, no infrastructure imports
- Ports: Protocol classes in `application/ports/`
- Stubs: Implementation stubs in `infrastructure/stubs/`
- Service: Business logic in `application/services/`

**Import Rules:**
- `domain/` imports NOTHING from other layers
- `application/` imports from `domain/` only
- `infrastructure/` implements ports from `application/`

### Key Differences from Story 6.3 (CessationConsiderationService)

| Aspect | Story 6.3 | Story 7.1 |
|--------|-----------|-----------|
| Trigger | >10 unacknowledged breaches in 90 days | 3 consecutive failures OR 5 in 90 days OR anti-success 90 days |
| Event | CessationConsiderationEventPayload | CessationAgendaPlacementEventPayload |
| Focus | Breach count threshold | Integrity failure patterns |
| RT Defense | N/A | RT-4 timing attack prevention |

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-7.1]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-012]
- [Source: src/domain/events/cessation.py] - Event payload pattern
- [Source: src/application/services/cessation_consideration_service.py] - Service pattern
- [Source: src/domain/events/anti_success_alert.py] - AntiSuccessAlertPayload
- [Source: src/application/ports/breach_repository.py] - Repository pattern
- [Source: _bmad-output/project-context.md] - Coding standards

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

- Implemented FR37 (3 consecutive failures in 30 days) trigger with boundary-tested thresholds
- Implemented RT-4 (5 failures in 90-day rolling window) timing attack prevention trigger
- Implemented FR38 (anti-success alert sustained 90 days) trigger with alert history tracking
- All triggers are idempotent (AC4) - duplicate evaluations return existing placement
- CT-11 compliance: HALT CHECK FIRST pattern in all service methods
- CT-12 compliance: All events witnessed via EventWriterService with signable_content()
- 57 total tests: 20 domain event tests, 27 service unit tests, 10 integration tests
- All tests pass with proper boundary testing (2 vs 3, 4 vs 5, 89 vs 90 days)

### File List

**New Files Created:**
- src/domain/events/cessation_agenda.py
- src/application/ports/integrity_failure_repository.py
- src/application/ports/anti_success_alert_repository.py
- src/application/ports/cessation_agenda_repository.py
- src/application/services/automatic_agenda_placement_service.py
- src/infrastructure/stubs/integrity_failure_repository_stub.py
- src/infrastructure/stubs/anti_success_alert_repository_stub.py
- src/infrastructure/stubs/cessation_agenda_repository_stub.py
- tests/unit/domain/test_cessation_agenda_event.py
- tests/unit/application/test_automatic_agenda_placement_service.py
- tests/integration/test_automatic_agenda_placement_integration.py

**Files Modified:**
- src/domain/events/__init__.py
- src/application/ports/__init__.py
- src/application/services/__init__.py
- src/infrastructure/stubs/__init__.py

## Change Log

- 2026-01-08: Initial implementation of automatic agenda placement (FR37, FR38, RT-4)
