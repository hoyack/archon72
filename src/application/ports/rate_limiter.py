"""Rate Limiter Port for per-submitter petition rate limiting (Story 1.4, FR-1.5, HC-4).

This module defines the abstract interface for checking per-submitter rate limits
using PostgreSQL time-bucket counters per architecture decision D4.

Constitutional Constraints:
- FR-1.5: Enforce rate limits per submitter_id
- HC-4: 10 petitions/user/hour (configurable)
- NFR-5.1: Rate limiting per identity: Configurable per type
- D4: PostgreSQL time-bucket counters with minute buckets summed over sliding window
- CT-11: Silent failure destroys legitimacy - return 429, never silently drop

Developer Golden Rules:
1. RATE LIMIT AFTER CAPACITY - Check rate limit AFTER queue capacity check (more specific)
2. RECORD AFTER SUCCESS - Only increment rate limit counter after successful submission
3. FAIL LOUD - Return 429 with full rate limit info, never silently drop
4. WITNESS BLOCKS - Rate limit blocks are governance-relevant events (per D4)
5. D4 COMPLIANCE - Use PostgreSQL time-bucket counters, NOT Redis or in-memory
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True)
class RateLimitResult:
    """Result of rate limit check (Story 1.4, AC1).

    Attributes:
        allowed: Whether the submission is allowed (under rate limit).
        remaining: Number of submissions remaining before rate limit.
        reset_at: UTC datetime when the rate limit window resets.
        current_count: Current number of submissions in the window.
        limit: Configured rate limit per hour.
    """

    allowed: bool
    remaining: int
    reset_at: datetime
    current_count: int
    limit: int


@runtime_checkable
class RateLimiterPort(Protocol):
    """Protocol for checking per-submitter rate limits (Story 1.4, FR-1.5, HC-4).

    Implementations must use PostgreSQL time-bucket counters per architecture
    decision D4. Minute buckets are summed over the sliding window (default 60 min).

    Constitutional Constraints:
    - FR-1.5: Enforce rate limits per submitter_id
    - HC-4: 10 petitions/user/hour (configurable)
    - NFR-5.1: Rate limiting per identity
    - D4: PostgreSQL time-bucket counters
    - CT-11: Fail loud, not silent

    Usage:
        rate_result = await rate_limiter.check_rate_limit(submitter_id)
        if not rate_result.allowed:
            raise HTTPException(
                status_code=429,
                headers={"Retry-After": str(retry_after_seconds)},
            )

        # After successful submission:
        await rate_limiter.record_submission(submitter_id)
    """

    async def check_rate_limit(self, submitter_id: UUID) -> RateLimitResult:
        """Check if submitter is within rate limit using sliding window.

        Uses minute buckets summed over the configured window (default 60 minutes)
        per architecture decision D4.

        Args:
            submitter_id: UUID of the submitter to check.

        Returns:
            RateLimitResult with:
            - allowed: True if under limit, False if at/over limit
            - remaining: Number of submissions remaining
            - reset_at: When the window resets (oldest bucket expires)
            - current_count: Current submissions in window
            - limit: Configured limit

        Note:
            Rate limit blocks should be witnessed as governance-relevant events
            per D4 architecture decision.
        """
        ...

    async def record_submission(self, submitter_id: UUID) -> None:
        """Record a submission against the submitter's rate limit.

        CRITICAL: Must be called AFTER successful submission persistence,
        not before. This ensures we don't count failed submissions.

        Increments the current minute bucket for the submitter using UPSERT:
        INSERT ... ON CONFLICT (submitter_id, bucket_minute) DO UPDATE SET count = count + 1

        Args:
            submitter_id: UUID of the submitter who submitted.
        """
        ...

    async def get_remaining(self, submitter_id: UUID) -> int:
        """Get remaining submissions in current window.

        Convenience method that calls check_rate_limit and returns just
        the remaining count.

        Args:
            submitter_id: UUID of the submitter to check.

        Returns:
            Number of submissions remaining before rate limit.
        """
        ...

    def get_limit(self) -> int:
        """Get configured rate limit per hour.

        Returns:
            Maximum submissions per submitter per hour (default: 10 per HC-4).
        """
        ...

    def get_window_minutes(self) -> int:
        """Get configured sliding window size in minutes.

        Returns:
            Window size in minutes (default: 60).
        """
        ...
