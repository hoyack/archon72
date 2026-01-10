"""Cessation flag repository port (Story 7.4, FR41, ADR-3).

This module defines the protocol for dual-channel cessation flag storage.
The CessationFlagRepositoryProtocol provides the interface for setting
and checking cessation state in both Redis and database.

Constitutional Constraints:
- FR41: Freeze on new actions except record preservation
- ADR-3: Dual-channel pattern for resilience
- CT-11: Silent failure destroys legitimacy -> Check both channels

This mirrors the HaltFlagRepository pattern from Story 3.3, but for
permanent cessation state rather than temporary halt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from src.domain.models.ceased_status_header import CessationDetails


class CessationFlagRepositoryProtocol(Protocol):
    """Protocol for dual-channel cessation flag storage (FR41, ADR-3).

    This protocol defines the interface for storing and checking
    cessation state in both Redis (fast) and database (durable).

    Constitutional Constraint (ADR-3):
    The flag MUST be set in BOTH channels atomically.
    If one channel fails, the operation should fail entirely.

    Permanent State (NFR40):
    Once set_ceased() succeeds, the flag cannot be unset.
    There is no clear_ceased() method by design.

    Implementers MUST:
    1. Set flag in both Redis and database
    2. Fail if either channel fails (atomic semantics)
    3. Return True from is_ceased() if EITHER channel has flag set
    4. Never provide a method to clear the ceased flag

    Usage:
        # Setting cessation (one-time, irreversible)
        await repo.set_ceased(details)

        # Checking cessation (fast path via Redis)
        if await repo.is_ceased():
            details = await repo.get_cessation_details()
    """

    async def set_ceased(self, details: CessationDetails) -> None:
        """Set the cessation flag in both channels.

        Constitutional Constraint (ADR-3):
        This MUST set the flag in BOTH Redis AND database.
        The operation should be as atomic as possible.

        Permanent State (NFR40):
        Once this method succeeds, the cessation state is permanent.
        There is no way to undo this operation.

        Args:
            details: CessationDetails containing all cessation information.

        Raises:
            CessationFlagWriteError: If flag cannot be set in either channel.
        """
        ...

    async def is_ceased(self) -> bool:
        """Check if cessation flag is set in either channel.

        This should check Redis first (fast path), then fall back
        to database if Redis is unavailable.

        Constitutional Constraint (ADR-3):
        Return True if EITHER channel has the flag set.
        This ensures cessation state is detected even with
        partial system availability.

        Returns:
            True if cessation flag is set in either channel,
            False otherwise.
        """
        ...

    async def get_cessation_details(self) -> CessationDetails | None:
        """Get cessation details from the repository.

        Returns the full CessationDetails if the system has ceased,
        or None if cessation has not occurred.

        Should try Redis first (fast path), then database.

        Returns:
            CessationDetails if cessation has occurred,
            None otherwise.
        """
        ...
