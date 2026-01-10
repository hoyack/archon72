# Story 8.8: Pre-mortem Operational Failures Prevention (FR106-FR107)

Status: done

## Story

As a **system operator**,
I want operational failure prevention based on pre-mortem analysis,
So that known failure modes are mitigated.

## Acceptance Criteria

### AC1: Failure Mode Registry
**Given** the pre-mortem findings from architecture validation
**When** I examine the failure prevention system
**Then** all identified failure modes are registered:
  - VAL-1: Silent signature corruption
  - VAL-2: Ceremony timeout limbo
  - VAL-3: Import boundary bypass
  - VAL-4: Halt storm via restarts
  - VAL-5: Observer verification staleness
**And** each failure mode has documented mitigation strategy
**And** mitigations are implemented and verified

### AC2: Early Warning Alert System
**Given** a known failure mode
**When** conditions approach the failure threshold
**Then** an early warning alert is raised BEFORE failure occurs
**And** the alert includes:
  - Failure mode ID (e.g., VAL-1)
  - Current metric value
  - Threshold that triggered alert
  - Recommended preventive action
**And** preventive action can be taken

### AC3: Failure Mode Monitoring
**Given** the monitoring system
**When** operational metrics are collected
**Then** each failure mode has associated health indicators
**And** indicators are checked at appropriate intervals
**And** historical trends are tracked for pattern detection

### AC4: Query Performance Compliance (FR106)
**Given** historical queries
**When** query range is up to 10,000 events
**Then** query completes within 30 seconds
**And** larger ranges are batched with progress indication
**And** query timeouts are logged as operational events

### AC5: Constitutional Event Priority (FR107)
**Given** system load conditions
**When** load approaches capacity limits
**Then** constitutional events are NEVER shed
**And** only operational telemetry may be deprioritized
**And** load shedding decisions are logged

### AC6: Pattern Violation Detection (From FMEA)
**Given** pattern violations from the Pattern Violation Risk Matrix
**When** code is executed
**Then** violations are detected:
  - PV-001: Raw string event type (EventType enum required)
  - PV-002: Plain string hash (ContentRef validation required)
  - PV-003: Missing HaltGuard (base class requirement)
**And** violations raise alerts with remediation guidance

## Tasks / Subtasks

- [x] **Task 1: Create Failure Mode Domain Models** (AC: 1)
  - [x] Create `src/domain/models/failure_mode.py`
    - [x] `FailureModeId` enum (VAL_1 through VAL_5, PV_001 through PV_003)
    - [x] `FailureMode` dataclass with id, description, severity, mitigation
    - [x] `FailureModeStatus` enum (healthy, warning, critical)
    - [x] `FailureModeThreshold` dataclass with metric_name, warning_value, critical_value
  - [x] Create `src/domain/errors/failure_prevention.py`
    - [x] `FailureModeViolationError` for pattern violations
    - [x] `EarlyWarningError` for pre-failure conditions

- [x] **Task 2: Create Failure Mode Registry Port** (AC: 1)
  - [x] Create `src/application/ports/failure_mode_registry.py`
    - [x] `FailureModeRegistryPort` protocol
    - [x] `get_failure_mode(mode_id: FailureModeId) -> FailureMode`
    - [x] `get_all_failure_modes() -> list[FailureMode]`
    - [x] `get_mode_status(mode_id: FailureModeId) -> FailureModeStatus`
    - [x] `update_mode_metrics(mode_id: FailureModeId, metrics: dict) -> None`

- [x] **Task 3: Create Failure Prevention Service** (AC: 1, 2, 3)
  - [x] Create `src/application/services/failure_prevention_service.py`
    - [x] `FailurePreventionService` class with `LoggingMixin`
    - [x] `check_failure_mode(mode_id: FailureModeId) -> FailureModeStatus`
    - [x] `get_early_warnings() -> list[EarlyWarning]`
    - [x] `record_metric(mode_id: FailureModeId, metric_name: str, value: float) -> None`
    - [x] `get_health_summary() -> dict[FailureModeId, FailureModeStatus]`

- [x] **Task 4: Create Early Warning Alert Infrastructure** (AC: 2)
  - [x] Create `src/domain/events/early_warning.py`
    - [x] `EarlyWarningEvent` payload with mode_id, current_value, threshold, recommended_action
    - [x] Register in `PAYLOAD_REGISTRY`
  - [x] Create `src/application/services/early_warning_service.py`
    - [x] `EarlyWarningService` class
    - [x] `evaluate_thresholds() -> list[EarlyWarningEvent]`
    - [x] `emit_warning(warning: EarlyWarningEvent) -> None`

- [x] **Task 5: Implement Query Performance Monitor** (AC: 4)
  - [x] Create `src/application/services/query_performance_service.py`
    - [x] `QueryPerformanceService` class
    - [x] `track_query(query_id: str, event_count: int, duration_ms: float) -> None`
    - [x] `check_compliance() -> bool` (30-second SLA for <10k events)
    - [x] `get_batch_progress(query_id: str) -> BatchProgress`
  - [x] Create `src/domain/models/batch_progress.py`
    - [x] `BatchProgress` dataclass with total_events, processed_events, estimated_completion

- [x] **Task 6: Implement Load Shedding Decision Service** (AC: 5)
  - [x] Create `src/application/services/load_shedding_service.py`
    - [x] `LoadSheddingService` class
    - [x] `evaluate_load() -> LoadStatus`
    - [x] `should_shed_telemetry() -> bool`
    - [x] `log_shedding_decision(reason: str) -> None`
  - [x] Create `src/domain/models/load_status.py`
    - [x] `LoadStatus` dataclass with current_load, capacity_percentage, shedding_active
  - [x] **CRITICAL**: Constitutional events MUST NEVER be shed - validated in tests

- [x] **Task 7: Implement Pattern Violation Detection** (AC: 6)
  - [x] Create `src/application/services/pattern_violation_service.py`
    - [x] `PatternViolationService` class
    - [x] `detect_violations() -> list[PatternViolation]`
    - [x] `validate_event_type(event_type: Any) -> bool` (must be EventType enum)
    - [x] `validate_content_ref(hash_value: Any) -> bool` (must be ContentRef)
    - [x] `validate_halt_guard_injection(service: Any) -> bool`
  - [x] Create `src/domain/models/pattern_violation.py`
    - [x] `PatternViolation` dataclass with violation_id, location, description, remediation

- [x] **Task 8: Create Failure Mode Registry Stub** (AC: 1)
  - [x] Create `src/infrastructure/stubs/failure_mode_registry_stub.py`
    - [x] `FailureModeRegistryStub` implementing port
    - [x] Pre-populate with all VAL-* and PV-* failure modes from architecture
    - [x] Configurable thresholds for testing

- [x] **Task 9: Create API Endpoints** (AC: 1, 2, 3)
  - [x] Create `src/api/routes/failure_prevention.py`
    - [x] `GET /v1/failure-modes` - List all failure modes
    - [x] `GET /v1/failure-modes/{mode_id}` - Get specific mode status
    - [x] `GET /v1/failure-modes/warnings` - Get current early warnings
    - [x] `GET /v1/failure-modes/health` - Get health summary
  - [x] Create `src/api/models/failure_prevention.py`
    - [x] Pydantic response models for all endpoints

- [x] **Task 10: Unit Tests** (AC: 1, 2, 3, 4, 5, 6)
  - [x] Create `tests/unit/application/test_failure_prevention_service.py`
    - [x] Test failure mode registration
    - [x] Test health status calculation
    - [x] Test threshold breach detection
  - [x] Create `tests/unit/domain/test_failure_mode.py`
    - [x] Test domain model validation
    - [x] Test DEFAULT_FAILURE_MODES dictionary
  - [x] Create `tests/unit/application/test_query_performance_service.py`
    - [x] Test SLA compliance checking
    - [x] Test batch progress tracking
  - [x] Create `tests/unit/application/test_load_shedding_service.py`
    - [x] Test load evaluation
    - [x] Test constitutional event protection (CRITICAL)
  - [x] Create `tests/unit/application/test_pattern_violation_service.py`
    - [x] Test EventType enum validation
    - [x] Test ContentRef validation
    - [x] Test HaltGuard injection validation

- [x] **Task 11: Integration Tests** (AC: 1, 2, 3, 4, 5)
  - [x] Create `tests/integration/test_failure_prevention_integration.py`
    - [x] Test end-to-end failure mode monitoring
    - [x] Test early warning flow
    - [x] Test query performance tracking
    - [x] Test load shedding decisions
    - [x] Test pattern violation detection

## Dev Notes

### Relevant Architecture Patterns and Constraints

**Pre-mortem Validation Summary (VAL-* Failure Modes):**
From architecture.md, these are the critical failure modes identified:

| ID | Failure Prevented | Prevention Measure | ADR | Owner |
|----|-------------------|-------------------|-----|-------|
| **VAL-1** | Silent signature corruption | Verify before DB write | ADR-1, ADR-4 | Dev |
| **VAL-2** | Ceremony timeout limbo | Timeout enforcement + auto-abort | ADR-6 | Ceremony Team |
| **VAL-3** | Import boundary bypass | Pre-commit hook + bypass detection | Structure | Ops |
| **VAL-4** | Halt storm via restarts | Aggregate rate limiting | ADR-3 | Platform |
| **VAL-5** | Observer verification staleness | Freshness health dimension | ADR-8 | Ops |

**Pattern Violation Risk Matrix (PV-* Violations):**
| ID | Violation | Failure Mode | Severity | Prevention |
|----|-----------|--------------|----------|------------|
| **PV-001** | Raw string event type | Orphan events | High | EventType enum + mypy |
| **PV-002** | Plain string hash | Invalid refs | Critical | ContentRef validation |
| **PV-003** | Missing HaltGuard | Operations during halt | Critical | Base class requirement |

**FR106 & FR107 Requirements:**
- FR106: Historical queries SHALL complete within 30 seconds for ranges up to 10,000 events; larger ranges batched with progress indication
- FR107: System SHALL NOT shed constitutional events under load; operational telemetry may be deprioritized but canonical events never dropped

**NFR43-NFR66 (Pre-mortem Operational Failures):**
Key NFRs to implement:
- NFR43: Under extreme load (>50× baseline), prioritize recent events over historical queries
- NFR44: Query queue depth bounded; beyond limit receive immediate backpressure
- NFR46-48: Time authority disagreement detection and handling
- NFR64-66: Config change alerting and review holds

### Source Tree Components to Touch

**Files to Create:**
```
src/domain/models/failure_mode.py
src/domain/models/pattern_violation.py
src/domain/models/batch_progress.py
src/domain/models/load_status.py
src/domain/errors/failure_prevention.py
src/domain/events/early_warning.py
src/application/ports/failure_mode_registry.py
src/application/services/failure_prevention_service.py
src/application/services/early_warning_service.py
src/application/services/query_performance_service.py
src/application/services/load_shedding_service.py
src/application/services/pattern_violation_service.py
src/infrastructure/stubs/failure_mode_registry_stub.py
src/api/routes/failure_prevention.py
src/api/models/failure_prevention.py
tests/unit/application/test_failure_prevention_service.py
tests/unit/application/test_early_warning_service.py
tests/unit/application/test_query_performance_service.py
tests/unit/application/test_load_shedding_service.py
tests/unit/application/test_pattern_violation_service.py
tests/integration/test_failure_prevention_integration.py
```

**Files to Modify:**
```
src/domain/models/__init__.py          # Export new models
src/domain/errors/__init__.py          # Export new errors
src/domain/events/__init__.py          # Export EarlyWarningEvent
src/application/ports/__init__.py      # Export new port
src/application/services/__init__.py   # Export new services
src/api/routes/__init__.py             # Register failure_prevention router
src/api/main.py                        # Include failure_prevention router
```

### Testing Standards Summary

- **Unit Tests Location**: `tests/unit/application/`
- **Integration Tests Location**: `tests/integration/`
- **Async Testing**: ALL tests use `pytest.mark.asyncio` and `async def test_*`
- **Coverage**: Focus on critical paths (constitutional event protection, early warning)

### Project Structure Notes

**Hexagonal Architecture Compliance:**
- Domain models in `domain/models/` (pure, no infrastructure)
- Ports in `application/ports/` (protocols)
- Services in `application/services/` (use cases)
- Stubs in `infrastructure/stubs/` (test implementations)
- API routes in `api/routes/`

**Import Rules:**
- `domain/` imports NOTHING from other layers
- `application/` imports from `domain/` only
- `infrastructure/` implements ports from `application/`
- `api/` depends on `application/` services

### Previous Story Intelligence (8-7: Structured Logging)

**Learnings from Story 8-7:**
1. **LoggingMixin pattern** - Use `_log_operation()` for all service operations
2. **Correlation ID** - Automatically propagated via context
3. **Service base** - `src/application/services/base.py` has `LoggingMixin`
4. **Router registration** - Must add to `__init__.py` AND `main.py`
5. **Structlog configuration** - Already configured in startup

**Key patterns established:**
```python
from src.application.services.base import LoggingMixin

class FailurePreventionService(LoggingMixin):
    def __init__(self, registry: FailureModeRegistryPort):
        self._registry = registry
        self._init_logger()

    async def check_failure_mode(self, mode_id: FailureModeId) -> FailureModeStatus:
        log = self._log_operation("check_failure_mode", mode_id=str(mode_id))
        # ... implementation
```

### Git Intelligence (Recent Commits)

```
686a37a feat(story-7.6): Implement cessation as final recorded event (FR24)
cdeb269 feat(story-3.6): Implement 48-hour recovery waiting period (FR21)
```

**Commit pattern for this story:**
```
feat(story-8.8): Implement pre-mortem operational failure prevention (FR106-FR107)
```

### Critical Implementation Notes

**CONSTITUTIONAL EVENT PROTECTION (FR107 - CRITICAL):**
```python
async def should_shed_telemetry(self) -> bool:
    """Determine if telemetry can be shed.

    CRITICAL: Constitutional events MUST NEVER be shed.
    This method only applies to operational telemetry.
    """
    # Only operational telemetry can be shed
    # Constitutional events bypass this check entirely
```

**Early Warning Alert Structure:**
```python
@dataclass
class EarlyWarningEvent(SignableContent):
    mode_id: FailureModeId
    current_value: float
    threshold: float
    threshold_type: str  # "warning" or "critical"
    recommended_action: str
    timestamp: datetime

    def signable_content(self) -> bytes:
        return f"{self.mode_id}:{self.current_value}:{self.threshold}".encode()
```

**Query Performance Compliance (FR106):**
```python
QUERY_SLA_THRESHOLD_EVENTS = 10_000
QUERY_SLA_TIMEOUT_SECONDS = 30

async def check_compliance(self, event_count: int, duration_seconds: float) -> bool:
    if event_count <= QUERY_SLA_THRESHOLD_EVENTS:
        return duration_seconds <= QUERY_SLA_TIMEOUT_SECONDS
    return True  # Larger ranges have extended SLA
```

### Dependencies

No new dependencies required. Uses existing:
- structlog (logging)
- pydantic (API models)
- FastAPI (routing)

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#VAL-1-to-VAL-5] - Pre-mortem validation
- [Source: _bmad-output/planning-artifacts/architecture.md#Pattern-Violation-Risk-Matrix] - PV-* violations
- [Source: _bmad-output/planning-artifacts/prd.md#FR106-FR107] - Scale realism requirements
- [Source: _bmad-output/planning-artifacts/prd.md#NFR43-66] - Pre-mortem operational failures
- [Source: _bmad-output/planning-artifacts/epics.md#Story-8.8] - Story definition
- [Source: _bmad-output/project-context.md] - Project rules

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None required - clean implementation.

### Completion Notes List

1. **All 11 tasks completed** - Full implementation of Story 8.8
2. **119 unit tests passing** - Comprehensive test coverage for all services
3. **31 integration tests passing** - End-to-end testing of all features
4. **FR106 compliance verified** - 30-second SLA for <10k events enforced
5. **FR107 compliance verified** - Constitutional events NEVER shed under any load
6. **All VAL-* and PV-* failure modes registered** - Pre-mortem analysis complete

### Test Count

- Unit tests: 119 (all passing)
- Integration tests: 31 (all passing)
- **Total: 150 tests**

### File List

**Domain Models (Created):**
- `src/domain/models/failure_mode.py`
- `src/domain/models/pattern_violation.py`
- `src/domain/models/batch_progress.py`
- `src/domain/models/load_status.py`
- `src/domain/errors/failure_prevention.py`
- `src/domain/events/early_warning.py`

**Application Layer (Created):**
- `src/application/ports/failure_mode_registry.py`
- `src/application/services/failure_prevention_service.py`
- `src/application/services/query_performance_service.py`
- `src/application/services/load_shedding_service.py`
- `src/application/services/pattern_violation_service.py`

**Infrastructure Layer (Created):**
- `src/infrastructure/stubs/failure_mode_registry_stub.py`

**API Layer (Created):**
- `src/api/routes/failure_prevention.py`
- `src/api/models/failure_prevention.py`

**Tests (Created):**
- `tests/unit/domain/test_failure_mode.py`
- `tests/unit/application/test_failure_prevention_service.py`
- `tests/unit/application/test_query_performance_service.py`
- `tests/unit/application/test_load_shedding_service.py`
- `tests/unit/application/test_pattern_violation_service.py`
- `tests/integration/test_failure_prevention_integration.py`

**Files Modified:**
- `src/domain/models/__init__.py`
- `src/domain/errors/__init__.py`
- `src/domain/events/__init__.py`
- `src/application/ports/__init__.py`
- `src/application/services/__init__.py`
- `src/infrastructure/stubs/__init__.py`
- `src/api/routes/__init__.py`
- `src/api/models/__init__.py`

