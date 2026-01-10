"""Operational health check endpoints for Archon 72 API (Story 8.1, Task 4; Story 8.10).

Provides liveness (/health) and readiness (/ready) endpoints.

OPERATIONAL HEALTH ONLY (AC3 - Constitutional Health Separation):
- These endpoints report operational health (liveness, dependencies)
- Constitutional health is at /health/constitutional
- Both domains visible, neither masks the other

NFR28 Requirements:
- /health for liveness (is process running?)
- /ready for readiness (are dependencies connected?)
- Kubernetes probe compatible responses
"""

from fastapi import APIRouter, Response, status

from src.api.models.health import HealthResponse, ReadyResponse
from src.application.services.health_service import get_health_service

router = APIRouter(prefix="/v1", tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Operational liveness check (Story 8.1)",
    description=(
        "Check if the service is alive. Returns 200 if process is responding. "
        "This is OPERATIONAL health only. For constitutional health metrics "
        "(governance), use /health/constitutional."
    ),
)
async def health_check() -> HealthResponse:
    """Return operational liveness status with uptime.

    This endpoint reports OPERATIONAL health only:
    - Is the process running?
    - How long has it been up?

    For constitutional health (governance metrics), use /health/constitutional.
    Per AC3 (Story 8.10), both domains are visible and neither masks the other.

    Returns:
        HealthResponse with status, uptime_seconds, and link to constitutional health.
    """
    service = get_health_service()
    return await service.check_liveness()


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Operational readiness check (Story 8.1)",
    description=(
        "Check if the service is ready to handle traffic. Checks database, Redis, "
        "and event store connectivity. This is OPERATIONAL health only. "
        "For constitutional health metrics (governance), use /health/constitutional."
    ),
    responses={
        200: {"description": "Service is ready"},
        503: {"description": "Service is not ready"},
    },
)
async def readiness_check(response: Response) -> ReadyResponse:
    """Return operational readiness status with dependency checks.

    This endpoint reports OPERATIONAL health only:
    - Are infrastructure dependencies connected?
    - Database, Redis, Event Store connectivity

    For constitutional health (governance metrics), use /health/constitutional.
    Per AC3 (Story 8.10), both domains are visible and neither masks the other.

    Returns:
        ReadyResponse with status, dependency checks, and link to constitutional health.
        Returns 503 status code if any dependency is unhealthy.
    """
    service = get_health_service()
    result = await service.check_readiness()

    if result.status == "not-ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return result
