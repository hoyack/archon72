# Story 6.4: Constitutional Threshold Definitions (FR33-FR34)

Status: done

## Story

As a **system operator**,
I want thresholds defined as constitutional (not operational),
So that they cannot be lowered below minimums.

## Acceptance Criteria

### AC1: Constitutional Threshold Model (FR33)
**Given** threshold configuration
**When** I examine threshold definitions
**Then** each includes: `threshold_name`, `constitutional_floor`, `current_value`
**And** `is_constitutional` flag is TRUE for protected thresholds

### AC2: Floor Enforcement (NFR39)
**Given** an attempt to set a threshold below constitutional floor
**When** the change is attempted
**Then** it is rejected
**And** error includes "FR33: Constitutional floor violation"

### AC3: Counter Preservation (FR34)
**Given** a threshold is changed
**When** the change is recorded
**Then** breach counters are NOT reset
**And** historical breach counts are preserved

## Tasks / Subtasks

- [ ] Task 1: Create Constitutional Threshold Domain Model (AC: #1)
  - [ ] 1.1 Create `src/domain/models/constitutional_threshold.py`:
    - `ConstitutionalThreshold` frozen dataclass with: `threshold_name`, `constitutional_floor`, `current_value`, `is_constitutional`, `description`, `fr_reference`
    - `is_valid()` property that checks `current_value >= constitutional_floor`
    - `validate()` method that raises `ConstitutionalFloorViolationError` if invalid
    - `to_dict()` for serialization
    - `__post_init__` validation to ensure floor <= current on creation
  - [ ] 1.2 Create `ConstitutionalThresholdRegistry` frozen dataclass:
    - Registry of all defined constitutional thresholds
    - Factory method `get_all_thresholds()` returning tuple of defined thresholds
    - `get_threshold(name: str)` method for lookup
    - `validate_all()` method that checks all thresholds
  - [ ] 1.3 Export from `src/domain/models/__init__.py`

- [ ] Task 2: Define Constitutional Threshold Constants (AC: #1)
  - [ ] 2.1 Create `src/domain/primitives/constitutional_thresholds.py`:
    - Define all constitutional thresholds with floors:
      - `CESSATION_BREACH_THRESHOLD`: floor=10, current=10 (FR32: >10 breaches in 90 days)
      - `CESSATION_WINDOW_DAYS`: floor=90, current=90 (FR32: rolling window)
      - `RECOVERY_WAITING_HOURS`: floor=48, current=48 (FR21, NFR41: 48-hour minimum)
      - `MINIMUM_KEEPER_QUORUM`: floor=3, current=3 (FR79: minimum Keepers)
      - `WITNESS_MINIMUM_HIGH_STAKES`: floor=12, current=12 (witness pool minimum)
      - `HALT_CHANNEL_CONFIRMATION_SECONDS`: floor=5, current=5 (ADR-3: Redis-DB confirmation)
      - `ESCALATION_DAYS`: floor=7, current=7 (FR31: 7-day escalation)
      - `ATTESTATION_PERIOD_DAYS`: floor=7, current=7 (FR78: weekly attestation)
      - `MISSED_ATTESTATIONS_THRESHOLD`: floor=2, current=2 (FR78: replacement trigger)
      - `OVERRIDE_WARNING_30_DAY`: floor=5, current=5 (FR27: anti-success alert)
      - `OVERRIDE_GOVERNANCE_365_DAY`: floor=20, current=20 (RT-3: governance review)
      - `TOPIC_DIVERSITY_THRESHOLD`: floor=0.30, current=0.30 (FR73: 30% max)
      - `FORK_SIGNAL_RATE_LIMIT`: floor=3, current=3 (FR85: signals per hour)
    - All defined as `ConstitutionalThreshold` instances
    - Include FR/NFR references in descriptions
  - [ ] 2.2 Create `CONSTITUTIONAL_THRESHOLD_REGISTRY` constant with all thresholds
  - [ ] 2.3 Export from `src/domain/primitives/__init__.py`

- [ ] Task 3: Create Constitutional Floor Violation Error (AC: #2)
  - [ ] 3.1 Create `src/domain/errors/threshold.py`:
    - `ThresholdError(ConstitutionalViolationError)` - base class
    - `ConstitutionalFloorViolationError(ThresholdError)` - floor violation
      - Attributes: `threshold_name`, `attempted_value`, `constitutional_floor`, `fr_reference`
      - Message format: "FR33: Constitutional floor violation - {threshold_name} cannot be set to {attempted_value}, minimum is {constitutional_floor}"
    - `ThresholdNotFoundError(ThresholdError)` - unknown threshold
    - `CounterResetAttemptedError(ThresholdError)` - FR34 violation for counter reset attempt
  - [ ] 3.2 Export from `src/domain/errors/__init__.py`

- [ ] Task 4: Create Threshold Configuration Service (AC: #1, #2, #3)
  - [ ] 4.1 Create `src/application/services/threshold_configuration_service.py`:
    - Inject: `HaltChecker`, `EventWriterService` (optional), `ThresholdRepository` (optional)
    - HALT CHECK FIRST at every operation boundary (CT-11)
  - [ ] 4.2 Implement `get_threshold(name: str) -> ConstitutionalThreshold`:
    - HALT CHECK FIRST (CT-11)
    - Look up threshold by name from registry
    - Return threshold definition with current value
    - Raise `ThresholdNotFoundError` if not found
  - [ ] 4.3 Implement `get_all_thresholds() -> list[ConstitutionalThreshold]`:
    - HALT CHECK FIRST (CT-11)
    - Return all constitutional thresholds with current values
    - Include constitutional flag for each
  - [ ] 4.4 Implement `validate_threshold_value(name: str, proposed_value: int | float) -> bool`:
    - HALT CHECK FIRST (CT-11)
    - Get threshold definition
    - Check proposed_value >= constitutional_floor
    - Return True if valid, raise `ConstitutionalFloorViolationError` if invalid
    - Log validation attempt with result
  - [ ] 4.5 Implement `update_threshold(name: str, new_value: int | float) -> ConstitutionalThreshold`:
    - HALT CHECK FIRST (CT-11)
    - Validate new_value against constitutional floor (FR33)
    - CRITICAL: Do NOT reset any counters (FR34)
    - If EventWriterService provided, write `ThresholdUpdatedEvent`
    - Return updated threshold definition
    - Raise `ConstitutionalFloorViolationError` if below floor
  - [ ] 4.6 Export from `src/application/services/__init__.py`

- [ ] Task 5: Create Threshold Updated Event (AC: #3)
  - [ ] 5.1 Create `src/domain/events/threshold.py`:
    - `ThresholdUpdatedEventPayload` frozen dataclass with:
      - `threshold_name`: Name of the threshold
      - `previous_value`: Value before update
      - `new_value`: Value after update
      - `constitutional_floor`: The floor that was enforced
      - `fr_reference`: FR reference (e.g., "FR33")
      - `updated_at`: datetime
      - `updated_by`: Agent/Keeper ID
    - `to_dict()` method for event writing
    - `signable_content()` for witnessing (CT-12)
    - Event type constant: `THRESHOLD_UPDATED_EVENT_TYPE = "threshold.updated"`
  - [ ] 5.2 Export from `src/domain/events/__init__.py`

- [ ] Task 6: Create Threshold Port (AC: #1, #2)
  - [ ] 6.1 Create `src/application/ports/threshold_configuration.py`:
    - `ThresholdConfigurationProtocol` with methods:
      - `async def get_threshold(name: str) -> ConstitutionalThreshold`
      - `async def get_all_thresholds() -> list[ConstitutionalThreshold]`
      - `async def validate_threshold_value(name: str, proposed_value: int | float) -> bool`
      - `async def update_threshold(name: str, new_value: int | float, updated_by: str) -> ConstitutionalThreshold`
    - Document FR33/FR34/NFR39 constraints
  - [ ] 6.2 Create `ThresholdRepositoryProtocol` for persistence (optional stub):
    - `async def save_threshold_override(name: str, value: int | float) -> None`
    - `async def get_threshold_override(name: str) -> Optional[int | float]`
  - [ ] 6.3 Export from `src/application/ports/__init__.py`

- [ ] Task 7: Create Threshold Repository Stub (AC: #1)
  - [ ] 7.1 Create `src/infrastructure/stubs/threshold_repository_stub.py`:
    - In-memory storage with `dict[str, int | float]` for overrides
    - Implement all protocol methods
    - `clear()` for test cleanup
    - DEV MODE watermark warning on initialization
  - [ ] 7.2 Export from `src/infrastructure/stubs/__init__.py`

- [ ] Task 8: Write Unit Tests (AC: #1, #2, #3)
  - [ ] 8.1 Create `tests/unit/domain/test_constitutional_threshold.py`:
    - Test `ConstitutionalThreshold` creation with required fields
    - Test `is_valid()` returns True when current >= floor
    - Test `is_valid()` returns False when current < floor
    - Test `validate()` passes when valid
    - Test `validate()` raises `ConstitutionalFloorViolationError` when invalid
    - Test `to_dict()` returns expected structure
    - Test `__post_init__` rejects creation with invalid values
    - Test threshold immutability (frozen dataclass)
  - [ ] 8.2 Create `tests/unit/domain/test_constitutional_thresholds.py`:
    - Test all defined thresholds exist in registry
    - Test all floors are correctly defined
    - Test `get_threshold()` returns correct threshold
    - Test `get_threshold()` raises for unknown name
    - Test `validate_all()` passes with default values
    - Test each threshold has FR/NFR reference in description
  - [ ] 8.3 Create `tests/unit/domain/test_threshold_errors.py`:
    - Test `ConstitutionalFloorViolationError` message includes FR33
    - Test `ConstitutionalFloorViolationError` includes threshold details
    - Test error inheritance hierarchy
    - Test `ThresholdNotFoundError` message
    - Test `CounterResetAttemptedError` message includes FR34
  - [ ] 8.4 Create `tests/unit/application/test_threshold_configuration_service.py`:
    - Test `get_threshold()` returns threshold with correct values
    - Test `get_threshold()` raises for unknown threshold
    - Test `get_all_thresholds()` returns all thresholds
    - Test `validate_threshold_value()` passes for valid values
    - Test `validate_threshold_value()` raises `ConstitutionalFloorViolationError` for below-floor values
    - Test `validate_threshold_value()` passes for exactly-at-floor values
    - Test `update_threshold()` succeeds for valid values
    - Test `update_threshold()` fails for below-floor values
    - Test `update_threshold()` writes event when EventWriter provided
    - Test HALT CHECK on all operations
  - [ ] 8.5 Create `tests/unit/domain/test_threshold_updated_event.py`:
    - Test `ThresholdUpdatedEventPayload` creation
    - Test `to_dict()` returns dict (not bytes)
    - Test `signable_content()` determinism
    - Test payload immutability (frozen dataclass)
  - [ ] 8.6 Create `tests/unit/infrastructure/test_threshold_repository_stub.py`:
    - Test all repository methods
    - Test override storage and retrieval
    - Test `clear()` method

- [ ] Task 9: Write Integration Tests (AC: #1, #2, #3)
  - [ ] 9.1 Create `tests/integration/test_constitutional_threshold_integration.py`:
    - Test: `test_fr33_threshold_includes_floor_definition` (AC1)
    - Test: `test_fr33_threshold_includes_is_constitutional_flag` (AC1)
    - Test: `test_nfr39_rejects_below_floor_value` (AC2)
    - Test: `test_nfr39_error_message_includes_fr33_reference` (AC2)
    - Test: `test_fr34_counter_not_reset_on_threshold_change` (AC3)
    - Test: `test_threshold_update_creates_witnessed_event` (AC3, CT-12)
    - Test: `test_halt_check_prevents_threshold_operations_during_halt`
    - Test: `test_all_existing_thresholds_at_or_above_floor`
    - Test: `test_cessation_threshold_is_constitutional`
    - Test: `test_recovery_waiting_period_is_constitutional`
    - Test: `test_keeper_quorum_is_constitutional`

## Dev Notes

### Constitutional Constraints (CRITICAL)

- **FR33**: Threshold definitions SHALL be constitutional, not operational
- **FR34**: Threshold changes SHALL NOT reset active counters
- **NFR39**: No configuration SHALL allow thresholds below constitutional floors
- **CT-11**: Silent failure destroys legitimacy -> HALT CHECK FIRST at every operation
- **CT-12**: Witnessing creates accountability -> Threshold changes must be witnessed

### Epic 6 Context - Story 6.4 Position

Story 6.4 defines the constitutional threshold system used throughout the application. This is foundational infrastructure that Stories 6.1-6.3 depend on conceptually (they use hardcoded constants today) and that Story 6.10 will enforce at runtime.

```
┌─────────────────────────────────────────────────────────────────┐
│ Constitutional Threshold Registry (Story 6.4)                    │
│ - Defines all protected thresholds                               │
│ - Enforces floors (FR33, NFR39)                                  │
│ - Prevents counter resets (FR34)                                 │
└─────────────────────────────────────────────────────────────────┘
         │
         │ Uses thresholds
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Dependent Services                                               │
│ - CessationConsiderationService (Story 6.3): CESSATION_THRESHOLD │
│ - EscalationService (Story 6.2): ESCALATION_THRESHOLD_DAYS       │
│ - RecoveryCoordinator (Story 3.6): RECOVERY_WAITING_HOURS        │
│ - KeeperAvailabilityService (Story 5.8): MINIMUM_KEEPER_QUORUM   │
│ - OverrideTrendService (Story 5.5): OVERRIDE thresholds          │
└─────────────────────────────────────────────────────────────────┘
         │
         │ Enforces at startup/runtime
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Story 6.10: Configuration Floor Enforcement (NFR39)              │
│ - Validates all values against floors at startup                 │
│ - Rejects runtime changes below floors                          │
└─────────────────────────────────────────────────────────────────┘
```

### Key Dependencies from Previous Stories

From existing codebase:
- `src/domain/models/breach_count_status.py`: Uses `CESSATION_THRESHOLD`, `WARNING_THRESHOLD`, `CESSATION_WINDOW_DAYS`
- `src/domain/models/pending_escalation.py`: Uses `ESCALATION_THRESHOLD_DAYS`
- `src/domain/models/keeper_attestation.py`: Uses `ATTESTATION_PERIOD_DAYS`, `MISSED_ATTESTATIONS_THRESHOLD`, `MINIMUM_KEEPER_QUORUM`
- `src/domain/models/recovery_waiting_period.py`: Uses `MINIMUM_WAITING_HOURS`
- `src/application/ports/topic_origin_tracker.py`: Uses `DIVERSITY_THRESHOLD`, `DIVERSITY_WINDOW_DAYS`
- `src/application/ports/fork_signal_rate_limiter.py`: Uses `RATE_LIMIT_THRESHOLD`, `RATE_LIMIT_WINDOW_HOURS`
- `src/application/services/override_trend_service.py`: Uses `PERCENTAGE_THRESHOLD`, `THRESHOLD_30_DAY`, `THRESHOLD_365_DAY`
- `src/domain/events/governance_review_required.py`: Uses `RT3_THRESHOLD`, `RT3_WINDOW_DAYS`

### Threshold Registry Design

```python
@dataclass(frozen=True)
class ConstitutionalThreshold:
    """A constitutional threshold that cannot be lowered below its floor.

    Constitutional Constraint (FR33):
    Threshold definitions SHALL be constitutional, not operational.
    This means they have a floor that cannot be breached.
    """
    threshold_name: str
    constitutional_floor: int | float  # Cannot go below this
    current_value: int | float  # Active value (>= floor)
    is_constitutional: bool  # Always True for these thresholds
    description: str
    fr_reference: str  # E.g., "FR32", "NFR39"

    def __post_init__(self) -> None:
        """Validate threshold on creation."""
        if self.current_value < self.constitutional_floor:
            raise ConstitutionalFloorViolationError(
                threshold_name=self.threshold_name,
                attempted_value=self.current_value,
                constitutional_floor=self.constitutional_floor,
                fr_reference=self.fr_reference,
            )

    @property
    def is_valid(self) -> bool:
        """Check if current value is at or above floor."""
        return self.current_value >= self.constitutional_floor

    def validate(self) -> None:
        """Validate threshold, raise error if invalid (FR33)."""
        if not self.is_valid:
            raise ConstitutionalFloorViolationError(
                threshold_name=self.threshold_name,
                attempted_value=self.current_value,
                constitutional_floor=self.constitutional_floor,
                fr_reference=self.fr_reference,
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "threshold_name": self.threshold_name,
            "constitutional_floor": self.constitutional_floor,
            "current_value": self.current_value,
            "is_constitutional": self.is_constitutional,
            "description": self.description,
            "fr_reference": self.fr_reference,
        }
```

### Constitutional Threshold Definitions

```python
# From constitutional_thresholds.py

# FR32: Cessation trigger threshold
CESSATION_BREACH_THRESHOLD = ConstitutionalThreshold(
    threshold_name="cessation_breach_count",
    constitutional_floor=10,
    current_value=10,
    is_constitutional=True,
    description="Maximum unacknowledged breaches before cessation consideration (>10 triggers)",
    fr_reference="FR32",
)

# FR32: Cessation window
CESSATION_WINDOW_DAYS_THRESHOLD = ConstitutionalThreshold(
    threshold_name="cessation_window_days",
    constitutional_floor=90,
    current_value=90,
    is_constitutional=True,
    description="Rolling window for breach counting in cessation consideration",
    fr_reference="FR32",
)

# FR21, NFR41: Recovery waiting period
RECOVERY_WAITING_HOURS_THRESHOLD = ConstitutionalThreshold(
    threshold_name="recovery_waiting_hours",
    constitutional_floor=48,
    current_value=48,
    is_constitutional=True,
    description="Minimum hours for recovery waiting period (constitutional floor)",
    fr_reference="NFR41",
)

# FR79: Minimum Keeper quorum
MINIMUM_KEEPER_QUORUM_THRESHOLD = ConstitutionalThreshold(
    threshold_name="minimum_keeper_quorum",
    constitutional_floor=3,
    current_value=3,
    is_constitutional=True,
    description="Minimum registered Keepers before system halt",
    fr_reference="FR79",
)

# FR31: Escalation threshold
ESCALATION_DAYS_THRESHOLD = ConstitutionalThreshold(
    threshold_name="escalation_days",
    constitutional_floor=7,
    current_value=7,
    is_constitutional=True,
    description="Days before unacknowledged breach escalates to Conclave agenda",
    fr_reference="FR31",
)

# FR78: Attestation period
ATTESTATION_PERIOD_THRESHOLD = ConstitutionalThreshold(
    threshold_name="attestation_period_days",
    constitutional_floor=7,
    current_value=7,
    is_constitutional=True,
    description="Days between required Keeper attestations",
    fr_reference="FR78",
)

# FR78: Missed attestation threshold
MISSED_ATTESTATIONS_THRESHOLD_DEF = ConstitutionalThreshold(
    threshold_name="missed_attestations_threshold",
    constitutional_floor=2,
    current_value=2,
    is_constitutional=True,
    description="Consecutive missed attestations before replacement trigger",
    fr_reference="FR78",
)

# FR27: 30-day override warning
OVERRIDE_WARNING_30_DAY_THRESHOLD = ConstitutionalThreshold(
    threshold_name="override_warning_30_day",
    constitutional_floor=5,
    current_value=5,
    is_constitutional=True,
    description="Maximum overrides in 30 days before anti-success alert",
    fr_reference="FR27",
)

# RT-3: 365-day governance review
OVERRIDE_GOVERNANCE_365_DAY_THRESHOLD = ConstitutionalThreshold(
    threshold_name="override_governance_365_day",
    constitutional_floor=20,
    current_value=20,
    is_constitutional=True,
    description="Maximum overrides in 365 days before governance review required",
    fr_reference="RT-3",
)

# FR73: Topic diversity
TOPIC_DIVERSITY_THRESHOLD_DEF = ConstitutionalThreshold(
    threshold_name="topic_diversity_threshold",
    constitutional_floor=0.30,
    current_value=0.30,
    is_constitutional=True,
    description="Maximum percentage from single origin type over 30 days",
    fr_reference="FR73",
)

# FR85: Fork signal rate limit
FORK_SIGNAL_RATE_LIMIT_THRESHOLD = ConstitutionalThreshold(
    threshold_name="fork_signal_rate_limit",
    constitutional_floor=3,
    current_value=3,
    is_constitutional=True,
    description="Maximum fork signals per hour per source",
    fr_reference="FR85",
)

# ADR-3: Halt confirmation window
HALT_CONFIRMATION_SECONDS_THRESHOLD = ConstitutionalThreshold(
    threshold_name="halt_confirmation_seconds",
    constitutional_floor=5,
    current_value=5,
    is_constitutional=True,
    description="Maximum seconds for Redis-DB halt confirmation",
    fr_reference="ADR-3",
)

# FR59-61: Witness pool minimum for high-stakes
WITNESS_POOL_MINIMUM_THRESHOLD = ConstitutionalThreshold(
    threshold_name="witness_pool_minimum_high_stakes",
    constitutional_floor=12,
    current_value=12,
    is_constitutional=True,
    description="Minimum witnesses for high-stakes operations",
    fr_reference="FR59",
)

# Registry of all constitutional thresholds
CONSTITUTIONAL_THRESHOLD_REGISTRY: tuple[ConstitutionalThreshold, ...] = (
    CESSATION_BREACH_THRESHOLD,
    CESSATION_WINDOW_DAYS_THRESHOLD,
    RECOVERY_WAITING_HOURS_THRESHOLD,
    MINIMUM_KEEPER_QUORUM_THRESHOLD,
    ESCALATION_DAYS_THRESHOLD,
    ATTESTATION_PERIOD_THRESHOLD,
    MISSED_ATTESTATIONS_THRESHOLD_DEF,
    OVERRIDE_WARNING_30_DAY_THRESHOLD,
    OVERRIDE_GOVERNANCE_365_DAY_THRESHOLD,
    TOPIC_DIVERSITY_THRESHOLD_DEF,
    FORK_SIGNAL_RATE_LIMIT_THRESHOLD,
    HALT_CONFIRMATION_SECONDS_THRESHOLD,
    WITNESS_POOL_MINIMUM_THRESHOLD,
)
```

### ConstitutionalFloorViolationError Design

```python
class ConstitutionalFloorViolationError(ThresholdError):
    """Raised when attempting to set a threshold below its constitutional floor (FR33).

    Constitutional Constraint (FR33):
    Threshold definitions SHALL be constitutional, not operational.
    Setting any threshold below its floor violates this constraint.

    Attributes:
        threshold_name: Name of the threshold being violated.
        attempted_value: The value that was attempted.
        constitutional_floor: The minimum allowed value.
        fr_reference: FR reference for the threshold.
    """

    def __init__(
        self,
        threshold_name: str,
        attempted_value: int | float,
        constitutional_floor: int | float,
        fr_reference: str,
    ) -> None:
        self.threshold_name = threshold_name
        self.attempted_value = attempted_value
        self.constitutional_floor = constitutional_floor
        self.fr_reference = fr_reference

        message = (
            f"FR33: Constitutional floor violation - "
            f"{threshold_name} cannot be set to {attempted_value}, "
            f"minimum is {constitutional_floor} ({fr_reference})"
        )
        super().__init__(message)
```

### Counter Preservation (FR34) Design

FR34 requires that changing a threshold does NOT reset any counters. This is critical to prevent gaming the system by raising and lowering thresholds to reset breach counts.

```python
async def update_threshold(
    self,
    name: str,
    new_value: int | float,
    updated_by: str,
) -> ConstitutionalThreshold:
    """Update a threshold value without resetting counters (FR33, FR34).

    CRITICAL FR34 CONSTRAINT:
    Threshold changes SHALL NOT reset active counters.
    This method ONLY updates the threshold value. It has NO access
    to breach repositories, escalation repositories, or any counter state.

    Counter preservation is enforced architecturally:
    - This service has no dependency on repositories with counters
    - Counter state lives in separate repositories (BreachRepository, etc.)
    - There is no code path from threshold update to counter reset
    """
    # HALT CHECK FIRST (CT-11)
    if await self._halt_checker.is_halted():
        raise SystemHaltedError("System halted")

    # Get threshold definition
    threshold = self._get_threshold_definition(name)

    # Validate against floor (FR33, NFR39)
    if new_value < threshold.constitutional_floor:
        raise ConstitutionalFloorViolationError(
            threshold_name=name,
            attempted_value=new_value,
            constitutional_floor=threshold.constitutional_floor,
            fr_reference=threshold.fr_reference,
        )

    # Create updated threshold (does NOT touch any counters - FR34)
    updated = ConstitutionalThreshold(
        threshold_name=threshold.threshold_name,
        constitutional_floor=threshold.constitutional_floor,
        current_value=new_value,
        is_constitutional=True,
        description=threshold.description,
        fr_reference=threshold.fr_reference,
    )

    # Write witnessed event if EventWriter provided (CT-12)
    if self._event_writer:
        payload = ThresholdUpdatedEventPayload(
            threshold_name=name,
            previous_value=threshold.current_value,
            new_value=new_value,
            constitutional_floor=threshold.constitutional_floor,
            fr_reference=threshold.fr_reference,
            updated_at=datetime.now(timezone.utc),
            updated_by=updated_by,
        )
        await self._event_writer.write_event(
            event_type=THRESHOLD_UPDATED_EVENT_TYPE,
            payload=payload.to_dict(),
            agent_id=updated_by,
            local_timestamp=payload.updated_at,
        )

    return updated
```

### Import Rules (Hexagonal Architecture)

- `domain/models/constitutional_threshold.py` imports from `domain/errors/`, `typing`, `dataclasses`
- `domain/primitives/constitutional_thresholds.py` imports from `domain/models/constitutional_threshold.py`
- `domain/errors/threshold.py` inherits from `ConstitutionalViolationError`
- `application/ports/threshold_configuration.py` imports from `domain/models/`, `domain/errors/`, `typing`
- `application/services/threshold_configuration_service.py` imports from `application/ports/`, `domain/`
- NEVER import from `infrastructure/` in `domain/` or `application/`

### Testing Standards

- ALL tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Unit tests mock the protocol interfaces
- Integration tests use stub implementations
- FR33 tests MUST verify:
  - Thresholds include `constitutional_floor` field
  - Thresholds include `is_constitutional` flag set to True
  - Below-floor values are rejected
  - Error messages include "FR33: Constitutional floor violation"
- FR34 tests MUST verify:
  - Threshold updates do NOT reset counters
  - Historical breach counts are preserved
  - Threshold update events are witnessed
- NFR39 tests MUST verify:
  - All thresholds have defined floors
  - No threshold can be set below its floor

### Relationship to Story 6.10

Story 6.4 defines the constitutional threshold model and registry. Story 6.10 (Configuration Floor Enforcement) will use this foundation to:
- Validate all configuration at startup
- Enforce floor validation at runtime via any configuration mechanism
- Ensure floors are defined in read-only configuration

Story 6.4 provides the data model; Story 6.10 provides the enforcement mechanism.

### Files to Create

```
src/domain/models/constitutional_threshold.py                    # Threshold model
src/domain/primitives/constitutional_thresholds.py               # All threshold definitions
src/domain/errors/threshold.py                                   # Threshold errors
src/domain/events/threshold.py                                   # Threshold update event
src/application/ports/threshold_configuration.py                 # Port protocol
src/application/services/threshold_configuration_service.py      # Service
src/infrastructure/stubs/threshold_repository_stub.py            # Repository stub
tests/unit/domain/test_constitutional_threshold.py               # Model tests
tests/unit/domain/test_constitutional_thresholds.py              # Registry tests
tests/unit/domain/test_threshold_errors.py                       # Error tests
tests/unit/domain/test_threshold_updated_event.py                # Event tests
tests/unit/application/test_threshold_configuration_service.py   # Service tests
tests/unit/infrastructure/test_threshold_repository_stub.py      # Stub tests
tests/integration/test_constitutional_threshold_integration.py   # Integration tests
```

### Files to Modify

```
src/domain/models/__init__.py                                    # Export new model
src/domain/primitives/__init__.py                                # Export threshold constants
src/domain/errors/__init__.py                                    # Export new errors
src/domain/events/__init__.py                                    # Export new event
src/application/ports/__init__.py                                # Export new port
src/application/services/__init__.py                             # Export new service
src/infrastructure/stubs/__init__.py                             # Export new stub
```

### Project Structure Notes

- Model follows existing frozen dataclass patterns from Stories 6.1-6.3
- Errors inherit from `ConstitutionalViolationError` with FR reference
- Service follows HALT CHECK FIRST pattern throughout
- Repository stub follows in-memory dict pattern from existing stubs
- Threshold registry defined as tuple for immutability

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-6.4] - Story definition
- [Source: _bmad-output/planning-artifacts/prd.md#FR33] - Constitutional threshold definitions
- [Source: _bmad-output/planning-artifacts/prd.md#FR34] - Counter preservation requirement
- [Source: _bmad-output/planning-artifacts/prd.md#NFR39] - No config below floors
- [Source: _bmad-output/planning-artifacts/architecture.md#CT-11] - Halt over degrade
- [Source: _bmad-output/planning-artifacts/architecture.md#CT-12] - Witnessing accountability
- [Source: src/domain/models/breach_count_status.py] - Existing threshold constants
- [Source: src/domain/models/keeper_attestation.py] - Existing attestation constants
- [Source: src/domain/models/recovery_waiting_period.py] - Existing recovery constants
- [Source: src/application/services/override_trend_service.py] - Existing override thresholds
- [Source: src/domain/primitives/prevent_delete.py] - Primitives pattern
- [Source: _bmad-output/project-context.md] - Project implementation rules

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-08 | Story created with comprehensive FR33/FR34/NFR39 context, threshold registry design | Create-Story Workflow (Opus 4.5) |

### File List

