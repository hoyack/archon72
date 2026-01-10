# Story 6.6: Witness Pool Anomaly Detection (FR116-FR118)

Status: done

## Story

As a **system operator**,
I want statistical anomaly flagging in witness co-occurrence,
So that collusion patterns are detected.

## Acceptance Criteria

### AC1: Statistical Anomaly Detection (FR116)
**Given** witness history over time
**When** co-occurrence patterns are analyzed
**Then** statistically anomalous pairs are flagged
**And** a `WitnessAnomalyEvent` is created
**And** affected pair is marked for review

### AC2: Collusion Pattern Detection (FR116)
**Given** the anomaly detection system
**When** the same pair appears more than expected by chance
**Then** an alert is raised
**And** pair is excluded from selection temporarily
**And** exclusion is logged as a witnessed event

### AC3: Witness Pool Degraded Mode (FR117)
**Given** witness pool minimum enforcement
**When** pool drops below 12 for high-stakes ceremonies
**Then** degraded mode is surfaced publicly
**And** `WitnessPoolDegradedEvent` is created
**And** low-stakes operations can continue with >=6 witnesses

### AC4: Unavailability Pattern Detection (FR116)
**Given** witness unavailability tracking
**When** patterns show same witnesses repeatedly unavailable
**Then** a security review is triggered
**And** the pattern is logged for investigation

## Tasks / Subtasks

- [ ] Task 1: Create Witness Anomaly Domain Events (AC: #1, #2)
  - [ ] 1.1 Create `src/domain/events/witness_anomaly.py`:
    - `WitnessAnomalyEventPayload` frozen dataclass with:
      - `anomaly_type: WitnessAnomalyType` (co_occurrence, unavailability_pattern, excessive_pairing)
      - `affected_witnesses: tuple[str, ...]` - Witnesses involved in anomaly
      - `confidence_score: float` - 0.0 to 1.0 confidence
      - `detection_window_hours: int` - Time window analyzed
      - `occurrence_count: int` - Number of occurrences detected
      - `expected_count: float` - Expected count by chance
      - `detected_at: datetime`
      - `review_status: str` - "pending", "investigating", "cleared", "confirmed"
    - `WitnessAnomalyType` enum: CO_OCCURRENCE, UNAVAILABILITY_PATTERN, EXCESSIVE_PAIRING
    - Event type constant: `WITNESS_ANOMALY_EVENT_TYPE = "witness.anomaly"`
    - `to_dict()` for event serialization
    - `signable_content()` for witnessing (CT-12)
  - [ ] 1.2 Create `WitnessPoolDegradedEventPayload` frozen dataclass:
    - `available_witnesses: int` - Current pool size
    - `minimum_required: int` - For the blocked operation type
    - `operation_type: str` - "high_stakes" or "standard"
    - `is_blocking: bool` - True if operations are paused
    - `degraded_at: datetime`
    - Event type constant: `WITNESS_POOL_DEGRADED_EVENT_TYPE = "witness.pool_degraded"`
  - [ ] 1.3 Export from `src/domain/events/__init__.py`

- [ ] Task 2: Create Witness Anomaly Domain Errors (AC: #1, #2)
  - [ ] 2.1 Create `src/domain/errors/witness_anomaly.py`:
    - `WitnessAnomalyError(ConstitutionalViolationError)` - Base class
    - `WitnessCollusionSuspectedError(WitnessAnomalyError)` - FR116 detected
      - Attributes: `witnesses: tuple[str, ...]`, `confidence: float`
      - Message: "FR116: Witness collusion suspected - pair excluded from selection"
    - `WitnessPairExcludedError(WitnessAnomalyError)` - Pair temporarily excluded
      - Attributes: `pair_key: str`, `excluded_until: datetime`
      - Message: "FR116: Witness pair {pair_key} temporarily excluded due to anomaly"
    - `WitnessUnavailabilityPatternError(WitnessAnomalyError)` - FR116 unavailability
      - Attributes: `witness_ids: tuple[str, ...]`, `unavailable_count: int`
      - Message: "FR116: Unavailability pattern detected - security review triggered"
  - [ ] 2.2 Export from `src/domain/errors/__init__.py`

- [ ] Task 3: Create Witness Anomaly Detector Port (AC: #1, #2, #4)
  - [ ] 3.1 Create `src/application/ports/witness_anomaly_detector.py`:
    - `WitnessAnomalyDetectorProtocol` ABC with methods:
      - `async def analyze_co_occurrence(window_hours: int) -> list[WitnessAnomalyResult]`
        - Analyzes witness pair co-occurrence frequency
        - Returns anomalies where pair appears more than statistically expected
      - `async def analyze_unavailability_patterns(window_hours: int) -> list[WitnessAnomalyResult]`
        - Detects patterns of repeated witness unavailability (FR116)
      - `async def get_excluded_pairs() -> set[str]`
        - Returns currently excluded pair canonical keys
      - `async def exclude_pair(pair_key: str, duration_hours: int) -> None`
        - Temporarily excludes a pair from selection
      - `async def clear_pair_exclusion(pair_key: str) -> None`
        - Removes exclusion (for review clearance)
      - `async def is_pair_excluded(pair_key: str) -> bool`
        - Checks if a pair is currently excluded
    - `WitnessAnomalyResult` dataclass:
      - `anomaly_type: WitnessAnomalyType`
      - `confidence_score: float`
      - `affected_witnesses: tuple[str, ...]`
      - `details: str`
  - [ ] 3.2 Export from `src/application/ports/__init__.py`

- [ ] Task 4: Create Witness Pool Monitor Port (AC: #3)
  - [ ] 4.1 Create `src/application/ports/witness_pool_monitor.py`:
    - `WitnessPoolMonitorProtocol` ABC with methods:
      - `async def get_pool_status() -> WitnessPoolStatus`
      - `async def is_degraded() -> bool`
      - `async def can_perform_operation(high_stakes: bool) -> bool`
      - `async def get_degraded_since() -> datetime | None`
    - `WitnessPoolStatus` frozen dataclass:
      - `available_count: int`
      - `minimum_for_standard: int` (6)
      - `minimum_for_high_stakes: int` (12)
      - `is_degraded: bool`
      - `degraded_since: datetime | None`
      - `excluded_witnesses: tuple[str, ...]` - Currently excluded due to anomaly
  - [ ] 4.2 Export from `src/application/ports/__init__.py`

- [ ] Task 5: Create Witness Anomaly Detection Service (AC: #1, #2, #4)
  - [ ] 5.1 Create `src/application/services/witness_anomaly_detection_service.py`:
    - Inject: `HaltChecker`, `WitnessAnomalyDetectorProtocol`, `WitnessPairHistoryProtocol`, `EventWriterService` (optional)
    - HALT CHECK FIRST at every operation boundary (CT-11)
  - [ ] 5.2 Implement `async def run_anomaly_scan(window_hours: int = 168) -> list[WitnessAnomalyEventPayload]`:
    - HALT CHECK FIRST (CT-11)
    - Call `analyze_co_occurrence(window_hours)`
    - Call `analyze_unavailability_patterns(window_hours)`
    - For each anomaly with confidence > 0.7:
      - Create `WitnessAnomalyEventPayload`
      - Write event if EventWriter provided
    - Return list of detected anomalies
  - [ ] 5.3 Implement `async def check_pair_for_anomaly(pair_key: str) -> bool`:
    - HALT CHECK FIRST (CT-11)
    - Check if pair is excluded due to prior anomaly
    - Used by VerifiableWitnessSelectionService before selection
  - [ ] 5.4 Implement `async def exclude_suspicious_pair(pair_key: str, confidence: float, duration_hours: int = 24) -> None`:
    - HALT CHECK FIRST (CT-11)
    - Exclude pair from selection
    - Create WitnessAnomalyEvent with exclusion details
    - Log exclusion as witnessed event
  - [ ] 5.5 Implement statistical anomaly scoring:
    - `_calculate_expected_occurrence(pool_size: int, events_count: int) -> float`
    - `_calculate_chi_square_deviation(observed: int, expected: float) -> float`
    - Chi-square > 3.84 (p < 0.05) flags as anomaly
  - [ ] 5.6 Export from `src/application/services/__init__.py`

- [ ] Task 6: Create Witness Pool Monitoring Service (AC: #3)
  - [ ] 6.1 Create `src/application/services/witness_pool_monitoring_service.py`:
    - Inject: `HaltChecker`, `WitnessPoolProtocol`, `WitnessAnomalyDetectorProtocol`, `EventWriterService` (optional)
    - HALT CHECK FIRST at every operation (CT-11)
  - [ ] 6.2 Implement `async def check_pool_health() -> WitnessPoolStatus`:
    - HALT CHECK FIRST (CT-11)
    - Get current pool size from WitnessPoolProtocol
    - Get excluded witnesses from anomaly detector
    - Calculate effective pool size (total - excluded)
    - Determine if degraded (effective < 12 for high-stakes)
    - Return status
  - [ ] 6.3 Implement `async def handle_pool_degraded(status: WitnessPoolStatus) -> WitnessPoolDegradedEventPayload`:
    - Create WitnessPoolDegradedEventPayload
    - Write event if EventWriter provided
    - Return payload for caller notification
  - [ ] 6.4 Implement `async def can_proceed_with_operation(high_stakes: bool) -> tuple[bool, str]`:
    - HALT CHECK FIRST (CT-11)
    - Check pool health
    - Return (can_proceed, reason) tuple
    - High-stakes requires 12, standard requires 6
  - [ ] 6.5 Export from `src/application/services/__init__.py`

- [ ] Task 7: Create Infrastructure Stubs (AC: #1, #2, #3, #4)
  - [ ] 7.1 Create `src/infrastructure/stubs/witness_anomaly_detector_stub.py`:
    - `WitnessAnomalyDetectorStub` implementing `WitnessAnomalyDetectorProtocol`
    - In-memory storage for excluded pairs with expiration
    - `inject_anomaly(result: WitnessAnomalyResult)` for test setup
    - `set_co_occurrence_anomalies(anomalies: list)` for test control
    - `set_unavailability_anomalies(anomalies: list)` for test control
    - `clear()` for test isolation
    - DEV MODE watermark warning on initialization
  - [ ] 7.2 Create `src/infrastructure/stubs/witness_pool_monitor_stub.py`:
    - `WitnessPoolMonitorStub` implementing `WitnessPoolMonitorProtocol`
    - Configurable pool size and degraded state
    - `set_pool_size(size: int)` for test control
    - `set_degraded(degraded: bool)` for test control
    - `clear()` for test isolation
  - [ ] 7.3 Export from `src/infrastructure/stubs/__init__.py`

- [ ] Task 8: Extend Verifiable Witness Selection Service (AC: #1, #2)
  - [ ] 8.1 Add optional `WitnessAnomalyDetectorProtocol` injection
  - [ ] 8.2 Update `_select_with_rotation_check()`:
    - Before selecting, check if pair is excluded due to anomaly
    - Skip excluded pairs in selection loop
  - [ ] 8.3 Add `async def select_witness_with_anomaly_check()`:
    - Combines selection with real-time anomaly checking
    - Falls back to regular selection if anomaly detector unavailable

- [ ] Task 9: Write Unit Tests (AC: #1, #2, #3, #4)
  - [ ] 9.1 Create `tests/unit/domain/test_witness_anomaly_events.py`:
    - Test `WitnessAnomalyEventPayload` creation with all fields
    - Test `WitnessAnomalyType` enum values
    - Test `to_dict()` returns expected structure
    - Test `signable_content()` determinism
    - Test confidence_score validation (0.0 to 1.0)
    - Test `WitnessPoolDegradedEventPayload` creation
  - [ ] 9.2 Create `tests/unit/domain/test_witness_anomaly_errors.py`:
    - Test `WitnessCollusionSuspectedError` message includes FR116
    - Test `WitnessPairExcludedError` includes pair_key
    - Test `WitnessUnavailabilityPatternError` includes witness count
    - Test error inheritance hierarchy
  - [ ] 9.3 Create `tests/unit/application/test_witness_anomaly_detection_service.py`:
    - Test `run_anomaly_scan()` calls both analyzers
    - Test `run_anomaly_scan()` filters by confidence threshold
    - Test `check_pair_for_anomaly()` returns exclusion status
    - Test `exclude_suspicious_pair()` creates event
    - Test `exclude_suspicious_pair()` updates exclusion list
    - Test HALT CHECK on all operations
    - Test chi-square calculation correctness
  - [ ] 9.4 Create `tests/unit/application/test_witness_pool_monitoring_service.py`:
    - Test `check_pool_health()` returns correct status
    - Test `check_pool_health()` accounts for excluded witnesses
    - Test `handle_pool_degraded()` creates event
    - Test `can_proceed_with_operation()` high-stakes threshold (12)
    - Test `can_proceed_with_operation()` standard threshold (6)
    - Test HALT CHECK on all operations
  - [ ] 9.5 Create `tests/unit/infrastructure/test_witness_anomaly_detector_stub.py`:
    - Test stub returns injected anomalies
    - Test excluded pair management
    - Test exclusion expiration
    - Test `clear()` method
  - [ ] 9.6 Create `tests/unit/infrastructure/test_witness_pool_monitor_stub.py`:
    - Test stub returns configured status
    - Test `set_pool_size()` affects status
    - Test `set_degraded()` affects status
    - Test `clear()` method

- [ ] Task 10: Write Integration Tests (AC: #1, #2, #3, #4)
  - [ ] 10.1 Create `tests/integration/test_witness_anomaly_detection_integration.py`:
    - Test: `test_fr116_co_occurrence_anomaly_detected` (AC1)
      - Set up high co-occurrence pair
      - Run anomaly scan
      - Verify anomaly event created
    - Test: `test_fr116_anomalous_pair_excluded_from_selection` (AC2)
      - Detect anomaly
      - Exclude pair
      - Attempt selection
      - Verify pair skipped
    - Test: `test_fr116_unavailability_pattern_triggers_review` (AC4)
      - Set up unavailability pattern
      - Run scan
      - Verify review triggered
    - Test: `test_fr117_degraded_mode_surfaced` (AC3)
      - Reduce pool below 12
      - Verify degraded status
      - Verify event created
    - Test: `test_fr117_low_stakes_continues_in_degraded` (AC3)
      - Pool at 8 witnesses
      - Verify low-stakes allowed
      - Verify high-stakes blocked
    - Test: `test_excluded_pair_clearance_restores_selection`
      - Exclude pair
      - Clear exclusion
      - Verify pair selectable again
    - Test: `test_halt_check_prevents_anomaly_scan`
      - Set system halted
      - Attempt scan
      - Verify SystemHaltedError
    - Test: `test_anomaly_event_witnessed`
      - Detect anomaly
      - Verify event has witness attribution

## Dev Notes

### Constitutional Constraints (CRITICAL)

- **FR116**: System SHALL detect patterns of witness unavailability affecting same witnesses repeatedly; pattern triggers security review
- **FR117**: If witness pool <12, continue only for low-stakes events; high-stakes events pause until restored. Degraded mode publicly surfaced.
- **FR118**: External topic sources rate-limited (not directly in this story, but related to anti-gaming)
- **CT-9**: Attackers are patient - aggregate erosion must be detected
- **CT-11**: Silent failure destroys legitimacy -> HALT CHECK FIRST at every operation
- **CT-12**: Witnessing creates accountability -> All anomaly events MUST be witnessed

### ADR-7: Aggregate Anomaly Detection

Story 6.6 implements the **Statistics layer** of ADR-7's three-layer detection system:

| Layer | Method | Response |
|-------|--------|----------|
| Rules | Predefined thresholds | Auto-alert, auto-halt if critical |
| **Statistics (THIS STORY)** | Baseline deviation detection | Queue for review |
| Human | Weekly anomaly review ceremony | Classify, escalate, or dismiss |

The anomaly detection follows the same patterns established in Story 5.9 (Override Abuse Detection) but applied to witness co-occurrence patterns.

### Epic 6 Context - Story 6.6 Position

```
┌─────────────────────────────────────────────────────────────────┐
│ Story 6.5: Verifiable Witness Selection (COMPLETED)             │
│ - External entropy source (FR61)                                │
│ - Hash chain seeding (FR59)                                     │
│ - Pair rotation enforcement (FR60)                              │
│ - VerifiableWitnessSelectionService                             │
└─────────────────────────────────────────────────────────────────┘
         │
         │ Extended by
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Story 6.6: Witness Pool Anomaly Detection (THIS STORY)          │
│ - Statistical co-occurrence analysis (FR116)                    │
│ - Unavailability pattern detection (FR116)                      │
│ - Witness pool degraded mode (FR117)                            │
│ - Pair exclusion for suspicious pairs                           │
│ - Integration with selection service                            │
└─────────────────────────────────────────────────────────────────┘
         │
         │ Enables
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Story 6.8: Breach Collusion Defense (FUTURE)                    │
│ - Collusion investigation triggered from anomalies              │
│ - Pair suspension pending review                                │
└─────────────────────────────────────────────────────────────────┘
```

### Key Dependencies from Previous Stories

From Story 6.5 (Verifiable Witness Selection):
- `src/application/services/verifiable_witness_selection_service.py` - Extend for anomaly checking
- `src/application/ports/witness_pair_history.py` - WitnessPairHistoryProtocol for history
- `src/domain/models/witness_pair.py` - WitnessPair for canonical keys
- `src/infrastructure/stubs/witness_pair_history_stub.py` - InMemoryWitnessPairHistory

From Story 5.9 (Override Abuse Detection - similar pattern):
- `src/application/ports/anomaly_detector.py` - AnomalyDetectorProtocol reference
- `src/infrastructure/stubs/anomaly_detector_stub.py` - Similar stub pattern
- `src/domain/events/override_abuse.py` - AnomalyType reference

From Story 6.4 (Constitutional Thresholds):
- `src/domain/primitives/constitutional_thresholds.py` - WITNESS_POOL_MINIMUM_THRESHOLD (12)

From Core Infrastructure:
- `src/application/ports/halt_checker.py` - HaltCheckerProtocol
- `src/domain/errors/writer.py` - SystemHaltedError
- `src/domain/events/event.py` - Base event patterns

### Statistical Anomaly Algorithm Design

```python
# Chi-square test for co-occurrence anomaly
#
# H0: Witness pairs appear with expected frequency
# H1: Some pairs appear more than expected (collusion indicator)

def calculate_expected_occurrence(
    pool_size: int,
    total_events: int,
) -> float:
    """Calculate expected co-occurrence for a random pair.

    If we have N witnesses and M witnessed events, the expected
    frequency for any specific pair is:

    E[pair] = M / (N * (N-1) / 2)

    Where N*(N-1)/2 is the total possible unique pairs.
    """
    total_pairs = pool_size * (pool_size - 1) / 2
    return total_events / total_pairs if total_pairs > 0 else 0.0


def calculate_chi_square_deviation(
    observed: int,
    expected: float,
) -> float:
    """Calculate chi-square statistic for a single pair.

    Chi-square = (observed - expected)^2 / expected

    Critical values:
    - χ² > 3.84 : p < 0.05 (flag for review)
    - χ² > 6.63 : p < 0.01 (high confidence anomaly)
    - χ² > 10.83: p < 0.001 (very high confidence)
    """
    if expected == 0:
        return float('inf') if observed > 0 else 0.0
    return (observed - expected) ** 2 / expected


# Confidence score mapping
def chi_square_to_confidence(chi_square: float) -> float:
    """Convert chi-square to confidence score (0.0 to 1.0).

    Based on chi-square distribution with 1 degree of freedom.
    """
    if chi_square < 3.84:
        return chi_square / 3.84 * 0.5  # Below threshold, low confidence
    elif chi_square < 6.63:
        return 0.5 + (chi_square - 3.84) / (6.63 - 3.84) * 0.2  # 0.5-0.7
    elif chi_square < 10.83:
        return 0.7 + (chi_square - 6.63) / (10.83 - 6.63) * 0.2  # 0.7-0.9
    else:
        return min(0.9 + (chi_square - 10.83) / 20, 1.0)  # 0.9-1.0
```

### Witness Anomaly Detector Protocol Design

```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

class WitnessAnomalyType(Enum):
    """Types of witness anomalies (FR116)."""
    CO_OCCURRENCE = "co_occurrence"
    UNAVAILABILITY_PATTERN = "unavailability_pattern"
    EXCESSIVE_PAIRING = "excessive_pairing"


@dataclass(frozen=True)
class WitnessAnomalyResult:
    """Result of witness anomaly analysis.

    Represents a detected anomaly for review queue.
    """
    anomaly_type: WitnessAnomalyType
    confidence_score: float  # 0.0 to 1.0
    affected_witnesses: tuple[str, ...]
    occurrence_count: int
    expected_count: float
    details: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError(
                f"confidence_score must be 0.0-1.0, got {self.confidence_score}"
            )


class WitnessAnomalyDetectorProtocol(Protocol):
    """Protocol for witness anomaly detection (FR116).

    Constitutional Constraint (FR116):
    System SHALL detect patterns of witness unavailability affecting
    same witnesses repeatedly; pattern triggers security review.
    """

    async def analyze_co_occurrence(
        self,
        window_hours: int,
    ) -> list[WitnessAnomalyResult]:
        """Analyze witness pair co-occurrence for anomalies.

        Detects pairs that appear together more often than
        statistically expected, indicating potential collusion.
        """
        ...

    async def analyze_unavailability_patterns(
        self,
        window_hours: int,
    ) -> list[WitnessAnomalyResult]:
        """Analyze unavailability patterns (FR116).

        Detects if same witnesses are repeatedly unavailable,
        which could indicate targeted DoS or manipulation.
        """
        ...

    async def get_excluded_pairs(self) -> set[str]:
        """Get canonical keys of currently excluded pairs."""
        ...

    async def exclude_pair(
        self,
        pair_key: str,
        duration_hours: int,
    ) -> None:
        """Temporarily exclude a pair from selection."""
        ...

    async def is_pair_excluded(self, pair_key: str) -> bool:
        """Check if a pair is currently excluded."""
        ...
```

### Witness Pool Degraded Mode (FR117)

```python
@dataclass(frozen=True)
class WitnessPoolStatus:
    """Current witness pool status (FR117).

    Constitutional Constraint (FR117):
    If witness pool <12, continue only for low-stakes events;
    high-stakes events pause until restored.
    Degraded mode publicly surfaced.
    """
    available_count: int
    minimum_for_standard: int = 6
    minimum_for_high_stakes: int = 12  # From constitutional thresholds
    is_degraded: bool = False
    degraded_since: datetime | None = None
    excluded_witnesses: tuple[str, ...] = ()

    @property
    def effective_count(self) -> int:
        """Available minus excluded."""
        return self.available_count - len(self.excluded_witnesses)

    def can_perform(self, high_stakes: bool) -> tuple[bool, str]:
        """Check if operation can proceed (FR117).

        Returns:
            Tuple of (can_proceed, reason)
        """
        required = self.minimum_for_high_stakes if high_stakes else self.minimum_for_standard
        effective = self.effective_count

        if effective >= required:
            return (True, f"Pool adequate: {effective} >= {required}")

        if high_stakes:
            return (False, f"FR117: High-stakes blocked - {effective} < {required} witnesses")

        return (False, f"Pool insufficient: {effective} < {required}")
```

### Import Rules (Hexagonal Architecture)

- `domain/events/witness_anomaly.py` imports from `domain/`, `typing`, `dataclasses`, `datetime`, `enum`
- `domain/errors/witness_anomaly.py` inherits from `ConstitutionalViolationError`
- `application/ports/witness_anomaly_detector.py` imports from `abc`, `typing`, domain events
- `application/ports/witness_pool_monitor.py` imports from `abc`, `typing`, `datetime`
- `application/services/witness_anomaly_detection_service.py` imports from `application/ports/`, `domain/`
- `application/services/witness_pool_monitoring_service.py` imports from `application/ports/`, `domain/`
- NEVER import from `infrastructure/` in `domain/` or `application/`

### Testing Standards

- ALL tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Unit tests mock the protocol interfaces
- Integration tests use stub implementations
- FR116 tests MUST verify:
  - Co-occurrence anomaly detection flags suspicious pairs
  - Unavailability patterns trigger security review
  - Excluded pairs are skipped in selection
- FR117 tests MUST verify:
  - Degraded mode surfaced when pool < 12
  - High-stakes blocked in degraded mode
  - Low-stakes continues with >= 6
  - Degraded event created and witnessed

### Files to Create

```
src/domain/events/witness_anomaly.py                          # Anomaly events
src/domain/errors/witness_anomaly.py                          # Anomaly errors
src/application/ports/witness_anomaly_detector.py             # Anomaly detector port
src/application/ports/witness_pool_monitor.py                 # Pool monitor port
src/application/services/witness_anomaly_detection_service.py # Detection service
src/application/services/witness_pool_monitoring_service.py   # Pool monitoring service
src/infrastructure/stubs/witness_anomaly_detector_stub.py     # Anomaly detector stub
src/infrastructure/stubs/witness_pool_monitor_stub.py         # Pool monitor stub
tests/unit/domain/test_witness_anomaly_events.py              # Event tests
tests/unit/domain/test_witness_anomaly_errors.py              # Error tests
tests/unit/application/test_witness_anomaly_detection_service.py  # Detection service tests
tests/unit/application/test_witness_pool_monitoring_service.py    # Pool service tests
tests/unit/infrastructure/test_witness_anomaly_detector_stub.py   # Detector stub tests
tests/unit/infrastructure/test_witness_pool_monitor_stub.py       # Monitor stub tests
tests/integration/test_witness_anomaly_detection_integration.py   # Integration tests
```

### Files to Modify

```
src/application/services/verifiable_witness_selection_service.py  # Add anomaly detection integration
src/domain/events/__init__.py                                     # Export new events
src/domain/errors/__init__.py                                     # Export new errors
src/application/ports/__init__.py                                 # Export new ports
src/application/services/__init__.py                              # Export new services
src/infrastructure/stubs/__init__.py                              # Export new stubs
```

### Project Structure Notes

- Anomaly detection service follows existing ADR-7 pattern from Story 5.9
- Pool monitoring follows existing service patterns
- Chi-square statistical test provides objective anomaly scoring
- Confidence score threshold (0.7) filters noise from real anomalies
- Pair exclusion is temporary (24 hours default) until human review
- Degraded mode is publicly visible per FR117 transparency requirement

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-6.6] - Story definition
- [Source: _bmad-output/planning-artifacts/prd.md#FR116] - Unavailability pattern detection
- [Source: _bmad-output/planning-artifacts/prd.md#FR117] - Witness pool minimum
- [Source: _bmad-output/planning-artifacts/prd.md#FR118] - Topic rate limiting (related)
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-7] - Aggregate Anomaly Detection
- [Source: src/application/services/verifiable_witness_selection_service.py] - Selection service to extend
- [Source: src/application/ports/anomaly_detector.py] - Similar anomaly detector pattern
- [Source: src/infrastructure/stubs/anomaly_detector_stub.py] - Similar stub pattern
- [Source: src/domain/primitives/constitutional_thresholds.py#WITNESS_POOL_MINIMUM_THRESHOLD] - Pool minimum
- [Source: _bmad-output/project-context.md] - Project implementation rules
- [Source: _bmad-output/implementation-artifacts/stories/6-5-witness-selection-with-verifiable-randomness.md] - Previous story context
- [Source: _bmad-output/implementation-artifacts/stories/5-9-override-abuse-detection.md] - Similar ADR-7 implementation

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-08 | Story created with comprehensive FR116/FR117 context, statistical anomaly algorithm, ADR-7 integration | Create-Story Workflow (Opus 4.5) |

### File List

