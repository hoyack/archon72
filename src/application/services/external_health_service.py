"""External health service (Story 8.3, FR53/FR54).

This module provides the service for external health checking that allows
third-party monitoring services to independently detect system unavailability.

Constitutional Constraints:
- FR53: Operational metrics SHALL NOT assess constitutional integrity
- FR54: System unavailability SHALL be independently detectable
- CT-11: Silent failure destroys legitimacy -> External detection critical

Key Design Principles:
1. NO DATABASE QUERIES - Must be fast (<50ms target)
2. In-memory halt/freeze state only
3. Apply precedence: HALTED > FROZEN > UP
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.application.ports.external_health import (
    ExternalHealthStatus,
)

if TYPE_CHECKING:
    from src.application.ports.freeze_checker import FreezeCheckerProtocol
    from src.application.ports.halt_checker import HaltChecker


class ExternalHealthService:
    """Service for external health checking (FR54).

    This service provides fast health status checks for external monitoring
    services. It checks halt and freeze state without database queries to
    ensure minimal latency (<50ms target).

    Constitutional Constraint (FR54):
    System unavailability SHALL be independently detectable by external parties.
    This service enables that by providing a fast, reliable health endpoint.

    Status Precedence:
    1. HALTED - Constitutional halt takes precedence (most severe)
    2. FROZEN - System ceased/frozen (still responds, read-only)
    3. UP - System operational

    Usage:
        service = ExternalHealthService(
            halt_checker=halt_checker,
            freeze_checker=freeze_checker,
        )
        status = await service.get_status()
        timestamp = await service.get_timestamp()
    """

    def __init__(
        self,
        *,
        halt_checker: HaltChecker,
        freeze_checker: FreezeCheckerProtocol,
    ) -> None:
        """Initialize the service.

        Args:
            halt_checker: HaltChecker for checking halt state.
            freeze_checker: FreezeCheckerProtocol for checking freeze state.
        """
        self._halt_checker = halt_checker
        self._freeze_checker = freeze_checker

    async def get_status(self) -> ExternalHealthStatus:
        """Get the current external health status.

        Checks system state and returns the appropriate status:
        1. If halted -> HALTED (highest precedence)
        2. If frozen -> FROZEN
        3. Otherwise -> UP

        This method is designed to be fast (<50ms) as it serves as
        the canary endpoint for external monitoring services.

        NO DATABASE QUERIES - uses in-memory cached state only.

        Returns:
            ExternalHealthStatus indicating current availability.
        """
        # Check halt state first (highest precedence)
        # Halt checker uses in-memory state from dual-channel (Story 3.3)
        if await self._halt_checker.is_halted():
            return ExternalHealthStatus.HALTED

        # Check freeze state (cessation)
        # Freeze checker uses in-memory state (Story 7.4)
        if await self._freeze_checker.is_frozen():
            return ExternalHealthStatus.FROZEN

        # System is operational
        return ExternalHealthStatus.UP

    async def get_timestamp(self) -> datetime:
        """Get the current timestamp for the health check.

        Returns the server's current UTC timestamp, useful for:
        - Response freshness verification
        - Clock drift detection by monitors
        - Audit trail of health checks

        Returns:
            Current UTC datetime.
        """
        return datetime.now(timezone.utc)


# Singleton instance for dependency injection
_external_health_service: ExternalHealthService | None = None


def get_external_health_service() -> ExternalHealthService:
    """Get the singleton ExternalHealthService instance.

    This function provides dependency injection for the external health
    service. In production, the service should be initialized at startup.

    Returns:
        The ExternalHealthService singleton.

    Raises:
        RuntimeError: If service not initialized.
    """
    if _external_health_service is None:
        raise RuntimeError(
            "ExternalHealthService not initialized. "
            "Call init_external_health_service() at startup."
        )
    return _external_health_service


def init_external_health_service(
    halt_checker: HaltChecker,
    freeze_checker: FreezeCheckerProtocol,
) -> ExternalHealthService:
    """Initialize the singleton ExternalHealthService.

    Should be called once at application startup.

    Args:
        halt_checker: HaltChecker for checking halt state.
        freeze_checker: FreezeCheckerProtocol for checking freeze state.

    Returns:
        The initialized ExternalHealthService.
    """
    global _external_health_service
    _external_health_service = ExternalHealthService(
        halt_checker=halt_checker,
        freeze_checker=freeze_checker,
    )
    return _external_health_service


def reset_external_health_service() -> None:
    """Reset the singleton for testing.

    Only use this in tests to ensure clean state between test cases.
    """
    global _external_health_service
    _external_health_service = None
