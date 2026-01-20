"""Co-sign rate limit errors (Story 5.4, FR-6.6, SYBIL-1).

This module defines errors for per-signer co-sign rate limiting.

Constitutional Constraints:
- FR-6.6: System SHALL apply SYBIL-1 rate limiting per signer
- NFR-5.1: Rate limiting per identity: Configurable per type
- CT-11: Silent failure destroys legitimacy (return 429, not drop)
- D4: PostgreSQL time-bucket counters
- SYBIL-1: Identity verification + rate limiting per verified identity
"""

from datetime import datetime
from uuid import UUID

from src.domain.errors.constitutional import ConstitutionalViolationError


class CoSignRateLimitExceededError(ConstitutionalViolationError):
    """Raised when signer exceeds co-sign rate limit (FR-6.6, SYBIL-1).

    This error triggers a 429 response with Retry-After header.
    The client should wait until reset_at before retrying.

    Constitutional Constraints:
    - FR-6.6: System SHALL apply SYBIL-1 rate limiting per signer
    - NFR-5.1: Rate limiting per identity: Configurable per type
    - CT-11: Fail loud, not silent drop
    - D4: Rate limit tracked via PostgreSQL time-bucket counters
    - SYBIL-1: Prevent flood attacks via identity rate limiting

    Attributes:
        signer_id: UUID of the rate-limited signer.
        current_count: Current co-signs in the window.
        limit: Configured maximum per window.
        reset_at: UTC datetime when window resets.
        retry_after_seconds: Suggested retry delay in seconds.
    """

    def __init__(
        self,
        signer_id: UUID,
        current_count: int,
        limit: int,
        reset_at: datetime,
        retry_after_seconds: int = 1800,  # 30 minutes default
    ) -> None:
        """Initialize co-sign rate limit exceeded error.

        Args:
            signer_id: UUID of the signer hitting the limit.
            current_count: Current co-sign count in window.
            limit: Maximum co-signs allowed per window.
            reset_at: UTC datetime when the rate limit resets.
            retry_after_seconds: Suggested client retry delay.
        """
        self.signer_id = signer_id
        self.current_count = current_count
        self.limit = limit
        self.reset_at = reset_at
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"FR-6.6: Co-sign rate limit exceeded for signer {signer_id}: "
            f"{current_count}/{limit} co-signs. "
            f"Resets at {reset_at.isoformat()}."
        )
