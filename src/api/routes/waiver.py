"""Waiver API routes (Story 9.8, SC-4, SR-10).

FastAPI router for constitutional waiver query endpoints.

Constitutional Constraints:
- SC-4: Epic 9 missing consent -> CT-15 deferred to Phase 2
- SR-10: CT-15 waiver documentation -> Must be explicit and tracked
- FR44: Public read access without authentication
- AC3: Waiver accessible via API
- CT-11: Silent failure destroys legitimacy - fail loud on errors
- CT-12: Witnessing creates accountability - all waivers have attribution
- CT-13: Reads allowed during halt

Developer Golden Rules:
1. HALT CHECK FIRST - Service handles halt checking
2. WITNESS EVERYTHING - Waiver events written via EventWriterService
3. FAIL LOUD - Return meaningful error responses
4. READS DURING HALT - All endpoints are read-only, work during halt
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request

from src.api.models.waiver import (
    WaiverErrorResponse,
    WaiverResponse,
    WaiversListResponse,
)
from src.application.services.waiver_documentation_service import (
    WaiverDocumentationService,
)
from src.domain.errors import SystemHaltedError

router = APIRouter(prefix="/v1/waivers", tags=["waivers"])


# =============================================================================
# Dependency Injection Placeholder
# =============================================================================
# In production, this would be replaced with proper DI from the FastAPI app
# For now, we raise NotImplementedError as a placeholder


async def get_waiver_service() -> WaiverDocumentationService:
    """Get waiver documentation service instance.

    This is a placeholder dependency. In production, this would be
    configured via FastAPI dependency injection with proper service
    instantiation.

    Raises:
        NotImplementedError: Until proper DI is configured.
    """
    # TODO: Replace with actual service instantiation
    raise NotImplementedError(
        "WaiverDocumentationService dependency not configured. "
        "Configure this in src/api/dependencies/waiver.py"
    )


# =============================================================================
# Waiver Endpoints
# =============================================================================


@router.get(
    "",
    response_model=WaiversListResponse,
    responses={
        503: {"model": WaiverErrorResponse, "description": "System halted"},
    },
    summary="List all waivers",
    description=(
        "List all documented constitutional waivers. "
        "Public read access without authentication (FR44). "
        "Returns all waivers regardless of status. "
        "SC-4, SR-10, FR44, AC3."
    ),
)
async def list_waivers(
    request: Request,
    waiver_service: WaiverDocumentationService = Depends(get_waiver_service),
) -> WaiversListResponse:
    """List all documented waivers (SC-4, SR-10, FR44, AC3).

    Returns all constitutional waivers, including active, implemented,
    and cancelled waivers. Public read access without authentication.

    Returns:
        WaiversListResponse with all waivers.

    Raises:
        HTTPException 503: If system is halted (CT-11).
    """
    try:
        waivers = await waiver_service.get_all_waivers()
        return WaiversListResponse(
            waivers=[
                WaiverResponse(
                    waiver_id=w.waiver_id,
                    constitutional_truth_id=w.constitutional_truth_id,
                    constitutional_truth_statement=w.constitutional_truth_statement,
                    what_is_waived=w.what_is_waived,
                    rationale=w.rationale,
                    target_phase=w.target_phase,
                    status=w.status.value,
                    documented_at=w.documented_at,
                    documented_by=w.documented_by,
                )
                for w in waivers
            ],
            total_count=len(waivers),
        )
    except SystemHaltedError:
        raise HTTPException(
            status_code=503,
            detail={
                "type": "https://archon72.io/errors/system-halted",
                "title": "System Halted",
                "status": 503,
                "detail": "System is halted - waiver queries unavailable",
                "instance": str(request.url),
            },
        )


@router.get(
    "/active",
    response_model=WaiversListResponse,
    responses={
        503: {"model": WaiverErrorResponse, "description": "System halted"},
    },
    summary="List active waivers",
    description=(
        "List only active constitutional waivers. "
        "Active waivers are those currently in effect. "
        "Public read access without authentication (FR44). "
        "SC-4, SR-10, FR44, AC3."
    ),
)
async def list_active_waivers(
    request: Request,
    waiver_service: WaiverDocumentationService = Depends(get_waiver_service),
) -> WaiversListResponse:
    """List only active waivers (SC-4, SR-10, FR44, AC3).

    Returns only constitutional waivers with status == ACTIVE.
    Public read access without authentication.

    Returns:
        WaiversListResponse with active waivers only.

    Raises:
        HTTPException 503: If system is halted (CT-11).
    """
    try:
        waivers = await waiver_service.get_active_waivers()
        return WaiversListResponse(
            waivers=[
                WaiverResponse(
                    waiver_id=w.waiver_id,
                    constitutional_truth_id=w.constitutional_truth_id,
                    constitutional_truth_statement=w.constitutional_truth_statement,
                    what_is_waived=w.what_is_waived,
                    rationale=w.rationale,
                    target_phase=w.target_phase,
                    status=w.status.value,
                    documented_at=w.documented_at,
                    documented_by=w.documented_by,
                )
                for w in waivers
            ],
            total_count=len(waivers),
        )
    except SystemHaltedError:
        raise HTTPException(
            status_code=503,
            detail={
                "type": "https://archon72.io/errors/system-halted",
                "title": "System Halted",
                "status": 503,
                "detail": "System is halted - waiver queries unavailable",
                "instance": str(request.url),
            },
        )


@router.get(
    "/{waiver_id}",
    response_model=WaiverResponse,
    responses={
        404: {"model": WaiverErrorResponse, "description": "Waiver not found"},
        503: {"model": WaiverErrorResponse, "description": "System halted"},
    },
    summary="Get a specific waiver",
    description=(
        "Get a specific constitutional waiver by ID. "
        "Public read access without authentication (FR44). "
        "SC-4, SR-10, FR44, AC3."
    ),
)
async def get_waiver(
    request: Request,
    waiver_id: Annotated[
        str,
        Path(
            description="Unique waiver identifier",
            examples=["CT-15-MVP-WAIVER"],
        ),
    ],
    waiver_service: WaiverDocumentationService = Depends(get_waiver_service),
) -> WaiverResponse:
    """Get a specific waiver by ID (SC-4, SR-10, FR44, AC3).

    Returns the constitutional waiver with the specified ID.
    Public read access without authentication.

    Args:
        waiver_id: Unique waiver identifier.

    Returns:
        WaiverResponse with waiver details.

    Raises:
        HTTPException 404: If waiver not found.
        HTTPException 503: If system is halted (CT-11).
    """
    try:
        waiver = await waiver_service.get_waiver(waiver_id)
        if waiver is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "https://archon72.io/errors/waiver-not-found",
                    "title": "Waiver Not Found",
                    "status": 404,
                    "detail": f"Waiver with ID '{waiver_id}' was not found",
                    "instance": str(request.url),
                },
            )
        return WaiverResponse(
            waiver_id=waiver.waiver_id,
            constitutional_truth_id=waiver.constitutional_truth_id,
            constitutional_truth_statement=waiver.constitutional_truth_statement,
            what_is_waived=waiver.what_is_waived,
            rationale=waiver.rationale,
            target_phase=waiver.target_phase,
            status=waiver.status.value,
            documented_at=waiver.documented_at,
            documented_by=waiver.documented_by,
        )
    except SystemHaltedError:
        raise HTTPException(
            status_code=503,
            detail={
                "type": "https://archon72.io/errors/system-halted",
                "title": "System Halted",
                "status": 503,
                "detail": "System is halted - waiver queries unavailable",
                "instance": str(request.url),
            },
        )
