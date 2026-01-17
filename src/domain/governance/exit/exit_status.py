"""Exit status enumeration for consent-based governance.

Story: consent-gov-7.1: Exit Request Processing

This module defines the ExitStatus enumeration for tracking exit request progress.
Exit processing is designed to be simple with minimal states.

Design Principles:
- Only 3 states needed (initiated, processing, completed)
- No "pending review" or "awaiting approval" states
- No states that could be used to delay or block exit
"""

from enum import Enum


class ExitStatus(str, Enum):
    """Status of an exit request.

    Exit processing is intentionally simple:
    - INITIATED: Request received (round-trip 1)
    - PROCESSING: System handling obligations
    - COMPLETED: Exit finished (round-trip 2)

    There is no:
    - PENDING_REVIEW: Would allow blocking
    - AWAITING_APPROVAL: Would require permission
    - CANCELLED: Exit cannot be cancelled once initiated
    - REJECTED: Exit cannot be rejected
    """

    INITIATED = "initiated"
    """Exit request received from Cluster. Processing begins immediately."""

    PROCESSING = "processing"
    """System is releasing obligations and preserving contributions.

    This is a transient state that exists only during processing.
    External systems should never see this state - it exists only
    for internal tracking.
    """

    COMPLETED = "completed"
    """Exit successfully completed. Cluster has left the system.

    Final state. Cluster data is preserved but no further
    interactions will occur.
    """

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal state.

        Only COMPLETED is terminal.
        """
        return self == ExitStatus.COMPLETED

    @property
    def allows_interaction(self) -> bool:
        """Check if this status allows further interaction.

        Once exit is initiated, no further interaction is allowed.
        This prevents barriers like "are you sure?" prompts.
        """
        return False  # No interaction allowed at any exit stage
