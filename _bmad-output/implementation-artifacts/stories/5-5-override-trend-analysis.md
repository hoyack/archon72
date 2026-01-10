# Story 5.5: Override Trend Analysis (FR27, RT-3)

Status: done

## Code Review Notes (2026-01-07)

**Reviewer:** Adversarial Senior Developer Code Review

**Issues Found & Fixed:**
1. **H3/M1/M2: EventWriterService Interface Mismatch (CRITICAL)** - Fixed
   - Missing `agent_id` and `local_timestamp` parameters in `write_event()` calls
   - Payload was passed as dataclass instead of dict
   - Added `TREND_ANALYSIS_SYSTEM_AGENT_ID` constant
   - Fixed calls to convert payload via `asdict()` and pass all required params

2. **M3: Missing Stub Unit Test** - Fixed
   - Created `tests/unit/infrastructure/test_override_trend_repository_stub.py`
   - 17 tests covering protocol compliance, all methods, edge cases

3. **Tests Updated**
   - Added `TestEventWriterInterfaceCompliance` class to unit tests
   - Updated integration tests to verify correct interface parameters
   - Updated mock fixtures to match actual EventWriterService interface

**Test Results:** 75/75 PASSED (was 54 before fixes)

## Story

As a **system operator**,
I want 90-day rolling window trend analysis with anti-success alerts,
So that override abuse is detected.

## Acceptance Criteria

### AC1: 90-Day Rolling Trend Query
**Given** override history
**When** I query trends
**Then** I receive 90-day rolling count and rate

### AC2: 50% Increase Anti-Success Alert
**Given** override count increases >50% over 30 days
**When** threshold is crossed
**Then** an `AntiSuccessAlert` event is created
**And** alert includes before/after counts and percentage

### AC3: 30-Day Threshold Alert (>5 overrides)
**Given** >5 overrides in any 30-day period
**When** threshold is crossed
**Then** alert is triggered

### AC4: 365-Day Governance Review Trigger (RT-3)
**Given** >20 overrides in any 365-day rolling window (RT-3)
**When** threshold is crossed
**Then** governance review is triggered
**And** `GovernanceReviewRequiredEvent` is created

## Tasks / Subtasks

- [x] Task 1: Create Override Trend Event Types (AC: #2, #4)
  - [x] 1.1 Create `src/domain/events/anti_success_alert.py`
    - `AntiSuccessAlertPayload` dataclass with: `alert_type`, `before_count`, `after_count`, `percentage_change`, `window_days`, `detected_at`
    - Event type constant: `ANTI_SUCCESS_ALERT_EVENT_TYPE = "override.anti_success_alert"`
    - `signable_content()` method for witnessing (CT-12)
  - [x] 1.2 Create `src/domain/events/governance_review_required.py`
    - `GovernanceReviewRequiredPayload` dataclass with: `override_count`, `window_days`, `threshold`, `detected_at`
    - Event type constant: `GOVERNANCE_REVIEW_REQUIRED_EVENT_TYPE = "override.governance_review_required"`
    - `signable_content()` method for witnessing (CT-12)
  - [x] 1.3 Export from `src/domain/events/__init__.py`

- [x] Task 2: Create Override Trend Repository Port (AC: #1)
  - [x] 2.1 Create `src/application/ports/override_trend_repository.py`
  - [x] 2.2 Define `OverrideTrendRepositoryProtocol`:
    - `async def get_override_count(days: int) -> int`
    - `async def get_override_count_for_period(start_date: datetime, end_date: datetime) -> int`
    - `async def get_rolling_trend(days: int) -> OverrideTrendData`
  - [x] 2.3 Create `OverrideTrendData` dataclass with: `total_count`, `daily_rate`, `period_days`, `oldest_override`, `newest_override`
  - [x] 2.4 Export from `src/application/ports/__init__.py`

- [x] Task 3: Create Override Trend Analysis Service (AC: #1, #2, #3, #4)
  - [x] 3.1 Create `src/application/services/override_trend_service.py`
  - [x] 3.2 Implement `OverrideTrendAnalysisService`:
    - Inject: `OverrideTrendRepositoryProtocol`, `EventWriterService`, `HaltChecker`
  - [x] 3.3 Implement `get_90_day_trend()` -> `OverrideTrendData` (AC1)
  - [x] 3.4 Implement `analyze_50_percent_increase()` (AC2):
    - Compare current 30-day count vs previous 30-day count
    - If >50% increase, write `AntiSuccessAlertPayload` event
    - Return `AntiSuccessAnalysisResult`
  - [x] 3.5 Implement `check_30_day_threshold()` (AC3):
    - Get 30-day override count
    - If >5, write `AntiSuccessAlertPayload` with `alert_type="30_DAY_THRESHOLD"`
    - Return boolean and count
  - [x] 3.6 Implement `check_365_day_governance_trigger()` (AC4, RT-3):
    - Get 365-day override count
    - If >20, write `GovernanceReviewRequiredPayload` event
    - Return `GovernanceAnalysisResult`
  - [x] 3.7 Implement `run_full_analysis()` -> `TrendAnalysisReport`:
    - Call all analysis methods
    - Aggregate results into comprehensive report
    - HALT CHECK FIRST (CT-11 pattern)
  - [x] 3.8 Export from `src/application/services/__init__.py`

- [x] Task 4: Create Override Trend Repository Stub (AC: #1)
  - [x] 4.1 Create `src/infrastructure/stubs/override_trend_repository_stub.py`
  - [x] 4.2 Implement `OverrideTrendRepositoryStub`:
    - In-memory storage for test data
    - `set_override_history(history: list[datetime])` for test setup
    - Implement all protocol methods
  - [x] 4.3 Export from `src/infrastructure/stubs/__init__.py`

- [x] Task 5: Create Trend Analysis Domain Errors (AC: #1, #2, #3, #4)
  - [x] 5.1 Create `src/domain/errors/trend.py`:
    - `TrendAnalysisError(ConclaveError)` - base for trend errors
    - `InsufficientDataError(TrendAnalysisError)` - not enough history for analysis
  - [x] 5.2 Export from `src/domain/errors/__init__.py`

- [x] Task 6: Write Unit Tests (AC: #1, #2, #3, #4)
  - [x] 6.1 Create `tests/unit/domain/test_anti_success_alert_event.py`:
    - Test payload creation with required fields
    - Test `signable_content()` determinism
    - Test event type constant value
  - [x] 6.2 Create `tests/unit/domain/test_governance_review_required_event.py`:
    - Test payload creation with required fields
    - Test `signable_content()` determinism
    - Test event type constant value
  - [x] 6.3 Create `tests/unit/application/test_override_trend_repository_port.py`:
    - Test protocol compliance with stub
    - Test `OverrideTrendData` dataclass
  - [x] 6.4 Create `tests/unit/application/test_override_trend_service.py`:
    - Test `get_90_day_trend()` returns correct data
    - Test `analyze_50_percent_increase()` triggers alert when threshold crossed
    - Test `analyze_50_percent_increase()` no alert when below threshold
    - Test `check_30_day_threshold()` triggers at >5 overrides
    - Test `check_30_day_threshold()` no alert at <=5 overrides
    - Test `check_365_day_governance_trigger()` triggers at >20 overrides (RT-3)
    - Test `check_365_day_governance_trigger()` no trigger at <=20 overrides
    - Test `run_full_analysis()` halt check first
    - Test `run_full_analysis()` aggregates all analyses

- [x] Task 7: Write Integration Tests (AC: #1, #2, #3, #4)
  - [x] 7.1 Create `tests/integration/test_override_trend_analysis_integration.py`:
    - Test: `test_90_day_trend_query_returns_correct_data` (AC1)
    - Test: `test_50_percent_increase_triggers_anti_success_alert` (AC2)
    - Test: `test_30_day_threshold_triggers_alert` (AC3)
    - Test: `test_365_day_governance_review_triggered` (AC4, RT-3)
    - Test: `test_anti_success_alert_event_is_witnessed`
    - Test: `test_governance_review_event_is_witnessed`
    - Test: `test_full_analysis_during_halt_raises_error`
    - Test: `test_multiple_thresholds_crossed_creates_multiple_events`

- [x] Task 8: Add API Endpoint (Optional - depends on existing API patterns)
  - [x] 8.1 Skipped - Service layer complete; API endpoint can be added later when needed
  - [x] 8.2 Skipped - Service layer provides full functionality

## Dev Notes

### Constitutional Constraints (CRITICAL)

- **FR27**: Override trend analysis with anti-success alerts
- **RT-3**: >20 overrides in 365-day window triggers governance review
- **CT-11**: Silent failure destroys legitimacy -> HALT CHECK FIRST
- **CT-12**: Witnessing creates accountability -> Alert events MUST be witnessed
- **ADR-7**: Aggregate Anomaly Detection - Three detection layers (Rules, Statistics, Human)

### ADR-7 Implementation Context

From the architecture document, ADR-7 defines a **hybrid detection system**:

| Layer | Method | Response |
|-------|--------|----------|
| **Rules** | Predefined thresholds | Auto-alert, auto-halt if critical |
| **Statistics** | Baseline deviation detection | Queue for review |
| **Human** | Weekly anomaly review ceremony | Classify, escalate, or dismiss |

**Metrics tracked (relevant to this story):**
- Halt frequency by source
- Ceremony frequency by type
- **Event rate patterns** ← Override events
- Failed verification attempts

This story implements the **Rules layer** for override trend detection:
- >50% increase in 30 days → `AntiSuccessAlert`
- >5 overrides in 30 days → `AntiSuccessAlert` (30_DAY_THRESHOLD)
- >20 overrides in 365 days → `GovernanceReviewRequired` (RT-3)

### Key Thresholds (From FR27 and RT-3)

| Threshold | Window | Alert Type |
|-----------|--------|------------|
| >50% increase | 30 days vs previous 30 days | AntiSuccessAlert |
| >5 overrides | Any 30-day period | AntiSuccessAlert (30_DAY_THRESHOLD) |
| >20 overrides | 365-day rolling | GovernanceReviewRequired (RT-3) |

### Key Implementation Patterns

**Anti-Success Alert Event (FR27):**
```python
# src/domain/events/anti_success_alert.py
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

# Event type constant
ANTI_SUCCESS_ALERT_EVENT_TYPE: str = "override.anti_success_alert"


class AlertType(Enum):
    """Types of anti-success alerts."""
    PERCENTAGE_INCREASE = "PERCENTAGE_INCREASE"  # >50% increase
    THRESHOLD_30_DAY = "THRESHOLD_30_DAY"  # >5 in 30 days


@dataclass(frozen=True, eq=True)
class AntiSuccessAlertPayload:
    """Payload for anti-success alert events (FR27).

    Constitutional Constraints:
    - FR27: Override trend analysis with anti-success alerts
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability
    """
    alert_type: AlertType
    before_count: int  # Count in comparison period
    after_count: int   # Count in current period
    percentage_change: float  # Percentage change (can be negative)
    window_days: int   # Analysis window in days
    detected_at: datetime

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12)."""
        return json.dumps(
            {
                "event_type": "AntiSuccessAlert",
                "alert_type": self.alert_type.value,
                "before_count": self.before_count,
                "after_count": self.after_count,
                "percentage_change": self.percentage_change,
                "window_days": self.window_days,
                "detected_at": self.detected_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")
```

**Governance Review Event (RT-3):**
```python
# src/domain/events/governance_review_required.py
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

# Event type constant
GOVERNANCE_REVIEW_REQUIRED_EVENT_TYPE: str = "override.governance_review_required"

# RT-3 threshold constants
RT3_THRESHOLD: int = 20
RT3_WINDOW_DAYS: int = 365


@dataclass(frozen=True, eq=True)
class GovernanceReviewRequiredPayload:
    """Payload for governance review required events (RT-3).

    Constitutional Constraints:
    - RT-3: >20 overrides in 365-day window triggers governance review
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability
    """
    override_count: int
    window_days: int
    threshold: int
    detected_at: datetime

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12)."""
        return json.dumps(
            {
                "event_type": "GovernanceReviewRequired",
                "override_count": self.override_count,
                "window_days": self.window_days,
                "threshold": self.threshold,
                "detected_at": self.detected_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")
```

**Trend Repository Port:**
```python
# src/application/ports/override_trend_repository.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol


@dataclass(frozen=True)
class OverrideTrendData:
    """Data structure for override trend analysis results."""
    total_count: int
    daily_rate: float  # Overrides per day average
    period_days: int
    oldest_override: Optional[datetime]
    newest_override: Optional[datetime]


class OverrideTrendRepositoryProtocol(Protocol):
    """Port for querying override history for trend analysis (FR27, RT-3)."""

    async def get_override_count(self, days: int) -> int:
        """Get total override count for the last N days."""
        ...

    async def get_override_count_for_period(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> int:
        """Get override count for a specific date range."""
        ...

    async def get_rolling_trend(self, days: int) -> OverrideTrendData:
        """Get rolling trend data for the last N days."""
        ...
```

**Trend Analysis Service (Core Implementation):**
```python
# src/application/services/override_trend_service.py
class OverrideTrendAnalysisService:
    """Analyzes override trends and triggers alerts (FR27, RT-3, ADR-7).

    Constitutional Constraints:
    - FR27: Override trend analysis with anti-success alerts
    - RT-3: >20 overrides in 365-day window triggers governance review
    - CT-11: HALT CHECK FIRST - Check halt state before any operation
    - CT-12: All alert events MUST be witnessed
    - ADR-7: Rules layer of aggregate anomaly detection
    """

    # Threshold constants (from FR27 and RT-3)
    PERCENTAGE_THRESHOLD: float = 50.0  # >50% increase triggers alert
    THRESHOLD_30_DAY: int = 5  # >5 overrides in 30 days
    THRESHOLD_365_DAY: int = 20  # >20 overrides in 365 days (RT-3)

    def __init__(
        self,
        trend_repository: OverrideTrendRepositoryProtocol,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
    ) -> None:
        self._trend_repository = trend_repository
        self._event_writer = event_writer
        self._halt_checker = halt_checker

    async def run_full_analysis(self) -> TrendAnalysisReport:
        """Run complete trend analysis with all threshold checks.

        Developer Golden Rule: HALT CHECK FIRST (CT-11 pattern)
        """
        # HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # Run all analyses...
```

### Architecture Pattern: Layered Analysis

```
Override Events (from Story 5.1)
     │
     ▼
┌─────────────────────────────────────────┐
│ OverrideTrendRepositoryProtocol         │ ← Story 5.5 (NEW)
│ - Query override counts by time window  │
│ - Calculate rolling trends              │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ OverrideTrendAnalysisService            │ ← Story 5.5 (NEW)
│ - HALT CHECK FIRST                      │
│ - 50% increase detection (FR27)         │
│ - 30-day threshold check (FR27)         │
│ - 365-day governance trigger (RT-3)     │
└─────────────────────────────────────────┘
     │ (if threshold crossed)
     ▼
┌─────────────────────────────────────────┐
│ EventWriterService                      │ ← Story 1.6
│ - Write AntiSuccessAlert events         │
│ - Write GovernanceReviewRequired events │
│ - Events are witnessed (CT-12)          │
└─────────────────────────────────────────┘
```

### Previous Story Learnings (from 5.4)

**Error Handling Pattern:**
- Create specific errors in `src/domain/errors/`
- Inherit from appropriate base class
- Include FR/RT reference in error message

**Service Injection Pattern:**
- Use Protocol for ports
- Optional dependencies for backward compatibility
- Bind logger with operation context

**Testing Pattern:**
- PM/RT tests MUST verify specific requirements
- Use `pytest.mark.asyncio` for all async tests
- Mock dependencies for unit tests
- Use stubs for integration tests

### Files to Create

```
src/domain/events/anti_success_alert.py                     # AntiSuccessAlertPayload
src/domain/events/governance_review_required.py             # GovernanceReviewRequiredPayload
src/domain/errors/trend.py                                  # Trend analysis errors
src/application/ports/override_trend_repository.py          # Repository protocol
src/application/services/override_trend_service.py          # Trend analysis service
src/infrastructure/stubs/override_trend_repository_stub.py  # Test stub
tests/unit/domain/test_anti_success_alert_event.py          # Event tests
tests/unit/domain/test_governance_review_required_event.py  # Event tests
tests/unit/application/test_override_trend_repository_port.py  # Port tests
tests/unit/application/test_override_trend_service.py       # Service unit tests
tests/integration/test_override_trend_analysis_integration.py  # Integration tests
```

### Files to Modify

```
src/domain/events/__init__.py                               # Export new events
src/domain/errors/__init__.py                               # Export new errors
src/application/ports/__init__.py                           # Export new port
src/application/services/__init__.py                        # Export new service
src/infrastructure/stubs/__init__.py                        # Export new stub
```

### Import Rules (Hexagonal Architecture)

- `domain/events/` imports from `domain/errors/`, `typing`, `json`, `datetime`, `dataclasses`
- `domain/errors/` inherits from base `ConclaveError`
- `application/ports/` imports from `typing` only (Protocol)
- `application/services/` imports from `application/ports/`, `domain/`
- NEVER import from `infrastructure/` in `api/` or `application/`

### Testing Standards

- ALL tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Unit tests mock the repository protocol
- Integration tests use stub implementation
- RT-3 test MUST verify 365-day governance trigger specifically

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-5.5] - Story definition
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-007] - Aggregate Anomaly Detection
- [Source: _bmad-output/planning-artifacts/architecture.md#RT-3] - Multi-Path Partition Detection (governance trigger)
- [Source: src/application/services/override_service.py] - Override orchestration pattern
- [Source: src/domain/events/override_event.py] - Override event patterns
- [Source: _bmad-output/implementation-artifacts/stories/5-4-constitution-supremacy-no-witness-suppression.md] - Previous story patterns

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 54 tests passing (45 unit + 9 integration)

### Completion Notes List

1. **All acceptance criteria implemented:**
   - AC1: 90-day trend query via `get_90_day_trend()` method
   - AC2: 50% increase alert via `analyze_50_percent_increase()` method
   - AC3: 30-day threshold (>5) via `check_30_day_threshold()` method
   - AC4: 365-day governance trigger (RT-3) via `check_365_day_governance_trigger()` method

2. **Constitutional compliance:**
   - CT-11: HALT CHECK FIRST pattern in `run_full_analysis()`
   - CT-12: All alert events have `signable_content()` for witnessing
   - FR27: Anti-success alerts implemented
   - RT-3: >20 overrides in 365 days triggers governance review

3. **Task 8 (API Endpoint) skipped:** Optional task; service layer provides complete functionality. API can be added later following existing patterns in `src/api/routes/override.py`.

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-07 | Story created with comprehensive FR27/RT-3 context | Create-Story Workflow (Opus 4.5) |
| 2026-01-07 | Implementation completed - all tasks done, 54 tests passing | Claude Opus 4.5 |

### File List

**Created:**
- `src/domain/events/anti_success_alert.py` - AntiSuccessAlertPayload event
- `src/domain/events/governance_review_required.py` - GovernanceReviewRequiredPayload event
- `src/domain/errors/trend.py` - TrendAnalysisError, InsufficientDataError
- `src/application/ports/override_trend_repository.py` - OverrideTrendRepositoryProtocol, OverrideTrendData
- `src/application/services/override_trend_service.py` - OverrideTrendAnalysisService
- `src/infrastructure/stubs/override_trend_repository_stub.py` - OverrideTrendRepositoryStub
- `tests/unit/domain/test_anti_success_alert_event.py` - 8 unit tests
- `tests/unit/domain/test_governance_review_required_event.py` - 8 unit tests
- `tests/unit/application/test_override_trend_repository_port.py` - 14 unit tests
- `tests/unit/application/test_override_trend_service.py` - 15 unit tests
- `tests/integration/test_override_trend_analysis_integration.py` - 9 integration tests

**Modified:**
- `src/domain/events/__init__.py` - Export new events
- `src/domain/errors/__init__.py` - Export new errors
- `src/application/ports/__init__.py` - Export new port
- `src/application/services/__init__.py` - Export new service
- `src/infrastructure/stubs/__init__.py` - Export new stub

