"""META petition API routes (Story 8.5, FR-10.4).

FastAPI router for META petition queue management endpoints.
High Archon authentication required for all operations.

Constitutional Constraints:
- FR-10.4: META petitions SHALL route to High Archon [P2]
- AC3: Queue returns sorted by received_at (oldest first, FIFO)
- AC4: High Archon can resolve with disposition and rationale
- CT-12: Witnessing creates accountability -> Log all operations
- CT-13: Explicit consent -> Resolution is explicit action
"""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from src.api.auth.high_archon_auth import get_high_archon_id
from src.api.models.meta_petition import (
    MetaDispositionEnum,
    MetaPetitionErrorResponse,
    MetaPetitionQueueItemResponse,
    MetaPetitionQueueResponse,
    MetaPetitionStatusEnum,
    ResolveMetaPetitionRequest,
    ResolveMetaPetitionResponse,
)
from src.application.ports.meta_petition_queue_repository import (
    MetaPetitionAlreadyResolvedError,
    MetaPetitionNotFoundError,
)
from src.application.services.meta_petition_resolution_service import (
    MetaPetitionResolutionService,
)
from src.domain.models.meta_petition import MetaDisposition

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/v1/governance/meta-petitions",
    tags=["governance", "meta-petitions"],
)


# Dependency injection placeholder
# In production, this would be provided by the DI container
_resolution_service: MetaPetitionResolutionService | None = None


def set_resolution_service(service: MetaPetitionResolutionService) -> None:
    """Set the resolution service for dependency injection.

    Args:
        service: The MetaPetitionResolutionService instance.
    """
    global _resolution_service
    _resolution_service = service


def get_resolution_service() -> MetaPetitionResolutionService:
    """Get the resolution service.

    Raises:
        RuntimeError: If resolution service not configured.
    """
    if _resolution_service is None:
        raise RuntimeError("META petition resolution service not configured")
    return _resolution_service


@router.get(
    "",
    response_model=MetaPetitionQueueResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": MetaPetitionErrorResponse, "description": "Unauthorized"},
        403: {"model": MetaPetitionErrorResponse, "description": "Forbidden - High Archon role required"},
    },
    summary="List pending META petitions",
    description="""
List META petitions in the High Archon queue awaiting resolution.

**Requires authentication via X-Archon-Id and X-Archon-Role headers.**
**Requires HIGH_ARCHON role.**

Returns petitions sorted by received_at (oldest first, FIFO ordering per AC3).

Per FR-10.4: META petitions route directly to High Archon queue.
Per AC3: Queue returns sorted oldest first (FIFO).
""",
)
async def list_pending_meta_petitions(
    high_archon_id: Annotated[UUID, Depends(get_high_archon_id)],
    resolution_service: Annotated[
        MetaPetitionResolutionService, Depends(get_resolution_service)
    ],
    limit: Annotated[
        int,
        Query(
            description="Maximum number of petitions to return",
            ge=1,
            le=100,
        ),
    ] = 50,
    offset: Annotated[
        int,
        Query(
            description="Number of petitions to skip for pagination",
            ge=0,
        ),
    ] = 0,
) -> MetaPetitionQueueResponse:
    """List pending META petitions for High Archon review.

    Per AC3: Returns petitions sorted oldest first (FIFO ordering).

    Args:
        high_archon_id: Authenticated High Archon ID from headers.
        resolution_service: Injected resolution service.
        limit: Maximum items to return (default 50, max 100).
        offset: Pagination offset.

    Returns:
        MetaPetitionQueueResponse with pending petitions.

    Raises:
        HTTPException 401: If authentication fails.
        HTTPException 403: If not HIGH_ARCHON role.
    """
    log = logger.bind(
        high_archon_id=str(high_archon_id),
        limit=limit,
        offset=offset,
    )
    log.info("meta_petition_queue_requested")

    items, total_count = await resolution_service.get_pending_queue(
        limit=limit, offset=offset
    )

    response_items = [
        MetaPetitionQueueItemResponse(
            petition_id=item.petition_id,
            submitter_id=item.submitter_id,
            petition_text=item.petition_text,
            received_at=item.received_at,
            status=MetaPetitionStatusEnum(item.status.value),
        )
        for item in items
    ]

    log.info(
        "meta_petition_queue_returned",
        count=len(response_items),
        total=total_count,
    )

    return MetaPetitionQueueResponse(
        items=response_items,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{petition_id}",
    response_model=MetaPetitionQueueItemResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": MetaPetitionErrorResponse, "description": "Unauthorized"},
        403: {"model": MetaPetitionErrorResponse, "description": "Forbidden - High Archon role required"},
        404: {"model": MetaPetitionErrorResponse, "description": "META petition not found"},
    },
    summary="Get META petition details",
    description="""
Get details of a specific META petition by ID.

**Requires authentication via X-Archon-Id and X-Archon-Role headers.**
**Requires HIGH_ARCHON role.**

Per FR-10.4: High Archon can view META petition details.
""",
)
async def get_meta_petition(
    high_archon_id: Annotated[UUID, Depends(get_high_archon_id)],
    resolution_service: Annotated[
        MetaPetitionResolutionService, Depends(get_resolution_service)
    ],
    petition_id: Annotated[
        UUID,
        Path(description="UUID of the META petition to retrieve"),
    ],
) -> MetaPetitionQueueItemResponse:
    """Get details of a specific META petition.

    Args:
        high_archon_id: Authenticated High Archon ID from headers.
        resolution_service: Injected resolution service.
        petition_id: UUID of the petition to retrieve.

    Returns:
        MetaPetitionQueueItemResponse with petition details.

    Raises:
        HTTPException 401: If authentication fails.
        HTTPException 403: If not HIGH_ARCHON role.
        HTTPException 404: If petition not found.
    """
    log = logger.bind(
        high_archon_id=str(high_archon_id),
        petition_id=str(petition_id),
    )
    log.info("meta_petition_detail_requested")

    item = await resolution_service.get_queue_item(petition_id)

    if item is None:
        log.warning("meta_petition_not_found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"META petition not found in queue: {petition_id}",
        )

    log.info("meta_petition_detail_returned", status=item.status.value)

    return MetaPetitionQueueItemResponse(
        petition_id=item.petition_id,
        submitter_id=item.submitter_id,
        petition_text=item.petition_text,
        received_at=item.received_at,
        status=MetaPetitionStatusEnum(item.status.value),
    )


@router.post(
    "/{petition_id}/resolve",
    response_model=ResolveMetaPetitionResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": MetaPetitionErrorResponse, "description": "Validation error (e.g., rationale too short)"},
        401: {"model": MetaPetitionErrorResponse, "description": "Unauthorized"},
        403: {"model": MetaPetitionErrorResponse, "description": "Forbidden - High Archon role required"},
        404: {"model": MetaPetitionErrorResponse, "description": "META petition not found"},
        409: {"model": MetaPetitionErrorResponse, "description": "META petition already resolved"},
    },
    summary="Resolve META petition",
    description="""
Resolve a META petition with a disposition and rationale.

**Requires authentication via X-Archon-Id and X-Archon-Role headers.**
**Requires HIGH_ARCHON role.**

Dispositions:
- **ACKNOWLEDGE**: Acknowledge the petition (no further action)
- **CREATE_ACTION**: Create a governance action item
- **FORWARD**: Forward to another governance body (requires forward_target)

Per FR-10.4: High Archon resolves META petitions.
Per AC4: Resolution requires disposition and rationale.
Per CT-13: Explicit consent through disposition selection.
""",
)
async def resolve_meta_petition(
    high_archon_id: Annotated[UUID, Depends(get_high_archon_id)],
    resolution_service: Annotated[
        MetaPetitionResolutionService, Depends(get_resolution_service)
    ],
    petition_id: Annotated[
        UUID,
        Path(description="UUID of the META petition to resolve"),
    ],
    request: ResolveMetaPetitionRequest,
) -> ResolveMetaPetitionResponse:
    """Resolve a META petition with disposition and rationale.

    Per AC4: High Archon resolves with explicit disposition.
    Per CT-13: Resolution is explicit consent action.

    Args:
        high_archon_id: Authenticated High Archon ID from headers.
        resolution_service: Injected resolution service.
        petition_id: UUID of the petition to resolve.
        request: Resolution request with disposition and rationale.

    Returns:
        ResolveMetaPetitionResponse with resolution details.

    Raises:
        HTTPException 400: If validation fails (rationale too short, etc.).
        HTTPException 401: If authentication fails.
        HTTPException 403: If not HIGH_ARCHON role.
        HTTPException 404: If petition not found.
        HTTPException 409: If petition already resolved.
    """
    log = logger.bind(
        high_archon_id=str(high_archon_id),
        petition_id=str(petition_id),
        disposition=request.disposition.value,
    )
    log.info("meta_petition_resolution_requested")

    # Convert API disposition to domain enum
    domain_disposition = MetaDisposition(request.disposition.value)

    try:
        event = await resolution_service.resolve_meta_petition(
            petition_id=petition_id,
            disposition=domain_disposition,
            rationale=request.rationale,
            high_archon_id=high_archon_id,
            forward_target=request.forward_target,
        )
    except ValueError as e:
        log.warning("resolution_validation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except MetaPetitionNotFoundError:
        log.warning("meta_petition_not_found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"META petition not found in queue: {petition_id}",
        )
    except MetaPetitionAlreadyResolvedError:
        log.warning("meta_petition_already_resolved")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"META petition already resolved: {petition_id}",
        )

    log.info(
        "meta_petition_resolved",
        disposition=event.disposition.value,
        has_forward_target=event.forward_target is not None,
    )

    return ResolveMetaPetitionResponse(
        success=True,
        petition_id=event.petition_id,
        disposition=MetaDispositionEnum(event.disposition.value),
        rationale=event.rationale,
        high_archon_id=event.high_archon_id,
        resolved_at=event.resolved_at,
        forward_target=event.forward_target,
    )
