"""Event emission errors for petition fate events (Story 1.7, FR-2.5).

This module defines errors for event emission failures during fate assignment.

Constitutional Constraints:
- FR-2.5: System SHALL emit fate event in same transaction as state update
- HC-1: Fate transition requires witness event - NO silent fate assignment
- NFR-3.3: Event witnessing: 100% fate events persisted [CRITICAL]
"""

from __future__ import annotations

from uuid import UUID


class FateEventEmissionError(Exception):
    """Raised when fate event emission fails during transactional fate assignment.

    This error indicates that a petition's state was successfully updated to a
    terminal fate, but the corresponding fate event could not be emitted.
    The caller MUST rollback the state change when this occurs.

    Constitutional Constraints:
    - FR-2.5: Event SHALL be emitted in same transaction as state update
    - HC-1: Fate transition requires witness event - NO silent fate assignment
    - NFR-3.3: 100% fate events persisted [CRITICAL]

    Attributes:
        petition_id: UUID of the petition.
        new_state: The fate state that was being assigned.
        cause: The underlying exception that caused emission failure.
    """

    def __init__(
        self,
        petition_id: UUID,
        new_state: str,
        cause: Exception,
    ) -> None:
        """Initialize fate event emission error.

        Args:
            petition_id: UUID of the petition.
            new_state: The terminal fate state (ACKNOWLEDGED/REFERRED/ESCALATED/DEFERRED/NO_RESPONSE).
            cause: The underlying exception from event emission.
        """
        self.petition_id = petition_id
        self.new_state = new_state
        self.cause = cause
        super().__init__(
            f"Failed to emit fate event for petition {petition_id}. "
            f"State change to {new_state} will be rolled back. "
            f"Cause: {type(cause).__name__}: {cause}"
        )
