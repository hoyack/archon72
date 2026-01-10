# Story 7.7: Public Cessation Trigger Conditions

Status: done

## Story

As an **external observer**,
I want public documentation of cessation trigger conditions,
so that I understand what causes cessation.

## Acceptance Criteria

### AC1: Public Endpoint for Trigger Conditions (FR134)
**Given** the public API
**When** I request cessation trigger conditions (`GET /api/v1/observer/cessation-triggers`)
**Then** all cessation trigger conditions are listed in JSON format
**And** the endpoint is unauthenticated (public read access per FR42)
**And** response includes `last_updated` timestamp

### AC2: Complete Trigger Condition Documentation (FR134)
**Given** the trigger conditions response
**When** I examine its contents
**Then** it includes ALL automatic trigger types:
  - **FR37**: 3 consecutive integrity failures in 30 days
  - **RT-4**: 5 non-consecutive failures in 90-day rolling window
  - **FR38**: Anti-success alert sustained 90 days
  - **FR39**: External observer petition with 100+ co-signers
  - **FR32**: >10 unacknowledged breaches in 90-day window
**And** each trigger includes: `trigger_type`, `threshold`, `window_days`, `description`, `fr_reference`

### AC3: Threshold Values from Constitutional Registry (FR134, FR33)
**Given** the trigger conditions endpoint
**When** I query current thresholds
**Then** values are sourced from `CONSTITUTIONAL_THRESHOLD_REGISTRY`
**And** no hardcoded values are used in response generation
**And** constitutional floors are included for each threshold

### AC4: Trigger Condition Change Event (FR134)
**Given** a cessation trigger condition changes (threshold update)
**When** the change is made via constitutional process
**Then** a `TriggerConditionChangedEvent` is created
**And** the event includes: `old_value`, `new_value`, `changed_by`, `change_reason`
**And** documentation endpoint reflects new values immediately

### AC5: Machine-Readable Format (FR134)
**Given** the documentation endpoint
**When** I request with `Accept: application/json`
**Then** response is valid JSON schema
**And** includes JSON-LD context for semantic interoperability
**And** can be consumed by verification toolkit (Story 4.4)

### AC6: Version Tracking (FR134)
**Given** the trigger conditions response
**When** I examine version metadata
**Then** it includes `schema_version` for API compatibility
**And** includes `constitution_version` for rule version tracking
**And** includes `effective_date` for when current rules took effect

### AC7: Integration with Observer API (FR134, FR42)
**Given** the existing observer API routes
**When** cessation triggers endpoint is accessed
**Then** it follows same patterns as other observer endpoints
**And** includes `CeasedResponseMiddleware` integration (returns cessation state in headers)
**And** continues to work after cessation (read-only access preserved)

## Tasks / Subtasks

- [x] **Task 1: Create trigger conditions domain model** (AC: 2,3,5)
  - [x] Create `src/domain/models/cessation_trigger_condition.py`
  - [x] Define `CessationTriggerCondition` dataclass with all required fields
  - [x] Define `CessationTriggerConditionSet` to hold all conditions
  - [x] Include `to_dict()` and JSON-LD context generation methods
  - [x] Link to `CONSTITUTIONAL_THRESHOLD_REGISTRY` for threshold values

- [x] **Task 2: Create trigger condition changed event** (AC: 4)
  - [x] Create `src/domain/events/trigger_condition_changed.py`
  - [x] Define `TriggerConditionChangedEventPayload` dataclass
  - [x] Include `old_value`, `new_value`, `changed_by`, `change_reason`
  - [x] Implement `signable_content()` for witnessing (CT-12)
  - [x] Define `TRIGGER_CONDITION_CHANGED_EVENT_TYPE` constant

- [x] **Task 3: Create public triggers service** (AC: 1,2,3,6)
  - [x] Create `src/application/services/public_triggers_service.py`
  - [x] Implement `get_trigger_conditions()` returning all conditions
  - [x] Source all thresholds from `CONSTITUTIONAL_THRESHOLD_REGISTRY`
  - [x] Include version metadata (schema, constitution, effective_date)
  - [x] Add caching with invalidation on threshold changes

- [x] **Task 4: Create API endpoint** (AC: 1,5,7)
  - [x] Add `GET /api/v1/observer/cessation-triggers` to observer routes
  - [x] Create Pydantic response models in `src/api/models/observer.py`
  - [x] Integrate with `CeasedResponseMiddleware` (via existing observer routes)
  - [x] Ensure no authentication required (public read)
  - [x] Return JSON-LD context for semantic interoperability

- [x] **Task 5: Write unit tests** (AC: all)
  - [x] `tests/unit/domain/test_cessation_trigger_condition.py`
  - [x] `tests/unit/domain/test_trigger_condition_changed_event.py`
  - [x] `tests/unit/application/test_public_triggers_service.py`
  - [x] `tests/unit/api/test_cessation_triggers_endpoint.py`
  - [x] Test threshold sourcing from registry
  - [x] Test JSON-LD context generation

- [x] **Task 6: Write integration tests** (AC: all)
  - [x] `tests/integration/test_public_cessation_triggers_integration.py`
  - [x] Test complete endpoint request/response cycle
  - [x] Test version metadata accuracy
  - [x] Test response after cessation (read-only still works)
  - [x] Test threshold change event creation

## Dev Notes

### Relevant Architecture Patterns and Constraints

**Constitutional Constraints:**
- **FR134**: Public documentation of cessation trigger conditions
- **FR33**: Threshold definitions SHALL be constitutional, not operational
- **FR42**: Read-only access indefinitely after cessation
- **CT-11**: Silent failure destroys legitimacy -> All conditions must be visible
- **CT-12**: Witnessing creates accountability -> Changes must be witnessed

**Developer Golden Rules:**
1. **REGISTRY SOURCE OF TRUTH** - All thresholds from `CONSTITUTIONAL_THRESHOLD_REGISTRY`
2. **PUBLIC READ** - No authentication required for trigger conditions
3. **WITNESS CHANGES** - Any threshold change must create witnessed event
4. **VERSION TRACKING** - Include schema and constitution versions
5. **READ-ONLY SURVIVES** - Endpoint must work after cessation

### Source Tree Components to Touch

**Files to Create:**
```
src/domain/models/cessation_trigger_condition.py    # Domain model
src/domain/events/trigger_condition_changed.py      # Change event
src/application/services/public_triggers_service.py # Service
src/api/models/cessation_triggers.py                # API models
tests/unit/domain/test_cessation_trigger_condition.py
tests/unit/domain/test_trigger_condition_changed_event.py
tests/unit/application/test_public_triggers_service.py
tests/unit/api/test_cessation_triggers_endpoint.py
tests/integration/test_public_cessation_triggers_integration.py
```

**Files to Modify:**
```
src/api/routes/observer.py                          # Add new endpoint
src/domain/events/__init__.py                       # Export new event
src/domain/models/__init__.py                       # Export new model
src/application/services/__init__.py                # Export new service
```

### Related Existing Code (MUST Review)

**Story 6.4 Constitutional Thresholds (Build on this):**
- `src/domain/primitives/constitutional_thresholds.py` - The registry!
  - `CONSTITUTIONAL_THRESHOLD_REGISTRY` - Contains all thresholds
  - `CESSATION_BREACH_THRESHOLD` - FR32 cessation at >10 breaches
  - `CESSATION_WINDOW_DAYS_THRESHOLD` - 90-day window
  - `ESCALATION_DAYS_THRESHOLD` - 7-day escalation
- `src/domain/models/constitutional_threshold.py` - Threshold model
  - `ConstitutionalThreshold` dataclass with floor enforcement
  - `ConstitutionalThresholdRegistry` for validation

**Story 7.1 Automatic Agenda Placement (Has trigger types):**
- `src/domain/events/cessation_agenda.py` - Event payloads
  - `AgendaTriggerType` enum: CONSECUTIVE_FAILURES, ROLLING_WINDOW, ANTI_SUCCESS_SUSTAINED
  - `CessationAgendaPlacementEventPayload` - Event structure
- `src/application/services/automatic_agenda_placement_service.py`
  - Constants: `CONSECUTIVE_FAILURE_THRESHOLD`, `ROLLING_WINDOW_THRESHOLD`, etc.
  - **WARNING**: These are hardcoded, should reference registry instead

**Story 7.2 External Observer Petition:**
- `src/application/services/petition_service.py` - Petition handling
  - Threshold of 100 co-signers for cessation agenda placement
  - Should also be in constitutional registry

**Story 4.1-4.4 Observer API (Pattern to follow):**
- `src/api/routes/observer.py` - Observer endpoints
  - Pattern for unauthenticated read access
  - Pattern for CeasedResponseMiddleware integration
- `src/api/models/observer.py` - Observer response models

**Story 7.5 Read-Only After Cessation (Regression test):**
- `src/api/middleware/ceased_response.py` - Middleware to integrate with
- This endpoint MUST work after cessation

### Design Decisions

**Why Source from Registry (not duplicate constants):**
1. Single source of truth for constitutional values
2. Prevents drift between API and enforcement code
3. Registry validates floor constraints
4. Amendment process updates one location

**JSON-LD Context for Semantic Interoperability:**
```json
{
  "@context": {
    "cessation": "https://archon72.org/schema/cessation#",
    "threshold": "cessation:threshold",
    "trigger_type": "cessation:triggerType",
    "fr_reference": "cessation:functionalRequirement"
  }
}
```

**Trigger Conditions to Document:**

| Trigger Type | Threshold | Window | FR Reference | Description |
|--------------|-----------|--------|--------------|-------------|
| consecutive_failures | 3 | 30 days | FR37 | Consecutive integrity failures |
| rolling_window | 5 | 90 days | RT-4 | Non-consecutive failures (timing attack prevention) |
| anti_success_sustained | 90 days | N/A | FR38 | Anti-success alert sustained |
| petition_threshold | 100 | N/A | FR39 | External observer petition co-signers |
| breach_threshold | >10 | 90 days | FR32 | Unacknowledged breaches |

**Response Structure:**
```json
{
  "schema_version": "1.0.0",
  "constitution_version": "1.0.0",
  "effective_date": "2026-01-01T00:00:00Z",
  "last_updated": "2026-01-08T12:00:00Z",
  "@context": { ... },
  "trigger_conditions": [
    {
      "trigger_type": "consecutive_failures",
      "threshold": 3,
      "window_days": 30,
      "constitutional_floor": 3,
      "description": "3 consecutive integrity failures in 30 days triggers cessation agenda placement",
      "fr_reference": "FR37"
    },
    ...
  ]
}
```

### Testing Standards Summary

- **Async Testing**: ALL tests use `pytest.mark.asyncio` and `async def test_*`
- **Mocking**: Use `AsyncMock` for async dependencies
- **Coverage**: 80% minimum required
- **Unit Test Location**: `tests/unit/domain/`, `tests/unit/application/`, `tests/unit/api/`
- **Integration Test Location**: `tests/integration/`
- **API Testing**: Use `httpx.AsyncClient` with `app` fixture

### Project Structure Notes

**Hexagonal Architecture Compliance:**
- Domain models: Pure dataclasses, no infrastructure imports
- Ports: Protocol classes in `application/ports/`
- Services: In `application/services/`
- API routes: In `api/routes/`
- API models: Pydantic models in `api/models/`

**Import Rules:**
- `domain/` imports NOTHING from other layers
- `application/` imports from `domain/` only
- `api/` depends on `application/` services
- `infrastructure/` implements ports from `application/`

### Edge Cases to Test

1. **Empty registry**: Should return defaults (shouldn't happen, but test)
2. **Threshold at floor**: Verify floor value is correct
3. **After cessation**: Endpoint still works (FR42)
4. **Concurrent requests**: Should return consistent data
5. **Cache invalidation**: When threshold changes, cache updates
6. **Missing threshold**: Should log warning, not crash
7. **JSON-LD context**: Should be valid for semantic parsers

### Previous Story Intelligence (7-6)

**Learnings from Story 7-6:**
1. **64 tests achieved** - High test count ensures comprehensive coverage
2. **DB trigger patterns** - Used for enforcement (not needed here, but pattern applies)
3. **Terminal event detection** - Built terminal detection infrastructure
4. **Atomic operations** - Event before flag pattern successful

**Files created in 7-6 to be aware of:**
- `src/infrastructure/adapters/persistence/terminal_event_detector.py` - Not directly used
- `migrations/008_terminal_event_trigger.sql` - DB enforcement pattern

**Key patterns established:**
- All cessation-related events must be witnessed (CT-12)
- Use structured logging with FR/CT references
- Check halt state before operations (CT-11)

### Git Intelligence (Recent Commits)

```
686a37a feat(story-7.6): Implement cessation as final recorded event (FR24)
cdeb269 feat(story-3.6): Implement 48-hour recovery waiting period (FR21)
```

**Patterns from recent commits:**
- Feature commits use `feat(story-X.Y):` prefix
- Include FR reference in commit message
- Co-Authored-By footer for AI assistance
- Comprehensive test coverage before commit

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-7.7]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-12] - Crisis Response
- [Source: src/domain/primitives/constitutional_thresholds.py] - Threshold registry
- [Source: src/domain/events/cessation_agenda.py] - AgendaTriggerType enum
- [Source: src/application/services/automatic_agenda_placement_service.py] - Trigger constants
- [Source: src/api/routes/observer.py] - Observer API patterns
- [Source: _bmad-output/implementation-artifacts/stories/7-6-cessation-as-final-recorded-event.md] - Previous story

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Implementation completed without issues.

### Completion Notes List

1. **All 6 tasks completed successfully** - Story fully implemented per acceptance criteria.
2. **86 tests written and passing** - 49 unit tests + 37 API/integration tests.
3. **API endpoints implemented**:
   - `GET /v1/observer/cessation-triggers` - Returns all trigger conditions
   - `GET /v1/observer/cessation-triggers.jsonld` - JSON-LD format with semantic context
   - `GET /v1/observer/cessation-triggers/{trigger_type}` - Single trigger lookup
4. **5 trigger conditions documented** per constitutional requirements:
   - consecutive_failures (FR37): 3 in 30 days
   - rolling_window (RT-4): 5 in 90 days
   - anti_success_sustained (FR38): 90 days sustained
   - petition_threshold (FR39): 100+ co-signers
   - breach_threshold (FR32): >10 in 90 days
5. **JSON-LD context implemented** for semantic interoperability (FR134 AC5).
6. **Constitutional floor enforcement** validated in all tests.
7. **No authentication required** per FR44 - public read access.

### File List

**Files Created:**
- `src/domain/models/cessation_trigger_condition.py` - Domain model
- `src/domain/events/trigger_condition_changed.py` - Change event payload
- `src/application/services/public_triggers_service.py` - Service layer
- `tests/unit/domain/test_cessation_trigger_condition.py` - 20 unit tests
- `tests/unit/domain/test_trigger_condition_changed_event.py` - 13 unit tests
- `tests/unit/application/test_public_triggers_service.py` - 16 unit tests
- `tests/unit/api/test_cessation_triggers_endpoint.py` - 18 unit tests
- `tests/integration/test_public_cessation_triggers_integration.py` - 19 integration tests

**Files Modified:**
- `src/domain/models/__init__.py` - Export new model
- `src/domain/events/__init__.py` - Export new event
- `src/application/services/__init__.py` - Export new service
- `src/api/models/observer.py` - Add Pydantic response models
- `src/api/routes/observer.py` - Add 3 new endpoints

## Change Log

- 2026-01-08: Story created via create-story workflow
- 2026-01-08: Story implemented and all tests passing (86 tests)
