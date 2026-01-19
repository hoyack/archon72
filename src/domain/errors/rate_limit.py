"""Rate limit errors for petition submission (Story 1.4, FR-1.5, HC-4).

This module defines errors for per-submitter rate limiting.

Constitutional Constraints:
- FR-1.5: Enforce rate limits per submitter_id
- HC-4: 10 petitions/user/hour (configurable)
- NFR-5.1: Rate limiting per identity
- CT-11: Silent failure destroys legitimacy (return 429, not drop)
- D4: PostgreSQL time-bucket counters
"""

from datetime import datetime
from uuid import UUID

from src.domain.errors.constitutional import ConstitutionalViolationError


class RateLimitExceededError(ConstitutionalViolationError):
    """Raised when submitter exceeds petition rate limit (FR-1.5, HC-4).

    This error triggers a 429 response with Retry-After header.
    The client should wait until reset_at before retrying.

    Constitutional Constraints:
    - FR-1.5: Enforce rate limits per submitter_id
    - HC-4: 10 petitions/user/hour (configurable)
    - NFR-5.1: Rate limiting per identity
    - CT-11: Fail loud, not silent drop
    - D4: Rate limit tracked via PostgreSQL time-bucket counters

    Attributes:
        submitter_id: UUID of the rate-limited submitter.
        current_count: Current submissions in the window.
        limit: Configured maximum per window.
        reset_at: UTC datetime when window resets.
        retry_after_seconds: Suggested retry delay in seconds.
    """

    def __init__(
        self,
        submitter_id: UUID,
        current_count: int,
        limit: int,
        reset_at: datetime,
        retry_after_seconds: int = 1800,  # 30 minutes default
    ) -> None:
        """Initialize rate limit exceeded error.

        Args:
            submitter_id: UUID of the submitter hitting the limit.
            current_count: Current submission count in window.
            limit: Maximum submissions allowed per window.
            reset_at: UTC datetime when the rate limit resets.
            retry_after_seconds: Suggested client retry delay.
        """
        self.submitter_id = submitter_id
        self.current_count = current_count
        self.limit = limit
        self.reset_at = reset_at
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Rate limit exceeded for submitter {submitter_id}: "
            f"{current_count}/{limit} petitions. "
            f"Resets at {reset_at.isoformat()}."
        )
