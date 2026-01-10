"""Halt Guard service - Read-only mode enforcement (Story 3.5, FR20).

This application service enforces read-only mode during system halt.
It wraps the DualChannelHaltTransport to provide semantic methods
for checking read, write, and provisional operations.

Constitutional Constraints:
- FR20: Read-only access during halt (no provisional operations)
- CT-11: Silent failure destroys legitimacy → Status is ALWAYS visible
- CT-13: Integrity outranks availability → Writes blocked during halt

Developer Golden Rules:
1. HALT FIRST - Check halt state before every WRITE, but allow READS
2. STATUS ALWAYS - Every response includes halt status header
3. FAIL LOUD - Write attempts during halt fail with clear FR20 message
4. NO QUEUING - Provisional operations cannot be queued for later execution
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import structlog

from src.domain.errors.read_only import (
    ProvisionalBlockedDuringHaltError,
    WriteBlockedDuringHaltError,
)
from src.domain.models.halt_status_header import HaltStatusHeader

if TYPE_CHECKING:
    from src.application.ports.dual_channel_halt import DualChannelHaltTransport

log = structlog.get_logger()


class HaltGuard:
    """Enforces read-only mode during halt (FR20).

    This is the application-layer enforcement point for halt semantics.
    - Reads: Always allowed, return status header
    - Writes: Blocked during halt
    - Provisional: Blocked during halt

    Constitutional Constraints:
    - FR20: Read-only access during halt
    - CT-11: Silent failure destroys legitimacy → Status is ALWAYS visible
    - AC1: Results include `system_status: HALTED` header
    - AC2: Write error includes "FR20: System halted - write operations blocked"
    - AC3: Provisional operations are not queued

    Example:
        >>> from src.infrastructure.stubs import DualChannelHaltStub
        >>> halt_transport = DualChannelHaltStub()
        >>> guard = HaltGuard(halt_transport)
        >>>
        >>> # Check write - raises if halted
        >>> await guard.check_write_allowed()  # Passes when not halted
        >>>
        >>> # Check read - always succeeds, returns status
        >>> status = await guard.check_read_allowed()
        >>> status.system_status  # "OPERATIONAL"
        >>>
        >>> # Trigger halt
        >>> halt_transport.trigger_halt("Fork detected")
        >>> await guard.check_write_allowed()  # Raises WriteBlockedDuringHaltError
    """

    def __init__(self, halt_transport: DualChannelHaltTransport) -> None:
        """Initialize HaltGuard with halt transport.

        Args:
            halt_transport: The dual-channel halt transport for checking halt state.
        """
        self._halt_transport = halt_transport
        self._log = log.bind(service="halt_guard")

    async def check_write_allowed(self) -> None:
        """Check if write operations are allowed.

        Call this BEFORE any write operation. This is the enforcement
        point for FR20 write blocking.

        Raises:
            WriteBlockedDuringHaltError: If system is halted.
                Message includes "FR20: System halted - write operations blocked"
                per AC2.

        Example:
            >>> await guard.check_write_allowed()  # Raises if halted
            >>> # If we get here, write is allowed
            >>> await event_store.append(event)
        """
        is_halted = await self._halt_transport.is_halted()
        if is_halted:
            reason = await self._halt_transport.get_halt_reason()
            self._log.warning(
                "write_blocked_during_halt",
                halt_reason=reason,
                fr="FR20",
            )
            raise WriteBlockedDuringHaltError(
                f"FR20: System halted - write operations blocked. Reason: {reason}"
            )

    async def check_read_allowed(self) -> HaltStatusHeader:
        """Check read status and return header.

        Reads are ALWAYS allowed per FR20. Returns status for transparency
        per CT-11 (silent failure destroys legitimacy).

        Returns:
            HaltStatusHeader indicating current system state.
            - If halted: system_status="HALTED", halt_reason set
            - If operational: system_status="OPERATIONAL"

        Example:
            >>> status = await guard.check_read_allowed()
            >>> if status.is_halted:
            ...     # System is halted, but read is still allowed
            ...     pass
            >>> # Include status in response headers
        """
        is_halted = await self._halt_transport.is_halted()
        if is_halted:
            reason = await self._halt_transport.get_halt_reason()
            self._log.info(
                "read_during_halt",
                halt_reason=reason,
                fr="FR20",
            )
            return HaltStatusHeader.halted(
                reason=reason or "Unknown",
                halted_at=datetime.now(timezone.utc),
            )

        return HaltStatusHeader.operational()

    async def check_provisional_allowed(self) -> None:
        """Check if provisional operations are allowed.

        Provisional operations include:
        - Scheduled future writes
        - Queued operations
        - Delayed execution requests

        Per AC3, provisional operations are NOT queued during halt.

        Raises:
            ProvisionalBlockedDuringHaltError: If system is halted.

        Example:
            >>> await guard.check_provisional_allowed()  # Raises if halted
            >>> # If we get here, provisional operation is allowed
            >>> await scheduler.queue_write(event, delay=3600)
        """
        is_halted = await self._halt_transport.is_halted()
        if is_halted:
            reason = await self._halt_transport.get_halt_reason()
            self._log.warning(
                "provisional_blocked_during_halt",
                halt_reason=reason,
                fr="FR20",
            )
            raise ProvisionalBlockedDuringHaltError(
                f"FR20: System halted - provisional operations blocked. Reason: {reason}"
            )

    async def get_status(self) -> HaltStatusHeader:
        """Get current halt status without side effects.

        Convenience method for getting status header without
        implying a read operation. Useful for health checks
        and status endpoints.

        Returns:
            HaltStatusHeader with current system state.
        """
        return await self.check_read_allowed()

    async def is_halted(self) -> bool:
        """Check if system is currently halted.

        Convenience method for simple boolean check.
        For full status details, use get_status() instead.

        Returns:
            True if system is halted, False otherwise.
        """
        return await self._halt_transport.is_halted()

    async def get_halt_reason(self) -> Optional[str]:
        """Get the current halt reason.

        Returns:
            Halt reason if halted, None otherwise.
        """
        if not await self.is_halted():
            return None
        return await self._halt_transport.get_halt_reason()
