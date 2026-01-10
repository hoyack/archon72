"""Constitutional health check endpoint (Story 8.10, ADR-10).

Provides the /health/constitutional endpoint for governance health status.

Constitutional Constraints:
- ADR-10: Constitutional health is a blocking gate for ceremonies
- AC1: Constitutional metrics distinct from operational metrics
- AC2: Routes to governance, not ops dashboards
- AC4: Ceremonies blocked when UNHEALTHY

Key Design Principles:
1. GOVERNANCE-FACING - routes to governance dashboards, not ops
2. CONSERVATIVE AGGREGATION - system health = worst component health
3. CEREMONIES BLOCKED - UNHEALTHY status blocks ceremonies without override
4. HALT CHECK FIRST - honors CT-11, checks halt state before operations
"""

from fastapi import APIRouter, HTTPException, status

from src.api.models.constitutional_health import (
    ConstitutionalHealthResponse,
    ConstitutionalMetricResponse,
)
from src.domain.errors import SystemHaltedError
from src.domain.models.constitutional_health import (
    ConstitutionalHealthStatus,
    MetricName,
)

router = APIRouter(tags=["constitutional-health"])

# Lazy service getter to avoid circular imports
_service = None


def get_constitutional_health_service():
    """Get constitutional health service instance.

    Returns:
        ConstitutionalHealthService instance.
    """
    global _service
    if _service is None:
        from src.application.services.constitutional_health_service import (
            get_constitutional_health_service as get_service,
        )
        _service = get_service()
    return _service


@router.get(
    "/health/constitutional",
    response_model=ConstitutionalHealthResponse,
    summary="Constitutional health status (ADR-10)",
    description=(
        "Constitutional health status for governance dashboards. "
        "Distinct from operational /health endpoints per ADR-10. "
        "Returns overall health status based on worst component health."
    ),
    responses={
        200: {
            "description": "Constitutional health status returned successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "healthy": {
                            "summary": "All constitutional metrics healthy",
                            "value": {
                                "status": "HEALTHY",
                                "ceremonies_blocked": False,
                                "blocking_reasons": [],
                                "metrics": {
                                    "breach_count": {
                                        "name": "breach_count",
                                        "value": 3,
                                        "status": "HEALTHY",
                                        "reason": "Below warning threshold (8)",
                                    },
                                    "override_rate": {
                                        "name": "override_rate",
                                        "value": 1,
                                        "status": "HEALTHY",
                                        "reason": "Below incident threshold (3)",
                                    },
                                    "dissent_health": {
                                        "name": "dissent_health",
                                        "value": 15.5,
                                        "status": "HEALTHY",
                                        "reason": "Above warning threshold (10%)",
                                    },
                                    "witness_coverage": {
                                        "name": "witness_coverage",
                                        "value": 72,
                                        "status": "HEALTHY",
                                        "reason": "Above minimum threshold (12)",
                                    },
                                },
                                "timestamp": "2026-01-08T12:00:00.000000Z",
                            },
                        },
                        "warning": {
                            "summary": "Constitutional health degraded",
                            "value": {
                                "status": "WARNING",
                                "ceremonies_blocked": False,
                                "blocking_reasons": [],
                                "metrics": {
                                    "breach_count": {
                                        "name": "breach_count",
                                        "value": 9,
                                        "status": "WARNING",
                                        "reason": "Reached warning threshold (8)",
                                    },
                                },
                                "timestamp": "2026-01-08T12:00:00.000000Z",
                            },
                        },
                        "unhealthy": {
                            "summary": "Constitutional health critical - ceremonies blocked",
                            "value": {
                                "status": "UNHEALTHY",
                                "ceremonies_blocked": True,
                                "blocking_reasons": [
                                    "Breach count (12) exceeded critical threshold (10)"
                                ],
                                "metrics": {
                                    "breach_count": {
                                        "name": "breach_count",
                                        "value": 12,
                                        "status": "UNHEALTHY",
                                        "reason": "Exceeded critical threshold (10)",
                                    },
                                },
                                "timestamp": "2026-01-08T12:00:00.000000Z",
                            },
                        },
                    }
                }
            },
        },
        503: {
            "description": "System halted - constitutional operations paused",
        },
    },
)
async def constitutional_health_check() -> ConstitutionalHealthResponse:
    """Return constitutional health status for governance.

    This endpoint provides constitutional health metrics for governance
    dashboards, distinct from operational health checks.

    Key characteristics:
    - Constitutional metrics only (not operational)
    - Routes to governance (not ops dashboards)
    - Worst component health = overall status
    - Ceremonies blocked when UNHEALTHY

    Constitutional metrics:
    - breach_count: Unacknowledged constitutional breaches
    - override_rate: Daily keeper override rate
    - dissent_health: Percentage of deliberations with dissent
    - witness_coverage: Available witnesses in pool

    Status values:
    - HEALTHY: All metrics within acceptable thresholds
    - WARNING: One or more metrics at warning level
    - UNHEALTHY: One or more metrics critical, ceremonies blocked

    Returns:
        ConstitutionalHealthResponse with metrics and overall status.

    Raises:
        HTTPException (503): If system is halted.
    """
    service = get_constitutional_health_service()

    try:
        snapshot = await service.get_constitutional_health()
    except SystemHaltedError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System halted - constitutional health check paused",
        )

    # Convert snapshot to response
    metrics = {}
    for metric in snapshot.get_all_metrics():
        metrics[metric.name.value] = ConstitutionalMetricResponse(
            name=metric.name.value,
            value=metric.value,
            warning_threshold=metric.warning_threshold,
            critical_threshold=metric.critical_threshold,
            status=metric.status.value,
            is_blocking=metric.is_blocking,
        )

    return ConstitutionalHealthResponse(
        status=snapshot.overall_status.value,
        ceremonies_blocked=snapshot.ceremonies_blocked,
        blocking_reasons=snapshot.blocking_reasons,
        metrics=metrics,
        checked_at=snapshot.calculated_at,
    )


@router.get(
    "/health/constitutional/ceremonies-allowed",
    response_model=bool,
    summary="Check if ceremonies are allowed (AC4)",
    description=(
        "Quick check whether ceremonies can proceed. "
        "Returns False if constitutional health is UNHEALTHY. "
        "Use this before initiating ceremonies that require healthy status."
    ),
    responses={
        200: {
            "description": "Ceremony permission status",
            "content": {
                "application/json": {
                    "examples": {
                        "allowed": {
                            "summary": "Ceremonies allowed",
                            "value": True,
                        },
                        "blocked": {
                            "summary": "Ceremonies blocked",
                            "value": False,
                        },
                    }
                }
            },
        },
        503: {
            "description": "System halted",
        },
    },
)
async def ceremonies_allowed() -> bool:
    """Check if ceremonies can proceed.

    Quick check for ceremony initiators to verify constitutional
    health allows the ceremony to proceed.

    Returns:
        True if ceremonies allowed (HEALTHY or WARNING status).
        False if ceremonies blocked (UNHEALTHY status).

    Raises:
        HTTPException (503): If system is halted.
    """
    service = get_constitutional_health_service()

    try:
        snapshot = await service.get_constitutional_health()
    except SystemHaltedError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System halted",
        )

    return not snapshot.ceremonies_blocked
