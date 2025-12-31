"""Health check endpoint for Archon 72 API."""

from fastapi import APIRouter

from src.api.models.health import HealthResponse

router = APIRouter(prefix="/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return health status.

    Returns:
        Health status with 200 OK.
    """
    return HealthResponse(status="healthy")
