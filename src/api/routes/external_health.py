"""External health check endpoint (Story 8.3, FR54).

Provides the /health/external endpoint for third-party monitoring services.

Constitutional Constraints:
- FR54: System unavailability SHALL be independently detectable
- CT-11: Silent failure destroys legitimacy

Key Design Principles:
1. NO AUTHENTICATION - publicly accessible
2. FAST RESPONSE - <50ms target (no DB queries)
3. MINIMAL RESPONSE - just status and timestamp
4. NO INTERNAL STATE EXPOSED - status values intentionally vague
"""

from fastapi import APIRouter

from src.api.models.external_health import ExternalHealthResponse
from src.application.services.external_health_service import get_external_health_service

router = APIRouter(tags=["external-health"])


@router.get(
    "/health/external",
    response_model=ExternalHealthResponse,
    summary="External health check (FR54)",
    description=(
        "External health check for third-party monitoring services. "
        "No authentication required. Returns minimal status: up, halted, or frozen. "
        "External monitors infer 'down' from timeout (no response)."
    ),
    responses={
        200: {
            "description": "Health status returned successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "up": {
                            "summary": "System operational",
                            "value": {
                                "status": "up",
                                "timestamp": "2026-01-08T12:00:00.000000Z",
                            },
                        },
                        "halted": {
                            "summary": "Constitutional halt active",
                            "value": {
                                "status": "halted",
                                "timestamp": "2026-01-08T12:00:00.000000Z",
                            },
                        },
                        "frozen": {
                            "summary": "System ceased (read-only)",
                            "value": {
                                "status": "frozen",
                                "timestamp": "2026-01-08T12:00:00.000000Z",
                            },
                        },
                    }
                }
            },
        },
    },
)
async def external_health_check() -> ExternalHealthResponse:
    """Return external health status.

    This endpoint is designed for third-party monitoring services
    (e.g., UptimeRobot, Pingdom, StatusCake) to independently detect
    system unavailability.

    Key characteristics:
    - No authentication required (FR54)
    - Fast response (<50ms target, no DB queries)
    - Minimal response (status + timestamp only)
    - Status values intentionally simple for security

    Status values:
    - "up": System is operational and accepting requests
    - "halted": Constitutional halt is active (Story 3.2-3.4)
    - "frozen": System has ceased, read-only access (Story 7.4)

    External monitors infer "down" from timeout (no response from server).

    Returns:
        ExternalHealthResponse with current status and timestamp.
    """
    service = get_external_health_service()
    status = await service.get_status()
    timestamp = await service.get_timestamp()

    return ExternalHealthResponse(
        status=status,
        timestamp=timestamp,
    )
