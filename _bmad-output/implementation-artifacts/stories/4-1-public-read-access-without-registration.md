# Story 4.1: Public Read Access Without Registration (FR44)

## Story

**As an** external observer,
**I want** to access events without registration,
**So that** verification is not gatekept.

## Status

Status: done

## Context

### Business Context
This is the first story in Epic 4 (Observer Verification Interface). The core principle is that external auditors and observers must be able to independently verify chain integrity without any barriers. Registration would create a gatekeeper that could selectively deny verification access, undermining the constitutional promise of transparency.

Key business drivers:
1. **Trust through verification**: External parties must verify claims without relying on the system's word
2. **No preferential treatment**: Anonymous and registered users get identical rate limits (FR48)
3. **Constitutional transparency**: The Archon 72 system's legitimacy depends on observer verification capability

### Technical Context
- **ADR-8**: Observer Consistency + Genesis Anchor governs observer API design
- **Epic dependencies**:
  - Epic 1 (Event Store) provides the foundational event data
  - Epic 3 (Halt & Fork Detection) provides halt status awareness
  - This story enables future Epic 4 stories (verification toolkit, Merkle proofs)
- **Existing API**: Basic health endpoint exists at `/v1/health` in `src/api/routes/health.py`
- **Event Store Port**: `src/application/ports/event_store.py` provides `get_events_by_sequence_range`, `get_event_by_id`, `get_event_by_sequence`

### Dependencies
- **Story 1.1**: Event store schema with events table
- **Story 1.5**: Sequence numbers and observer query methods
- **Story 3.10**: Checkpoint query capability (for future stories)

### Constitutional Constraints
- **FR44**: Public read access without registration - NO authentication required for read endpoints
- **FR48**: Rate limits identical for anonymous and authenticated users
- **CT-11**: Silent failure destroys legitimacy - API errors must be visible, not hidden
- **CT-12**: Witnessing creates accountability - observer access enables external witnessing
- **CT-13**: Integrity outranks availability - halt state must be respected

### Architecture Decision
Per ADR-8 (Observer Consistency + Genesis Anchor):
1. Observer API runs as separate process (`src/processes/observer/`)
2. Genesis anchor provides trust root for verification
3. Checkpoints provide periodic anchors for light verification
4. API must be highly available (99.9% SLA per Story 4.9)

For this first story:
1. Create public observer API routes (no auth middleware)
2. Expose events with full hash chain data
3. Respect halt state (read-only access during halt)
4. Match rate limits for all users

## Acceptance Criteria

### AC1: Unauthenticated GET request returns event data
**Given** the public events API
**When** I make an unauthenticated GET request
**Then** I receive event data
**And** no login or API key is required

### AC2: Rate limits identical for anonymous vs authenticated
**Given** identical rate limits (FR48)
**When** I compare anonymous vs authenticated access
**Then** rate limits are the same for both
**And** no preferential treatment for registered users

### AC3: Authentication is optional for all read endpoints
**Given** the API endpoint
**When** I examine the docs
**Then** authentication is optional
**And** all read endpoints work without auth

## Tasks

### Task 1: Create ObserverEventsResponse schema
Create Pydantic response model for observer event queries.

**Files:**
- `src/api/models/observer.py` (new)
- `tests/unit/api/test_observer_models.py` (new)

**Test Cases (RED):**
- `test_observer_event_response_fields`
- `test_observer_event_response_includes_hashes`
- `test_observer_events_list_response`
- `test_pagination_metadata_response`
- `test_response_datetime_iso8601_format`

**Implementation (GREEN):**
```python
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ObserverEventResponse(BaseModel):
    """Single event response for observer API.

    Includes all hash chain data for independent verification.
    Per FR44: No fields are hidden from observers.
    """
    event_id: UUID
    sequence: int
    event_type: str
    payload: dict  # Raw payload for verification
    content_hash: str
    prev_hash: str
    signature: str
    agent_id: str
    witness_id: str
    witness_signature: str
    local_timestamp: datetime
    authority_timestamp: Optional[datetime] = None
    hash_algorithm_version: str = Field(default="SHA256")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z" if v else None
        }


class PaginationMetadata(BaseModel):
    """Pagination info for list responses."""
    total_count: int
    offset: int
    limit: int
    has_more: bool


class ObserverEventsListResponse(BaseModel):
    """List response for observer events query."""
    events: list[ObserverEventResponse]
    pagination: PaginationMetadata
```

### Task 2: Create ObserverRateLimiter middleware
Rate limiter that applies identical limits regardless of authentication.

**Files:**
- `src/api/middleware/rate_limiter.py` (new)
- `tests/unit/api/test_rate_limiter.py` (new)

**Test Cases (RED):**
- `test_rate_limiter_applies_to_anonymous`
- `test_rate_limiter_applies_to_authenticated`
- `test_rate_limits_identical_anonymous_authenticated`
- `test_rate_limit_exceeded_returns_429`
- `test_rate_limit_headers_included`
- `test_rate_limit_window_resets`

**Implementation (GREEN):**
```python
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Request, HTTPException


class ObserverRateLimiter:
    """Rate limiter for observer API.

    Per FR48: Rate limits MUST be identical for anonymous
    and authenticated users. No preferential treatment.

    Constitutional Constraint:
    - Equal access is a transparency guarantee
    - Different limits would create gatekeeping
    """

    # Same limits for ALL users - constitutional requirement
    REQUESTS_PER_MINUTE = 60
    BURST_LIMIT = 100

    def __init__(self) -> None:
        self._request_counts: dict[str, list[datetime]] = {}

    def _get_client_key(self, request: Request) -> str:
        """Get client identifier - IP-based, not auth-based.

        Per FR48: We identify by IP, not by auth status.
        This ensures anonymous and authenticated get same treatment.
        """
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def check_rate_limit(self, request: Request) -> None:
        """Check and enforce rate limit.

        Raises HTTPException(429) if limit exceeded.
        """
        # Implementation with sliding window
        ...
```

### Task 3: Create observer events router
FastAPI router for public event access endpoints.

**Files:**
- `src/api/routes/observer.py` (new)
- `tests/unit/api/test_observer_routes.py` (new)

**Test Cases (RED):**
- `test_get_events_no_auth_required`
- `test_get_events_returns_list`
- `test_get_events_includes_hashes`
- `test_get_events_pagination`
- `test_get_event_by_id_no_auth`
- `test_get_event_by_sequence_no_auth`
- `test_get_events_respects_halt_state`
- `test_rate_limit_applied`

**Implementation (GREEN):**
```python
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from src.api.middleware.rate_limiter import ObserverRateLimiter
from src.api.models.observer import (
    ObserverEventResponse,
    ObserverEventsListResponse,
    PaginationMetadata,
)
from src.application.ports.event_store import EventStorePort

router = APIRouter(prefix="/v1/observer", tags=["observer"])


# No authentication dependency - this is intentional per FR44
# Rate limiter applies equally to all users per FR48


@router.get("/events", response_model=ObserverEventsListResponse)
async def get_events(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    event_store: EventStorePort = Depends(get_event_store),
) -> ObserverEventsListResponse:
    """Get events for observer verification.

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    Returns events with full hash chain data for
    independent verification.
    """
    # Implementation
    ...


@router.get("/events/{event_id}", response_model=ObserverEventResponse)
async def get_event_by_id(
    event_id: UUID,
    event_store: EventStorePort = Depends(get_event_store),
) -> ObserverEventResponse:
    """Get single event by ID.

    No authentication required (FR44).
    """
    ...


@router.get("/events/sequence/{sequence}", response_model=ObserverEventResponse)
async def get_event_by_sequence(
    sequence: int,
    event_store: EventStorePort = Depends(get_event_store),
) -> ObserverEventResponse:
    """Get single event by sequence number.

    No authentication required (FR44).
    Sequence is the authoritative ordering (Story 1.5).
    """
    ...
```

### Task 4: Create EventToObserverAdapter
Adapter to transform domain Event to API response.

**Files:**
- `src/api/adapters/observer.py` (new)
- `tests/unit/api/test_observer_adapter.py` (new)

**Test Cases (RED):**
- `test_adapt_event_to_response`
- `test_adapter_includes_all_hashes`
- `test_adapter_formats_datetime_correctly`
- `test_adapter_handles_null_authority_timestamp`
- `test_adapt_list_of_events`

**Implementation (GREEN):**
```python
from src.api.models.observer import ObserverEventResponse
from src.domain.events import Event


class EventToObserverAdapter:
    """Adapts domain Event to observer API response.

    Per FR44: ALL event data is exposed to observers.
    No fields are hidden or transformed.
    """

    @staticmethod
    def to_response(event: Event) -> ObserverEventResponse:
        """Convert domain event to API response."""
        return ObserverEventResponse(
            event_id=event.event_id,
            sequence=event.sequence,
            event_type=event.event_type,
            payload=event.payload,
            content_hash=event.content_hash,
            prev_hash=event.prev_hash,
            signature=event.signature,
            agent_id=event.agent_id,
            witness_id=event.witness_id,
            witness_signature=event.witness_signature,
            local_timestamp=event.local_timestamp,
            authority_timestamp=event.authority_timestamp,
            hash_algorithm_version=event.hash_algorithm_version,
        )

    @staticmethod
    def to_response_list(events: list[Event]) -> list[ObserverEventResponse]:
        """Convert list of domain events to API responses."""
        return [EventToObserverAdapter.to_response(e) for e in events]
```

### Task 5: Create ObserverService application service
Application service for observer operations.

**Files:**
- `src/application/services/observer_service.py` (new)
- `tests/unit/application/test_observer_service.py` (new)

**Test Cases (RED):**
- `test_get_events_returns_events`
- `test_get_events_with_pagination`
- `test_get_event_by_id_found`
- `test_get_event_by_id_not_found`
- `test_get_event_by_sequence_found`
- `test_get_event_by_sequence_not_found`
- `test_service_respects_halt_for_reads`

**Implementation (GREEN):**
```python
from typing import Optional
from uuid import UUID

from src.application.ports.event_store import EventStorePort
from src.application.ports.halt_checker import HaltChecker
from src.domain.events import Event


class ObserverService:
    """Application service for observer operations.

    Provides observer access to events without authentication.
    Per FR44: All read operations are public.
    Per CT-13: Reads allowed during halt (Story 3.5).
    """

    def __init__(
        self,
        event_store: EventStorePort,
        halt_checker: HaltChecker,
    ) -> None:
        self._event_store = event_store
        self._halt_checker = halt_checker

    async def get_events(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Event], int]:
        """Get events with pagination.

        Returns:
            Tuple of (events, total_count).
        """
        # During halt, reads are still allowed (Story 3.5)
        # No halt check needed for read operations

        total = await self._event_store.count_events()
        max_seq = await self._event_store.get_max_sequence()

        start_seq = offset + 1  # Sequences are 1-based
        end_seq = min(start_seq + limit - 1, max_seq)

        if start_seq > max_seq:
            return [], total

        events = await self._event_store.get_events_by_sequence_range(
            start=start_seq,
            end=end_seq,
        )

        return events, total

    async def get_event_by_id(self, event_id: UUID) -> Optional[Event]:
        """Get single event by ID."""
        return await self._event_store.get_event_by_id(event_id)

    async def get_event_by_sequence(self, sequence: int) -> Optional[Event]:
        """Get single event by sequence number."""
        return await self._event_store.get_event_by_sequence(sequence)
```

### Task 6: Register observer routes in main app
Add observer router to FastAPI application.

**Files:**
- `src/api/main.py` (modify)
- `tests/integration/test_observer_api_integration.py` (new)

**Test Cases (RED - integration):**
- `test_observer_endpoints_accessible_without_auth`
- `test_observer_returns_real_events`
- `test_observer_pagination_works`
- `test_observer_rate_limit_enforced`
- `test_observer_api_during_halt_state`

**Implementation (GREEN):**
```python
# In src/api/main.py, add:
from src.api.routes.observer import router as observer_router

# Register the observer router
app.include_router(observer_router)
```

### Task 7: Create dependencies for observer routes
Dependency injection setup for observer components.

**Files:**
- `src/api/dependencies/observer.py` (new)
- `tests/unit/api/test_observer_dependencies.py` (new)

**Test Cases (RED):**
- `test_get_observer_service_returns_instance`
- `test_get_rate_limiter_returns_singleton`
- `test_dependencies_use_configured_limits`

**Implementation (GREEN):**
```python
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from src.api.middleware.rate_limiter import ObserverRateLimiter
from src.application.ports.event_store import EventStorePort
from src.application.ports.halt_checker import HaltChecker
from src.application.services.observer_service import ObserverService


@lru_cache(maxsize=1)
def get_rate_limiter() -> ObserverRateLimiter:
    """Get singleton rate limiter."""
    return ObserverRateLimiter()


def get_observer_service(
    event_store: Annotated[EventStorePort, Depends(get_event_store)],
    halt_checker: Annotated[HaltChecker, Depends(get_halt_checker)],
) -> ObserverService:
    """Get observer service instance."""
    return ObserverService(
        event_store=event_store,
        halt_checker=halt_checker,
    )
```

### Task 8: Integration tests for public access
End-to-end tests verifying public access without auth.

**Files:**
- `tests/integration/test_public_read_access_integration.py` (new)

**Test Cases:**
- `test_no_auth_header_allowed`
- `test_events_returned_with_full_hash_data`
- `test_rate_limit_identical_anonymous_authenticated`
- `test_pagination_works_correctly`
- `test_event_by_id_accessible`
- `test_event_by_sequence_accessible`
- `test_404_for_missing_event`
- `test_constitutional_compliance_fr44`
- `test_constitutional_compliance_fr48`

### Task 9: Update __init__.py exports
Update all package __init__.py files.

**Files:**
- `src/api/models/__init__.py` (modify)
- `src/api/routes/__init__.py` (modify)
- `src/api/middleware/__init__.py` (new)
- `src/api/adapters/__init__.py` (new)
- `src/api/dependencies/__init__.py` (new)
- `src/application/services/__init__.py` (modify)

## Technical Notes

### Implementation Order
1. Tasks 1, 4: Response models and adapter (foundation)
2. Task 2: Rate limiter middleware
3. Task 5: ObserverService application service
4. Tasks 3, 6, 7: Routes, registration, dependencies
5. Tasks 8, 9: Integration tests and exports

### Testing Strategy
- Unit tests for each component in isolation
- Integration tests for full API flow without authentication
- Verify rate limits are identical for anonymous/authenticated
- All tests follow red-green-refactor TDD cycle

### Constitutional Compliance Matrix
| Requirement | Implementation |
|-------------|----------------|
| FR44 | No auth middleware on observer routes |
| FR48 | ObserverRateLimiter uses IP-based limits only |
| CT-11 | Errors returned as RFC 7807 responses |
| CT-12 | Observer access enables external witnessing |
| CT-13 | Reads allowed during halt (per Story 3.5) |

### Key Design Decisions
1. **No auth middleware**: Observer routes explicitly skip authentication
2. **IP-based rate limiting**: Uses client IP, not auth identity, for rate limits
3. **Full hash exposure**: All hash chain data exposed for independent verification
4. **Halt respects reads**: Per Story 3.5, read-only access during halt

### API Patterns from Existing Code
From `src/api/routes/health.py`:
- Router prefix: `/v1/{resource}`
- Tags for grouping: `tags=["observer"]`
- Response model typing: `response_model=ResponseClass`
- Async handlers: `async def handler() -> Response`

### Patterns from Previous Stories to Follow
From Story 3.10:
- Use Protocol-based ports for dependencies
- Domain models are immutable (`@dataclass(frozen=True)`)
- Services check halt state where appropriate
- Follow hexagonal architecture layers

## Dev Notes

### Project Structure Notes
- API routes: `src/api/routes/observer.py`
- API models: `src/api/models/observer.py`
- API middleware: `src/api/middleware/rate_limiter.py`
- API adapters: `src/api/adapters/observer.py`
- Application services: `src/application/services/observer_service.py`
- API dependencies: `src/api/dependencies/observer.py`

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-4.1]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-8]
- [Source: _bmad-output/project-context.md#Framework-Specific-Rules]
- [Source: src/api/routes/health.py - API pattern reference]
- [Source: src/application/ports/event_store.py - EventStorePort interface]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- All 9 tasks completed successfully
- 60 tests passing (36 unit tests + 11 service tests + 13 integration tests)
- Constitutional constraints FR44 (public access) and FR48 (equal rate limits) verified
- Reads work during halt state per CT-13 / Story 3.5
- Clean TDD red-green-refactor cycle followed throughout

### File List

**New Files Created:**
- `src/api/models/observer.py` - ObserverEventResponse, PaginationMetadata, ObserverEventsListResponse
- `src/api/middleware/__init__.py` - Middleware package init
- `src/api/middleware/rate_limiter.py` - ObserverRateLimiter (FR48 compliant)
- `src/api/adapters/__init__.py` - Adapters package init
- `src/api/adapters/observer.py` - EventToObserverAdapter
- `src/api/dependencies/__init__.py` - Dependencies package init
- `src/api/dependencies/observer.py` - Dependency injection for observer routes
- `src/api/routes/observer.py` - Observer API routes (FR44 - no auth required)
- `src/application/services/observer_service.py` - ObserverService application service
- `tests/unit/api/__init__.py` - API unit test package init
- `tests/unit/api/test_observer_models.py` - 8 tests for response models
- `tests/unit/api/test_rate_limiter.py` - 11 tests for rate limiter
- `tests/unit/api/test_observer_adapter.py` - 9 tests for adapter
- `tests/unit/api/test_observer_routes.py` - 8 tests for routes
- `tests/unit/application/test_observer_service.py` - 11 tests for service
- `tests/integration/test_public_read_access_integration.py` - 13 integration tests

**Modified Files:**
- `src/api/main.py` - Added observer router
- `src/api/models/__init__.py` - Added observer model exports
- `src/api/routes/__init__.py` - Added observer router export
- `src/application/services/__init__.py` - Added ObserverService export
