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
import time
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from src.api.dependencies.petition_submission import (
    get_petition_submission_service,
    get_queue_capacity_service,
    get_rate_limiter,
    get_transcript_access_service,
)
from src.api.models.deliberation_summary import (
    DeliberationOutcomeEnum,
    DeliberationPendingErrorResponse,
    DeliberationPhaseEnum,
    DeliberationSummaryResponse,
    EscalationTriggerEnum,
    PetitionNotFoundErrorResponse,
    PhaseSummaryModel,
)
from src.api.models.petition_submission import (
    PetitionSubmissionErrorResponse,
    PetitionSubmissionStatusResponse,
    PetitionTypeEnum,
    SubmitPetitionSubmissionRequest,
    SubmitPetitionSubmissionResponse,
    WithdrawPetitionRequest,
    WithdrawPetitionResponse,
)
from src.application.ports.rate_limiter import RateLimiterPort
from src.application.services.petition_submission_service import (
    InvalidRealmError,
    PetitionSubmissionService,
)
from src.application.services.queue_capacity_service import QueueCapacityService
from src.application.services.transcript_access_mediation_service import (
    TranscriptAccessMediationService,
)
from src.bootstrap.metrics import get_metrics_collector
from src.bootstrap.status_token_registry import get_status_token_registry
from src.domain.errors import (
    QueueOverflowError,
    RateLimitExceededError,
    SystemHaltedError,
    UnauthorizedWithdrawalError,
)
from src.domain.errors.deliberation import DeliberationPendingError
from src.domain.errors.petition import PetitionNotFoundError
from src.domain.errors.state_transition import PetitionAlreadyFatedError
from src.domain.models.petition_submission import PetitionType
from src.domain.models.status_token import (
    ExpiredStatusTokenError,
    InvalidStatusTokenError,
    StatusToken,
)

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
        if request_data.submitter_id is not None:
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
            submitter_id=request_data.submitter_id,
        )

        # 4. RECORD RATE LIMIT AFTER SUCCESS (Story 1.4)
        # Only record submission after successful persist to avoid counting failures
        if request_data.submitter_id is not None:
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
        "Returns status_token for efficient long-polling. "
        "FR-7.1, FR-7.2, FR-7.4, NFR-1.2, CT-13."
    ),
)
async def get_petition_submission(
    petition_id: UUID,
    request: Request,
    service: PetitionSubmissionService = Depends(get_petition_submission_service),
) -> PetitionSubmissionStatusResponse:
    """Get petition submission status (FR-7.1, FR-7.2, FR-7.4, Story 1.8, Story 7.1).

    Constitutional Constraints:
    - FR-7.1: Observers can query petition status
    - FR-7.2: System returns status_token for efficient long-poll (Story 7.1)
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

    # Generate status_token for long-polling (FR-7.2, Story 7.1)
    # Version is computed from content hash and state for deterministic change detection
    state_version = StatusToken.compute_version_from_hash(
        submission.content_hash, submission.state.value
    )
    status_token = StatusToken.create(
        petition_id=submission.id,
        version=state_version,
    )

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
        status_token=status_token.encode(),
    )


# Long-poll timeout in seconds (AC2)
LONGPOLL_TIMEOUT_SECONDS = 30.0


@router.get(
    "/{petition_id}/status",
    response_model=PetitionSubmissionStatusResponse,
    responses={
        304: {
            "description": "Not Modified - no state change within timeout",
        },
        400: {
            "model": PetitionSubmissionErrorResponse,
            "description": "Invalid or expired status token",
        },
        404: {
            "model": PetitionSubmissionErrorResponse,
            "description": "Petition not found",
        },
    },
    summary="Long-poll petition status",
    description=(
        "Long-poll for petition status changes using a status_token. "
        "Blocks until state changes or 30-second timeout (HTTP 304). "
        "Public access - works during halt (read operation). "
        "FR-7.2, NFR-1.2, CT-13, AC2."
    ),
)
async def longpoll_petition_status(
    petition_id: UUID,
    request: Request,
    token: str = Query(
        ...,
        description="Status token from previous status response",
    ),
    service: PetitionSubmissionService = Depends(get_petition_submission_service),
) -> Response | PetitionSubmissionStatusResponse:
    """Long-poll for petition status changes (Story 7.1, FR-7.2, AC2).

    Constitutional Constraints:
    - FR-7.2: System SHALL return status_token for efficient long-poll
    - NFR-1.2: Response latency < 100ms p99 on state change
    - CT-13: Reads allowed during halt
    - AC2: 30-second timeout with HTTP 304
    - AC3: Efficient connection management (no busy-wait)
    - D7: RFC 7807 error responses

    Flow:
    1. Validate token (petition_id match, expiry)
    2. Check if state already changed (return immediately)
    3. Wait for state change (max 30 seconds)
    4. On timeout: return HTTP 304 Not Modified
    5. On change: return new status with new token
    """
    start_time = time.monotonic()
    metrics = get_metrics_collector()
    registry = await get_status_token_registry()

    # 1. Validate token
    try:
        status_token = StatusToken.decode(token)
        status_token.validate_petition_id(petition_id)
        status_token.validate_not_expired()
    except InvalidStatusTokenError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://archon72.io/errors/invalid-status-token",
                "title": "Invalid Status Token",
                "status": 400,
                "detail": str(e),
                "instance": str(request.url),
            },
        ) from None
    except ExpiredStatusTokenError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://archon72.io/errors/expired-status-token",
                "title": "Expired Status Token",
                "status": 400,
                "detail": str(e),
                "instance": str(request.url),
                "max_age_seconds": e.max_age_seconds,
            },
        ) from None

    # 2. Get current petition state
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

    # Compute current version
    current_version = StatusToken.compute_version_from_hash(
        submission.content_hash, submission.state.value
    )

    # 3. Check if already changed (return immediately)
    if status_token.has_changed(current_version):
        duration = time.monotonic() - start_time
        metrics.increment_longpoll_changed()
        metrics.observe_longpoll_latency(duration, "immediate")
        return _build_status_response(submission, current_version)

    # 4. Wait for state change (with metrics tracking)
    metrics.increment_longpoll_connections()
    try:
        # Register current version in registry
        await registry.register_petition(petition_id, current_version)

        # Wait for change
        changed = await registry.wait_for_change(
            petition_id=petition_id,
            current_version=current_version,
            timeout_seconds=LONGPOLL_TIMEOUT_SECONDS,
        )

        duration = time.monotonic() - start_time

        if not changed:
            # 5a. Timeout - return HTTP 304 Not Modified
            metrics.increment_longpoll_timeout()
            metrics.observe_longpoll_latency(duration, "timeout")
            return Response(
                status_code=304,
                headers={
                    "X-Status-Token": token,  # Return same token
                    "Cache-Control": "no-cache",
                },
            )

        # 5b. State changed - fetch new state and return
        metrics.increment_longpoll_changed()
        metrics.observe_longpoll_latency(duration, "changed")

        # Re-fetch petition to get updated state
        submission = await service.get_petition(petition_id)
        if submission is None:
            # Petition was deleted during wait
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "https://archon72.io/errors/petition-not-found",
                    "title": "Petition Not Found",
                    "status": 404,
                    "detail": f"Petition {petition_id} was deleted",
                    "instance": str(request.url),
                },
            )

        new_version = StatusToken.compute_version_from_hash(
            submission.content_hash, submission.state.value
        )
        return _build_status_response(submission, new_version)

    finally:
        metrics.decrement_longpoll_connections()


def _build_status_response(
    submission: "PetitionSubmission", version: int  # noqa: F821
) -> PetitionSubmissionStatusResponse:
    """Build a status response with token for the given submission.

    Args:
        submission: The petition submission domain object.
        version: Computed state version for the token.

    Returns:
        PetitionSubmissionStatusResponse with status_token.
    """
    # Encode content hash if present
    content_hash_b64 = None
    if submission.content_hash:
        content_hash_b64 = base64.b64encode(submission.content_hash).decode("ascii")

    # Only include fate_reason for terminal states
    fate_reason = None
    if submission.state.is_terminal():
        fate_reason = submission.fate_reason

    # Generate new token
    new_token = StatusToken.create(
        petition_id=submission.id,
        version=version,
    )

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
        status_token=new_token.encode(),
    )


# =============================================================================
# Petition Withdrawal Endpoint (Story 7.3, FR-7.5)
# =============================================================================


@router.post(
    "/{petition_id}/withdraw",
    response_model=WithdrawPetitionResponse,
    status_code=200,
    responses={
        400: {
            "model": PetitionSubmissionErrorResponse,
            "description": "Petition already fated (cannot withdraw)",
        },
        403: {
            "model": PetitionSubmissionErrorResponse,
            "description": "Unauthorized withdrawal (not the original petitioner)",
        },
        404: {
            "model": PetitionSubmissionErrorResponse,
            "description": "Petition not found",
        },
        503: {
            "model": PetitionSubmissionErrorResponse,
            "description": "System halted",
        },
    },
    summary="Withdraw a petition",
    description=(
        "Withdraw a petition before fate assignment. "
        "Only the original petitioner can withdraw. "
        "Anonymous petitions cannot be withdrawn. "
        "FR-7.5, CT-13, D7."
    ),
)
async def withdraw_petition(
    petition_id: UUID,
    request_data: WithdrawPetitionRequest,
    request: Request,
    service: PetitionSubmissionService = Depends(get_petition_submission_service),
) -> WithdrawPetitionResponse:
    """Withdraw a petition before fate assignment (Story 7.3, FR-7.5).

    Constitutional Constraints:
    - FR-7.5: Petitioner can withdraw before fate assignment
    - CT-13: Rejected during halt (write operation)
    - D7: RFC 7807 error responses with governance extensions
    - AC1: Successful withdrawal transitions to ACKNOWLEDGED with WITHDRAWN reason
    - AC2: Cannot withdraw already-fated petitions (400)
    - AC3: Only original petitioner can withdraw (403)
    - AC4: Petition must exist (404)
    - AC5: System must not be halted (503)
    """
    try:
        result = await service.withdraw_petition(
            petition_id=petition_id,
            requester_id=request_data.requester_id,
            reason=request_data.reason,
        )

        return WithdrawPetitionResponse(
            petition_id=result.id,
            state=result.state.value,
            fate_reason=result.fate_reason or "WITHDRAWN: Petitioner withdrew",
            updated_at=result.updated_at,
        )

    except PetitionNotFoundError:
        # AC4: Petition not found - 404
        raise HTTPException(
            status_code=404,
            detail={
                "type": "urn:archon72:petition:not-found",
                "title": "Petition Not Found",
                "status": 404,
                "detail": f"Petition {petition_id} not found",
                "instance": str(request.url),
                "petition_id": str(petition_id),
            },
        ) from None

    except UnauthorizedWithdrawalError as e:
        # AC3: Unauthorized - 403
        raise HTTPException(
            status_code=403,
            detail={
                "type": "urn:archon72:petition:unauthorized-withdrawal",
                "title": "Unauthorized Withdrawal",
                "status": 403,
                "detail": str(e),
                "instance": str(request.url),
                "petition_id": str(petition_id),
                # Governance extension (D7)
                "actor": f"submitter:{request_data.requester_id}",
            },
        ) from None

    except PetitionAlreadyFatedError as e:
        # AC2: Already fated - 400
        raise HTTPException(
            status_code=400,
            detail={
                "type": "urn:archon72:petition:already-fated",
                "title": "Petition Already Fated",
                "status": 400,
                "detail": f"Cannot withdraw petition {petition_id}: already fated as {e.terminal_state.value}",
                "instance": str(request.url),
                "petition_id": str(petition_id),
                "current_state": e.terminal_state.value,
            },
        ) from None

    except SystemHaltedError as e:
        # AC5: System halted - 503
        raise HTTPException(
            status_code=503,
            detail={
                "type": "urn:archon72:system:halted",
                "title": "System Halted",
                "status": 503,
                "detail": str(e),
                "instance": str(request.url),
            },
            headers={"Retry-After": "3600"},  # 1 hour default
        ) from None


# =============================================================================
# Deliberation Summary Endpoint (Story 7.4, FR-7.4, Ruling-2)
# =============================================================================


@router.get(
    "/{petition_id}/deliberation-summary",
    response_model=DeliberationSummaryResponse,
    responses={
        400: {
            "model": DeliberationPendingErrorResponse,
            "description": "Deliberation not yet complete (AC-3)",
        },
        404: {
            "model": PetitionNotFoundErrorResponse,
            "description": "Petition not found (AC-4)",
        },
    },
    summary="Get deliberation summary",
    description=(
        "Get mediated deliberation summary for a petition (Observer tier access). "
        "Returns outcome, vote breakdown, phase metadata, and hash references. "
        "Does NOT expose raw transcripts, Archon identities, or who voted for what. "
        "FR-7.4, Ruling-2, CT-13 (reads allowed during halt). "
        "AC-5: This is a read operation, permitted during halt."
    ),
)
async def get_deliberation_summary(
    petition_id: UUID,
    request: Request,
    service: TranscriptAccessMediationService = Depends(get_transcript_access_service),
) -> DeliberationSummaryResponse:
    """Get mediated deliberation summary (Story 7.4, FR-7.4, Ruling-2).

    Constitutional Constraints:
    - FR-7.4: System SHALL provide deliberation summary to Observer
    - Ruling-2: Tiered transcript access - mediated view
    - CT-13: Reads allowed during halt (AC-5)
    - D7: RFC 7807 error responses
    - PRD Section 13A.8: Observer tier access

    MEDIATION GUARANTEES (Ruling-2):
    - Vote breakdown is anonymous ("2-1", not who voted what)
    - has_dissent is boolean only, not dissenter identity
    - Phase summaries are metadata + hashes, not content
    - No Archon UUIDs exposed anywhere

    Acceptance Criteria:
    - AC-1: Returns DeliberationSummary with mediated fields
    - AC-2: Handles auto-escalation (no deliberation session)
    - AC-3: Returns 400 if deliberation not complete
    - AC-4: Returns 404 if petition not found
    - AC-5: Read operation works during halt
    - AC-6: Handles timeout-triggered escalation
    - AC-7: Handles deadlock-triggered escalation
    """
    try:
        summary = await service.get_deliberation_summary(petition_id)

        # Convert domain model to API response
        phase_summaries = [
            PhaseSummaryModel(
                phase=DeliberationPhaseEnum(ps.phase.value),
                duration_seconds=ps.duration_seconds,
                transcript_hash_hex=ps.transcript_hash_hex,
                themes=list(ps.themes) if ps.themes else None,
                convergence_reached=ps.convergence_reached,
            )
            for ps in summary.phase_summaries
        ]

        return DeliberationSummaryResponse(
            petition_id=str(summary.petition_id),
            outcome=DeliberationOutcomeEnum(summary.outcome.value),
            vote_breakdown=summary.vote_breakdown,
            has_dissent=summary.has_dissent,
            phase_summaries=phase_summaries,
            duration_seconds=summary.duration_seconds,
            completed_at=summary.completed_at,
            escalation_trigger=(
                EscalationTriggerEnum(summary.escalation_trigger.value)
                if summary.escalation_trigger
                else None
            ),
            escalation_reason=summary.escalation_reason,
            timed_out=summary.timed_out,
            rounds_attempted=summary.rounds_attempted,
        )

    except PetitionNotFoundError:
        # AC-4: Petition not found - 404
        raise HTTPException(
            status_code=404,
            detail={
                "type": "urn:archon72:petition:not-found",
                "title": "Petition Not Found",
                "status": 404,
                "detail": f"Petition {petition_id} not found",
                "instance": str(request.url),
            },
        ) from None

    except DeliberationPendingError as e:
        # AC-3: Deliberation not complete - 400
        raise HTTPException(
            status_code=400,
            detail={
                "type": "urn:archon72:petition:deliberation-pending",
                "title": "Deliberation Pending",
                "status": 400,
                "detail": str(e),
                "instance": str(request.url),
            },
        ) from None
