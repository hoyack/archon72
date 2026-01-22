"""Escalation Queue and Decision Package API routes (Stories 6.1-6.2, FR-5.4).

FastAPI router for King's escalation endpoints:
- Story 6.1: Escalation queue listing
- Story 6.2: Escalation decision package (full context for adoption/acknowledgment)

Constitutional Constraints:
- FR-5.4: King SHALL receive escalation queue distinct from organic Motions [P0]
- CT-13: Halt check first pattern
- D8: Keyset pagination compliance
- RULING-3: Realm-scoped data access
- RULING-2: Tiered transcript access (mediated summaries for Kings)
- NFR-1.2: Endpoint latency p99 < 200ms

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

from src.api.dependencies.escalation import (
    get_escalation_queue_service,
    get_escalation_decision_package_service,
)
from src.api.models.escalation import (
    CoSignerListResponse,
    CoSignerResponse,
    DeliberationSummaryResponse,
    EscalationDecisionPackageResponse,
    EscalationHistoryResponse,
    EscalationQueueErrorResponse,
    EscalationQueueItemResponse,
    EscalationQueueResponse,
    EscalationSourceEnum,
    KnightRecommendationResponse,
    PetitionTypeEnum,
    SubmitterMetadataResponse,
)
from src.application.ports.escalation_queue import EscalationQueueItem, EscalationSource
from src.application.services.escalation_queue_service import EscalationQueueService
from src.application.services.escalation_decision_package_service import (
    DecisionPackageData,
    EscalationDecisionPackageService,
    EscalationNotFoundError,
    RealmMismatchError,
)
from src.domain.errors import SystemHaltedError
from src.domain.errors.petition import PetitionSubmissionNotFoundError
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


# =============================================================================
# Story 6.2: Escalation Decision Package Endpoint
# =============================================================================


def _package_data_to_api(data: DecisionPackageData) -> EscalationDecisionPackageResponse:
    """Convert service DecisionPackageData to API response model."""
    # Convert co-signers
    co_signer_items = [
        CoSignerResponse(
            public_key_hash=cs.public_key_hash,
            signed_at=cs.signed_at,
            sequence=cs.sequence,
        )
        for cs in data.co_signers.items
    ]

    co_signers = CoSignerListResponse(
        items=co_signer_items,
        total_count=data.co_signers.total_count,
        next_cursor=data.co_signers.next_cursor,
        has_more=data.co_signers.has_more,
    )

    # Convert deliberation summary (if present)
    deliberation_summary = None
    if data.escalation_history.deliberation_summary:
        ds = data.escalation_history.deliberation_summary
        deliberation_summary = DeliberationSummaryResponse(
            vote_breakdown=ds.vote_breakdown,
            has_dissent=ds.has_dissent,
            decision_outcome=ds.decision_outcome,
            transcript_hash=ds.transcript_hash,
        )

    # Convert knight recommendation (if present)
    knight_recommendation = None
    if data.escalation_history.knight_recommendation:
        kr = data.escalation_history.knight_recommendation
        knight_recommendation = KnightRecommendationResponse(
            knight_id=kr.knight_id,
            recommendation_text=kr.recommendation_text,
            recommended_at=kr.recommended_at,
        )

    # Build escalation history
    escalation_history = EscalationHistoryResponse(
        escalation_source=EscalationSourceEnum(data.escalation_history.escalation_source),
        escalated_at=data.escalation_history.escalated_at,
        co_signer_count_at_escalation=data.escalation_history.co_signer_count_at_escalation,
        deliberation_summary=deliberation_summary,
        knight_recommendation=knight_recommendation,
    )

    return EscalationDecisionPackageResponse(
        petition_id=data.petition_id,
        petition_type=PetitionTypeEnum(data.petition_type),
        petition_content=data.petition_content,
        submitter_metadata=SubmitterMetadataResponse(
            public_key_hash=data.submitter_metadata.public_key_hash,
            submitted_at=data.submitter_metadata.submitted_at,
        ),
        co_signers=co_signers,
        escalation_history=escalation_history,
    )


@router.get(
    "/escalations/{petition_id}",
    response_model=EscalationDecisionPackageResponse,
    status_code=200,
    responses={
        403: {
            "model": EscalationQueueErrorResponse,
            "description": "Forbidden - Not a King or realm mismatch",
        },
        404: {
            "model": EscalationQueueErrorResponse,
            "description": "Not Found - Petition not found or not escalated",
        },
        503: {
            "model": EscalationQueueErrorResponse,
            "description": "Service Unavailable - System halted",
        },
    },
)
async def get_escalation_decision_package(
    petition_id: UUID,
    king_realm: str = Query(
        ...,
        description="Realm of the requesting King (for authorization per RULING-3)",
    ),
    decision_package_service: EscalationDecisionPackageService = Depends(
        get_escalation_decision_package_service
    ),
) -> EscalationDecisionPackageResponse:
    """Get complete decision package for escalated petition (Story 6.2, FR-5.4).

    Provides comprehensive context for King adoption/acknowledgment decision:
    - Petition core data (text, type, submitter metadata)
    - Co-signer information (paginated list with total count)
    - Escalation history (source, deliberation summary, or Knight recommendation)

    Constitutional Constraints:
    - FR-5.4: King receives complete escalation context
    - RULING-2: Mediated deliberation summaries (not raw transcripts)
    - RULING-3: Realm-scoped access (King must match escalation realm)
    - CT-13: Halt check first pattern (handled by service)

    Args:
        petition_id: UUID of the escalated petition
        king_realm: Realm of the requesting King (for authorization)
        decision_package_service: Injected decision package service

    Returns:
        EscalationDecisionPackageResponse with complete escalation context

    Raises:
        403: Realm mismatch (King's realm doesn't match escalation realm)
        404: Petition not found or not escalated
        503: System halted (CT-13)
    """
    try:
        # Service handles halt check (CT-13) and realm authorization (RULING-3)
        package_data = await decision_package_service.get_decision_package(
            petition_id=petition_id,
            king_realm=king_realm,
        )

        # Convert service data to API response
        return _package_data_to_api(package_data)

    except RealmMismatchError as e:
        # RULING-3: Realm mismatch - King can only access their realm's escalations
        return JSONResponse(
            status_code=403,
            content={
                "type": "https://archon.example.com/errors/realm-mismatch",
                "title": "Realm Mismatch",
                "status": 403,
                "detail": str(e),
                "instance": f"/api/v1/escalations/{petition_id}",
            },
        )

    except (PetitionSubmissionNotFoundError, EscalationNotFoundError) as e:
        # Petition not found or not escalated
        return JSONResponse(
            status_code=404,
            content={
                "type": "https://archon.example.com/errors/not-found",
                "title": "Not Found",
                "status": 404,
                "detail": str(e),
                "instance": f"/api/v1/escalations/{petition_id}",
            },
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
                "instance": f"/api/v1/escalations/{petition_id}",
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
                "instance": f"/api/v1/escalations/{petition_id}",
            },
        )
