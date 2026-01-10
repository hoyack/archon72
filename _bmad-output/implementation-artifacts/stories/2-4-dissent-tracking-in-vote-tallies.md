# Story 2.4: Dissent Tracking in Vote Tallies (FR12)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **external observer**,
I want dissent percentages visible in every vote tally,
So that I can detect healthy disagreement vs groupthink.

## Acceptance Criteria

### AC1: Vote Tally Structure
**Given** a vote is tallied
**When** the result is recorded
**Then** the event includes: `yes_count`, `no_count`, `abstain_count`
**And** `dissent_percentage` is calculated as (minority votes / total votes) × 100

### AC2: Unanimous Vote Handling
**Given** a unanimous vote (100% agreement)
**When** the result is recorded
**Then** `dissent_percentage` is 0
**And** `unanimous` flag is TRUE
**And** a `UnanimousVoteEvent` is created (separate from standard vote)

### AC3: Dissent Health Metrics (PM Finding)
**Given** the dissent health metrics requirement
**When** I query dissent trends
**Then** rolling averages are available
**And** alerts fire if dissent drops below 10% over 30 days

## Tasks / Subtasks

- [x] Task 1: Create UnanimousVoteEvent Domain Type (AC: 2) - 16 tests
  - [x] 1.1 Create `src/domain/events/unanimous_vote.py`
  - [x] 1.2 Define `UnanimousVotePayload` frozen dataclass
  - [x] 1.3 Define `VoteOutcome` enum with YES_UNANIMOUS, NO_UNANIMOUS, ABSTAIN_UNANIMOUS
  - [x] 1.4 Add `UNANIMOUS_VOTE_EVENT_TYPE = "vote.unanimous"` constant
  - [x] 1.5 Add validation in `__post_init__` for unanimity constraints
  - [x] 1.6 Add `to_dict()` method for serialization
  - [x] 1.7 Add to `src/domain/events/__init__.py` exports
  - [x] 1.8 Add unit tests (actual: 16 tests)

- [x] Task 2: Create DissentMetricsPort Interface (AC: 3) - 11 tests
  - [x] 2.1 Create `src/application/ports/dissent_metrics.py`
  - [x] 2.2 Define `DissentMetricsPort(Protocol)` with all required methods
  - [x] 2.3 Define `DissentRecord` dataclass
  - [x] 2.4 Add to `src/application/ports/__init__.py` exports
  - [x] 2.5 Add unit tests (actual: 11 tests)

- [x] Task 3: Create DissentHealthService Application Layer (AC: 3) - 9 tests
  - [x] 3.1 Create `src/application/services/dissent_health_service.py`
  - [x] 3.2 Inject: `HaltChecker`, `DissentMetricsPort`
  - [x] 3.3 Implement `record_dissent` with HALT FIRST
  - [x] 3.4 Implement `get_health_status`
  - [x] 3.5 Implement `check_alert_condition`
  - [x] 3.6 Define `DissentHealthStatus` and `DissentAlert` dataclasses
  - [x] 3.7 Add unit tests (actual: 9 tests)

- [x] Task 4: Create DissentMetricsStub Infrastructure (AC: 3) - 11 tests
  - [x] 4.1 Create `src/infrastructure/stubs/dissent_metrics_stub.py`
  - [x] 4.2 Implement `DissentMetricsStub` with in-memory storage
  - [x] 4.3 Follow DEV_MODE_WATERMARK pattern (RT-1/ADR-4)
  - [x] 4.4 Store records with timestamp for time-based queries
  - [x] 4.5 Add unit tests (actual: 11 tests)

- [x] Task 5: Integrate UnanimousVoteEvent with CollectiveOutputService (AC: 2) - 8 tests
  - [x] 5.1 Modify `src/application/services/collective_output_service.py`
  - [x] 5.2 Create `UnanimousVotePort` protocol
  - [x] 5.3 Create `UnanimousVoteStub`
  - [x] 5.4 Add unit tests (actual: 8 tests)

- [x] Task 6: Integrate Dissent Recording with CollectiveOutputService (AC: 1, 3)
  - [x] 6.1 Add `DissentHealthService` injection to `CollectiveOutputService`
  - [x] 6.2 Ensure dissent is recorded for EVERY collective output
  - [x] 6.3 Tests covered by integration tests

- [x] Task 7: FR12 Compliance Integration Tests (AC: 1, 2, 3) - 13 tests
  - [x] 7.1 Create `tests/integration/test_dissent_tracking_integration.py`
  - [x] 7.2 Test: Dissent percentage calculated correctly for split votes
  - [x] 7.3 Test: Unanimous vote creates UnanimousVoteEvent with correct outcome
  - [x] 7.4 Test: 100% yes vote → YES_UNANIMOUS outcome
  - [x] 7.5 Test: 100% no vote → NO_UNANIMOUS outcome
  - [x] 7.6 Test: 100% abstain vote → ABSTAIN_UNANIMOUS outcome
  - [x] 7.7 Test: Rolling average calculated correctly over 30 days
  - [x] 7.8 Test: Alert fires when dissent drops below 10%
  - [x] 7.9 Test: No alert when dissent is healthy (above 10%)
  - [x] 7.10 Test: HALT state blocks dissent recording
  - [x] 7.11 Integration tests (actual: 13 tests)

## Dev Notes

### Critical Architecture Context

**FR12: Dissent Tracking in Vote Tallies**
From the PRD, FR12 states: "Dissent percentages are visible in every vote tally so observers can detect healthy disagreement vs groupthink." This is a governance health metric that external observers use to verify the system isn't converging on groupthink.

**NFR-023: Dissent Health Metrics**
From the NFRs, the system must track "voting correlation" as a health metric. Low dissent over time is a constitutional concern - it may indicate agents are converging or being manipulated.

**Constitutional Truths Honored:**
- **CT-11:** Silent failure destroys legitimacy → If dissent recording fails, raise error immediately
- **CT-12:** Witnessing creates accountability → Unanimous votes get special witness events
- **CT-13:** Integrity outranks availability → Better to reject vote without dissent tracking than accept silently

### Previous Story Intelligence (Stories 2.1, 2.2, 2.3)

**CRITICAL: Core dissent infrastructure already exists from Story 2.3!**

The following components are already implemented:

1. **VoteCounts** (`src/domain/events/collective_output.py`):
```python
@dataclass(frozen=True, eq=True)
class VoteCounts:
    yes_count: int
    no_count: int
    abstain_count: int

    @property
    def total(self) -> int:
        return self.yes_count + self.no_count + self.abstain_count
```

2. **calculate_dissent_percentage** (`src/domain/services/collective_output_enforcer.py`):
```python
def calculate_dissent_percentage(vote_counts: VoteCounts) -> float:
    """Formula: (minority_votes / total_votes) × 100"""
    total = vote_counts.total
    if total == 0:
        return 0.0
    majority = max(vote_counts.yes_count, vote_counts.no_count, vote_counts.abstain_count)
    minority = total - majority
    return (minority / total) * 100.0
```

3. **is_unanimous** (`src/domain/services/collective_output_enforcer.py`):
```python
def is_unanimous(vote_counts: VoteCounts) -> bool:
    """True if all votes are for the same option."""
    total = vote_counts.total
    if total == 0:
        return True
    majority = max(vote_counts.yes_count, vote_counts.no_count, vote_counts.abstain_count)
    return majority == total
```

4. **CollectiveOutputPayload** already includes `dissent_percentage` and `unanimous` fields.

**What Story 2.4 Adds:**
- `UnanimousVoteEvent` for special tracking of unanimous outcomes
- `DissentMetricsPort` for time-series dissent tracking
- `DissentHealthService` for health monitoring and alerting
- Rolling average calculation over configurable periods
- Alert triggering when dissent drops below threshold

### VoteOutcome Enum Design

```python
from enum import Enum

class VoteOutcome(Enum):
    """Outcome of a unanimous vote (FR12)."""
    YES_UNANIMOUS = "yes_unanimous"      # All votes were YES
    NO_UNANIMOUS = "no_unanimous"        # All votes were NO
    ABSTAIN_UNANIMOUS = "abstain_unanimous"  # All votes were ABSTAIN
```

### Dissent Threshold Logic

Per the PM finding documented in the epics:
- **Threshold:** 10% dissent over 30 days
- **Alert Condition:** Rolling average < 10%
- **Health Indicator:** Healthy disagreement = dissent > 10%

Example calculation:
```python
# 30 votes recorded over 30 days with these dissent percentages:
dissent_values = [5.0, 8.0, 3.0, 12.0, 15.0, ...]  # 30 values
rolling_average = sum(dissent_values) / len(dissent_values)

if rolling_average < 10.0:
    alert = DissentAlert(
        threshold=10.0,
        actual_average=rolling_average,
        period_days=30,
        alert_type="DISSENT_BELOW_THRESHOLD",
    )
```

### Project Structure Notes

**Files to Create:**
```
src/
├── domain/
│   └── events/
│       └── unanimous_vote.py           # UnanimousVotePayload, VoteOutcome
├── application/
│   ├── ports/
│   │   ├── dissent_metrics.py          # DissentMetricsPort, DissentRecord
│   │   └── unanimous_vote.py           # UnanimousVotePort
│   └── services/
│       └── dissent_health_service.py   # DissentHealthService, alerts
└── infrastructure/
    └── stubs/
        ├── dissent_metrics_stub.py     # In-memory dissent tracking
        └── unanimous_vote_stub.py      # In-memory unanimous vote store

tests/
├── unit/
│   ├── domain/
│   │   └── test_unanimous_vote_event.py  # 12 tests
│   └── application/
│       ├── test_dissent_metrics_port.py  # 8 tests
│       └── test_dissent_health_service.py # 10 tests
│   └── infrastructure/
│       ├── test_dissent_metrics_stub.py  # 8 tests
│       └── test_unanimous_vote_stub.py   # 8 tests
└── integration/
    └── test_dissent_tracking_integration.py # 12 tests
```

**Files to Modify:**
```
src/application/services/collective_output_service.py
src/domain/events/__init__.py
src/application/ports/__init__.py
```

**Alignment with Hexagonal Architecture:**
- Domain layer (`domain/`) has NO infrastructure imports
- Application layer (`application/`) orchestrates domain and uses ports
- Infrastructure layer (`infrastructure/`) implements adapters for ports
- Import boundary enforcement from Story 0-6 MUST be respected

### Testing Standards

Per `project-context.md`:
- ALL test files use `pytest.mark.asyncio`
- Use `async def test_*` for async tests
- Use `AsyncMock` not `Mock` for async functions
- Unit tests in `tests/unit/{module}/test_{name}.py`
- Integration tests in `tests/integration/test_{feature}_integration.py`
- 80% minimum coverage

**Expected Test Count:** ~66 tests total (12+8+10+8+8+8+12)

### Library/Framework Requirements

**Required Dependencies (already installed in Epic 0):**
- `structlog` for logging (NO print statements, NO f-strings in logs)
- `pytest-asyncio` for async testing
- Python 3.10+ compatible (use `Optional[T]` not `T | None`)
- `datetime` from stdlib for timestamp handling

**Do NOT add new dependencies without explicit approval.**

### Reuse Existing Code

**DO NOT REIMPLEMENT:** The following already exist and MUST be reused:
- `VoteCounts` from `src/domain/events/collective_output.py`
- `calculate_dissent_percentage()` from `src/domain/services/collective_output_enforcer.py`
- `is_unanimous()` from `src/domain/services/collective_output_enforcer.py`
- `CollectiveOutputService` patterns from `src/application/services/collective_output_service.py`
- `HaltChecker` pattern from `src/application/ports/halt_checker.py`

### Logging Pattern

Per `project-context.md`, use structured logging:
```python
import structlog

logger = structlog.get_logger()

# CORRECT
logger.info(
    "dissent_recorded",
    output_id=str(output_id),
    dissent_percentage=dissent_pct,
)

logger.warning(
    "dissent_alert_triggered",
    threshold=10.0,
    actual_average=rolling_avg,
    period_days=30,
)

# WRONG - Never do these
print(f"Dissent: {dissent_pct}")  # No print
logger.info(f"Recorded dissent {dissent_pct}")  # No f-strings in logs
```

### Integration with Previous Stories

**Story 2.1 (FR9 - No Preview):**
- Dissent metrics should follow commit-before-view pattern
- All dissent records are part of the witnessed event stream

**Story 2.2 (FR10 - 72 Concurrent Agents):**
- Unanimous votes with 72 agents are notable events
- `voter_count` in UnanimousVotePayload should typically be 72

**Story 2.3 (FR11 - Collective Output Irreducibility):**
- Dissent tracking integrates with `CollectiveOutputService`
- Reuse existing `VoteCounts` and calculation functions

### Security Considerations

**No Manipulation of Dissent Metrics:**
- Dissent records are append-only (no edits)
- Historical dissent cannot be altered
- Alerts are based on raw data, not computed after-the-fact

**Audit Trail:**
- Every dissent record includes timestamp
- Rolling averages can be independently verified by observers
- Unanimous votes are separately witnessed

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.4: Dissent Tracking in Vote Tallies]
- [Source: _bmad-output/project-context.md]
- [Source: _bmad-output/implementation-artifacts/stories/2-1-no-preview-constraint.md] - FR9 patterns
- [Source: _bmad-output/implementation-artifacts/stories/2-2-72-concurrent-agent-deliberations.md] - Concurrent patterns
- [Source: _bmad-output/implementation-artifacts/stories/2-3-collective-output-irreducibility.md] - Dissent calculation patterns
- [Source: src/domain/events/collective_output.py] - VoteCounts, existing dissent fields
- [Source: src/domain/services/collective_output_enforcer.py] - calculate_dissent_percentage, is_unanimous
- [Source: src/application/services/collective_output_service.py] - Integration target

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - No errors encountered during implementation.

### Completion Notes List

- All 7 tasks completed successfully
- Total tests: 80 (16 + 11 + 9 + 11 + 8 + 12 + 13)
- All acceptance criteria met:
  - AC1: Vote tally structure with yes/no/abstain counts and dissent percentage
  - AC2: UnanimousVoteEvent created for 100% agreement votes
  - AC3: Rolling averages and alert thresholds implemented
- HALT FIRST pattern enforced throughout
- DEV_MODE_WATERMARK pattern followed for all stubs
- Hexagonal architecture maintained (domain has no infrastructure imports)
- Structured logging with structlog (no print statements or f-strings)

### File List

**Files Created:**
- `src/domain/events/unanimous_vote.py` - UnanimousVotePayload, VoteOutcome enum
- `src/application/ports/dissent_metrics.py` - DissentMetricsPort, DissentRecord
- `src/application/ports/unanimous_vote.py` - UnanimousVotePort, StoredUnanimousVote
- `src/application/services/dissent_health_service.py` - DissentHealthService, alerts
- `src/infrastructure/stubs/dissent_metrics_stub.py` - In-memory dissent tracking
- `src/infrastructure/stubs/unanimous_vote_stub.py` - In-memory unanimous vote store
- `tests/unit/domain/test_unanimous_vote_event.py` - 16 tests
- `tests/unit/application/test_dissent_metrics_port.py` - 11 tests
- `tests/unit/application/test_dissent_health_service.py` - 9 tests
- `tests/unit/infrastructure/test_dissent_metrics_stub.py` - 11 tests
- `tests/unit/infrastructure/test_unanimous_vote_stub.py` - 8 tests
- `tests/integration/test_dissent_tracking_integration.py` - 13 tests

**Files Modified:**
- `src/domain/events/__init__.py` - Added exports for unanimous vote types
- `src/application/ports/__init__.py` - Added exports for new ports
- `src/application/services/collective_output_service.py` - FR12 integration

