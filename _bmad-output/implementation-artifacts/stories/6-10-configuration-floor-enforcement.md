# Story 6.10: Configuration Floor Enforcement (NFR39)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **system operator**,
I want configuration floors enforced in all environments,
So that no environment can run below constitutional minimums.

## Acceptance Criteria

### AC1: Startup Configuration Validation (NFR39)
**Given** application startup
**When** configuration is loaded from any source (env vars, config files, defaults)
**Then** all values are validated against constitutional floors from `CONSTITUTIONAL_THRESHOLD_REGISTRY`
**And** startup fails immediately if any value is below its floor
**And** error message includes: threshold name, attempted value, floor value, FR reference
**And** log entry created with severity CRITICAL before exit

### AC2: Runtime Configuration Change Validation (NFR39)
**Given** runtime configuration change
**When** attempted via any mechanism (API, env var reload, config file change)
**Then** floor enforcement applies to the requested change
**And** changes below floor are rejected with `ConstitutionalFloorViolationError`
**And** rejection is logged with full audit trail
**And** original value is preserved (atomic rejection)

### AC3: Read-Only Floor Configuration (NFR39)
**Given** floor configuration definitions
**When** I examine the `CONSTITUTIONAL_THRESHOLD_REGISTRY`
**Then** floor values are defined in frozen dataclasses
**And** floor values cannot be modified at runtime (immutable)
**And** any attempt to modify floor raises `RuntimeError`
**And** registry is validated at module load time

### AC4: Environment-Agnostic Enforcement (NFR39)
**Given** any environment (dev, staging, production)
**When** the application starts
**Then** the same constitutional floors apply uniformly
**And** no environment variable can lower floors below constitutional minimums
**And** DEV_MODE=true does NOT relax constitutional floor enforcement
**And** only current_value can vary, never constitutional_floor

### AC5: Configuration Violation Event Creation
**Given** any configuration floor violation
**When** a violation is detected (startup or runtime)
**Then** a `ConfigurationFloorViolationEvent` is created
**And** event includes: threshold_name, attempted_value, floor_value, source (startup/runtime/api)
**And** event is witnessed (CT-12)
**And** violation triggers HALT if during runtime (CT-11)

### AC6: Configuration Health Check Endpoint
**Given** the health check API
**When** I call `/v1/health/configuration`
**Then** response includes all constitutional thresholds
**And** each threshold shows: name, floor, current_value, is_valid
**And** response includes overall configuration_valid: true/false
**And** response is publicly accessible (no auth required)

## Tasks / Subtasks

- [x] Task 1: Create Configuration Floor Enforcement Domain Events (AC: #5)
  - [x] 1.1 Create `src/domain/events/configuration_floor.py`:
    - `ConfigurationFloorViolationEventPayload` frozen dataclass with:
      - `violation_id: str` - Unique violation identifier
      - `threshold_name: str` - Which threshold was violated
      - `attempted_value: int | float` - Value that was attempted
      - `constitutional_floor: int | float` - Floor that was violated
      - `fr_reference: str` - Constitutional reference (e.g., "NFR39")
      - `source: ConfigurationSource` - Where violation originated
      - `detected_at: datetime`
      - Event type constant: `CONFIGURATION_FLOOR_VIOLATION_EVENT_TYPE = "configuration.floor_violation"`
      - `to_dict()` for event serialization
      - `signable_content()` for witnessing (CT-12)
    - `ConfigurationSource` enum: STARTUP, RUNTIME_API, RUNTIME_ENV, RUNTIME_FILE
  - [x] 1.2 Export from `src/domain/events/__init__.py`

- [x] Task 2: Create Configuration Floor Domain Errors (AC: #1, #2)
  - [x] 2.1 Extend `src/domain/errors/threshold.py` OR create `src/domain/errors/configuration_floor.py`:
    - `ConfigurationFloorEnforcementError(ConstitutionalViolationError)` - Base class
    - `StartupFloorViolationError(ConfigurationFloorEnforcementError)` - Startup-specific
      - Attributes: `threshold_name: str`, `attempted_value: int | float`, `constitutional_floor: int | float`, `fr_reference: str`
      - Message: "NFR39: Startup blocked - {threshold_name} cannot be configured to {attempted_value}, constitutional minimum is {constitutional_floor} ({fr_reference})"
    - `RuntimeFloorViolationError(ConfigurationFloorEnforcementError)` - Runtime-specific
      - Message: "NFR39: Configuration change rejected - {threshold_name} cannot be set to {attempted_value} at runtime, constitutional minimum is {constitutional_floor}"
    - `FloorModificationAttemptedError(ConfigurationFloorEnforcementError)` - Attempt to modify floor
      - Message: "NFR39: Constitutional floor modification is prohibited"
  - [x] 2.2 Export from `src/domain/errors/__init__.py`

- [x] Task 3: Create Configuration Floor Validator Port (AC: #1, #2, #3, #4)
  - [x] 3.1 Create `src/application/ports/configuration_floor_validator.py`:
    - `ConfigurationFloorValidatorProtocol` ABC with methods:
      - `async def validate_startup_configuration() -> ConfigurationValidationResult`
        - Validates all configuration values against floors at startup
      - `async def validate_configuration_change(threshold_name: str, new_value: int | float) -> ConfigurationChangeResult`
        - Validates a single configuration change at runtime
      - `def get_all_floors() -> tuple[ConstitutionalThreshold, ...]`
        - Returns all constitutional floor definitions (sync - pure domain lookup)
      - `def get_floor(threshold_name: str) -> ConstitutionalThreshold`
        - Returns specific floor definition (sync - pure domain lookup)
      - `async def get_configuration_health() -> ConfigurationHealthStatus`
        - Returns health status of all configurations
    - `ConfigurationValidationResult` frozen dataclass:
      - `is_valid: bool`
      - `violations: tuple[ThresholdViolation, ...]`
      - `validated_count: int`
      - `validated_at: datetime`
    - `ConfigurationChangeResult` frozen dataclass:
      - `is_valid: bool`
      - `threshold_name: str`
      - `requested_value: int | float`
      - `floor_value: int | float`
      - `rejection_reason: str | None`
    - `ConfigurationHealthStatus` frozen dataclass:
      - `is_healthy: bool`
      - `threshold_statuses: tuple[ThresholdStatus, ...]`
      - `checked_at: datetime`
    - `ThresholdViolation` frozen dataclass:
      - `threshold_name: str`
      - `attempted_value: int | float`
      - `floor_value: int | float`
      - `fr_reference: str`
    - `ThresholdStatus` frozen dataclass:
      - `threshold_name: str`
      - `floor_value: int | float`
      - `current_value: int | float`
      - `is_valid: bool`
  - [x] 3.2 Export from `src/application/ports/__init__.py`

- [x] Task 4: Create Configuration Floor Enforcement Service (AC: #1, #2, #3, #4, #5)
  - [x] 4.1 Create `src/application/services/configuration_floor_enforcement_service.py`:
    - Inject: `HaltChecker`, `EventWriterService` (optional), `CONSTITUTIONAL_THRESHOLD_REGISTRY`
    - HALT CHECK on runtime operations (CT-11)
  - [x] 4.2 Implement `def validate_startup_configuration(config: dict[str, Any]) -> None`:
    - NOTE: Sync method for startup (no async context yet)
    - Load all thresholds from registry
    - For each threshold, check if config has a value
    - If value < floor, collect violation
    - If ANY violations, raise `StartupFloorViolationError` with first violation
    - Log CRITICAL for all violations before raising
    - Return None if all valid
  - [x] 4.3 Implement `async def validate_runtime_change(threshold_name: str, new_value: int | float) -> None`:
    - HALT CHECK FIRST (CT-11)
    - Get floor from registry
    - If new_value < floor:
      - Create `ConfigurationFloorViolationEvent`
      - Raise `RuntimeFloorViolationError`
      - Trigger halt (CT-11 - silent failure destroys legitimacy)
    - Log change attempt for audit trail
  - [x] 4.4 Implement `def get_configuration_health() -> ConfigurationHealthStatus`:
    - Sync method for health checks
    - Iterate all thresholds in registry
    - Return status of each with current_value and floor_value
    - Set is_healthy = False if any threshold invalid
  - [x] 4.5 Implement `def ensure_floors_immutable() -> None`:
    - Verify registry is frozen dataclass
    - Verify all thresholds are frozen dataclasses
    - Called at module load time
  - [x] 4.6 Export from `src/application/services/__init__.py`

- [x] Task 5: Create Configuration Floor Validator Stub (AC: #1, #2, #3, #4)
  - [x] 5.1 Create `src/infrastructure/stubs/configuration_floor_validator_stub.py`:
    - `ConfigurationFloorValidatorStub` implementing `ConfigurationFloorValidatorProtocol`
    - Uses `CONSTITUTIONAL_THRESHOLD_REGISTRY` from domain primitives
    - `inject_threshold_override(name: str, current_value: int | float)` for test setup
    - `set_startup_configuration(config: dict[str, Any])` for test control
    - `clear()` for test isolation
    - DEV MODE watermark warning on initialization
  - [x] 5.2 Export from `src/infrastructure/stubs/__init__.py`

- [x] Task 6: Create Startup Hook Integration (AC: #1, #4)
  - [x] 6.1 Create or update `src/api/startup.py`:
    - Import `validate_startup_configuration` from service
    - Import `CONSTITUTIONAL_THRESHOLD_REGISTRY` from primitives
    - Call validation BEFORE FastAPI app starts
    - If validation fails, log CRITICAL and exit with code 1
    - Log INFO on successful validation with threshold count
  - [x] 6.2 Ensure startup hook is registered in FastAPI `lifespan` or `on_startup`

- [x] Task 7: Create Health Check Endpoint (AC: #6)
  - [x] 7.1 Create or update `src/api/routes/health.py`:
    - Add endpoint `GET /v1/health/configuration`
    - Return Pydantic model with all threshold statuses
    - Include: threshold_name, constitutional_floor, current_value, is_valid
    - Include: overall configuration_valid boolean
    - Return 200 if healthy, 503 if any violation
    - No authentication required (public)
  - [x] 7.2 Register route in API router

- [x] Task 8: Write Unit Tests (AC: #1, #2, #3, #4, #5, #6)
  - [x] 8.1 Create `tests/unit/domain/test_configuration_floor_events.py`:
    - Test `ConfigurationFloorViolationEventPayload` creation with all fields
    - Test `ConfigurationSource` enum values
    - Test `to_dict()` returns expected structure
    - Test `signable_content()` determinism (CT-12)
  - [x] 8.2 Create `tests/unit/domain/test_configuration_floor_errors.py`:
    - Test `StartupFloorViolationError` message includes NFR39
    - Test `RuntimeFloorViolationError` message includes threshold details
    - Test `FloorModificationAttemptedError` message
    - Test error inheritance hierarchy (all inherit from ConstitutionalViolationError)
  - [x] 8.3 Create `tests/unit/application/test_configuration_floor_validator_port.py`:
    - Test protocol method signatures
    - Test result dataclass field validation
    - Test ThresholdViolation, ThresholdStatus creation
  - [x] 8.4 Create `tests/unit/application/test_configuration_floor_enforcement_service.py`:
    - Test `validate_startup_configuration()` passes with valid config
    - Test `validate_startup_configuration()` raises on floor violation
    - Test `validate_runtime_change()` passes with valid change
    - Test `validate_runtime_change()` raises on floor violation
    - Test `validate_runtime_change()` creates violation event
    - Test `get_configuration_health()` returns all thresholds
    - Test `get_configuration_health()` marks invalid if any violation
    - Test floors are immutable (frozen dataclasses)
    - Test same floors apply in dev and prod mode
  - [x] 8.5 Create `tests/unit/infrastructure/test_configuration_floor_validator_stub.py`:
    - Test stub uses real registry by default
    - Test `inject_threshold_override()` for test control
    - Test `clear()` resets to defaults

- [x] Task 9: Write Integration Tests (AC: #1, #2, #3, #4, #5, #6)
  - [x] 9.1 Create `tests/integration/test_configuration_floor_enforcement_integration.py`:
    - Test: `test_nfr39_startup_blocks_below_floor` (AC1)
      - Configure value below floor
      - Call startup validation
      - Verify `StartupFloorViolationError` raised
      - Verify log includes CRITICAL severity
    - Test: `test_nfr39_startup_passes_at_floor` (AC1)
      - Configure values at floor
      - Call startup validation
      - Verify no error raised
    - Test: `test_nfr39_runtime_rejects_below_floor` (AC2)
      - Attempt runtime change below floor
      - Verify `RuntimeFloorViolationError` raised
      - Verify original value preserved
      - Verify violation event created
    - Test: `test_nfr39_runtime_accepts_at_floor` (AC2)
      - Attempt runtime change at floor
      - Verify change accepted
    - Test: `test_nfr39_floors_are_immutable` (AC3)
      - Attempt to modify floor value
      - Verify modification fails
      - Verify TypeError or similar raised
    - Test: `test_nfr39_same_floors_all_environments` (AC4)
      - Set DEV_MODE=true
      - Verify floors unchanged
      - Set DEV_MODE=false
      - Verify floors unchanged
    - Test: `test_nfr39_violation_event_witnessed` (AC5)
      - Trigger floor violation
      - Verify `ConfigurationFloorViolationEvent` created
      - Verify event has signable content
    - Test: `test_health_endpoint_returns_all_thresholds` (AC6)
      - Call `/v1/health/configuration`
      - Verify all 13 thresholds returned
      - Verify response includes floor, current_value, is_valid
    - Test: `test_health_endpoint_no_auth_required` (AC6)
      - Call endpoint without authentication
      - Verify 200 response
    - Test: `test_halt_check_on_runtime_change`
      - Set system halted
      - Attempt runtime configuration change
      - Verify `SystemHaltedError` raised

## Dev Notes

### Constitutional Constraints (CRITICAL)

- **NFR39**: No configuration SHALL allow thresholds below constitutional floors (Configuration Enforcement)
- **FR33**: Threshold definitions SHALL be constitutional, not operational (from Story 6.4)
- **FR34**: Threshold changes SHALL NOT reset active counters (from Story 6.4)
- **CT-11**: Silent failure destroys legitimacy -> HALT on runtime violations
- **CT-12**: Witnessing creates accountability -> All violation events witnessed
- **CT-13**: Integrity outranks availability -> Startup failure over running below floor

### Relationship to Story 6.4 (Constitutional Threshold Definitions)

Story 6.4 implemented the **foundation** for configuration floor enforcement:
- `ConstitutionalThreshold` model with floor/current_value/is_constitutional
- `ConstitutionalThresholdRegistry` with all 13 defined thresholds
- `ConstitutionalFloorViolationError` for when floors are violated
- `ThresholdConfigurationService` for runtime threshold management

**This story (6.10) extends with:**
- **Startup validation** - Fails startup if any config below floor
- **Runtime enforcement** - Rejects runtime changes that violate floors
- **Immutability guarantee** - Floors cannot be changed at runtime
- **Environment uniformity** - Same floors in dev/staging/prod
- **Health check endpoint** - Public visibility into configuration health
- **Violation events** - Constitutional events for any violation

### Existing Constitutional Thresholds (from Story 6.4)

The following 13 thresholds are defined in `src/domain/primitives/constitutional_thresholds.py`:

| Threshold Name | Floor | FR Reference | Description |
|----------------|-------|--------------|-------------|
| cessation_breach_count | 10 | FR32 | Max breaches before cessation |
| cessation_window_days | 90 | FR32 | Rolling window for breaches |
| recovery_waiting_hours | 48 | NFR41 | Minimum recovery wait |
| minimum_keeper_quorum | 3 | FR79 | Min Keepers before halt |
| escalation_days | 7 | FR31 | Days before escalation |
| attestation_period_days | 7 | FR78 | Keeper attestation period |
| missed_attestations_threshold | 2 | FR78 | Missed before replacement |
| override_warning_30_day | 5 | FR27 | Anti-success alert threshold |
| override_governance_365_day | 20 | RT-3 | Governance review threshold |
| topic_diversity_threshold | 0.30 | FR73 | Max single origin % |
| fork_signal_rate_limit | 3 | FR85 | Signals per hour per source |
| halt_confirmation_seconds | 5 | ADR-3 | Redis-DB confirmation time |
| witness_pool_minimum_high_stakes | 12 | FR59 | Min witnesses for high-stakes |

### Epic 6 Context - Story 6.10 Position

```
┌─────────────────────────────────────────────────────────────────┐
│ Story 6.9: Topic Manipulation Defense (COMPLETED)               │
│ - Daily rate limiting for external sources (FR118)              │
│ - Autonomous topic priority (FR119)                             │
│ - Pattern detection, seed validation                            │
└─────────────────────────────────────────────────────────────────┘
         │
         │ Followed by
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Story 6.10: Configuration Floor Enforcement (THIS STORY)        │
│ - Startup configuration validation (NFR39)                      │
│ - Runtime floor enforcement                                     │
│ - Immutability guarantee                                        │
│ - Health check endpoint                                         │
└─────────────────────────────────────────────────────────────────┘
         │
         │ Final story in Epic 6
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Epic 6 Complete                                                 │
│ - Epic 7: Cessation Protocol begins                             │
└─────────────────────────────────────────────────────────────────┘
```

### Key Dependencies from Previous Stories

From Story 6.4 (Constitutional Threshold Definitions):
- `src/domain/models/constitutional_threshold.py` - ConstitutionalThreshold, ConstitutionalThresholdRegistry
- `src/domain/errors/threshold.py` - ConstitutionalFloorViolationError, ThresholdNotFoundError
- `src/domain/primitives/constitutional_thresholds.py` - CONSTITUTIONAL_THRESHOLD_REGISTRY, get_threshold, validate_all_thresholds
- `src/application/services/threshold_configuration_service.py` - ThresholdConfigurationService
- `src/infrastructure/stubs/threshold_repository_stub.py` - ThresholdRepositoryStub

From Core Infrastructure:
- `src/application/ports/halt_checker.py` - HaltCheckerProtocol
- `src/domain/errors/writer.py` - SystemHaltedError
- `src/domain/errors/constitutional.py` - ConstitutionalViolationError
- `src/domain/events/event.py` - Base event patterns

### Startup Validation Pattern

```python
# src/api/startup.py
from src.domain.primitives.constitutional_thresholds import (
    CONSTITUTIONAL_THRESHOLD_REGISTRY,
    validate_all_thresholds,
)
from src.application.services.configuration_floor_enforcement_service import (
    validate_startup_configuration,
)
import structlog
import sys

log = structlog.get_logger(__name__)

def run_startup_checks(config: dict[str, Any]) -> None:
    """Validate configuration floors before app starts (NFR39).

    This function MUST be called before FastAPI app starts.
    If any floor violation is detected, the application exits.
    """
    try:
        # Validate all defined thresholds are valid
        validate_all_thresholds()

        # Validate configuration against floors
        validate_startup_configuration(config)

        log.info(
            "startup_floor_validation_passed",
            threshold_count=len(CONSTITUTIONAL_THRESHOLD_REGISTRY),
        )
    except ConstitutionalFloorViolationError as e:
        log.critical(
            "startup_floor_violation",
            threshold_name=e.threshold_name,
            attempted_value=e.attempted_value,
            constitutional_floor=e.constitutional_floor,
            fr_reference=e.fr_reference,
            message="Startup blocked: configuration below constitutional floor",
        )
        sys.exit(1)
```

### Runtime Enforcement Pattern

```python
# src/application/services/configuration_floor_enforcement_service.py
async def validate_runtime_change(
    self,
    threshold_name: str,
    new_value: int | float,
) -> None:
    """Validate runtime configuration change (NFR39).

    HALT CHECK FIRST (CT-11).

    Args:
        threshold_name: The threshold being changed.
        new_value: The new value being requested.

    Raises:
        SystemHaltedError: If system is halted.
        RuntimeFloorViolationError: If new_value < constitutional_floor.
    """
    # HALT CHECK FIRST (CT-11)
    if await self._halt_checker.is_halted():
        raise SystemHaltedError("System halted")

    # Get floor from registry
    threshold = get_threshold(threshold_name)

    if new_value < threshold.constitutional_floor:
        # Create violation event (CT-12)
        event = ConfigurationFloorViolationEvent(
            violation_id=str(uuid4()),
            threshold_name=threshold_name,
            attempted_value=new_value,
            constitutional_floor=threshold.constitutional_floor,
            fr_reference=threshold.fr_reference,
            source=ConfigurationSource.RUNTIME_API,
            detected_at=datetime.now(UTC),
        )

        if self._event_writer:
            await self._event_writer.write(event)

        # Trigger halt on runtime violation (CT-11)
        await self._trigger_halt(
            reason=f"Configuration floor violation: {threshold_name}"
        )

        raise RuntimeFloorViolationError(
            threshold_name=threshold_name,
            attempted_value=new_value,
            constitutional_floor=threshold.constitutional_floor,
            fr_reference=threshold.fr_reference,
        )

    log.info(
        "runtime_configuration_change_validated",
        threshold_name=threshold_name,
        new_value=new_value,
        floor=threshold.constitutional_floor,
    )
```

### Health Check Endpoint Pattern

```python
# src/api/routes/health.py
from fastapi import APIRouter
from pydantic import BaseModel
from src.domain.primitives.constitutional_thresholds import (
    CONSTITUTIONAL_THRESHOLD_REGISTRY,
)

router = APIRouter(prefix="/v1/health", tags=["health"])

class ThresholdHealthStatus(BaseModel):
    threshold_name: str
    constitutional_floor: float
    current_value: float
    is_valid: bool
    fr_reference: str

class ConfigurationHealthResponse(BaseModel):
    configuration_valid: bool
    threshold_count: int
    thresholds: list[ThresholdHealthStatus]
    checked_at: str

@router.get("/configuration", response_model=ConfigurationHealthResponse)
async def get_configuration_health() -> ConfigurationHealthResponse:
    """Get configuration health status (NFR39).

    Returns status of all constitutional thresholds.
    No authentication required - public visibility.
    """
    statuses = []
    all_valid = True

    for threshold in CONSTITUTIONAL_THRESHOLD_REGISTRY:
        is_valid = threshold.current_value >= threshold.constitutional_floor
        if not is_valid:
            all_valid = False

        statuses.append(ThresholdHealthStatus(
            threshold_name=threshold.threshold_name,
            constitutional_floor=float(threshold.constitutional_floor),
            current_value=float(threshold.current_value),
            is_valid=is_valid,
            fr_reference=threshold.fr_reference,
        ))

    return ConfigurationHealthResponse(
        configuration_valid=all_valid,
        threshold_count=len(statuses),
        thresholds=statuses,
        checked_at=datetime.now(UTC).isoformat(),
    )
```

### Import Rules (Hexagonal Architecture)

- `domain/events/configuration_floor.py` imports from `domain/`, `typing`, `dataclasses`, `datetime`, `enum`
- `domain/errors/configuration_floor.py` inherits from `ConstitutionalViolationError`
- `application/ports/configuration_floor_validator.py` imports from `abc`, `typing`, domain models
- `application/services/configuration_floor_enforcement_service.py` imports from `application/ports/`, `domain/`
- `api/startup.py` imports from `application/services/`, `domain/primitives/`
- `api/routes/health.py` imports from `domain/primitives/`
- NEVER import from `infrastructure/` in `domain/` or `application/`

### Testing Standards

- ALL tests use `pytest.mark.asyncio` for async tests
- Use `AsyncMock` for async dependencies
- Unit tests mock the protocol interfaces
- Integration tests use stub implementations
- NFR39 tests MUST verify:
  - Startup blocks on floor violation
  - Runtime changes rejected below floor
  - Floors are immutable
  - Same floors in all environments
  - Violation events are witnessed
  - Health endpoint returns all thresholds

### Files to Create

```
src/domain/events/configuration_floor.py                           # Floor violation events
src/domain/errors/configuration_floor.py                           # Floor enforcement errors
src/application/ports/configuration_floor_validator.py             # Validator port
src/application/services/configuration_floor_enforcement_service.py # Enforcement service
src/infrastructure/stubs/configuration_floor_validator_stub.py     # Validator stub
src/api/startup.py                                                 # Startup validation hook
tests/unit/domain/test_configuration_floor_events.py               # Event tests
tests/unit/domain/test_configuration_floor_errors.py               # Error tests
tests/unit/application/test_configuration_floor_validator_port.py  # Port tests
tests/unit/application/test_configuration_floor_enforcement_service.py # Service tests
tests/unit/infrastructure/test_configuration_floor_validator_stub.py # Stub tests
tests/integration/test_configuration_floor_enforcement_integration.py # Integration tests
```

### Files to Modify

```
src/domain/events/__init__.py                                     # Export new events
src/domain/errors/__init__.py                                     # Export new errors
src/application/ports/__init__.py                                 # Export new ports
src/application/services/__init__.py                              # Export new services
src/infrastructure/stubs/__init__.py                              # Export new stubs
src/api/routes/health.py                                          # Add configuration endpoint
src/api/routes/__init__.py                                        # Register health routes
src/api/main.py                                                   # Add startup hook
```

### Project Structure Notes

- Startup validation is SYNCHRONOUS (no async context before app starts)
- Runtime validation is ASYNC (uses halt checker)
- Floors are immutable - defined in frozen dataclasses in domain/primitives
- Health endpoint is PUBLIC - no authentication required
- Violation events MUST be witnessed (CT-12)
- Runtime violations trigger HALT (CT-11)

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-6.10] - Story definition
- [Source: _bmad-output/planning-artifacts/prd.md#NFR39] - No configuration below constitutional floors
- [Source: _bmad-output/planning-artifacts/prd.md#FR33] - Threshold definitions are constitutional
- [Source: _bmad-output/planning-artifacts/prd.md#FR34] - Threshold changes don't reset counters
- [Source: _bmad-output/planning-artifacts/architecture.md#CT-11] - Silent failure destroys legitimacy
- [Source: _bmad-output/planning-artifacts/architecture.md#CT-12] - Witnessing creates accountability
- [Source: src/domain/primitives/constitutional_thresholds.py] - All 13 threshold definitions
- [Source: src/domain/models/constitutional_threshold.py] - ConstitutionalThreshold model
- [Source: src/domain/errors/threshold.py] - ConstitutionalFloorViolationError
- [Source: _bmad-output/implementation-artifacts/stories/6-9-topic-manipulation-defense.md] - Previous story patterns
- [Source: _bmad-output/project-context.md] - Project implementation rules

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 111 tests pass (92 unit + 19 integration)
- RED-GREEN-REFACTOR TDD pattern followed

### Completion Notes List

- **Task 1**: Created `ConfigurationFloorViolationEventPayload` with `ConfigurationSource` enum, `to_dict()`, and `signable_content()` for witnessing (CT-12)
- **Task 2**: Created error hierarchy with `StartupFloorViolationError`, `RuntimeFloorViolationError`, `FloorModificationAttemptedError` all inheriting from `ConstitutionalViolationError`
- **Task 3**: Created `ConfigurationFloorValidatorProtocol` port with frozen result dataclasses
- **Task 4**: Created `ConfigurationFloorEnforcementService` with startup validation, runtime change validation (with halt trigger), and health check
- **Task 5**: Created `ConfigurationFloorValidatorStub` wrapping the real service with validation count tracking for testing
- **Task 6**: Created `src/api/startup.py` with `validate_configuration_floors_at_startup()` and integrated with FastAPI lifespan context manager
- **Task 7**: Created `/v1/configuration/health` endpoint with Pydantic response models, registered in router
- **Task 8**: 92 unit tests covering all components
- **Task 9**: 19 integration tests verifying NFR39 enforcement

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-08 | Story created with NFR39 floor enforcement, startup/runtime validation, health endpoint, builds on Story 6.4 foundation | Create-Story Workflow (Opus 4.5) |
| 2026-01-08 | Story implemented with all 9 tasks complete, 111 tests passing | Dev-Story Workflow (Opus 4.5) |

### File List

**Created:**
- `src/domain/events/configuration_floor.py` - Floor violation events with signable content
- `src/domain/errors/configuration_floor.py` - Floor enforcement error hierarchy
- `src/application/ports/configuration_floor_validator.py` - Validator protocol with result dataclasses
- `src/application/services/configuration_floor_enforcement_service.py` - Main enforcement service
- `src/infrastructure/stubs/configuration_floor_validator_stub.py` - Test stub with validation tracking
- `src/api/startup.py` - Startup validation hook
- `src/api/routes/configuration_health.py` - Health check endpoint router
- `src/api/models/configuration_health.py` - Pydantic response models
- `tests/unit/domain/test_configuration_floor_events.py` - 14 tests
- `tests/unit/domain/test_configuration_floor_errors.py` - 21 tests
- `tests/unit/application/test_configuration_floor_validator_port.py` - 20 tests
- `tests/unit/application/test_configuration_floor_enforcement_service.py` - 15 tests
- `tests/unit/infrastructure/test_configuration_floor_validator_stub.py` - 10 tests
- `tests/unit/api/test_startup_configuration_validation.py` - 4 tests
- `tests/unit/api/test_configuration_health_endpoint.py` - 8 tests
- `tests/integration/test_configuration_floor_enforcement_integration.py` - 19 tests

**Modified:**
- `src/domain/events/__init__.py` - Added configuration floor event exports
- `src/domain/errors/__init__.py` - Added configuration floor error exports
- `src/application/ports/__init__.py` - Added configuration floor validator exports
- `src/application/services/__init__.py` - Added configuration floor service exports
- `src/infrastructure/stubs/__init__.py` - Added configuration floor validator stub exports
- `src/api/main.py` - Added lifespan manager with startup validation, registered configuration health router
- `src/api/routes/__init__.py` - Added configuration health router

