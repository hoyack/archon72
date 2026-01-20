"""Co-Sign API routes (Story 5.2, Story 5.3, Story 5.4, FR-6.1, FR-6.2, FR-6.3, FR-6.4, FR-6.6).

FastAPI router for Three Fates petition co-signing endpoints.

Constitutional Constraints:
- FR-6.1: Seeker SHALL be able to co-sign active petition
- FR-6.2: System SHALL enforce unique constraint (petition_id, signer_id)
- FR-6.3: System SHALL reject co-sign after fate assignment
- FR-6.4: System SHALL increment co-signer count atomically
- FR-6.6: System SHALL apply SYBIL-1 rate limiting per signer
- NFR-5.1: Rate limiting per identity: Configurable per type
- NFR-5.2: Identity verification for co-sign: Required [LEGIT-1]
- CT-11: Silent failure destroys legitimacy - fail loud on errors, return 429 never silently drop
- CT-12: Witnessing creates accountability - all actions have attribution
- CT-13: Halt rejects writes, allows reads
- NFR-3.5: 0 duplicate signatures ever exist
- NFR-1.3: Response latency < 150ms p99
- D7: RFC 7807 error responses with governance extensions
- SYBIL-1: Identity verification + rate limiting per verified identity

Developer Golden Rules:
1. HALT CHECK FIRST - Service handles halt for writes (CT-13)
2. VERIFY IDENTITY - Check signer identity before accepting co-sign (NFR-5.2)
3. RATE LIMIT CHECK - Apply SYBIL-1 rate limiting after identity verification (FR-6.6)
4. WITNESS EVERYTHING - Co-sign events are witnessed (CT-12)
5. FAIL LOUD - Return meaningful RFC 7807 error responses (D7)
6. ATOMIC OPERATIONS - Count increment is atomic (FR-6.4)
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.dependencies.co_sign import (
    get_co_sign_count_verification_service,
    get_co_sign_submission_service,
)
from src.api.models.co_sign import (
    BatchCountVerificationRequest,
    BatchCountVerificationResponse,
    CoSignErrorResponse,
    CoSignRequest,
    CoSignResponse,
    CountVerificationResponse,
)
from src.application.services.co_sign_count_verification_service import (
    CoSignCountVerificationService,
)
from src.application.services.co_sign_submission_service import CoSignSubmissionService
from src.domain.errors import (
    AlreadySignedError,
    CoSignPetitionFatedError,
    CoSignPetitionNotFoundError,
    CoSignRateLimitExceededError,
    IdentityNotFoundError,
    IdentityServiceUnavailableError,
    IdentitySuspendedError,
    SystemHaltedError,
)

router = APIRouter(prefix="/v1/petitions", tags=["co-sign"])


@router.post(
    "/{petition_id}/co-sign",
    response_model=CoSignResponse,
    status_code=201,
    responses={
        403: {
            "model": CoSignErrorResponse,
            "description": "Identity not found or suspended (NFR-5.2, LEGIT-1)",
        },
        404: {
            "model": CoSignErrorResponse,
            "description": "Petition not found (FR-6.1)",
        },
        409: {
            "model": CoSignErrorResponse,
            "description": "Duplicate co-sign (FR-6.2, NFR-3.5) or petition fated (FR-6.3)",
        },
        429: {
            "model": CoSignErrorResponse,
            "description": "Rate limit exceeded (FR-6.6, SYBIL-1)",
        },
        503: {
            "model": CoSignErrorResponse,
            "description": "System halted (CT-13) or identity service unavailable (NFR-5.2)",
        },
    },
    summary="Co-sign a petition",
    description=(
        "Add a co-signature to an active petition in the Three Fates system. "
        "Seekers can express support for petitions they wish to see deliberated. "
        "FR-6.1, FR-6.2, FR-6.3, FR-6.4, FR-6.6, NFR-5.2, CT-12, CT-13."
    ),
)
async def co_sign_petition(
    petition_id: UUID,
    request_data: CoSignRequest,
    request: Request,
    service: CoSignSubmissionService = Depends(get_co_sign_submission_service),
) -> CoSignResponse:
    """Co-sign a petition (FR-6.1, FR-6.4, FR-6.6, NFR-5.2, CT-12, CT-13).

    Constitutional Constraints:
    - FR-6.1: Seeker SHALL be able to co-sign active petition
    - FR-6.2: System SHALL reject duplicate co-signature (NFR-3.5)
    - FR-6.3: System SHALL reject co-sign after fate assignment
    - FR-6.4: System SHALL increment co-signer count atomically
    - FR-6.6: System SHALL apply SYBIL-1 rate limiting per signer
    - NFR-5.1: Rate limiting per identity: Configurable per type
    - NFR-5.2: Identity verification for co-sign: Required [LEGIT-1]
    - CT-11: Fail loud, never silently drop - return 429 on rate limit
    - CT-12: Witnessing creates accountability
    - CT-13: Rejected during halt (write operation)
    - NFR-3.5: 0 duplicate signatures ever exist
    - NFR-1.3: Response latency < 150ms p99
    - D7: RFC 7807 error responses with governance extensions
    - SYBIL-1: Identity verification + rate limiting per verified identity

    Args:
        petition_id: UUID of the petition to co-sign.
        request_data: Co-sign request with signer_id.
        request: FastAPI request for error context.
        service: Injected co-sign submission service.

    Returns:
        CoSignResponse with co-signature details and rate limit info on success.

    Raises:
        HTTPException 403: Identity not found or suspended
        HTTPException 404: Petition not found
        HTTPException 409: Duplicate co-sign or petition already fated
        HTTPException 429: Rate limit exceeded (FR-6.6, SYBIL-1)
        HTTPException 503: System halted or identity service unavailable
    """
    try:
        result = await service.submit_co_sign(
            petition_id=petition_id,
            signer_id=request_data.signer_id,
        )

        return CoSignResponse(
            cosign_id=result.cosign_id,
            petition_id=result.petition_id,
            signer_id=result.signer_id,
            signed_at=result.signed_at,
            content_hash=result.content_hash,
            co_signer_count=result.co_signer_count,
            identity_verified=result.identity_verified,
            rate_limit_remaining=result.rate_limit_remaining,
            rate_limit_reset_at=result.rate_limit_reset_at,
        )

    except IdentityNotFoundError as e:
        # Identity not found - return 403 (NFR-5.2, LEGIT-1)
        raise HTTPException(
            status_code=403,
            detail={
                "type": "urn:archon72:identity:not-found",
                "title": "Identity Not Found",
                "status": 403,
                "detail": str(e),
                "instance": str(request.url),
                "signer_id": str(e.signer_id),
                "nfr_reference": e.nfr_reference,
                "hardening_control": e.hardening_control,
            },
        ) from None

    except IdentitySuspendedError as e:
        # Identity suspended - return 403 (NFR-5.2, LEGIT-1)
        raise HTTPException(
            status_code=403,
            detail={
                "type": "urn:archon72:identity:suspended",
                "title": "Identity Suspended",
                "status": 403,
                "detail": str(e),
                "instance": str(request.url),
                "signer_id": str(e.signer_id),
                "suspension_reason": e.reason,
                "nfr_reference": e.nfr_reference,
                "hardening_control": e.hardening_control,
            },
        ) from None

    except IdentityServiceUnavailableError as e:
        # Identity service unavailable - return 503 (NFR-5.2)
        raise HTTPException(
            status_code=503,
            detail={
                "type": "urn:archon72:identity:service-unavailable",
                "title": "Identity Service Unavailable",
                "status": 503,
                "detail": str(e),
                "instance": str(request.url),
                "signer_id": str(e.signer_id),
                "retry_after": e.retry_after,
                "nfr_reference": e.nfr_reference,
                "hardening_control": e.hardening_control,
            },
            headers={"Retry-After": str(e.retry_after)},
        ) from None

    except CoSignRateLimitExceededError as e:
        # Rate limit exceeded - return 429 (FR-6.6, SYBIL-1, CT-11)
        # Per AC1: Return HTTP 429 with Retry-After header
        # Per AC1: RFC 7807 error format with rate_limit_remaining extension
        raise HTTPException(
            status_code=429,
            detail={
                "type": "urn:archon72:co-sign:rate-limit-exceeded",
                "title": "Co-Sign Rate Limit Exceeded",
                "status": 429,
                "detail": str(e),
                "instance": str(request.url),
                "signer_id": str(e.signer_id),
                "current_count": e.current_count,
                "limit": e.limit,
                "rate_limit_remaining": 0,
                "rate_limit_reset_at": e.reset_at.isoformat(),
                "nfr_reference": "NFR-5.1",
                "hardening_control": "SYBIL-1",
            },
            headers={"Retry-After": str(e.retry_after_seconds)},
        ) from None

    except CoSignPetitionNotFoundError as e:
        # Petition not found - return 404 (FR-6.1)
        raise HTTPException(
            status_code=404,
            detail={
                "type": "urn:archon72:co-sign:petition-not-found",
                "title": "Petition Not Found",
                "status": 404,
                "detail": str(e),
                "instance": str(request.url),
                "petition_id": str(e.petition_id),
            },
        ) from None

    except AlreadySignedError as e:
        # Duplicate co-sign - return 409 (FR-6.2, NFR-3.5)
        # Story 5.7: Use RFC 7807 serialization with existing signature details
        error_detail = e.to_rfc7807_dict()
        error_detail["instance"] = str(request.url)
        raise HTTPException(
            status_code=409,
            detail=error_detail,
        ) from None

    except CoSignPetitionFatedError as e:
        # Petition already fated - return 409 (FR-6.3)
        raise HTTPException(
            status_code=409,
            detail={
                "type": "urn:archon72:co-sign:petition-fated",
                "title": "Petition Already Fated",
                "status": 409,
                "detail": str(e),
                "instance": str(request.url),
                "petition_id": str(e.petition_id),
                "terminal_state": e.terminal_state,
            },
        ) from None

    except SystemHaltedError as e:
        # System halted - return 503 (CT-13)
        raise HTTPException(
            status_code=503,
            detail={
                "type": "urn:archon72:co-sign:system-halted",
                "title": "System Halted",
                "status": 503,
                "detail": str(e),
                "instance": str(request.url),
            },
            headers={"Retry-After": "3600"},  # 1 hour default
        ) from None


@router.get(
    "/{petition_id}/cosigners/count/verify",
    response_model=CountVerificationResponse,
    status_code=200,
    responses={
        404: {
            "model": CoSignErrorResponse,
            "description": "Petition not found",
        },
        503: {
            "model": CoSignErrorResponse,
            "description": "Verification service unavailable",
        },
    },
    summary="Verify co-signer count consistency",
    description=(
        "Verify that the co_signer_count counter column matches the actual "
        "COUNT(*) from the co_signs table. Used for periodic consistency checks. "
        "Story 5.8, AC5, NFR-2.2."
    ),
)
async def verify_co_signer_count(
    petition_id: UUID,
    request: Request,
    service: CoSignCountVerificationService | None = Depends(
        get_co_sign_count_verification_service
    ),
) -> CountVerificationResponse:
    """Verify co-signer count consistency (Story 5.8, AC5, NFR-2.2).

    This read-only endpoint compares the pre-computed counter column against
    the actual COUNT(*) to detect any drift.

    Constitutional Constraints:
    - NFR-2.2: 100k+ co-signers - counter enables O(1) reads
    - AC5: Any discrepancy triggers MEDIUM alert
    - CT-11: Silent failure destroys legitimacy
    - CT-13: Read operation - allowed during halt

    Args:
        petition_id: UUID of the petition to verify.
        request: FastAPI request for error context.
        service: Injected verification service.

    Returns:
        CountVerificationResponse with consistency details.

    Raises:
        HTTPException 503: Verification service unavailable (no DB).
    """
    if service is None:
        raise HTTPException(
            status_code=503,
            detail={
                "type": "urn:archon72:co-sign:verification-unavailable",
                "title": "Verification Service Unavailable",
                "status": 503,
                "detail": "Count verification requires database access",
                "instance": str(request.url),
            },
        )

    result = await service.verify_count(petition_id)

    return CountVerificationResponse(
        petition_id=result.petition_id,
        counter_value=result.counter_value,
        actual_count=result.actual_count,
        is_consistent=result.is_consistent,
        discrepancy=result.discrepancy,
    )


@router.post(
    "/cosigners/count/verify/batch",
    response_model=BatchCountVerificationResponse,
    status_code=200,
    responses={
        503: {
            "model": CoSignErrorResponse,
            "description": "Verification service unavailable",
        },
    },
    summary="Batch verify co-signer count consistency",
    description=(
        "Verify co_signer_count consistency for multiple petitions at once. "
        "Max 100 petitions per batch. Story 5.8, AC5."
    ),
)
async def batch_verify_co_signer_count(
    request_data: BatchCountVerificationRequest,
    request: Request,
    service: CoSignCountVerificationService | None = Depends(
        get_co_sign_count_verification_service
    ),
) -> BatchCountVerificationResponse:
    """Batch verify co-signer count consistency (Story 5.8, AC5).

    Processes multiple petitions in sequence for consistency verification.

    Args:
        request_data: Request with list of petition IDs to verify.
        request: FastAPI request for error context.
        service: Injected verification service.

    Returns:
        BatchCountVerificationResponse with aggregate and individual results.

    Raises:
        HTTPException 503: Verification service unavailable.
    """
    if service is None:
        raise HTTPException(
            status_code=503,
            detail={
                "type": "urn:archon72:co-sign:verification-unavailable",
                "title": "Verification Service Unavailable",
                "status": 503,
                "detail": "Count verification requires database access",
                "instance": str(request.url),
            },
        )

    results = await service.verify_batch(request_data.petition_ids)

    response_results = [
        CountVerificationResponse(
            petition_id=r.petition_id,
            counter_value=r.counter_value,
            actual_count=r.actual_count,
            is_consistent=r.is_consistent,
            discrepancy=r.discrepancy,
        )
        for r in results
    ]

    inconsistent_count = sum(1 for r in results if not r.is_consistent)

    return BatchCountVerificationResponse(
        total=len(results),
        consistent=len(results) - inconsistent_count,
        inconsistent=inconsistent_count,
        results=response_results,
    )
