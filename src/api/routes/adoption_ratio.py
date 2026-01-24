"""Adoption ratio API routes (Story 8.6, PREVENT-7).

FastAPI router for adoption ratio monitoring endpoints.
High Archon authentication required for dashboard access.

Constitutional Constraints:
- PREVENT-7: Alert when adoption ratio exceeds 50%
- ASM-7: Monitor adoption vs organic ratio
- FR-8.4: High Archon SHALL have access to legitimacy dashboard
"""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.auth.high_archon_auth import get_high_archon_id
from src.api.models.adoption_ratio import (
    AdoptionRatioAlertResponse,
    AdoptionRatioDashboardResponse,
    AdoptionRatioErrorResponse,
    AdoptionRatioMetricsResponse,
    RealmAdoptionRatioStatusResponse,
)
from src.application.ports.adoption_ratio_repository import (
    AdoptionRatioRepositoryProtocol,
)
from src.application.services.adoption_ratio_alerting_service import (
    AdoptionRatioAlertingService,
)
from src.domain.models.adoption_ratio import AdoptionRatioAlert, AdoptionRatioMetrics

router = APIRouter(
    prefix="/v1/governance/dashboard/adoption-ratios",
    tags=["governance", "adoption-ratio", "dashboard"],
)


# Dependency injection placeholders
_repository: AdoptionRatioRepositoryProtocol | None = None
_alerting_service: AdoptionRatioAlertingService | None = None


def set_repository(repository: AdoptionRatioRepositoryProtocol) -> None:
    """Set the repository for dependency injection."""
    global _repository
    _repository = repository


def get_repository() -> AdoptionRatioRepositoryProtocol:
    """Get the repository.

    Raises:
        RuntimeError: If repository not configured.
    """
    if _repository is None:
        raise RuntimeError("Adoption ratio repository not configured")
    return _repository


def set_alerting_service(service: AdoptionRatioAlertingService) -> None:
    """Set the alerting service for dependency injection."""
    global _alerting_service
    _alerting_service = service


def get_alerting_service() -> AdoptionRatioAlertingService:
    """Get the alerting service.

    Raises:
        RuntimeError: If alerting service not configured.
    """
    if _alerting_service is None:
        raise RuntimeError("Adoption ratio alerting service not configured")
    return _alerting_service


def _metrics_to_response(metrics: AdoptionRatioMetrics) -> AdoptionRatioMetricsResponse:
    """Convert domain metrics to API response model."""
    return AdoptionRatioMetricsResponse(
        metrics_id=str(metrics.metrics_id),
        realm_id=metrics.realm_id,
        cycle_id=metrics.cycle_id,
        escalation_count=metrics.escalation_count,
        adoption_count=metrics.adoption_count,
        adoption_ratio=metrics.adoption_ratio,
        health_status=metrics.health_status(),
        adopting_kings=[str(k) for k in metrics.adopting_kings],
        computed_at=metrics.computed_at,
    )


def _alert_to_response(alert: AdoptionRatioAlert) -> AdoptionRatioAlertResponse:
    """Convert domain alert to API response model."""
    return AdoptionRatioAlertResponse(
        alert_id=str(alert.alert_id),
        realm_id=alert.realm_id,
        cycle_id=alert.cycle_id,
        adoption_count=alert.adoption_count,
        escalation_count=alert.escalation_count,
        adoption_ratio=alert.adoption_ratio,
        threshold=alert.threshold,
        severity=alert.severity,
        trend_delta=alert.trend_delta,
        adopting_kings=[str(k) for k in alert.adopting_kings],
        created_at=alert.created_at,
        resolved_at=alert.resolved_at,
        status=alert.status,
    )


@router.get(
    "",
    response_model=AdoptionRatioDashboardResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": AdoptionRatioErrorResponse, "description": "Unauthorized"},
        403: {
            "model": AdoptionRatioErrorResponse,
            "description": "Forbidden - High Archon role required",
        },
    },
    summary="Get adoption ratio dashboard",
    description="""
Get the High Archon adoption ratio dashboard with per-realm metrics.

**Requires authentication via X-Archon-Id and X-Archon-Role headers.**
**Requires HIGH_ARCHON role.**

Dashboard includes:
- Per-realm adoption ratio metrics
- Active alerts for realms exceeding 50% threshold
- Summary counts (realms exceeding threshold, critical alerts)

Per PREVENT-7: Alert when adoption ratio exceeds 50%.
Per FR-8.4: High Archon SHALL have access to legitimacy dashboard.
""",
)
async def get_dashboard(
    high_archon_id: Annotated[UUID, Depends(get_high_archon_id)],
    repository: Annotated[AdoptionRatioRepositoryProtocol, Depends(get_repository)],
    alerting_service: Annotated[
        AdoptionRatioAlertingService, Depends(get_alerting_service)
    ],
    cycle_id: Annotated[
        str,
        Query(
            description="Governance cycle ID (e.g., '2026-W04')",
            example="2026-W04",
        ),
    ],
) -> AdoptionRatioDashboardResponse:
    """Get adoption ratio dashboard data (Story 8.6, PREVENT-7).

    Restricted to High Archon role only.

    Args:
        high_archon_id: Authenticated High Archon ID from headers.
        repository: Injected repository.
        alerting_service: Injected alerting service.
        cycle_id: Governance cycle identifier.

    Returns:
        AdoptionRatioDashboardResponse with complete dashboard metrics.

    Raises:
        HTTPException 401: If authentication fails.
        HTTPException 403: If not HIGH_ARCHON role.
    """
    # Get all realm metrics for the cycle
    all_metrics = await repository.get_all_realms_current_cycle(cycle_id)

    # Get all active alerts
    active_alerts = await alerting_service.get_active_alerts()

    # Build realm status list
    realm_statuses: list[RealmAdoptionRatioStatusResponse] = []
    realms_exceeding = 0
    realms_critical = 0

    for metrics in all_metrics:
        # Check if realm has active alert
        active_alert = None
        for alert in active_alerts:
            if alert.realm_id == metrics.realm_id:
                active_alert = _alert_to_response(alert)
                break

        realm_statuses.append(
            RealmAdoptionRatioStatusResponse(
                realm_id=metrics.realm_id,
                metrics=_metrics_to_response(metrics),
                active_alert=active_alert,
            )
        )

        # Count thresholds
        if metrics.exceeds_threshold(0.50):
            realms_exceeding += 1
        if metrics.severity() == "CRITICAL":
            realms_critical += 1

    return AdoptionRatioDashboardResponse(
        cycle_id=cycle_id,
        total_realms_with_data=len(all_metrics),
        realms_exceeding_threshold=realms_exceeding,
        realms_critical=realms_critical,
        active_alerts_count=len(active_alerts),
        realm_metrics=realm_statuses,
        active_alerts=[_alert_to_response(a) for a in active_alerts],
        data_refreshed_at=datetime.now(timezone.utc),
    )


@router.get(
    "/realm/{realm_id}",
    response_model=RealmAdoptionRatioStatusResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": AdoptionRatioErrorResponse, "description": "Unauthorized"},
        403: {
            "model": AdoptionRatioErrorResponse,
            "description": "Forbidden - High Archon role required",
        },
        404: {"model": AdoptionRatioErrorResponse, "description": "Realm not found"},
    },
    summary="Get adoption ratio for specific realm",
    description="""
Get adoption ratio metrics and alert status for a specific realm.

**Requires authentication via X-Archon-Id and X-Archon-Role headers.**
**Requires HIGH_ARCHON role.**

Returns the current cycle metrics and any active alert for the realm.
""",
)
async def get_realm_status(
    realm_id: str,
    high_archon_id: Annotated[UUID, Depends(get_high_archon_id)],
    repository: Annotated[AdoptionRatioRepositoryProtocol, Depends(get_repository)],
    cycle_id: Annotated[
        str,
        Query(
            description="Governance cycle ID (e.g., '2026-W04')",
            example="2026-W04",
        ),
    ],
) -> RealmAdoptionRatioStatusResponse:
    """Get adoption ratio status for a specific realm (Story 8.6).

    Args:
        realm_id: Realm identifier.
        high_archon_id: Authenticated High Archon ID from headers.
        repository: Injected repository.
        cycle_id: Governance cycle identifier.

    Returns:
        RealmAdoptionRatioStatusResponse with metrics and alert status.

    Raises:
        HTTPException 401: If authentication fails.
        HTTPException 403: If not HIGH_ARCHON role.
    """
    # Get metrics for the realm/cycle
    metrics = await repository.get_metrics_by_realm_cycle(
        realm_id=realm_id,
        cycle_id=cycle_id,
    )

    # Get active alert (if any)
    active_alert = await repository.get_active_alert(realm_id)

    return RealmAdoptionRatioStatusResponse(
        realm_id=realm_id,
        metrics=_metrics_to_response(metrics) if metrics else None,
        active_alert=_alert_to_response(active_alert) if active_alert else None,
    )


@router.get(
    "/alerts",
    response_model=list[AdoptionRatioAlertResponse],
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": AdoptionRatioErrorResponse, "description": "Unauthorized"},
        403: {
            "model": AdoptionRatioErrorResponse,
            "description": "Forbidden - High Archon role required",
        },
    },
    summary="Get all active adoption ratio alerts",
    description="""
Get all currently active adoption ratio alerts across all realms.

**Requires authentication via X-Archon-Id and X-Archon-Role headers.**
**Requires HIGH_ARCHON role.**

Per PREVENT-7: Alerts are raised when adoption ratio exceeds 50%.
""",
)
async def get_active_alerts(
    high_archon_id: Annotated[UUID, Depends(get_high_archon_id)],
    alerting_service: Annotated[
        AdoptionRatioAlertingService, Depends(get_alerting_service)
    ],
) -> list[AdoptionRatioAlertResponse]:
    """Get all active adoption ratio alerts (Story 8.6, PREVENT-7).

    Args:
        high_archon_id: Authenticated High Archon ID from headers.
        alerting_service: Injected alerting service.

    Returns:
        List of active AdoptionRatioAlertResponse objects.

    Raises:
        HTTPException 401: If authentication fails.
        HTTPException 403: If not HIGH_ARCHON role.
    """
    alerts = await alerting_service.get_active_alerts()
    return [_alert_to_response(a) for a in alerts]


@router.get(
    "/alert/{alert_id}",
    response_model=AdoptionRatioAlertResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": AdoptionRatioErrorResponse, "description": "Unauthorized"},
        403: {
            "model": AdoptionRatioErrorResponse,
            "description": "Forbidden - High Archon role required",
        },
        404: {"model": AdoptionRatioErrorResponse, "description": "Alert not found"},
    },
    summary="Get specific adoption ratio alert",
    description="""
Get a specific adoption ratio alert by ID.

**Requires authentication via X-Archon-Id and X-Archon-Role headers.**
**Requires HIGH_ARCHON role.**
""",
)
async def get_alert(
    alert_id: str,
    high_archon_id: Annotated[UUID, Depends(get_high_archon_id)],
    repository: Annotated[AdoptionRatioRepositoryProtocol, Depends(get_repository)],
) -> AdoptionRatioAlertResponse:
    """Get a specific adoption ratio alert (Story 8.6).

    Args:
        alert_id: UUID of the alert.
        high_archon_id: Authenticated High Archon ID from headers.
        repository: Injected repository.

    Returns:
        AdoptionRatioAlertResponse with alert details.

    Raises:
        HTTPException 401: If authentication fails.
        HTTPException 403: If not HIGH_ARCHON role.
        HTTPException 404: If alert not found.
    """
    try:
        alert_uuid = UUID(alert_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid alert ID format (must be UUID)",
        )

    alert = await repository.get_alert_by_id(alert_uuid)

    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert not found: {alert_id}",
        )

    return _alert_to_response(alert)
