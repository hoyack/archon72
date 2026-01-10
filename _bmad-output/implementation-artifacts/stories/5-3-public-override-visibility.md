# Story 5.3: Public Override Visibility (FR25)

Status: done

## Story

As an **external observer**,
I want all overrides publicly visible,
So that override usage is transparent.

## Acceptance Criteria

### AC1: Public Override Query Endpoint
**Given** the public API
**When** I query `/v1/observer/overrides`
**Then** I receive all override events
**And** no authentication required (FR44)

### AC2: Full Keeper Identity Visibility
**Given** an override event
**When** displayed publicly
**Then** Keeper identity is visible (not anonymized)
**And** full scope and reason are visible
**And** duration and expiration info are visible

### AC3: Date Range and Pagination Support
**Given** override history
**When** I query for a date range
**Then** I receive all overrides in that range
**And** pagination is supported (limit/offset)
**And** total count is included in response

## Tasks / Subtasks

- [x] Task 1: Create Override API response models (AC: #1, #2)
  - [x] 1.1 Create `src/api/models/override.py` with response models
  - [x] 1.2 Define `OverrideEventResponse` with all public fields:
    - `override_id: UUID` - Event ID
    - `keeper_id: str` - Keeper identity (VISIBLE per FR25)
    - `scope: str` - What is being overridden
    - `duration: int` - Duration in seconds
    - `reason: str` - Override reason (FR28 enumerated)
    - `action_type: str` - Type of override action
    - `initiated_at: datetime` - When initiated (UTC)
    - `expires_at: datetime` - When expires (calculated)
    - `event_hash: str` - Content hash for verification
    - `sequence: int` - Event sequence number
    - `witness_id: Optional[str]` - Witness attribution (CT-12)
  - [x] 1.3 Define `OverrideEventsListResponse` with:
    - `overrides: list[OverrideEventResponse]`
    - `pagination: PaginationMetadata` (reuse from observer.py)
  - [x] 1.4 Export models from `src/api/models/__init__.py`

- [x] Task 2: Create Override service for public queries (AC: #1, #3)
  - [x] 2.1 Create `src/application/services/public_override_service.py`
  - [x] 2.2 Inject dependency: `EventStorePort` (read-only)
  - [x] 2.3 Implement `async def get_overrides(limit, offset, start_date, end_date) -> tuple[list[Event], int]`
  - [x] 2.4 Filter events where `event_type == "override.initiated"`
  - [x] 2.5 Support date range filtering on `authority_timestamp`
  - [x] 2.6 Return total count for pagination
  - [x] 2.7 Export from `src/application/services/__init__.py`

- [x] Task 3: Create Override routes (AC: #1, #2, #3)
  - [x] 3.1 Create `src/api/routes/override.py` with router
  - [x] 3.2 Add router prefix `/v1/observer/overrides` (extends observer API)
  - [x] 3.3 Implement `GET /` endpoint:
    - Query params: `limit`, `offset`, `start_date`, `end_date`
    - No auth dependency (FR44)
    - Apply rate limiting (FR48 - same limits as all users)
    - Return `OverrideEventsListResponse`
  - [x] 3.4 Implement `GET /{override_id}` endpoint for single override
  - [x] 3.5 Register router in `src/api/main.py`

- [x] Task 4: Create Override adapter (AC: #2)
  - [x] 4.1 Create `src/api/adapters/override.py`
  - [x] 4.2 Implement `EventToOverrideAdapter.to_response(event: Event) -> OverrideEventResponse`
  - [x] 4.3 Map event payload to response model with full visibility
  - [x] 4.4 Calculate `expires_at` from `initiated_at + duration`
  - [x] 4.5 Ensure Keeper ID is NOT anonymized (FR25 requirement)

- [x] Task 5: Create dependencies for DI (AC: #1)
  - [x] 5.1 Create `src/api/dependencies/override.py`
  - [x] 5.2 Implement `get_public_override_service() -> PublicOverrideService`
  - [x] 5.3 Wire up EventStorePort dependency

- [x] Task 6: Write unit tests (AC: #1, #2, #3)
  - [x] 6.1 Create `tests/unit/api/test_override_routes.py`
    - Test GET /overrides returns list
    - Test pagination (limit, offset, total_count)
    - Test date range filtering
    - Test no auth required
    - Test rate limiting applied
  - [x] 6.2 Create `tests/unit/api/test_override_adapter.py`
    - Test event to response conversion
    - Test Keeper ID is visible (not anonymized)
    - Test expires_at calculation
  - [x] 6.3 Create `tests/unit/application/test_public_override_service.py`
    - Test filtering by event type
    - Test date range filtering
    - Test pagination

- [x] Task 7: Write integration tests (AC: #1, #2, #3)
  - [x] 7.1 Create `tests/integration/test_public_override_visibility_integration.py`
  - [x] 7.2 Test end-to-end: override created -> visible in /overrides
  - [x] 7.3 Test Keeper identity visibility (NOT anonymized)
  - [x] 7.4 Test date range query returns correct events
  - [x] 7.5 Test pagination works correctly
  - [x] 7.6 Test no authentication required (anonymous access)

## Dev Notes

### Constitutional Constraints (CRITICAL)

- **FR25**: All overrides SHALL be publicly visible
- **FR44**: No authentication required for read endpoints
- **FR48**: Rate limits identical for anonymous and authenticated users
- **CT-12**: Witnessing creates accountability -> Include witness attribution
- **CT-11**: Silent failure destroys legitimacy -> Errors must be visible

### Pattern References from Previous Stories

**API Response Pattern** (from `src/api/routes/observer.py`):
```python
@router.get("/overrides", response_model=OverrideEventsListResponse)
async def get_overrides(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    public_override_service: PublicOverrideService = Depends(get_public_override_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> OverrideEventsListResponse:
    """Get all override events for public transparency (FR25).

    No authentication required (FR44).
    Rate limits identical for all users (FR48).
    """
    await rate_limiter.check_rate_limit(request)

    overrides, total = await public_override_service.get_overrides(
        limit=limit,
        offset=offset,
        start_date=start_date,
        end_date=end_date,
    )

    event_responses = EventToOverrideAdapter.to_response_list(overrides)
    has_more = (offset + len(overrides)) < total

    return OverrideEventsListResponse(
        overrides=event_responses,
        pagination=PaginationMetadata(
            total_count=total,
            offset=offset,
            limit=limit,
            has_more=has_more,
        ),
    )
```

**Adapter Pattern** (from `src/api/adapters/observer.py`):
```python
class EventToOverrideAdapter:
    """Converts domain events to API response models."""

    @staticmethod
    def to_response(event: Event) -> OverrideEventResponse:
        """Convert Event to OverrideEventResponse.

        CRITICAL: Keeper ID is NOT anonymized per FR25.
        """
        payload = event.payload  # OverrideEventPayload
        return OverrideEventResponse(
            override_id=event.event_id,
            keeper_id=payload.keeper_id,  # VISIBLE - FR25
            scope=payload.scope,
            duration=payload.duration,
            reason=payload.reason,
            action_type=payload.action_type.value,
            initiated_at=payload.initiated_at,
            expires_at=payload.expires_at,
            event_hash=event.content_hash,
            sequence=event.sequence,
            witness_id=event.witness_id,
        )
```

### Key Dependencies from Previous Stories

- `EventStorePort` from Story 1.1 - for reading override events
- `ObserverRateLimiter` from Story 4.1 - for rate limiting
- `PaginationMetadata` from Story 4.1 - reuse for pagination
- `OverrideEventPayload` from Story 5.1 - event structure
- `OverrideReason` from Story 5.2 - reason enumeration

### Project Structure Notes

**Files to Create:**
```
src/api/models/override.py                    # New - API response models
src/api/routes/override.py                    # New - Override routes
src/api/adapters/override.py                  # New - Event to response adapter
src/api/dependencies/override.py              # New - DI dependencies
src/application/services/public_override_service.py  # New - Query service
tests/unit/api/test_override_routes.py        # New
tests/unit/api/test_override_adapter.py       # New
tests/unit/application/test_public_override_service.py  # New
tests/integration/test_public_override_visibility_integration.py  # New
```

**Files to Modify:**
```
src/api/models/__init__.py                    # Export override models
src/api/routes/__init__.py                    # Export override router
src/api/main.py                               # Register override router
src/application/services/__init__.py          # Export PublicOverrideService
```

### Import Rules (Hexagonal Architecture)

- `api/models/` imports from Pydantic only
- `api/routes/` imports from `api/models/`, `api/dependencies/`, `application/services/`
- `api/adapters/` imports from `api/models/`, `domain/events/`
- `application/services/` imports from `application/ports/`, `domain/`
- NEVER import from `infrastructure/` in `api/` or `application/`

### Testing Standards

- ALL tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Mock `EventStorePort` in unit tests
- Integration tests use real stubs, in-memory event store
- Test no-auth by NOT providing authentication headers

### API Route Path Decision

**Option A: Extend Observer Routes** (Recommended)
- Path: `GET /v1/observer/overrides`
- Rationale: Overrides are part of observable constitutional events
- Follows existing FR44/FR48 patterns in observer.py

**Option B: Separate Override API**
- Path: `GET /v1/overrides`
- More explicit but duplicates auth/rate-limit setup

**Decision: Use Option A** - `/v1/observer/overrides` extends the observer API namespace.

### Cross-Story Integration Points

| Story | Integration | Notes |
|-------|-------------|-------|
| 5.1 | OverrideEventPayload | Events to expose publicly |
| 5.2 | Duration/Reason | Visible in public response |
| 5.4 | Witness attribution | CT-12 compliance visible |
| 5.5 | Trend analysis | Queries same data |
| 4.1 | Rate limiting | Reuse ObserverRateLimiter |
| 4.3 | Date filtering | Reuse filter patterns |

### Security Considerations

- **FR25 Explicit**: Keeper identity MUST be visible (override transparency)
- **No PII concerns**: Keeper IDs are system identifiers, not personal data
- **Rate limiting**: Apply same limits as observer (FR48)
- **Read-only**: This story is query-only, no mutations

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-5.3] - Story definition
- [Source: _bmad-output/planning-artifacts/architecture.md#FR25] - Override visibility requirement
- [Source: src/api/routes/observer.py] - Observer API patterns
- [Source: src/api/models/observer.py] - Response model patterns
- [Source: src/domain/events/override_event.py] - Override event structure
- [Source: _bmad-output/implementation-artifacts/stories/5-1-override-immediate-logging.md] - Story 5.1 patterns
- [Source: _bmad-output/implementation-artifacts/stories/5-2-keeper-attribution-with-scope-and-duration.md] - Story 5.2 patterns

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Clean implementation with no debugging issues.

### Completion Notes List

- All 7 tasks completed successfully
- 43 unit tests passing
- 21 integration tests passing
- Total: 64 new tests
- FR25 (Public Override Visibility) fully implemented
- FR44 (No auth required) verified
- FR48 (Rate limiting) applied
- CT-12 (Witness accountability) included in responses

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-07 | Story created with comprehensive context | Create-Story Workflow (Opus 4.5) |
| 2026-01-07 | Implementation complete - all acceptance criteria verified | Dev-Story Workflow (Opus 4.5) |

### File List

**Created:**
- `src/api/models/override.py` - API response models
- `src/api/routes/override.py` - Override routes
- `src/api/adapters/override.py` - Event to response adapter
- `src/api/dependencies/override.py` - DI dependencies
- `src/application/services/public_override_service.py` - Query service
- `tests/unit/api/test_override_routes.py` - Route unit tests (17 tests)
- `tests/unit/api/test_override_adapter.py` - Adapter unit tests (14 tests)
- `tests/unit/application/test_public_override_service.py` - Service unit tests (12 tests)
- `tests/integration/test_public_override_visibility_integration.py` - Integration tests (21 tests)

**Modified:**
- `src/api/models/__init__.py` - Export override models
- `src/api/routes/__init__.py` - Export override router
- `src/api/main.py` - Register override router
- `src/application/services/__init__.py` - Export PublicOverrideService

