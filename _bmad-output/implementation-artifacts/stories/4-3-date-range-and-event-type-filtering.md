# Story 4.3: Date Range and Event Type Filtering (FR46)

## Story

**As an** external observer,
**I want** to filter events by date range and event type,
**So that** I can focus my verification on specific periods or event types.

## Status

Status: done

## Context

### Business Context
This is the third story in Epic 4 (Observer Verification Interface). It builds on Stories 4.1 (Public Read Access) and 4.2 (Raw Events with Hashes) by adding filtering capabilities to the observer API.

Key business drivers:
1. **Targeted verification**: Observers don't need to download all events to verify specific periods
2. **Breach investigation**: Filter by event type (e.g., "halt", "breach") to focus on critical events
3. **Regulatory compliance**: Export events within specific date ranges for audit purposes
4. **Performance optimization**: Reduce data transfer by only fetching relevant events

### Technical Context
- **FR46**: Query interface SHALL support date range and event type filtering
- **ADR-8**: Observer Consistency + Genesis Anchor governs observer API design

**Existing Implementation:**
- Story 4.1: Public observer API with pagination (`/v1/observer/events`)
- Story 4.2: Full hash chain data in responses
- ObserverService with get_events() returning paginated events
- EventStorePort with get_events_by_type() and existing indexes

**Spike Analysis (Story 1.9):**
The Observer Query Schema Design Spike confirmed:
- `idx_events_authority_timestamp` EXISTS - supports date range queries
- `idx_events_event_type` EXISTS - supports type filtering
- Combined filter uses index intersection (acceptable performance)
- Optional composite index `(authority_timestamp, event_type)` for optimization

### Dependencies
- **Story 4.1**: Public read access endpoints (DONE)
- **Story 4.2**: Raw events with hashes (DONE)
- **Story 1.9**: Observer query schema spike (DONE) - confirmed index support

### Constitutional Constraints
- **FR44**: Public read access without registration - filters must work without auth
- **FR46**: Query interface SHALL support date range and event type filtering
- **FR48**: Rate limits identical for all users
- **CT-13**: Reads allowed during halt

### Architecture Decision
Per spike report (Story 1.9):
- Date range uses `authority_timestamp` column (not `local_timestamp`)
- Event types are comma-separated in query parameter
- Filters combine with AND logic
- Pagination must work with filters

Query patterns identified:
```sql
-- Date range filter
SELECT * FROM events
WHERE authority_timestamp BETWEEN $1 AND $2
ORDER BY sequence;

-- Event type filter (multiple types)
SELECT * FROM events
WHERE event_type IN ($1, $2, $3)
ORDER BY sequence;

-- Combined filter (most common)
SELECT * FROM events
WHERE authority_timestamp BETWEEN $1 AND $2
  AND event_type = $3
ORDER BY sequence
LIMIT $4 OFFSET $5;
```

## Acceptance Criteria

### AC1: Date range filtering with ISO 8601 format
**Given** the events query API
**When** I specify `start_date` and `end_date` parameters
**Then** only events within that range are returned
**And** dates use ISO 8601 format (e.g., "2026-01-01T00:00:00Z")

### AC2: Event type filtering with multiple types
**Given** the events query API
**When** I specify `event_type` parameter
**Then** only events of that type are returned
**And** multiple types can be specified (comma-separated)

### AC3: Combined filtering with AND logic
**Given** combined filtering
**When** I specify both date range and event type
**Then** filters are applied with AND logic
**And** pagination is supported for large result sets

### AC4: Partial date range support (NEW)
**Given** the events query API
**When** I specify only `start_date` (no `end_date`)
**Then** all events from start_date to now are returned
**When** I specify only `end_date` (no `start_date`)
**Then** all events from beginning to end_date are returned

## Tasks

### Task 1: Add filter parameters to get_events endpoint

Extend the existing GET /v1/observer/events endpoint with filter parameters.

**Files:**
- `src/api/routes/observer.py` (modify)
- `tests/unit/api/test_observer_routes.py` (modify)

**Test Cases (RED):**
- `test_get_events_with_start_date_filter`
- `test_get_events_with_end_date_filter`
- `test_get_events_with_date_range_filter`
- `test_get_events_with_single_event_type`
- `test_get_events_with_multiple_event_types`
- `test_get_events_with_combined_filters`
- `test_date_params_iso8601_format`
- `test_invalid_date_format_returns_422`

**Implementation (GREEN):**
```python
from datetime import datetime
from typing import Optional

@router.get("/events", response_model=ObserverEventsListResponse)
async def get_events(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    start_date: Optional[datetime] = Query(
        default=None,
        description="Filter events from this date (ISO 8601 format)",
    ),
    end_date: Optional[datetime] = Query(
        default=None,
        description="Filter events until this date (ISO 8601 format)",
    ),
    event_type: Optional[str] = Query(
        default=None,
        description="Filter by event type(s), comma-separated",
    ),
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> ObserverEventsListResponse:
    """Get events for observer verification with optional filters.

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    Filtering (FR46):
    - start_date: ISO 8601 datetime, events from this timestamp
    - end_date: ISO 8601 datetime, events until this timestamp
    - event_type: Comma-separated event types (e.g., "vote,halt,breach")

    Filters are combined with AND logic.
    """
    await rate_limiter.check_rate_limit(request)

    # Parse event types
    event_types = None
    if event_type:
        event_types = [t.strip() for t in event_type.split(",") if t.strip()]

    # Get filtered events
    events, total = await observer_service.get_events_filtered(
        limit=limit,
        offset=offset,
        start_date=start_date,
        end_date=end_date,
        event_types=event_types,
    )

    # Convert to API response
    event_responses = EventToObserverAdapter.to_response_list(events)
    has_more = (offset + len(events)) < total

    return ObserverEventsListResponse(
        events=event_responses,
        pagination=PaginationMetadata(
            total_count=total,
            offset=offset,
            limit=limit,
            has_more=has_more,
        ),
    )
```

### Task 2: Add filtered query methods to EventStorePort

Extend the EventStorePort interface with filtered query methods.

**Files:**
- `src/application/ports/event_store.py` (modify)
- `tests/unit/application/test_event_store_port.py` (modify if exists)

**Test Cases (RED):**
- `test_port_defines_get_events_filtered`
- `test_port_defines_count_events_filtered`

**Implementation (GREEN):**
```python
@abstractmethod
async def get_events_filtered(
    self,
    limit: int = 100,
    offset: int = 0,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    event_types: Optional[list[str]] = None,
) -> list["Event"]:
    """Get events with optional filters.

    Used by observer API for filtered queries (FR46).

    Args:
        limit: Maximum number of events to return.
        offset: Number of events to skip.
        start_date: Filter events from this timestamp (authority_timestamp).
        end_date: Filter events until this timestamp (authority_timestamp).
        event_types: Filter by event types (OR within types, AND with dates).

    Returns:
        List of events matching filters, ordered by sequence.

    Raises:
        EventStoreError: For storage-related failures.
    """
    ...

@abstractmethod
async def count_events_filtered(
    self,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    event_types: Optional[list[str]] = None,
) -> int:
    """Count events matching filters.

    Args:
        start_date: Filter events from this timestamp.
        end_date: Filter events until this timestamp.
        event_types: Filter by event types.

    Returns:
        Count of matching events.

    Raises:
        EventStoreError: For storage-related failures.
    """
    ...
```

### Task 3: Add get_events_filtered to ObserverService

Add service method that orchestrates filtered event queries.

**Files:**
- `src/application/services/observer_service.py` (modify)
- `tests/unit/application/test_observer_service.py` (modify)

**Test Cases (RED):**
- `test_get_events_filtered_no_filters`
- `test_get_events_filtered_by_start_date`
- `test_get_events_filtered_by_end_date`
- `test_get_events_filtered_by_date_range`
- `test_get_events_filtered_by_single_type`
- `test_get_events_filtered_by_multiple_types`
- `test_get_events_filtered_combined`
- `test_get_events_filtered_with_pagination`

**Implementation (GREEN):**
```python
async def get_events_filtered(
    self,
    limit: int = 100,
    offset: int = 0,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    event_types: Optional[list[str]] = None,
) -> tuple[list[Event], int]:
    """Get events with optional filters (FR46).

    Per FR44: This is a public read operation, no auth required.
    Per CT-13: Reads are allowed during halt.
    Per FR46: Supports date range and event type filtering.

    Args:
        limit: Maximum number of events to return.
        offset: Number of events to skip.
        start_date: Filter events from this timestamp.
        end_date: Filter events until this timestamp.
        event_types: Filter by event types.

    Returns:
        Tuple of (events, total_count).
    """
    # Get total count for pagination
    total = await self._event_store.count_events_filtered(
        start_date=start_date,
        end_date=end_date,
        event_types=event_types,
    )

    # Get filtered events
    events = await self._event_store.get_events_filtered(
        limit=limit,
        offset=offset,
        start_date=start_date,
        end_date=end_date,
        event_types=event_types,
    )

    return events, total
```

### Task 4: Implement filtered queries in event store stub

Add stub implementation for filtered query methods.

**Files:**
- `src/infrastructure/stubs/event_store_stub.py` (new or modify existing)
- `tests/unit/infrastructure/test_event_store_stub.py` (new or modify)

**Test Cases (RED):**
- `test_stub_get_events_filtered_no_filter`
- `test_stub_get_events_filtered_by_date_range`
- `test_stub_get_events_filtered_by_type`
- `test_stub_get_events_filtered_combined`
- `test_stub_count_events_filtered`

**Implementation (GREEN):**
```python
async def get_events_filtered(
    self,
    limit: int = 100,
    offset: int = 0,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    event_types: Optional[list[str]] = None,
) -> list[Event]:
    """Get events with optional filters (stub implementation)."""
    # Start with all events ordered by sequence
    filtered = sorted(self._events.values(), key=lambda e: e.sequence)

    # Apply date range filter on authority_timestamp
    if start_date:
        filtered = [e for e in filtered if e.authority_timestamp >= start_date]
    if end_date:
        filtered = [e for e in filtered if e.authority_timestamp <= end_date]

    # Apply event type filter (OR within types)
    if event_types:
        filtered = [e for e in filtered if e.event_type in event_types]

    # Apply pagination
    return filtered[offset:offset + limit]

async def count_events_filtered(
    self,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    event_types: Optional[list[str]] = None,
) -> int:
    """Count events matching filters (stub implementation)."""
    # Reuse filter logic
    events = await self.get_events_filtered(
        limit=len(self._events),
        offset=0,
        start_date=start_date,
        end_date=end_date,
        event_types=event_types,
    )
    return len(events)
```

### Task 5: Create FilterParams model for API documentation

Create a model to document and validate filter parameters.

**Files:**
- `src/api/models/observer.py` (modify)
- `tests/unit/api/test_observer_models.py` (modify)

**Test Cases (RED):**
- `test_filter_params_example_in_schema`
- `test_filtered_events_response_example`

**Implementation (GREEN):**
```python
class EventFilterParams(BaseModel):
    """Filter parameters for event queries (FR46).

    All filters are optional. When multiple filters are provided,
    they are combined with AND logic.

    Attributes:
        start_date: Filter events from this timestamp (inclusive).
        end_date: Filter events until this timestamp (inclusive).
        event_type: Filter by event type(s), comma-separated.
    """

    start_date: Optional[datetime] = Field(
        default=None,
        description="Filter events from this date (ISO 8601 format)",
        json_schema_extra={"example": "2026-01-01T00:00:00Z"},
    )
    end_date: Optional[datetime] = Field(
        default=None,
        description="Filter events until this date (ISO 8601 format)",
        json_schema_extra={"example": "2026-01-31T23:59:59Z"},
    )
    event_type: Optional[str] = Field(
        default=None,
        description="Filter by event type(s), comma-separated",
        json_schema_extra={"example": "vote,halt,breach"},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "start_date": "2026-01-01T00:00:00Z",
                    "end_date": "2026-01-31T23:59:59Z",
                    "event_type": "vote,halt",
                },
                {
                    "start_date": "2026-01-15T00:00:00Z",
                    "event_type": "breach",
                },
            ]
        }
    }
```

### Task 6: Integration tests for FR46 compliance

Comprehensive integration tests for date range and event type filtering.

**Files:**
- `tests/integration/test_date_range_filtering_integration.py` (new)

**Test Cases:**
- `test_fr46_date_range_filtering_works`
- `test_fr46_event_type_single_filter`
- `test_fr46_event_type_multiple_comma_separated`
- `test_fr46_combined_filters_and_logic`
- `test_fr46_pagination_with_filters`
- `test_fr46_empty_result_on_no_match`
- `test_fr46_partial_date_range_start_only`
- `test_fr46_partial_date_range_end_only`
- `test_fr46_iso8601_date_format_required`
- `test_fr46_filters_work_without_auth`
- `test_fr46_rate_limits_apply_to_filtered`

**Implementation (GREEN):**
```python
@pytest.mark.asyncio
async def test_fr46_date_range_filtering_works(
    client: TestClient,
    event_store_with_events: EventStorePort,
):
    """Verify date range filtering per FR46."""
    # Given: Events spanning multiple days
    start = "2026-01-15T00:00:00Z"
    end = "2026-01-16T23:59:59Z"

    # When: Query with date range
    response = client.get(
        f"/v1/observer/events?start_date={start}&end_date={end}"
    )

    # Then: Only events in range returned
    assert response.status_code == 200
    data = response.json()
    for event in data["events"]:
        ts = datetime.fromisoformat(event["authority_timestamp"].replace("Z", "+00:00"))
        assert ts >= datetime.fromisoformat(start.replace("Z", "+00:00"))
        assert ts <= datetime.fromisoformat(end.replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_fr46_event_type_multiple_comma_separated(
    client: TestClient,
    event_store_with_events: EventStorePort,
):
    """Verify multiple event types can be specified comma-separated."""
    # Given: Events of different types exist

    # When: Query with multiple types
    response = client.get(
        "/v1/observer/events?event_type=vote,halt"
    )

    # Then: Events of both types returned
    assert response.status_code == 200
    data = response.json()
    types_found = {e["event_type"] for e in data["events"]}
    assert types_found <= {"vote", "halt"}  # Subset of allowed types


@pytest.mark.asyncio
async def test_fr46_combined_filters_and_logic(
    client: TestClient,
    event_store_with_events: EventStorePort,
):
    """Verify combined filters use AND logic."""
    # Given: Events with different types and dates
    start = "2026-01-15T00:00:00Z"
    end = "2026-01-16T23:59:59Z"
    event_type = "vote"

    # When: Query with both date and type filters
    response = client.get(
        f"/v1/observer/events?start_date={start}&end_date={end}&event_type={event_type}"
    )

    # Then: Only events matching BOTH criteria returned
    assert response.status_code == 200
    data = response.json()
    for event in data["events"]:
        assert event["event_type"] == event_type
        ts = datetime.fromisoformat(event["authority_timestamp"].replace("Z", "+00:00"))
        assert ts >= datetime.fromisoformat(start.replace("Z", "+00:00"))
        assert ts <= datetime.fromisoformat(end.replace("Z", "+00:00"))
```

### Task 7: Update existing event store stub/adapter

Ensure the existing event store infrastructure supports filtered queries.

**Files:**
- Check if `src/infrastructure/adapters/persistence/` has event store adapter
- Update stub in `src/infrastructure/stubs/` if not already done

**Test Cases (RED):**
- `test_existing_stub_supports_filtered_queries`

**Implementation:**
If using Supabase adapter, add SQL query building:
```python
async def get_events_filtered(
    self,
    limit: int = 100,
    offset: int = 0,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    event_types: Optional[list[str]] = None,
) -> list[Event]:
    """Get filtered events from Supabase."""
    query = self._client.table("events").select("*")

    # Apply filters
    if start_date:
        query = query.gte("authority_timestamp", start_date.isoformat())
    if end_date:
        query = query.lte("authority_timestamp", end_date.isoformat())
    if event_types:
        query = query.in_("event_type", event_types)

    # Order and paginate
    query = query.order("sequence").range(offset, offset + limit - 1)

    response = await query.execute()
    return [self._to_event(row) for row in response.data]
```

### Task 8: Update __init__.py exports

Ensure all new models and methods are properly exported.

**Files:**
- `src/api/models/__init__.py` (modify if needed)
- `src/application/services/__init__.py` (modify if needed)

## Technical Notes

### Implementation Order
1. Task 2: Add port interface methods (foundation)
2. Task 4: Implement stub methods (enables testing)
3. Task 3: Add service methods (orchestration)
4. Task 5: Create filter params model (documentation)
5. Task 1: Add route parameters (API layer)
6. Task 6: Integration tests
7. Task 7: Update adapters if needed
8. Task 8: Exports

### Testing Strategy
- Unit tests for each component in isolation
- Integration tests for full API flow with filters
- Test edge cases: empty results, partial date ranges, invalid formats
- All tests follow red-green-refactor TDD cycle

### Constitutional Compliance Matrix
| Requirement | Implementation |
|-------------|----------------|
| FR44 | Filtered endpoints require no authentication |
| FR46 | start_date, end_date, event_type parameters |
| FR48 | Rate limiter applied to filtered requests |
| CT-13 | No halt check for read operations |

### Key Design Decisions
1. **ISO 8601 dates**: FastAPI auto-parses datetime query params
2. **Comma-separated types**: Simple parsing, no array syntax needed in URL
3. **AND logic**: Filters combine restrictively, matching SQL WHERE AND
4. **Pagination preserved**: Filters don't break existing pagination

### Query Optimization Notes
From spike report (Story 1.9):
- Current indexes support these queries with acceptable performance
- Combined filter uses index intersection (BitmapAnd)
- Optional: Add composite index `(authority_timestamp, event_type)` if benchmarks show need
- Performance at 10M scale: <100ms for combined queries with pagination

### Date Handling
- `authority_timestamp` is used (not `local_timestamp`) per architecture
- ISO 8601 format: "2026-01-01T00:00:00Z"
- FastAPI automatically validates datetime format
- Invalid format returns 422 Unprocessable Entity

### Patterns from Previous Stories to Follow
From Story 4.1/4.2:
- Router prefix: `/v1/observer`
- No auth dependency (FR44)
- Rate limiter on all endpoints (FR48)
- Async handlers
- EventToObserverAdapter for response conversion

## Dev Notes

### Project Structure Notes
- Routes: `src/api/routes/observer.py`
- Models: `src/api/models/observer.py`
- Service: `src/application/services/observer_service.py`
- Port: `src/application/ports/event_store.py`
- Stub: `src/infrastructure/stubs/` (if exists)

### Previous Story Intelligence
From Story 4.1 (60 tests):
- ObserverService uses EventStorePort for data access
- Rate limiter uses IP-based tracking
- Pagination works with offset/limit
- Events ordered by sequence

From Story 4.2 (62 tests):
- Response includes all hash fields
- Adapter handles type conversions
- No transformation of payload data

### API Pattern Reference
Existing endpoint signature:
```python
@router.get("/events", response_model=ObserverEventsListResponse)
async def get_events(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> ObserverEventsListResponse:
```

New parameters to add:
- `start_date: Optional[datetime] = Query(default=None)`
- `end_date: Optional[datetime] = Query(default=None)`
- `event_type: Optional[str] = Query(default=None)`

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-4.3]
- [Source: docs/spikes/1-9-observer-query-schema-spike-report.md]
- [Source: _bmad-output/implementation-artifacts/stories/4-1-public-read-access-without-registration.md]
- [Source: _bmad-output/implementation-artifacts/stories/4-2-raw-events-with-hashes.md]
- [Source: src/api/routes/observer.py - existing endpoint]
- [Source: src/application/ports/event_store.py - EventStorePort interface]
- [Source: src/application/services/observer_service.py - ObserverService]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - all tests passed on final run.

### Completion Notes List

1. All 8 tasks completed via TDD approach
2. 125 tests passing across unit and integration test files
3. Fixed SQL syntax error in integration test (CAST instead of ::jsonb)
4. Added filtered methods to both EventStoreStub in stubs module and dependency stub
5. Constitutional compliance verified: FR44, FR46, FR48, CT-13

### File List

Modified:
- `src/application/ports/event_store.py` - Added get_events_filtered, count_events_filtered methods
- `src/application/services/observer_service.py` - Added get_events_filtered method
- `src/api/routes/observer.py` - Added start_date, end_date, event_type query parameters
- `src/api/models/observer.py` - Added EventFilterParams model
- `src/api/models/__init__.py` - Added exports for new models
- `src/api/dependencies/observer.py` - Added filtered methods to stub
- `src/infrastructure/stubs/__init__.py` - Added EventStoreStub export

Created:
- `src/infrastructure/stubs/event_store_stub.py` - Full EventStorePort implementation
- `tests/unit/infrastructure/test_event_store_stub.py` - 16 tests
- `tests/integration/test_date_range_filtering_integration.py` - 11 tests

Test files modified:
- `tests/unit/application/test_event_store_port.py` - 6 tests added
- `tests/unit/application/test_observer_service.py` - 8 tests added
- `tests/unit/api/test_observer_models.py` - 9 tests added
- `tests/unit/api/test_observer_routes.py` - 10 tests added
