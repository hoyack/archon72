# Story 8.2: Operational-Constitutional Separation (FR52)

Status: done

## Story

As a **system architect**,
I want operational metrics excluded from constitutional event store,
So that operational noise doesn't pollute the constitutional record.

## Acceptance Criteria

### AC1: Operational Metrics Excluded from Event Store
**Given** operational metrics (uptime, latency, error rates)
**When** they are collected and stored
**Then** they go to Prometheus/operational storage (NOT event store)
**And** no operational metrics appear in the constitutional event store
**And** the EventStorePort is never used for operational data

### AC2: Constitutional Integrity Assessment Independence
**Given** constitutional integrity assessment processes
**When** they perform their calculations
**Then** operational metrics are NOT used as inputs
**And** only constitutional events inform the assessment
**And** system uptime/latency has no bearing on constitutional health

### AC3: Event Store Purity Verification
**Given** the event store
**When** I query it with any filter combination
**Then** no uptime/latency/error events appear
**And** only constitutional events (deliberation, vote, witness, halt, etc.) are present
**And** event types are strictly constitutional categories

### AC4: Separation Validator Port
**Given** a new operation that writes data
**When** it attempts to write
**Then** a separation validator can classify it as operational or constitutional
**And** operational data is routed away from event store
**And** constitutional data flows through witnessing

## Tasks / Subtasks

- [x] **Task 1: Create Separation Validator Port** (AC: 4)
  - [x] Create `src/application/ports/separation_validator.py`
    - [x] Define `SeparationValidatorPort` protocol
    - [x] `classify_data(data_type: str) -> DataClassification` enum
    - [x] `is_constitutional(data_type: str) -> bool`
    - [x] `is_operational(data_type: str) -> bool`
    - [x] `get_allowed_event_types() -> set[str]` (constitutional only)
  - [x] Create `DataClassification` enum (CONSTITUTIONAL, OPERATIONAL, UNKNOWN)
  - [x] Export from `src/application/ports/__init__.py`

- [x] **Task 2: Create Separation Validator Stub** (AC: 4)
  - [x] Create `src/infrastructure/stubs/separation_validator_stub.py`
    - [x] Implement `SeparationValidatorPort`
    - [x] Hardcode constitutional event types from existing codebase
    - [x] Hardcode operational data types (uptime, latency, error_rate, request_count)
    - [x] Return OPERATIONAL for any metric-related types
    - [x] Return CONSTITUTIONAL for event types
  - [x] Export from `src/infrastructure/stubs/__init__.py`

- [x] **Task 3: Create Separation Enforcement Service** (AC: 1,2,3,4)
  - [x] Create `src/application/services/separation_enforcement_service.py`
    - [x] `SeparationEnforcementService` class
    - [x] `validate_write_target(data_type: str, target: WriteTarget) -> ValidationResult`
    - [x] `assert_not_event_store(data_type: str)` raises if operational → event store
    - [x] `get_constitutional_event_types() -> set[str]`
    - [x] `get_operational_metric_types() -> set[str]`
  - [x] Define `WriteTarget` enum (EVENT_STORE, PROMETHEUS, OPERATIONAL_DB)
  - [x] Define `ValidationResult` dataclass (valid: bool, reason: str)
  - [x] Export from `src/application/services/__init__.py`

- [x] **Task 4: Create Separation Violation Domain Errors** (AC: 1,3)
  - [x] Create `src/domain/errors/separation.py`
    - [x] `SeparationViolationError(ConstitutionalViolationError)` - base
    - [x] `OperationalToEventStoreError` - operational data routed to event store
    - [x] `ConstitutionalToOperationalError` - constitutional routed to ops
    - [x] Include violation details (data_type, intended_target, correct_target)
  - [x] Export from `src/domain/errors/__init__.py`

- [x] **Task 5: Add Event Type Registry** (AC: 3)
  - [x] Create `src/domain/models/event_type_registry.py`
    - [x] `EventTypeRegistry` class with class constants
    - [x] `CONSTITUTIONAL_TYPES: frozenset[str]` - all valid event types
    - [x] `OPERATIONAL_TYPES: frozenset[str]` - explicitly forbidden in event store
    - [x] `is_valid_constitutional_type(event_type: str) -> bool`
    - [x] Gather all existing event types from `src/domain/events/`
  - [x] Export from `src/domain/models/__init__.py`

- [x] **Task 6: Add Event Store Type Validation** (AC: 1,3)
  - [x] Update `src/application/ports/event_store.py`
    - [x] Add docstring noting FR52 separation requirement
    - [x] Document that only constitutional event types are allowed
  - [x] Update `src/infrastructure/stubs/event_store_stub.py`
    - [x] Add validation in `append_event()` to reject operational types
    - [x] Raise `OperationalToEventStoreError` if operational type detected
    - [x] Reference `EventTypeRegistry` for validation

- [x] **Task 7: Unit Tests** (AC: 1,2,3,4)
  - [x] Create `tests/unit/application/test_separation_validator_port.py`
    - [x] Test port protocol definition
    - [x] Test classification enum
  - [x] Create `tests/unit/infrastructure/test_separation_validator_stub.py`
    - [x] Test classify_data for constitutional types
    - [x] Test classify_data for operational types
    - [x] Test is_constitutional/is_operational helpers
    - [x] Test get_allowed_event_types returns only constitutional
  - [x] Create `tests/unit/application/test_separation_enforcement_service.py`
    - [x] Test validate_write_target allows constitutional → event store
    - [x] Test validate_write_target blocks operational → event store
    - [x] Test assert_not_event_store raises for operational types
  - [x] Create `tests/unit/domain/test_separation_errors.py`
    - [x] Test OperationalToEventStoreError creation
    - [x] Test error message formatting
  - [x] Create `tests/unit/domain/test_event_type_registry.py`
    - [x] Test CONSTITUTIONAL_TYPES contains all expected types
    - [x] Test OPERATIONAL_TYPES contains metric types
    - [x] Test is_valid_constitutional_type

- [x] **Task 8: Integration Tests** (AC: 1,2,3)
  - [x] Create `tests/integration/test_separation_enforcement_integration.py`
    - [x] Test event store rejects operational metric event types
    - [x] Test metrics endpoint contains no constitutional data
    - [x] Test existing constitutional events still write successfully
    - [x] Test operational metrics go to Prometheus registry only
    - [x] Test full separation flow: metrics → Prometheus, events → event store

## Dev Notes

### Relevant Architecture Patterns and Constraints

**FR52 (Operational-Constitutional Separation) CRITICAL:**
- Operational metrics (uptime, latency, errors) NEVER enter event store
- Constitutional events (votes, deliberations, halts) NEVER go to ops storage
- This is a HARD separation - not a preference, a constitutional constraint
- Event store is for WITNESSED, CONSTITUTIONAL events ONLY

**Why This Matters (Constitutional Truths):**
- CT-12: Witnessing creates accountability - operational noise would dilute this
- CT-11: Silent failure destroys legitimacy - mixing data creates confusion
- CT-13: Integrity outranks availability - constitutional record must be pure

**Relationship to Story 8.1:**
- Story 8.1 created Prometheus metrics infrastructure with FR52 compliance
- Story 8.2 adds the ENFORCEMENT layer - validators that prevent violations
- Together they ensure separation is not just followed but enforced

**Developer Golden Rules:**
1. **NEVER** write uptime/latency/error data to EventStorePort
2. **NEVER** use MetricsCollector for constitutional events
3. **ALWAYS** classify data before choosing storage target
4. **ALWAYS** raise errors loudly if separation is violated

### Source Tree Components to Touch

**Files to Create:**
```
src/application/ports/separation_validator.py          # Port definition
src/infrastructure/stubs/separation_validator_stub.py  # Stub implementation
src/application/services/separation_enforcement_service.py  # Enforcement service
src/domain/errors/separation.py                        # Domain errors
src/domain/models/event_type_registry.py              # Event type constants
tests/unit/application/test_separation_validator_port.py
tests/unit/infrastructure/test_separation_validator_stub.py
tests/unit/application/test_separation_enforcement_service.py
tests/unit/domain/test_separation_errors.py
tests/unit/domain/test_event_type_registry.py
tests/integration/test_separation_enforcement_integration.py
```

**Files to Modify:**
```
src/application/ports/__init__.py                      # Export port
src/infrastructure/stubs/__init__.py                   # Export stub
src/application/services/__init__.py                   # Export service
src/domain/errors/__init__.py                          # Export errors
src/domain/models/__init__.py                          # Export registry
src/application/ports/event_store.py                   # Add FR52 docs
src/infrastructure/stubs/event_store_stub.py           # Add type validation
```

### Related Existing Code (MUST Review)

**Story 8.1 Implementation (Reference):**
- `src/infrastructure/monitoring/metrics.py:1-269` - MetricsCollector, already FR52 compliant
- `src/api/middleware/metrics_middleware.py` - Request instrumentation to Prometheus

**Event Store Port (Must Not Pollute):**
- `src/application/ports/event_store.py:1-623` - EventStorePort, append-only, witnessed
- Constitutional constraints: FR102 (append-only), FR1 (witnessed), CT-12

**Existing Event Types (Reference for Registry):**
- `src/domain/events/*.py` - All constitutional event types
- Key types: DeliberationEvent, VoteEvent, HaltEvent, WitnessEvent, etc.

**Domain Errors Pattern:**
- `src/domain/errors/__init__.py` - Base ConstitutionalViolationError
- All separation errors should inherit from ConstitutionalViolationError

### Design Decisions

**Why Separation Validator Port:**
```python
# Port enables testing with mocks and future implementation flexibility
class SeparationValidatorPort(Protocol):
    async def classify_data(self, data_type: str) -> DataClassification:
        """Classify data as CONSTITUTIONAL or OPERATIONAL."""
        ...
```

**Why Event Type Registry:**
```python
# Centralized source of truth for allowed event types
class EventTypeRegistry:
    # Constitutional events (ONLY these in event store)
    CONSTITUTIONAL_TYPES: frozenset[str] = frozenset({
        "deliberation_started",
        "deliberation_completed",
        "vote_cast",
        "vote_tallied",
        "halt_triggered",
        "halt_cleared",
        # ... all types from domain/events/
    })

    # Operational types (NEVER in event store)
    OPERATIONAL_TYPES: frozenset[str] = frozenset({
        "uptime_recorded",
        "latency_measured",
        "error_logged",
        "request_counted",
    })
```

**Error Hierarchy:**
```python
ConstitutionalViolationError
└── SeparationViolationError
    ├── OperationalToEventStoreError  # Operational → event store
    └── ConstitutionalToOperationalError  # Constitutional → ops
```

**Write Target Classification:**
```python
class WriteTarget(Enum):
    EVENT_STORE = "event_store"       # Constitutional only
    PROMETHEUS = "prometheus"         # Operational metrics
    OPERATIONAL_DB = "operational_db"  # Operational logs/state
```

### Testing Standards Summary

- **Unit Tests Location**: `tests/unit/application/`, `tests/unit/domain/`, `tests/unit/infrastructure/`
- **Integration Tests Location**: `tests/integration/`
- **Async Testing**: ALL tests use `pytest.mark.asyncio` and `async def test_*`
- **Mocking**: Mock EventStoreStub to verify rejection behavior
- **Coverage**: All classification paths, all error types, all validation scenarios

### Project Structure Notes

**Hexagonal Architecture Compliance:**
- Port: `src/application/ports/separation_validator.py`
- Stub: `src/infrastructure/stubs/separation_validator_stub.py`
- Service: `src/application/services/separation_enforcement_service.py`
- Domain errors: `src/domain/errors/separation.py`
- Domain models: `src/domain/models/event_type_registry.py`

**Import Rules:**
- Domain models/errors: No external imports
- Ports: Import from domain only
- Services: Import ports and domain
- Stubs: Implement ports, may import domain

### Previous Story Intelligence (8-1)

**Learnings from Story 8-1:**
1. **FR52 compliance pattern** - MetricsCollector already excludes constitutional metrics
2. **Stub defaults work well** - HealthService uses stubs by default (intentional)
3. **Registry pattern** - Singleton with thread-safe initialization
4. **Test organization** - Unit tests per module, integration tests per feature

**Key code established:**
- `MetricsCollector` singleton pattern - reuse for enforcement service
- `prometheus_client` for metrics storage - never event store
- Test patterns: 15+ unit tests per module, 15+ integration tests per feature

### Git Intelligence (Recent Commits)

```
686a37a feat(story-7.6): Implement cessation as final recorded event (FR24)
cdeb269 feat(story-3.6): Implement 48-hour recovery waiting period (FR21)
```

**Commit patterns:**
- Feature commits use `feat(story-X.Y):` prefix
- Include FR reference in commit message
- Co-Authored-By footer for AI assistance

### Edge Cases to Test

1. **Unknown data type**: Should return UNKNOWN classification, not crash
2. **Empty event type**: Should raise validation error
3. **Mixed writes**: Ensure one type doesn't leak to wrong storage
4. **Concurrent writes**: Thread-safe separation enforcement
5. **Event store stub validation**: Rejects operational types at boundary
6. **Registry completeness**: All existing event types included
7. **New event type addition**: Easy to add to registry

### Environment Variables

None required for this story - separation is code-enforced, not config-driven.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-8.2] - Story requirements
- [Source: _bmad-output/planning-artifacts/architecture.md#FR52] - Separation requirements
- [Source: src/infrastructure/monitoring/metrics.py] - Existing operational metrics (8.1)
- [Source: src/application/ports/event_store.py] - Event store port (must not pollute)
- [Source: src/domain/events/] - All constitutional event types
- [Source: _bmad-output/project-context.md] - Project rules

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

## Change Log

- 2026-01-08: Story created via create-story workflow with comprehensive context
