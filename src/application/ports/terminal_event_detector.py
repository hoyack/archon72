"""Terminal event detection port (Story 7.3, FR40, NFR40).

This module defines the protocol for detecting system termination state.
The TerminalEventDetectorProtocol provides the interface for checking
whether the system has been permanently terminated via a cessation event.

Constitutional Constraints:
- FR40: No cessation_reversal event type in schema
- NFR40: Cessation reversal is architecturally prohibited
- CT-11: Silent failure destroys legitimacy -> Terminal state must be checked
- CT-13: Integrity outranks availability -> Terminate > Continue after cessation

Developer Golden Rules:
1. TERMINAL FIRST - Check termination BEFORE halt state
2. FAIL LOUD - Raise SchemaIrreversibilityError for post-cessation writes
3. WITNESS EVERYTHING - Log all terminal state checks
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from src.domain.events.event import Event


class TerminalEventDetectorProtocol(Protocol):
    """Protocol for detecting system termination state (FR40, NFR40).

    This protocol defines the interface for checking whether the system
    has been permanently terminated via a CESSATION_EXECUTED event.

    Constitutional Constraint (NFR40):
    Cessation is architecturally irreversible. Once is_system_terminated()
    returns True, it MUST always return True. There is no reversal.

    Implementers MUST:
    1. Return True once a terminal event has been detected
    2. Never return False after returning True (permanent state)
    3. Handle concurrent access safely (terminal state is monotonic)

    Usage in EventWriterService:
        # TERMINAL FIRST (before halt check)
        if await terminal_detector.is_system_terminated():
            terminal_event = await terminal_detector.get_terminal_event()
            raise SchemaIrreversibilityError(
                f"NFR40: Cannot write events after cessation. "
                f"System terminated at seq {terminal_event.sequence}"
            )

    The check order in EventWriterService MUST be:
    1. Terminal check (this protocol)
    2. Halt check
    3. Writer lock check
    4. Startup verification check
    5. Actual write
    """

    async def is_system_terminated(self) -> bool:
        """Check if system has been terminated via cessation event.

        Constitutional Constraint (NFR40):
        Once this method returns True, it MUST always return True.
        Terminal state is permanent and irreversible.

        This check should be performed BEFORE the halt state check
        in EventWriterService, because:
        - Cessation is permanent; halt is temporary
        - A halted system can be unhalted; a ceased system cannot
        - Terminal state supersedes all other states

        Returns:
            True if a CESSATION_EXECUTED event has been recorded,
            False otherwise.
        """
        ...

    async def get_terminal_event(self) -> Event | None:
        """Get the terminal event (CESSATION_EXECUTED) if one exists.

        This method returns the actual cessation event that terminated
        the system, or None if the system has not been terminated.

        The returned event can be used for:
        - Logging the termination details in error messages
        - Extracting the final sequence number
        - Verifying the termination was properly witnessed

        Returns:
            The CESSATION_EXECUTED Event if system is terminated,
            None otherwise.
        """
        ...

    async def get_termination_timestamp(self) -> datetime | None:
        """Get the timestamp when system was terminated.

        Returns the execution_timestamp from the CESSATION_EXECUTED
        payload, or None if the system has not been terminated.

        This timestamp is useful for:
        - Error messages ("System terminated at {timestamp}")
        - Audit logs
        - Determining how long the system has been terminated

        Returns:
            The datetime when cessation occurred (UTC),
            or None if system has not been terminated.
        """
        ...
