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
    get_petition_adoption_service,
    get_acknowledgment_execution_service,
)
from src.api.models.escalation import (
    PetitionAdoptionRequest,
    PetitionAdoptionResponse,
    CoSignerListResponse,
    CoSignerResponse,
    DeliberationSummaryResponse,
    EscalationDecisionPackageResponse,
    EscalationHistoryResponse,
    EscalationQueueErrorResponse,
    EscalationQueueItemResponse,
    EscalationQueueResponse,
    EscalationSourceEnum,
    KingAcknowledgmentRequest,
    KingAcknowledgmentResponse,
    KnightRecommendationResponse,
    PetitionTypeEnum,
    SubmitterMetadataResponse,
)
from src.application.ports.escalation_queue import EscalationQueueItem, EscalationSource
from src.application.ports.petition_adoption import (
    InsufficientBudgetException,
    PetitionNotEscalatedException,
    RealmMismatchException,
)
from src.application.services.escalation_queue_service import EscalationQueueService
from src.application.services.escalation_decision_package_service import (
    DecisionPackageData,
    EscalationDecisionPackageService,
    EscalationNotFoundError,
    RealmMismatchError,
)
from src.application.services.petition_adoption_service import SystemHaltedException
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


# =============================================================================
# Petition Adoption Endpoint (Story 6.3)
# =============================================================================


@router.post(
    "/escalations/{petition_id}/adopt",
    response_model=PetitionAdoptionResponse,
    status_code=200,
    responses={
        200: {
            "description": "Petition successfully adopted, Motion created",
        },
        400: {
            "description": "Validation error, not escalated, or insufficient budget",
        },
        403: {
            "description": "Realm mismatch - King can only adopt from their realm",
        },
        404: {
            "description": "Petition not found",
        },
        503: {
            "description": "System halted - adoption not permitted",
        },
    },
    summary="Adopt escalated petition and create Motion",
)
async def adopt_petition(
    petition_id: UUID,
    request: PetitionAdoptionRequest,
    king_id: UUID = Query(..., description="UUID of the King making the adoption"),
    realm_id: str = Query(..., description="Realm ID of the King (for authorization)"),
    adoption_service = Depends(get_petition_adoption_service),
):
    """Adopt an escalated petition and create a Motion (Story 6.3, FR-5.5)."""
    try:
        from src.application.ports.petition_adoption import AdoptionRequest
        from src.api.models.escalation import ProvenanceResponse
        from datetime import datetime, timezone

        adoption_request = AdoptionRequest(
            petition_id=petition_id,
            king_id=king_id,
            realm_id=realm_id,
            motion_title=request.motion_title,
            motion_body=request.motion_body,
            adoption_rationale=request.adoption_rationale,
        )

        result = await adoption_service.adopt_petition(adoption_request)

        if not result.success:
            if "PETITION_NOT_FOUND" in result.errors:
                return JSONResponse(
                    status_code=404,
                    content={
                        "type": "https://archon.example.com/errors/not-found",
                        "title": "Petition Not Found",
                        "status": 404,
                        "detail": f"Petition {petition_id} not found",
                        "instance": f"/api/v1/escalations/{petition_id}/adopt",
                    },
                )
            return JSONResponse(
                status_code=400,
                content={
                    "type": "https://archon.example.com/errors/validation-failed",
                    "title": "Adoption Failed",
                    "status": 400,
                    "detail": f"Adoption failed: {', '.join(result.errors)}",
                    "instance": f"/api/v1/escalations/{petition_id}/adopt",
                },
            )

        provenance = ProvenanceResponse(
            source_petition_ref=petition_id,
            adoption_rationale=request.adoption_rationale,
            budget_consumed=result.budget_consumed,
        )

        return PetitionAdoptionResponse(
            motion_id=result.motion_id,
            petition_id=petition_id,
            sponsor_id=king_id,
            created_at=datetime.now(timezone.utc),
            provenance=provenance,
        )

    except PetitionNotEscalatedException as e:
        return JSONResponse(
            status_code=400,
            content={
                "type": "https://archon.example.com/errors/petition-not-escalated",
                "title": "Petition Not Escalated",
                "status": 400,
                "detail": f"Petition {petition_id} is not escalated (state: {e.current_state})",
                "instance": f"/api/v1/escalations/{petition_id}/adopt",
            },
        )
    except RealmMismatchException as e:
        return JSONResponse(
            status_code=403,
            content={
                "type": "https://archon.example.com/errors/realm-mismatch",
                "title": "Realm Authorization Failed",
                "status": 403,
                "detail": f"Realm mismatch: King realm={e.king_realm}, petition realm={e.petition_realm}",
                "instance": f"/api/v1/escalations/{petition_id}/adopt",
            },
        )
    except InsufficientBudgetException as e:
        return JSONResponse(
            status_code=400,
            content={
                "type": "https://archon.example.com/errors/insufficient-budget",
                "title": "Insufficient Promotion Budget",
                "status": 400,
                "detail": f"King {king_id} has exhausted promotion budget",
                "instance": f"/api/v1/escalations/{petition_id}/adopt",
            },
        )
    except SystemHaltedException as e:
        return JSONResponse(
            status_code=503,
            content={
                "type": "https://archon.example.com/errors/system-halted",
                "title": "System Halted",
                "status": 503,
                "detail": "Adoption not permitted during system halt",
                "instance": f"/api/v1/escalations/{petition_id}/adopt",
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "type": "https://archon.example.com/errors/internal-server-error",
                "title": "Internal Server Error",
                "status": 500,
                "detail": f"Unexpected error: {str(e)}",
                "instance": f"/api/v1/escalations/{petition_id}/adopt",
            },
        )


# =============================================================================
# King Acknowledgment Endpoint (Story 6.5)
# =============================================================================


@router.post(
    "/escalations/{petition_id}/acknowledge",
    response_model=KingAcknowledgmentResponse,
    status_code=200,
    responses={
        200: {
            "description": "Petition successfully acknowledged by King",
        },
        400: {
            "description": "Validation error, not escalated, or rationale too short",
        },
        403: {
            "description": "Realm mismatch - King can only acknowledge from their realm",
        },
        404: {
            "description": "Petition not found",
        },
        503: {
            "description": "System halted - acknowledgment not permitted",
        },
    },
    summary="Acknowledge escalated petition as King",
)
async def acknowledge_escalation(
    petition_id: UUID,
    request: KingAcknowledgmentRequest,
    king_id: UUID = Query(..., description="UUID of the King making the acknowledgment"),
    realm_id: str = Query(..., description="Realm ID of the King (for authorization)"),
    acknowledgment_service = Depends(get_acknowledgment_execution_service),
):
    """Acknowledge an escalated petition as King (Story 6.5, FR-5.8).

    Allows a King to formally decline adoption of an escalated petition
    while providing rationale to respect the petitioners.

    Constitutional Constraints:
    - FR-5.8: King SHALL be able to ACKNOWLEDGE escalation (with rationale) [P0]
    - Story 6.5 AC2: Rationale must be >= 100 characters
    - Story 6.5 AC3: Petition must be in ESCALATED state
    - Story 6.5 AC4: Realm authorization (King's realm must match petition's realm)
    - CT-13: Halt check first pattern (handled by service)

    Args:
        petition_id: UUID of the escalated petition to acknowledge
        request: KingAcknowledgmentRequest with reason_code and rationale
        king_id: UUID of the King making the acknowledgment
        realm_id: Realm ID of the King (for authorization per RULING-3)
        acknowledgment_service: Injected acknowledgment execution service

    Returns:
        KingAcknowledgmentResponse with acknowledgment details

    Raises:
        400: Validation error, petition not escalated, or rationale too short
        403: Realm mismatch (King's realm doesn't match petition's realm)
        404: Petition not found
        503: System halted
    """
    try:
        from src.domain.models.acknowledgment_reason import AcknowledgmentReasonCode
        from src.domain.errors.acknowledgment import PetitionNotFoundError
        from src.domain.errors.petition import PetitionNotEscalatedError, RealmMismatchError

        # Parse reason code
        try:
            reason_code = AcknowledgmentReasonCode(request.reason_code)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={
                    "type": "https://archon.example.com/errors/invalid-reason-code",
                    "title": "Invalid Reason Code",
                    "status": 400,
                    "detail": f"Invalid reason code: {request.reason_code}. "
                             f"Must be one of: {', '.join(rc.value for rc in AcknowledgmentReasonCode)}",
                    "instance": f"/api/v1/kings/escalations/{petition_id}/acknowledge",
                },
            )

        # Execute King acknowledgment
        acknowledgment = await acknowledgment_service.execute_king_acknowledge(
            petition_id=petition_id,
            king_id=king_id,
            reason_code=reason_code,
            rationale=request.rationale,
            realm_id=realm_id,
        )

        # Build response
        return KingAcknowledgmentResponse(
            acknowledgment_id=acknowledgment.id,
            petition_id=petition_id,
            king_id=king_id,
            reason_code=reason_code.value,
            acknowledged_at=acknowledgment.acknowledged_at,
            realm_id=realm_id,
        )

    except PetitionNotFoundError:
        return JSONResponse(
            status_code=404,
            content={
                "type": "https://archon.example.com/errors/not-found",
                "title": "Petition Not Found",
                "status": 404,
                "detail": f"Petition {petition_id} not found",
                "instance": f"/api/v1/kings/escalations/{petition_id}/acknowledge",
            },
        )

    except PetitionNotEscalatedError as e:
        return JSONResponse(
            status_code=400,
            content={
                "type": "https://archon.example.com/errors/petition-not-escalated",
                "title": "Petition Not Escalated",
                "status": 400,
                "detail": f"Petition {petition_id} is not escalated (current state: {e.current_state}). "
                         "King can only acknowledge ESCALATED petitions.",
                "instance": f"/api/v1/kings/escalations/{petition_id}/acknowledge",
            },
        )

    except RealmMismatchError as e:
        return JSONResponse(
            status_code=403,
            content={
                "type": "https://archon.example.com/errors/realm-mismatch",
                "title": "Realm Authorization Failed",
                "status": 403,
                "detail": str(e),
                "instance": f"/api/v1/kings/escalations/{petition_id}/acknowledge",
            },
        )

    except ValueError as e:
        # Rationale too short or other validation error
        return JSONResponse(
            status_code=400,
            content={
                "type": "https://archon.example.com/errors/validation-failed",
                "title": "Validation Failed",
                "status": 400,
                "detail": str(e),
                "instance": f"/api/v1/kings/escalations/{petition_id}/acknowledge",
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
                "detail": "Acknowledgment not permitted during system halt",
                "instance": f"/api/v1/kings/escalations/{petition_id}/acknowledge",
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
                "instance": f"/api/v1/kings/escalations/{petition_id}/acknowledge",
            },
        )
