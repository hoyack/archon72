# Story 8.3: External Detectability (FR53/FR54)

Status: done

## Story

As an **external observer**,
I want system unavailability independently detectable,
So that I don't rely on system self-reporting.

## Acceptance Criteria

### AC1: Third-Party Ping Endpoint
**Given** external monitoring services (e.g., UptimeRobot, Pingdom, external scripts)
**When** they send HTTP requests to the system
**Then** a dedicated health/ping endpoint responds with minimal latency
**And** the endpoint returns clear status (up/down/degraded)
**And** no authentication is required for basic availability check

### AC2: External Unavailability Detection
**Given** the system becomes unavailable
**When** external monitors detect it (via timeout or error response)
**Then** external parties are notified through their own alerting systems
**And** system self-reporting is NOT the only source of truth
**And** the detection is independent of internal monitoring

### AC3: Multi-Geographic Monitoring Configuration
**Given** external monitoring configuration
**When** I examine it
**Then** multiple geographic locations are configured for monitoring
**And** single-location false positives are mitigated
**And** documentation exists for setting up external monitors

### AC4: Halt State Visibility to External Monitors
**Given** the system is in halt state (via constitutional halt)
**When** an external monitor checks availability
**Then** the response indicates halted state (not healthy)
**And** halt reason is NOT exposed (security)
**And** external observers can distinguish "down" from "halted"

### AC5: Frozen State Visibility to External Monitors
**Given** the system is in frozen/ceased state
**When** an external monitor checks availability
**Then** the response indicates frozen state
**And** frozen systems still respond (read-only available)
**And** external observers can distinguish operational states

## Tasks / Subtasks

- [x] **Task 1: Create External Health Endpoint** (AC: 1,2)
  - [x] Create `src/api/routes/external_health.py`
    - [x] `GET /health/external` - No auth, minimal response
    - [x] Return only: `{"status": "up"|"down"|"halted"|"frozen", "timestamp": "..."}`
    - [x] Response time target: <50ms (no DB queries)
    - [x] Use cached halt/freeze status (in-memory check only)
  - [x] Add route to `src/api/routes/__init__.py`
  - [x] Create `src/api/models/external_health.py`
    - [x] `ExternalHealthResponse` Pydantic model
    - [x] `ExternalHealthStatus` enum (UP, DOWN, HALTED, FROZEN)

- [x] **Task 2: Create External Health Service** (AC: 1,4,5)
  - [x] Create `src/application/services/external_health_service.py`
    - [x] `ExternalHealthService` class
    - [x] `get_external_status() -> ExternalHealthStatus`
    - [x] Check halt state (in-memory cache from dual-channel)
    - [x] Check freeze state (from freeze checker)
    - [x] NO database queries - must be fast
    - [x] Inject `HaltCheckerPort` and `FreezeCheckerPort`
  - [x] Export from `src/application/services/__init__.py`

- [x] **Task 3: Create External Health Port** (AC: 1,2)
  - [x] Create `src/application/ports/external_health.py`
    - [x] `ExternalHealthPort` protocol
    - [x] `get_status() -> ExternalHealthStatus`
    - [x] `get_timestamp() -> datetime`
  - [x] Export from `src/application/ports/__init__.py`

- [x] **Task 4: Create External Health Stub** (AC: 1)
  - [x] Create `src/infrastructure/stubs/external_health_stub.py`
    - [x] Implement `ExternalHealthPort`
    - [x] Default to UP status
    - [x] Support test injection of halt/frozen states
  - [x] Export from `src/infrastructure/stubs/__init__.py`

- [x] **Task 5: Create Monitoring Configuration Documentation** (AC: 3)
  - [x] Create `docs/operations/external-monitoring-setup.md`
    - [x] Recommended external monitoring services
    - [x] Configuration for multiple geographic locations
    - [x] Alert thresholds and false-positive mitigation
    - [x] Integration with internal alerting (PagerDuty/Slack)
    - [x] Sample UptimeRobot/Pingdom configuration

- [x] **Task 6: Unit Tests** (AC: 1,2,4,5)
  - [x] Create `tests/unit/api/test_external_health_route.py`
    - [x] Test endpoint returns 200 with UP status when healthy
    - [x] Test endpoint returns 200 with HALTED when halted
    - [x] Test endpoint returns 200 with FROZEN when frozen
    - [x] Test no auth required
    - [x] Test response format matches ExternalHealthResponse
  - [x] Create `tests/unit/application/test_external_health_service.py`
    - [x] Test get_external_status returns UP when healthy
    - [x] Test returns HALTED when halt checker indicates halt
    - [x] Test returns FROZEN when freeze checker indicates frozen
    - [x] Test HALTED takes precedence over FROZEN
    - [x] Test service does NOT make DB calls

- [x] **Task 7: Integration Tests** (AC: 1,2,3,4,5)
  - [x] Create `tests/integration/test_external_health_integration.py`
    - [x] Test HTTP request to /health/external returns valid JSON
    - [x] Test response time <100ms (allowing margin)
    - [x] Test endpoint accessible without authentication
    - [x] Test halt state properly reflected in response
    - [x] Test frozen state properly reflected in response
    - [x] Test status transitions (up→halted→up)

## Dev Notes

### Relevant Architecture Patterns and Constraints

**FR54 (No Silent Failures) - CRITICAL:**
- System unavailability MUST be independently detectable
- External observers should NOT rely on system self-reporting
- This aligns with CT-11 (Silent failure destroys legitimacy)

**FR53 (Operational Metrics NOT for Constitutional Assessment):**
- This endpoint is OPERATIONAL - it checks availability, not constitutional health
- Constitutional health is a separate concern (Story 8-10)
- Keep these concerns strictly separated per FR52

**CT-11 Implication:**
- If the system can't respond, external monitors detect it
- No "silent death" - external parties will know
- This is a TRUST mechanism - observers don't need to trust our reporting

**Performance Requirements:**
- External health check MUST be fast (<50ms target)
- NO database queries in the hot path
- Use cached halt/freeze state from in-memory
- This is the "canary" endpoint - if it's slow, everything is slow

**Security Considerations:**
- No authentication required for basic ping
- DO NOT expose internal state details
- DO NOT expose halt reasons (security-sensitive)
- Status values are intentionally vague (up/halted/frozen)

### Source Tree Components to Touch

**Files to Create:**
```
src/api/routes/external_health.py              # FastAPI route
src/api/models/external_health.py              # Response models
src/application/ports/external_health.py       # Port definition
src/application/services/external_health_service.py  # Service
src/infrastructure/stubs/external_health_stub.py  # Stub
docs/operations/external-monitoring-setup.md   # Operations guide
tests/unit/api/test_external_health_route.py
tests/unit/application/test_external_health_service.py
tests/integration/test_external_health_integration.py
```

**Files to Modify:**
```
src/api/routes/__init__.py                     # Export route
src/application/ports/__init__.py              # Export port
src/application/services/__init__.py           # Export service
src/infrastructure/stubs/__init__.py           # Export stub
```

### Related Existing Code (MUST Review)

**Story 8.1 & 8.2 Implementation (Reference):**
- `src/infrastructure/monitoring/metrics.py` - Prometheus metrics
- `src/application/services/separation_enforcement_service.py` - FR52 separation
- `src/domain/models/event_type_registry.py` - Event type classification

**Halt Transport (MUST Use for Halt State):**
- `src/application/ports/halt_checker.py` - HaltCheckerPort interface
- `src/infrastructure/stubs/halt_checker_stub.py` - Stub implementation
- Story 3-4 established halt state checking patterns

**Freeze Checker (MUST Use for Freeze State):**
- `src/application/ports/freeze_checker.py` - FreezeCheckerPort interface
- `src/infrastructure/stubs/freeze_checker_stub.py` - Stub implementation
- Story 7-4 established freeze mechanics

**Health Routes (Pattern Reference):**
- `src/api/routes/health.py` - Internal health check (NOT external)
- `src/api/models/health.py` - Health response models
- Note: External health is SEPARATE from internal health

### Design Decisions

**Why Separate Endpoint from /health:**
```python
# Internal health (existing) - detailed, may have auth
GET /health/ready -> { services, database, redis, ... }

# External health (new) - minimal, no auth, fast
GET /health/external -> { status: "up", timestamp: "..." }
```

**Status Enum Design:**
```python
class ExternalHealthStatus(str, Enum):
    UP = "up"           # System operational
    DOWN = "down"       # System not responding (detected by timeout)
    HALTED = "halted"   # Constitutional halt in effect
    FROZEN = "frozen"   # System ceased/frozen (read-only)
```

**Why No DB Queries:**
```python
# WRONG - Database query makes this slow and dependent
async def get_status(self) -> ExternalHealthStatus:
    result = await self.db.execute("SELECT 1")  # NO!

# CORRECT - In-memory check only
async def get_status(self) -> ExternalHealthStatus:
    if await self.halt_checker.is_halted():  # Cached in-memory
        return ExternalHealthStatus.HALTED
    if await self.freeze_checker.is_frozen():  # Cached in-memory
        return ExternalHealthStatus.FROZEN
    return ExternalHealthStatus.UP
```

**Precedence Rules:**
1. If halted → return HALTED (most severe)
2. If frozen → return FROZEN (still operational but ceased)
3. Otherwise → return UP
4. DOWN is never returned by the service (external monitors infer DOWN from timeout)

### Testing Standards Summary

- **Unit Tests Location**: `tests/unit/api/`, `tests/unit/application/`
- **Integration Tests Location**: `tests/integration/`
- **Async Testing**: ALL tests use `pytest.mark.asyncio` and `async def test_*`
- **Mocking**: Mock HaltCheckerPort, FreezeCheckerPort
- **Performance**: Integration tests verify response time <100ms
- **Coverage**: All status paths, all precedence rules

### Project Structure Notes

**Hexagonal Architecture Compliance:**
- Port: `src/application/ports/external_health.py`
- Stub: `src/infrastructure/stubs/external_health_stub.py`
- Service: `src/application/services/external_health_service.py`
- Route: `src/api/routes/external_health.py`
- Models: `src/api/models/external_health.py`

**Import Rules:**
- Port imports from domain only (enums)
- Service imports ports and domain
- Route imports service and API models
- Stub implements port

### Previous Story Intelligence (8-2)

**Learnings from Story 8-2:**
1. **Separation enforcement pattern** - Keep operational/constitutional concerns separate
2. **Event type registry pattern** - Centralized type management works well
3. **Stub patterns** - Default to healthy/valid states for testing
4. **Test organization** - Unit tests per module, integration tests per feature

**Key code established:**
- `SeparationEnforcementService` - separation validation pattern
- `EventTypeRegistry` - centralized type constants
- FR52 compliance in event store - type validation at boundary

### Git Intelligence (Recent Commits)

```
686a37a feat(story-7.6): Implement cessation as final recorded event (FR24)
cdeb269 feat(story-3.6): Implement 48-hour recovery waiting period (FR21)
```

**Commit patterns:**
- Feature commits use `feat(story-X.Y):` prefix
- Include FR reference in commit message
- Co-Authored-By footer for AI assistance

### External Monitoring Services (Reference)

**Recommended Services for Multi-Geographic Monitoring:**
- UptimeRobot (free tier: 50 monitors, 5 locations)
- Pingdom (commercial, 100+ locations)
- StatusCake (free tier: 10 monitors)
- Better Uptime (commercial, many locations)

**Configuration Best Practices:**
- Monitor from at least 3 geographic regions
- Set timeout to 10 seconds (generous)
- Alert after 2 consecutive failures (avoid flapping)
- Check every 1-5 minutes

### Edge Cases to Test

1. **Simultaneous halt and freeze**: HALTED takes precedence
2. **Rapid state transitions**: Response reflects current state
3. **High concurrent requests**: Endpoint handles load
4. **Network partition**: External monitors detect unavailability
5. **Slow dependencies**: External health still responds fast
6. **Empty/invalid state**: Defaults to UP (fail-open for monitoring)

### Environment Variables

None required for this story - external health is stateless.

Optional configuration (if needed later):
```
EXTERNAL_HEALTH_CACHE_TTL_SECONDS=5  # How long to cache halt/freeze state
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-8.3] - Story requirements
- [Source: _bmad-output/planning-artifacts/prd.md#FR53-FR54] - Functional requirements
- [Source: _bmad-output/planning-artifacts/architecture.md#CT-11] - Silent failure truth
- [Source: src/application/ports/halt_checker.py] - Halt checking port
- [Source: src/application/ports/freeze_checker.py] - Freeze checking port
- [Source: src/api/routes/health.py] - Existing health routes (reference)
- [Source: _bmad-output/project-context.md] - Project rules

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - implementation proceeded without issues.

### Completion Notes List

1. All 7 tasks completed successfully
2. 46 tests written and passing (11 unit API, 20 unit service, 15 integration)
3. Response time verified <100ms in integration tests
4. Halt/Freeze precedence rules implemented and tested
5. No authentication required for external endpoint
6. Documentation provided for multi-geographic monitoring setup

### File List

**Created:**
- `src/application/ports/external_health.py` - Port definition with ExternalHealthStatus enum
- `src/application/services/external_health_service.py` - Service with singleton management
- `src/infrastructure/stubs/external_health_stub.py` - Stub for testing
- `src/api/routes/external_health.py` - FastAPI route for /health/external
- `src/api/models/external_health.py` - Pydantic response model
- `docs/operations/external-monitoring-setup.md` - Monitoring setup guide
- `tests/unit/api/test_external_health_route.py` - Unit tests for route
- `tests/unit/application/test_external_health_service.py` - Unit tests for service
- `tests/integration/test_external_health_integration.py` - Integration tests

**Modified:**
- `src/application/ports/__init__.py` - Added exports
- `src/api/routes/__init__.py` - Added router export
- `src/infrastructure/stubs/__init__.py` - Added stub export

## Change Log

- 2026-01-08: Story created via create-story workflow with comprehensive context
- 2026-01-08: Story implemented - all tasks completed, 46 tests passing
