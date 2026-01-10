# Story 8.4: Incident Reporting (FR54, FR145, FR147)

Status: done

## Story

As a **system operator**,
I want incident reports for halt, fork, or >3 overrides/day,
So that significant events are documented and actionable.

## Acceptance Criteria

### AC1: Halt Event Incident Report
**Given** a halt event
**When** it occurs
**Then** an incident report is created
**And** report includes: timeline, cause, impact, response
**And** report is stored for later retrieval and publication

### AC2: Fork Detection Incident Report
**Given** a fork detection
**When** it occurs
**Then** incident report is created
**And** includes: detection details, affected events, resolution
**And** report links to the ForkDetectedEvent

### AC3: Override Threshold Incident Report (>3/day)
**Given** >3 overrides in a single day
**When** threshold is crossed
**Then** incident report is triggered
**And** includes: override list, Keeper identities, reasons
**And** report aggregates all overrides for the day

### AC4: Incident Report Publication (7-day rule)
**Given** incident report transparency (FR147)
**When** 7 days pass from report creation
**Then** report is eligible for publication publicly
**And** sensitive operational details may be redacted
**And** report publication status is tracked

### AC5: Incident Report Query API
**Given** the incident reporting system
**When** an operator queries for incidents
**Then** incidents can be filtered by type, date range, and status
**And** both draft and published reports are accessible

## Tasks / Subtasks

- [x] **Task 1: Create Incident Report Domain Model** (AC: 1,2,3,4)
  - [x] Create `src/domain/models/incident_report.py`
    - [x] `IncidentType` enum: HALT, FORK, OVERRIDE_THRESHOLD
    - [x] `IncidentStatus` enum: DRAFT, PENDING_PUBLICATION, PUBLISHED, REDACTED
    - [x] `IncidentReport` dataclass with all required fields
    - [x] `TimelineEntry` dataclass with timestamp, description, event_id
  - [x] Export from `src/domain/models/__init__.py`

- [x] **Task 2: Create Incident Report Events** (AC: 1,2,3,4)
  - [x] Create `src/domain/events/incident_report.py`
    - [x] `INCIDENT_REPORT_CREATED_EVENT_TYPE = "incident.report.created"`
    - [x] `INCIDENT_REPORT_PUBLISHED_EVENT_TYPE = "incident.report.published"`
    - [x] `IncidentReportCreatedPayload` dataclass
    - [x] `IncidentReportPublishedPayload` dataclass
    - [x] Both payloads include `signable_content()` (CT-12)
  - [x] Export from `src/domain/events/__init__.py`

- [x] **Task 3: Create Incident Report Repository Port** (AC: 1,2,3,4,5)
  - [x] Create `src/application/ports/incident_report_repository.py`
    - [x] `IncidentReportRepositoryPort` protocol with all required methods
  - [x] Export from `src/application/ports/__init__.py`

- [x] **Task 4: Create Incident Report Repository Stub** (AC: 1,2,3,4,5)
  - [x] Create `src/infrastructure/stubs/incident_report_repository_stub.py`
    - [x] Implement `IncidentReportRepositoryPort`
    - [x] In-memory storage with dict[UUID, IncidentReport]
    - [x] Support all query operations
  - [x] Export from `src/infrastructure/stubs/__init__.py`

- [x] **Task 5: Create Incident Reporting Service** (AC: 1,2,3,4)
  - [x] Create `src/application/services/incident_reporting_service.py`
    - [x] `IncidentReportingService` class with all required methods
    - [x] HALT CHECK FIRST before any write operation (CT-11)
    - [x] Write events on create/publish (CT-12)
  - [x] Export from `src/application/services/__init__.py`

- [x] **Task 6: Create Override Daily Threshold Monitor** (AC: 3)
  - [x] Create `src/application/services/override_daily_threshold_monitor.py`
    - [x] `OverrideDailyThresholdMonitor` class
    - [x] Threshold constant: `DAILY_OVERRIDE_THRESHOLD = 3`
    - [x] If >3 overrides today, create incident report
  - [x] Export from `src/application/services/__init__.py`

- [x] **Task 7: Create Incident Report API Models** (AC: 5)
  - [x] Create `src/api/models/incident.py`
    - [x] `IncidentDetailResponse` Pydantic model
    - [x] `IncidentSummaryResponse` Pydantic model
    - [x] `ListIncidentsResponse` Pydantic model
    - [x] `IncidentQueryParams` Pydantic model for filtering
  - [x] Export from `src/api/models/__init__.py`

- [x] **Task 8: Create Incident Report API Routes** (AC: 5)
  - [x] Create `src/api/routes/incident.py`
    - [x] `GET /v1/incidents` - List/query incidents
    - [x] `GET /v1/incidents/{incident_id}` - Get single incident
    - [x] `GET /v1/incidents/published` - List published incidents (no auth)
    - [x] `GET /v1/incidents/pending` - List pending publication
  - [x] Add router to `src/api/routes/__init__.py`

- [x] **Task 9: Unit Tests** (AC: 1,2,3,4,5)
  - [x] Create `tests/unit/domain/test_incident_report.py` (27 tests)
  - [x] Create `tests/unit/domain/test_incident_report_events.py` (16 tests)
  - [x] Create `tests/unit/application/test_incident_reporting_service.py` (14 tests)
  - [x] Create `tests/unit/application/test_override_daily_threshold_monitor.py` (9 tests)

- [x] **Task 10: Integration Tests** (AC: 1,2,3,4,5)
  - [x] Create `tests/integration/test_incident_reporting_integration.py` (8 tests)
    - [x] Test halt event creates incident
    - [x] Test fork detection creates incident
    - [x] Test >3 overrides/day creates incident
    - [x] Test incident query API
    - [x] Test publication flow
    - [x] Test 7-day rule enforcement

## Dev Notes

### Relevant Architecture Patterns and Constraints

**FR54 (No Silent Failures) - CRITICAL:**
- Incident reports ensure significant events are documented
- System unavailability (halt) MUST be independently detectable
- Fork detection (constitutional crisis) MUST create paper trail
- Override abuse (>3/day) MUST trigger documentation

**FR145 (Incident Investigation):**
- Following halt, fork, or >3 overrides/day: incident report with timeline, root cause, contributing factors, prevention recommendations
- Reports are operational artifacts (NOT constitutional events until published)

**FR147 (Incident Transparency):**
- Incident reports SHALL be publicly available within 7 days of resolution
- Redaction only for active security vulnerabilities
- Publication creates a constitutional event (witnessed, CT-12)

**CT-11 (Silent Failure Destroys Legitimacy):**
- HALT CHECK FIRST before any write operation
- Never suppress errors in incident creation

**CT-12 (Witnessing Creates Accountability):**
- Incident report creation/publication events MUST be witnessed
- All events include `signable_content()` for verification

**NFR30 (Incident Investigation):**
- Incident reports SHALL be generated for halt, fork, or >3 overrides/day

### Source Tree Components to Touch

**Files to Create:**
```
src/domain/models/incident_report.py              # Domain model
src/domain/events/incident_report.py              # Event payloads
src/application/ports/incident_report_repository.py  # Port definition
src/application/services/incident_reporting_service.py  # Core service
src/application/services/override_daily_monitor.py   # Daily threshold monitor
src/infrastructure/stubs/incident_report_repository_stub.py  # Stub
src/api/routes/incident_report.py                 # API routes
src/api/models/incident_report.py                 # API models
tests/unit/domain/test_incident_report.py
tests/unit/application/test_incident_reporting_service.py
tests/unit/application/test_override_daily_monitor.py
tests/integration/test_incident_reporting_integration.py
```

**Files to Modify:**
```
src/domain/models/__init__.py                     # Export models
src/domain/events/__init__.py                     # Export events
src/application/ports/__init__.py                 # Export port
src/application/services/__init__.py              # Export services
src/infrastructure/stubs/__init__.py              # Export stub
src/api/routes/__init__.py                        # Export routes
src/api/models/__init__.py                        # Export models
```

### Related Existing Code (MUST Review)

**Halt Checker (Incident Trigger - Story 3.1-3.4):**
- `src/application/ports/halt_checker.py` - HaltChecker interface
- `src/infrastructure/stubs/halt_checker_stub.py` - Stub implementation
- `src/domain/events/halt_cleared.py` - Halt event patterns

**Fork Monitor (Incident Trigger - Story 3.1):**
- `src/application/ports/fork_monitor.py` - ForkMonitor interface
- `src/domain/events/fork_detected.py` - Fork detection event

**Override Tracking (Incident Trigger - Story 5.1-5.5):**
- `src/application/ports/override_trend_repository.py` - Override history queries
- `src/application/services/override_trend_service.py` - Trend analysis (30-day, 365-day patterns)
- `src/domain/events/override_event.py` - Override event payloads
- Use `OverrideTrendRepositoryProtocol.get_override_count_for_period()` for daily counts

**Event Writer (Witnessed Events - Story 1.6):**
- `src/application/services/event_writer_service.py` - Event writing with witnessing
- All incident events must use this service for CT-12 compliance

**External Health (Story 8.3 reference):**
- `src/application/services/external_health_service.py` - Status patterns
- Story 8.3 established operational health patterns

### Design Decisions

**Incident vs Event Architecture:**
```python
# Incidents are OPERATIONAL artifacts (mutable, with status)
# They become CONSTITUTIONAL when published (immutable event)

# Operational (stored in operational DB, not event store)
class IncidentReport:
    incident_id: UUID
    status: IncidentStatus  # DRAFT -> PENDING_PUBLICATION -> PUBLISHED
    # ... mutable fields like timeline, response

# Constitutional (written to event store when created/published)
# IncidentReportCreatedEvent - documents creation
# IncidentReportPublishedEvent - documents publication with content hash
```

**Daily Override Threshold Logic:**
```python
# FR145: >3 overrides/day triggers incident
DAILY_OVERRIDE_THRESHOLD = 3  # Strictly greater than 3

async def check_daily_threshold(self) -> Optional[IncidentReport]:
    today = date.today()
    count = await self._repo.get_override_count_for_period(
        start_date=datetime.combine(today, time.min),
        end_date=datetime.combine(today, time.max),
    )
    if count > DAILY_OVERRIDE_THRESHOLD:  # >3, not >=3
        return await self._create_override_threshold_incident(today)
    return None
```

**Publication Flow:**
```python
# FR147: 7 days from resolution (not creation)
async def publish_incident(
    self,
    incident_id: UUID,
    redacted_fields: Optional[list[str]] = None,
) -> None:
    incident = await self._repo.get_by_id(incident_id)

    # Check 7-day eligibility
    if incident.resolution_at is None:
        raise IncidentNotResolvedError("Cannot publish unresolved incident")

    publish_eligible_at = incident.resolution_at + timedelta(days=7)
    if datetime.now(timezone.utc) < publish_eligible_at:
        raise PublicationNotEligibleError(
            f"Incident not eligible until {publish_eligible_at}"
        )

    # Redact sensitive fields if specified
    if redacted_fields:
        incident = incident.with_redactions(redacted_fields)

    # Write constitutional event
    await self._event_writer.write_event(
        event_type=INCIDENT_REPORT_PUBLISHED_EVENT_TYPE,
        payload=IncidentReportPublishedPayload(
            incident_id=incident.incident_id,
            content_hash=incident.content_hash(),
            redacted_fields=redacted_fields or [],
        ).to_dict(),
        agent_id=INCIDENT_SYSTEM_AGENT_ID,
    )

    incident.status = IncidentStatus.PUBLISHED
    incident.published_at = datetime.now(timezone.utc)
    await self._repo.save(incident)
```

**Timeline Entry Pattern:**
```python
@dataclass(frozen=True)
class TimelineEntry:
    timestamp: datetime
    description: str
    event_id: Optional[UUID] = None  # Link to related constitutional event
    actor: Optional[str] = None  # Who took the action

# Example timeline for halt incident:
timeline = [
    TimelineEntry(
        timestamp=halt_detected_at,
        description="Fork detected by continuous monitor",
        event_id=fork_event_id,
        actor="system.fork_monitor",
    ),
    TimelineEntry(
        timestamp=halt_triggered_at,
        description="System halt triggered per FR17",
        event_id=halt_event_id,
        actor="system.halt_trigger",
    ),
    # ... more entries added during investigation
]
```

### Testing Standards Summary

- **Unit Tests Location**: `tests/unit/domain/`, `tests/unit/application/`
- **Integration Tests Location**: `tests/integration/`
- **Async Testing**: ALL tests use `pytest.mark.asyncio` and `async def test_*`
- **Mocking**: Mock `HaltChecker`, `EventWriterService`, repository ports
- **Coverage**: All trigger conditions, all status transitions, 7-day rule

### Project Structure Notes

**Hexagonal Architecture Compliance:**
- Port: `src/application/ports/incident_report_repository.py`
- Stub: `src/infrastructure/stubs/incident_report_repository_stub.py`
- Service: `src/application/services/incident_reporting_service.py`
- Route: `src/api/routes/incident_report.py`
- Models: `src/api/models/incident_report.py`, `src/domain/models/incident_report.py`

**Import Rules:**
- Domain imports nothing from other layers
- Application imports from domain only (plus ports)
- Infrastructure implements ports
- API depends on application services

### Previous Story Intelligence (8-3)

**Learnings from Story 8-3 (External Detectability):**
1. **Service singleton pattern** - Use `get_service()` factory for singleton management
2. **Status precedence** - HALTED > FROZEN > UP; similar pattern for incidents
3. **No auth for public endpoints** - `/v1/incidents/public` should be unauthenticated
4. **Response time** - Keep incident queries efficient (index by type, date)
5. **Test organization** - Unit tests per module, integration tests per feature

**Code patterns from 8-3:**
- `ExternalHealthService` - singleton management pattern
- `ExternalHealthStatus` enum - status enumeration pattern
- `ExternalHealthResponse` - Pydantic response pattern

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

1. **Multiple triggers same day**: Halt + Fork + >3 overrides all trigger separate incidents
2. **Partial override threshold**: Exactly 3 overrides does NOT trigger (>3 required)
3. **Publication before 7 days**: Should be rejected
4. **Unresolved incident publication**: Should be rejected
5. **Redaction edge cases**: Empty redaction list vs null
6. **Halt during incident creation**: HALT CHECK pattern must work
7. **Timeline ordering**: Entries must be chronological
8. **Duplicate incident prevention**: Same halt event shouldn't create multiple incidents

### Environment Variables

None required for this story - incident reporting uses existing infrastructure.

Optional configuration (if needed later):
```
INCIDENT_PUBLICATION_DELAY_DAYS=7  # Default 7 per FR147
DAILY_OVERRIDE_THRESHOLD=3         # Default 3 per FR145
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-8.4] - Story requirements
- [Source: _bmad-output/planning-artifacts/prd.md#FR54] - No Silent Failures
- [Source: _bmad-output/planning-artifacts/prd.md#FR145] - Incident Investigation
- [Source: _bmad-output/planning-artifacts/prd.md#FR147] - Incident Transparency
- [Source: _bmad-output/planning-artifacts/prd.md#NFR30] - Incident report generation
- [Source: src/application/ports/halt_checker.py] - Halt checking port
- [Source: src/application/ports/fork_monitor.py] - Fork monitoring port
- [Source: src/application/services/override_trend_service.py] - Override tracking patterns
- [Source: _bmad-output/implementation-artifacts/stories/8-3-external-detectability.md] - Previous story
- [Source: _bmad-output/project-context.md] - Project rules

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

1. **Domain Model** - Created `IncidentReport`, `IncidentType`, `IncidentStatus`, `TimelineEntry` with full FR145/FR147 compliance
2. **Event Payloads** - Created `IncidentReportCreatedPayload` and `IncidentReportPublishedPayload` with `signable_content()` for CT-12 witnessing
3. **Repository Port** - Defined `IncidentReportRepositoryPort` with comprehensive query capabilities
4. **Repository Stub** - Implemented in-memory stub with event indexing and date filtering
5. **Reporting Service** - Full HALT CHECK FIRST pattern (CT-11), witnessed events (CT-12), reads during halt (CT-13)
6. **Daily Monitor** - `OverrideDailyThresholdMonitor` checks >3 overrides/day threshold per FR145
7. **API Layer** - Pydantic models and FastAPI routes for `/v1/incidents` endpoints
8. **Tests** - 74 total tests (66 unit + 8 integration), all passing

### File List

**Files Created:**
- `src/domain/models/incident_report.py` - Domain model (317 lines)
- `src/domain/events/incident_report.py` - Event payloads (135 lines)
- `src/application/ports/incident_report_repository.py` - Repository port (97 lines)
- `src/application/services/incident_reporting_service.py` - Core service (395 lines)
- `src/application/services/override_daily_threshold_monitor.py` - Monitor service (189 lines)
- `src/infrastructure/stubs/incident_report_repository_stub.py` - Stub (203 lines)
- `src/api/models/incident.py` - API models (155 lines)
- `src/api/routes/incident.py` - API routes (272 lines)
- `tests/unit/domain/test_incident_report.py` - Domain tests (27 tests)
- `tests/unit/domain/test_incident_report_events.py` - Event tests (16 tests)
- `tests/unit/application/test_incident_reporting_service.py` - Service tests (14 tests)
- `tests/unit/application/test_override_daily_threshold_monitor.py` - Monitor tests (9 tests)
- `tests/integration/test_incident_reporting_integration.py` - Integration tests (8 tests)

**Files Modified:**
- `src/domain/models/__init__.py` - Added incident model exports
- `src/domain/events/__init__.py` - Added incident event exports
- `src/application/ports/__init__.py` - Added repository port export
- `src/application/services/__init__.py` - Added service exports
- `src/infrastructure/stubs/__init__.py` - Added stub export
- `src/api/models/__init__.py` - Added API model exports
- `src/api/routes/__init__.py` - Added incident router

## Change Log

- 2026-01-08: Story created via create-story workflow with comprehensive context
- 2026-01-08: Story completed - all 10 tasks done, 74 tests passing
