"""External health checker stub for testing (Story 8.3, FR54).

This module provides a stub implementation of ExternalHealthPort
for unit and integration testing.

The stub allows tests to:
1. Configure health status (UP, HALTED, FROZEN)
2. Inject halt/freeze checkers for integration testing
3. Track check calls for verification
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.application.ports.external_health import (
    ExternalHealthPort,
    ExternalHealthStatus,
)

if TYPE_CHECKING:
    from src.application.ports.freeze_checker import FreezeCheckerProtocol
    from src.application.ports.halt_checker import HaltChecker


class ExternalHealthStub:
    """Stub implementation of ExternalHealthPort for testing.

    Provides configurable health status for testing external health checks.

    Modes of operation (in priority order):
    1. Injected checkers mode: Uses HaltChecker and FreezeCheckerProtocol
    2. Forced status mode: Uses force_status for simple testing

    Usage:
        # Simple mode - force a specific status
        stub = ExternalHealthStub(force_status=ExternalHealthStatus.HALTED)
        assert await stub.get_status() == ExternalHealthStatus.HALTED

        # Checker mode - integrate with halt/freeze checkers
        stub = ExternalHealthStub(
            halt_checker=halt_checker_stub,
            freeze_checker=freeze_checker_stub,
        )
        assert await stub.get_status() == ExternalHealthStatus.UP

        # Track calls
        await stub.get_status()
        assert stub.check_count == 1
    """

    def __init__(
        self,
        *,
        halt_checker: HaltChecker | None = None,
        freeze_checker: FreezeCheckerProtocol | None = None,
        force_status: ExternalHealthStatus | None = None,
    ) -> None:
        """Initialize the stub.

        Args:
            halt_checker: HaltChecker to check halt state (takes precedence).
            freeze_checker: FreezeCheckerProtocol to check freeze state.
            force_status: Force a specific status (overrides checkers).
        """
        self._halt_checker = halt_checker
        self._freeze_checker = freeze_checker
        self._force_status = force_status
        self._check_count: int = 0
        self._timestamp_count: int = 0

    @property
    def check_count(self) -> int:
        """Get the number of times get_status() was called."""
        return self._check_count

    @property
    def timestamp_count(self) -> int:
        """Get the number of times get_timestamp() was called."""
        return self._timestamp_count

    def set_force_status(self, status: ExternalHealthStatus | None) -> None:
        """Set or clear the forced status.

        Args:
            status: Status to force, or None to use checkers.
        """
        self._force_status = status

    def set_halt_checker(self, halt_checker: HaltChecker | None) -> None:
        """Set or clear the halt checker.

        Args:
            halt_checker: HaltChecker to use, or None to clear.
        """
        self._halt_checker = halt_checker

    def set_freeze_checker(self, freeze_checker: FreezeCheckerProtocol | None) -> None:
        """Set or clear the freeze checker.

        Args:
            freeze_checker: FreezeCheckerProtocol to use, or None to clear.
        """
        self._freeze_checker = freeze_checker

    def reset_counts(self) -> None:
        """Reset check counts for test isolation."""
        self._check_count = 0
        self._timestamp_count = 0

    async def get_status(self) -> ExternalHealthStatus:
        """Get the current external health status.

        Checks in priority order:
        1. force_status (if set)
        2. halt_checker.is_halted() -> HALTED
        3. freeze_checker.is_frozen() -> FROZEN
        4. Default -> UP

        Returns:
            ExternalHealthStatus indicating current availability.
        """
        self._check_count += 1

        # Force status takes highest priority (for testing edge cases)
        if self._force_status is not None:
            return self._force_status

        # Check halt state (constitutional halt)
        if self._halt_checker is not None:
            if await self._halt_checker.is_halted():
                return ExternalHealthStatus.HALTED

        # Check freeze state (cessation)
        if self._freeze_checker is not None:
            if await self._freeze_checker.is_frozen():
                return ExternalHealthStatus.FROZEN

        # Default to UP
        return ExternalHealthStatus.UP

    async def get_timestamp(self) -> datetime:
        """Get the current timestamp for the health check.

        Returns:
            Current UTC datetime.
        """
        self._timestamp_count += 1
        return datetime.now(timezone.utc)


# Type assertion to verify protocol compliance
def _check_protocol_compliance() -> None:
    """Verify that ExternalHealthStub implements ExternalHealthPort."""
    stub: ExternalHealthPort = ExternalHealthStub()
    _ = stub  # Silence unused variable warning
