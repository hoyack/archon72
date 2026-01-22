"""Legitimacy API routes (Story consent-gov-5-3).

FastAPI router for legitimacy restoration endpoint.
Authentication required for restoration operations.

Constitutional Constraints:
- FR30: Human Operator can acknowledge and execute upward legitimacy transition
- FR31: System can record all legitimacy transitions in append-only ledger
- FR32: System can prevent upward transitions without explicit acknowledgment
- AC5: Operator must be authenticated and authorized
- AC4: Only one band up at a time
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from src.api.auth.high_archon_auth import get_high_archon_id
from src.api.models.legitimacy import (
    ArchonAcknowledgmentRateResponse,
    DeliberationMetricsResponse,
    LegitimacyDashboardResponse,
    LegitimacyErrorResponse,
    LegitimacyStatusResponse,
    LegitimacyTrendPointResponse,
    PetitionStateCountsResponse,
    RestorationHistoryItem,
    RestorationHistoryResponse,
    RestorationRequest,
    RestorationResponse,
)
from src.application.services.governance.legitimacy_restoration_service import (
    LegitimacyRestorationService,
)
from src.application.services.legitimacy_dashboard_service import (
    LegitimacyDashboardService,
)
from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.restoration_acknowledgment import (
    RestorationRequest as DomainRestorationRequest,
)

router = APIRouter(
    prefix="/v1/governance/legitimacy", tags=["governance", "legitimacy"]
)


# Dependency injection placeholders
# In production, these would be provided by the DI container
_restoration_service: LegitimacyRestorationService | None = None
_dashboard_service: LegitimacyDashboardService | None = None


def set_restoration_service(service: LegitimacyRestorationService) -> None:
    """Set the restoration service for dependency injection."""
    global _restoration_service
    _restoration_service = service


def get_restoration_service() -> LegitimacyRestorationService:
    """Get the restoration service.

    Raises:
        RuntimeError: If restoration service not configured.
    """
    if _restoration_service is None:
        raise RuntimeError("Restoration service not configured")
    return _restoration_service


def set_dashboard_service(service: LegitimacyDashboardService) -> None:
    """Set the dashboard service for dependency injection (Story 8.4)."""
    global _dashboard_service
    _dashboard_service = service


def get_dashboard_service() -> LegitimacyDashboardService:
    """Get the dashboard service.

    Raises:
        RuntimeError: If dashboard service not configured.
    """
    if _dashboard_service is None:
        raise RuntimeError("Dashboard service not configured")
    return _dashboard_service


def get_operator_id(
    x_operator_id: Annotated[
        str | None,
        Header(
            description="Operator ID for authentication. Required for restoration operations."
        ),
    ] = None,
) -> UUID:
    """Extract and validate operator ID from header.

    Per AC5: Operator must be authenticated.

    Args:
        x_operator_id: Operator ID from X-Operator-Id header.

    Returns:
        Validated operator UUID.

    Raises:
        HTTPException: If operator ID is missing or invalid.
    """
    if not x_operator_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Operator-Id header is required",
        )

    try:
        return UUID(x_operator_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid operator ID format (must be UUID)",
        )


@router.post(
    "/restore",
    response_model=RestorationResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": LegitimacyErrorResponse, "description": "Unauthorized"},
        403: {"model": LegitimacyErrorResponse, "description": "Forbidden"},
        422: {"model": LegitimacyErrorResponse, "description": "Validation Error"},
    },
    summary="Restore legitimacy band",
    description="""
Restore the system's legitimacy band one step upward. This is an explicit
acknowledgment operation requiring human authorization.

**Requires authentication via X-Operator-Id header.**
**Requires restore_legitimacy permission.**

Per FR30: Human Operator can acknowledge and execute upward legitimacy transition.
Per AC4: Only one band up at a time.
Per AC5: Operator must be authenticated and authorized.
Per AC7: Acknowledgment must include reason and evidence.
Per AC8: FAILED state cannot be restored (requires reconstitution).
""",
)
async def restore_legitimacy(
    request: RestorationRequest,
    operator_id: Annotated[UUID, Depends(get_operator_id)],
    restoration_service: Annotated[
        LegitimacyRestorationService, Depends(get_restoration_service)
    ],
) -> RestorationResponse:
    """Restore legitimacy band one step upward.

    Per FR30: Human Operator can acknowledge and execute upward legitimacy transition.
    Per AC5: Operator must be authenticated and authorized.

    Args:
        request: Restoration request with target band, reason, and evidence.
        operator_id: Authenticated operator ID from header.
        restoration_service: Injected restoration service.

    Returns:
        RestorationResponse with acknowledgment details.

    Raises:
        HTTPException: If unauthorized, forbidden, or invalid request.
    """
    # Convert API target band to domain LegitimacyBand
    try:
        target_band = LegitimacyBand(request.target_band)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid target band: {request.target_band}",
        )

    # Create domain request
    domain_request = DomainRestorationRequest(
        operator_id=operator_id,
        target_band=target_band,
        reason=request.reason,
        evidence=request.evidence,
    )

    # Execute restoration
    result = await restoration_service.request_restoration(domain_request)

    if not result.success:
        # Determine appropriate error code based on error message
        error_detail = result.error or "Unknown error"

        if "not authorized" in error_detail.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_detail,
            )
        elif (
            "terminal" in error_detail.lower()
            or "FAILED" in error_detail
            or "one step" in error_detail.lower()
            or "upward" in error_detail.lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error_detail,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )

    # Success - return response
    ack = result.acknowledgment
    if ack is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Restoration acknowledgment missing from result",
        )
    return RestorationResponse(
        success=True,
        acknowledgment_id=str(ack.acknowledgment_id),
        from_band=ack.from_band.value,
        to_band=ack.to_band.value,
        operator_id=str(ack.operator_id),
        acknowledged_at=ack.acknowledged_at,
        reason=ack.reason,
        evidence=ack.evidence,
    )


@router.get(
    "/status",
    response_model=LegitimacyStatusResponse,
    summary="Get legitimacy status",
    description="""
Get the current legitimacy status of the system.

This endpoint does NOT require authentication as legitimacy status
is public information for transparency.
""",
)
async def get_legitimacy_status(
    restoration_service: Annotated[
        LegitimacyRestorationService, Depends(get_restoration_service)
    ],
) -> LegitimacyStatusResponse:
    """Get current legitimacy status.

    Public endpoint - no authentication required.

    Args:
        restoration_service: Injected restoration service.

    Returns:
        LegitimacyStatusResponse with current status.
    """
    # Get current state from the underlying legitimacy port
    state = await restoration_service._legitimacy.get_legitimacy_state()
    restoration_count = await restoration_service.get_restoration_count()

    return LegitimacyStatusResponse(
        current_band=state.current_band.value,
        entered_at=state.entered_at,
        violation_count=state.violation_count,
        restoration_count=restoration_count,
        last_transition_type=(
            state.last_transition_type.value if state.last_transition_type else None
        ),
    )


@router.get(
    "/history",
    response_model=RestorationHistoryResponse,
    summary="Get restoration history",
    description="""
Get the history of legitimacy restorations.

This endpoint does NOT require authentication as restoration history
is public information for transparency and audit purposes (FR31).
""",
)
async def get_restoration_history(
    restoration_service: Annotated[
        LegitimacyRestorationService, Depends(get_restoration_service)
    ],
    since: Annotated[
        datetime | None,
        Query(description="Only return restorations after this timestamp"),
    ] = None,
    limit: Annotated[
        int | None,
        Query(description="Maximum number of restorations to return", ge=1, le=100),
    ] = None,
) -> RestorationHistoryResponse:
    """Get restoration history.

    Public endpoint - no authentication required.

    Per FR31: System can record all legitimacy transitions in append-only ledger.

    Args:
        restoration_service: Injected restoration service.
        since: Optional filter for restorations after this time.
        limit: Optional maximum number of results.

    Returns:
        RestorationHistoryResponse with list of acknowledgments.
    """
    acknowledgments = await restoration_service.get_restoration_history(
        since=since, limit=limit
    )
    total_count = await restoration_service.get_restoration_count()

    items = [
        RestorationHistoryItem(
            acknowledgment_id=str(ack.acknowledgment_id),
            operator_id=str(ack.operator_id),
            from_band=ack.from_band.value,
            to_band=ack.to_band.value,
            reason=ack.reason,
            evidence=ack.evidence,
            acknowledged_at=ack.acknowledged_at,
        )
        for ack in acknowledgments
    ]

    return RestorationHistoryResponse(
        total_count=total_count,
        items=items,
    )


@router.get(
    "/acknowledgment/{acknowledgment_id}",
    response_model=RestorationHistoryItem,
    responses={
        404: {"model": LegitimacyErrorResponse, "description": "Not Found"},
    },
    summary="Get specific acknowledgment",
    description="""
Get a specific restoration acknowledgment by ID.

This endpoint does NOT require authentication as acknowledgment records
are public information for transparency and audit purposes.
""",
)
async def get_acknowledgment(
    acknowledgment_id: str,
    restoration_service: Annotated[
        LegitimacyRestorationService, Depends(get_restoration_service)
    ],
) -> RestorationHistoryItem:
    """Get a specific restoration acknowledgment.

    Public endpoint - no authentication required.

    Args:
        acknowledgment_id: The UUID of the acknowledgment to retrieve.
        restoration_service: Injected restoration service.

    Returns:
        RestorationHistoryItem with acknowledgment details.

    Raises:
        HTTPException: If acknowledgment not found.
    """
    try:
        ack_uuid = UUID(acknowledgment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid acknowledgment ID format (must be UUID)",
        )

    acknowledgment = await restoration_service.get_acknowledgment(ack_uuid)

    if acknowledgment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Acknowledgment not found: {acknowledgment_id}",
        )

    return RestorationHistoryItem(
        acknowledgment_id=str(acknowledgment.acknowledgment_id),
        operator_id=str(acknowledgment.operator_id),
        from_band=acknowledgment.from_band.value,
        to_band=acknowledgment.to_band.value,
        reason=acknowledgment.reason,
        evidence=acknowledgment.evidence,
        acknowledged_at=acknowledgment.acknowledged_at,
    )


@router.get(
    "/dashboard",
    response_model=LegitimacyDashboardResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": LegitimacyErrorResponse, "description": "Unauthorized"},
        403: {"model": LegitimacyErrorResponse, "description": "Forbidden - High Archon role required"},
    },
    summary="Get legitimacy dashboard",
    description="""
Get the High Archon legitimacy dashboard with petition system health metrics.

**Requires authentication via X-Archon-Id and X-Archon-Role headers.**
**Requires HIGH_ARCHON role.**

Dashboard includes:
- Current cycle legitimacy score
- Historical trend (last 10 cycles)
- Petitions by state
- Orphan petition count
- Average/median time-to-fate
- Deliberation metrics (consensus, timeout, deadlock rates)
- Per-archon acknowledgment rates

Per FR-8.4: High Archon SHALL have access to legitimacy dashboard.
Per NFR-5.6: Dashboard data refreshes every 5 minutes (cached).
""",
)
async def get_dashboard(
    high_archon_id: Annotated[UUID, Depends(get_high_archon_id)],
    dashboard_service: Annotated[
        LegitimacyDashboardService, Depends(get_dashboard_service)
    ],
    current_cycle_id: Annotated[
        str,
        Query(
            description="Current governance cycle ID (e.g., '2026-W04')",
            example="2026-W04",
        ),
    ],
) -> LegitimacyDashboardResponse:
    """Get legitimacy dashboard data (Story 8.4, FR-8.4).

    Restricted to High Archon role only.

    Args:
        high_archon_id: Authenticated High Archon ID from headers.
        dashboard_service: Injected dashboard service.
        current_cycle_id: Current governance cycle identifier.

    Returns:
        LegitimacyDashboardResponse with complete dashboard metrics.

    Raises:
        HTTPException 401: If authentication fails.
        HTTPException 403: If not HIGH_ARCHON role.
        HTTPException 400: If cycle_id is invalid.
    """
    try:
        dashboard_data = dashboard_service.get_dashboard_data(current_cycle_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid cycle ID: {str(e)}",
        )

    # Convert domain model to API response
    return LegitimacyDashboardResponse(
        current_cycle_score=dashboard_data.current_cycle_score,
        current_cycle_id=dashboard_data.current_cycle_id,
        health_status=dashboard_data.health_status,
        historical_trend=[
            LegitimacyTrendPointResponse(
                cycle_id=point.cycle_id,
                legitimacy_score=point.legitimacy_score,
                computed_at=point.computed_at,
            )
            for point in dashboard_data.historical_trend
        ],
        petitions_by_state=PetitionStateCountsResponse(
            received=dashboard_data.petitions_by_state.received,
            deliberating=dashboard_data.petitions_by_state.deliberating,
            acknowledged=dashboard_data.petitions_by_state.acknowledged,
            referred=dashboard_data.petitions_by_state.referred,
            escalated=dashboard_data.petitions_by_state.escalated,
            total=dashboard_data.petitions_by_state.total(),
        ),
        orphan_petition_count=dashboard_data.orphan_petition_count,
        average_time_to_fate=dashboard_data.average_time_to_fate,
        median_time_to_fate=dashboard_data.median_time_to_fate,
        deliberation_metrics=DeliberationMetricsResponse(
            total_deliberations=dashboard_data.deliberation_metrics.total_deliberations,
            consensus_rate=dashboard_data.deliberation_metrics.consensus_rate,
            timeout_rate=dashboard_data.deliberation_metrics.timeout_rate,
            deadlock_rate=dashboard_data.deliberation_metrics.deadlock_rate,
        ),
        archon_acknowledgment_rates=[
            ArchonAcknowledgmentRateResponse(
                archon_id=str(rate.archon_id),
                archon_name=rate.archon_name,
                acknowledgment_count=rate.acknowledgment_count,
                rate=rate.rate,
            )
            for rate in dashboard_data.archon_acknowledgment_rates
        ],
        requires_attention=dashboard_data.requires_attention(),
        data_refreshed_at=dashboard_data.data_refreshed_at,
    )
