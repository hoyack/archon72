"""Freeze state checker port (Story 7.4, FR41).

This module defines the protocol for checking system freeze state
after cessation. The FreezeCheckerProtocol provides the interface
for determining whether the system has been permanently frozen.

Constitutional Constraints:
- FR41: Freeze on new actions except record preservation
- CT-11: Silent failure destroys legitimacy -> Freeze state must be checked
- CT-13: Integrity outranks availability -> Freeze > Continue after cessation

Developer Golden Rules:
1. FREEZE SECOND - Check freeze AFTER terminal check (Story 7.3)
2. FAIL LOUD - Raise SystemCeasedError for post-cessation writes
3. READ ALWAYS - Read operations must succeed with status header
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from src.domain.models.ceased_status_header import CessationDetails


class FreezeCheckerProtocol(Protocol):
    """Protocol for checking system freeze state (FR41).

    This protocol defines the interface for checking whether the system
    is in a frozen (ceased) state after a CESSATION_EXECUTED event.

    Constitutional Constraint (FR41):
    Once is_frozen() returns True, it MUST always return True.
    Freeze state is permanent and irreversible (per NFR40).

    Implementers MUST:
    1. Return True once system has been frozen
    2. Never return False after returning True (permanent state)
    3. Handle concurrent access safely (freeze state is monotonic)

    Usage in EventWriterService:
        # After terminal check (Story 7.3)
        if await freeze_checker.is_frozen():
            details = await freeze_checker.get_freeze_details()
            raise SystemCeasedError.from_details(details)

    The check order in EventWriterService MUST be:
    1. Terminal check (Story 7.3) - cessation event exists
    2. Freeze check (this protocol) - operational freeze in effect
    3. Halt check - temporary halt state
    4. Writer lock check
    5. Startup verification check
    6. Actual write
    """

    async def is_frozen(self) -> bool:
        """Check if system is in frozen (ceased) state.

        Constitutional Constraint (FR41):
        Once this method returns True, it MUST always return True.
        Freeze state is permanent and irreversible.

        This check should be performed AFTER the terminal check
        in EventWriterService, because:
        - Terminal check verifies cessation event exists (Story 7.3)
        - Freeze check verifies operational freeze is in effect (Story 7.4)

        Returns:
            True if system is frozen after cessation,
            False otherwise.
        """
        ...

    async def get_freeze_details(self) -> CessationDetails | None:
        """Get details about the freeze state.

        Returns cessation details if the system is frozen,
        or None if the system has not been frozen.

        The returned details can be used for:
        - Creating SystemCeasedError with full context
        - Including in API response headers
        - Logging freeze state information

        Returns:
            CessationDetails if system is frozen,
            None otherwise.
        """
        ...

    async def get_ceased_at(self) -> datetime | None:
        """Get the timestamp when system was frozen.

        Returns the ceased_at timestamp from the cessation details,
        or None if the system has not been frozen.

        Returns:
            The datetime when cessation occurred (UTC),
            or None if system has not been frozen.
        """
        ...

    async def get_final_sequence(self) -> int | None:
        """Get the final sequence number at freeze time.

        Returns the final_sequence_number from the cessation details,
        or None if the system has not been frozen.

        This is the sequence number of the CESSATION_EXECUTED event,
        which is the last valid event in the store.

        Returns:
            The final sequence number,
            or None if system has not been frozen.
        """
        ...
