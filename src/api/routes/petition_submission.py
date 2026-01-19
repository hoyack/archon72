"""Petition Submission API routes (Story 1.1, FR-1.1, Story 1.3, FR-1.4, Story 1.4, FR-1.5).

FastAPI router for Three Fates petition submission endpoints.

Constitutional Constraints:
- FR-1.1: Accept petition submissions via REST API
- FR-1.2: Generate UUIDv7 petition_id (using uuid4 for Python 3.11)
- FR-1.3: Validate petition schema
- FR-1.4: Return HTTP 503 on queue overflow (Story 1.3)
- FR-1.5: Enforce rate limits per submitter_id (Story 1.4)
- FR-1.6: Set initial state to RECEIVED
- FR-10.1: Support GENERAL, CESSATION, GRIEVANCE, COLLABORATION types
- HC-4: 10 petitions/user/hour (configurable) (Story 1.4)
- D4: PostgreSQL time-bucket counters for rate limiting
- CT-11: Silent failure destroys legitimacy - fail loud on errors
- CT-12: Witnessing creates accountability - all actions have attribution
- CT-13: Halt rejects writes, allows reads
- NFR-1.1: p99 latency < 200ms
- NFR-3.1: No silent petition loss
- NFR-5.1: Rate limiting per identity

Developer Golden Rules:
1. CAPACITY CHECK FIRST - Check queue capacity before any work (Story 1.3)
2. RATE LIMIT CHECK SECOND - After capacity, check per-submitter rate (Story 1.4)
3. HALT CHECK - Service handles halt for writes
4. WITNESS EVERYTHING - Events written via EventWriterService (Story 1.2)
5. FAIL LOUD - Return meaningful RFC 7807 error responses
6. RECORD AFTER SUCCESS - Only record rate limit after successful persist
7. READS DURING HALT - GET endpoints work during halt

Note: This router is SEPARATE from the Story 7.2 petition router (/v1/petitions)
which handles cessation co-signing. This router handles Three Fates submissions.
"""

import base64
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.dependencies.petition_submission import (
    get_petition_submission_service,
    get_queue_capacity_service,
    get_rate_limiter,
)
from src.api.models.petition_submission import (
    PetitionSubmissionErrorResponse,
    PetitionSubmissionStatusResponse,
    PetitionTypeEnum,
    SubmitPetitionSubmissionRequest,
    SubmitPetitionSubmissionResponse,
)
from src.application.ports.rate_limiter import RateLimiterPort
from src.application.services.petition_submission_service import (
    InvalidRealmError,
    PetitionSubmissionService,
)
from src.application.services.queue_capacity_service import QueueCapacityService
from src.domain.errors import QueueOverflowError, RateLimitExceededError, SystemHaltedError
from src.domain.models.petition_submission import PetitionType

router = APIRouter(prefix="/v1/petition-submissions", tags=["petition-submissions"])


# =============================================================================
# Type Mapping
# =============================================================================


def _api_type_to_domain(api_type: PetitionTypeEnum) -> PetitionType:
    """Convert API enum to domain enum."""
    return PetitionType(api_type.value)


def _domain_type_to_api(domain_type: PetitionType) -> PetitionTypeEnum:
    """Convert domain enum to API enum."""
    return PetitionTypeEnum(domain_type.value)


# =============================================================================
# Petition Submission Endpoints
# =============================================================================


@router.post(
    "",
    response_model=SubmitPetitionSubmissionResponse,
    status_code=201,
    responses={
        400: {
            "model": PetitionSubmissionErrorResponse,
            "description": "Invalid petition data",
        },
        429: {
            "model": PetitionSubmissionErrorResponse,
            "description": "Rate limit exceeded (Story 1.4)",
        },
        503: {
            "model": PetitionSubmissionErrorResponse,
            "description": "System halted or queue overflow",
        },
    },
    summary="Submit a new petition",
    description=(
        "Submit a new petition to the Three Fates deliberation system. "
        "Returns a petition_id and RECEIVED state. "
        "FR-1.1, FR-1.2, FR-1.3, FR-1.6, FR-10.1."
    ),
)
async def submit_petition_submission(
    request_data: SubmitPetitionSubmissionRequest,
    request: Request,
    service: PetitionSubmissionService = Depends(get_petition_submission_service),
    capacity_service: QueueCapacityService = Depends(get_queue_capacity_service),
    rate_limiter: RateLimiterPort = Depends(get_rate_limiter),
) -> SubmitPetitionSubmissionResponse:
    """Submit a new petition to the Three Fates system (FR-1.1, FR-1.4, FR-1.5).

    Constitutional Constraints:
    - FR-1.1: Accept petition submissions via REST API
    - FR-1.2: Generate petition_id
    - FR-1.3: Validate schema (via Pydantic)
    - FR-1.4: Return 503 if queue at capacity (Story 1.3)
    - FR-1.5: Return 429 if rate limit exceeded (Story 1.4)
    - FR-1.6: Set state to RECEIVED
    - FR-10.1: Support all petition types
    - HC-4: 10 petitions/user/hour (configurable)
    - CT-13: Rejected during halt (write operation)
    - HP-2: Content hash computed
    - NFR-3.1: No silent petition loss
    - NFR-5.1: Rate limiting per identity
    """
    try:
        # 1. CAPACITY CHECK FIRST (Story 1.3, FR-1.4)
        # Check queue depth before doing any work to fail fast
        if not await capacity_service.is_accepting_submissions():
            queue_depth = await capacity_service.get_queue_depth()
            threshold = capacity_service.get_threshold()
            retry_after = capacity_service.get_retry_after_seconds()
            # Record rejection metric (AC4)
            capacity_service.record_rejection()
            raise QueueOverflowError(
                queue_depth=queue_depth,
                threshold=threshold,
                retry_after_seconds=retry_after,
            )

        # 2. RATE LIMIT CHECK SECOND (Story 1.4, FR-1.5, HC-4)
        # Check per-submitter rate limit after capacity check (more specific)
        rate_result = await rate_limiter.check_rate_limit(request_data.submitter_id)
        if not rate_result.allowed:
            retry_seconds = int(
                (rate_result.reset_at - datetime.now(timezone.utc)).total_seconds()
            )
            retry_seconds = max(1, retry_seconds)  # Minimum 1 second
            raise RateLimitExceededError(
                submitter_id=request_data.submitter_id,
                current_count=rate_result.current_count,
                limit=rate_result.limit,
                reset_at=rate_result.reset_at,
                retry_after_seconds=retry_seconds,
            )

        # 3. Submit petition
        result = await service.submit_petition(
            petition_type=_api_type_to_domain(request_data.type),
            text=request_data.text,
            realm=request_data.realm,
        )

        # 4. RECORD RATE LIMIT AFTER SUCCESS (Story 1.4)
        # Only record submission after successful persist to avoid counting failures
        await rate_limiter.record_submission(request_data.submitter_id)

        return SubmitPetitionSubmissionResponse(
            petition_id=result.petition_id,
            state=result.state.value,
            type=_domain_type_to_api(result.petition_type),
            content_hash=result.content_hash,
            realm=result.realm,
            created_at=result.created_at,
        )

    except QueueOverflowError as e:
        # Queue overflow - return 503 with Retry-After (FR-1.4, AC3)
        raise HTTPException(
            status_code=503,
            detail={
                "type": "https://archon72.io/errors/queue-overflow",
                "title": "Queue Overflow",
                "status": 503,
                "detail": str(e),
                "instance": str(request.url),
                "queue_depth": e.queue_depth,
                "threshold": e.threshold,
            },
            headers={"Retry-After": str(e.retry_after_seconds)},
        ) from None

    except RateLimitExceededError as e:
        # Rate limit exceeded - return 429 with Retry-After (FR-1.5, HC-4, D7)
        raise HTTPException(
            status_code=429,
            detail={
                "type": "urn:archon72:petition:rate-limit-exceeded",
                "title": "Rate Limit Exceeded",
                "status": 429,
                "detail": f"Maximum {e.limit} petitions per hour exceeded",
                "instance": str(request.url),
                # Rate limit extensions (AC1)
                "rate_limit_remaining": 0,
                "rate_limit_reset": e.reset_at.isoformat(),
                "rate_limit_limit": e.limit,
                "rate_limit_current": e.current_count,
                # Governance extensions (D7)
                "actor": f"submitter:{e.submitter_id}",
            },
            headers={"Retry-After": str(e.retry_after_seconds)},
        ) from None

    except SystemHaltedError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "type": "https://archon72.io/errors/system-halted",
                "title": "System Halted",
                "status": 503,
                "detail": str(e),
                "instance": str(request.url),
            },
            headers={"Retry-After": "3600"},  # 1 hour default
        ) from None

    except InvalidRealmError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://archon72.io/errors/invalid-realm",
                "title": "Invalid Realm",
                "status": 400,
                "detail": str(e),
                "instance": str(request.url),
            },
        ) from None

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://archon72.io/errors/invalid-petition",
                "title": "Invalid Petition Submission",
                "status": 400,
                "detail": str(e),
                "instance": str(request.url),
            },
        ) from None


@router.get(
    "/{petition_id}",
    response_model=PetitionSubmissionStatusResponse,
    responses={
        404: {
            "model": PetitionSubmissionErrorResponse,
            "description": "Petition not found",
        },
    },
    summary="Get petition status",
    description=(
        "Get the current status of a petition submission. "
        "Public access - works during halt (read operation). "
        "FR-7.1, FR-7.4, NFR-1.2, CT-13."
    ),
)
async def get_petition_submission(
    petition_id: UUID,
    request: Request,
    service: PetitionSubmissionService = Depends(get_petition_submission_service),
) -> PetitionSubmissionStatusResponse:
    """Get petition submission status (FR-7.1, FR-7.4, Story 1.8).

    Constitutional Constraints:
    - FR-7.1: Observers can query petition status
    - FR-7.4: System exposes co_signer_count in response
    - NFR-1.2: Status query latency p99 < 100ms
    - CT-13: Reads allowed during halt
    - D7: RFC 7807 error responses with governance extensions
    """
    submission = await service.get_petition(petition_id)

    if submission is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "https://archon72.io/errors/petition-not-found",
                "title": "Petition Not Found",
                "status": 404,
                "detail": f"Petition {petition_id} not found",
                "instance": str(request.url),
            },
        )

    # Encode content hash if present
    content_hash_b64 = None
    if submission.content_hash:
        content_hash_b64 = base64.b64encode(submission.content_hash).decode("ascii")

    # Only include fate_reason for terminal states (AC3)
    fate_reason = None
    if submission.state.is_terminal():
        fate_reason = submission.fate_reason

    return PetitionSubmissionStatusResponse(
        petition_id=submission.id,
        state=submission.state.value,
        type=_domain_type_to_api(submission.type),
        content_hash=content_hash_b64,
        realm=submission.realm,
        co_signer_count=submission.co_signer_count,
        created_at=submission.created_at,
        updated_at=submission.updated_at,
        fate_reason=fate_reason,
    )
