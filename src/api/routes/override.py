"""Override API routes (Story 5.3, FR25).

FastAPI router for public override visibility endpoints.
All override data is publicly accessible without authentication.

Constitutional Constraints:
- FR25: All overrides SHALL be publicly visible
- FR44: No authentication required for read endpoints
- FR48: Rate limits identical for anonymous and authenticated users
- CT-12: Witnessing creates accountability - witness attribution visible
- CT-11: Silent failure destroys legitimacy - errors must be visible
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.api.adapters.override import EventToOverrideAdapter
from src.api.dependencies.observer import get_rate_limiter
from src.api.dependencies.override import get_public_override_service
from src.api.middleware.rate_limiter import ObserverRateLimiter
from src.api.models.observer import PaginationMetadata
from src.api.models.override import OverrideEventResponse, OverrideEventsListResponse
from src.application.services.public_override_service import PublicOverrideService

router = APIRouter(prefix="/v1/observer/overrides", tags=["overrides"])


# No authentication dependency - this is intentional per FR44
# Rate limiter applies equally to all users per FR48


@router.get("", response_model=OverrideEventsListResponse)
async def get_overrides(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    start_date: datetime | None = Query(
        default=None,
        description="Filter overrides from this date (ISO 8601 format)",
    ),
    end_date: datetime | None = Query(
        default=None,
        description="Filter overrides until this date (ISO 8601 format)",
    ),
    public_override_service: PublicOverrideService = Depends(
        get_public_override_service
    ),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> OverrideEventsListResponse:
    """Get all override events for public transparency (FR25).

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    All override data is fully visible including:
    - Keeper identity (NOT anonymized per FR25)
    - Override scope and reason
    - Duration and expiration
    - Witness attribution (CT-12)

    Args:
        request: The FastAPI request object.
        limit: Maximum number of overrides to return (1-1000).
        offset: Number of overrides to skip.
        start_date: Filter overrides from this date (inclusive).
        end_date: Filter overrides until this date (inclusive).
        public_override_service: Injected override service.
        rate_limiter: Injected rate limiter.

    Returns:
        List of override events with pagination metadata.
    """
    # Apply rate limiting (FR48 - same limits for all users)
    await rate_limiter.check_rate_limit(request)

    # Get override events
    overrides, total = await public_override_service.get_overrides(
        limit=limit,
        offset=offset,
        start_date=start_date,
        end_date=end_date,
    )

    # Convert to API response
    override_responses = EventToOverrideAdapter.to_response_list(overrides)

    # Calculate has_more
    has_more = (offset + len(overrides)) < total

    return OverrideEventsListResponse(
        overrides=override_responses,
        pagination=PaginationMetadata(
            total_count=total,
            offset=offset,
            limit=limit,
            has_more=has_more,
        ),
    )


@router.get("/{override_id}", response_model=OverrideEventResponse)
async def get_override_by_id(
    request: Request,
    override_id: UUID,
    public_override_service: PublicOverrideService = Depends(
        get_public_override_service
    ),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> OverrideEventResponse:
    """Get single override event by ID (FR25).

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    CRITICAL: Keeper identity is NOT anonymized per FR25.

    Args:
        request: The FastAPI request object.
        override_id: The UUID of the override event.
        public_override_service: Injected override service.
        rate_limiter: Injected rate limiter.

    Returns:
        The override event if found.

    Raises:
        HTTPException: 404 if override not found.
    """
    # Apply rate limiting (FR48 - same limits for all users)
    await rate_limiter.check_rate_limit(request)

    # Get override event
    event = await public_override_service.get_override_by_id(str(override_id))

    if event is None:
        raise HTTPException(
            status_code=404,
            detail=f"Override with ID {override_id} not found",
        )

    return EventToOverrideAdapter.to_response(event)
