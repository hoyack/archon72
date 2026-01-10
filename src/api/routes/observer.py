"""Observer API routes (Story 4.1, Task 3; Story 4.2, Tasks 4, 7; Story 4.3, Task 1; Story 4.5, Task 2; Story 4.6, Tasks 5, 6; Story 4.7, Task 3; Story 4.8, Tasks 3, 4; Story 4.9, Tasks 1, 2, 4; Story 7.10 - FR144).

FastAPI router for public event access endpoints.

Constitutional Constraints:
- FR44: No authentication required for read endpoints
- FR46: Query interface supports date range and event type filtering
- FR48: Rate limits identical for all users
- FR62: Raw event data for independent hash computation
- FR63: Exact hash algorithm, encoding, field ordering as immutable spec
- FR64: Verification bundles for offline verification
- FR88: Query for state as of any sequence number or timestamp
- FR89: Historical queries return hash chain proof to current head
- FR136: Merkle proof SHALL be included in event query responses when requested
- FR137: Observers SHALL be able to verify event inclusion without downloading full chain
- FR138: Weekly checkpoint anchors SHALL be published at consistent intervals
- FR139: Export SHALL support structured audit format (JSON Lines, CSV)
- FR140: Third-party attestation interface with attestation metadata
- FR144: System SHALL maintain published Integrity Case Artifact (Story 7.10)
- SR-9: Observer push notifications - webhook/SSE for breach events
- RT-5: Breach events pushed to multiple channels, 99.9% uptime SLA
- CT-11: Silent failure destroys legitimacy - notification delivery logged
- CT-12: Witnessing creates accountability - notification events have attribution
- CT-13: Reads allowed during halt (per Story 3.5)
- ADR-8: Observer Consistency + Genesis Anchor - checkpoint fallback during outage
"""

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.api.adapters.observer import EventToObserverAdapter
from src.api.dependencies.observer import (
    get_deliberation_recorder,
    get_export_service,
    get_integrity_case_service,
    get_notification_service,
    get_observer_service,
    get_rate_limiter,
)
from src.application.ports.final_deliberation_recorder import FinalDeliberationRecorder
from src.api.middleware.rate_limiter import ObserverRateLimiter
from src.api.models.observer import (
    ArchonDeliberationResponse,
    ArchonPositionResponse,
    AttestationMetadata,
    CessationTriggerConditionResponse,
    CessationTriggerConditionsJsonLdResponse,
    CessationTriggerConditionsResponse,
    ChainVerificationResult,
    CheckpointAnchor,
    CheckpointFallback,
    DependencyHealth,
    ExportFormat,
    FinalDeliberationResponse,
    HashChainProof,
    HashVerificationSpec,
    HistoricalQueryMetadata,
    IntegrityCaseHistoryResponse,
    IntegrityCaseJsonLdResponse,
    IntegrityCaseResponse,
    IntegrityGuaranteeResponse,
    MerkleProof,
    NotificationEventType,
    NotificationPayload,
    ObserverEventResponse,
    ObserverEventsListResponse,
    ObserverHealthResponse,
    ObserverHealthStatus,
    ObserverReadyResponse,
    PaginationMetadata,
    SchemaDocumentation,
    VoteCountsResponse,
    WebhookSubscription,
    WebhookSubscriptionResponse,
)
from src.application.services.export_service import ExportService
from src.application.services.integrity_case_service import IntegrityCaseService
from src.application.services.notification_service import NotificationService
from src.application.services.observer_service import ObserverService
from src.domain.errors.event_store import EventNotFoundError


router = APIRouter(prefix="/v1/observer", tags=["observer"])


# =============================================================================
# API Lifecycle Tracking (Story 4.9 - RT-5)
# =============================================================================

# Track API startup time for uptime calculation
_API_START_TIME: float = time.time()
_API_READY: bool = False


def mark_api_ready() -> None:
    """Mark API as ready after startup initialization.

    Called when FastAPI lifespan startup completes.
    Per RT-5: Track readiness for external monitoring.
    """
    global _API_READY
    _API_READY = True


def get_api_uptime_seconds() -> float:
    """Get current API uptime in seconds.

    Returns:
        Seconds since API started.
    """
    return time.time() - _API_START_TIME


# No authentication dependency - this is intentional per FR44
# Rate limiter applies equally to all users per FR48


async def apply_rate_limit(
    request: Request,
    rate_limiter: Annotated[ObserverRateLimiter, Depends(get_rate_limiter)],
) -> None:
    """Apply rate limiting to request.

    Per FR48: Rate limits MUST be identical for anonymous and authenticated.
    """
    await rate_limiter.check_rate_limit(request)


@router.get("/verification-spec", response_model=HashVerificationSpec)
async def get_verification_spec(
    request: Request,
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> HashVerificationSpec:
    """Get hash verification specification.

    Returns the exact hash computation method for independent
    verification (FR62, FR63).

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    This endpoint returns the immutable specification that observers
    can use to independently verify chain integrity:
    - Hash algorithm and version
    - Signature algorithm and version
    - Genesis hash for chain root
    - Fields included/excluded from hash computation
    - JSON canonicalization rules
    - Hash encoding format

    Args:
        request: The FastAPI request object.
        rate_limiter: Injected rate limiter.

    Returns:
        HashVerificationSpec containing the verification documentation.
    """
    await rate_limiter.check_rate_limit(request)
    return HashVerificationSpec()


@router.get("/schema", response_model=SchemaDocumentation)
async def get_schema_docs(
    request: Request,
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> SchemaDocumentation:
    """Get schema documentation for Observer API (FR50).

    Returns versioned schema documentation with same availability
    as the event store.

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    This endpoint returns:
    - Schema version and API version
    - Last updated timestamp
    - List of supported event types
    - JSON Schema for event format
    - URL to verification specification

    Args:
        request: The FastAPI request object.
        rate_limiter: Injected rate limiter.

    Returns:
        SchemaDocumentation containing the API schema documentation.
    """
    await rate_limiter.check_rate_limit(request)
    return SchemaDocumentation()


@router.get("/events", response_model=ObserverEventsListResponse)
async def get_events(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    start_date: Optional[datetime] = Query(
        default=None,
        description="Filter events from this date (ISO 8601 format, e.g., 2026-01-01T00:00:00Z)",
    ),
    end_date: Optional[datetime] = Query(
        default=None,
        description="Filter events until this date (ISO 8601 format, e.g., 2026-01-31T23:59:59Z)",
    ),
    event_type: Optional[str] = Query(
        default=None,
        description="Filter by event type(s), comma-separated (e.g., vote,halt,breach)",
    ),
    as_of_sequence: Optional[int] = Query(
        default=None,
        ge=1,
        description="Query state as of this sequence number (FR88). Returns events with sequence <= value.",
    ),
    as_of_timestamp: Optional[datetime] = Query(
        default=None,
        description="Query state as of this timestamp (FR88). Returns events up to the last event before timestamp.",
    ),
    include_proof: bool = Query(
        default=False,
        description="Include hash chain proof connecting queried state to current head (FR89).",
    ),
    include_merkle_proof: bool = Query(
        default=False,
        description="Include Merkle proof for O(log n) verification (FR136). Only available for checkpointed events.",
    ),
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> ObserverEventsListResponse:
    """Get events for observer verification with optional filters and historical queries.

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    Filtering (FR46):
    - start_date: ISO 8601 datetime, events from this timestamp (inclusive)
    - end_date: ISO 8601 datetime, events until this timestamp (inclusive)
    - event_type: Comma-separated event types (e.g., "vote,halt,breach")

    Historical Queries (FR88, FR89):
    - as_of_sequence: Return events up to this sequence number
    - as_of_timestamp: Return events up to the last event before this timestamp
    - include_proof: Include hash chain proof to current head

    Merkle Proofs (FR136, FR137):
    - include_merkle_proof: Include O(log n) Merkle proof for checkpointed events

    Filters are combined with AND logic. Date filters apply to authority_timestamp.
    Multiple event types use OR logic (any of the specified types match).

    Returns events with full hash chain data for independent verification.

    Args:
        request: The FastAPI request object.
        limit: Maximum number of events to return (1-1000).
        offset: Number of events to skip.
        start_date: Filter events from this date (inclusive).
        end_date: Filter events until this date (inclusive).
        event_type: Filter by event type(s), comma-separated.
        as_of_sequence: Query state as of this sequence (FR88).
        as_of_timestamp: Query state as of this timestamp (FR88).
        include_proof: Include hash chain proof (FR89).
        include_merkle_proof: Include Merkle proof (FR136).
        observer_service: Injected observer service.
        rate_limiter: Injected rate limiter.

    Returns:
        List of events with pagination metadata, and optional historical query info.

    Raises:
        HTTPException: 404 if as_of_sequence doesn't exist, 400 if both as_of params specified.
    """
    # Apply rate limiting
    await rate_limiter.check_rate_limit(request)

    # Validate mutually exclusive parameters
    if as_of_sequence is not None and as_of_timestamp is not None:
        raise HTTPException(
            status_code=400,
            detail="Cannot specify both as_of_sequence and as_of_timestamp. Use one or the other.",
        )

    # Parse event types from comma-separated string with input validation
    # Security: Limit number of event types to prevent resource exhaustion
    MAX_EVENT_TYPES = 20
    event_types: Optional[list[str]] = None
    if event_type:
        raw_types = [t.strip() for t in event_type.split(",") if t.strip()]
        if len(raw_types) > MAX_EVENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum {MAX_EVENT_TYPES} event types allowed per query. Received {len(raw_types)}.",
            )
        event_types = raw_types

    # Historical query handling (FR88, FR89, FR136)
    if as_of_sequence is not None:
        try:
            # Use Merkle proof method if requested (FR136)
            if include_merkle_proof:
                events, total, merkle_proof, hash_proof = await observer_service.get_events_with_merkle_proof(
                    as_of_sequence=as_of_sequence,
                    limit=limit,
                    offset=offset,
                )

                # Get current head for metadata
                current_head = await observer_service._event_store.get_max_sequence()

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
                    historical_query=HistoricalQueryMetadata(
                        queried_as_of_sequence=as_of_sequence,
                        resolved_sequence=as_of_sequence,
                        current_head_sequence=current_head,
                    ),
                    merkle_proof=merkle_proof,
                    proof=hash_proof,  # Fallback hash chain proof for pending events
                )
            else:
                events, total, proof = await observer_service.get_events_as_of(
                    as_of_sequence=as_of_sequence,
                    limit=limit,
                    offset=offset,
                    include_proof=include_proof,
                )

                # Get current head for metadata
                current_head = await observer_service._event_store.get_max_sequence()

                # Convert to API response
                event_responses = EventToObserverAdapter.to_response_list(events)
                has_more = (offset + len(events)) < total

                # Build response with historical metadata
                return ObserverEventsListResponse(
                    events=event_responses,
                    pagination=PaginationMetadata(
                        total_count=total,
                        offset=offset,
                        limit=limit,
                        has_more=has_more,
                    ),
                    historical_query=HistoricalQueryMetadata(
                        queried_as_of_sequence=as_of_sequence,
                        resolved_sequence=as_of_sequence,
                        current_head_sequence=current_head,
                    ),
                    proof=proof,
                )
        except EventNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

    elif as_of_timestamp is not None:
        events, total, resolved_seq, proof = await observer_service.get_events_as_of_timestamp(
            as_of_timestamp=as_of_timestamp,
            limit=limit,
            offset=offset,
            include_proof=include_proof,
        )

        if resolved_seq == 0:
            # No events before timestamp
            return ObserverEventsListResponse(
                events=[],
                pagination=PaginationMetadata(
                    total_count=0,
                    offset=offset,
                    limit=limit,
                    has_more=False,
                ),
                historical_query=HistoricalQueryMetadata(
                    queried_as_of_timestamp=as_of_timestamp,
                    resolved_sequence=0,
                    current_head_sequence=0,
                ),
            )

        # Get current head for metadata
        current_head = await observer_service._event_store.get_max_sequence()

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
            historical_query=HistoricalQueryMetadata(
                queried_as_of_timestamp=as_of_timestamp,
                resolved_sequence=resolved_seq,
                current_head_sequence=current_head,
            ),
            proof=proof,
        )

    # Standard query (non-historical)
    # Check if any filters are applied
    has_filters = start_date is not None or end_date is not None or event_types is not None

    if has_filters:
        # Use filtered query
        events, total = await observer_service.get_events_filtered(
            limit=limit,
            offset=offset,
            start_date=start_date,
            end_date=end_date,
            event_types=event_types,
        )
    else:
        # Use standard query (backwards compatible)
        events, total = await observer_service.get_events(limit=limit, offset=offset)

    # Convert to API response
    event_responses = EventToObserverAdapter.to_response_list(events)

    # Calculate has_more
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


@router.get("/events/sequence/{sequence}", response_model=ObserverEventResponse)
async def get_event_by_sequence(
    request: Request,
    sequence: int,
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> ObserverEventResponse:
    """Get single event by sequence number.

    No authentication required (FR44).
    Sequence is the authoritative ordering (Story 1.5).

    Args:
        request: The FastAPI request object.
        sequence: The sequence number of the event.
        observer_service: Injected observer service.
        rate_limiter: Injected rate limiter.

    Returns:
        The event if found.

    Raises:
        HTTPException: 404 if event not found.
    """
    # Apply rate limiting
    await rate_limiter.check_rate_limit(request)

    event = await observer_service.get_event_by_sequence(sequence)

    if event is None:
        raise HTTPException(
            status_code=404,
            detail=f"Event with sequence {sequence} not found",
        )

    return EventToObserverAdapter.to_response(event)


# =============================================================================
# SSE Stream Endpoint - MUST be before /events/{event_id} due to route matching
# =============================================================================


@router.get("/events/stream")
async def stream_events(
    request: Request,
    event_types: Optional[str] = Query(
        default=None,
        description="Event types to receive, comma-separated (breach,halt,fork). Default: all",
    ),
    notification_service: NotificationService = Depends(get_notification_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> EventSourceResponse:
    """Stream events via Server-Sent Events (SR-9).

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    Per SR-9: Observer push notifications via SSE.
    Per RT-5: Breach events pushed in real-time.

    Supports automatic reconnection via Last-Event-ID header.
    Sends keepalive comments every 30 seconds.

    Event types:
    - breach: Constitutional breach detected
    - halt: System halt triggered
    - fork: Fork detected in event chain
    - constitutional_crisis: Constitutional crisis declared
    - all: All of the above (default)

    Args:
        request: The FastAPI request object.
        event_types: Filter by event types (comma-separated).
        notification_service: Injected notification service.
        rate_limiter: Injected rate limiter.

    Returns:
        EventSourceResponse streaming notifications.
    """
    await rate_limiter.check_rate_limit(request)

    # Parse event types
    parsed_types: list[NotificationEventType] = [NotificationEventType.ALL]
    if event_types:
        parsed_types = []
        for t in event_types.split(","):
            t_stripped = t.strip().lower()
            try:
                parsed_types.append(NotificationEventType(t_stripped))
            except ValueError:
                # Invalid type, skip
                pass
        if not parsed_types:
            parsed_types = [NotificationEventType.ALL]

    # Register SSE connection
    connection_id, queue = notification_service.register_sse_connection(parsed_types)

    # Get Last-Event-ID for reconnection support
    last_event_id = request.headers.get("Last-Event-ID")

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        """Generate SSE events with keepalive."""
        try:
            while True:
                try:
                    # Wait for event with timeout for keepalive
                    payload: NotificationPayload = await asyncio.wait_for(
                        queue.get(), timeout=30.0
                    )
                    yield {
                        "event": payload.event_type,
                        "data": payload.model_dump_json(),
                        "id": str(payload.notification_id),
                    }
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield {"comment": "keepalive"}
        finally:
            # Cleanup on disconnect
            notification_service.unregister_sse_connection(connection_id)

    return EventSourceResponse(
        event_generator(),
        headers={
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Cache-Control": "no-cache",
        },
    )


@router.get("/events/{event_id}", response_model=ObserverEventResponse)
async def get_event_by_id(
    request: Request,
    event_id: UUID,
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> ObserverEventResponse:
    """Get single event by ID.

    No authentication required (FR44).

    Args:
        request: The FastAPI request object.
        event_id: The UUID of the event.
        observer_service: Injected observer service.
        rate_limiter: Injected rate limiter.

    Returns:
        The event if found.

    Raises:
        HTTPException: 404 if event not found.
    """
    # Apply rate limiting
    await rate_limiter.check_rate_limit(request)

    event = await observer_service.get_event_by_id(event_id)

    if event is None:
        raise HTTPException(
            status_code=404,
            detail=f"Event with ID {event_id} not found",
        )

    return EventToObserverAdapter.to_response(event)


@router.get("/verify-chain", response_model=ChainVerificationResult)
async def verify_chain(
    request: Request,
    start: int = Query(ge=1, description="First sequence number to verify"),
    end: int = Query(ge=1, description="Last sequence number to verify"),
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> ChainVerificationResult:
    """Verify hash chain integrity for a range of events (FR64).

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    Verifies that:
    1. prev_hash of each event matches content_hash of previous event
    2. For sequence 1, prev_hash equals the genesis constant (64 zeros)
    3. No sequence gaps exist in the range

    This allows observers to verify chain integrity without trusting
    the system's verification claims.

    Args:
        request: The FastAPI request object.
        start: First sequence number to verify (must be >= 1).
        end: Last sequence number to verify (must be >= start).
        observer_service: Injected observer service.
        rate_limiter: Injected rate limiter.

    Returns:
        ChainVerificationResult with:
        - is_valid: True if chain is valid
        - verified_count: Number of events verified
        - first_invalid_sequence: First failing sequence (if invalid)
        - error_message: Description of failure (if invalid)
    """
    await rate_limiter.check_rate_limit(request)

    result = await observer_service.verify_chain(start, end)

    return ChainVerificationResult(
        start_sequence=result.start_sequence,
        end_sequence=result.end_sequence,
        is_valid=result.is_valid,
        first_invalid_sequence=result.first_invalid_sequence,
        error_message=result.error_message,
        verified_count=result.verified_count,
    )


# =============================================================================
# Checkpoint Endpoints (Story 4.6, Task 5 - FR137, FR138)
# =============================================================================


class CheckpointListResponse(BaseModel):
    """Response model for checkpoint list."""

    checkpoints: list[CheckpointAnchor]
    pagination: PaginationMetadata


@router.get("/checkpoints", response_model=CheckpointListResponse)
async def list_checkpoints(
    request: Request,
    limit: int = Query(default=10, ge=1, le=100, description="Maximum checkpoints to return"),
    offset: int = Query(default=0, ge=0, description="Number to skip"),
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> CheckpointListResponse:
    """List checkpoint anchors with pagination (FR138).

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    Returns checkpoints ordered by event_sequence descending (most recent first).
    Per FR138: Weekly checkpoint anchors SHALL be published at consistent intervals.

    Args:
        request: The FastAPI request object.
        limit: Maximum checkpoints to return (1-100).
        offset: Number to skip.
        observer_service: Injected observer service.
        rate_limiter: Injected rate limiter.

    Returns:
        CheckpointListResponse with checkpoints and pagination.
    """
    await rate_limiter.check_rate_limit(request)

    checkpoints, total = await observer_service.list_checkpoints(limit=limit, offset=offset)

    # Convert domain checkpoints to API models
    checkpoint_responses = [
        CheckpointAnchor(
            checkpoint_id=cp.checkpoint_id,
            sequence_start=1,  # First event sequence for this checkpoint
            sequence_end=cp.event_sequence,
            merkle_root=cp.anchor_hash,
            created_at=cp.timestamp,
            anchor_type=cp.anchor_type if cp.anchor_type in ("genesis", "rfc3161", "pending") else "pending",
            anchor_reference=None,  # Will be populated when external anchoring is implemented
            event_count=cp.event_sequence,  # Events from 1 to sequence
        )
        for cp in checkpoints
    ]

    has_more = (offset + len(checkpoints)) < total

    return CheckpointListResponse(
        checkpoints=checkpoint_responses,
        pagination=PaginationMetadata(
            total_count=total,
            offset=offset,
            limit=limit,
            has_more=has_more,
        ),
    )


@router.get("/checkpoints/{sequence}", response_model=CheckpointAnchor)
async def get_checkpoint_for_sequence(
    request: Request,
    sequence: int,
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> CheckpointAnchor:
    """Get the checkpoint containing a specific event sequence.

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    Returns the checkpoint whose interval contains the given sequence.
    Returns 404 if the sequence is in the pending interval (not yet checkpointed).

    Args:
        request: The FastAPI request object.
        sequence: Event sequence number.
        observer_service: Injected observer service.
        rate_limiter: Injected rate limiter.

    Returns:
        CheckpointAnchor containing the sequence.

    Raises:
        HTTPException: 404 if sequence is in pending interval.
    """
    await rate_limiter.check_rate_limit(request)

    checkpoint = await observer_service.get_checkpoint_for_sequence(sequence)

    if checkpoint is None:
        raise HTTPException(
            status_code=404,
            detail=f"Sequence {sequence} is in the pending interval (not yet checkpointed)",
        )

    return CheckpointAnchor(
        checkpoint_id=checkpoint.checkpoint_id,
        sequence_start=1,
        sequence_end=checkpoint.event_sequence,
        merkle_root=checkpoint.anchor_hash,
        created_at=checkpoint.timestamp,
        anchor_type=checkpoint.anchor_type if checkpoint.anchor_type in ("genesis", "rfc3161", "pending") else "pending",
        anchor_reference=None,
        event_count=checkpoint.event_sequence,
    )


@router.get("/events/sequence/{sequence}/merkle-proof", response_model=MerkleProof)
async def get_merkle_proof(
    request: Request,
    sequence: int,
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> MerkleProof:
    """Get Merkle proof for a specific event sequence (FR136, FR137).

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    Per FR136: Merkle proof SHALL be included in event query responses when requested.
    Per FR137: Observers SHALL be able to verify event inclusion without downloading full chain.

    Returns a Merkle proof that allows O(log n) verification of event inclusion
    in the checkpoint containing that event.

    Args:
        request: The FastAPI request object.
        sequence: Event sequence number.
        observer_service: Injected observer service.
        rate_limiter: Injected rate limiter.

    Returns:
        MerkleProof for the event.

    Raises:
        HTTPException: 404 if sequence not found or in pending interval.
    """
    await rate_limiter.check_rate_limit(request)

    proof = await observer_service._generate_merkle_proof(sequence)

    if proof is None:
        raise HTTPException(
            status_code=404,
            detail=f"Merkle proof not available for sequence {sequence}. Event may be in pending interval or not exist.",
        )

    return proof


# =============================================================================
# Export Endpoints (Story 4.7, Task 3 - FR139, FR140)
# =============================================================================


@router.get("/export")
async def export_events(
    request: Request,
    format: ExportFormat = Query(
        default=ExportFormat.JSONL,
        description="Export format: 'jsonl' for JSON Lines or 'csv' for CSV (FR139)",
    ),
    start_sequence: Optional[int] = Query(
        default=None,
        ge=1,
        description="First sequence to export (inclusive)",
    ),
    end_sequence: Optional[int] = Query(
        default=None,
        ge=1,
        description="Last sequence to export (inclusive)",
    ),
    start_date: Optional[datetime] = Query(
        default=None,
        description="Filter events from this date (ISO 8601)",
    ),
    end_date: Optional[datetime] = Query(
        default=None,
        description="Filter events until this date (ISO 8601)",
    ),
    event_type: Optional[str] = Query(
        default=None,
        description="Filter by event type(s), comma-separated",
    ),
    include_attestation: bool = Query(
        default=False,
        description="Include attestation metadata header (FR140)",
    ),
    export_service: ExportService = Depends(get_export_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> StreamingResponse:
    """Export events in regulatory format (FR139).

    Streams events in JSON Lines or CSV format for regulatory export.
    Suitable for third-party attestation services (FR140).

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    Per FR139: Export SHALL support structured audit format (JSON Lines, CSV).
    Per FR140: Third-party attestation interface with attestation metadata.
    Per CT-11: All hash chain data included for verification.
    Per CT-12: Witness attribution included.

    Args:
        request: The FastAPI request object.
        format: Export format ('jsonl' or 'csv').
        start_sequence: First sequence to export.
        end_sequence: Last sequence to export.
        start_date: Filter from date.
        end_date: Filter until date.
        event_type: Filter by event types (comma-separated).
        include_attestation: Include attestation metadata header.
        export_service: Injected export service.
        rate_limiter: Injected rate limiter.

    Returns:
        StreamingResponse with export data.
    """
    await rate_limiter.check_rate_limit(request)

    # Parse event types with input validation
    # Security: Limit number of event types to prevent resource exhaustion
    MAX_EVENT_TYPES = 20
    event_types: Optional[list[str]] = None
    if event_type:
        raw_types = [t.strip() for t in event_type.split(",") if t.strip()]
        if len(raw_types) > MAX_EVENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum {MAX_EVENT_TYPES} event types allowed per export. Received {len(raw_types)}.",
            )
        event_types = raw_types

    # Get streaming iterator based on format
    if format == ExportFormat.CSV:
        content_type = "text/csv"
        filename = "events.csv"
        stream = export_service.export_csv(
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            start_date=start_date,
            end_date=end_date,
            event_types=event_types,
        )
    else:  # JSONL
        content_type = "application/x-ndjson"
        filename = "events.jsonl"
        stream = export_service.export_jsonl(
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            start_date=start_date,
            end_date=end_date,
            event_types=event_types,
        )

    # Wrap for proper streaming
    async def stream_wrapper() -> AsyncIterator[str]:
        async for line in stream:
            yield line

    return StreamingResponse(
        stream_wrapper(),
        media_type=content_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )


@router.get("/export/attestation", response_model=AttestationMetadata)
async def get_attestation_for_range(
    request: Request,
    start_sequence: int = Query(
        ge=1,
        description="First sequence in export range",
    ),
    end_sequence: int = Query(
        ge=1,
        description="Last sequence in export range",
    ),
    export_service: ExportService = Depends(get_export_service),
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> AttestationMetadata:
    """Get attestation metadata for an export range (FR140).

    Returns attestation metadata including:
    - Export ID (UUID)
    - Timestamp
    - Sequence range
    - Event count
    - Chain hash at export time
    - Export signature (if HSM available)

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    Per FR140: Third-party attestation interface with attestation metadata.

    Args:
        request: The FastAPI request object.
        start_sequence: First sequence in range.
        end_sequence: Last sequence in range.
        export_service: Injected export service.
        observer_service: Injected observer service.
        rate_limiter: Injected rate limiter.

    Returns:
        AttestationMetadata for the specified range.

    Raises:
        HTTPException: 400 if range is invalid.
    """
    await rate_limiter.check_rate_limit(request)

    if end_sequence < start_sequence:
        raise HTTPException(
            status_code=400,
            detail="end_sequence must be >= start_sequence",
        )

    # Count events in range
    event_count = await observer_service._event_store.count_events_in_range(
        start_sequence=start_sequence,
        end_sequence=end_sequence,
    )

    return await export_service.generate_attestation_metadata(
        sequence_start=start_sequence,
        sequence_end=end_sequence,
        event_count=event_count,
    )


# =============================================================================
# Webhook Subscription Endpoints (Story 4.8 - SR-9, RT-5)
# =============================================================================


@router.post("/subscriptions/webhook", response_model=WebhookSubscriptionResponse)
async def subscribe_webhook(
    request: Request,
    subscription: WebhookSubscription,
    notification_service: NotificationService = Depends(get_notification_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> WebhookSubscriptionResponse:
    """Subscribe to webhook notifications (SR-9).

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    Per SR-9: Register webhook for push notifications.
    Per RT-5: Breach events pushed to registered webhooks.

    A test notification will be sent to verify the webhook URL.

    Args:
        request: The FastAPI request object.
        subscription: Webhook subscription details.
        notification_service: Injected notification service.
        rate_limiter: Injected rate limiter.

    Returns:
        WebhookSubscriptionResponse with subscription ID.
    """
    await rate_limiter.check_rate_limit(request)

    return await notification_service.subscribe_webhook(subscription)


@router.delete("/subscriptions/webhook/{subscription_id}")
async def unsubscribe_webhook(
    request: Request,
    subscription_id: UUID,
    notification_service: NotificationService = Depends(get_notification_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> dict[str, str]:
    """Unsubscribe from webhook notifications (SR-9).

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    Args:
        request: The FastAPI request object.
        subscription_id: ID of subscription to remove.
        notification_service: Injected notification service.
        rate_limiter: Injected rate limiter.

    Returns:
        Success message.

    Raises:
        HTTPException: 404 if subscription not found.
    """
    await rate_limiter.check_rate_limit(request)

    removed = await notification_service.unsubscribe_webhook(subscription_id)

    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"Subscription {subscription_id} not found",
        )

    return {"status": "unsubscribed", "subscription_id": str(subscription_id)}


@router.get("/subscriptions/webhook/{subscription_id}", response_model=WebhookSubscriptionResponse)
async def get_webhook_subscription(
    request: Request,
    subscription_id: UUID,
    notification_service: NotificationService = Depends(get_notification_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> WebhookSubscriptionResponse:
    """Get webhook subscription details (SR-9).

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    Args:
        request: The FastAPI request object.
        subscription_id: ID of subscription to retrieve.
        notification_service: Injected notification service.
        rate_limiter: Injected rate limiter.

    Returns:
        WebhookSubscriptionResponse with subscription details.

    Raises:
        HTTPException: 404 if subscription not found.
    """
    await rate_limiter.check_rate_limit(request)

    subscription = notification_service.get_subscription(subscription_id)

    if subscription is None:
        raise HTTPException(
            status_code=404,
            detail=f"Subscription {subscription_id} not found",
        )

    return subscription


# =============================================================================
# Health & SLA Endpoints (Story 4.9 - RT-5, ADR-8)
# =============================================================================


async def _check_database_health(
    observer_service: ObserverService,
) -> DependencyHealth:
    """Check database health with latency measurement.

    Per CT-11: Health status must be accurate, not optimistic.

    Args:
        observer_service: Observer service with database access.

    Returns:
        DependencyHealth for the database dependency.
    """
    start = time.time()
    try:
        # Simple query to check DB connectivity
        await observer_service.check_database_health()
        latency_ms = (time.time() - start) * 1000  # Convert to ms

        # Determine status based on latency
        # > 1 second is degraded (high latency affects user experience)
        if latency_ms > 1000:
            return DependencyHealth(
                name="database",
                status=ObserverHealthStatus.DEGRADED,
                latency_ms=latency_ms,
            )

        return DependencyHealth(
            name="database",
            status=ObserverHealthStatus.HEALTHY,
            latency_ms=latency_ms,
        )
    except Exception as e:
        return DependencyHealth(
            name="database",
            status=ObserverHealthStatus.UNHEALTHY,
            latency_ms=None,
            error=str(e),
        )


@router.get("/health", response_model=ObserverHealthResponse)
async def observer_health(
    request: Request,
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> ObserverHealthResponse:
    """Observer API health check endpoint (RT-5).

    Returns detailed health status for external monitoring.
    No authentication required (FR44).

    Per RT-5: External uptime monitoring requires this endpoint.
    Per CT-11: Status must be accurate (HALT OVER DEGRADE).

    The health endpoint checks:
    - Database connectivity and latency
    - Overall system status
    - Last checkpoint sequence for fallback info

    Status levels:
    - HEALTHY: All dependencies operational, latency normal
    - DEGRADED: System operational but high latency (> 1s)
    - UNHEALTHY: Critical dependency unavailable

    Args:
        request: The FastAPI request object.
        observer_service: Injected observer service.
        rate_limiter: Injected rate limiter.

    Returns:
        ObserverHealthResponse with detailed health status.
    """
    await rate_limiter.check_rate_limit(request)

    dependencies: list[DependencyHealth] = []
    overall_status = ObserverHealthStatus.HEALTHY

    # Check database connectivity
    db_health = await _check_database_health(observer_service)
    dependencies.append(db_health)

    # Worst status wins (per CT-11: accurate health)
    if db_health.status == ObserverHealthStatus.UNHEALTHY:
        overall_status = ObserverHealthStatus.UNHEALTHY
    elif db_health.status == ObserverHealthStatus.DEGRADED:
        if overall_status != ObserverHealthStatus.UNHEALTHY:
            overall_status = ObserverHealthStatus.DEGRADED

    # Get last checkpoint for fallback info
    last_checkpoint = await observer_service.get_last_checkpoint_sequence()

    return ObserverHealthResponse(
        status=overall_status,
        uptime_seconds=get_api_uptime_seconds(),
        dependencies=dependencies,
        last_checkpoint_sequence=last_checkpoint,
    )


@router.get("/ready", response_model=ObserverReadyResponse)
async def observer_ready(
    request: Request,
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> ObserverReadyResponse:
    """Observer API readiness check endpoint (RT-5).

    Returns whether API is ready to serve requests.
    Used by load balancers and orchestrators.

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    Readiness differs from health:
    - Ready: API can accept traffic (startup complete)
    - Health: API dependencies are functioning

    Args:
        request: The FastAPI request object.
        rate_limiter: Injected rate limiter.

    Returns:
        ObserverReadyResponse indicating readiness.
    """
    await rate_limiter.check_rate_limit(request)

    if not _API_READY:
        return ObserverReadyResponse(
            ready=False,
            reason="API startup not complete",
            startup_complete=False,
        )

    return ObserverReadyResponse(ready=True)


@router.get("/fallback", response_model=CheckpointFallback)
async def get_checkpoint_fallback(
    request: Request,
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> CheckpointFallback:
    """Get checkpoint fallback information (RT-5, ADR-8).

    Returns checkpoint anchors for fallback verification during
    API unavailability.

    Per ADR-8: Genesis anchor verification works during API outage.
    Per RT-5: Fallback to checkpoint anchor when API unavailable.

    This endpoint provides:
    - Latest checkpoint anchor for offline verification
    - Genesis anchor hash for root verification
    - Total checkpoint count
    - Instructions for fallback verification

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    Args:
        request: The FastAPI request object.
        observer_service: Injected observer service.
        rate_limiter: Injected rate limiter.

    Returns:
        CheckpointFallback with checkpoint and genesis info.
    """
    await rate_limiter.check_rate_limit(request)

    latest_checkpoint = await observer_service.get_latest_checkpoint()
    genesis_hash = await observer_service.get_genesis_anchor_hash()
    checkpoint_count = await observer_service.get_checkpoint_count()

    return CheckpointFallback(
        latest_checkpoint=latest_checkpoint,
        genesis_anchor_hash=genesis_hash,
        checkpoint_count=checkpoint_count,
    )


@router.get("/metrics", response_class=PlainTextResponse)
async def observer_metrics(
    request: Request,
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> PlainTextResponse:
    """Observer API metrics in Prometheus format (RT-5).

    Returns metrics for external uptime monitoring.
    No authentication required (FR44).

    Per RT-5: External monitoring requires metrics endpoint.
    Per NFR27: Prometheus metrics for operational monitoring.

    Metrics exposed:
    - observer_uptime_seconds: Total uptime
    - observer_uptime_percentage: Current SLA percentage
    - observer_sla_target: Target SLA (99.9%)
    - observer_meeting_sla: 1 if meeting SLA, 0 otherwise
    - observer_api_ready: 1 if ready, 0 otherwise
    - observer_last_checkpoint_age_seconds: Age of last checkpoint

    Args:
        request: The FastAPI request object.
        observer_service: Injected observer service.
        rate_limiter: Injected rate limiter.

    Returns:
        Prometheus-formatted metrics as plain text.
    """
    await rate_limiter.check_rate_limit(request)

    uptime_seconds = get_api_uptime_seconds()

    # Calculate uptime percentage (assume 100% unless we track downtime)
    # In production, wire up UptimeService for accurate tracking
    uptime_percentage = 100.0
    meeting_sla = 1 if uptime_percentage >= 99.9 else 0

    # Get checkpoint age
    checkpoint_age_line = ""
    last_checkpoint_seq = await observer_service.get_last_checkpoint_sequence()
    if last_checkpoint_seq:
        checkpoint_time = await observer_service.get_checkpoint_timestamp(
            last_checkpoint_seq
        )
        if checkpoint_time:
            checkpoint_age = (
                datetime.now(timezone.utc) - checkpoint_time
            ).total_seconds()
            checkpoint_age_line = f"""
# HELP observer_last_checkpoint_age_seconds Age of last checkpoint anchor in seconds
# TYPE observer_last_checkpoint_age_seconds gauge
observer_last_checkpoint_age_seconds {checkpoint_age}
"""

    # Format as Prometheus exposition format
    metrics = f"""# HELP observer_uptime_seconds Total uptime of Observer API in seconds
# TYPE observer_uptime_seconds gauge
observer_uptime_seconds {uptime_seconds}

# HELP observer_uptime_percentage Current uptime percentage
# TYPE observer_uptime_percentage gauge
observer_uptime_percentage {uptime_percentage}

# HELP observer_sla_target Target SLA percentage
# TYPE observer_sla_target gauge
observer_sla_target 99.9

# HELP observer_meeting_sla Whether currently meeting SLA (1=yes, 0=no)
# TYPE observer_meeting_sla gauge
observer_meeting_sla {meeting_sla}

# HELP observer_api_ready Whether API is ready to serve (1=ready, 0=not ready)
# TYPE observer_api_ready gauge
observer_api_ready {1 if _API_READY else 0}
{checkpoint_age_line}"""

    return PlainTextResponse(
        content=metrics.strip() + "\n",
        media_type="text/plain; version=0.0.4",
    )


# =============================================================================
# Cessation Trigger Conditions Endpoints (Story 7.7 - FR134)
# =============================================================================


@router.get(
    "/cessation-triggers",
    response_model=CessationTriggerConditionsResponse,
    summary="Get all cessation trigger conditions",
    description="Returns all cessation trigger conditions with thresholds and descriptions. Per FR134: Public documentation of cessation trigger conditions. No authentication required.",
)
async def get_cessation_triggers(
    request: Request,
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> CessationTriggerConditionsResponse:
    """Get all cessation trigger conditions (FR134).

    Returns all automatic trigger conditions that can cause cessation
    agenda placement with their thresholds and descriptions.

    Constitutional Constraint (FR134):
    All cessation trigger conditions SHALL be publicly documented.
    This endpoint provides complete transparency about what can
    trigger cessation consideration.

    Constitutional Constraint (CT-11):
    Silent failure destroys legitimacy. All trigger conditions
    are exposed for external verification.

    No authentication required (FR44).
    Rate limits identical for all users (FR48).
    This endpoint MUST work after cessation (CT-13).

    Args:
        request: The FastAPI request object.
        rate_limiter: Injected rate limiter.

    Returns:
        CessationTriggerConditionsResponse with all trigger conditions.
    """
    await rate_limiter.check_rate_limit(request)

    # Import here to avoid circular dependencies
    from src.application.services.public_triggers_service import PublicTriggersService

    service = PublicTriggersService()
    condition_set = service.get_trigger_conditions()

    # Convert domain model to API response model
    trigger_conditions = [
        CessationTriggerConditionResponse(
            trigger_type=c.trigger_type,
            threshold=c.threshold,
            window_days=c.window_days,
            description=c.description,
            fr_reference=c.fr_reference,
            constitutional_floor=c.constitutional_floor,
        )
        for c in condition_set.conditions
    ]

    return CessationTriggerConditionsResponse(
        schema_version=condition_set.schema_version,
        constitution_version=condition_set.constitution_version,
        effective_date=condition_set.effective_date,
        last_updated=condition_set.last_updated,
        trigger_conditions=trigger_conditions,
    )


@router.get(
    "/cessation-triggers.jsonld",
    response_model=CessationTriggerConditionsJsonLdResponse,
    summary="Get cessation trigger conditions in JSON-LD format",
    description="Returns cessation trigger conditions with JSON-LD semantic context. Per FR134 AC5: Machine-readable format with semantic vocabulary.",
)
async def get_cessation_triggers_jsonld(
    request: Request,
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> CessationTriggerConditionsJsonLdResponse:
    """Get cessation trigger conditions in JSON-LD format (FR134 AC5).

    Returns all trigger conditions with JSON-LD @context for
    semantic interoperability.

    Constitutional Constraint (FR134 AC5):
    Machine-readable format with semantic context for
    external verification and integration.

    No authentication required (FR44).
    Rate limits identical for all users (FR48).
    This endpoint MUST work after cessation (CT-13).

    Args:
        request: The FastAPI request object.
        rate_limiter: Injected rate limiter.

    Returns:
        CessationTriggerConditionsJsonLdResponse with JSON-LD context.
    """
    await rate_limiter.check_rate_limit(request)

    # Import here to avoid circular dependencies
    from src.application.services.public_triggers_service import PublicTriggersService

    service = PublicTriggersService()
    condition_set = service.get_trigger_conditions()

    # Get JSON-LD formatted data from domain model
    json_ld_data = condition_set.to_json_ld()

    return CessationTriggerConditionsJsonLdResponse(
        context=json_ld_data["@context"],
        type=json_ld_data["@type"],
        schema_version=json_ld_data["schema_version"],
        constitution_version=json_ld_data["constitution_version"],
        effective_date=json_ld_data["effective_date"],
        last_updated=json_ld_data["last_updated"],
        trigger_conditions=json_ld_data["trigger_conditions"],
    )


@router.get(
    "/cessation-triggers/{trigger_type}",
    response_model=CessationTriggerConditionResponse,
    summary="Get a specific cessation trigger condition",
    description="Returns a single cessation trigger condition by type. Per FR134: Public documentation of cessation trigger conditions.",
)
async def get_cessation_trigger_by_type(
    trigger_type: str,
    request: Request,
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> CessationTriggerConditionResponse:
    """Get a specific cessation trigger condition by type (FR134).

    Returns a single trigger condition identified by its trigger_type.
    Raises 404 if the trigger type is not found.

    Valid trigger_type values:
    - consecutive_failures: 3 consecutive failures in 30 days (FR37)
    - rolling_window: 5 failures in 90-day rolling window (RT-4)
    - anti_success_sustained: Anti-success alert sustained 90 days (FR38)
    - petition_threshold: External petition with 100+ co-signers (FR39)
    - breach_threshold: >10 unacknowledged breaches in 90 days (FR32)

    No authentication required (FR44).
    Rate limits identical for all users (FR48).
    This endpoint MUST work after cessation (CT-13).

    Args:
        trigger_type: The trigger_type to look up.
        request: The FastAPI request object.
        rate_limiter: Injected rate limiter.

    Returns:
        CessationTriggerConditionResponse for the requested type.

    Raises:
        HTTPException 404: If trigger_type is not found.
    """
    await rate_limiter.check_rate_limit(request)

    # Import here to avoid circular dependencies
    from src.application.services.public_triggers_service import PublicTriggersService

    service = PublicTriggersService()
    condition = service.get_trigger_condition(trigger_type)

    if condition is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "https://archon72.io/errors/trigger-not-found",
                "title": "Trigger Condition Not Found",
                "status": 404,
                "detail": f"No cessation trigger condition with type '{trigger_type}' exists",
                "instance": f"/v1/observer/cessation-triggers/{trigger_type}",
            },
        )

    return CessationTriggerConditionResponse(
        trigger_type=condition.trigger_type,
        threshold=condition.threshold,
        window_days=condition.window_days,
        description=condition.description,
        fr_reference=condition.fr_reference,
        constitutional_floor=condition.constitutional_floor,
    )


# =============================================================================
# Final Deliberation Endpoints (Story 7.8 - FR135 AC7)
# =============================================================================


class FinalDeliberationListResponse(BaseModel):
    """Response model for final deliberation list."""

    deliberations: list[FinalDeliberationResponse]
    pagination: PaginationMetadata


@router.get(
    "/cessation-deliberations",
    response_model=FinalDeliberationListResponse,
    summary="List all final cessation deliberations",
    description="Returns all final cessation deliberations with pagination. Per FR135 AC7: Observer query access to vote counts, dissent, and reasoning. No authentication required (FR42).",
)
async def list_cessation_deliberations(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum deliberations to return"),
    offset: int = Query(default=0, ge=0, description="Number to skip"),
    deliberation_recorder: FinalDeliberationRecorder = Depends(get_deliberation_recorder),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> FinalDeliberationListResponse:
    """List all final cessation deliberations (FR135 AC7).

    Returns all final cessation deliberations with vote counts, dissent
    percentages, and all 72 Archon reasonings.

    Constitutional Constraints:
    - FR135: Final deliberation SHALL be recorded and immutable
    - FR12: Dissent percentages visible in every vote tally
    - FR42: Public read access without authentication
    - CT-12: Each deliberation is witnessed for accountability

    No authentication required (FR44).
    Rate limits identical for all users (FR48).
    This endpoint MUST work after cessation (CT-13).

    Args:
        request: The FastAPI request object.
        limit: Maximum deliberations to return (1-1000).
        offset: Number to skip.
        deliberation_recorder: Injected recorder for accessing deliberations.
        rate_limiter: Injected rate limiter.

    Returns:
        FinalDeliberationListResponse with all deliberations and pagination.
    """
    await rate_limiter.check_rate_limit(request)

    deliberations, total = await deliberation_recorder.list_deliberations(
        limit=limit,
        offset=offset,
    )

    # Convert domain payloads to API responses
    deliberation_responses = [
        _convert_deliberation_to_response(d)
        for d in deliberations
    ]

    has_more = (offset + len(deliberations)) < total

    return FinalDeliberationListResponse(
        deliberations=deliberation_responses,
        pagination=PaginationMetadata(
            total_count=total,
            offset=offset,
            limit=limit,
            has_more=has_more,
        ),
    )


@router.get(
    "/cessation-deliberation/{deliberation_id}",
    response_model=FinalDeliberationResponse,
    summary="Get a specific cessation deliberation",
    description="Returns a single cessation deliberation by ID. Per FR135 AC7: Observer query access to vote counts, dissent, timing, and all Archon reasonings. No authentication required (FR42).",
)
async def get_cessation_deliberation(
    deliberation_id: UUID,
    request: Request,
    deliberation_recorder: FinalDeliberationRecorder = Depends(get_deliberation_recorder),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> FinalDeliberationResponse:
    """Get a specific cessation deliberation by ID (FR135 AC7).

    Returns a single cessation deliberation including:
    - All 72 Archon positions and reasonings
    - Vote counts (yes/no/abstain)
    - Dissent percentage (FR12)
    - Timing information (start, end, duration)
    - Witness attribution (CT-12)

    Constitutional Constraints:
    - FR135: Final deliberation SHALL be recorded and immutable
    - FR12: Dissent percentages visible in every vote tally
    - FR42: Public read access without authentication
    - CT-12: Each deliberation is witnessed for accountability

    No authentication required (FR44).
    Rate limits identical for all users (FR48).
    This endpoint MUST work after cessation (CT-13).

    Args:
        deliberation_id: The UUID of the deliberation to retrieve.
        request: The FastAPI request object.
        deliberation_recorder: Injected recorder for accessing deliberations.
        rate_limiter: Injected rate limiter.

    Returns:
        FinalDeliberationResponse with full deliberation details.

    Raises:
        HTTPException 404: If deliberation not found.
    """
    await rate_limiter.check_rate_limit(request)

    deliberation = await deliberation_recorder.get_deliberation(deliberation_id)

    if deliberation is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "https://archon72.io/errors/deliberation-not-found",
                "title": "Deliberation Not Found",
                "status": 404,
                "detail": f"No cessation deliberation with ID '{deliberation_id}' exists",
                "instance": f"/v1/observer/cessation-deliberation/{deliberation_id}",
            },
        )

    return _convert_deliberation_to_response(deliberation)


def _convert_deliberation_to_response(
    record: "DeliberationWithEventMetadata",
) -> FinalDeliberationResponse:
    """Convert DeliberationWithEventMetadata to FinalDeliberationResponse.

    Per CT-12: Includes real event metadata (content_hash, witness_id,
    witness_signature) for accountability verification.

    Args:
        record: Domain record with payload and event metadata.

    Returns:
        API response model with real verification data.
    """
    from src.application.ports.final_deliberation_recorder import (
        DeliberationWithEventMetadata,
    )

    payload = record.payload

    # Convert archon deliberations
    archon_responses = [
        ArchonDeliberationResponse(
            archon_id=ad.archon_id,
            position=ArchonPositionResponse(ad.position.value),
            reasoning=ad.reasoning,
            statement_timestamp=ad.statement_timestamp,
        )
        for ad in payload.archon_deliberations
    ]

    return FinalDeliberationResponse(
        event_id=record.event_id,  # Real event ID from event store (CT-12)
        deliberation_id=payload.deliberation_id,
        deliberation_started_at=payload.deliberation_started_at,
        deliberation_ended_at=payload.deliberation_ended_at,
        vote_recorded_at=payload.vote_recorded_at,
        duration_seconds=payload.duration_seconds,
        archon_deliberations=archon_responses,
        vote_counts=VoteCountsResponse(
            yes_count=payload.vote_counts.yes_count,
            no_count=payload.vote_counts.no_count,
            abstain_count=payload.vote_counts.abstain_count,
            total=payload.vote_counts.total,
        ),
        dissent_percentage=payload.dissent_percentage,
        content_hash=record.content_hash,  # Real hash (CT-12)
        witness_id=record.witness_id,  # Real witness (CT-12)
        witness_signature=record.witness_signature,  # Real signature (CT-12)
    )


# =============================================================================
# Integrity Case Artifact Endpoints (Story 7.10 - FR144)
# =============================================================================


@router.get(
    "/integrity-case",
    response_model=IntegrityCaseResponse,
    summary="Get the Integrity Case Artifact",
    description="Returns the complete Integrity Case Artifact documenting all constitutional guarantees. Per FR144: System SHALL maintain published Integrity Case Artifact. No authentication required (FR42).",
)
async def get_integrity_case(
    request: Request,
    integrity_service: IntegrityCaseService = Depends(get_integrity_case_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> IntegrityCaseResponse:
    """Get the Integrity Case Artifact (FR144).

    Returns the complete Integrity Case Artifact documenting all
    constitutional guarantees, their enforcement mechanisms, and
    invalidation conditions.

    Constitutional Constraints:
    - FR144: System SHALL maintain published Integrity Case Artifact
    - FR42: Public read access without authentication
    - CT-11: Silent failure destroys legitimacy - all guarantees documented
    - CT-13: MUST remain available after cessation (read-only)

    The artifact includes:
    - All 15 constitutional constraints (CT-1 through CT-15)
    - All FR-derived guarantees (FR5-FR39)
    - Enforcement mechanisms for each guarantee
    - Invalidation conditions that would void each guarantee
    - Amendment history tracking

    No authentication required (FR44).
    Rate limits identical for all users (FR48).
    This endpoint MUST work after cessation (CT-13).

    Args:
        request: The FastAPI request object.
        integrity_service: Injected integrity case service.
        rate_limiter: Injected rate limiter.

    Returns:
        IntegrityCaseResponse with the complete artifact.
    """
    await rate_limiter.check_rate_limit(request)

    artifact = await integrity_service.get_artifact()

    # Convert domain model to API response
    guarantee_responses = [
        IntegrityGuaranteeResponse(
            guarantee_id=g.guarantee_id,
            category=g.category.value,
            name=g.name,
            description=g.description,
            fr_reference=g.fr_reference,
            ct_reference=g.ct_reference,
            adr_reference=g.adr_reference,
            mechanism=g.mechanism,
            invalidation_conditions=list(g.invalidation_conditions),
            is_constitutional=g.is_constitutional,
        )
        for g in artifact.guarantees
    ]

    return IntegrityCaseResponse(
        version=artifact.version,
        schema_version=artifact.schema_version,
        constitution_version=artifact.constitution_version,
        created_at=artifact.created_at,
        last_updated=artifact.last_updated,
        amendment_event_id=artifact.amendment_event_id,
        guarantee_count=artifact.guarantee_count,
        guarantees=guarantee_responses,
    )


@router.get(
    "/integrity-case.jsonld",
    response_model=IntegrityCaseJsonLdResponse,
    summary="Get Integrity Case Artifact in JSON-LD format",
    description="Returns the Integrity Case Artifact with JSON-LD semantic context. Per FR144: Machine-readable format with semantic vocabulary for external verification.",
)
async def get_integrity_case_jsonld(
    request: Request,
    integrity_service: IntegrityCaseService = Depends(get_integrity_case_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> IntegrityCaseJsonLdResponse:
    """Get the Integrity Case Artifact in JSON-LD format (FR144).

    Returns the Integrity Case Artifact with JSON-LD @context for
    semantic interoperability with external verification systems.

    Constitutional Constraints:
    - FR144: System SHALL maintain published Integrity Case Artifact
    - FR42: Public read access without authentication
    - CT-13: MUST remain available after cessation (read-only)

    JSON-LD enables:
    - Machine-readable guarantee definitions
    - Semantic vocabulary for external tools
    - Integration with linked data ecosystems
    - Automated compliance checking

    No authentication required (FR44).
    Rate limits identical for all users (FR48).
    This endpoint MUST work after cessation (CT-13).

    Args:
        request: The FastAPI request object.
        integrity_service: Injected integrity case service.
        rate_limiter: Injected rate limiter.

    Returns:
        IntegrityCaseJsonLdResponse with JSON-LD context.
    """
    await rate_limiter.check_rate_limit(request)

    json_ld_data = await integrity_service.get_artifact_jsonld()

    return IntegrityCaseJsonLdResponse(
        context=json_ld_data["@context"],
        type=json_ld_data["@type"],
        version=json_ld_data["version"],
        schema_version=json_ld_data["schema_version"],
        constitution_version=json_ld_data["constitution_version"],
        created_at=json_ld_data["created_at"],
        last_updated=json_ld_data["last_updated"],
        amendment_event_id=json_ld_data.get("amendment_event_id"),
        guarantee_count=json_ld_data["guarantee_count"],
        guarantees=json_ld_data["guarantees"],
    )


@router.get(
    "/integrity-case/guarantees/{guarantee_id}",
    response_model=IntegrityGuaranteeResponse,
    summary="Get a specific integrity guarantee",
    description="Returns a single integrity guarantee by ID. Per FR144: Public documentation of constitutional guarantees.",
)
async def get_integrity_guarantee(
    guarantee_id: str,
    request: Request,
    integrity_service: IntegrityCaseService = Depends(get_integrity_case_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> IntegrityGuaranteeResponse:
    """Get a specific integrity guarantee by ID (FR144).

    Returns a single integrity guarantee identified by its guarantee_id.
    Raises 404 if the guarantee is not found.

    Valid guarantee_id formats:
    - Constitutional constraints: ct-1 through ct-15
    - FR guarantees: fr-5, fr-12, fr-16, fr-39, fr-44

    Constitutional Constraints:
    - FR144: System SHALL maintain published Integrity Case Artifact
    - FR42: Public read access without authentication
    - CT-13: MUST remain available after cessation (read-only)

    No authentication required (FR44).
    Rate limits identical for all users (FR48).
    This endpoint MUST work after cessation (CT-13).

    Args:
        guarantee_id: The guarantee_id to look up (e.g., "ct-11", "fr-44").
        request: The FastAPI request object.
        integrity_service: Injected integrity case service.
        rate_limiter: Injected rate limiter.

    Returns:
        IntegrityGuaranteeResponse for the requested guarantee.

    Raises:
        HTTPException 404: If guarantee_id is not found.
    """
    await rate_limiter.check_rate_limit(request)

    guarantee = await integrity_service.get_guarantee(guarantee_id)

    if guarantee is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "https://archon72.io/errors/guarantee-not-found",
                "title": "Integrity Guarantee Not Found",
                "status": 404,
                "detail": f"No integrity guarantee with ID '{guarantee_id}' exists",
                "instance": f"/v1/observer/integrity-case/guarantees/{guarantee_id}",
            },
        )

    return IntegrityGuaranteeResponse(
        guarantee_id=guarantee.guarantee_id,
        category=guarantee.category.value,
        name=guarantee.name,
        description=guarantee.description,
        fr_reference=guarantee.fr_reference,
        ct_reference=guarantee.ct_reference,
        adr_reference=guarantee.adr_reference,
        mechanism=guarantee.mechanism,
        invalidation_conditions=list(guarantee.invalidation_conditions),
        is_constitutional=guarantee.is_constitutional,
    )


@router.get(
    "/integrity-case/history",
    response_model=IntegrityCaseHistoryResponse,
    summary="Get Integrity Case Artifact version history",
    description="Returns the version history of the Integrity Case Artifact. Per FR144: Amendment synchronization tracked for transparency.",
)
async def get_integrity_case_history(
    request: Request,
    integrity_service: IntegrityCaseService = Depends(get_integrity_case_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> IntegrityCaseHistoryResponse:
    """Get the version history of the Integrity Case Artifact (FR144).

    Returns the history of all versions of the Integrity Case Artifact,
    showing when amendments were applied.

    Constitutional Constraints:
    - FR144: System SHALL maintain published Integrity Case Artifact
    - FR42: Public read access without authentication
    - CT-12: Amendment changes are witnessed and tracked
    - CT-13: MUST remain available after cessation (read-only)

    No authentication required (FR44).
    Rate limits identical for all users (FR48).
    This endpoint MUST work after cessation (CT-13).

    Args:
        request: The FastAPI request object.
        integrity_service: Injected integrity case service.
        rate_limiter: Injected rate limiter.

    Returns:
        IntegrityCaseHistoryResponse with version history.
    """
    await rate_limiter.check_rate_limit(request)

    history = await integrity_service.get_version_history()

    return history
