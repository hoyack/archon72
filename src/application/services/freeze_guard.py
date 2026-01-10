"""Freeze Guard service (Story 7.4, FR41).

This service provides freeze mechanics enforcement for write operations.
It checks the freeze state before allowing writes and provides status
information for read responses.

Constitutional Constraints:
- FR41: Freeze on new actions except record preservation
- CT-11: Silent failure destroys legitimacy → Log ALL freeze violations
- CT-13: Integrity outranks availability → Freeze > Continue after cessation

This service complements the terminal detection from Story 7.3:
- Story 7.3: Terminal check = cessation event exists (SchemaIrreversibilityError)
- Story 7.4: Freeze check = operational freeze in effect (SystemCeasedError)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncGenerator

from structlog import get_logger

from src.domain.errors.ceased import CeasedWriteAttemptError, SystemCeasedError
from src.domain.models.ceased_status_header import CeasedStatusHeader

if TYPE_CHECKING:
    from src.application.ports.freeze_checker import FreezeCheckerProtocol

logger = get_logger()


class FreezeGuard:
    """Guard service for freeze mechanics enforcement (FR41).

    This service checks the freeze state before allowing writes and
    provides status information for read responses.

    Developer Golden Rules:
    1. FREEZE SECOND - Call after terminal check (Story 7.3)
    2. FAIL LOUD - Always raise SystemCeasedError when frozen
    3. LOG EVERYTHING - Per CT-11, all rejections are logged
    4. READ ALWAYS - Read operations must succeed with status header

    Usage in EventWriterService:
        # After terminal check (Story 7.3)
        await freeze_guard.ensure_not_frozen()
        # Proceed with write...

    Usage for read responses:
        status = await freeze_guard.get_freeze_status()
        if status:
            response.headers["X-System-Status"] = status.system_status

    Attributes:
        _freeze_checker: Interface to check freeze state.
    """

    def __init__(
        self,
        freeze_checker: FreezeCheckerProtocol,
    ) -> None:
        """Initialize FreezeGuard.

        Args:
            freeze_checker: Interface to check freeze state.
        """
        self._freeze_checker = freeze_checker

    async def is_frozen(self) -> bool:
        """Check if system is in frozen (ceased) state.

        Convenience method that delegates to freeze_checker.

        Returns:
            True if system is frozen, False otherwise.
        """
        return await self._freeze_checker.is_frozen()

    async def ensure_not_frozen(self) -> None:
        """Ensure system is not frozen before proceeding.

        Call this before any write operation to enforce FR41.

        Raises:
            SystemCeasedError: If system is frozen (never retry!).
        """
        if not await self._freeze_checker.is_frozen():
            return

        # System is frozen - get details for the error
        details = await self._freeze_checker.get_freeze_details()

        log = logger.bind(operation="freeze_check")

        if details:
            log.critical(
                "write_rejected_system_frozen",
                ceased_at=details.ceased_at.isoformat(),
                final_sequence=details.final_sequence_number,
                reason=details.reason,
                message="FR41: System ceased - writes frozen",
            )
            raise SystemCeasedError.from_details(details)
        else:
            # Frozen but no details (shouldn't happen, but handle it)
            ceased_at = await self._freeze_checker.get_ceased_at()
            final_seq = await self._freeze_checker.get_final_sequence()

            log.critical(
                "write_rejected_system_frozen",
                ceased_at=ceased_at.isoformat() if ceased_at else "unknown",
                final_sequence=final_seq,
                message="FR41: System ceased - writes frozen",
            )
            raise SystemCeasedError(
                message="FR41: System ceased - writes frozen",
                ceased_at=ceased_at,
                final_sequence_number=final_seq,
            )

    async def get_freeze_status(self) -> CeasedStatusHeader | None:
        """Get freeze status for read responses.

        Returns a CeasedStatusHeader if the system is frozen,
        or None if the system is operational.

        This should be called for all read responses to include
        the system status header per AC6.

        Returns:
            CeasedStatusHeader if frozen, None otherwise.
        """
        if not await self._freeze_checker.is_frozen():
            return None

        details = await self._freeze_checker.get_freeze_details()

        if details:
            return CeasedStatusHeader.from_cessation_details(details)

        # Frozen but no details - construct from individual methods
        ceased_at = await self._freeze_checker.get_ceased_at()
        final_seq = await self._freeze_checker.get_final_sequence()

        if ceased_at and final_seq:
            return CeasedStatusHeader.ceased(
                ceased_at=ceased_at,
                final_sequence_number=final_seq,
                reason="System ceased",
            )

        return None

    @asynccontextmanager
    async def for_operation(
        self,
        operation: str,
    ) -> AsyncGenerator[None, None]:
        """Context manager for operations that require freeze check.

        Use this to wrap write operations with automatic freeze checking
        and specific operation context in the error.

        Args:
            operation: Name of the operation being performed.

        Yields:
            None if not frozen.

        Raises:
            CeasedWriteAttemptError: If system is frozen.

        Example:
            async with freeze_guard.for_operation("write_event"):
                await event_store.append(event)
        """
        if not await self._freeze_checker.is_frozen():
            yield
            return

        # System is frozen - get details and raise operation-specific error
        details = await self._freeze_checker.get_freeze_details()

        log = logger.bind(operation=operation)

        if details:
            log.critical(
                "operation_rejected_system_frozen",
                ceased_at=details.ceased_at.isoformat(),
                final_sequence=details.final_sequence_number,
                reason=details.reason,
                message=f"FR41: Operation '{operation}' rejected - system ceased",
            )
            raise CeasedWriteAttemptError.for_operation(
                operation=operation,
                ceased_at=details.ceased_at,
                final_sequence_number=details.final_sequence_number,
            )
        else:
            ceased_at = await self._freeze_checker.get_ceased_at()
            final_seq = await self._freeze_checker.get_final_sequence()

            log.critical(
                "operation_rejected_system_frozen",
                ceased_at=ceased_at.isoformat() if ceased_at else "unknown",
                final_sequence=final_seq,
                message=f"FR41: Operation '{operation}' rejected - system ceased",
            )

            if ceased_at and final_seq:
                raise CeasedWriteAttemptError.for_operation(
                    operation=operation,
                    ceased_at=ceased_at,
                    final_sequence_number=final_seq,
                )
            else:
                raise SystemCeasedError("FR41: System ceased - writes frozen")
