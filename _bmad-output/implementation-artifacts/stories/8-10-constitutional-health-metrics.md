# Story 8.10: Constitutional Health Metrics (ADR-10)

Status: dev-complete

## Story

As a **system operator**,
I want constitutional health metrics distinct from operational metrics,
So that I can assess constitutional integrity.

## Acceptance Criteria

### AC1: Constitutional Health Metrics Visibility
**Given** constitutional health metrics
**When** I query them
**Then** I see:
  - Breach count (unacknowledged in 90-day window)
  - Override rate (daily/weekly/monthly)
  - Dissent health (rolling average percentage)
  - Witness coverage (effective pool size)
**And** each metric includes its health threshold

### AC2: Constitutional Health Degradation Alerts
**Given** a constitutional health degradation
**When** thresholds are crossed:
  - Breach count > 8 (warning) or > 10 (critical per FR32)
  - Override rate > 3/day (incident threshold per Story 8.4)
  - Dissent health < 10% over 30 days (per NFR-023)
  - Witness coverage < 12 (degraded per FR117)
**Then** constitutional alert is raised (distinct from operational alert)
**And** alert routes to governance, not ops
**And** alert severity reflects urgency (WARNING vs CRITICAL)

### AC3: Constitutional vs Operational Health Distinction
**Given** the distinction
**When** operational metrics are green but constitutional metrics are red
**Then** both states are visible
**And** constitutional issues are not masked by operational health
**And** health endpoints clearly separate the two domains

### AC4: Constitutional Health as Blocking Gate (ADR-10)
**Given** constitutional health is a blocking gate
**When** constitutional health is red (any CRITICAL metric)
**Then** ceremonies are blocked from execution
**And** emergency override is required to proceed
**And** override creates auditable record per ADR-10

### AC5: Constitutional Health API Endpoint
**Given** the constitutional health endpoint
**When** I call `/api/v1/health/constitutional`
**Then** response includes all constitutional metrics
**And** response includes overall constitutional status (healthy/warning/unhealthy)
**And** response is distinct from `/health` (operational liveness)

## Tasks / Subtasks

- [x] **Task 1: Create Constitutional Health Models** (AC: 1, 3)
  - [x] Create `src/api/models/constitutional_health.py`
    - [x] `ConstitutionalMetric` model (name, value, threshold, status)
    - [x] `ConstitutionalHealthResponse` model (metrics dict, overall status)
    - [x] `ConstitutionalHealthStatus` enum (HEALTHY, WARNING, UNHEALTHY)
  - [x] Create `src/domain/models/constitutional_health.py`
    - [x] `ConstitutionalHealthSnapshot` domain model
    - [x] Threshold constants for each metric

- [x] **Task 2: Create Constitutional Health Port** (AC: 1, 2, 4)
  - [x] Create `src/application/ports/constitutional_health.py`
    - [x] `ConstitutionalHealthPort` protocol
    - [x] Methods: `get_breach_count()`, `get_override_rate()`, `get_dissent_health()`, `get_witness_coverage()`
    - [x] Method: `get_overall_status()` -> ConstitutionalHealthStatus
    - [x] Method: `is_blocking_ceremonies()` -> bool

- [x] **Task 3: Implement Constitutional Health Service** (AC: 1, 2, 3, 4)
  - [x] Create `src/application/services/constitutional_health_service.py`
    - [x] Inject existing ports: `BreachRepository`, `OverrideTrendRepository`, `DissentMetricsPort`, `WitnessPoolMonitor`
    - [x] HALT CHECK FIRST on all public methods (CT-11)
    - [x] `get_constitutional_health()` -> ConstitutionalHealthSnapshot
    - [x] `check_ceremony_allowed()` -> tuple[bool, Optional[str]]
    - [x] `get_blocking_metrics()` -> list[ConstitutionalMetric]
  - [x] Create `src/infrastructure/stubs/constitutional_health_stub.py` for testing

- [x] **Task 4: Create Constitutional Alert Events** (AC: 2)
  - [x] Create `src/domain/events/constitutional_health.py`
    - [x] `ConstitutionalHealthAlertEvent` payload
    - [x] Alert types: BREACH_WARNING, BREACH_CRITICAL, OVERRIDE_HIGH, DISSENT_LOW, WITNESS_DEGRADED
  - [x] Create `src/domain/errors/constitutional_health.py`
    - [x] `ConstitutionalHealthDegradedError`
    - [x] `CeremonyBlockedByConstitutionalHealthError`

- [x] **Task 5: Create Constitutional Health API Route** (AC: 5)
  - [x] Create `src/api/routes/constitutional_health.py`
    - [x] `GET /health/constitutional` endpoint
    - [x] Response model with all metrics and overall status
    - [x] Distinct from operational `/health` endpoint
  - [x] Update `src/api/routes/__init__.py` to include new router
  - [x] Update `src/api/main.py` to register router

- [x] **Task 6: Create Health Dashboard Separation** (AC: 3)
  - [x] Update `src/api/models/health.py`
    - [x] Add `health_type: Literal["operational"]` field
    - [x] Add `constitutional_health_url` field pointing to `/health/constitutional`
  - [x] Update `src/api/routes/health.py`
    - [x] Ensure `/health` only returns operational status
    - [x] Add docstring clarifying separation from constitutional health

- [x] **Task 7: Write Unit Tests** (AC: 1, 2, 3, 4, 5)
  - [x] Create `tests/unit/application/test_constitutional_health_service.py`
    - [x] Test each metric calculation (5 tests)
    - [x] Test threshold crossing detection (5 tests)
    - [x] Test ceremony blocking logic (4 tests)
    - [x] Test HALT CHECK FIRST pattern (5 tests)
    - [x] Test snapshot generation (5 tests)
    - [x] Total: 24 unit tests for service
  - [x] Create `tests/unit/api/test_constitutional_health_route.py`
    - [x] Test endpoint response structure (8 tests)
    - [x] Test ceremonies-allowed endpoint (3 tests)
    - [x] Total: 11 unit tests for API route
  - [x] Create `tests/unit/domain/test_constitutional_health.py`
    - [x] Total: 25 unit tests for domain models

- [x] **Task 8: Write Integration Tests** (AC: 1, 2, 3, 4, 5)
  - [x] Create `tests/integration/test_constitutional_health_integration.py`
    - [x] Test healthy/warning/unhealthy response structures (6 tests)
    - [x] Test ceremonies-allowed endpoint (4 tests)
    - [x] Test separation from operational health (3 tests)
    - [x] Test conservative aggregation (3 tests)
    - [x] Test blocking reasons (3 tests)
    - [x] Total: 19 integration tests

## Dev Notes

### Relevant Architecture Patterns and Constraints

**ADR-10 (Constitutional Health + Operational Governance):**
From `_bmad-output/planning-artifacts/architecture.md:731-773`:

> **Constitutional health is a blocking gate with witnessed emergency override.**
>
> **Health check integration:**
> * Constitutional health check runs before every ceremony
> * Unhealthy constitution blocks ceremony execution
> * Emergency override requires:
>   * Witnessed approval
>   * Recorded justification
>   * Automatic escalation to Tier 2 review
>
> **Constitutional health metrics:**
> * Chain integrity verified
> * All invariant monitors green
> * No unresolved P0 anomalies
> * Watchdog healthy
> * Key custody verified

**ADR-10 Gap Resolution (architecture.md:4952-4959):**
```
| Gap | Resolution |
|-----|------------|
| Health aggregation | System health = worst component health (conservative) |
| Auto-halt threshold | UNHEALTHY for > 5 minutes = automatic halt trigger |
| Delegation bootstrap | Initial delegation set defined in genesis config |
```

**Critical Implementation Note - Auto-Halt:**
If constitutional health is UNHEALTHY for > 5 minutes continuously, system should automatically halt (per ADR-10 gap resolution).

### Existing Services to Integrate

**Breach Count (Story 6.3):**
- `src/domain/models/breach_count_status.py`: `BreachCountStatus` with thresholds
- `CESSATION_THRESHOLD = 10`, `WARNING_THRESHOLD = 8`
- Use `BreachRepository` port to get unacknowledged breaches

**Override Rate (Story 5.5, 8.4):**
- `src/application/ports/override_trend_repository.py`: Get daily/weekly/monthly rates
- Incident threshold: >3 overrides/day triggers incident report

**Dissent Health (Story 2.4):**
- `src/application/services/dissent_health_service.py`: `DissentHealthService`
- `DEFAULT_DISSENT_THRESHOLD = 10.0`, `DEFAULT_PERIOD_DAYS = 30`
- Use `DissentMetricsPort` for rolling average

**Witness Coverage (Story 6.6):**
- `src/application/services/witness_pool_monitoring_service.py`: `WitnessPoolMonitoringService`
- `MINIMUM_WITNESSES_STANDARD = 12` (degraded below this)
- Use `WitnessPoolMonitorProtocol` for effective pool size

### Source Tree Components to Touch

**Files to Create:**
```
src/api/models/constitutional_health.py
src/api/routes/constitutional_health.py
src/domain/models/constitutional_health.py
src/domain/events/constitutional_health.py
src/domain/errors/constitutional_health.py
src/application/ports/constitutional_health.py
src/application/services/constitutional_health_service.py
src/infrastructure/stubs/constitutional_health_stub.py
tests/unit/application/test_constitutional_health_service.py
tests/unit/api/test_constitutional_health_route.py
tests/integration/test_constitutional_health_integration.py
```

**Files to Modify:**
```
src/api/routes/__init__.py          # Register new router
src/api/models/__init__.py          # Export new models
src/domain/models/__init__.py       # Export new domain model
src/domain/events/__init__.py       # Export new event
src/domain/errors/__init__.py       # Export new errors
src/application/ports/__init__.py   # Export new port
src/application/services/__init__.py # Export new service
```

### Testing Standards Summary

**Coverage Requirements:**
- Minimum 80% coverage
- 100% coverage for constitutional health service (critical path)

**Async Testing:**
- ALL test files use `pytest.mark.asyncio`
- Use `AsyncMock` for async port methods

**Key Test Scenarios:**
1. All metrics healthy -> overall HEALTHY
2. One metric at WARNING -> overall WARNING
3. Any metric at CRITICAL -> overall UNHEALTHY
4. UNHEALTHY blocks ceremonies
5. Override can bypass blocking (with witnessed record)
6. Constitutional health independent of operational health

### Project Structure Notes

**Hexagonal Architecture Compliance:**
```
src/
├── domain/           # ConstitutionalHealthSnapshot, events, errors
├── application/      # ConstitutionalHealthService, port definition
├── infrastructure/   # Stub implementation
└── api/              # Routes, response models
```

**Import Rules:**
- `domain/` imports NOTHING from other layers
- `application/` imports from `domain/` only
- Service orchestrates existing ports, does NOT access infrastructure directly

### Previous Story Intelligence (8-9: Operational Runbooks)

**Learnings from Story 8-9:**
1. Constitutional vs Operational distinction clearly marked with icons:
   - 🔵 **OPERATIONAL** - Affects system performance/availability
   - 🔴 **CONSTITUTIONAL** - Affects governance/integrity guarantees
2. Severity levels defined:
   - CRITICAL: Page immediately, halt system
   - HIGH: Page immediately
   - MEDIUM: Alert on-call, 15 min response
   - LOW: Next business day
3. Runbook for Epic 8 monitoring exists at `docs/operations/runbooks/epic-8-monitoring.md`

**Apply This Pattern:**
Use 🔴 CONSTITUTIONAL marker in all constitutional health metrics and alerts.
Ensure alerts route to governance (not ops).

### Git Intelligence (Recent Commits)

```
686a37a feat(story-7.6): Implement cessation as final recorded event (FR24)
cdeb269 feat(story-3.6): Implement 48-hour recovery waiting period (FR21)
```

**Commit pattern for this story:**
```
feat(story-8.10): Implement constitutional health metrics (ADR-10)
```

### Critical Implementation Notes

**HALT CHECK FIRST Pattern (Golden Rule #1):**
```python
async def get_constitutional_health(self) -> ConstitutionalHealthSnapshot:
    # HALT FIRST (Golden Rule #1)
    if await self._halt_checker.is_halted():
        raise SystemHaltedError("System halted")

    # Then proceed with health check
    ...
```

**Health Aggregation (ADR-10 Resolution):**
```python
# System health = worst component health (conservative)
def calculate_overall_status(metrics: list[ConstitutionalMetric]) -> ConstitutionalHealthStatus:
    statuses = [m.status for m in metrics]
    if ConstitutionalHealthStatus.UNHEALTHY in statuses:
        return ConstitutionalHealthStatus.UNHEALTHY
    if ConstitutionalHealthStatus.WARNING in statuses:
        return ConstitutionalHealthStatus.WARNING
    return ConstitutionalHealthStatus.HEALTHY
```

**Constitutional Health Response Structure:**
```python
class ConstitutionalHealthResponse(BaseModel):
    """Response model for constitutional health endpoint."""

    status: ConstitutionalHealthStatus
    metrics: dict[str, ConstitutionalMetric]
    ceremonies_blocked: bool
    blocking_reasons: list[str]
    checked_at: datetime
```

**Threshold Constants (from existing code):**
```python
# Breach count (Story 6.3)
BREACH_WARNING_THRESHOLD = 8
BREACH_CRITICAL_THRESHOLD = 10

# Override rate (Story 8.4)
OVERRIDE_INCIDENT_THRESHOLD = 3  # per day

# Dissent health (Story 2.4)
DISSENT_WARNING_THRESHOLD = 10.0  # percentage

# Witness coverage (Story 6.6)
WITNESS_DEGRADED_THRESHOLD = 12  # minimum pool size
```

### Dependencies

**Required Ports (inject via constructor):**
- `HaltChecker` - HALT CHECK FIRST pattern
- `BreachRepository` - Breach count metrics
- `OverrideTrendRepository` - Override rate metrics
- `DissentMetricsPort` - Dissent health metrics
- `WitnessPoolMonitorProtocol` - Witness coverage metrics

**All ports already exist** - this story integrates existing constitutional metrics into a unified health view.

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-010] - Constitutional Health + Operational Governance
- [Source: _bmad-output/planning-artifacts/epics.md#Story-8.10] - Story definition
- [Source: src/domain/models/breach_count_status.py] - Breach threshold constants
- [Source: src/application/services/dissent_health_service.py] - Dissent health service
- [Source: src/application/services/witness_pool_monitoring_service.py] - Witness coverage
- [Source: src/application/services/health_service.py] - Operational health pattern
- [Source: _bmad-output/project-context.md] - Project coding standards
- [Source: docs/operations/runbooks/epic-8-monitoring.md] - Operational monitoring runbook

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Fixed `ConstitutionalConstraintError` -> `ConstitutionalViolationError` in errors base class
- Fixed service mock method names to match actual port method signatures
- Fixed `ConstitutionalHealthSnapshot` constructor to take raw values not metric objects
- Fixed API route to use `calculated_at` instead of `checked_at` for timestamp
- Fixed test assertions to use `checked_at` (API model field name)

### Completion Notes List

1. **All 79 tests passing**: 25 domain + 24 service + 11 API route + 19 integration
2. **ADR-10 compliant**: Constitutional health is a blocking gate for ceremonies
3. **CT-11 compliant**: HALT CHECK FIRST pattern implemented in service
4. **Conservative aggregation**: System health = worst component health
5. **Clear separation**: Constitutional health endpoint distinct from operational /health
6. **Four constitutional metrics tracked**:
   - breach_count: Unacknowledged breaches (warning: 8, critical: >10)
   - override_rate: Daily keeper overrides (incident: >3)
   - dissent_health: Rolling average dissent percentage (warning: <10%)
   - witness_coverage: Effective witness pool size (degraded: <12)

### File List

**Created:**
- `src/domain/models/constitutional_health.py` - Domain model with thresholds
- `src/domain/events/constitutional_health.py` - Alert event payloads
- `src/domain/errors/constitutional_health.py` - Constitutional health errors
- `src/api/models/constitutional_health.py` - API response models
- `src/api/routes/constitutional_health.py` - /health/constitutional endpoint
- `src/application/ports/constitutional_health.py` - Port definition
- `src/application/services/constitutional_health_service.py` - Service implementation
- `src/infrastructure/stubs/constitutional_health_stub.py` - Test stub
- `tests/unit/domain/test_constitutional_health.py` - 25 domain tests
- `tests/unit/application/test_constitutional_health_service.py` - 24 service tests
- `tests/unit/api/test_constitutional_health_route.py` - 11 API route tests
- `tests/integration/test_constitutional_health_integration.py` - 19 integration tests

**Modified:**
- `src/domain/errors/__init__.py` - Added constitutional health error exports
- `src/api/routes/__init__.py` - Registered constitutional health router
- `src/api/main.py` - Registered constitutional health router
- `src/api/models/health.py` - Added health_type and constitutional_health_url fields
- `src/api/routes/health.py` - Updated docstring for separation clarity

