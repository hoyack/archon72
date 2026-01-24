"""Governance transcript API routes (Story 7.6, FR-7.4, Ruling-2).

This module implements the API endpoint for elevated transcript access
for governance actors (HIGH_ARCHON and AUDITOR roles).

Constitutional Constraints:
- Ruling-2: Elevated tier access for HIGH_ARCHON and AUDITOR only
- FR-7.4: System SHALL provide full transcript to governance actors
- CT-12: Witnessing creates accountability - Log all access attempts
- AC-1: HIGH_ARCHON role gets full access
- AC-2: AUDITOR role gets full access
- AC-3: OBSERVER role denied with redirect hint
- AC-4: SEEKER role denied with redirect hint
- AC-5: Session not found returns 404
- AC-6: Read operations permitted during halt

Developer Golden Rules:
1. ELEVATED - Only HIGH_ARCHON and AUDITOR roles allowed
2. FULL ACCESS - No filtering of Archon identities or content
3. AUDIT - All access attempts logged (CT-12)
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.auth.elevated_auth import ElevatedActor, get_elevated_actor
from src.api.models.governance_transcript import (
    FullTranscriptResponse,
    TranscriptAccessError,
)
from src.application.ports.deliberation_summary import (
    DeliberationSummaryRepositoryProtocol,
)
from src.application.ports.transcript_store import TranscriptStoreProtocol
from src.application.services.governance_transcript_access_service import (
    GovernanceTranscriptAccessService,
)
from src.bootstrap.deliberation_summary import (
    get_deliberation_summary_repository as _get_deliberation_summary_repository,
)
from src.bootstrap.transcript_store import (
    get_transcript_store as _get_transcript_store,
)
from src.domain.errors.deliberation import SessionNotFoundError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/deliberations", tags=["governance", "transcripts"])


async def get_summary_repo() -> DeliberationSummaryRepositoryProtocol:
    """Get deliberation summary repository (dependency injection).

    In production, this would be wired up in main.py with the real adapter.
    """
    return _get_deliberation_summary_repository()


async def get_transcript_store() -> TranscriptStoreProtocol:
    """Get transcript store (dependency injection).

    In production, this would be wired up in main.py with the real adapter.
    """
    return _get_transcript_store()


async def get_transcript_service(
    summary_repo: DeliberationSummaryRepositoryProtocol = Depends(get_summary_repo),
    transcript_store: TranscriptStoreProtocol = Depends(get_transcript_store),
) -> GovernanceTranscriptAccessService:
    """Get governance transcript access service (dependency injection)."""
    return GovernanceTranscriptAccessService(
        summary_repo=summary_repo,
        transcript_store=transcript_store,
    )


@router.get(
    "/{session_id}/transcript",
    response_model=FullTranscriptResponse,
    summary="Get full deliberation transcript (elevated access)",
    description="""
    Get the complete deliberation transcript for a session.

    **ELEVATED ACCESS**: Requires HIGH_ARCHON or AUDITOR role.

    Returns the full transcript including:
    - All utterances with Archon attribution (archon_id)
    - Timestamps for each utterance (ISO 8601 UTC)
    - Phase boundaries (ASSESS, POSITION, CROSS_EXAMINE, VOTE)
    - Raw dissent text (if present)

    OBSERVER and SEEKER roles will receive 403 Forbidden with a redirect
    hint to the mediated summary endpoint.

    Constitutional Requirements:
    - Ruling-2: Tiered transcript access (elevated tier)
    - FR-7.4: Full transcript access for governance actors
    - CT-12: All access logged for audit trail
    """,
    responses={
        200: {
            "description": "Full transcript returned successfully",
            "model": FullTranscriptResponse,
        },
        401: {
            "description": "Authentication required (missing headers)",
        },
        403: {
            "description": "Insufficient role for elevated access",
            "model": TranscriptAccessError,
            "content": {
                "application/json": {
                    "example": {
                        "type": "urn:archon72:transcript:insufficient-role",
                        "title": "Elevated role required for full transcript access",
                        "status": 403,
                        "detail": "Role 'OBSERVER' does not have elevated transcript access. "
                        "Use the mediated summary endpoint instead.",
                        "redirect_hint": "/api/v1/petitions/{petition_id}/deliberation-summary",
                    }
                }
            },
        },
        404: {
            "description": "Session not found",
            "model": TranscriptAccessError,
            "content": {
                "application/json": {
                    "example": {
                        "type": "urn:archon72:transcript:session-not-found",
                        "title": "Session Not Found",
                        "status": 404,
                        "detail": "Deliberation session not found",
                    }
                }
            },
        },
    },
)
async def get_full_transcript(
    session_id: Annotated[UUID, "UUID of the deliberation session"],
    request: Request,
    actor: Annotated[ElevatedActor, Depends(get_elevated_actor)],
    service: Annotated[
        GovernanceTranscriptAccessService,
        Depends(get_transcript_service),
    ],
) -> FullTranscriptResponse:
    """Get full deliberation transcript for a session (Story 7.6).

    ELEVATED ACCESS: Only HIGH_ARCHON and AUDITOR roles allowed.

    Constitutional Constraints:
    - Ruling-2: Elevated tier access
    - FR-7.4: Full transcript access
    - CT-12: Access logged for audit trail (AC-7)
    - AC-5: Session not found returns 404
    - AC-6: Read operations permitted during halt

    Args:
        session_id: UUID of the deliberation session.
        request: FastAPI request for logging context.
        actor: Authenticated elevated actor (validated by dependency).
        service: Governance transcript access service.

    Returns:
        FullTranscriptResponse with complete transcript data.

    Raises:
        HTTPException 401: If authentication headers missing.
        HTTPException 403: If role is not elevated.
        HTTPException 404: If session not found.
    """
    log = logger.bind(
        session_id=str(session_id),
        accessor_archon_id=str(actor.archon_id),
        accessor_role=actor.role,
        request_ip=request.client.host if request.client else "unknown",
    )

    log.info("transcript_request_received")

    try:
        transcript = await service.get_full_transcript(
            session_id=session_id,
            accessor_archon_id=actor.archon_id,
            accessor_role=actor.role,
        )

        log.info(
            "transcript_request_succeeded",
            outcome=transcript.outcome,
            has_dissent=transcript.has_dissent,
            phase_count=len(transcript.phases),
        )

        return transcript

    except SessionNotFoundError as e:
        log.warning("session_not_found", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "urn:archon72:transcript:session-not-found",
                "title": "Session Not Found",
                "status": 404,
                "detail": str(e),
                "instance": str(request.url),
            },
        )
