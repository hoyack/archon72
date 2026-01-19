"""Queue overflow errors for petition submission (Story 1.3, FR-1.4).

This module defines errors for petition queue capacity protection.

Constitutional Constraints:
- FR-1.4: Return HTTP 503 on queue overflow (no silent drop)
- NFR-3.1: No silent petition loss
- CT-11: Silent failure destroys legitimacy
"""

from src.domain.errors.constitutional import ConstitutionalViolationError


class QueueOverflowError(ConstitutionalViolationError):
    """Raised when petition queue exceeds capacity threshold (FR-1.4).

    This error triggers a 503 response with Retry-After header.
    The client should retry after the specified delay.

    Constitutional Constraints:
    - FR-1.4: System SHALL return HTTP 503 when queue overwhelmed
    - NFR-3.1: No silent petition loss (fail loud, don't drop)
    - CT-11: Silent failure destroys legitimacy

    Attributes:
        queue_depth: Current number of pending petitions.
        threshold: Configured maximum capacity.
        retry_after_seconds: Suggested retry delay.
    """

    def __init__(
        self,
        queue_depth: int,
        threshold: int,
        retry_after_seconds: int = 60,
    ) -> None:
        """Initialize queue overflow error.

        Args:
            queue_depth: Current pending petition count.
            threshold: Maximum capacity before overflow.
            retry_after_seconds: Suggested client retry delay.
        """
        self.queue_depth = queue_depth
        self.threshold = threshold
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Petition queue at capacity ({queue_depth}/{threshold}). "
            f"Retry after {retry_after_seconds} seconds."
        )
