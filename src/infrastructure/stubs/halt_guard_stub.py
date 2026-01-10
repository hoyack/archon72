"""Halt Guard Stub for testing/development (Story 3.5, Task 7).

This stub provides a simplified HaltGuard implementation for testing
scenarios without needing the full DualChannelHaltTransport.

The stub allows direct control of halt state for testing:
- trigger_halt(): Set halted state
- clear_halt(): Set operational state
- set_halt_reason(): Set the halt reason

Usage:
    stub = HaltGuardStub()

    # Normal operation
    await stub.check_write_allowed()  # Passes
    status = await stub.check_read_allowed()  # Returns OPERATIONAL

    # Trigger halt
    stub.trigger_halt("Test halt reason")

    # Now blocked
    await stub.check_write_allowed()  # Raises WriteBlockedDuringHaltError
    status = await stub.check_read_allowed()  # Returns HALTED

WARNING: This stub is NOT for production use.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import structlog

from src.domain.errors.read_only import (
    ProvisionalBlockedDuringHaltError,
    WriteBlockedDuringHaltError,
)
from src.domain.models.halt_status_header import HaltStatusHeader

log = structlog.get_logger(__name__)


class HaltGuardStub:
    """Stub implementation of HaltGuard for testing.

    Provides direct control over halt state without infrastructure
    dependencies. Useful for testing components that depend on HaltGuard.

    The stub mirrors the HaltGuard interface but allows direct
    manipulation of state via helper methods.

    Example:
        >>> stub = HaltGuardStub()
        >>> await stub.is_halted()
        False
        >>> stub.trigger_halt("Test")
        >>> await stub.is_halted()
        True
    """

    def __init__(self) -> None:
        """Initialize stub with operational (not halted) state."""
        self._is_halted: bool = False
        self._halt_reason: Optional[str] = None
        self._halted_at: Optional[datetime] = None
        self._check_count: int = 0

    async def check_write_allowed(self) -> None:
        """Check if write operations are allowed.

        Raises:
            WriteBlockedDuringHaltError: If stub is in halted state.
        """
        self._check_count += 1
        if self._is_halted:
            log.info(
                "stub_write_blocked",
                halt_reason=self._halt_reason,
            )
            raise WriteBlockedDuringHaltError(
                f"FR20: System halted - write operations blocked. Reason: {self._halt_reason}"
            )

    async def check_read_allowed(self) -> HaltStatusHeader:
        """Check read status and return header.

        Reads are always allowed. Returns status header for transparency.

        Returns:
            HaltStatusHeader with current state.
        """
        self._check_count += 1
        if self._is_halted:
            return HaltStatusHeader.halted(
                reason=self._halt_reason or "Unknown",
                halted_at=self._halted_at or datetime.now(timezone.utc),
            )
        return HaltStatusHeader.operational()

    async def check_provisional_allowed(self) -> None:
        """Check if provisional operations are allowed.

        Raises:
            ProvisionalBlockedDuringHaltError: If stub is in halted state.
        """
        self._check_count += 1
        if self._is_halted:
            log.info(
                "stub_provisional_blocked",
                halt_reason=self._halt_reason,
            )
            raise ProvisionalBlockedDuringHaltError(
                f"FR20: System halted - provisional operations blocked. Reason: {self._halt_reason}"
            )

    async def get_status(self) -> HaltStatusHeader:
        """Get current halt status."""
        return await self.check_read_allowed()

    async def is_halted(self) -> bool:
        """Check if system is halted."""
        return self._is_halted

    async def get_halt_reason(self) -> Optional[str]:
        """Get halt reason if halted."""
        if not self._is_halted:
            return None
        return self._halt_reason

    # Test helper methods

    def trigger_halt(
        self,
        reason: str = "Test halt",
        halted_at: Optional[datetime] = None,
    ) -> None:
        """Trigger halt state for testing.

        Args:
            reason: Halt reason to set.
            halted_at: Optional timestamp, defaults to now.
        """
        log.info("stub_halt_triggered", reason=reason)
        self._is_halted = True
        self._halt_reason = reason
        self._halted_at = halted_at or datetime.now(timezone.utc)

    def clear_halt(self) -> None:
        """Clear halt state for testing."""
        log.info("stub_halt_cleared")
        self._is_halted = False
        self._halt_reason = None
        self._halted_at = None

    def set_halt_reason(self, reason: str) -> None:
        """Set halt reason for testing.

        Args:
            reason: New halt reason (only effective if halted).
        """
        self._halt_reason = reason

    def get_check_count(self) -> int:
        """Get number of check calls for verification.

        Returns:
            Number of times any check method was called.
        """
        return self._check_count

    def reset(self) -> None:
        """Reset stub to initial state."""
        self._is_halted = False
        self._halt_reason = None
        self._halted_at = None
        self._check_count = 0
