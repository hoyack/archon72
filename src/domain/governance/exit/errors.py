"""Exit-related errors for consent-based governance.

Story: consent-gov-7.1: Exit Request Processing

This module defines errors related to exit processing, particularly
the ExitBarrierError which serves as a code smell detector.

Design Philosophy:
- ExitBarrierError should never be raised in production
- Its existence is to catch code that attempts to add barriers
- Raising this error indicates constitutional violation
"""


class ExitBarrierError(ValueError):
    """Raised when code attempts to add an exit barrier.

    This error is a CODE SMELL DETECTOR. If this error is raised,
    it indicates that code is attempting to violate NFR-EXIT-01
    by adding barriers to the exit process.

    Barriers that trigger this error:
    - Adding confirmation prompts ("are you sure?")
    - Adding waiting periods
    - Adding penalty warnings
    - Requiring justification
    - Adding multi-step verification

    Per Golden Rule: Exit is an unconditional right.
    Per NFR-EXIT-01: Exit completes in ≤2 message round-trips.

    Example:
        def confirm_exit(self) -> bool:
            '''This method should not exist.'''
            raise ExitBarrierError(
                "Confirmation prompts violate NFR-EXIT-01"
            )
    """

    def __init__(self, barrier_description: str) -> None:
        """Initialize ExitBarrierError.

        Args:
            barrier_description: Description of the barrier that was attempted.
        """
        self.barrier_description = barrier_description
        super().__init__(
            f"NFR-EXIT-01 VIOLATION: Attempted to add exit barrier - "
            f"{barrier_description}. Exit must be immediate and unconditional."
        )


class ExitNotFoundError(ValueError):
    """Raised when an exit request is not found.

    Used when looking up an exit request by ID that doesn't exist.
    """

    def __init__(self, request_id: str) -> None:
        """Initialize ExitNotFoundError.

        Args:
            request_id: ID of the exit request that was not found.
        """
        self.request_id = request_id
        super().__init__(f"Exit request not found: {request_id}")


class AlreadyExitedError(ValueError):
    """Raised when a Cluster that has already exited attempts to exit again.

    This is not a barrier - it's a logical error. A Cluster that has
    already exited cannot exit again.
    """

    def __init__(self, cluster_id: str) -> None:
        """Initialize AlreadyExitedError.

        Args:
            cluster_id: ID of the Cluster that has already exited.
        """
        self.cluster_id = cluster_id
        super().__init__(
            f"Cluster {cluster_id} has already exited and cannot exit again"
        )
