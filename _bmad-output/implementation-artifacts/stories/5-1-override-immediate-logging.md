# Story 5.1: Override Immediate Logging (FR23)

Status: done

## Story

As an **external observer**,
I want override actions logged before they take effect,
So that I can verify no unlogged overrides occur.

## Acceptance Criteria

### AC1: Override Event Written First
**Given** a Keeper initiates an override
**When** the override is submitted
**Then** an `OverrideEvent` is written to the event store FIRST
**And** only AFTER successful log, the override action executes

### AC2: Override Event Payload Structure
**Given** an override event
**When** I examine it
**Then** it includes: `keeper_id`, `scope`, `duration`, `reason`, `timestamp`
**And** `action_type` describes what is being overridden

### AC3: Failed Log Blocks Override Execution
**Given** an override log fails to write
**When** the event store rejects it
**Then** the override action does NOT execute
**And** error is returned to Keeper

## Tasks / Subtasks

- [x] Task 1: Create OverrideEvent payload (AC: #2)
  - [x] 1.1 Create `src/domain/events/override_event.py` with `OverrideEventPayload` dataclass
  - [x] 1.2 Define `OVERRIDE_EVENT_TYPE = "override.initiated"` constant
  - [x] 1.3 Include fields: `keeper_id`, `scope`, `duration`, `reason`, `action_type`, `initiated_at`
  - [x] 1.4 Implement `signable_content()` method for witnessing (CT-12 pattern)
  - [x] 1.5 Add validation in `__post_init__`: scope non-empty, duration > 0, valid action_type
  - [x] 1.6 Export from `src/domain/events/__init__.py`

- [x] Task 2: Create Override domain errors (AC: #3)
  - [x] 2.1 Create `src/domain/errors/override.py`
  - [x] 2.2 Define `OverrideLoggingFailedError(ConstitutionalViolationError)` - FR23 violation
  - [x] 2.3 Define `OverrideBlockedError(ConstitutionalViolationError)` - override rejected
  - [x] 2.4 Export from `src/domain/errors/__init__.py`

- [x] Task 3: Create Override port interface (AC: #1, #3)
  - [x] 3.1 Create `src/application/ports/override_executor.py`
  - [x] 3.2 Define `OverrideExecutorPort(Protocol)` with async `execute_override()` method
  - [x] 3.3 Method signature: `execute_override(override_payload: OverrideEventPayload) -> OverrideResult`
  - [x] 3.4 Define `OverrideResult` dataclass with `success`, `event_id`, `error_message` fields
  - [x] 3.5 Export from `src/application/ports/__init__.py`

- [x] Task 4: Create OverrideService application service (AC: #1, #3)
  - [x] 4.1 Create `src/application/services/override_service.py`
  - [x] 4.2 Inject dependencies: `EventWriterService`, `HaltChecker`
  - [x] 4.3 Implement `initiate_override()`:
    - Step 1: HALT CHECK FIRST (CT-11 pattern from EventWriterService)
    - Step 2: Validate override payload
    - Step 3: Write OverrideEvent to event store FIRST
    - Step 4: Only if write succeeds, execute override action
    - Step 5: If write fails, return error WITHOUT executing override
  - [x] 4.4 Log all operations with structlog (event_id, keeper_id, scope)
  - [x] 4.5 Export from `src/application/services/__init__.py`

- [x] Task 5: Create Override stub adapter (AC: #1)
  - [x] 5.1 Create `src/infrastructure/stubs/override_executor_stub.py`
  - [x] 5.2 Implement `OverrideExecutorStub(OverrideExecutorPort)`
  - [x] 5.3 Track executed overrides in-memory for testing
  - [x] 5.4 Export from `src/infrastructure/stubs/__init__.py`

- [x] Task 6: Write unit tests (AC: #1, #2, #3)
  - [x] 6.1 Create `tests/unit/domain/test_override_event.py`
    - Test payload creation and validation
    - Test signable_content() produces deterministic bytes
    - Test invalid payloads raise ConstitutionalViolationError
  - [x] 6.2 Create `tests/unit/application/test_override_service.py`
    - Test override event written BEFORE execution
    - Test failed write blocks override execution
    - Test halt check runs first
    - Test successful flow with mocked dependencies
  - [x] 6.3 Create `tests/unit/infrastructure/test_override_executor_stub.py`
    - Test stub tracks executed overrides
    - Test stub implements port correctly

- [x] Task 7: Write integration tests (AC: #1, #3)
  - [x] 7.1 Create `tests/integration/test_override_immediate_logging_integration.py`
  - [x] 7.2 Test end-to-end: override initiated -> event written -> override executes
  - [x] 7.3 Test failure case: event write fails -> override NOT executed
  - [x] 7.4 Test halt state: system halted -> override rejected with SystemHaltedError

## Dev Notes

### Constitutional Constraints (CRITICAL)
- **FR23**: Override actions MUST be logged before they take effect
- **CT-11**: Silent failure destroys legitimacy -> Log failure = NO override execution
- **CT-12**: Witnessing creates accountability -> OverrideEvent MUST be witnessed
- **FR26**: Overrides cannot suppress witnessing (Epic 1 enforces, Epic 5 invokes) - tested in Story 5.4

### Pattern References from Previous Stories

**Event Payload Pattern** (from `halt_cleared.py`):
```python
@dataclass(frozen=True, eq=True)
class OverrideEventPayload:
    """Payload for override events - immutable."""

    keeper_id: str
    scope: str  # What is being overridden (component, policy, etc.)
    duration: int  # Duration in seconds
    reason: str  # Enumerated reason (FR28 - Story 5.2)
    action_type: str  # Type of override action
    initiated_at: datetime

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12)."""
        return json.dumps({
            "event_type": "OverrideEvent",
            "keeper_id": self.keeper_id,
            "scope": self.scope,
            "duration": self.duration,
            "reason": self.reason,
            "action_type": self.action_type,
            "initiated_at": self.initiated_at.isoformat(),
        }, sort_keys=True).encode("utf-8")
```

**Service Pattern** (from `event_writer_service.py`):
```python
# HALT FIRST pattern - MUST be first check
if await self._halt_checker.is_halted():
    reason = await self._halt_checker.get_halt_reason()
    log.critical("override_rejected_system_halted", halt_reason=reason)
    raise SystemHaltedError(f"CT-11: System is halted: {reason}")
```

### Valid Override Scopes (from Architecture ADR-4)
- `config.parameter` - Operational parameters
- `ceremony.health_check` - Health check override (Tier 1)
- `watchdog.restart` - Watchdog restart
- `halt.clear` - Halt clearing (already implemented in Story 3.4)

### Valid Action Types
- `CONFIG_CHANGE` - Modify configuration
- `CEREMONY_OVERRIDE` - Override ceremony requirement
- `SYSTEM_RESTART` - Restart system component
- `HALT_CLEAR` - Clear halt state (reference existing implementation)

### Key Dependencies
- `EventWriterService` from Story 1.6 - for writing OverrideEvent
- `HaltChecker` port - for halt state check
- `SigningService` from Story 1.3 - for Keeper signature verification (Story 5.6)

### Project Structure Notes

**Files to Create:**
```
src/domain/events/override_event.py          # New
src/domain/errors/override.py                 # New
src/application/ports/override_executor.py    # New
src/application/services/override_service.py  # New
src/infrastructure/stubs/override_executor_stub.py  # New
tests/unit/domain/test_override_event.py      # New
tests/unit/application/test_override_service.py     # New
tests/unit/infrastructure/test_override_executor_stub.py  # New
tests/integration/test_override_immediate_logging_integration.py  # New
```

**Files to Modify:**
```
src/domain/events/__init__.py                # Export OverrideEventPayload
src/domain/errors/__init__.py                # Export override errors
src/application/ports/__init__.py            # Export OverrideExecutorPort
src/application/services/__init__.py         # Export OverrideService
src/infrastructure/stubs/__init__.py         # Export OverrideExecutorStub
```

### Import Rules (Hexagonal Architecture)
- `domain/events/` imports ONLY from `domain/` and stdlib
- `application/services/` imports from `domain/` and `application/ports/`
- `infrastructure/stubs/` imports from `application/ports/`
- NEVER import from `infrastructure/` in `domain/` or `application/`

### Testing Standards
- ALL tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Mock `EventWriterService`, `HaltChecker` in unit tests
- Integration tests use real stubs, in-memory event store

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-5.1] - Story definition and acceptance criteria
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-4] - Keeper Adversarial Defense
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-6] - Amendment Tiers
- [Source: _bmad-output/project-context.md#Constitutional-Implementation-Rules] - Developer golden rules
- [Source: src/domain/events/halt_cleared.py] - Event payload pattern reference
- [Source: src/application/services/event_writer_service.py] - HALT FIRST pattern reference
- [Source: src/domain/events/event.py] - Base Event entity pattern

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - All tests passed on first implementation

### Completion Notes List

1. **Task 1-7**: All completed successfully
2. **Tests**: 50 tests total (23 unit domain + 10 unit application + 9 unit infrastructure + 8 integration)
3. **Constitutional Compliance**: FR23, CT-11, CT-12 all enforced
4. **Hexagonal Architecture**: All import rules followed

### Senior Developer Review (AI)

**Review Date:** 2026-01-07
**Reviewer:** Claude Opus 4.5 (Code Review Agent)
**Outcome:** APPROVED with fixes applied

**Issues Fixed During Review:**
- M1: Removed 3 unused imports from `override_service.py` (datetime, UUID, OverrideBlockedError)
- M2: Removed unused `field` import from `override_executor_stub.py`
- M4: Added 2 tests for whitespace-only keeper_id and reason validation

**Verified:**
- All 50 tests passing
- Linter clean (ruff)
- Type hints valid (mypy)
- No import boundary violations in Story 5-1 files
- FR23, CT-11, CT-12 compliance confirmed

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-07 | Initial implementation | Dev Agent (Opus 4.5) |
| 2026-01-07 | Code review fixes: unused imports, test coverage | Code Review Agent (Opus 4.5) |

### File List

**New Files Created (9):**
- `src/domain/events/override_event.py` - OverrideEventPayload dataclass with ActionType enum
- `src/domain/errors/override.py` - OverrideLoggingFailedError, OverrideBlockedError
- `src/application/ports/override_executor.py` - OverrideExecutorPort protocol, OverrideResult
- `src/application/services/override_service.py` - OverrideService with HALT FIRST pattern
- `src/infrastructure/stubs/override_executor_stub.py` - OverrideExecutorStub with tracking
- `tests/unit/domain/test_override_event.py` - 21 unit tests
- `tests/unit/application/test_override_service.py` - 10 unit tests
- `tests/unit/infrastructure/test_override_executor_stub.py` - 9 unit tests
- `tests/integration/test_override_immediate_logging_integration.py` - 8 integration tests

**Modified Files (5):**
- `src/domain/events/__init__.py` - Added OVERRIDE_EVENT_TYPE, ActionType, OverrideEventPayload exports
- `src/domain/errors/__init__.py` - Added OverrideBlockedError, OverrideLoggingFailedError exports
- `src/application/ports/__init__.py` - Added OverrideExecutorPort, OverrideResult exports
- `src/application/services/__init__.py` - Added OverrideService export
- `src/infrastructure/stubs/__init__.py` - Added ExecutedOverride, OverrideExecutorStub exports
