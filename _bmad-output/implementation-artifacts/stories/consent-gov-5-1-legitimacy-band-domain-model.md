# Story consent-gov-5.1: Legitimacy Band Domain Model

Status: review

---

## Story

As a **governance system**,
I want **a legitimacy band state machine**,
So that **system health has clear states and transitions that are visible to all**.

---

## Acceptance Criteria

1. **AC1:** Five bands defined: `Stable`, `Strained`, `Eroding`, `Compromised`, `Failed` (FR28)
2. **AC2:** State machine enforces valid transitions only
3. **AC3:** Current band tracked and queryable (FR28)
4. **AC4:** Band state queryable by any participant
5. **AC5:** Downward transitions allowed automatically
6. **AC6:** Upward transitions require explicit acknowledgment
7. **AC7:** All transitions recorded with timestamp
8. **AC8:** Band definitions include severity level and description
9. **AC9:** Unit tests for band transitions

---

## Tasks / Subtasks

- [x] **Task 1: Create LegitimacyBand enum** (AC: 1, 8)
  - [x] Create `src/domain/governance/legitimacy/__init__.py`
  - [x] Create `src/domain/governance/legitimacy/legitimacy_band.py`
  - [x] Define five bands: STABLE, STRAINED, ERODING, COMPROMISED, FAILED
  - [x] Include severity level (0-4) and descriptions

- [x] **Task 2: Create LegitimacyState domain model** (AC: 3, 7)
  - [x] Define `LegitimacyState` as immutable value object
  - [x] Include current_band, entered_at, violation_count
  - [x] Include last triggering event reference
  - [x] Track band history

- [x] **Task 3: Create transition rules** (AC: 2, 5, 6)
  - [x] Create `src/domain/governance/legitimacy/band_transition_rules.py`
  - [x] Define valid downward transitions (any band → lower bands)
  - [x] Define valid upward transitions (only one step up, requires ack)
  - [x] Reject invalid transitions

- [x] **Task 4: Define band characteristics** (AC: 1, 8)
  - [x] STABLE: Normal operation, no active issues
  - [x] STRAINED: Minor issues detected, monitoring required
  - [x] ERODING: Significant issues, intervention recommended
  - [x] COMPROMISED: Critical issues, limited operation
  - [x] FAILED: System integrity compromised, halt recommended

- [x] **Task 5: Create LegitimacyTransition model** (AC: 7)
  - [x] Define transition record with from_band, to_band
  - [x] Include timestamp, triggering_event_id
  - [x] Include actor (system or operator)
  - [x] Include transition_type (automatic or acknowledged)

- [x] **Task 6: Implement transition validation** (AC: 2, 5, 6)
  - [x] Validate downward transitions (automatic allowed)
  - [x] Validate upward transitions (acknowledgment required)
  - [x] Reject FAILED → any transition (terminal unless reconstitution)
  - [x] Return validation result with reason

- [x] **Task 7: Create LegitimacyPort interface** (AC: 3, 4)
  - [x] Create `src/application/ports/governance/legitimacy_port.py`
  - [x] Define `get_current_band()` method
  - [x] Define `get_legitimacy_state()` method
  - [x] Define `transition()` method

- [x] **Task 8: Write comprehensive unit tests** (AC: 9)
  - [x] Test all five bands exist with correct severity
  - [x] Test valid downward transitions
  - [x] Test upward transitions rejected without ack
  - [x] Test transition records include timestamp
  - [x] Test band query returns current state
  - [x] Test FAILED is terminal

---

## Documentation Checklist

- [x] Architecture docs updated (legitimacy bands) - In module __init__.py docstring
- [x] Inline comments explaining band meanings - In legitimacy_band.py
- [x] Band severity descriptions - In legitimacy_band.py
- [x] N/A - README (internal component)

---

## File List

### Created Files
- `src/domain/governance/legitimacy/__init__.py` - Module exports with comprehensive docstring
- `src/domain/governance/legitimacy/legitimacy_band.py` - LegitimacyBand enum with 5 bands
- `src/domain/governance/legitimacy/legitimacy_state.py` - LegitimacyState frozen dataclass
- `src/domain/governance/legitimacy/legitimacy_transition.py` - LegitimacyTransition frozen dataclass
- `src/domain/governance/legitimacy/transition_type.py` - TransitionType enum (AUTOMATIC, ACKNOWLEDGED)
- `src/domain/governance/legitimacy/transition_validation.py` - TransitionValidation result class
- `src/domain/governance/legitimacy/band_transition_rules.py` - BandTransitionRules validation class
- `src/domain/governance/legitimacy/errors.py` - Domain-specific exceptions
- `src/application/ports/governance/legitimacy_port.py` - LegitimacyPort and LegitimacyQueryPort protocols
- `tests/unit/domain/governance/legitimacy/__init__.py` - Test package init
- `tests/unit/domain/governance/legitimacy/test_legitimacy_band.py` - 22 band enum tests
- `tests/unit/domain/governance/legitimacy/test_legitimacy_state.py` - 19 state model tests
- `tests/unit/domain/governance/legitimacy/test_legitimacy_transition.py` - 18 transition model tests
- `tests/unit/domain/governance/legitimacy/test_transition_rules.py` - 22 transition rules tests
- `tests/unit/application/ports/governance/test_legitimacy_port.py` - 14 port interface tests

### Modified Files
- `src/application/ports/governance/__init__.py` - Added LegitimacyPort, LegitimacyQueryPort exports

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-17 | Initial implementation - All 8 tasks complete | Claude |
| 2026-01-17 | 95 unit tests passing | Claude |

---

## Dev Notes

### Key Architectural Decisions

**Five-Band Model:**
```
Band        │ Severity │ Description
────────────┼──────────┼─────────────────────────────────────
STABLE      │    0     │ Normal operation, no active issues
STRAINED    │    1     │ Minor issues detected, monitoring
ERODING     │    2     │ Significant issues, intervention needed
COMPROMISED │    3     │ Critical issues, limited operation
FAILED      │    4     │ Integrity compromised, halt recommended
```

**Transition Rules:**
```
Downward (automatic):
  STABLE → STRAINED → ERODING → COMPROMISED → FAILED
  (can skip bands based on severity of violation)

Upward (requires acknowledgment):
  FAILED → cannot recover (terminal)
  COMPROMISED → ERODING (ack required)
  ERODING → STRAINED (ack required)
  STRAINED → STABLE (ack required)
  (only one step at a time)
```

**Why Asymmetric?**
```
Decay is automatic because:
  - Violations are objective events
  - Delayed decay would hide problems
  - System should transparently show health

Restoration requires acknowledgment because:
  - Human must verify issue is resolved
  - Prevents premature restoration
  - Creates accountability for decisions
  - NFR-CONST-04 requires explicit actor
```

### Domain Models

```python
class LegitimacyBand(Enum):
    """System legitimacy bands (health levels)."""

    STABLE = "stable"
    STRAINED = "strained"
    ERODING = "eroding"
    COMPROMISED = "compromised"
    FAILED = "failed"

    @property
    def severity(self) -> int:
        """Severity level (0=healthy, 4=failed)."""
        return {
            self.STABLE: 0,
            self.STRAINED: 1,
            self.ERODING: 2,
            self.COMPROMISED: 3,
            self.FAILED: 4,
        }[self]

    @property
    def description(self) -> str:
        """Human-readable description."""
        return {
            self.STABLE: "Normal operation, no active issues",
            self.STRAINED: "Minor issues detected, monitoring required",
            self.ERODING: "Significant issues, intervention recommended",
            self.COMPROMISED: "Critical issues, limited operation",
            self.FAILED: "System integrity compromised, halt recommended",
        }[self]

    def can_transition_to(self, target: "LegitimacyBand") -> bool:
        """Check if transition to target is valid."""
        if self == LegitimacyBand.FAILED:
            return False  # Terminal state

        # Downward always allowed
        if target.severity > self.severity:
            return True

        # Upward only one step at a time
        if target.severity == self.severity - 1:
            return True

        return False


@dataclass(frozen=True)
class LegitimacyState:
    """Current legitimacy state of the system."""
    current_band: LegitimacyBand
    entered_at: datetime
    violation_count: int
    last_triggering_event_id: UUID | None
    last_transition_type: str  # "automatic" or "acknowledged"


class TransitionType(Enum):
    """Type of legitimacy transition."""
    AUTOMATIC = "automatic"       # System-triggered decay
    ACKNOWLEDGED = "acknowledged"  # Human-acknowledged restoration


@dataclass(frozen=True)
class LegitimacyTransition:
    """Record of a legitimacy band transition."""
    transition_id: UUID
    from_band: LegitimacyBand
    to_band: LegitimacyBand
    transition_type: TransitionType
    actor: str  # "system" or operator UUID
    triggering_event_id: UUID | None  # For automatic transitions
    acknowledgment_id: UUID | None  # For acknowledged transitions
    timestamp: datetime
    reason: str
```

### Transition Rules

```python
class BandTransitionRules:
    """Rules for legitimacy band transitions."""

    @staticmethod
    def validate_transition(
        current: LegitimacyBand,
        target: LegitimacyBand,
        transition_type: TransitionType,
    ) -> TransitionValidation:
        """Validate a proposed transition."""

        # FAILED is terminal
        if current == LegitimacyBand.FAILED:
            return TransitionValidation.invalid(
                "FAILED is terminal - reconstitution required"
            )

        # Same band (no-op)
        if current == target:
            return TransitionValidation.invalid("Already at target band")

        # Downward transition (automatic allowed)
        if target.severity > current.severity:
            if transition_type == TransitionType.AUTOMATIC:
                return TransitionValidation.valid()
            else:
                return TransitionValidation.valid()  # Ack also allowed

        # Upward transition (acknowledgment required)
        if target.severity < current.severity:
            if transition_type != TransitionType.ACKNOWLEDGED:
                return TransitionValidation.invalid(
                    "Upward transition requires acknowledgment"
                )

            # Only one step at a time
            if target.severity != current.severity - 1:
                return TransitionValidation.invalid(
                    "Upward transition must be one step at a time"
                )

            return TransitionValidation.valid()

        return TransitionValidation.invalid("Invalid transition")


@dataclass(frozen=True)
class TransitionValidation:
    """Result of transition validation."""
    is_valid: bool
    reason: str | None

    @classmethod
    def valid(cls) -> "TransitionValidation":
        return cls(is_valid=True, reason=None)

    @classmethod
    def invalid(cls, reason: str) -> "TransitionValidation":
        return cls(is_valid=False, reason=reason)
```

### Port Interface

```python
class LegitimacyPort(Protocol):
    """Port for legitimacy band operations."""

    async def get_current_band(self) -> LegitimacyBand:
        """Get current legitimacy band."""
        ...

    async def get_legitimacy_state(self) -> LegitimacyState:
        """Get full legitimacy state including history."""
        ...

    async def get_transition_history(
        self,
        since: datetime | None = None,
    ) -> list[LegitimacyTransition]:
        """Get transition history."""
        ...
```

### Test Patterns

```python
class TestLegitimacyBand:
    """Unit tests for legitimacy band domain model."""

    def test_all_five_bands_exist(self):
        """All five bands are defined."""
        assert len(LegitimacyBand) == 5
        assert LegitimacyBand.STABLE in LegitimacyBand
        assert LegitimacyBand.STRAINED in LegitimacyBand
        assert LegitimacyBand.ERODING in LegitimacyBand
        assert LegitimacyBand.COMPROMISED in LegitimacyBand
        assert LegitimacyBand.FAILED in LegitimacyBand

    def test_severity_ordering(self):
        """Severity increases from STABLE to FAILED."""
        assert LegitimacyBand.STABLE.severity == 0
        assert LegitimacyBand.STRAINED.severity == 1
        assert LegitimacyBand.ERODING.severity == 2
        assert LegitimacyBand.COMPROMISED.severity == 3
        assert LegitimacyBand.FAILED.severity == 4

    def test_downward_transition_allowed(self):
        """Downward transitions are valid."""
        assert LegitimacyBand.STABLE.can_transition_to(LegitimacyBand.STRAINED)
        assert LegitimacyBand.STABLE.can_transition_to(LegitimacyBand.COMPROMISED)
        assert LegitimacyBand.STRAINED.can_transition_to(LegitimacyBand.FAILED)

    def test_upward_one_step_allowed(self):
        """Upward transitions one step are valid."""
        assert LegitimacyBand.STRAINED.can_transition_to(LegitimacyBand.STABLE)
        assert LegitimacyBand.ERODING.can_transition_to(LegitimacyBand.STRAINED)
        assert LegitimacyBand.COMPROMISED.can_transition_to(LegitimacyBand.ERODING)

    def test_upward_multiple_steps_invalid(self):
        """Upward transitions multiple steps are invalid."""
        assert not LegitimacyBand.ERODING.can_transition_to(LegitimacyBand.STABLE)
        assert not LegitimacyBand.COMPROMISED.can_transition_to(LegitimacyBand.STRAINED)

    def test_failed_is_terminal(self):
        """FAILED cannot transition to any band."""
        for band in LegitimacyBand:
            assert not LegitimacyBand.FAILED.can_transition_to(band)


class TestBandTransitionRules:
    """Unit tests for transition rules."""

    def test_automatic_downward_valid(self):
        """Automatic downward transitions are valid."""
        result = BandTransitionRules.validate_transition(
            current=LegitimacyBand.STABLE,
            target=LegitimacyBand.STRAINED,
            transition_type=TransitionType.AUTOMATIC,
        )
        assert result.is_valid

    def test_automatic_upward_invalid(self):
        """Automatic upward transitions are invalid."""
        result = BandTransitionRules.validate_transition(
            current=LegitimacyBand.STRAINED,
            target=LegitimacyBand.STABLE,
            transition_type=TransitionType.AUTOMATIC,
        )
        assert not result.is_valid
        assert "acknowledgment" in result.reason.lower()

    def test_acknowledged_upward_valid(self):
        """Acknowledged upward transitions are valid."""
        result = BandTransitionRules.validate_transition(
            current=LegitimacyBand.STRAINED,
            target=LegitimacyBand.STABLE,
            transition_type=TransitionType.ACKNOWLEDGED,
        )
        assert result.is_valid

    def test_failed_terminal(self):
        """FAILED state cannot transition."""
        result = BandTransitionRules.validate_transition(
            current=LegitimacyBand.FAILED,
            target=LegitimacyBand.COMPROMISED,
            transition_type=TransitionType.ACKNOWLEDGED,
        )
        assert not result.is_valid
        assert "terminal" in result.reason.lower()
```

### Dependencies

- **Depends on:** consent-gov-1-1 (event infrastructure)
- **Enables:** consent-gov-5-2 (automatic decay), consent-gov-5-3 (explicit restoration)

### References

- FR28: System can track current legitimacy band
- NFR-CONST-04: All transitions logged with timestamp and actor
- governance-architecture.md: 5-band state machine
