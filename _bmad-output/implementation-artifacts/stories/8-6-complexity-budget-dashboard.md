# Story 8.6: Complexity Budget Dashboard (SC-3, RT-6)

Status: done

## Story

As a **system operator**,
I want a complexity budget dashboard tracking CT-14 limits,
So that I can prevent complexity creep.

## Acceptance Criteria

### AC1: Complexity Metrics Display
**Given** the dashboard
**When** I access it
**Then** I see:
- ADR count (limit: ≤15)
- Ceremony type count (limit: ≤10)
- Cross-component dependency count (limit: ≤20)
**And** each metric shows current value and limit
**And** percentage utilization is displayed

### AC2: Complexity Budget Breach Alert
**Given** any complexity budget is exceeded
**When** limit is crossed
**Then** alert is raised
**And** a `ComplexityBudgetBreachEvent` is created (RT-6 hardening)
**And** event is witnessed (CT-12)

### AC3: Governance Ceremony Required (RT-6)
**Given** complexity budget breach (RT-6)
**When** it occurs
**Then** governance ceremony is required to proceed
**And** system flags the breach as requiring approval
**And** breach cannot be silently ignored

### AC4: Automatic Escalation
**Given** complexity budget exceeded without approval
**When** no governance ceremony addresses the breach within escalation period
**Then** automatic escalation occurs
**And** escalation creates additional constitutional event
**And** escalation period is configurable (default: 7 days)

### AC5: Complexity Metrics API
**Given** the complexity budget system
**When** an operator queries for metrics
**Then** current values for all complexity dimensions are returned
**And** historical trends can be queried
**And** breach events can be listed

## Tasks / Subtasks

- [x] **Task 1: Create Complexity Budget Domain Model** (AC: 1,2,3)
  - [x] Create `src/domain/models/complexity_budget.py`
    - [x] `ComplexityDimension` enum: ADR_COUNT, CEREMONY_TYPES, CROSS_COMPONENT_DEPS
    - [x] `ComplexityBudget` dataclass with dimension, limit, current_value
    - [x] `ComplexityBudgetStatus` enum: WITHIN_BUDGET, WARNING, BREACHED
    - [x] `ComplexitySnapshot` dataclass with all dimensions and timestamp
  - [x] Export from `src/domain/models/__init__.py`

- [x] **Task 2: Create Complexity Budget Events** (AC: 2,3,4)
  - [x] Create `src/domain/events/complexity_budget.py`
    - [x] `COMPLEXITY_BUDGET_BREACHED_EVENT_TYPE = "complexity.budget.breached"`
    - [x] `COMPLEXITY_BUDGET_ESCALATED_EVENT_TYPE = "complexity.budget.escalated"`
    - [x] `ComplexityBudgetBreachedPayload` dataclass
    - [x] `ComplexityBudgetEscalatedPayload` dataclass
    - [x] Both payloads include `signable_content()` (CT-12)
  - [x] Export from `src/domain/events/__init__.py`

- [x] **Task 3: Create Complexity Budget Errors** (AC: 2,3)
  - [x] Create `src/domain/errors/complexity_budget.py`
    - [x] `ComplexityBudgetBreachedError` with dimension and values
    - [x] `ComplexityBudgetApprovalRequiredError` for RT-6 enforcement
    - [x] `ComplexityBudgetEscalationError` for unresolved breaches
  - [x] Export from `src/domain/errors/__init__.py`

- [x] **Task 4: Create Complexity Budget Calculator Port** (AC: 1,2)
  - [x] Create `src/application/ports/complexity_calculator.py`
    - [x] `ComplexityCalculatorPort` protocol
    - [x] `count_adrs() -> int`
    - [x] `count_ceremony_types() -> int`
    - [x] `count_cross_component_deps() -> int`
    - [x] `calculate_snapshot() -> ComplexitySnapshot`
  - [x] Export from `src/application/ports/__init__.py`

- [x] **Task 5: Create Complexity Budget Repository Port** (AC: 1,2,5)
  - [x] Create `src/application/ports/complexity_budget_repository.py`
    - [x] `ComplexityBudgetRepositoryPort` protocol
    - [x] `save_snapshot(snapshot: ComplexitySnapshot) -> None`
    - [x] `get_latest_snapshot() -> Optional[ComplexitySnapshot]`
    - [x] `get_snapshots_in_range(start: datetime, end: datetime) -> list[ComplexitySnapshot]`
    - [x] `get_breach_events() -> list[ComplexityBudgetBreachedPayload]`
  - [x] Export from `src/application/ports/__init__.py`

- [x] **Task 6: Create Complexity Budget Repository Stub** (AC: 1,2,5)
  - [x] Create `src/infrastructure/stubs/complexity_budget_repository_stub.py`
    - [x] Implement `ComplexityBudgetRepositoryPort`
    - [x] In-memory storage with list[ComplexitySnapshot]
    - [x] Support all query operations
  - [x] Export from `src/infrastructure/stubs/__init__.py`

- [x] **Task 7: Create Complexity Calculator Stub** (AC: 1,2)
  - [x] Create `src/infrastructure/stubs/complexity_calculator_stub.py`
    - [x] Implement `ComplexityCalculatorPort`
    - [x] Configurable return values for testing
    - [x] Default values within budget
  - [x] Export from `src/infrastructure/stubs/__init__.py`

- [x] **Task 8: Create Complexity Budget Service** (AC: 1,2,3,4)
  - [x] Create `src/application/services/complexity_budget_service.py`
    - [x] `ComplexityBudgetService` class
    - [x] `check_all_budgets() -> ComplexitySnapshot`
    - [x] `is_budget_breached(dimension: ComplexityDimension) -> bool`
    - [x] `get_budget_status() -> dict[ComplexityDimension, ComplexityBudgetStatus]`
    - [x] `record_breach(dimension: ComplexityDimension) -> ComplexityBudgetBreachedPayload`
    - [x] HALT CHECK FIRST before any write operation (CT-11)
    - [x] Write events on breach (CT-12)
  - [x] Export from `src/application/services/__init__.py`
  - [x] Constants:
    - [x] `ADR_LIMIT = 15`
    - [x] `CEREMONY_TYPE_LIMIT = 10`
    - [x] `CROSS_COMPONENT_DEP_LIMIT = 20`
    - [x] `WARNING_THRESHOLD_PERCENT = 80`

- [x] **Task 9: Create Complexity Budget Escalation Service** (AC: 4)
  - [x] Create `src/application/services/complexity_budget_escalation_service.py`
    - [x] `ComplexityBudgetEscalationService` class
    - [x] `check_pending_breaches() -> list[ComplexityBudgetBreachedPayload]`
    - [x] `escalate_breach(breach_id: UUID) -> ComplexityBudgetEscalatedPayload`
    - [x] `is_breach_resolved(breach_id: UUID) -> bool`
    - [x] `ESCALATION_PERIOD_DAYS = 7` constant
  - [x] Export from `src/application/services/__init__.py`

- [x] **Task 10: Create Complexity Budget API Models** (AC: 5)
  - [x] Create `src/api/models/complexity_budget.py`
    - [x] `ComplexityMetricResponse` Pydantic model
    - [x] `ComplexityDashboardResponse` Pydantic model
    - [x] `ComplexityBreachResponse` Pydantic model
    - [x] `ComplexityTrendResponse` Pydantic model
  - [x] Export from `src/api/models/__init__.py`

- [x] **Task 11: Create Complexity Budget API Routes** (AC: 5)
  - [x] Create `src/api/routes/complexity_budget.py`
    - [x] `GET /v1/complexity/dashboard` - Get current complexity dashboard
    - [x] `GET /v1/complexity/metrics` - Get all complexity metrics
    - [x] `GET /v1/complexity/breaches` - List complexity breaches
    - [x] `GET /v1/complexity/trends` - Get historical trends
  - [x] Add router to `src/api/routes/__init__.py`

- [x] **Task 12: Unit Tests** (AC: 1,2,3,4,5)
  - [x] Create `tests/unit/application/test_complexity_budget_service.py`
    - [x] Test budget checking (25 tests)
    - [x] Test breach detection
    - [x] Test halt check enforcement (CT-11)
    - [x] Test event creation on breach (CT-12)
  - [x] Create `tests/unit/application/test_complexity_budget_escalation_service.py`
    - [x] Test pending breach detection (25 tests)
    - [x] Test escalation logic (level 1 and 2)
    - [x] Test resolution checking

- [x] **Task 13: Integration Tests** (AC: 1,2,3,4,5)
  - [x] Create `tests/integration/test_complexity_budget_integration.py`
    - [x] Test full dashboard display (22 tests)
    - [x] Test breach event creation (CT-12 witnessed)
    - [x] Test escalation after period expires
    - [x] Test historical trend queries
    - [x] Test constitutional constraints (CT-11, CT-12, CT-14, RT-6, SC-3)

## Dev Notes

### Relevant Architecture Patterns and Constraints

**CT-14 (Complexity is a Failure Vector) - CRITICAL:**
- Complexity must be budgeted explicitly
- Exceeding limits requires governance ceremony
- Dashboard provides visibility into complexity growth
- This is OPERATIONAL monitoring, not constitutional enforcement

**SC-3 (Self-Consistency Finding):**
- Epic 8 was missing complexity budget dashboard
- This story addresses that gap
- Traceability to CT-14 required

**RT-6 (Red Team Hardening - Complexity Bomb):**
- Monitor without enforce was identified as attack vector
- Breach = constitutional event (not just alert)
- Exceeding limits requires governance ceremony to proceed
- Automatic escalation if limits exceeded without ceremony approval

**CT-11 (Silent Failure Destroys Legitimacy):**
- HALT CHECK FIRST before any write operation
- Never suppress errors in breach detection

**CT-12 (Witnessing Creates Accountability):**
- Breach events MUST be witnessed
- Escalation events MUST be witnessed
- All events include `signable_content()` for verification

### Source Tree Components to Touch

**Files to Create:**
```
src/domain/models/complexity_budget.py
src/domain/events/complexity_budget.py
src/domain/errors/complexity_budget.py
src/application/ports/complexity_calculator.py
src/application/ports/complexity_budget_repository.py
src/infrastructure/stubs/complexity_budget_repository_stub.py
src/infrastructure/stubs/complexity_calculator_stub.py
src/application/services/complexity_budget_service.py
src/application/services/complexity_budget_escalation_service.py
src/api/models/complexity_budget.py
src/api/routes/complexity_budget.py
tests/unit/domain/test_complexity_budget.py
tests/unit/domain/test_complexity_budget_events.py
tests/unit/domain/test_complexity_budget_errors.py
tests/unit/application/test_complexity_budget_service.py
tests/unit/application/test_complexity_budget_escalation_service.py
tests/integration/test_complexity_budget_integration.py
```

**Files to Modify:**
```
src/domain/models/__init__.py                    # Export models
src/domain/events/__init__.py                    # Export events
src/domain/errors/__init__.py                    # Export errors
src/application/ports/__init__.py                # Export ports
src/application/services/__init__.py             # Export services
src/infrastructure/stubs/__init__.py             # Export stubs
src/api/models/__init__.py                       # Export API models
src/api/routes/__init__.py                       # Add router
```

### Design Decisions

**Complexity Dimension Limits:**
```python
# From architecture.md and epics.md
ADR_LIMIT = 15                    # Architecture Decision Records
CEREMONY_TYPE_LIMIT = 10          # Types of governance ceremonies
CROSS_COMPONENT_DEP_LIMIT = 20    # Inter-component dependencies

# Warning threshold (percentage of limit)
WARNING_THRESHOLD_PERCENT = 80    # 80% = warning, 100% = breach
```

**Budget Status Calculation:**
```python
@dataclass(frozen=True)
class ComplexityBudget:
    dimension: ComplexityDimension
    limit: int
    current_value: int

    @property
    def status(self) -> ComplexityBudgetStatus:
        percentage = (self.current_value / self.limit) * 100
        if percentage >= 100:
            return ComplexityBudgetStatus.BREACHED
        elif percentage >= 80:
            return ComplexityBudgetStatus.WARNING
        return ComplexityBudgetStatus.WITHIN_BUDGET

    @property
    def utilization_percent(self) -> float:
        return (self.current_value / self.limit) * 100
```

**Breach Event Payload:**
```python
@dataclass(frozen=True)
class ComplexityBudgetBreachedPayload:
    breach_id: UUID
    dimension: ComplexityDimension
    limit: int
    actual_value: int
    breached_at: datetime
    requires_governance_ceremony: bool = True  # RT-6

    def signable_content(self) -> str:
        # Deterministic JSON for CT-12 witnessing
        return json.dumps({
            "breach_id": str(self.breach_id),
            "dimension": self.dimension.value,
            "limit": self.limit,
            "actual_value": self.actual_value,
            "breached_at": self.breached_at.isoformat(),
        }, sort_keys=True)
```

**Dashboard Response:**
```python
class ComplexityDashboardResponse(BaseModel):
    """Complexity budget dashboard response."""

    adr_count: int
    adr_limit: int = 15
    adr_utilization: float
    adr_status: str  # "within_budget", "warning", "breached"

    ceremony_types: int
    ceremony_type_limit: int = 10
    ceremony_type_utilization: float
    ceremony_type_status: str

    cross_component_deps: int
    cross_component_dep_limit: int = 20
    cross_component_dep_utilization: float
    cross_component_dep_status: str

    overall_status: str  # worst status of all dimensions
    active_breaches: int
    pending_escalations: int
    last_updated: datetime
```

### Testing Standards Summary

- **Unit Tests Location**: `tests/unit/domain/`, `tests/unit/application/`
- **Integration Tests Location**: `tests/integration/`
- **Async Testing**: ALL tests use `pytest.mark.asyncio` and `async def test_*`
- **Mocking**: Mock complexity calculator and repository ports
- **Coverage**: All dimensions, status calculations, breach/escalation flows

### Project Structure Notes

**Hexagonal Architecture Compliance:**
- Models: `src/domain/models/complexity_budget.py`
- Events: `src/domain/events/complexity_budget.py`
- Errors: `src/domain/errors/complexity_budget.py`
- Ports: `src/application/ports/complexity_calculator.py`, `complexity_budget_repository.py`
- Services: `src/application/services/complexity_budget_service.py`, `complexity_budget_escalation_service.py`
- Stubs: `src/infrastructure/stubs/complexity_*.py`
- API: `src/api/routes/complexity_budget.py`, `src/api/models/complexity_budget.py`

**Import Rules:**
- Domain imports nothing from other layers
- Service imports ports and domain
- Stubs implement ports
- API imports services

### Previous Story Intelligence (8-5)

**Learnings from Story 8-5 (Pre-Operational Verification):**
1. **Verification result pattern** - Status enum with helper properties works well
2. **Bypass logic** - Clear conditions for when exceptions allowed
3. **Event payloads** - Include `signable_content()` for CT-12 witnessing
4. **Stub pattern** - Configurable stubs with `with_dev_key` style parameters

### Git Intelligence (Recent Commits)

```
686a37a feat(story-7.6): Implement cessation as final recorded event (FR24)
cdeb269 feat(story-3.6): Implement 48-hour recovery waiting period (FR21)
```

**Commit patterns:**
- Feature commits use `feat(story-X.Y):` prefix
- Include relevant constraint references (CT-14, RT-6, SC-3)
- Co-Authored-By footer for AI assistance

### Edge Cases to Test

1. **All dimensions within budget**: Dashboard shows green status
2. **Single dimension warning**: 80%+ utilization triggers warning
3. **Single dimension breached**: 100%+ creates breach event
4. **Multiple dimensions breached**: All breaches tracked
5. **Breach with governance approval**: Breach resolved, no escalation
6. **Breach without approval**: Escalation after 7 days
7. **Breach resolved then re-breached**: New breach event created
8. **Concurrent breach detection**: Multiple services detecting same breach
9. **Calculator failure**: Graceful handling with error event
10. **Historical trend query**: Empty range returns empty list

### Complexity Calculator Implementation Notes

The `ComplexityCalculatorPort` stub should be configurable for testing. In a real implementation:

- **ADR Count**: Could scan `docs/architecture/adr/` for files or query a metadata store
- **Ceremony Types**: Could query ceremony registry or configuration
- **Cross-Component Deps**: Could analyze import graph or dependency manifest

For MVP, the stub returns configurable values. Real implementation is future work.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-8.6] - Story requirements
- [Source: _bmad-output/planning-artifacts/architecture.md#CT-14] - Complexity constraint
- [Source: _bmad-output/planning-artifacts/epics.md#RT-6] - Red Team hardening
- [Source: _bmad-output/planning-artifacts/epics.md#SC-3] - Self-consistency finding
- [Source: _bmad-output/project-context.md] - Project rules

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Fixed ComplexitySnapshot interface mismatch (used `get_budget()` instead of property access)
- Fixed HaltCheckerStub parameter (`force_halted` instead of `is_halted`)
- Fixed ComplexityBudgetEscalatedPayload missing `original_breach_at` field
- Fixed repository stub to use `timestamp` instead of `snapshot_timestamp`

### Completion Notes List

1. **Domain Model** - Created ComplexityBudget, ComplexitySnapshot, ComplexityDimension, ComplexityBudgetStatus
2. **Events** - Created ComplexityBudgetBreachedPayload, ComplexityBudgetEscalatedPayload with signable_content()
3. **Errors** - Created ComplexityBudgetBreachedError, ComplexityBudgetApprovalRequiredError, ComplexityBudgetEscalationError
4. **Ports** - Created ComplexityCalculatorPort, ComplexityBudgetRepositoryPort
5. **Stubs** - Created ComplexityCalculatorStub, ComplexityBudgetRepositoryStub
6. **Services** - Created ComplexityBudgetService, ComplexityBudgetEscalationService
7. **API** - Created Pydantic models and FastAPI routes
8. **Tests** - 187 passing tests (102 domain + 50 application + 13 API + 22 integration)

### File List

**Files Created:**
- `src/domain/models/complexity_budget.py`
- `src/domain/events/complexity_budget.py`
- `src/domain/errors/complexity_budget.py`
- `src/application/ports/complexity_calculator.py`
- `src/application/ports/complexity_budget_repository.py`
- `src/infrastructure/stubs/complexity_budget_repository_stub.py`
- `src/infrastructure/stubs/complexity_calculator_stub.py`
- `src/application/services/complexity_budget_service.py`
- `src/application/services/complexity_budget_escalation_service.py`
- `src/api/models/complexity_budget.py`
- `src/api/routes/complexity_budget.py`
- `tests/unit/domain/test_complexity_budget.py`
- `tests/unit/domain/test_complexity_budget_events.py`
- `tests/unit/domain/test_complexity_budget_errors.py`
- `tests/unit/application/test_complexity_budget_service.py`
- `tests/unit/application/test_complexity_budget_escalation_service.py`
- `tests/unit/api/test_complexity_budget_routes.py`
- `tests/integration/test_complexity_budget_integration.py`

**Files Modified:**
- `src/domain/models/__init__.py` (exports)
- `src/domain/events/__init__.py` (exports)
- `src/domain/errors/__init__.py` (exports)
- `src/application/ports/__init__.py` (exports)
- `src/application/services/__init__.py` (exports)
- `src/infrastructure/stubs/__init__.py` (exports)
- `src/api/models/__init__.py` (exports)
- `src/api/routes/__init__.py` (router registration)

### Test Results

```
============================== 187 passed ==============================

Domain Unit Tests (102):
- test_complexity_budget.py: 36 passed
- test_complexity_budget_events.py: 38 passed
- test_complexity_budget_errors.py: 28 passed

Application Unit Tests (50):
- test_complexity_budget_service.py: 25 passed
- test_complexity_budget_escalation_service.py: 25 passed

API Unit Tests (13):
- test_complexity_budget_routes.py: 13 passed

Integration Tests (22):
- test_complexity_budget_integration.py: 22 passed

Coverage:
- AC1: Three-dimension tracking ✓
- AC2: Status thresholds (within_budget/warning/breached) ✓
- AC3: Breach = constitutional event requiring governance ✓
- AC4: Automatic escalation after 7/14 days ✓
- AC5: Dashboard data and historical trends ✓
- CT-11: Halt check first enforcement ✓
- CT-12: Breach events witnessed ✓
- CT-14: Complexity budgeting active ✓
- RT-6: Governance ceremony required for breaches ✓
- SC-3: Dashboard available ✓
```

## Change Log

- 2026-01-08: Story created via workflow-status command with comprehensive context
- 2026-01-08: Implementation completed - all 13 tasks done, 72 tests passing
- 2026-01-09: Code review fixes - Fixed broken get_metrics endpoint, added 13 API route unit tests
