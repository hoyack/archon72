"""Concurrent modification error for atomic CAS operations (Story 1.6, FR-2.4).

This module defines the error for concurrent modification detection
in optimistic locking scenarios, specifically fate assignment CAS.

Constitutional Constraints:
- FR-2.4: System SHALL use atomic CAS for fate assignment (no double-fate)
- NFR-3.2: Fate assignment atomicity: 100% single-fate [CRITICAL]
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from src.domain.errors.constitutional import ConstitutionalViolationError

if TYPE_CHECKING:
    from src.domain.models.petition_submission import PetitionState


class ConcurrentModificationError(ConstitutionalViolationError):
    """Raised when CAS operation fails due to concurrent modification (FR-2.4).

    This error is raised when an atomic compare-and-swap operation fails
    because the expected state no longer matches the current state. This
    indicates another process has modified the petition concurrently.

    Constitutional Constraints:
    - FR-2.4: System SHALL use atomic CAS for fate assignment (no double-fate)
    - NFR-3.2: Fate assignment atomicity: 100% single-fate [CRITICAL]

    This is a recoverable error - the caller should re-read the petition
    and decide whether to retry or abort.

    Attributes:
        petition_id: UUID of the petition that was being modified.
        expected_state: The state that was expected to be current.
        operation: Description of the operation that failed (e.g., "fate_assignment").
    """

    def __init__(
        self,
        petition_id: UUID,
        expected_state: PetitionState,
        operation: str = "fate_assignment",
    ) -> None:
        """Initialize concurrent modification error.

        Args:
            petition_id: UUID of the petition being modified.
            expected_state: The state expected for the CAS operation.
            operation: Description of the failed operation.
        """
        self.petition_id = petition_id
        self.expected_state = expected_state
        self.operation = operation
        super().__init__(
            f"Concurrent modification detected for petition {petition_id} "
            f"during {operation}. Expected state: {expected_state.value}. "
            "Another process has modified this petition."
        )
