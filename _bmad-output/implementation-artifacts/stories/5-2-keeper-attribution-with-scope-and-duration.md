# Story 5.2: Keeper Attribution with Scope & Duration (FR24)

Status: done

## Story

As an **external observer**,
I want overrides attributed with scope, duration, and reason,
So that I can analyze override patterns and verify time-limited interventions.

## Acceptance Criteria

### AC1: Override Scope, Duration, and Reason Requirements
**Given** an override request is submitted
**When** the request is processed
**Then**
- `scope` defines exactly what is overridden (specific component, action, or policy)
- `duration` specifies how long the override is in effect (validated, required)
- `reason` is required and must match enumerated reasons (FR28)
- All three fields are captured, stored, and immutable

### AC2: Automatic Duration Expiration
**Given** an override with a specified duration is active
**When** the duration expires
**Then**
- The override automatically reverts (no longer active)
- An `OverrideExpiredEvent` is created in the event store
- The reversion is logged and visible to observers
- The expiration timestamp is recorded in UTC

### AC3: Indefinite Override Rejection
**Given** an indefinite override attempt (missing or invalid duration)
**When** the request is submitted
**Then**
- It is rejected with error "FR24: Duration required for all overrides"
- No partial logging occurs
- Keeper receives clear error feedback

### AC4: Maximum Duration Enforcement
**Given** an override request with excessive duration
**When** duration exceeds maximum allowed (7 days = 604800 seconds)
**Then**
- It is rejected with error "FR24: Duration exceeds maximum of 7 days"
- No override event is created

### AC5: Enumerated Reason Validation
**Given** an override request with reason
**When** the reason is not in the enumerated list (FR28)
**Then**
- It is rejected with "FR24: Invalid override reason"
- Valid reasons are returned in error message

## Tasks / Subtasks

- [x] Task 1: Define OverrideReason enumeration (AC: #3, #5) ✅
  - [x] 1.1 Create `src/domain/models/override_reason.py`
  - [x] 1.2 Define `OverrideReason(Enum)` with FR28-specified reasons
  - [x] 1.3 Add `description` property returning human-readable text
  - [x] 1.4 Export from `src/domain/models/__init__.py`

- [x] Task 2: Create Duration validation domain service (AC: #1, #3, #4) ✅
  - [x] 2.1 Create `src/domain/services/duration_validator.py`
  - [x] 2.2 Define constants: MIN_DURATION_SECONDS=60, MAX_DURATION_SECONDS=604800
  - [x] 2.3 Implement `validate_duration(duration_seconds: int) -> None`
  - [x] 2.4 Export from `src/domain/services/__init__.py`

- [x] Task 3: Create DurationValidationError domain error (AC: #3, #4) ✅
  - [x] 3.1 Add `DurationValidationError(ConstitutionalViolationError)` to `src/domain/errors/override.py`
  - [x] 3.2 Add `InvalidOverrideReasonError(ConstitutionalViolationError)`
  - [x] 3.3 Export new errors from `src/domain/errors/__init__.py`

- [x] Task 4: Update OverrideEventPayload for strict validation (AC: #1, #3, #4, #5) ✅
  - [x] 4.1 Update `src/domain/events/override_event.py` with MAX_DURATION_SECONDS
  - [x] 4.2 Update `_validate_duration()` to check max duration (raises DurationValidationError)
  - [x] 4.3 Add `expires_at` computed property

- [x] Task 5: Create OverrideExpiredEvent payload (AC: #2) ✅
  - [x] 5.1 Create `OverrideExpiredEventPayload` dataclass
  - [x] 5.2 Define fields: original_override_id, keeper_id, scope, expired_at, reversion_status
  - [x] 5.3 Add `OVERRIDE_EXPIRED_EVENT_TYPE = "override.expired"` constant
  - [x] 5.4 Implement `signable_content()` method
  - [x] 5.5 Export from `src/domain/events/__init__.py`

- [x] Task 6: Create OverrideRegistry port interface (AC: #2) ✅
  - [x] 6.1 Create `src/application/ports/override_registry.py`
  - [x] 6.2 Define `OverrideRegistryPort(Protocol)` with all methods
  - [x] 6.3 Define `ExpiredOverrideInfo` dataclass
  - [x] 6.4 Export from `src/application/ports/__init__.py`

- [x] Task 7: Create OverrideExpirationService (AC: #2) ✅
  - [x] 7.1 Create `src/application/services/override_expiration_service.py`
  - [x] 7.2 Inject dependencies: EventWriterService, OverrideRegistryPort
  - [x] 7.3 Implement `async def process_expirations()` method
  - [x] 7.4 Export from `src/application/services/__init__.py`

- [x] Task 8: Update OverrideService to integrate new validation (AC: #1, #3, #4, #5) ✅
  - [x] 8.1 Update `src/application/services/override_service.py`:
    - Add `OverrideRegistryPort` optional dependency
    - Register active override after successful event write

- [x] Task 9: Create OverrideRegistry stub adapter (AC: #2) ✅
  - [x] 9.1 Create `src/infrastructure/stubs/override_registry_stub.py`
  - [x] 9.2 Implement `OverrideRegistryStub(OverrideRegistryPort)`
  - [x] 9.3 Use in-memory dict with asyncio Lock
  - [x] 9.4 Export from `src/infrastructure/stubs/__init__.py`

- [x] Task 10: Write unit tests (AC: #1-#5) ✅
  - [x] 10.1 Create `tests/unit/domain/test_override_reason.py` (14 tests)
  - [x] 10.2 Create `tests/unit/domain/test_duration_validator.py` (16 tests)
  - [x] 10.3 Update `tests/unit/domain/test_override_event.py` (38 tests total)
  - [x] 10.5 Create `tests/unit/infrastructure/test_override_registry_stub.py` (11 tests)

- [x] Task 11: Write integration tests (AC: #1-#5) ✅
  - [x] 11.1 Create `tests/integration/test_keeper_attribution_integration.py` (18 tests)
    - AC1: Enumerated reasons
    - AC2: Automatic expiration
    - AC3: Duration validation
    - AC4: expires_at property

## Dev Notes

### Constitutional Constraints (CRITICAL)

- **FR24**: Override events SHALL include Keeper attribution, scope, duration, and reason
- **FR28**: Override reasons must be from enumerated list (linked)
- **CT-11**: Silent failure destroys legitimacy -> All expirations must be logged
- **CT-12**: Witnessing creates accountability -> OverrideExpiredEvent MUST be witnessed
- **FR23**: Override actions must be logged before they take effect (from Story 5.1)

### Pattern References from Story 5.1 (FOLLOW EXACTLY)

**Event Payload Pattern** (from `override_event.py`):
```python
@dataclass(frozen=True, eq=True)
class OverrideExpiredEventPayload:
    """Payload for override expiration events - immutable."""

    original_override_id: UUID
    keeper_id: str
    scope: str
    expired_at: datetime
    reversion_status: str  # "success" or "failed"

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12)."""
        return json.dumps({
            "event_type": "OverrideExpiredEvent",
            "original_override_id": str(self.original_override_id),
            "keeper_id": self.keeper_id,
            "scope": self.scope,
            "expired_at": self.expired_at.isoformat(),
            "reversion_status": self.reversion_status,
        }, sort_keys=True).encode("utf-8")
```

**Enum Pattern** (from `ActionType`):
```python
class OverrideReason(Enum):
    """Enumerated override reasons (FR28).

    Each reason must be documented and auditable.
    """
    TECHNICAL_FAILURE = "TECHNICAL_FAILURE"
    """Technical failure preventing normal operation."""

    CEREMONY_HEALTH = "CEREMONY_HEALTH"
    """Ceremony health check override (Tier 1)."""

    # ... etc
```

**Service Pattern** (from Story 5.1 `override_service.py`):
```python
# HALT FIRST pattern - MUST be first check
if await self._halt_checker.is_halted():
    reason = await self._halt_checker.get_halt_reason()
    log.critical("operation_rejected_system_halted", halt_reason=reason)
    raise SystemHaltedError(f"CT-11: System is halted: {reason}")
```

### Valid Override Reasons (FR28 - Architecture ADR-4)

| Reason Code | Description | Use Case |
|-------------|-------------|----------|
| `TECHNICAL_FAILURE` | Technical failure preventing normal operation | System bugs, crashes |
| `CEREMONY_HEALTH` | Ceremony health check override | Tier 1 ceremony issues |
| `EMERGENCY_HALT_CLEAR` | Emergency halt clearing | Critical system recovery |
| `CONFIGURATION_ERROR` | Configuration error correction | Misconfigurations |
| `WATCHDOG_INTERVENTION` | Watchdog intervention required | Watchdog-detected issues |
| `SECURITY_INCIDENT` | Security incident response | Active security threats |

### Duration Constraints

| Constraint | Value | Rationale |
|------------|-------|-----------|
| Minimum | 60 seconds (1 minute) | Prevent accidental instant expirations |
| Maximum | 604800 seconds (7 days) | Prevent long-term power consolidation |
| Default | N/A (required field) | Indefinite overrides prohibited |

### Key Dependencies (from Story 5.1)

- `EventWriterService` from Story 1.6 - for writing OverrideExpiredEvent
- `HaltChecker` port - for halt state check
- `OverrideEventPayload` from Story 5.1 - base override structure
- `OverrideService` from Story 5.1 - service to extend

### Project Structure Notes

**Files to Create:**
```
src/domain/models/override_reason.py              # New - OverrideReason enum
src/domain/services/duration_validator.py         # New - Duration validation
src/domain/services/__init__.py                   # New - Export services
src/application/ports/override_registry.py        # New - Registry port
src/application/services/override_expiration_service.py  # New - Expiration service
src/infrastructure/stubs/override_registry_stub.py       # New - Registry stub
tests/unit/domain/test_override_reason.py         # New
tests/unit/domain/test_duration_validator.py      # New
tests/unit/application/test_override_expiration_service.py  # New
tests/unit/infrastructure/test_override_registry_stub.py    # New
tests/integration/test_keeper_attribution_integration.py    # New
```

**Files to Modify:**
```
src/domain/events/override_event.py               # Add OverrideExpiredEventPayload, update validation
src/domain/errors/override.py                     # Add DurationValidationError, InvalidOverrideReasonError
src/domain/errors/__init__.py                     # Export new errors
src/domain/events/__init__.py                     # Export OverrideExpiredEventPayload
src/domain/models/__init__.py                     # Export OverrideReason
src/application/ports/__init__.py                 # Export OverrideRegistryPort
src/application/services/__init__.py              # Export OverrideExpirationService
src/application/services/override_service.py      # Integrate registry, validation
src/infrastructure/stubs/__init__.py              # Export OverrideRegistryStub
```

### Import Rules (Hexagonal Architecture)

- `domain/models/` imports ONLY from `domain/` and stdlib
- `domain/services/` imports from `domain/` and stdlib ONLY
- `application/services/` imports from `domain/` and `application/ports/`
- `infrastructure/stubs/` imports from `application/ports/`
- NEVER import from `infrastructure/` in `domain/` or `application/`

### Testing Standards

- ALL tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Mock `EventWriterService`, `HaltChecker`, `OverrideRegistryPort` in unit tests
- Integration tests use real stubs, in-memory event store
- Test expiration with mocked time (don't wait real seconds)

### Expiration Mechanism Design Decision

**Option A: Background Worker (Recommended)**
- Background async task polls registry every N seconds
- Simple, testable, follows existing patterns

**Option B: Database TTL/Scheduler**
- More complex, requires DB-level scheduler
- Not recommended for MVP

**Decision: Use Option A** - Create `OverrideExpirationService` that can be called by a background worker or scheduler. The service itself is stateless and testable.

### Cross-Story Integration Points

| Story | Integration | Notes |
|-------|-------------|-------|
| 5.1 | OverrideEventPayload | Extends with strict reason/duration validation |
| 5.3 | Public visibility | Scope and duration visible in /overrides endpoint |
| 5.5 | Trend analysis | Uses scope for pattern detection |
| 5.6 | Cryptographic signing | Signature covers scope/duration/reason |

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-5.2] - Story definition
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-4] - Key Custody + Keeper Adversarial Defense
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-6] - Amendment Tiers (override reasons)
- [Source: src/domain/events/override_event.py] - Story 5.1 override event pattern
- [Source: src/application/services/override_service.py] - Story 5.1 service pattern
- [Source: _bmad-output/implementation-artifacts/stories/5-1-override-immediate-logging.md] - Previous story learnings

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-07 | Story created with comprehensive context | Create-Story Workflow (Opus 4.5) |

### File List
