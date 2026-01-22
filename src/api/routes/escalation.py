"""Escalation Queue API routes (Story 6.1, FR-5.4).

FastAPI router for King's escalation queue endpoints.

Constitutional Constraints:
- FR-5.4: King SHALL receive escalation queue distinct from organic Motions [P0]
- CT-13: Halt check first pattern
- D8: Keyset pagination compliance
- RULING-3: Realm-scoped data access
- NFR-1.3: Endpoint latency < 200ms p95

Developer Golden Rules:
1. HALT CHECK FIRST - Service handles halt check (CT-13)
2. KING AUTHORIZATION - Verify King rank before access
3. REALM SCOPED - Only return petitions for King's realm (RULING-3)
4. KEYSET PAGINATION - Use cursor parameter, not offset (D8)
5. FAIL LOUD - Return meaningful RFC 7807 error responses
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from src.api.dependencies.escalation import get_escalation_queue_service
from src.api.models.escalation import (
    EscalationQueueErrorResponse,
    EscalationQueueItemResponse,
    EscalationQueueResponse,
    EscalationSourceEnum,
    PetitionTypeEnum,
)
from src.application.ports.escalation_queue import EscalationQueueItem, EscalationSource
from src.application.services.escalation_queue_service import EscalationQueueService
from src.domain.errors import SystemHaltedError
from src.domain.models.petition_submission import PetitionType

router = APIRouter(prefix="/v1/kings", tags=["escalation"])

# Pagination limits (D8)
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


# =============================================================================
# Type Mapping
# =============================================================================


def _domain_type_to_api(domain_type: PetitionType) -> PetitionTypeEnum:
    """Convert domain PetitionType to API enum."""
    return PetitionTypeEnum(domain_type.value)


def _domain_source_to_api(domain_source: EscalationSource) -> EscalationSourceEnum:
    """Convert domain EscalationSource to API enum."""
    return EscalationSourceEnum(domain_source.value)


def _domain_item_to_api(item: EscalationQueueItem) -> EscalationQueueItemResponse:
    """Convert domain EscalationQueueItem to API response model."""
    return EscalationQueueItemResponse(
        petition_id=item.petition_id,
        petition_type=_domain_type_to_api(item.petition_type),
        escalation_source=_domain_source_to_api(item.escalation_source),
        co_signer_count=item.co_signer_count,
        escalated_at=item.escalated_at,
    )


# =============================================================================
# Escalation Queue Endpoints
# =============================================================================


@router.get(
    "/{king_id}/escalations",
    response_model=EscalationQueueResponse,
    status_code=200,
    responses={
        400: {
            "model": EscalationQueueErrorResponse,
            "description": "Invalid parameters (e.g., invalid limit)",
        },
        403: {
            "model": EscalationQueueErrorResponse,
            "description": "Forbidden - Not a King or wrong realm",
        },
        503: {
            "model": EscalationQueueErrorResponse,
            "description": "Service Unavailable - System halted",
        },
    },
)
async def get_escalation_queue(
    king_id: UUID,
    cursor: str | None = Query(
        None,
        description="Cursor for pagination (keyset-based, D8)",
    ),
    limit: int = Query(
        DEFAULT_LIMIT,
        description=f"Maximum number of items (default {DEFAULT_LIMIT}, max {MAX_LIMIT})",
        ge=1,
        le=MAX_LIMIT,
    ),
    escalation_service: EscalationQueueService = Depends(get_escalation_queue_service),
) -> EscalationQueueResponse:
    """Get escalation queue for a King's realm (Story 6.1, FR-5.4).

    Returns paginated list of petitions that have been escalated to the King's
    realm, ordered by escalated_at ascending (FIFO).

    Uses keyset pagination (D8) for efficiency:
    - First page: GET /api/v1/kings/{king_id}/escalations
    - Next page: GET /api/v1/kings/{king_id}/escalations?cursor={next_cursor}

    Constitutional Constraints:
    - FR-5.4: King SHALL receive escalation queue distinct from organic Motions
    - CT-13: Halt check first pattern (handled by service)
    - D8: Keyset pagination for efficient navigation
    - RULING-3: Realm-scoped data access

    Args:
        king_id: UUID of the King requesting the queue
        cursor: Optional cursor for pagination (keyset-based)
        limit: Maximum number of items to return (1-100, default 20)
        escalation_service: Injected escalation queue service

    Returns:
        EscalationQueueResponse with items, next_cursor, and has_more flag

    Raises:
        400: Invalid parameters (e.g., invalid limit)
        403: Not a King or wrong realm (TODO: implement authorization)
        503: System halted (CT-13)
    """
    # TODO: Implement King authorization check
    # For now, we assume king_id is valid and authorized
    # In production, use PermissionEnforcerProtocol to verify King rank

    # Hardcode realm for now - in production, fetch from King profile
    # TODO: Get realm_id from King's profile/configuration
    realm_id = "governance"  # Placeholder

    try:
        # Service handles halt check (CT-13)
        result = await escalation_service.get_queue(
            king_id=king_id,
            realm_id=realm_id,
            cursor=cursor,
            limit=limit,
        )

        # Convert domain items to API response models
        api_items = [_domain_item_to_api(item) for item in result.items]

        return EscalationQueueResponse(
            items=api_items,
            next_cursor=result.next_cursor,
            has_more=result.has_more,
        )

    except SystemHaltedError as e:
        # CT-13: Return 503 during halt
        return JSONResponse(
            status_code=503,
            content={
                "type": "https://archon.example.com/errors/system-halted",
                "title": "System Halted",
                "status": 503,
                "detail": str(e),
                "instance": f"/api/v1/kings/{king_id}/escalations",
            },
        )

    except ValueError as e:
        # Invalid parameters (e.g., invalid cursor or limit)
        return JSONResponse(
            status_code=400,
            content={
                "type": "https://archon.example.com/errors/invalid-request",
                "title": "Invalid Request",
                "status": 400,
                "detail": str(e),
                "instance": f"/api/v1/kings/{king_id}/escalations",
            },
        )

    except Exception as e:
        # Unexpected error - fail loud (CT-11)
        return JSONResponse(
            status_code=500,
            content={
                "type": "https://archon.example.com/errors/internal-server-error",
                "title": "Internal Server Error",
                "status": 500,
                "detail": f"Unexpected error: {str(e)}",
                "instance": f"/api/v1/kings/{king_id}/escalations",
            },
        )
