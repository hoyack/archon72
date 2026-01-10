"""Configuration health check endpoint (Story 6.10, NFR39, AC6).

This module provides the configuration health endpoint that reports
the status of constitutional configuration floors.

Constitutional Constraints:
- NFR39: No configuration SHALL allow thresholds below constitutional floors
- AC6: Health endpoint should report floor status
"""

from fastapi import APIRouter

from src.api.models.configuration_health import (
    ConfigurationHealthResponse,
    ThresholdStatusResponse,
)
from src.application.services.configuration_floor_enforcement_service import (
    ConfigurationFloorEnforcementService,
)
from src.infrastructure.stubs.halt_trigger_stub import HaltTriggerStub

router = APIRouter(prefix="/v1/configuration", tags=["configuration"])


@router.get("/health", response_model=ConfigurationHealthResponse)
async def get_configuration_health() -> ConfigurationHealthResponse:
    """Get configuration floor health status (AC6).

    Returns the status of all constitutional configuration floors,
    showing whether each threshold is at or above its minimum.

    Returns:
        ConfigurationHealthResponse with health status for all thresholds.
    """
    # Create service (using stub halt trigger for read-only operation)
    halt_trigger = HaltTriggerStub()
    service = ConfigurationFloorEnforcementService(halt_trigger=halt_trigger)

    # Get health status
    health = await service.get_configuration_health()

    # Convert to response model
    threshold_statuses = [
        ThresholdStatusResponse(
            threshold_name=s.threshold_name,
            floor_value=s.floor_value,
            current_value=s.current_value,
            is_valid=s.is_valid,
        )
        for s in health.threshold_statuses
    ]

    return ConfigurationHealthResponse(
        is_healthy=health.is_healthy,
        threshold_statuses=threshold_statuses,
        checked_at=health.checked_at.isoformat(),
    )
